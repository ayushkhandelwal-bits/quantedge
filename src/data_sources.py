"""Market-data access: Yahoo Finance (via yfinance), local cache, and synthetic fallback.

Resolution order for a request (mode="auto"):
    1. Local cache that covers the requested range       -> label CACHED
    2. Live yfinance download (with retries/back-off)     -> label LIVE, then cached
    3. Any local cache for the symbol (partial coverage)  -> label CACHED (coverage shown)
    4. Deterministic synthetic demo series               -> label SYNTHETIC

The app never presents synthetic data as market data: every DataBundle carries a
``source`` label and ``is_synthetic`` flag that the UI displays.
"""
from __future__ import annotations

import json
import os
import time
import zlib
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd

import config

OHLCV = ["Open", "High", "Low", "Close", "Volume"]

# symbol -> time of the last failed download. In "auto" mode a symbol that just failed is not
# retried for FAIL_COOLDOWN seconds, so an offline session does not wait on every page.
_RECENT_FAILURES: dict[str, float] = {}
FAIL_COOLDOWN = 600


@dataclass
class DataBundle:
    symbol: str
    df: pd.DataFrame                     # raw (pre-cleaning) OHLCV, DatetimeIndex named "Date"
    source: str                          # one of config.SRC_*
    is_synthetic: bool
    requested_start: date
    requested_end: date
    fetched_at: str | None = None        # ISO time of the download that produced this data
    messages: list[str] = field(default_factory=list)   # warnings / errors for the UI
    meta: dict = field(default_factory=dict)

    @property
    def status(self) -> str:
        if self.is_synthetic:
            return "SYNTHETIC"
        return "LIVE" if self.source == config.SRC_LIVE else "CACHED"


# --------------------------------------------------------------------------- helpers
def _safe_name(symbol: str) -> str:
    return symbol.replace("^", "IDX_").replace(".", "_").replace("/", "_")


def raw_path(symbol: str) -> str:
    return os.path.join(config.RAW_DIR, f"{_safe_name(symbol)}.csv")


def meta_path(symbol: str) -> str:
    return os.path.join(config.RAW_DIR, f"{_safe_name(symbol)}.meta.json")


def sample_path(symbol: str) -> str:
    return os.path.join(config.SAMPLE_DIR, f"{_safe_name(symbol)}_SYNTHETIC.csv")


def standardise(df: pd.DataFrame) -> pd.DataFrame:
    """Return a frame with a tz-naive DatetimeIndex 'Date' and columns Open..Volume."""
    if df is None or df.empty:
        return pd.DataFrame(columns=OHLCV, index=pd.DatetimeIndex([], name="Date"))
    out = df.copy()
    if isinstance(out.columns, pd.MultiIndex):          # yfinance multi-ticker layout
        out.columns = out.columns.get_level_values(0)
    out = out.rename(columns={c: str(c).strip().title() for c in out.columns})
    if "Date" in out.columns:
        out = out.set_index("Date")
    out.index = pd.to_datetime(out.index)
    if getattr(out.index, "tz", None) is not None:
        out.index = out.index.tz_localize(None)
    out.index = out.index.normalize()
    out.index.name = "Date"
    for c in OHLCV:
        if c not in out.columns:
            out[c] = np.nan
    out = out[OHLCV].apply(pd.to_numeric, errors="coerce")
    return out


# --------------------------------------------------------------------------- cache
def save_cache(symbol: str, df: pd.DataFrame, meta: dict) -> None:
    df.to_csv(raw_path(symbol))
    with open(meta_path(symbol), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2, default=str)


def load_cache(symbol: str) -> tuple[pd.DataFrame | None, dict]:
    p = raw_path(symbol)
    if not os.path.exists(p):
        return None, {}
    try:
        df = standardise(pd.read_csv(p, parse_dates=["Date"]))
    except Exception:
        return None, {}
    meta = {}
    if os.path.exists(meta_path(symbol)):
        try:
            with open(meta_path(symbol), encoding="utf-8") as fh:
                meta = json.load(fh)
        except Exception:
            meta = {}
    return df, meta


def list_cached() -> list[dict]:
    """Inventory of locally stored real data (for the 'select stored data' control)."""
    rows = []
    for sym in config.INSTRUMENTS:
        df, meta = load_cache(sym)
        if df is not None and not df.empty:
            rows.append({
                "Symbol": sym,
                "Name": config.INSTRUMENTS[sym]["name"],
                "First": df.index.min().date(),
                "Last": df.index.max().date(),
                "Rows": len(df),
                "Downloaded": meta.get("fetched_at", "unknown"),
            })
    return rows


def cache_covers(df: pd.DataFrame, start: date, end: date, tolerance_days: int = 7) -> bool:
    if df is None or df.empty:
        return False
    first, last = df.index.min().date(), df.index.max().date()
    return first <= start + timedelta(days=tolerance_days) and last >= min(end, date.today()) - timedelta(days=tolerance_days)


