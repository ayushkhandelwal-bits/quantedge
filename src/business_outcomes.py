"""Translate backtest outputs into business-language findings and a transparent classification.

Classification is rule-based, not a weighted score. Each criterion is shown with its
threshold, the measured value and pass/fail, so the reasoning can be audited:

* Weak under current assumptions   – net result ≤ 0, OR out-of-sample Sharpe ≤ 0
* Worth further investigation      – passes every criterion
* Requires more validation         – everything else
* Not assessable                   – data is synthetic (results illustrate mechanics only)

Thresholds are user-configurable on the Business Outcomes page.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Thresholds:
    min_sharpe: float = 0.5
    max_drawdown: float = 0.25          # 25%
    min_oos_degradation: float = 0.5    # OOS Sharpe ≥ 50% of in-sample Sharpe
    max_cost_share: float = 0.30        # costs ≤ 30% of gross profit
    min_trades: int = 10
    beat_benchmark: bool = True


def gross_net(m: dict) -> dict:
    gross, costs = m.get("gross_pnl", 0.0), m.get("total_costs", 0.0)
    return {
        "gross_pnl": gross,
        "charges": m.get("charges", 0.0),
        "slippage": m.get("slippage", 0.0),
        "total_costs": costs,
        "net_pnl_trades": gross - costs,
        "cost_share_of_gross": (costs / gross) if gross > 0 else None,
        "cost_share_of_turnover": (costs / m["turnover"]) if m.get("turnover") else None,
    }


def evaluate(m: dict, bench_return: float | None, wf, th: Thresholds, synthetic: bool) -> dict:
    gn = gross_net(m)
    crit = []

    def add(name, value, target, ok, why):
        crit.append({"Criterion": name, "Measured": value, "Threshold": target,
                     "Result": "Pass" if ok else ("Fail" if ok is False else "n/a"), "Why it matters": why})

    tr = m.get("total_return")
    add("Net return after costs", tr, "> 0", (tr is not None and tr > 0), "A strategy must at least make money after all costs.")
    if th.beat_benchmark:
        ok = None if (tr is None or bench_return is None) else tr > bench_return
        add("Beats buy-and-hold of the same instrument", tr, f"> {bench_return:.1%}" if bench_return is not None else "n/a", ok,
            "If passive holding did better, the active strategy adds cost and complexity without benefit.")
    sh = m.get("sharpe")
    add("Sharpe ratio", sh, f"≥ {th.min_sharpe:g}", None if sh is None else sh >= th.min_sharpe,
        "Return earned per unit of volatility; protects against strategies that only win by taking big risks.")
    dd = m.get("max_drawdown")
    add("Maximum drawdown", dd, f"≤ {th.max_drawdown:.0%}", None if dd is None else dd <= th.max_drawdown,
        "Large peak-to-trough losses are hard to tolerate and often force abandonment at the worst time.")
    oos_sh = getattr(wf, "oos_sharpe_avg", None) if wf is not None else None
    deg = getattr(wf, "degradation", None) if wf is not None else None
    add("Out-of-sample Sharpe (walk-forward)", oos_sh, "> 0", None if oos_sh is None else oos_sh > 0,
        "Performance on data not used to choose parameters is the best available test of robustness.")
    add("Out-of-sample / in-sample Sharpe", deg, f"≥ {th.min_oos_degradation:g}", None if deg is None else deg >= th.min_oos_degradation,
        "A large drop after parameter selection suggests over-fitting.")
    cs = gn["cost_share_of_gross"]
    add("Costs as share of gross profit", cs, f"≤ {th.max_cost_share:.0%}",
        None if cs is None else cs <= th.max_cost_share,
        "If fees and slippage absorb most of the gross edge, small changes in costs can erase it.")
    nt = m.get("trades", 0)
    add("Number of completed trades", nt, f"≥ {th.min_trades}", nt >= th.min_trades,
        "Few trades mean results could be luck; statistics on a handful of trades are unreliable.")

    fails = [c for c in crit if c["Result"] == "Fail"]
    nas = [c for c in crit if c["Result"] == "n/a"]
    if synthetic:
        label, tone = "Not assessable – synthetic data", "neutral"
        reason = "The data is simulated, so these results demonstrate the method only and say nothing about real markets."
    elif (tr is not None and tr <= 0) or (oos_sh is not None and oos_sh <= 0):
        label, tone = "Weak under current assumptions", "negative"
        reason = "It lost money after costs and/or failed to make money in the out-of-sample test windows."
    elif not fails and not nas:
        label, tone = "Worth further investigation", "positive"
        reason = "It passed every criterion. This justifies more research (other periods, instruments, live paper trading) – not an investment decision."
    else:
        label, tone = "Requires more validation", "warning"
        names = [c["Criterion"].lower() for c in fails + nas]
        reason = "It made money but did not clear: " + "; ".join(names) + "."
    return {"label": label, "tone": tone, "reason": reason, "criteria": crit, "gross_net": gn}


def capital_scenarios(m: dict, capital: float, wf_oos: dict | None = None) -> list[dict]:
    """Historical outcomes rescaled to the user's capital. Illustrations, not forecasts."""
    out = []
    if m.get("total_return") is not None:
        out.append({"Scenario": "Full-period result (historical)", "Return": m["total_return"],
                    "Amount": capital * m["total_return"], "Ending value": capital * (1 + m["total_return"])})
    if m.get("cagr") is not None:
        out.append({"Scenario": "One typical year at historical CAGR", "Return": m["cagr"],
                    "Amount": capital * m["cagr"], "Ending value": capital * (1 + m["cagr"])})
    if m.get("max_drawdown") is not None:
        out.append({"Scenario": "Worst historical peak-to-trough fall", "Return": -m["max_drawdown"],
                    "Amount": -capital * m["max_drawdown"], "Ending value": capital * (1 - m["max_drawdown"])})
    if m.get("largest_loss") is not None and m.get("trades"):
        out.append({"Scenario": "Largest single-trade loss (scaled to capital)", "Return": None,
                    "Amount": m["largest_loss"] * capital / m.get("_capital", capital), "Ending value": None})
    if wf_oos and wf_oos.get("total_return") is not None:
        out.append({"Scenario": "Out-of-sample periods only (walk-forward)", "Return": wf_oos["total_return"],
                    "Amount": capital * wf_oos["total_return"], "Ending value": capital * (1 + wf_oos["total_return"])})
    return out


