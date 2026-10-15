import calendar

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src import performance_metrics as pm
from src import storage, ui
from src.strategies import REGISTRY

ui.header("Backtesting & Performance Analytics", "All strategies on the same instrument, period, capital and cost assumptions.")
ds = ui.dataset()
ui.after_load()
ui.data_status_banner(ds)
s = st.session_state
runs = ui.run_all()
for rr in runs.values():
    ui.log_run(rr, ds)
sel = runs[s.strategy]

rows = []
for k, r in runs.items():
    m = r.metrics
    rows.append({"key": k, "Strategy": REGISTRY[k].name, "Total return": m["total_return"], "CAGR": m["cagr"], "Sharpe": m["sharpe"],
                 "Sortino": m["sortino"], "Max drawdown": m["max_drawdown"], "Win rate": m["win_rate"], "Profit factor": m["profit_factor"],
                 "Trades": m["trades"], "Avg win": m["avg_win"], "Avg loss": m["avg_loss"], "Expectancy": m["expectancy"],
                 "Costs": m["total_costs"], "Gross P&L": m["gross_pnl"]})
tbl = pd.DataFrame(rows).fillna(value=np.nan)
tbl = tbl.astype({c: float for c in tbl.columns if c not in ("key", "Strategy", "Trades")})

st.markdown("## Strategy comparison")
st.caption("Selected strategy uses the sidebar parameters; others use their default parameters. n/a = undefined (e.g. no losing trades, "
           "fewer than 20 sessions). Hover column headers for definitions.")
disp = tbl.drop(columns=["key", "Gross P&L"]).set_index("Strategy")
st.dataframe(
    disp.style.format({"Total return": lambda x: ui.pct(x, 1, True), "CAGR": lambda x: ui.pct(x, 1, True), "Sharpe": ui.num, "Sortino": ui.num,
                       "Max drawdown": lambda x: ui.pct(x, 1), "Win rate": lambda x: ui.pct(x, 0), "Profit factor": ui.num,
                       "Avg win": ui.inr, "Avg loss": ui.inr, "Expectancy": ui.inr, "Costs": ui.inr}, na_rep="n/a"),
    width="stretch",
    column_config={c: st.column_config.Column(help=pm.METRIC_HELP.get(h)) for c, h in
                   [("Total return", "total_return"), ("CAGR", "cagr"), ("Sharpe", "sharpe"), ("Sortino", "sortino"), ("Max drawdown", "max_drawdown"),
                    ("Win rate", "win_rate"), ("Profit factor", "profit_factor"), ("Expectancy", "expectancy"), ("Costs", "total_costs")]})
best_ret = tbl.loc[tbl["Total return"].idxmax()]
valid_sh = tbl.dropna(subset=["Sharpe"])
best_sh = valid_sh.loc[valid_sh["Sharpe"].idxmax()] if len(valid_sh) else None
txt = f"Highest total return: **{best_ret['Strategy']}** ({ui.pct(best_ret['Total return'], 1, True)}, max drawdown {ui.pct(best_ret['Max drawdown'])})."
if best_sh is not None and best_sh["Strategy"] != best_ret["Strategy"]:
    txt += f" Best return per unit of risk: **{best_sh['Strategy']}** (Sharpe {ui.num(best_sh['Sharpe'])}, drawdown {ui.pct(best_sh['Max drawdown'])})."
ui.takeaway(txt + " A higher total return is not automatically better: it may come from taking far more risk (deeper drawdowns), "
            "from a handful of lucky trades, or from a period that happened to suit the rule. Compare Sharpe, drawdown and trade count together.")

t1, t2, t3, t4 = st.tabs(["Equity & drawdown", "Monthly returns & distribution", "Cost impact", "Run history"])
with t1:
    show = st.multiselect("Strategies to plot", list(runs), default=[s.strategy, "buy_hold"], format_func=lambda k: REGISTRY[k].name)
    fig = go.Figure()
    for k in show:
        fig.add_trace(go.Scatter(x=runs[k].result.curve.index, y=runs[k].result.curve, name=REGISTRY[k].name,
                                 line=dict(color=ui.STRAT_COLOR[k], width=2), hovertemplate="₹%{y:,.0f}"))
    bench, blabel = ui.benchmark_curve(s.capital, sel.result.curve.index)
    if bench is not None and s.benchmark != s.symbol:
        fig.add_trace(go.Scatter(x=bench.index, y=bench, name=f"{blabel} index", line=dict(color=ui.MUTED, width=1.5, dash="dot"),
                                 hovertemplate="₹%{y:,.0f}"))
    st.plotly_chart(ui.style(fig, "Equity curves (net of costs)", "Portfolio value (₹)"), width="stretch")
    fig = go.Figure()
    for k in show:
        dd = pm.drawdown_series(runs[k].result.curve)
        fig.add_trace(go.Scatter(x=dd.index, y=dd, name=REGISTRY[k].name, line=dict(color=ui.STRAT_COLOR[k], width=1.6),
                                 hovertemplate="%{y:.1%}"))
    fig.update_yaxes(tickformat=".0%")
    st.plotly_chart(ui.style(fig, "Drawdown: decline from previous peak", "Drawdown", height=320), width="stretch")
    c = st.columns(3)
    m = sel.metrics
    ui.kpi(c[0], "Longest time below a peak", f"{m['max_dd_days']} days" if m["max_dd_days"] is not None else "n/a", REGISTRY[s.strategy].name)
    ui.kpi(c[1], "Calmar ratio", ui.num(m["calmar"]), "CAGR ÷ max drawdown")
    ui.kpi(c[2], "Annualised volatility", ui.pct(m["volatility"]), "of daily portfolio returns")

