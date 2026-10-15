"""Rule-based candlestick pattern detection (transparent, no machine learning).

Definitions use only the OHLC of the signal session and earlier sessions.
Forward returns are measured *after* the signal: from the signal-day close to the close
h sessions later, so the evaluation window never overlaps the information used to detect
the pattern.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class PatternParams:
    doji_body_max: float = 0.10          # body <= 10% of the day's range
    shadow_ratio: float = 2.0            # long shadow >= 2x body (hammer / shooting star)
    small_shadow_max: float = 0.25       # opposite shadow <= 25% of range
    trend_lookback: int = 10             # prior trend measured vs 10-session SMA
    require_trend: bool = True           # hammer needs prior downtrend, star needs prior uptrend
    marubozu_body_min: float = 0.90      # Marubozu: body >= 90% of range (almost no shadows)
    long_body_min: float = 0.60          # "long" candle (stars, soldiers/crows): body >= 60% of range
    star_body_max: float = 0.30          # middle star candle body <= 30% of the first candle's body
    soldier_shadow_max: float = 0.30     # soldiers/crows: closing-side shadow <= 30% of range


PATTERNS = {
    "Doji": {"bias": "Neutral", "rule": "Real body ≤ {doji_body_max:.0%} of the High–Low range (indecision)."},
    "Hammer": {"bias": "Bullish", "rule": "Lower shadow ≥ {shadow_ratio:g}× body, upper shadow ≤ {small_shadow_max:.0%} of range"
               "{trend_down}."},
    "Shooting Star": {"bias": "Bearish", "rule": "Upper shadow ≥ {shadow_ratio:g}× body, lower shadow ≤ {small_shadow_max:.0%} of range"
                      "{trend_up}."},
    "Bullish Engulfing": {"bias": "Bullish", "rule": "Prior candle bearish; today bullish; today's body opens at/below prior close and "
                          "closes at/above prior open (body fully engulfs the prior body)."},
    "Bearish Engulfing": {"bias": "Bearish", "rule": "Prior candle bullish; today bearish; today's body opens at/above prior close and "
                          "closes at/below prior open."},
    "Bullish Marubozu": {"bias": "Bullish", "rule": "Bullish candle whose body is ≥ {marubozu_body_min:.0%} of the High–Low range "
                         "(buyers in control from open to close)."},
    "Bearish Marubozu": {"bias": "Bearish", "rule": "Bearish candle whose body is ≥ {marubozu_body_min:.0%} of the High–Low range "
                         "(sellers in control from open to close)."},
    "Morning Star": {"bias": "Bullish", "rule": "Three candles: (1) long bearish (body ≥ {long_body_min:.0%} of range); (2) small body "
                     "(≤ {star_body_max:.0%} of candle 1's body) closing below candle 1's close; (3) bullish, closing above the midpoint "
                     "of candle 1's body{trend_down3}."},
    "Evening Star": {"bias": "Bearish", "rule": "Three candles: (1) long bullish (body ≥ {long_body_min:.0%} of range); (2) small body "
                     "(≤ {star_body_max:.0%} of candle 1's body) closing above candle 1's close; (3) bearish, closing below the midpoint "
                     "of candle 1's body{trend_up3}."},
    "Three White Soldiers": {"bias": "Bullish", "rule": "Three consecutive long bullish candles (body ≥ {long_body_min:.0%} of range), "
                             "each opening within the previous body, closing higher than the previous close, with upper shadow "
                             "≤ {soldier_shadow_max:.0%} of range."},
    "Three Black Crows": {"bias": "Bearish", "rule": "Three consecutive long bearish candles (body ≥ {long_body_min:.0%} of range), "
                          "each opening within the previous body, closing lower than the previous close, with lower shadow "
                          "≤ {soldier_shadow_max:.0%} of range."},
}

# The five original patterns keep their definitions; the strategies built on them are unaffected.
ORIGINAL_PATTERNS = ["Doji", "Hammer", "Shooting Star", "Bullish Engulfing", "Bearish Engulfing"]


def describe_rule(name: str, p: PatternParams) -> str:
    td = f", after a decline (prior close below its {p.trend_lookback}-day average)" if p.require_trend else ""
    tu = f", after a rise (prior close above its {p.trend_lookback}-day average)" if p.require_trend else ""
    td3 = f", after a decline (close before the pattern below its {p.trend_lookback}-day average)" if p.require_trend else ""
    tu3 = f", after a rise (close before the pattern above its {p.trend_lookback}-day average)" if p.require_trend else ""
    return PATTERNS[name]["rule"].format(doji_body_max=p.doji_body_max, shadow_ratio=p.shadow_ratio,
                                         small_shadow_max=p.small_shadow_max, trend_down=td, trend_up=tu,
                                         marubozu_body_min=p.marubozu_body_min, long_body_min=p.long_body_min,
                                         star_body_max=p.star_body_max, soldier_shadow_max=p.soldier_shadow_max,
                                         trend_down3=td3, trend_up3=tu3)


def detect(df: pd.DataFrame, p: PatternParams | None = None) -> pd.DataFrame:
    """Boolean frame (one column per pattern) aligned to df.index."""
    p = p or PatternParams()
    o, h, l, c = df["Open"], df["High"], df["Low"], df["Close"]
    rng = (h - l).replace(0, np.nan)
    body = (c - o).abs()
    upper = h - np.maximum(o, c)
    lower = np.minimum(o, c) - l
    prev_o, prev_c = o.shift(1), c.shift(1)
    trend_ma = c.rolling(p.trend_lookback).mean()
    down_before = (prev_c < trend_ma.shift(1)) if p.require_trend else pd.Series(True, index=df.index)
    up_before = (prev_c > trend_ma.shift(1)) if p.require_trend else pd.Series(True, index=df.index)
    body_nz = body.where(body > 0, rng * 0.01)  # avoid 0x comparisons on exact dojis

    out = pd.DataFrame(index=df.index)
    out["Doji"] = body <= p.doji_body_max * rng
    out["Hammer"] = (lower >= p.shadow_ratio * body_nz) & (upper <= p.small_shadow_max * rng) & down_before & ~out["Doji"]
    out["Shooting Star"] = (upper >= p.shadow_ratio * body_nz) & (lower <= p.small_shadow_max * rng) & up_before & ~out["Doji"]
    out["Bullish Engulfing"] = (prev_c < prev_o) & (c > o) & (o <= prev_c) & (c >= prev_o) & (body > (prev_c - prev_o).abs())
    out["Bearish Engulfing"] = (prev_c > prev_o) & (c < o) & (o >= prev_c) & (c <= prev_o) & (body > (prev_c - prev_o).abs())

    # ---- added patterns (all use only sessions t-2, t-1, t) ----
    bull, bear = c > o, c < o
    out["Bullish Marubozu"] = bull & (body >= p.marubozu_body_min * rng)
    out["Bearish Marubozu"] = bear & (body >= p.marubozu_body_min * rng)

    long_c = body >= p.long_body_min * rng
    o1, c1, b1, long1 = o.shift(2), c.shift(2), body.shift(2), long_c.shift(2).fillna(False).astype(bool)
    o2, c2, b2 = o.shift(1), c.shift(1), body.shift(1)
    mid1 = (o1 + c1) / 2
    trend_ma3 = trend_ma.shift(3)
    down3 = (c.shift(3) < trend_ma3) if p.require_trend else pd.Series(True, index=df.index)
    up3 = (c.shift(3) > trend_ma3) if p.require_trend else pd.Series(True, index=df.index)
    out["Morning Star"] = (c1 < o1) & long1 & (b2 <= p.star_body_max * b1) & (c2 < c1) & bull & (c > mid1) & down3
    out["Evening Star"] = (c1 > o1) & long1 & (b2 <= p.star_body_max * b1) & (c2 > c1) & bear & (c < mid1) & up3

    def _run(direction):
        cond = []
        for k in range(3):
            ok, ck, okp, ckp = o.shift(k), c.shift(k), o.shift(k + 1), c.shift(k + 1)
            rk, hk, lk = rng.shift(k), h.shift(k), l.shift(k)
            bk = (ck - ok).abs()
            if direction > 0:
                shadow = hk - ck
                c_ok = (ck > ok) & (bk >= p.long_body_min * rk) & (shadow <= p.soldier_shadow_max * rk)
                if k < 2:   # link to the previous soldier
                    c_ok &= (ckp > okp) & (ok >= okp) & (ok <= ckp) & (ck > ckp)
            else:
                shadow = ck - lk
                c_ok = (ck < ok) & (bk >= p.long_body_min * rk) & (shadow <= p.soldier_shadow_max * rk)
                if k < 2:
                    c_ok &= (ckp < okp) & (ok <= okp) & (ok >= ckp) & (ck < ckp)
            cond.append(c_ok)
        return cond[0] & cond[1] & cond[2]

    out["Three White Soldiers"] = _run(+1)
    out["Three Black Crows"] = _run(-1)
    return out.fillna(False).astype(bool)


def forward_returns(close: pd.Series, horizons=(1, 5, 10)) -> pd.DataFrame:
    """Return from the close on date t to the close h sessions later (NaN where not yet observable)."""
    return pd.DataFrame({f"fwd_{h}d": close.shift(-h) / close - 1 for h in horizons}, index=close.index)


def events(df: pd.DataFrame, symbol: str, p: PatternParams | None = None, horizons=(1, 5, 10)) -> pd.DataFrame:
    """One row per detected pattern occurrence with its subsequent returns."""
    p = p or PatternParams()
    det = detect(df, p)
    fwd = forward_returns(df["Close"], horizons)
    rows = []
    for name in PATTERNS:
        for d in det.index[det[name]]:
            r = {"Date": d, "Instrument": symbol, "Pattern": name, "Bias": PATTERNS[name]["bias"],
                 "Open": df.at[d, "Open"], "High": df.at[d, "High"], "Low": df.at[d, "Low"], "Close": df.at[d, "Close"]}
            for col in fwd.columns:
                r[col] = fwd.at[d, col]
            rows.append(r)
    return pd.DataFrame(rows).sort_values("Date").reset_index(drop=True) if rows else pd.DataFrame(
        columns=["Date", "Instrument", "Pattern", "Bias", "Open", "High", "Low", "Close"] + list(fwd.columns))


def summary(ev: pd.DataFrame, close: pd.Series, horizons=(1, 5, 10)) -> pd.DataFrame:
    """Occurrences, directional hit rate and average forward return per pattern and horizon,
    compared with the unconditional average return over the same horizon (base rate)."""
    base = forward_returns(close, horizons)
    rows = []
    for name, meta in PATTERNS.items():
        sub = ev[ev["Pattern"] == name] if len(ev) else ev
        for h in horizons:
            col = f"fwd_{h}d"
            vals = sub[col].dropna() if len(sub) else pd.Series(dtype=float)
            n = len(vals)
            if meta["bias"] == "Bullish":
                hit = (vals > 0).mean() if n else np.nan
                base_hit = (base[col].dropna() > 0).mean()
            elif meta["bias"] == "Bearish":
                hit = (vals < 0).mean() if n else np.nan
                base_hit = (base[col].dropna() < 0).mean()
            else:
                hit, base_hit = np.nan, np.nan
            rows.append({"Pattern": name, "Bias": meta["bias"], "Horizon (sessions)": h, "Occurrences": n,
                         "Hit rate": hit, "Base-rate hit": base_hit,
                         "Avg return": vals.mean() if n else np.nan,
                         "Avg return, all days": base[col].mean(),
                         "Median return": vals.median() if n else np.nan})
    return pd.DataFrame(rows)
