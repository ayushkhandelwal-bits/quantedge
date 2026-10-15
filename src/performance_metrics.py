"""Performance metrics with explicit conventions and safe handling of undefined values.

Conventions
-----------
* Return frequency: daily, from the end-of-day equity curve.
* Annualisation: 252 trading sessions per year for volatility, Sharpe and Sortino;
  CAGR uses calendar time between the first and last observation (days / 365.25).
* Risk-free rate: user-set annual rate converted to a daily rate (rf / 252).
* Open positions: liquidated at the final close (and charged) by the backtester, so every
  trade in the statistics is a completed round trip.
* Undefined values are returned as ``None`` (shown as "n/a" with a reason), never as ±inf:
  zero volatility → Sharpe n/a; no downside returns → Sortino n/a; no losing trades → profit
  factor n/a; no trades → trade statistics n/a.
* Missing observations are not filled; returns are computed between consecutive sessions.

Where a function in ``src/reference/metrics.py`` (third-party, MIT-licensed; see
``src/reference/LICENSE``) matches these conventions it is used directly
(``total_return``, ``max_drawdown``, ``trade_expectancy``) and cross-checked in the tests.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from src.reference import metrics as ref

TRADING_DAYS = 252


def _clean(x):
    if x is None:
        return None
    try:
        if math.isnan(x) or math.isinf(x):
            return None
    except TypeError:
        return x
    return float(x)


def total_return(equity: pd.Series) -> float | None:
    if len(equity) < 2 or equity.iloc[0] <= 0:
        return None
    return ref.total_return(equity.tolist()) / 100


def cagr(equity: pd.Series) -> float | None:
    if len(equity) < 2 or equity.iloc[0] <= 0 or equity.iloc[-1] <= 0:
        return None
    years = (equity.index[-1] - equity.index[0]).days / 365.25
    if years <= 0:
        return None
    return (equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1


def daily_returns(equity: pd.Series) -> pd.Series:
    return equity.pct_change().dropna()


def annual_volatility(equity: pd.Series) -> float | None:
    r = daily_returns(equity)
    if len(r) < 2:
        return None
    return _clean(r.std(ddof=1) * np.sqrt(TRADING_DAYS))


def sharpe(equity: pd.Series, rf: float = 0.0) -> float | None:
    r = daily_returns(equity)
    if len(r) < 20:
        return None
    sd = r.std(ddof=1)
    if sd == 0 or np.isnan(sd):
        return None
    return _clean((r.mean() - rf / TRADING_DAYS) / sd * np.sqrt(TRADING_DAYS))


def sortino(equity: pd.Series, rf: float = 0.0) -> float | None:
    r = daily_returns(equity)
    if len(r) < 20:
        return None
    excess = r - rf / TRADING_DAYS
    downside = np.minimum(excess, 0)
    dd = np.sqrt((downside ** 2).mean())
    if dd == 0:
        return None
    return _clean(excess.mean() / dd * np.sqrt(TRADING_DAYS))


def drawdown_series(equity: pd.Series) -> pd.Series:
    peak = equity.cummax()
    return (equity / peak - 1).rename("Drawdown")


def max_drawdown(equity: pd.Series) -> float | None:
    """Largest peak-to-trough decline as a positive fraction (0.25 = 25%)."""
    if len(equity) < 2:
        return None
    return ref.max_drawdown(equity.tolist()) / 100


def max_drawdown_duration(equity: pd.Series) -> int | None:
    """Longest stretch (calendar days) spent below a previous peak."""
    if len(equity) < 2:
        return None
    under = equity < equity.cummax()
    longest, start = 0, None
    for d, u in under.items():
        if u and start is None:
            start = d
        elif not u and start is not None:
            longest = max(longest, (d - start).days)
            start = None
    if start is not None:
        longest = max(longest, (equity.index[-1] - start).days)
    return longest


def trade_stats(trades: pd.DataFrame) -> dict:
    n = len(trades)
    if n == 0:
        return {"trades": 0, "win_rate": None, "profit_factor": None, "avg_win": None, "avg_loss": None,
                "expectancy": None, "avg_holding_days": None, "largest_loss": None}
    pnl = trades["Net P&L"]
    wins, losses = pnl[pnl > 0], pnl[pnl <= 0]
    gross_loss = -pnl[pnl < 0].sum()
    pf = pnl[pnl > 0].sum() / gross_loss if gross_loss > 0 else None
    exp = ref.trade_expectancy([{"pnl": float(x)} for x in pnl])
    return {
        "trades": n,
        "win_rate": len(wins) / n,
        "profit_factor": _clean(pf),
        "avg_win": float(wins.mean()) if len(wins) else None,
        "avg_loss": float(losses.mean()) if len(losses) else None,   # negative number
        "expectancy": _clean(exp),
        "avg_holding_days": float(trades["Holding days"].mean()),
        "largest_loss": float(pnl.min()),
    }


def compute_all(equity: pd.Series, trades: pd.DataFrame, rf: float, eq_frame: pd.DataFrame | None = None) -> dict:
    m = {
        "total_return": total_return(equity),
        "cagr": cagr(equity),
        "volatility": annual_volatility(equity),
        "sharpe": sharpe(equity, rf),
        "sortino": sortino(equity, rf),
        "max_drawdown": max_drawdown(equity),
        "max_dd_days": max_drawdown_duration(equity),
    }
    m["calmar"] = _clean(m["cagr"] / m["max_drawdown"]) if m["cagr"] is not None and m["max_drawdown"] else None
    m.update(trade_stats(trades))
    m["gross_pnl"] = float(trades["Gross P&L"].sum()) if len(trades) else 0.0
    m["charges"] = float(trades["Charges"].sum()) if len(trades) else 0.0
    m["slippage"] = float(trades["Slippage"].sum()) if len(trades) else 0.0
    m["total_costs"] = m["charges"] + m["slippage"]
    m["net_pnl"] = float(equity.iloc[-1] - equity.iloc[0])
    m["turnover"] = float((trades["Entry price"] * trades["Quantity"] + trades["Exit price"] * trades["Quantity"]).sum()) if len(trades) else 0.0
    m["exposure"] = float(eq_frame["exposure"].gt(0).mean()) if eq_frame is not None else None
    m["start"], m["end"] = equity.index[0].date(), equity.index[-1].date()
    return m


def monthly_returns(equity: pd.Series) -> pd.DataFrame:
    """Year × month table of returns (fractions)."""
    me = equity.resample("ME").last()
    first = equity.iloc[0]
    r = me.pct_change()
    r.iloc[0] = me.iloc[0] / first - 1
    t = pd.DataFrame({"Year": r.index.year, "Month": r.index.month, "Return": r.values})
    return t.pivot(index="Year", columns="Month", values="Return")


METRIC_HELP = {
    "total_return": "Change in portfolio value over the whole period, after costs.",
    "cagr": "Compound annual growth rate: the constant yearly return that would produce the same end value.",
    "volatility": "Annualised standard deviation of daily returns – how much the portfolio value swings.",
    "sharpe": "Return above the risk-free rate per unit of volatility (annualised). Above 1 is generally considered good; compare like with like.",
    "sortino": "Like Sharpe, but only downside swings count as risk.",
    "max_drawdown": "Worst fall from a previous peak to a later low – the deepest loss an investor would have sat through.",
    "calmar": "CAGR divided by maximum drawdown: return earned per unit of worst-case loss.",
    "win_rate": "Share of completed trades that made money after costs.",
    "profit_factor": "Total profit of winning trades ÷ total loss of losing trades. Above 1 means winners outweigh losers.",
    "expectancy": "Average net profit per trade = win rate × average win − loss rate × average loss.",
    "trades": "Number of completed round trips (entry and exit).",
    "total_costs": "Brokerage, taxes, exchange fees, stamp duty, GST, DP charges and slippage paid.",
    "exposure": "Share of sessions with an open position.",
}
