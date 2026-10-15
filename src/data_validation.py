"""Data validation and transparent cleaning for daily OHLCV.

Every treatment is recorded in a CleaningReport so the UI can show exactly what changed.
Nothing is forward-filled: missing prices are dropped (and counted), missing volume is
kept as NaN and flagged, so indicators are never computed on invented prices.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import numpy as np
import pandas as pd

PRICE_COLS = ["Open", "High", "Low", "Close"]


@dataclass
class CleaningReport:
    rows_in: int = 0
    rows_out: int = 0
    steps: list[dict] = field(default_factory=list)     # {"check","found","treatment"}
    flags: pd.DataFrame | None = None                    # per-row flags on the cleaned data
    coverage: dict = field(default_factory=dict)

    def add(self, check: str, found: int, treatment: str):
        self.steps.append({"Check": check, "Rows affected": int(found), "Treatment": treatment})

    def as_frame(self) -> pd.DataFrame:
        return pd.DataFrame(self.steps)


def clean_ohlcv(df: pd.DataFrame, requested_start: date | None = None, requested_end: date | None = None,
                gap_threshold: float = 0.05, volume_z: float = 4.0) -> tuple[pd.DataFrame, CleaningReport]:
    rep = CleaningReport(rows_in=len(df))
    out = df.copy()

    # 1. chronological order
    unsorted = int((~out.index.to_series().diff().dropna().ge(pd.Timedelta(0))).sum())
    out = out.sort_index()
    rep.add("Out-of-order timestamps", unsorted, "Sorted chronologically" if unsorted else "None needed")

    # 2. duplicate timestamps
    dups = int(out.index.duplicated(keep="last").sum())
    out = out[~out.index.duplicated(keep="last")]
    rep.add("Duplicate timestamps", dups, "Kept the last record for each date" if dups else "None needed")

    # 3. missing prices
    miss_px = out[PRICE_COLS].isna().any(axis=1)
    out = out[~miss_px]
    rep.add("Missing price values", int(miss_px.sum()), "Row removed (prices are never filled in)" if miss_px.any() else "None needed")

    # 4. invalid prices
    nonpos = (out[PRICE_COLS] <= 0).any(axis=1)
    incons = (out["High"] < out["Low"]) | (out["Close"] > out["High"] * 1.0001) | (out["Close"] < out["Low"] * 0.9999) \
        | (out["Open"] > out["High"] * 1.0001) | (out["Open"] < out["Low"] * 0.9999)
    bad = nonpos | incons
    out = out[~bad]
    rep.add("Invalid prices (≤0 or outside High–Low)", int(bad.sum()), "Row removed" if bad.any() else "None needed")

    # 5. volume
    miss_vol = int(out["Volume"].isna().sum())
    zero_vol = int((out["Volume"] == 0).sum())
    rep.add("Missing volume", miss_vol, "Kept; volume left blank and flagged (prices unaffected)" if miss_vol else "None needed")
    rep.add("Zero volume", zero_vol, "Kept and flagged (common for indices on Yahoo Finance)" if zero_vol else "None needed")

    # flags (informational, no removal)
    prev_close = out["Close"].shift(1)
    gap = (out["Open"] / prev_close - 1)
    lv = np.log(out["Volume"].where(out["Volume"] > 0))
    z = (lv - lv.rolling(60, min_periods=20).mean()) / lv.rolling(60, min_periods=20).std()
    cal_gap = out.index.to_series().diff().dt.days
    flags = pd.DataFrame({
        "price_gap": gap.abs() > gap_threshold,
        "gap_pct": gap * 100,
        "volume_missing": out["Volume"].isna(),
        "volume_zero": out["Volume"] == 0,
        "volume_spike": z.abs() > volume_z,
        "calendar_gap_days": cal_gap,
    }, index=out.index)
    rep.add(f"Overnight price gaps > {gap_threshold:.0%}", int(flags["price_gap"].sum()), "Kept and flagged (genuine market moves)")
    rep.add(f"Volume anomalies (|z| > {volume_z:g} vs 60-day log volume)", int(flags["volume_spike"].sum()), "Kept and flagged")
    long_gaps = int((cal_gap > 5).sum())
    rep.add("Calendar gaps > 5 days between sessions", long_gaps, "Kept; no rows invented for missing sessions")

    rep.rows_out = len(out)
    rep.flags = flags
    if len(out):
        first, last = out.index.min().date(), out.index.max().date()
        rep.coverage = {
            "requested_start": requested_start, "requested_end": requested_end,
            "actual_start": first, "actual_end": last,
            "sessions": len(out),
            "years": round((last - first).days / 365.25, 2),
            "short_of_request_days": max(0, (first - requested_start).days) if requested_start else 0,
            "short_at_end_days": max(0, (requested_end - last).days) if requested_end else 0,
        }
    return out, rep


def dataset_summary(raw: pd.DataFrame, clean: pd.DataFrame) -> dict:
    return {
        "rows_raw": len(raw),
        "rows_clean": len(clean),
        "columns": raw.shape[1] + 1,       # + Date index
        "missing_values": int(raw.isna().sum().sum()),
        "duplicate_timestamps": int(raw.index.duplicated().sum()),
        "first": clean.index.min().date() if len(clean) else None,
        "last": clean.index.max().date() if len(clean) else None,
    }