# --------------------------------------------------------------------------- yfinance
_REACH = {"t": 0.0, "ok": True}


def yahoo_reachable(timeout: float = 4.0) -> bool:
    """Fast connectivity probe (any HTTP response counts as reachable). Result cached for 60 s,
    so an offline session fails in seconds instead of waiting on retries for every symbol."""
    if time.time() - _REACH["t"] < 60:
        return _REACH["ok"]
    try:
        import requests
        requests.head("https://query1.finance.yahoo.com", timeout=timeout)
        ok = True
    except Exception:  # noqa: BLE001
        ok = False
    _REACH.update(t=time.time(), ok=ok)
    return ok

def fetch_yfinance(symbol: str, start: date, end: date, *, retries: int = config.YF_MAX_RETRIES,
                   backoff: float = config.YF_BACKOFF_SECONDS, downloader=None) -> pd.DataFrame:
    """Download daily OHLCV from Yahoo Finance with retries and exponential back-off.

    Prices are adjusted for splits and dividends (``auto_adjust=True``).
    ``downloader`` is injectable for testing; defaults to ``yfinance.download``.
    Raises RuntimeError with a readable message if every attempt fails.
    """
    if downloader is None:
        if not yahoo_reachable():
            raise RuntimeError("Yahoo Finance is not reachable from this machine (no internet connection, firewall or proxy). "
                               "No retries attempted.")
        import yfinance as yf  # imported lazily so the app starts even without it
        downloader = yf.download
    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            raw = downloader(symbol, start=str(start), end=str(end + timedelta(days=1)), interval="1d",
                             auto_adjust=True, progress=False, threads=False, timeout=config.YF_TIMEOUT_SECONDS)
            df = standardise(raw)
            df = df.dropna(how="all")
            if df.empty:
                raise RuntimeError("Yahoo Finance returned no rows (symbol unavailable, rate-limited, or no data in range)")
            return df
        except Exception as e:  # noqa: BLE001 - surface any provider error to the user
            last_err = e
            msg = str(e).lower()
            wait = backoff * (2 ** (attempt - 1))
            if "rate" in msg or "too many" in msg or "429" in msg:
                wait *= 3
            if attempt < retries:
                time.sleep(wait)
    raise RuntimeError(f"Download failed for {symbol} after {retries} attempts: {last_err}")


# --------------------------------------------------------------------------- synthetic
def synthetic_ohlcv(symbol: str, start: date, end: date, inject_issues: bool = True) -> tuple[pd.DataFrame, dict]:
    """Deterministic synthetic daily OHLCV for offline demonstration.

    A regime-switching geometric Brownian motion (calm-up / volatile-down / sideways regimes)
    seeded from the symbol name, so the same symbol always yields the same series.
    A few deliberate data-quality issues are injected (and recorded in the metadata) so the
    data-quality tab has something to show. THIS IS NOT MARKET DATA.
    """
    seed = zlib.crc32(symbol.encode()) % (2**31)
    rng = np.random.default_rng(seed)
    days = pd.bdate_range(start, end, name="Date")          # weekdays only; no exchange holidays
    n = len(days)
    if n < 2:
        raise ValueError("Date range too short for synthetic data")
    regimes = {0: (0.14, 0.15), 1: (-0.18, 0.32), 2: (0.02, 0.12)}   # annual drift, vol
    trans = np.array([[0.985, 0.007, 0.008], [0.02, 0.97, 0.01], [0.012, 0.006, 0.982]])
    state, states = 0, np.empty(n, dtype=int)
    for i in range(n):
        states[i] = state
        state = rng.choice(3, p=trans[state])
    mu = np.array([regimes[s][0] for s in states]) / 252
    sig = np.array([regimes[s][1] for s in states]) / np.sqrt(252)
    # Daily log return = overnight gap + intraday move, drawn independently, so the
    # synthetic series has no built-in tendency for gaps to fill or extend.
    gap_share = 0.35                                    # share of daily variance arriving overnight
    shocks = rng.standard_t(df=5, size=n) * np.sqrt(3 / 5)
    gap = shocks * sig * np.sqrt(gap_share)
    intraday = rng.standard_t(df=5, size=n) * np.sqrt(3 / 5) * sig * np.sqrt(1 - gap_share) + mu - 0.5 * sig**2
    base = 500 + (seed % 3000)
    close = base * np.exp(np.cumsum(gap + intraday))
    open_ = close * np.exp(-intraday)                   # open sits between yesterday's close and today's close path
    hi = np.maximum(open_, close) * np.exp(np.abs(rng.normal(0, sig * 0.6)))
    lo = np.minimum(open_, close) * np.exp(-np.abs(rng.normal(0, sig * 0.6)))
    vol = (rng.lognormal(mean=14, sigma=0.35, size=n) * (1 + 2 * (states == 1))).round()
    df = pd.DataFrame({"Open": open_, "High": hi, "Low": lo, "Close": close, "Volume": vol}, index=days).round(2)
    issues = []
    if inject_issues and n > 60:
        k = int(n * 0.5)
        df.iloc[k, df.columns.get_loc("Volume")] = np.nan
        issues.append(f"missing volume on {df.index[k].date()}")
        df.iloc[k + 7, df.columns.get_loc("Volume")] = 0
        issues.append(f"zero volume on {df.index[k + 7].date()}")
        dup = df.iloc[[k + 15]]
        df = pd.concat([df, dup]).sort_index()
        issues.append(f"duplicate row for {dup.index[0].date()}")
    meta = {"generator": "regime-switching GBM (Student-t shocks)", "seed": seed,
            "injected_issues": issues, "label": config.SRC_SYNTHETIC}
    return df, meta