def interpretation(m: dict, bench_return: float | None, name: str) -> str:
    """Plain-language one-paragraph read-out built only from computed numbers."""
    def pct(x):
        return "n/a" if x is None else f"{x:.1%}"
    parts = []
    tr = m.get("total_return")
    if tr is None:
        return "Not enough data to evaluate this strategy."
    parts.append(f"{name} returned {pct(tr)} after costs over the period (CAGR {pct(m.get('cagr'))})")
    if bench_return is not None:
        diff = tr - bench_return
        parts[-1] += f", {'ahead of' if diff > 0 else 'behind'} buy-and-hold ({pct(bench_return)}) by {abs(diff):.1%} points."
    else:
        parts[-1] += "."
    dd = m.get("max_drawdown")
    if dd is not None:
        parts.append(f"The worst fall from a peak was {pct(dd)}.")
    sh = m.get("sharpe")
    if sh is not None:
        qual = "strong" if sh >= 1 else "moderate" if sh >= 0.5 else "weak" if sh >= 0 else "negative"
        parts.append(f"Risk-adjusted performance was {qual} (Sharpe {sh:.2f}).")
    gn = gross_net(m)
    if gn["gross_pnl"] > 0 and gn["cost_share_of_gross"] is not None:
        parts.append(f"Costs consumed {gn['cost_share_of_gross']:.0%} of gross trading profit across {m.get('trades', 0)} trades.")
    elif m.get("trades"):
        parts.append(f"Trades lost money even before costs; costs added ₹{gn['total_costs']:,.0f} to the loss.")
    return " ".join(parts)
