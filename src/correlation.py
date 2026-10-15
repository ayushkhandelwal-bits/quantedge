"""Correlation and regime dynamics for daily returns.

Methods
-------
* Returns: simple daily returns computed per instrument on its own trading days, then aligned by
  date. Pairs use **pairwise-complete** observations (dates where both instruments traded); the number
  of observations behind every coefficient is reported. Nothing is forward-filled into returns.
* Coefficients: Pearson (linear) or Spearman (rank, robust to outliers).
* Uncertainty: Fisher z-transform 95% confidence intervals and p-values (H0: ρ = 0); a Fisher z-test
  compares a correlation between two regimes. Daily returns are not perfectly independent (volatility
  clusters), so intervals are approximate.
* Rolling correlation and beta use a trailing window ending on each date (no look-ahead).
* Regimes are defined on NIFTY 50 (see pattern_validation.market_regime): Bullish (close above
  200-session average), Bearish (below), and High volatility (20-session volatility above the 75th percentile of
  its own history to date), which overrides the trend label.
* Correlation describes co-movement only. It does not establish causation; a common driver
  (rates, global risk appetite, sector news) can make two series move together.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
from scipy import stats


def returns_panel(closes: dict[str, pd.Series]) -> pd.DataFrame:
    """Daily simple returns, one column per instrument, outer-aligned by date (NaN where not traded)."""
    rets = {k: v.sort_index().pct_change() for k, v in closes.items()}
    return pd.DataFrame(rets).dropna(how="all")


def pair_n(rets: pd.DataFrame) -> pd.DataFrame:
    m = rets.notna().astype(int)
    return m.T @ m


def corr_matrix(rets: pd.DataFrame, method: str = "pearson", min_periods: int = 30) -> pd.DataFrame:
    return rets.corr(method=method, min_periods=min_periods)


def fisher_ci(r: float, n: int, conf: float = 0.95) -> tuple[float, float]:
    if n is None or n < 4 or r is None or math.isnan(r) or abs(r) >= 1:
        return (math.nan, math.nan)
    z = np.arctanh(r)
    se = 1 / math.sqrt(n - 3)
    zc = stats.norm.ppf(0.5 + conf / 2)
    return (float(np.tanh(z - zc * se)), float(np.tanh(z + zc * se)))


def corr_pvalue(r: float, n: int) -> float:
    if n is None or n < 4 or math.isnan(r) or abs(r) >= 1:
        return math.nan
    t = r * math.sqrt((n - 2) / (1 - r**2))
    return float(2 * stats.t.sf(abs(t), n - 2))


def fisher_diff_test(r1: float, n1: int, r2: float, n2: int) -> float:
    """Two-sided p-value for H0: two independent correlations are equal."""
    if min(n1, n2) < 4 or any(math.isnan(x) for x in (r1, r2)):
        return math.nan
    z = (np.arctanh(r1) - np.arctanh(r2)) / math.sqrt(1 / (n1 - 3) + 1 / (n2 - 3))
    return float(2 * stats.norm.sf(abs(z)))


def vs_benchmark(rets: pd.DataFrame, bench: str, method: str = "pearson") -> pd.DataFrame:
    """Correlation and beta of each instrument with the benchmark, with n, CI and p-value."""
    rows = []
    for col in rets.columns:
        if col == bench:
            continue
        pair = rets[[col, bench]].dropna()
        n = len(pair)
        if n < 30:
            rows.append({"Instrument": col, "Observations": n})
            continue
        r = pair[col].corr(pair[bench], method=method)
        lo, hi = fisher_ci(r, n)
        beta = pair[col].cov(pair[bench]) / pair[bench].var()
        rows.append({"Instrument": col, "Observations": n, "Correlation": r, "CI low": lo, "CI high": hi,
                     "p-value": corr_pvalue(r, n), "Beta": beta, "R²": r**2 if method == "pearson" else math.nan})
    return pd.DataFrame(rows)


def rolling_corr(rets: pd.DataFrame, a: str, b: str, window: int = 63) -> pd.Series:
    pair = rets[[a, b]].dropna()
    return pair[a].rolling(window, min_periods=window).corr(pair[b]).rename(a)


def rolling_beta(rets: pd.DataFrame, a: str, b: str, window: int = 63) -> pd.Series:
    pair = rets[[a, b]].dropna()
    cov = pair[a].rolling(window, min_periods=window).cov(pair[b])
    return (cov / pair[b].rolling(window, min_periods=window).var()).rename(a)


def by_regime(rets: pd.DataFrame, regime: pd.Series, bench: str, method: str = "pearson") -> pd.DataFrame:
    """Correlation with the benchmark inside each regime, with n, CI and a test against 'all days'."""
    reg = regime.reindex(rets.index)
    rows = []
    for col in rets.columns:
        if col == bench:
            continue
        all_pair = rets[[col, bench]].dropna()
        r_all = all_pair[col].corr(all_pair[bench], method=method) if len(all_pair) >= 30 else math.nan
        for lab in sorted(reg.dropna().unique()):
            if lab == "Insufficient history":
                continue
            pair = rets.loc[reg == lab, [col, bench]].dropna()
            n = len(pair)
            r = pair[col].corr(pair[bench], method=method) if n >= 30 else math.nan
            lo, hi = fisher_ci(r, n)
            rows.append({"Instrument": col, "Regime": lab, "Observations": n, "Correlation": r, "CI low": lo, "CI high": hi,
                         "All-days correlation": r_all,
                         "p-value vs all days": fisher_diff_test(r, n, r_all, len(all_pair)) if n >= 30 else math.nan})
    return pd.DataFrame(rows)


def regime_matrices(rets: pd.DataFrame, regime: pd.Series, method: str = "pearson") -> dict[str, tuple[pd.DataFrame, int]]:
    reg = regime.reindex(rets.index)
    out = {}
    for lab in sorted(reg.dropna().unique()):
        if lab == "Insufficient history":
            continue
        sub = rets[reg == lab]
        out[lab] = (sub.corr(method=method, min_periods=30), int(sub.dropna().shape[0]))
    return out


def portfolio_risk(rets: pd.DataFrame, weights: pd.Series | None = None, corr: pd.DataFrame | None = None) -> dict:
    """Annualised volatility of a portfolio vs the weighted average of its members' volatilities.

    If ``corr`` is given, member volatilities come from ``rets`` but the correlation structure is
    replaced by ``corr`` – used to ask "what if correlations behaved as in regime X?".
    """
    data = rets.dropna()
    cols = list(data.columns)
    w = (weights.reindex(cols).fillna(0) if weights is not None else pd.Series(1 / len(cols), index=cols)).to_numpy()
    vol = data.std(ddof=1).to_numpy() * math.sqrt(252)
    c = (corr.loc[cols, cols].to_numpy() if corr is not None else data.corr().to_numpy())
    cov = np.outer(vol, vol) * c
    port = float(math.sqrt(max(w @ cov @ w, 0)))
    avg = float(w @ vol)
    avg_corr = float((c.sum() - len(cols)) / (len(cols) * (len(cols) - 1))) if len(cols) > 1 else math.nan
    return {"portfolio_vol": port, "weighted_avg_vol": avg, "diversification_ratio": avg / port if port > 0 else math.nan,
            "risk_reduction": 1 - port / avg if avg > 0 else math.nan, "avg_pairwise_corr": avg_corr, "observations": len(data)}
