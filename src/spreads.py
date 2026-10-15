"""User-supplied futures contracts: calendar spreads and butterflies (e.g. short-term interest-rate futures).

No free source provides multi-year history for individual (including expired) contract months, so
this module works ONLY on data the user uploads. It never fabricates contract prices.

Expected CSV (long format, one row per contract per date):
    Date,Contract,Close
    2024-01-02,IRF-MAR24,92.15
    2024-01-02,IRF-JUN24,92.40
Optional columns: Expiry, Volume, OpenInterest.

For interest-rate futures quoted as 100 − rate, a calendar spread (near − far) is in price points;
multiply by 100 for basis points if the quote uses that convention.
"""
from __future__ import annotations

import io

import numpy as np
import pandas as pd

REQUIRED = ["Date", "Contract", "Close"]

TEMPLATE = """# TEMPLATE ONLY - these rows are illustrative placeholders, NOT market data. Replace with real contract prices.
Date,Contract,Expiry,Close
2025-01-02,CONTRACT_A,2025-03-26,100.00
2025-01-02,CONTRACT_B,2025-06-25,100.00
2025-01-02,CONTRACT_C,2025-09-24,100.00
"""


def parse_contracts(raw: bytes | str) -> tuple[pd.DataFrame, list[str]]:
    """Return a Date × Contract price table and a list of validation messages."""
    text = raw.decode("utf-8", errors="replace") if isinstance(raw, (bytes, bytearray)) else raw
    df = pd.read_csv(io.StringIO(text), comment="#")
    df.columns = [c.strip() for c in df.columns]
    msgs = []
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required column(s): {', '.join(missing)}. Expected at least {REQUIRED}.")
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df["Close"] = pd.to_numeric(df["Close"], errors="coerce")
    bad = df["Date"].isna() | df["Close"].isna()
    if bad.any():
        msgs.append(f"{int(bad.sum())} row(s) with unreadable date or price were dropped.")
    df = df[~bad]
    dups = df.duplicated(["Date", "Contract"], keep="last")
    if dups.any():
        msgs.append(f"{int(dups.sum())} duplicate Date/Contract row(s); kept the last one.")
    df = df[~dups]
    wide = df.pivot(index="Date", columns="Contract", values="Close").sort_index()
    if len(wide) < 30:
        msgs.append(f"Only {len(wide)} dates supplied – statistics will be very uncertain.")
    return wide, msgs


def calendar_spread(wide: pd.DataFrame, near: str, far: str) -> pd.Series:
    return (wide[near] - wide[far]).rename(f"{near} − {far}")


def butterfly(wide: pd.DataFrame, front: str, middle: str, back: str) -> pd.Series:
    """Front − 2 × Middle + Back (long wings, short body)."""
    return (wide[front] - 2 * wide[middle] + wide[back]).rename(f"{front} − 2×{middle} + {back}")


def spread_stats(s: pd.Series) -> dict:
    s = s.dropna()
    ch = s.diff().dropna()
    return {"observations": len(s), "first": s.index.min(), "last": s.index.max(), "mean": float(s.mean()) if len(s) else np.nan,
            "std": float(s.std()) if len(s) > 1 else np.nan, "min": float(s.min()) if len(s) else np.nan,
            "max": float(s.max()) if len(s) else np.nan, "daily_change_std": float(ch.std()) if len(ch) > 1 else np.nan}
