"""Candlestick-pattern validation across stocks, regimes and correlation environments.

Research design
---------------
* Detection uses only sessions up to and including the signal date t (see candlestick_patterns).
* Entry: by default at the OPEN of t+1 (a signal is only known after t's close); optionally at t's
  close for comparison with the textbook convention.
* Outcome over horizon h: Close(t+h) / entry − 1. "Directional return" flips the sign for bearish
  patterns so that a positive number always means "the pattern was right".
* Adverse excursion (drawdown while waiting): worst move against the pattern between entry and t+h,
  using intraday lows (bullish) or highs (bearish) of sessions t+1 … t+h.
* Net return subtracts an assumed round-trip cost (default from the published cost schedule).
* Context attached to each event uses information available at t only: the stock's own trend regime,
  the NIFTY 50 regime, and the 63-session rolling correlation of the stock with NIFTY (ending at t).
* Uncertainty: Wilson 95% interval for hit rates, Student-t 95% interval for mean returns, an exact
  binomial test of the hit rate against the stock's own base rate, and Benjamini–Hochberg
  adjustment because many pattern × horizon tests are run at once.
* Out-of-sample: events are split chronologically (first X% of each stock's history vs the rest)
  and the edge is compared between the two periods.

Neutral patterns (Doji) have no direction, so directional statistics are not computed for them;
instead the size of the subsequent move is compared with the stock's typical move ("does
indecision precede larger moves?").
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
from scipy import stats

from src import candlestick_patterns as cp

HORIZONS = (1, 3, 5, 10)
CORR_WINDOW = 63
CORR_BUCKETS = ((-1.01, 0.3, "Low (< 0.3)"), (0.3, 0.6, "Medium (0.3–0.6)"), (0.6, 1.01, "High (≥ 0.6)"))
MIN_SAMPLE = 20


# ------------------------------------------------------------------ statistics helpers
def wilson_ci(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (math.nan, math.nan)
    p = successes / n
    denom = 1 + z**2 / n
    centre = (p + z**2 / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
    return (centre - half, centre + half)


def mean_ci(x: pd.Series, conf: float = 0.95) -> tuple[float, float]:
    x = x.dropna()
    n = len(x)
    if n < 2:
        return (math.nan, math.nan)
    m, se = x.mean(), x.std(ddof=1) / math.sqrt(n)
    t = stats.t.ppf(0.5 + conf / 2, n - 1)
    return (m - t * se, m + t * se)


def benjamini_hochberg(p: pd.Series) -> pd.Series:
    """BH false-discovery-rate adjusted p-values (q-values); NaNs are kept."""
    valid = p.dropna().sort_values()
    m = len(valid)
    if m == 0:
        return p * np.nan
    ranks = np.arange(1, m + 1)
    q = (valid.values * m / ranks)
    q = np.minimum.accumulate(q[::-1])[::-1]
    out = pd.Series(np.nan, index=p.index)
    out.loc[valid.index] = np.minimum(q, 1.0)
    return out


# ------------------------------------------------------------------ context series
def trend_regime(close: pd.Series, window: int = 200) -> pd.Series:
    ma = close.rolling(window, min_periods=window).mean()
    lab = pd.Series(np.where(close > ma, "Bullish", "Bearish"), index=close.index)
    return lab.where(ma.notna(), "Insufficient history")


def vol_regime(close: pd.Series, window: int = 20, quantile: float = 0.75) -> pd.Series:
    """High volatility = 20-session volatility above the 75th percentile of its own history up to that date."""
    vol = close.pct_change().rolling(window).std()
    med = vol.expanding(min_periods=window * 3).quantile(quantile)
    lab = pd.Series(np.where(vol > med, "High volatility", "Normal volatility"), index=close.index)
    return lab.where(med.notna(), "Insufficient history")


def market_regime(nifty_close: pd.Series) -> pd.Series:
    """Combined NIFTY regime used for comparisons: High volatility overrides trend."""
    t, v = trend_regime(nifty_close), vol_regime(nifty_close)
    lab = t.where(v != "High volatility", "High volatility")
    return lab.where((t != "Insufficient history") & (v != "Insufficient history"), "Insufficient history")


def rolling_corr(stock_close: pd.Series, bench_close: pd.Series, window: int = CORR_WINDOW) -> pd.Series:
    r = pd.concat([stock_close.pct_change(), bench_close.pct_change()], axis=1, join="inner").dropna()
    return r.iloc[:, 0].rolling(window, min_periods=window).corr(r.iloc[:, 1]).reindex(stock_close.index)


def corr_bucket(c: float) -> str:
    if c is None or (isinstance(c, float) and math.isnan(c)):
        return "Insufficient history"
    for lo, hi, lab in CORR_BUCKETS:
        if lo <= c < hi:
            return lab
    return "Insufficient history"


# ------------------------------------------------------------------ events
def stock_events(df: pd.DataFrame, symbol: str, params: cp.PatternParams | None = None, horizons=HORIZONS,
                 entry: str = "next_open", cost_pct: float = 0.0, bench_close: pd.Series | None = None,
                 oos_fraction: float = 0.3, patterns: list[str] | None = None) -> pd.DataFrame:
    """One row per pattern occurrence with forward outcomes and context. ``cost_pct`` is the
    round-trip cost as a fraction of notional (e.g. 0.0025 = 0.25%)."""
    params = params or cp.PatternParams()
    det = cp.detect(df, params)
    pats = patterns or list(cp.PATTERNS)
    o, h, l, c = df["Open"].to_numpy(), df["High"].to_numpy(), df["Low"].to_numpy(), df["Close"].to_numpy()
    n = len(df)
    idx = df.index
    split_at = idx[int(n * (1 - oos_fraction))] if 0 < oos_fraction < 1 and n > 10 else idx[-1]
    own_trend = trend_regime(df["Close"])
    own_vol = vol_regime(df["Close"])
    if bench_close is not None:
        b = bench_close.reindex(idx).ffill()
        mkt = market_regime(bench_close).reindex(idx).ffill().fillna("Insufficient history")
        rc = rolling_corr(df["Close"], bench_close)
    else:
        mkt = pd.Series("No benchmark", index=idx)
        rc = pd.Series(np.nan, index=idx)
    rows = []
    for name in pats:
        bias = cp.PATTERNS[name]["bias"]
        sign = 1 if bias == "Bullish" else -1 if bias == "Bearish" else 0
        for i in np.flatnonzero(det[name].to_numpy()):
            if entry == "next_open":
                if i + 1 >= n:
                    continue
                px_in = o[i + 1]
            else:
                px_in = c[i]
            r = {"Date": idx[i], "Instrument": symbol, "Pattern": name, "Bias": bias,
                 "Period": "In-sample" if idx[i] < split_at else "Out-of-sample",
                 "Stock trend": own_trend.iloc[i], "Stock volatility": own_vol.iloc[i],
                 "Market regime": mkt.iloc[i], "Corr with NIFTY": rc.iloc[i], "Correlation environment": corr_bucket(rc.iloc[i]),
                 "Entry price": px_in}
            for hz in horizons:
                j = i + hz
                if j >= n:
                    r[f"ret_{hz}d"] = np.nan
                    r[f"dir_{hz}d"] = np.nan
                    r[f"net_{hz}d"] = np.nan
                    r[f"mae_{hz}d"] = np.nan
                    continue
                ret = c[j] / px_in - 1
                r[f"ret_{hz}d"] = ret
                if sign != 0:
                    d = sign * ret
                    r[f"dir_{hz}d"] = d
                    r[f"net_{hz}d"] = d - cost_pct
                    win = slice(i + 1, j + 1)
                    r[f"mae_{hz}d"] = (l[win].min() / px_in - 1) if sign > 0 else -(h[win].max() / px_in - 1)
                else:
                    r[f"dir_{hz}d"] = r[f"net_{hz}d"] = r[f"mae_{hz}d"] = np.nan
                    r[f"absmove_{hz}d"] = abs(ret)
            rows.append(r)
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    return out.sort_values(["Date", "Pattern"]).reset_index(drop=True)


def base_rates(df: pd.DataFrame, horizons=HORIZONS, entry: str = "next_open") -> dict:
    """Unconditional outcomes for the same stock: share of up moves, mean return and mean absolute move."""
    o, c = df["Open"], df["Close"]
    px = o.shift(-1) if entry == "next_open" else c
    out = {}
    for hz in horizons:
        ret = (c.shift(-hz) / px - 1).dropna()
        out[hz] = {"up": float((ret > 0).mean()), "mean": float(ret.mean()), "absmean": float(ret.abs().mean()), "n": len(ret)}
    return out


# ------------------------------------------------------------------ summaries
def summarise(ev: pd.DataFrame, bases: dict, horizon: int, by: list[str] | None = None, min_sample: int = MIN_SAMPLE) -> pd.DataFrame:
    """Statistics per group for one horizon. ``bases`` maps instrument -> base_rates()."""
    if ev.empty:
        return pd.DataFrame()
    ev = ev.reset_index(drop=True)   # events from several stocks may share index labels
    by = by or ["Pattern"]
    rows = []
    for key, g in ev.groupby(by, dropna=False):
        key = key if isinstance(key, tuple) else (key,)
        bias = g["Bias"].iloc[0] if g["Bias"].nunique() == 1 else "Mixed"
        rec = dict(zip(by, key))
        rec["Bias"] = bias
        dcol, ncol, mcol, rcol = f"dir_{horizon}d", f"net_{horizon}d", f"mae_{horizon}d", f"ret_{horizon}d"
        if bias in ("Bullish", "Bearish"):
            d = g[dcol].dropna()
            n = len(d)
            wins = int((d > 0).sum())
            # expected hit rate under "no information": each event's stock base rate in the pattern's direction
            exp = []
            for _, row in g.loc[d.index].iterrows():
                up = bases[row["Instrument"]][horizon]["up"]
                exp.append(up if row["Bias"] == "Bullish" else 1 - up)
            base_hit = float(np.mean(exp)) if exp else math.nan
            lo, hi = wilson_ci(wins, n)
            p = stats.binomtest(wins, n, base_hit, alternative="two-sided").pvalue if n > 0 and 0 < base_hit < 1 else math.nan
            net = g[ncol].dropna()
            mlo, mhi = mean_ci(d)
            sd = d.std(ddof=1) if n > 1 else math.nan
            rec.update({
                "Occurrences": n, "Hit rate": wins / n if n else math.nan, "Hit rate CI low": lo, "Hit rate CI high": hi,
                "Base-rate hit": base_hit, "Hit-rate p-value": p,
                "Avg directional return": d.mean() if n else math.nan, "Return CI low": mlo, "Return CI high": mhi,
                "Avg net return (after costs)": net.mean() if len(net) else math.nan,
                "Success rate (net > 0)": (net > 0).mean() if len(net) else math.nan,
                "Failure rate": 1 - (net > 0).mean() if len(net) else math.nan,
                "Avg adverse excursion": g[mcol].dropna().mean() if n else math.nan,
                "Worst adverse excursion": g[mcol].dropna().min() if n else math.nan,
                "Return / risk (mean ÷ sd)": (d.mean() / sd) if n > 1 and sd > 0 else math.nan,
                "Sample flag": "OK" if n >= min_sample else f"Small sample (< {min_sample})",
            })
        else:
            a = g[f"absmove_{horizon}d"].dropna() if f"absmove_{horizon}d" in g else pd.Series(dtype=float)
            n = len(a)
            exp = np.array([bases[ins][horizon]["absmean"] for ins in g.loc[a.index, "Instrument"]]) if n else np.array([])
            base_abs = float(exp.mean()) if n else math.nan
            p = float(stats.ttest_1samp(a.to_numpy() - exp, 0).pvalue) if n > 2 else math.nan
            rec.update({"Occurrences": n, "Avg absolute move": a.mean() if n else math.nan, "Typical absolute move": base_abs,
                        "Move ratio": (a.mean() / base_abs) if n and base_abs else math.nan, "Move p-value": p,
                        "Avg return": g[rcol].dropna().mean() if n else math.nan,
                        "Sample flag": "OK" if n >= min_sample else f"Small sample (< {min_sample})"})
        rows.append(rec)
    out = pd.DataFrame(rows)
    if "Hit-rate p-value" in out:
        out["q-value (BH)"] = benjamini_hochberg(out["Hit-rate p-value"])
    return out


def verdict(row: pd.Series) -> str:
    """Plain-language reading of one directional summary row."""
    if row.get("Bias") not in ("Bullish", "Bearish"):
        r = row.get("Move ratio")
        if r is None or (isinstance(r, float) and math.isnan(r)):
            return "Not enough data"
        return "Larger moves follow" if (r > 1 and row.get("Move p-value", 1) < 0.05) else "No reliable difference"
    n = row.get("Occurrences", 0)
    if n < MIN_SAMPLE:
        return "Too few cases to judge"
    lo, base = row.get("Hit rate CI low"), row.get("Base-rate hit")
    hi = row.get("Hit rate CI high")
    q = row.get("q-value (BH)", row.get("Hit-rate p-value", 1))
    net = row.get("Avg net return (after costs)")
    if lo > base and q < 0.1 and net > 0:
        return "Edge, survives costs"
    if lo > base and q < 0.1:
        return "Edge before costs only"
    if hi < base and q < 0.1:
        return "Worse than chance"
    return "No reliable edge"


def oos_comparison(ev: pd.DataFrame, bases: dict, horizon: int) -> pd.DataFrame:
    """Same statistics computed separately for the earlier (in-sample) and later (out-of-sample) period."""
    if ev.empty:
        return pd.DataFrame()
    s = summarise(ev, bases, horizon, by=["Pattern", "Period"])
    s = s[s["Bias"].isin(["Bullish", "Bearish"])]
    if s.empty:
        return s
    piv = s.pivot(index="Pattern", columns="Period", values=["Occurrences", "Hit rate", "Base-rate hit", "Avg net return (after costs)"])
    piv.columns = [f"{a} – {b}" for a, b in piv.columns]
    out = piv.reset_index()

    def consistency(r):
        nin, nout = r.get("Occurrences – In-sample", 0), r.get("Occurrences – Out-of-sample", 0)
        if (nin or 0) < 10 or (nout or 0) < 10:
            return "Too few cases"
        ein = r.get("Hit rate – In-sample", np.nan) - r.get("Base-rate hit – In-sample", np.nan)
        eout = r.get("Hit rate – Out-of-sample", np.nan) - r.get("Base-rate hit – Out-of-sample", np.nan)
        if np.isnan(ein) or np.isnan(eout):
            return "Too few cases"
        if ein > 0.02 and eout > 0.02:
            return "Edge persisted"
        if ein > 0.02 and eout <= 0:
            return "Edge disappeared"
        if ein <= 0 and eout <= 0:
            return "No edge in either period"
        return "Mixed"
    out["Consistency"] = out.apply(consistency, axis=1)
    return out
