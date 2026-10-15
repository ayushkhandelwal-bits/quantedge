"""Download ~5 years of daily OHLCV for the configured universe into data/raw/ (free, via yfinance).

Usage:  python scripts/download_data.py [--years 5] [--symbols RELIANCE.NS ITC.NS ...]
After this runs once, the dashboard works offline with real (cached) data.
"""
import argparse
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config  # noqa: E402
from src import data_sources as ds  # noqa: E402
from src.data_validation import clean_ohlcv  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", type=int, default=config.DEFAULT_YEARS)
    ap.add_argument("--symbols", nargs="*", default=list(config.INSTRUMENTS))
    a = ap.parse_args()
    end = date.today()
    start = date(end.year - a.years, end.month, min(end.day, 28))
    ok = 0
    for sym in a.symbols:
        try:
            b = ds.get_data(sym, start, end, mode="refresh", allow_synthetic=False)
        except RuntimeError as e:
            print(f"FAIL {sym:15s} {e}")
            continue
        if b.status == "LIVE":
            clean, rep = clean_ohlcv(b.df, start, end)
            c = rep.coverage
            print(f"OK   {sym:15s} {c['actual_start']} → {c['actual_end']}  {c['sessions']:5d} sessions  -> {ds.raw_path(sym)}")
            ok += 1
        else:
            print(f"FAIL {sym:15s} {' | '.join(b.messages)}")
    print(f"\n{ok}/{len(a.symbols)} instruments downloaded.")


if __name__ == "__main__":
    main()
