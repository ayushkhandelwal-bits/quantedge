import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src import performance_metrics as pm
from src import ui
from src import walk_forward as wfm
from src.backtester import BacktestConfig
from src.strategies import REGISTRY

ui.header("Risk & Robustness", "Is the observed performance reliable enough to justify further work?")
ds = ui.dataset()
ui.after_load()
ui.data_status_banner(ds)
s = st.session_state
strat = REGISTRY[s.strategy]
r = ui.run()
cfg = ui.bt_config()

t1, t2, t3, t4 = st.tabs(["Walk-forward validation", "Parameter & cost sensitivity", "Market regimes", "Limits of the evidence"])

with t1:
    if not strat.params:
        st.info("Buy & Hold has no parameters to optimise; walk-forward validation applies to the trading strategies.")
    else:
        c1, c2 = st.columns(2)
        ty = c1.select_slider("Training window (years)", [1.0, 1.5, 2.0, 3.0], 2.0)
        tm = c2.select_slider("Test window (months)", [3, 6, 12], 6)
        wf = ui.walk_forward(s.strategy, ty, tm)
        if wf.splits.empty:
            st.warning("Not enough history for even one train/test window. Widen the date range or shorten the windows.")
        else:
            c = st.columns(4)
            ui.kpi(c[0], "Windows tested", len(wf.splits), f"{ty:g}y train → {tm}m test, rolling")
            ui.kpi(c[1], "Avg in-sample Sharpe", ui.num(wf.is_sharpe_avg), "on the data used to pick parameters")
            ui.kpi(c[2], "Avg out-of-sample Sharpe", ui.num(wf.oos_sharpe_avg), "on unseen data")
            ui.kpi(c[3], "OOS ÷ IS Sharpe", ui.num(wf.degradation),
                   "≥ 0.5 often read as acceptable" if wf.degradation is not None else "n/a – in-sample Sharpe ≤ 0")
            st.write("")
            fig = go.Figure()
            fig.add_trace(go.Bar(x=wf.splits["Window"], y=wf.splits["In-sample Sharpe"], name="In-sample (training)", marker_color=ui.SERIES[0]))
            fig.add_trace(go.Bar(x=wf.splits["Window"], y=wf.splits["Out-of-sample Sharpe"], name="Out-of-sample (test)", marker_color=ui.SERIES[1]))
            fig.update_layout(barmode="group", bargap=0.3, bargroupgap=0.08, hovermode="x unified")
            fig.update_xaxes(tickmode="array", tickvals=wf.splits["Window"], ticktext=wf.splits["Test"].str.split(" → ").str[0])
            st.plotly_chart(ui.style(fig, "Sharpe ratio by window: training vs following test period", "Sharpe ratio", "Test window start"),
                            width="stretch")
            st.dataframe(wf.splits.astype({c: float for c in ["In-sample Sharpe", "Out-of-sample Sharpe", "OOS return", "OOS max drawdown"]}).style.format({"In-sample Sharpe": ui.num, "Out-of-sample Sharpe": ui.num,
                                                 "OOS return": lambda x: ui.pct(x, 1, True), "OOS max drawdown": lambda x: ui.pct(x)}, na_rep="n/a"),
                         hide_index=True, width="stretch")
            full = r.result.curve.loc[wf.oos_equity.index[0]:]
            full = full / full.iloc[0] * wf.oos_equity.iloc[0]
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=wf.oos_equity.index, y=wf.oos_equity, name="Walk-forward (parameters re-chosen each window)",
                                     line=dict(color=ui.SERIES[1], width=2), hovertemplate="₹%{y:,.0f}"))
            fig.add_trace(go.Scatter(x=full.index, y=full, name="Fixed sidebar parameters (same period)",
                                     line=dict(color=ui.SERIES[0], width=2), hovertemplate="₹%{y:,.0f}"))
            st.plotly_chart(ui.style(fig, "Out-of-sample equity, stitched across test windows", "Portfolio value (₹)", height=340),
                            width="stretch")
            om = wf.oos_metrics
            ui.takeaway(f"Across {len(wf.splits)} unseen test windows the strategy returned {ui.pct(om.get('total_return'), 1, True)} in total "
                        f"(Sharpe {ui.num(om.get('sharpe'))}, worst drawdown {ui.pct(om.get('max_drawdown'))}). "
                        + ("Out-of-sample results held up relative to training." if (wf.degradation or 0) >= 0.5 else
                           "Performance on unseen data was materially weaker than in training (or training itself was unprofitable) – "
                           "a warning sign of over-fitting or regime dependence."))
            st.caption("Parameters are picked by highest net Sharpe on each training window from a small grid, then applied unchanged to the "
                       "next test window, which starts flat. Indicators may use earlier prices, as they would in real time.")

