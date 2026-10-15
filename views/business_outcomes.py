import re
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src import business_outcomes as bo
from src import ui
from src.strategies import REGISTRY

ui.header("Business Outcomes & Decision Support", "From backtest statistics to a decision an investment committee can audit.")
ds = ui.dataset()
ui.after_load()
ui.data_status_banner(ds)
s = st.session_state
r = ui.run()
m = r.metrics
bh = ui.run("buy_hold")
strat = REGISTRY[s.strategy]
wf = ui.walk_forward() if strat.params else None

with st.expander("Classification thresholds (editable)", expanded=False):
    c = st.columns(5)
    th = bo.Thresholds(
        min_sharpe=c[0].number_input("Min Sharpe", -1.0, 3.0, 0.5, 0.1),
        max_drawdown=c[1].number_input("Max drawdown (%)", 5.0, 90.0, 25.0, 1.0) / 100,
        min_oos_degradation=c[2].number_input("Min OOS/IS Sharpe", 0.0, 2.0, 0.5, 0.05),
        max_cost_share=c[3].number_input("Max costs / gross profit (%)", 1.0, 100.0, 30.0, 1.0) / 100,
        min_trades=int(c[4].number_input("Min trades", 1, 500, 10, 1)),
    )
ev = bo.evaluate(m, bh.metrics["total_return"], wf, th, ds.bundle.is_synthetic)
gn = ev["gross_net"]

tone = {"positive": "#e7f5e7", "warning": "#fff3d6", "negative": "#fbe9e9", "neutral": "#f0efec"}[ev["tone"]]
icon = {"positive": "✅", "warning": "⚠️", "negative": "⛔", "neutral": "ℹ️"}[ev["tone"]]
st.markdown(f"<div class='ql-verdict' style='background:{tone}'><div class='t'>{icon} {strat.name}: {ev['label']}</div>{ev['reason']}</div>",
            unsafe_allow_html=True)

st.markdown("## A. Profitability after costs")
c = st.columns(4)
ui.kpi(c[0], "Gross trading P&L", ui.inr(gn["gross_pnl"]), "before any costs")
ui.kpi(c[1], "Total transaction costs", ui.inr(gn["total_costs"]), f"charges {ui.inr(gn['charges'])} · slippage {ui.inr(gn['slippage'])}")
ui.kpi(c[2], "Net P&L", ui.inr(m["net_pnl"]), f"net return {ui.pct(m['total_return'], 1, True)} on {ui.inr(s.capital)}")
ui.kpi(c[3], "Costs / gross profit", ui.pct(gn["cost_share_of_gross"], 0) if gn["cost_share_of_gross"] is not None else "n/a",
       f"costs / turnover {ui.pct(gn['cost_share_of_turnover'], 2)}" if gn["cost_share_of_turnover"] else "no turnover")
fig = go.Figure(go.Waterfall(
    x=["Gross P&L", "Charges", "Slippage", "Net P&L"], measure=["absolute", "relative", "relative", "total"],
    y=[gn["gross_pnl"], -gn["charges"], -gn["slippage"], 0], connector=dict(line=dict(color=ui.AXIS)),
    increasing=dict(marker=dict(color=ui.SERIES[0])), decreasing=dict(marker=dict(color=ui.CRIT)), totals=dict(marker=dict(color=ui.SERIES[1])),
    text=[ui.inr(gn["gross_pnl"]), ui.inr(-gn["charges"]), ui.inr(-gn["slippage"]), ui.inr(gn["net_pnl_trades"])], textposition="outside",
    hovertemplate="%{x}: ₹%{y:,.0f}<extra></extra>"))
st.plotly_chart(ui.style(fig, "From gross to net trading profit", "₹", height=340, legend=False), width="stretch")
if gn["gross_pnl"] <= 0:
    msg = "The strategy lost money before costs, so costs only deepened the loss – the problem is the signal, not the fees."
elif gn["cost_share_of_gross"] is not None and gn["cost_share_of_gross"] > th.max_cost_share:
    msg = f"Costs absorbed {gn['cost_share_of_gross']:.0%} of gross profit – above the {th.max_cost_share:.0%} tolerance. Small increases in spreads or fees could eliminate the edge."
else:
    msg = f"Costs absorbed {ui.pct(gn['cost_share_of_gross'], 0)} of gross profit – the result is not dominated by trading frictions."
ui.takeaway(msg)

st.markdown("## B. Risk-adjusted performance")
runs = ui.run_all()
rows = [{"Strategy": REGISTRY[k].name, "Net return": x.metrics["total_return"], "Volatility": x.metrics["volatility"],
         "Sharpe": x.metrics["sharpe"], "Max drawdown": x.metrics["max_drawdown"], "Return / drawdown": x.metrics["calmar"],
         "Trades": x.metrics["trades"]} for k, x in runs.items()]
rt = pd.DataFrame(rows).astype({"Net return": float, "Volatility": float, "Sharpe": float, "Max drawdown": float, "Return / drawdown": float}).sort_values("Sharpe", ascending=False, na_position="last")
st.dataframe(rt.style.format({"Net return": lambda x: ui.pct(x, 1, True), "Volatility": lambda x: ui.pct(x), "Sharpe": ui.num,
                              "Max drawdown": lambda x: ui.pct(x), "Return / drawdown": ui.num}, na_rep="n/a"),
             hide_index=True, width="stretch")
top = rt.dropna(subset=["Sharpe"]).head(2)
if len(top):
    ui.takeaway(f"Ranked by Sharpe, **{top.iloc[0]['Strategy']}** earned the most return per unit of volatility"
                + (f", followed by {top.iloc[1]['Strategy']}" if len(top) > 1 else "")
                + ". No single metric decides 'best': check that a high Sharpe is not built on very few trades or an unacceptable drawdown.")

