"""Technical indicators as pandas Series.

The arithmetic is delegated to the pure-Python implementations in
``src/reference/indicators.py`` (third-party, MIT-licensed; see ``src/reference/LICENSE``) so
each indicator has exactly one definition in the project. This module only converts between lists and pandas objects.

All indicators are causal: the value on date t uses only observations up to and
including t. Signals that act on them are executed on the next session (see backtester).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.reference import indicators as ref


def _s(values, index, name):
    return pd.Series([np.nan if v is None else v for v in values], index=index, name=name, dtype=float)


def sma(close: pd.Series, n: int) -> pd.Series:
    return _s(ref.sma(close.tolist(), n), close.index, f"SMA{n}")


def ema(close: pd.Series, n: int) -> pd.Series:
    return _s(ref.ema(close.tolist(), n), close.index, f"EMA{n}")


def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    """RSI using simple rolling averages of gains/losses (reference implementation; 'Cutler' RSI)."""
    return _s(ref.rsi(close.tolist(), n), close.index, f"RSI{n}")


def macd(close: pd.Series, fast=12, slow=26, signal=9) -> pd.DataFrame:
    m, s, h = ref.macd(close.tolist(), fast, slow, signal)
    return pd.DataFrame({"MACD": _s(m, close.index, "MACD"), "MACD_signal": _s(s, close.index, "MACD_signal"),
                         "MACD_hist": _s(h, close.index, "MACD_hist")})


def bollinger(close: pd.Series, n=20, k=2.0) -> pd.DataFrame:
    bands = ref.bollinger_bands(close.tolist(), n, k)
    up = [b[0] if b else None for b in bands]
    mid = [b[1] if b else None for b in bands]
    lo = [b[2] if b else None for b in bands]
    return pd.DataFrame({"BB_upper": _s(up, close.index, "BB_upper"), "BB_mid": _s(mid, close.index, "BB_mid"),
                         "BB_lower": _s(lo, close.index, "BB_lower")})


def atr(df: pd.DataFrame, n=14) -> pd.Series:
    return _s(ref.atr(df["High"].tolist(), df["Low"].tolist(), df["Close"].tolist(), n), df.index, f"ATR{n}")


def donchian(df: pd.DataFrame, n=20) -> pd.DataFrame:
    """Channel of the *previous* n sessions (excludes today), matching the reference strategy."""
    return pd.DataFrame({"DC_upper": df["High"].shift(1).rolling(n).max(),
                         "DC_lower": df["Low"].shift(1).rolling(n).min()})


def daily_returns(close: pd.Series) -> pd.Series:
    return close.pct_change().rename("Return")


def log_returns(close: pd.Series) -> pd.Series:
    return np.log(close / close.shift(1)).rename("LogReturn")


def rolling_volatility(close: pd.Series, n=20) -> pd.Series:
    """Annualised rolling standard deviation of daily returns (sample std, ×√252)."""
    return (daily_returns(close).rolling(n).std() * np.sqrt(252)).rename(f"Vol{n}")


def feature_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Price data plus the standard derived fields shown in the data dictionary."""
    c = df["Close"]
    out = df.copy()
    out["Return"] = daily_returns(c)
    out["LogReturn"] = log_returns(c)
    out["SMA20"] = sma(c, 20)
    out["SMA50"] = sma(c, 50)
    out["EMA20"] = ema(c, 20)
    out["RSI14"] = rsi(c, 14)
    out = out.join(macd(c)).join(bollinger(c)).join(donchian(df))
    out["ATR14"] = atr(df, 14)
    out["Vol20"] = rolling_volatility(c, 20)
    return out