with t2:
    if strat.params:
        sv = ui.sensitivity()
        names = [p.name for p in strat.params]
        if len(names) == 2 and len(sv):
            piv = sv.pivot(index=names[0], columns=names[1], values="Sharpe")
            fig = go.Figure(go.Heatmap(z=piv.values, x=[f"{v:g}" for v in piv.columns], y=[f"{v:g}" for v in piv.index],
                                       colorscale=ui.DIVERGING, zmid=0, text=np.round(piv.values, 2), texttemplate="%{text}",
                                       hovertemplate=f"{strat.params[0].label} %{{y}}<br>{strat.params[1].label} %{{x}}<br>Sharpe %{{z:.2f}}<extra></extra>",
                                       colorbar=dict(title="Sharpe")))
            st.plotly_chart(ui.style(fig, "Sharpe ratio across parameter choices (full period)", strat.params[0].label, strat.params[1].label,
                                     height=380, legend=False), width="stretch")
        elif len(names) == 1 and len(sv):
            fig = go.Figure(go.Scatter(x=sv[names[0]], y=sv["Sharpe"], mode="lines+markers", line=dict(color=ui.SERIES[0], width=2),
                                       marker=dict(size=9), hovertemplate="%{x}: Sharpe %{y:.2f}<extra></extra>"))
            st.plotly_chart(ui.style(fig, "Sharpe ratio across parameter choices (full period)", "Sharpe", strat.params[0].label, 320, legend=False),
                            width="stretch")
        st.dataframe(sv.style.format({"Sharpe": ui.num, "Total return": lambda x: ui.pct(x, 1, True), "Max drawdown": lambda x: ui.pct(x)}, na_rep="n/a"),
                     hide_index=True, width="stretch")
        if len(sv) and sv["Sharpe"].notna().any():
            spread = sv["Sharpe"].max() - sv["Sharpe"].min()
            ui.takeaway(f"Sharpe ranges from {ui.num(sv['Sharpe'].min())} to {ui.num(sv['Sharpe'].max())} across nearby settings (spread {ui.num(spread)}). "
                        "A robust rule performs similarly across neighbouring parameters; a single bright cell surrounded by poor ones is likely luck.")
    cs = ui.cost_sensitivity(r.params)
    fig = go.Figure(go.Bar(x=cs["Label"], y=cs["Total return"], marker_color=[ui.SERIES[0]] + [ui.SERIES[1]] * (len(cs) - 1),
                           text=[ui.pct(v, 1, True) for v in cs["Total return"]], textposition="outside",
                           hovertemplate="%{x}: %{y:.1%}<extra></extra>"))
    fig.update_yaxes(tickformat=".0%")
    st.plotly_chart(ui.style(fig, "Total return under different cost levels", "Total return", height=320, legend=False), width="stretch")
    st.caption("Current costs = published delivery charges + the sidebar slippage. 2× and 3× stress-test wider spreads or a costlier broker.")
    nxt = ui.run(cfg=BacktestConfig(**{**cfg.__dict__, "execution": "next_open"}))
    same = ui.run(cfg=BacktestConfig(**{**cfg.__dict__, "execution": "same_close"}))
    c = st.columns(2)
    ui.kpi(c[0], "Return – fill at next open (realistic)", ui.pct(nxt.metrics["total_return"], 1, True), f"Sharpe {ui.num(nxt.metrics['sharpe'])}")
    ui.kpi(c[1], "Return – fill at signal close (optimistic)", ui.pct(same.metrics["total_return"], 1, True), f"Sharpe {ui.num(same.metrics['sharpe'])}")
    st.caption("Many simple backtesters fill orders at the close of the bar that produced the signal. The gap between these two numbers "
               "shows how much results depend on that assumption.")

