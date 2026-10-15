import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src import business_outcomes as bo
from src import performance_metrics as pm
from src import ui
from src.strategies import REGISTRY

ui.header("Executive Overview", "What did the strategy achieve, how much risk did it take, and should we investigate it further?")
ds = ui.dataset()
ui.after_load()
ui.data_status_banner(ds)
s = st.session_state
r = ui.run()
ui.log_run(r, ds)
m = r.metrics
bh = ui.run("buy_hold")
strat = REGISTRY[s.strategy]

c = st.columns(4)
ui.kpi(c[0], "Instrument", ds.bundle.symbol, ui.badge(ds.bundle) + ("simulated prices" if ds.bundle.is_synthetic else "Yahoo Finance"))
ui.kpi(c[1], "Strategy", strat.name if len(strat.name) < 26 else strat.name[:24] + "…", strat.family)
ui.kpi(c[2], "Analysis period", f"{m['start']:%b %Y} – {m['end']:%b %Y}", f"{len(ds.clean):,} sessions")
ui.kpi(c[3], "Completed trades", f"{m['trades']}", f"time in market {ui.pct(m['exposure'], 0)}")
st.write("")
c = st.columns(4)
diff = None if m["total_return"] is None or bh.metrics["total_return"] is None else m["total_return"] - bh.metrics["total_return"]
ui.kpi(c[0], "Total return (net)", ui.pct(m["total_return"], 1, True), f"vs buy & hold {ui.pct(bh.metrics['total_return'], 1, True)}",
       pm.METRIC_HELP["total_return"])
ui.kpi(c[1], "CAGR", ui.pct(m["cagr"], 1, True), f"buy & hold {ui.pct(bh.metrics['cagr'], 1, True)}", pm.METRIC_HELP["cagr"])
ui.kpi(c[2], "Sharpe ratio", ui.num(m["sharpe"]), f"risk-free {s.rf:.2%} · buy & hold {ui.num(bh.metrics['sharpe'])}", pm.METRIC_HELP["sharpe"])
ui.kpi(c[3], "Maximum drawdown", ui.pct(-m["max_drawdown"] if m["max_drawdown"] is not None else None, 1),
       f"buy & hold {ui.pct(-bh.metrics['max_drawdown'] if bh.metrics['max_drawdown'] is not None else None, 1)}", pm.METRIC_HELP["max_drawdown"])

ui.takeaway(bo.interpretation(m, bh.metrics["total_return"], strat.name))

left, right = st.columns([3, 2])
with left:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=r.result.curve.index, y=r.result.curve, name=strat.name, line=dict(color=ui.STRAT_COLOR[s.strategy], width=2)))
    fig.add_trace(go.Scatter(x=bh.result.curve.index, y=bh.result.curve, name=f"Buy & hold {ds.bundle.symbol}",
                             line=dict(color=ui.STRAT_COLOR["buy_hold"], width=2)))
    bench, blabel = ui.benchmark_curve(s.capital, r.result.curve.index)
    if bench is not None and s.benchmark != s.symbol:
        fig.add_trace(go.Scatter(x=bench.index, y=bench, name=f"{blabel} (index)", line=dict(color=ui.MUTED, width=1.5, dash="dot")))
    fig.update_traces(hovertemplate="₹%{y:,.0f}")
    st.plotly_chart(ui.style(fig, "Growth of starting capital (after costs)", "Portfolio value (₹)"), width="stretch")
with right:
    runs = ui.run_all()
    rows = []
    for k, rr in runs.items():
        mm = rr.metrics
        if mm["volatility"] is None or mm["cagr"] is None:
            continue
        rows.append({"key": k, "Strategy": REGISTRY[k].name, "Volatility": mm["volatility"], "CAGR": mm["cagr"], "Sharpe": mm["sharpe"]})
    rv = pd.DataFrame(rows)
    fig = go.Figure()
    for _, row in rv.iterrows():
        sel = row["key"] == s.strategy
        fig.add_trace(go.Scatter(x=[row["Volatility"]], y=[row["CAGR"]], mode="markers+text", name=row["Strategy"],
                                 text=[row["Strategy"].split(" (")[0] if sel or row["key"] == "buy_hold" else ""],
                                 textposition="top center", cliponaxis=False,
                                 marker=dict(size=14 if sel else 10, color=ui.STRAT_COLOR[row["key"]],
                                             line=dict(color="white" if not sel else ui.INK, width=2)),
                                 hovertemplate=f"<b>{row['Strategy']}</b><br>CAGR %{{y:.1%}}<br>Volatility %{{x:.1%}}<br>Sharpe {ui.num(row['Sharpe'])}<extra></extra>"))
    fig.update_xaxes(tickformat=".0%")
    fig.update_yaxes(tickformat=".0%")
    fig = ui.style(fig, "Return vs risk – all strategies", "CAGR", "Annualised volatility", legend=False)
    fig.update_layout(hovermode="closest")
    st.plotly_chart(fig, width="stretch")
    st.caption("Up and to the left is better: more return for less volatility. Same instrument, period, capital and costs for all.")

st.markdown("## Recent trading activity")
tr = r.result.trades
if len(tr):
    recent = tr.tail(6).iloc[::-1][["Direction", "Entry date", "Exit date", "Entry reason", "Exit reason", "Net P&L", "Return %"]].copy()
    recent["Entry date"] = recent["Entry date"].dt.date
    recent["Exit date"] = recent["Exit date"].dt.date
    st.dataframe(recent.style.format({"Net P&L": ui.inr, "Return %": "{:+.2f}%"}), width="stretch", hide_index=True)
    last_sig = r.result.signals["target"].iloc[-1]
    st.caption(f"Latest signal (close of {ds.clean.index[-1].date()}): **{ {1: 'Long', 0: 'Flat', -1: 'Short'}[int(last_sig)] }**. "
               "Signals are historical outputs of the rule, not recommendations.")
else:
    st.info("The strategy generated no completed trades over this period with the current settings.")

st.markdown("## Should we investigate further?")
wf = ui.walk_forward()
ev = bo.evaluate(m, bh.metrics["total_return"], wf, bo.Thresholds(), ds.bundle.is_synthetic)
tone = {"positive": "#e7f5e7", "warning": "#fff3d6", "negative": "#fbe9e9", "neutral": "#f0efec"}[ev["tone"]]
icon = {"positive": "✅", "warning": "⚠️", "negative": "⛔", "neutral": "ℹ️"}[ev["tone"]]
st.markdown(f"<div class='ql-verdict' style='background:{tone}'><div class='t'>{icon} {ev['label']}</div>{ev['reason']}</div>",
            unsafe_allow_html=True)
st.caption("Criteria, thresholds and the out-of-sample evidence are on the **Business Outcomes** and **Risk & Robustness** pages.")
ui.footer(ds)
