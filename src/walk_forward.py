"""Walk-forward validation, parameter sensitivity, cost sensitivity and market regimes.

Walk-forward design:

    |---- train (choose params) ----|-- test (apply them) --|
              |---- train ----|-- test --|
                        |---- train ----|-- test --|   ... rolling forward

* Windows are strictly chronological; test windows never overlap one another.
* Parameters are chosen on the training window only (highest net Sharpe after costs).
* Indicators in the test window may use earlier prices (as they would in real time), but no
  price from after a test date can affect a decision on that date.
* Each test window starts flat (no position carried over from training).
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass

import numpy as np
import pandas as pd

from src import performance_metrics as pm
from src.backtester import BacktestConfig, run_backtest
from src.strategies import Strategy


def param_grid(strategy: Strategy, max_combos: int = 36) -> list[dict]:
    names = [p.name for p in strategy.params]
    grids = [p.grid or [p.default] for p in strategy.params]
    combos = [dict(zip(names, vals)) for vals in itertools.product(*grids)]
    if strategy.key == "sma_crossover":
        combos = [c for c in combos if c["short_window"] < c["long_window"]]
    if strategy.key == "gap_fill":
        combos = [c for c in combos if c["min_gap_pct"] < c["max_gap_pct"]]
    return combos[:max_combos] or [strategy.defaults()]


def _test_run(df, strategy, params, cfg, start, end, rf):
    """Signals computed on data up to ``end`` (history allowed), trades only within [start, end]."""
    hist = df.loc[:end]
    sig = strategy.signals(hist, params)
    window = df.loc[start:end]
    res = run_backtest(window, sig.loc[start:end], cfg)
    return res, pm.sharpe(res.curve, rf)


@dataclass
class WFResult:
    splits: pd.DataFrame
    oos_equity: pd.Series
    is_sharpe_avg: float | None
    oos_sharpe_avg: float | None
    degradation: float | None
    oos_metrics: dict


def walk_forward(df: pd.DataFrame, strategy: Strategy, cfg: BacktestConfig, rf: float,
                 train_years: float = 2.0, test_months: int = 6) -> WFResult:
    idx = df.index
    grid = param_grid(strategy)
    splits = []
    test_start = idx[0] + pd.DateOffset(months=int(train_years * 12))
    oos_curves = []
    capital = cfg.initial_capital
    while True:
        test_end = test_start + pd.DateOffset(months=test_months) - pd.Timedelta(days=1)
        if test_start > idx[-1]:
            break
        train_start = test_start - pd.DateOffset(months=int(train_years * 12))
        train = df.loc[train_start:test_start - pd.Timedelta(days=1)]
        test = df.loc[test_start:test_end]
        if len(train) < 120 or len(test) < 20:
            break
        best, best_sh = None, -np.inf
        for prm in grid:
            try:
                r, sh = _test_run(df, strategy, prm, cfg, train.index[0], train.index[-1], rf)
            except ValueError:
                continue
            sh = -np.inf if sh is None else sh
            if sh > best_sh:
                best, best_sh = prm, sh
        if best is None:
            best = strategy.defaults()
        tcfg = BacktestConfig(**{**cfg.__dict__, "initial_capital": capital})
        res, oos_sh = _test_run(df, strategy, best, tcfg, test.index[0], test.index[-1], rf)
        capital = float(res.curve.iloc[-1])
        oos_curves.append(res.curve)
        splits.append({
            "Window": len(splits) + 1,
            "Train": f"{train.index[0].date()} → {train.index[-1].date()}",
            "Test": f"{test.index[0].date()} → {test.index[-1].date()}",
            "Chosen parameters": ", ".join(f"{k}={v:g}" for k, v in best.items()) if best else "—",
            "In-sample Sharpe": None if best_sh == -np.inf else best_sh,
            "Out-of-sample Sharpe": oos_sh,
            "OOS return": pm.total_return(res.curve),
            "OOS max drawdown": pm.max_drawdown(res.curve),
            "OOS trades": len(res.trades),
        })
        test_start = test_end + pd.Timedelta(days=1)
    sp = pd.DataFrame(splits)
    if sp.empty:
        return WFResult(sp, pd.Series(dtype=float), None, None, None, {})
    oos = pd.concat(oos_curves)
    oos = oos[~oos.index.duplicated(keep="last")]
    is_avg = sp["In-sample Sharpe"].dropna().mean() if sp["In-sample Sharpe"].notna().any() else None
    oos_avg = sp["Out-of-sample Sharpe"].dropna().mean() if sp["Out-of-sample Sharpe"].notna().any() else None
    deg = (oos_avg / is_avg) if (is_avg is not None and oos_avg is not None and is_avg > 0) else None
    return WFResult(sp, oos, is_avg, oos_avg, deg,
                    {"total_return": pm.total_return(oos), "cagr": pm.cagr(oos), "sharpe": pm.sharpe(oos, rf),
                     "max_drawdown": pm.max_drawdown(oos)})


def sensitivity(df: pd.DataFrame, strategy: Strategy, cfg: BacktestConfig, rf: float) -> pd.DataFrame:
    """Full-period results for every parameter combination in the grid."""
    rows = []
    for prm in param_grid(strategy):
        try:
            res = run_backtest(df, strategy.signals(df, prm), cfg)
        except ValueError:
            continue
        rows.append({**prm, "Sharpe": pm.sharpe(res.curve, rf), "Total return": pm.total_return(res.curve),
                     "Max drawdown": pm.max_drawdown(res.curve), "Trades": len(res.trades)})
    return pd.DataFrame(rows)


def cost_sensitivity(df, strategy, params, cfg: BacktestConfig, rf, factors=(0.0, 1.0, 2.0, 3.0)) -> pd.DataFrame:
    sig = strategy.signals(df, params)
    rows = []
    for f in factors:
        cs = cfg.costs.scaled(f) if f > 0 else cfg.costs.zero()
        res = run_backtest(df, sig, BacktestConfig(**{**cfg.__dict__, "costs": cs}))
        rows.append({"Cost multiplier": f, "Label": "No costs" if f == 0 else f"{f:g}× current costs",
                     "Total return": pm.total_return(res.curve), "Sharpe": pm.sharpe(res.curve, rf),
                     "Costs paid": float(res.trades["Charges"].sum() + res.trades["Slippage"].sum()) if len(res.trades) else 0.0})
    return pd.DataFrame(rows)


def regimes(close: pd.Series, trend_window: int = 200, vol_window: int = 20) -> pd.Series:
    """Transparent, causal market-regime label for each session.

    Trend: close above / below its 200-session average (Bull / Bear).
    Volatility: 20-session volatility above / below its own expanding median (High / Low vol).
    """
    ma = close.rolling(trend_window, min_periods=trend_window).mean()
    vol = close.pct_change().rolling(vol_window).std()
    med = vol.expanding(min_periods=vol_window * 3).median()
    trend = np.where(close > ma, "Uptrend", "Downtrend")
    vlab = np.where(vol > med, "high vol", "low vol")
    lab = pd.Series([f"{t}, {v}" for t, v in zip(trend, vlab)], index=close.index)
    return lab.where(ma.notna() & med.notna(), "Insufficient history")


def returns_by_regime(equity: pd.Series, regime: pd.Series, bench_close: pd.Series) -> pd.DataFrame:
    r = equity.pct_change()
    b = bench_close.reindex(equity.index).pct_change()
    df = pd.DataFrame({"strategy": r, "benchmark": b, "regime": regime.reindex(equity.index)}).dropna()
    g = df.groupby("regime")
    out = pd.DataFrame({
        "Sessions": g.size(),
        "Strategy avg daily return": g["strategy"].mean(),
        "Benchmark avg daily return": g["benchmark"].mean(),
        "Strategy annualised": g["strategy"].mean() * 252,
        "Benchmark annualised": g["benchmark"].mean() * 252,
    })
    return out.reset_index().rename(columns={"regime": "Regime"})