with t3:
    reg = wfm.regimes(ds.clean["Close"])
    tbl = wfm.returns_by_regime(r.result.curve, reg, ds.clean["Close"])
    tbl = tbl[tbl["Regime"] != "Insufficient history"]
    if len(tbl):
        fig = go.Figure()
        fig.add_trace(go.Bar(x=tbl["Regime"], y=tbl["Strategy annualised"], name=strat.name, marker_color=ui.SERIES[0]))
        fig.add_trace(go.Bar(x=tbl["Regime"], y=tbl["Benchmark annualised"], name=f"Buy & hold {s.symbol}", marker_color=ui.SERIES[1]))
        fig.update_layout(barmode="group", bargap=0.3, bargroupgap=0.08)
        fig.update_yaxes(tickformat=".0%")
        st.plotly_chart(ui.style(fig, "Annualised average return by market regime", "Annualised return (mean daily × 252)"), width="stretch")
        st.dataframe(tbl.style.format({"Strategy avg daily return": lambda x: ui.pct(x, 3, True), "Benchmark avg daily return": lambda x: ui.pct(x, 3, True),
                                       "Strategy annualised": lambda x: ui.pct(x, 1, True), "Benchmark annualised": lambda x: ui.pct(x, 1, True)}),
                     hide_index=True, width="stretch")
    lab = reg.where(reg != "Insufficient history")
    cats = sorted(lab.dropna().unique())
    fig = go.Figure(go.Scatter(x=ds.clean.index, y=ds.clean["Close"], mode="lines", line=dict(color=ui.AXIS, width=1), name="Close", showlegend=False))
    for i, cname in enumerate(cats):
        m = lab == cname
        fig.add_trace(go.Scatter(x=ds.clean.index[m], y=ds.clean["Close"][m], mode="markers", marker=dict(size=4, color=ui.SERIES[i]), name=cname))
    st.plotly_chart(ui.style(fig, "Price coloured by regime", "Price", height=340), width="stretch")
    st.caption("Regime rules (transparent and causal): Uptrend if close is above its 200-session average, otherwise Downtrend; high vol if "
               "20-session volatility exceeds its own running median. The first ~200 sessions are unlabelled.")

with t4:
    st.markdown("""
- **History is one path.** A backtest shows what *did* happen under one sequence of prices, not the range of what *could* happen.
- **Small samples.** Strategies with few trades (under ~30) produce statistics that can swing widely on a few outcomes.
- **Parameter selection.** Testing many settings and reporting the best inflates results; walk-forward reduces but does not remove this.
- **Survivorship bias.** The universe is today's large, successful companies. Stocks that were delisted or fell out of the index are absent, which flatters long-only results.
- **Execution.** Fills at the next open with fixed slippage; real fills depend on liquidity, order size, auctions and circuit limits. Dividends are reflected through adjusted prices rather than cash payments.
- **Costs and tax.** Charges follow a published discount-broker schedule; capital-gains tax is not modelled.
- **Shorting.** Off by default; if enabled it is a simplification (no borrow fees, margin or recall risk).
- **Regime change.** Market structure, regulation and participants change; past relationships may not persist.
- **Synthetic data** (when shown) demonstrates the mechanics only and carries no information about real markets.
""")
    st.info("Walk-forward validation is a stronger test than a single backtest, but it does not guarantee future profitability.")
ui.footer(ds)