# --------------------------------------------------------------------------- main entry
def get_data(symbol: str, start: date, end: date, mode: str = "auto", downloader=None,
             allow_synthetic: bool = True) -> DataBundle:
    """Get daily OHLCV for ``symbol``.

    mode: "auto"      cache if it covers the range, else download, else fall back
          "refresh"   force a download attempt, fall back if it fails
          "cache"     never touch the network
          "synthetic" demo data only
    """
    msgs: list[str] = []
    if mode == "synthetic":
        df, meta = synthetic_ohlcv(symbol, start, end)
        return DataBundle(symbol, df, config.SRC_SYNTHETIC, True, start, end, None,
                          ["Synthetic demo data selected: prices are simulated and must not be used to judge real strategies."], meta)

    cached, cmeta = load_cache(symbol)
    if mode in ("auto", "cache") and cache_covers(cached, start, end):
        sub = cached.loc[str(start):str(end)]
        stale = _is_stale(cmeta)
        if stale:
            msgs.append(f"Cached data was downloaded at {cmeta.get('fetched_at')}; use Refresh for newer observations.")
        return DataBundle(symbol, sub, config.SRC_CACHED, False, start, end, cmeta.get("fetched_at"), msgs, cmeta)

    recently_failed = time.time() - _RECENT_FAILURES.get(symbol, 0) < FAIL_COOLDOWN
    if mode == "auto" and recently_failed and downloader is None:
        msgs.append("Live download skipped: it failed within the last 10 minutes (use Refresh to retry).")
    elif mode in ("auto", "refresh"):
        if mode == "refresh":
            _REACH["t"] = 0.0          # re-probe connectivity on an explicit refresh
        try:
            df = fetch_yfinance(symbol, start, end, downloader=downloader)
            fetched_at = datetime.now().isoformat(timespec="seconds")
            meta = {"symbol": symbol, "source": "Yahoo Finance via yfinance", "fetched_at": fetched_at,
                    "requested_start": str(start), "requested_end": str(end), "auto_adjust": True,
                    "rows": len(df)}
            merged = df if cached is None else pd.concat([cached, df])
            merged = merged[~merged.index.duplicated(keep="last")].sort_index()
            save_cache(symbol, merged, meta)
            _RECENT_FAILURES.pop(symbol, None)
            return DataBundle(symbol, df, config.SRC_LIVE, False, start, end, fetched_at, msgs, meta)
        except Exception as e:  # noqa: BLE001
            _RECENT_FAILURES[symbol] = time.time()
            msgs.append(f"Live download unavailable: {e}")

    if cached is not None and not cached.empty:
        sub = cached.loc[str(start):str(end)]
        if not sub.empty:
            msgs.append("Using previously downloaded data; it may not cover the full requested range.")
            return DataBundle(symbol, sub, config.SRC_CACHED, False, start, end, cmeta.get("fetched_at"), msgs, cmeta)

    if not allow_synthetic:
        raise RuntimeError("; ".join(msgs) or f"No data available for {symbol}")
    df, meta = synthetic_ohlcv(symbol, start, end)
    msgs.append("No real data available offline — showing SYNTHETIC demo data. Results illustrate the workflow only.")
    return DataBundle(symbol, df, config.SRC_SYNTHETIC, True, start, end, None, msgs, meta)


def _is_stale(meta: dict) -> bool:
    try:
        t = datetime.fromisoformat(meta["fetched_at"])
    except Exception:
        return True
    return datetime.now() - t > timedelta(hours=config.CACHE_MAX_AGE_HOURS)


def write_sample_files(start: date = date(2021, 1, 1), end: date = date(2025, 12, 31)) -> list[str]:
    """Write the bundled synthetic sample CSVs (labelled SYNTHETIC in the filename and a header file)."""
    out = []
    for sym in config.INSTRUMENTS:
        df, meta = synthetic_ohlcv(sym, start, end)
        p = sample_path(sym)
        df.to_csv(p)
        out.append(p)
    with open(os.path.join(config.SAMPLE_DIR, "README.txt"), "w", encoding="utf-8") as fh:
        fh.write("All files in this folder are SYNTHETIC demonstration data generated by\n"
                 "src/data_sources.synthetic_ohlcv (regime-switching GBM, seeded by symbol).\n"
                 "They are NOT market prices and must not be used to assess real strategies.\n")
    return out