with t2:
    k = st.selectbox("Strategy", list(runs), index=list(runs).index(s.strategy), format_func=lambda k: REGISTRY[k].name, key="mr_sel")
    mr = pm.monthly_returns(runs[k].result.curve)
    mr.columns = [calendar.month_abbr[c] for c in mr.columns]
    z = mr.values
    lim = np.nanmax(np.abs(z)) if np.isfinite(z).any() else 0.1
    fig = go.Figure(go.Heatmap(z=z, x=mr.columns, y=mr.index.astype(str), colorscale=ui.DIVERGING, zmid=0, zmin=-lim, zmax=lim,
                               text=[[ui.pct(v, 1, True) if np.isfinite(v) else "" for v in row] for row in z], texttemplate="%{text}",
                               hovertemplate="%{x} %{y}: %{z:.2%}<extra></extra>", colorbar=dict(tickformat=".0%")))
    fig.update_yaxes(autorange="reversed")
    st.plotly_chart(ui.style(fig, f"Monthly returns – {REGISTRY[k].name}", "Year", height=80 + 42 * len(mr), legend=False), width="stretch")
    dr = pm.daily_returns(runs[k].result.curve)
    dr = dr[dr != 0]
    fig = go.Figure(go.Histogram(x=dr, nbinsx=70, marker_color=ui.STRAT_COLOR[k], hovertemplate="%{x:.2%}: %{y} days<extra></extra>"))
    fig.update_xaxes(tickformat=".1%")
    st.plotly_chart(ui.style(fig, "Distribution of daily returns (days with a position)", "Sessions", "Daily return", 300, legend=False),
                    width="stretch")
    tr = runs[k].result.trades
    if len(tr):
        fig = go.Figure(go.Histogram(x=tr["Return %"] / 100, nbinsx=40, marker_color=ui.STRAT_COLOR[k], hovertemplate="%{x:.1%}: %{y} trades<extra></extra>"))
        fig.update_xaxes(tickformat=".0%")
        st.plotly_chart(ui.style(fig, "Distribution of trade returns (net)", "Trades", "Return per trade", 280, legend=False), width="stretch")

with t3:
    fig = go.Figure()
    fig.add_trace(go.Bar(x=tbl["Strategy"], y=tbl["Gross P&L"], name="Gross P&L (before costs)", marker_color=ui.SERIES[0],
                         hovertemplate="%{x}<br>Gross ₹%{y:,.0f}<extra></extra>"))
    fig.add_trace(go.Bar(x=tbl["Strategy"], y=tbl["Gross P&L"] - tbl["Costs"], name="Net P&L (after costs)", marker_color=ui.SERIES[1],
                         hovertemplate="%{x}<br>Net ₹%{y:,.0f}<extra></extra>"))
    fig.update_layout(barmode="group", bargap=0.3, bargroupgap=0.08, hovermode="closest")
    st.plotly_chart(ui.style(fig, "Gross vs net trading P&L by strategy", "₹"), width="stretch")
    cb = sel.result.trades[["Charges", "Slippage"]].sum() if len(sel.result.trades) else pd.Series({"Charges": 0, "Slippage": 0})
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=sel.result.equity.index, y=sel.result.equity["gross_equity"], name="Before costs (approx.)",
                             line=dict(color=ui.SERIES[0], width=2), hovertemplate="₹%{y:,.0f}"))
    fig.add_trace(go.Scatter(x=sel.result.equity.index, y=sel.result.equity["equity"], name="After costs",
                             line=dict(color=ui.SERIES[1], width=2), hovertemplate="₹%{y:,.0f}"))
    st.plotly_chart(ui.style(fig, f"Cost drag over time – {REGISTRY[s.strategy].name}", "Portfolio value (₹)", height=320), width="stretch")
    c = st.columns(3)
    ui.kpi(c[0], "Statutory & broker charges", ui.inr(cb["Charges"]), "STT, exchange, SEBI, stamp, GST, DP")
    ui.kpi(c[1], "Slippage", ui.inr(cb["Slippage"]), f"{s.slippage_bps:g} bps per side" if s.cost_on else "costs disabled")
    ui.kpi(c[2], "Cost per trade", ui.inr((cb.sum() / sel.metrics["trades"]) if sel.metrics["trades"] else None), "average round trip")
    st.caption("“Before costs” adds back cumulative costs to the net curve; it ignores the small compounding effect of having paid them.")

with t4:
    st.caption("Every distinct run is stored in SQLite (data/database/results.db) with its inputs and data status, for reproducibility.")
    try:
        h = storage.load_runs(100)
        st.dataframe(h.style.format({"total_return": lambda x: ui.pct(x, 1, True), "sharpe": ui.num, "max_drawdown": lambda x: ui.pct(x)}, na_rep="n/a"),
                     hide_index=True, width="stretch")
    except Exception as e:  # noqa: BLE001
        st.warning(f"Run history unavailable: {e}")
ui.footer(ds)
