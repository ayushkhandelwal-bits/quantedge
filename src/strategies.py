"""Strategy registry.

Each enabled strategy returns a *target position* series (+1 long, 0 flat, -1 short) where
the value on date t is decided with information available at the close of t (or, for the
gap strategy, at the open of t). The backtester decides when that decision can be executed.

Signal logic for SMA Crossover, Bollinger Mean Reversion, Donchian Breakout, RSI Divergence
and Gap Fill comes from ``src/reference/strategy.py`` (third-party, MIT-licensed; see
``src/reference/LICENSE``), called unchanged. Candlestick Reversal and Buy & Hold are defined here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import pandas as pd

from src import candlestick_patterns as cp
from src.reference import strategy as ref


def to_rows(df: pd.DataFrame) -> list[dict]:
    """Convert a frame to the list-of-dicts layout used by the reference strategies."""
    return [{"date": d.strftime("%Y-%m-%d"), "open": float(r.Open), "high": float(r.High), "low": float(r.Low),
             "close": float(r.Close), "volume": float(r.Volume) if pd.notna(r.Volume) else 0.0}
            for d, r in zip(df.index, df.itertuples(index=False))]


def _from_signals(sigs: list[dict], index: pd.Index) -> pd.DataFrame:
    return pd.DataFrame({"target": [int(s["signal"]) for s in sigs], "reason": [s.get("reason", "") for s in sigs]}, index=index)


@dataclass
class Param:
    name: str
    label: str
    default: float
    min: float
    max: float
    step: float
    help: str = ""
    grid: list = field(default_factory=list)   # values used by walk-forward / sensitivity


@dataclass
class Strategy:
    key: str
    name: str
    family: str
    objective: str
    rule: str
    entry: str
    exit: str
    data_required: str
    struggles: str
    metrics: str
    params: list[Param]
    fn: Callable | None
    uses_short: bool = False
    execution: str = "next_open"       # next_open | open_to_close
    available: bool = True
    unavailable_reason: str = ""
    source: str = "src/reference/strategy.py (MIT-licensed module)"

    def defaults(self) -> dict:
        return {p.name: p.default for p in self.params}

    def signals(self, df: pd.DataFrame, params: dict | None = None) -> pd.DataFrame:
        if not self.available or self.fn is None:
            raise RuntimeError(f"{self.name} is not available: {self.unavailable_reason}")
        prm = self.defaults() | (params or {})
        return self.fn(df, prm)


# --------------------------------------------------------------------------- implementations
def _sma(df, p):
    s, l = int(p["short_window"]), int(p["long_window"])
    if s >= l:
        raise ValueError("Short window must be shorter than long window")
    return _from_signals(ref.sma_crossover_strategy(to_rows(df), s, l), df.index)


def _bb(df, p):
    cfg = {"window": int(p["window"]), "num_std": float(p["num_std"]), "rsi_period": 14,
           "rsi_oversold": float(p["rsi_oversold"]), "rsi_overbought": 100 - float(p["rsi_oversold"])}
    return _from_signals(ref.bollinger_mean_reversion(to_rows(df), cfg), df.index)


def _donchian(df, p):
    return _from_signals(ref.donchian_breakout(to_rows(df), {"window": int(p["window"])}), df.index)


def _rsi_div(df, p):
    return _from_signals(ref.rsi_divergence(to_rows(df), {"rsi_period": int(p["rsi_period"]), "lookback": int(p["lookback"])}), df.index)


def _gap(df, p):
    cfg = {"min_gap_pct": float(p["min_gap_pct"]) / 100, "max_gap_pct": float(p["max_gap_pct"]) / 100}
    return _from_signals(ref.gap_fill_strategy(to_rows(df), cfg), df.index)


def _candle(df, p):
    det = cp.detect(df, cp.PatternParams())
    trigger = det["Hammer"] | det["Bullish Engulfing"]
    hold = int(p["hold_days"])
    target = pd.Series(0, index=df.index, dtype=int)
    reason = pd.Series("", index=df.index, dtype=object)
    remaining = 0
    for i, d in enumerate(df.index):
        if trigger.iloc[i]:
            remaining = hold
            reason.iloc[i] = "Hammer" if det["Hammer"].iloc[i] else "Bullish Engulfing"
        if remaining > 0:
            target.iloc[i] = 1
            remaining -= 1
            if not reason.iloc[i]:
                reason.iloc[i] = "Holding"
    return pd.DataFrame({"target": target, "reason": reason}, index=df.index)


def _buy_hold(df, p):
    return pd.DataFrame({"target": 1, "reason": "Buy & hold"}, index=df.index)


# --------------------------------------------------------------------------- registry
REGISTRY: dict[str, Strategy] = {
    "sma_crossover": Strategy(
        "sma_crossover", "SMA Crossover", "Trend following",
        "Stay invested while the short-term trend is above the long-term trend.",
        "Long when SMA(short) > SMA(long); flat otherwise.",
        "Short average crosses above long average.", "Short average crosses below long average.",
        "Daily close prices of one instrument.",
        "Choppy, range-bound markets produce repeated false crossovers (whipsaws); signals lag turning points.",
        "CAGR vs benchmark, max drawdown, time in market, number of whipsaw trades.",
        [Param("short_window", "Short SMA (sessions)", 20, 5, 100, 1, grid=[10, 20, 30, 50]),
         Param("long_window", "Long SMA (sessions)", 50, 20, 250, 5, grid=[50, 100, 150, 200])],
        _sma),
    "bollinger_mr": Strategy(
        "bollinger_mr", "Bollinger Band Mean Reversion", "Mean reversion",
        "Buy unusually weak prices / sell unusually strong prices, expecting a return to the average.",
        "Long when close < lower band AND RSI < oversold; short when close > upper band AND RSI > 100−oversold.",
        "Price stretched beyond a band with RSI confirmation.", "Close crosses back to the middle band.",
        "Daily close prices of one instrument.",
        "Strong trends: price can 'walk the band' and keep moving against the position.",
        "Win rate, average win/loss, drawdown, behaviour in trending regimes.",
        [Param("window", "Band window (sessions)", 20, 10, 60, 1, grid=[15, 20, 30]),
         Param("num_std", "Band width (std devs)", 2.0, 1.0, 3.0, 0.1, grid=[1.5, 2.0, 2.5]),
         Param("rsi_oversold", "RSI oversold level", 30, 10, 45, 1, grid=[30, 35, 40])],
        _bb, uses_short=True),
    "donchian": Strategy(
        "donchian", "Donchian Breakout", "Breakout / trend",
        "Join a move once price breaks out of its recent trading range.",
        "Long when close > highest high of previous N sessions; short when close < lowest low of previous N sessions.",
        "Close breaks the N-session channel.", "Opposite breakout reverses (or exits, if shorting is disabled).",
        "Daily OHLC of one instrument.",
        "Range-bound markets with false breakouts; large give-backs before the opposite signal.",
        "Profit factor, average win/loss, drawdown.",
        [Param("window", "Channel length (sessions)", 20, 5, 100, 1, grid=[10, 20, 40, 55])],
        _donchian, uses_short=True),
    "rsi_divergence": Strategy(
        "rsi_divergence", "RSI Divergence", "Momentum reversal",
        "Spot weakening momentum before price turns.",
        "Bullish: price makes a lower low while RSI makes a higher low → long. Bearish: higher high in price, lower high in RSI → short.",
        "Divergence detected within the look-back window.", "Opposite divergence (position persists until then).",
        "Daily close prices of one instrument.",
        "Divergences can persist for a long time in strong trends; swing-point detection is noisy.",
        "Win rate, expectancy, drawdown.",
        [Param("rsi_period", "RSI period", 14, 5, 30, 1, grid=[10, 14, 21]),
         Param("lookback", "Look-back window (sessions)", 20, 10, 60, 1, grid=[15, 20, 30])],
        _rsi_div, uses_short=True),
    "gap_fill": Strategy(
        "gap_fill", "Gap Fill (open-to-close)", "Mean reversion (intraday)",
        "Fade moderate overnight gaps, expecting part of the gap to close during the session.",
        "Gap up between min% and max% → short at the open; gap down → long at the open.",
        "At the open, once the gap is known.", "Same session's close (one-day holding).",
        "Daily open and previous close of one instrument.",
        "Gaps driven by real news often extend rather than fill; intraday short-selling is required for gap-ups.",
        "Win rate, average trade, cost drag (one round trip per signal day).",
        [Param("min_gap_pct", "Minimum gap (%)", 0.3, 0.1, 2.0, 0.1, grid=[0.3, 0.5, 1.0]),
         Param("max_gap_pct", "Maximum gap (%)", 2.0, 0.5, 5.0, 0.1, grid=[1.5, 2.0, 3.0])],
        _gap, uses_short=True, execution="open_to_close"),
    "candle_reversal": Strategy(
        "candle_reversal", "Candlestick Reversal (Hammer / Bullish Engulfing)", "Pattern-based",
        "Test whether bullish reversal candles are followed by gains.",
        "Long after a Hammer or Bullish Engulfing candle; hold a fixed number of sessions.",
        "Next open after the pattern completes.", "After N sessions (timer resets if a new pattern appears).",
        "Daily OHLC of one instrument.",
        "Patterns are frequent and individually weak; results are sensitive to definitions and holding period.",
        "Hit rate vs base rate, average trade, cost drag.",
        [Param("hold_days", "Holding period (sessions)", 5, 1, 20, 1, grid=[3, 5, 10])],
        _candle, source="src/strategies.py"),
    "buy_hold": Strategy(
        "buy_hold", "Buy & Hold (benchmark)", "Benchmark",
        "Passive reference: buy on the first session and hold.",
        "Always long.", "First session.", "End of period.",
        "Daily close of one instrument.", "Bear markets: full exposure to every decline.",
        "Total return, CAGR, drawdown.", [], _buy_hold, source="src/strategies.py"),
    # ---- known strategies that are not runnable on free daily single-instrument data
    "vwap_mr": Strategy("vwap_mr", "VWAP Mean Reversion", "Intraday", "Fade deviations from intraday VWAP.", "", "", "",
                        "Intraday (5–15 min) bars with volume.", "", "", [], None, available=False,
                        unavailable_reason="Needs intraday bars. Yahoo Finance offers only ~60 days of free intraday history, too little for a credible backtest."),
    "orb": Strategy("orb", "Opening Range Breakout", "Intraday", "Trade breakouts from the first 15 minutes.", "", "", "",
                    "Intraday (1–15 min) bars.", "", "", [], None, available=False,
                    unavailable_reason="Needs intraday bars with timestamps; not available freely for multi-year history."),
    "xs_momentum": Strategy("xs_momentum", "Cross-Sectional Momentum", "Factor (portfolio)", "Long recent winners, short losers.", "", "", "",
                            "Daily prices for a whole universe, rebalanced monthly.", "", "", [], None, available=False,
                            unavailable_reason="Needs a multi-asset portfolio backtester (simultaneous positions across many stocks). This engine trades one instrument at a time."),
    "pairs": Strategy("pairs", "Pairs Trading", "Market-neutral (two legs)", "Trade the spread of two related stocks.", "", "", "",
                      "Daily prices for two instruments; short selling of one leg.", "", "", [], None, available=False,
                      unavailable_reason="Needs a two-leg (long/short) portfolio backtester and overnight short selling. Not enabled in this version."),
    "short_straddle": Strategy("short_straddle", "Weekly Short Straddle", "Options", "Collect option premium as time decays.", "", "", "",
                               "Historical option contract prices (premiums) for each expiry.", "", "", [], None, available=False,
                               unavailable_reason="Needs genuine historical option prices. Pricing past trades with a model instead would manufacture returns, so it stays disabled until real contract data is supplied."),
}

ENABLED = [k for k, s in REGISTRY.items() if s.available]
TRADING = [k for k in ENABLED if k != "buy_hold"]