st.markdown("## C. Capital and loss scenarios")
cap = st.number_input("Illustrative capital (₹)", 10_000.0, 1e10, float(s.capital), 100_000.0, format="%.0f",
                      help="Rescales historical percentage results; the backtest itself uses the sidebar capital.")
sc = pd.DataFrame(bo.capital_scenarios(m, cap, wf.oos_metrics if wf is not None else None))
if len(sc):
    st.dataframe(sc.style.format({"Return": lambda x: ui.pct(x, 1, True) if x is not None and x == x else "—", "Amount": ui.inr,
                                  "Ending value": lambda x: ui.inr(x) if x is not None and x == x else "—"}, na_rep="—"),
                 hide_index=True, width="stretch")
st.caption("Historical outcomes rescaled to the chosen capital – scenarios, not forecasts or guarantees. Larger positions may face "
           "higher slippage than modelled.")

st.markdown("## D. Recommendation framework")
crit = pd.DataFrame(ev["criteria"])


def _fmt(row):
    v = row["Measured"]
    n = row["Criterion"]
    if v is None:
        return "n/a"
    if "trades" in n:
        return f"{int(v)}"
    if "Sharpe" in n and "/" not in n:
        return ui.num(v)
    if "/" in n:
        return ui.num(v)
    return ui.pct(v, 1)


crit["Measured"] = crit.apply(_fmt, axis=1)
crit["Result"] = crit["Result"].map({"Pass": "✅ Pass", "Fail": "❌ Fail", "n/a": "➖ n/a"})
st.dataframe(crit, hide_index=True, width="stretch")
st.caption("Rules: *Weak* if the net result or the out-of-sample Sharpe is ≤ 0; *Worth further investigation* only if every criterion "
           "passes; otherwise *Requires more validation*. Synthetic data is never classified. This is a research triage, not investment advice.")

st.markdown("## E. Executive summary")
wf_line = (f"Walk-forward over {len(wf.splits)} test windows: average out-of-sample Sharpe {ui.num(wf.oos_sharpe_avg)} vs in-sample "
           f"{ui.num(wf.is_sharpe_avg)}; out-of-sample total return {ui.pct(wf.oos_metrics.get('total_return'), 1, True)}."
           if wf is not None and not wf.splits.empty else "Walk-forward validation not applicable or not enough history.")
fails = [c["Criterion"] for c in ev["criteria"] if c["Result"] == "Fail"]
summary = f"""# Executive Summary – {strat.name} on {s.symbol}
Generated {datetime.now():%d %b %Y %H:%M} · Quantitative Trading & Derivatives Analytics Dashboard

**Data:** {ds.bundle.source}; {ds.report.coverage['actual_start']} to {ds.report.coverage['actual_end']} ({ds.report.coverage['sessions']:,} daily sessions).
**Assumptions:** starting capital {ui.inr(s.capital)}; orders filled at {'next open' if s.execution == 'next_open' else 'signal close (optimistic)'}; shorting {'allowed' if s.allow_short else 'not allowed'}; costs {'per published delivery schedule + ' + str(s.slippage_bps) + ' bps slippage' if s.cost_on else 'excluded'}; risk-free rate {s.rf:.2%}.
**Parameters:** {', '.join(f'{k}={v:g}' for k, v in r.params.items()) or 'none'}

## Classification: {ev['label']}
{ev['reason']}

## Main results
- Net return {ui.pct(m['total_return'], 1, True)} (CAGR {ui.pct(m['cagr'], 1, True)}) vs buy-and-hold {ui.pct(bh.metrics['total_return'], 1, True)}.
- Sharpe {ui.num(m['sharpe'])}, Sortino {ui.num(m['sortino'])}, annualised volatility {ui.pct(m['volatility'])}.
- {m['trades']} completed trades, win rate {ui.pct(m['win_rate'], 0)}, expectancy {ui.inr(m['expectancy'])} per trade.

## Major risks
- Maximum drawdown {ui.pct(m['max_drawdown'])} (≈ {ui.inr(-(m['max_drawdown'] or 0) * s.capital)} on the starting capital); longest period below a previous peak {m['max_dd_days']} days.
- Criteria not met: {', '.join(fails) if fails else 'none'}.

## Transaction-cost impact
Gross P&L {ui.inr(gn['gross_pnl'])}; charges {ui.inr(gn['charges'])} and slippage {ui.inr(gn['slippage'])}; costs equal {ui.pct(gn['cost_share_of_gross'], 0) if gn['cost_share_of_gross'] is not None else 'n/a'} of gross profit.

## Out-of-sample findings
{wf_line}

## Data limitations
{'SYNTHETIC DEMO DATA – results illustrate the method only and must not be used for decisions. ' if ds.bundle.is_synthetic else ''}Single instrument and period; survivorship bias in the large-cap universe; adjusted daily prices; capital-gains tax not modelled; past performance does not predict future results.

## Suggested next steps
1. Repeat on other instruments and an earlier, non-overlapping period.
2. Stress-test costs (2–3×) and execution assumptions.
3. If still promising, paper-trade before committing capital.
"""
with st.container(border=True):
    st.markdown(re.sub(r"^(#{1,2}) ", lambda mm: "####" + (" " if len(mm.group(1)) == 1 else "# "), summary, flags=re.M))
st.download_button("Download executive summary (Markdown)", summary, f"executive_summary_{s.symbol}_{s.strategy}.md", "text/markdown")
ui.footer(ds)
