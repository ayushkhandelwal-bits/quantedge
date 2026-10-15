"""Reproducible business-outcomes report: every enabled strategy on every instrument, same assumptions.

Usage:  python scripts/generate_report.py [--mode cache|auto|synthetic] [--out docs/business_outcomes_report.md]

Uses stored Yahoo Finance data when available (run scripts/download_data.py first);
otherwise falls back to SYNTHETIC data and says so prominently in the report.
"""
import argparse
import os
import sys
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd  # noqa: E402

import config  # noqa: E402
from src import analysis  # noqa: E402
from src import business_outcomes as bo  # noqa: E402
from src import walk_forward as wfm  # noqa: E402
from src.backtester import BacktestConfig  # noqa: E402
from src.strategies import ENABLED, REGISTRY, TRADING  # noqa: E402


def pct(x):
    return "n/a" if x is None or x != x else f"{x:+.1%}"


def num(x):
    return "n/a" if x is None or x != x else f"{x:.2f}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="cache", choices=["cache", "auto", "synthetic"])
    ap.add_argument("--start", default=str(config.DEFAULT_START))
    ap.add_argument("--end", default=str(config.DEFAULT_END))
    ap.add_argument("--out", default=os.path.join(config.BASE_DIR, "docs", "business_outcomes_report.md"))
    a = ap.parse_args()
    start, end = date.fromisoformat(a.start), date.fromisoformat(a.end)
    cfg = BacktestConfig(initial_capital=config.INITIAL_CAPITAL)
    rf = config.RISK_FREE_RATE
    rows, statuses, verdicts = [], {}, []
    for sym in config.INSTRUMENTS:
        d = analysis.load_dataset(sym, start, end, a.mode)
        statuses[sym] = d.bundle.status
        bh = analysis.run_strategy(d.clean, "buy_hold", {}, cfg, rf)
        for k in ENABLED:
            r = analysis.run_strategy(d.clean, k, {}, cfg, rf)
            m = r.metrics
            wf = wfm.walk_forward(d.clean, REGISTRY[k], cfg, rf) if k in TRADING else None
            ev = bo.evaluate(m, bh.metrics["total_return"], wf, bo.Thresholds(), d.bundle.is_synthetic) if k in TRADING else None
            rows.append({"Instrument": sym, "Data": d.bundle.status, "Strategy": REGISTRY[k].name, "Net return": pct(m["total_return"]),
                         "CAGR": pct(m["cagr"]), "Sharpe": num(m["sharpe"]), "Max DD": pct(-m["max_drawdown"] if m["max_drawdown"] is not None else None),
                         "Trades": m["trades"], "Costs (₹)": f"{m['total_costs']:,.0f}",
                         "OOS Sharpe": num(wf.oos_sharpe_avg) if wf else "—", "Classification": ev["label"] if ev else "benchmark"})
    df = pd.DataFrame(rows)
    synthetic = [s for s, st in statuses.items() if st == "SYNTHETIC"]
    lines = [f"# Business Outcomes Report", "",
             f"Generated {datetime.now():%Y-%m-%d %H:%M} by `scripts/generate_report.py --mode {a.mode}`. "
             f"Period requested {start} → {end}; capital ₹{cfg.initial_capital:,.0f}; next-open execution; long-only; "
             f"published delivery cost schedule + {cfg.costs.slippage_bps:g} bps slippage; risk-free {rf:.2%}; default parameters.", ""]
    if synthetic:
        lines += ["> **WARNING – SYNTHETIC DATA.** The following instruments had no real data available when this report was generated "
                  f"and were run on simulated prices: {', '.join(synthetic)}. Their rows demonstrate the workflow only and contain **no** "
                  "information about real-market strategy performance. Run `python scripts/download_data.py` on a machine with internet "
                  "access, then `python scripts/generate_report.py` to regenerate this report with real data.", ""]
    lines += ["## Results by instrument and strategy", "", df.to_markdown(index=False), "",
              "## How to read this", "",
              "- *Classification* applies the transparent rules on the Business Outcomes page (net result, buy-and-hold comparison, Sharpe ≥ 0.5, "
              "drawdown ≤ 25%, walk-forward out-of-sample Sharpe > 0 and ≥ 50% of in-sample, costs ≤ 30% of gross profit, ≥ 10 trades).",
              "- Synthetic rows are never classified.",
              "- Historical results are not forecasts; see the Methodology page for limitations.", ""]
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print(f"Wrote {a.out} ({len(df)} rows; synthetic instruments: {len(synthetic)})")


if __name__ == "__main__":
    main()
