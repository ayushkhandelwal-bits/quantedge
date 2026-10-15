import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from src import options_pricing as op
from src import ui

ui.header("Derivatives Analytics", "Theoretical option values, sensitivities (Greeks) and strategy payoffs.")
ds = ui.dataset()
ui.after_load()
s = st.session_state
st.info("**All option prices on this page are theoretical model outputs** (Black–Scholes–Merton, European exercise), not exchange-traded "
        "prices. Historical options backtesting is **disabled**: it requires genuine historical contract prices, which are not freely "
        "available in a reliable form. Nothing here manufactures historical option returns.", icon="ℹ️")

last = float(ds.clean["Close"].iloc[-1])
hv = float(ds.clean["Close"].pct_change().tail(60).std() * np.sqrt(252))
src_note = f"last close of {s.symbol} on {ds.clean.index[-1].date()}" + (" – SYNTHETIC" if ds.bundle.is_synthetic else "")

with st.container(border=True):
    st.markdown("**Inputs** (hypothetical – edit freely)")
    c = st.columns(6)
    S = c[0].number_input("Underlying price (₹)", 1.0, 1e7, round(last, 2), help=f"Default: {src_note}")
    K = c[1].number_input("Strike (₹)", 1.0, 1e7, float(round(last / 10) * 10))
    days = c[2].number_input("Days to expiry", 0, 1095, 30, help="Calendar days; T = days / 365")
    vol = c[3].number_input("Volatility (% p.a.)", 1.0, 200.0, round(hv * 100, 1), 0.5,
                            help="Default: annualised volatility of the last 60 daily returns (historical, not implied)") / 100
    r = c[4].number_input("Risk-free rate (% p.a.)", 0.0, 20.0, round(s.rf * 100, 2), 0.25, help="Continuously compounded assumption") / 100
    q = c[5].number_input("Dividend yield (% p.a.)", 0.0, 15.0, 0.0, 0.1) / 100
T = days / 365

t1, t2, t3, t4 = st.tabs(["Pricing & Greeks", "Implied volatility", "Strategy payoff builder", "Scenario analysis"])

with t1:
    call, put = op.bs_price(S, K, T, r, vol, "call", q), op.bs_price(S, K, T, r, vol, "put", q)
    gc, gp = op.greeks(S, K, T, r, vol, "call", q), op.greeks(S, K, T, r, vol, "put", q)
    c = st.columns(4)
    ui.kpi(c[0], "Call value (theoretical)", f"₹{call:,.2f}", f"intrinsic ₹{max(S - K, 0):,.2f} · time value ₹{call - max(S - K, 0):,.2f}")
    ui.kpi(c[1], "Put value (theoretical)", f"₹{put:,.2f}", f"intrinsic ₹{max(K - S, 0):,.2f} · time value ₹{put - max(K - S, 0):,.2f}")
    ui.kpi(c[2], "Moneyness (S/K)", f"{S / K:.3f}", "ATM ≈ 1.00")
    parity = call - put - (S * np.exp(-q * T) - K * np.exp(-r * T))
    ui.kpi(c[3], "Put–call parity check", f"{0.0 if abs(parity) < 5e-7 else parity:+.6f}", "should be ≈ 0")
    g = pd.DataFrame({"Call": gc, "Put": gp}).T[["delta", "gamma", "theta", "vega", "rho"]]
    g.columns = ["Delta (₹ per ₹1 in S)", "Gamma (Δ per ₹1)", "Theta (₹ per day)", "Vega (₹ per 1 vol pt)", "Rho (₹ per 1% rate)"]
    st.dataframe(g.style.format("{:,.4f}"), width="stretch")
    st.caption("Per one unit of the underlying. Multiply by the contract lot size for a real position. Assumptions: European exercise, "
               "constant volatility and rates, lognormal prices, no transaction costs.")

    grid = np.linspace(S * 0.6, S * 1.4, 161)
    fig = make_subplots(rows=1, cols=3, subplot_titles=("Value vs underlying price", "Value vs volatility", "Value vs days to expiry"))
    fig.add_trace(go.Scatter(x=grid, y=[op.bs_price(x, K, T, r, vol, "call", q) for x in grid], name="Call", line=dict(color=ui.SERIES[0], width=2)), 1, 1)
    fig.add_trace(go.Scatter(x=grid, y=[op.bs_price(x, K, T, r, vol, "put", q) for x in grid], name="Put", line=dict(color=ui.SERIES[1], width=2)), 1, 1)
    fig.add_trace(go.Scatter(x=grid, y=np.maximum(grid - K, 0), name="Call payoff at expiry", line=dict(color=ui.SERIES[0], width=1, dash="dot")), 1, 1)
    fig.add_trace(go.Scatter(x=grid, y=np.maximum(K - grid, 0), name="Put payoff at expiry", line=dict(color=ui.SERIES[1], width=1, dash="dot")), 1, 1)
    vg = np.linspace(0.05, max(0.8, vol * 2), 80)
    fig.add_trace(go.Scatter(x=vg * 100, y=[op.bs_price(S, K, T, r, v, "call", q) for v in vg], line=dict(color=ui.SERIES[0], width=2), showlegend=False), 1, 2)
    fig.add_trace(go.Scatter(x=vg * 100, y=[op.bs_price(S, K, T, r, v, "put", q) for v in vg], line=dict(color=ui.SERIES[1], width=2), showlegend=False), 1, 2)
    dg = np.arange(max(days, 1), -1, -1)
    fig.add_trace(go.Scatter(x=dg, y=[op.bs_price(S, K, d / 365, r, vol, "call", q) for d in dg], line=dict(color=ui.SERIES[0], width=2), showlegend=False), 1, 3)
    fig.add_trace(go.Scatter(x=dg, y=[op.bs_price(S, K, d / 365, r, vol, "put", q) for d in dg], line=dict(color=ui.SERIES[1], width=2), showlegend=False), 1, 3)
    fig.update_xaxes(title_text="Underlying (₹)", row=1, col=1)
    fig.update_xaxes(title_text="Volatility (%)", row=1, col=2)
    fig.update_xaxes(title_text="Days to expiry", autorange="reversed", row=1, col=3)
    st.plotly_chart(ui.style(fig, "How the theoretical value responds to each input", "Option value (₹)", height=400).update_layout(margin_t=84), width="stretch")

    fig = make_subplots(rows=1, cols=4, subplot_titles=("Delta", "Gamma", "Theta (₹/day)", "Vega (₹/vol pt)"))
    for j, gname in enumerate(["delta", "gamma", "theta", "vega"]):
        for kind, col in (("call", ui.SERIES[0]), ("put", ui.SERIES[1])):
            fig.add_trace(go.Scatter(x=grid, y=[op.greeks(x, K, T, r, vol, kind, q)[gname] for x in grid], name=kind.title(),
                                     line=dict(color=col, width=2), showlegend=(j == 0)), 1, j + 1)
        fig.add_vline(x=K, line=dict(color=ui.AXIS, dash="dot"), row=1, col=j + 1)
    st.plotly_chart(ui.style(fig, "Greeks across underlying prices (dotted line = strike)", height=340).update_layout(margin_t=84), width="stretch")
    ui.takeaway("Gamma and theta peak near the strike as expiry approaches: at-the-money options change value fastest and decay fastest. "
                "Vega shows that buying an option is also a bet that volatility will rise.")

with t2:
    st.caption("Enter an observed option price to back out the volatility the market is implying (inputs above for S, K, expiry, r, q).")
    c = st.columns(3)
    kind = c[0].radio("Option type", ["call", "put"], horizontal=True)
    mkt = c[1].number_input("Observed option price (₹)", 0.0, 1e7, round(op.bs_price(S, K, T, r, vol, kind, q) * 1.1, 2))
    iv = op.implied_vol(mkt, S, K, T, r, kind, q)
    with c[2]:
        if iv is None:
            st.error("No volatility reproduces this price – it is below intrinsic value or above the theoretical maximum, or expiry is 0 days.")
        else:
            ui.kpi(st.container(), "Implied volatility", f"{iv:.2%}", f"vs historical {hv:.1%} (60-day)")
    if iv is not None:
        st.caption("Implied volatility above historical volatility means the price embeds an expectation of larger future moves (or a risk premium).")

with t3:
    c = st.columns(4)
    preset = c[0].selectbox("Strategy", op.PRESETS)
    k1 = c[1].number_input("Strike 1 (₹)", 1.0, 1e7, float(K), key="k1")
    k2 = c[2].number_input("Strike 2 (₹, if used)", 1.0, 1e7, float(round(K * 1.05, 2)), key="k2")
    lot = c[3].number_input("Quantity (units)", 1, 100000, 1, help="Use the exchange lot size for a contract-level view")
    legs = op.build_strategy(preset, S, T, r, vol, q, k1, k2, lot)
    st.caption("Premiums below are computed with the model and can be overwritten with observed prices.")
    leg_df = pd.DataFrame([{"Instrument": l.kind, "Position": "Long" if l.side > 0 else "Short", "Strike": l.strike if l.kind != "stock" else None,
                            "Premium / price": round(l.premium, 2), "Quantity": l.qty} for l in legs])
    ed = st.data_editor(leg_df, hide_index=True, width="stretch", num_rows="dynamic", key=f"legs_{preset}",
                        column_config={"Instrument": st.column_config.SelectboxColumn(options=["call", "put", "stock"]),
                                       "Position": st.column_config.SelectboxColumn(options=["Long", "Short"])})
    legs = []
    for _, row in ed.dropna(subset=["Instrument", "Position"]).iterrows():
        legs.append(op.Leg(row["Instrument"], 1 if row["Position"] == "Long" else -1, float(row["Strike"] or 0) if row["Instrument"] != "stock" else 0.0,
                           float(row["Premium / price"] or 0), float(row["Quantity"] or 1)))
    if legs:
        a = op.analyse_payoff(legs, S)
        c = st.columns(4)
        npm = a["net_premium"]
        ui.kpi(c[0], "Initial premium", ui.inr(abs(npm), 2), "net credit received" if npm > 0 else "net debit paid")
        ui.kpi(c[1], "Maximum profit", "Unlimited" if a["max_profit"] is None else ui.inr(a["max_profit"], 2), "at expiry")
        ui.kpi(c[2], "Maximum loss", "Unlimited" if a["max_loss"] is None else ui.inr(a["max_loss"], 2), "at expiry")
        ui.kpi(c[3], "Break-even(s)", ", ".join(f"₹{b:,.2f}" for b in a["breakevens"]) or "none", "underlying price at expiry")
        lo, hi = S * 0.6, S * 1.4
        xs = np.linspace(lo, hi, 241)
        prof = sum(l.profit(xs) for l in legs)
        cost0 = sum(l.side * l.qty * l.premium for l in legs)
        hold = st.slider("Show theoretical P&L today and after N days", 0, max(days, 1), 0)
        Tn = max(T - hold / 365, 0)
        now = np.array([sum(l.value(x, Tn, r, vol, q) for l in legs) for x in xs]) - cost0
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=xs, y=np.where(prof >= 0, prof, np.nan), name="Profit at expiry", line=dict(color=ui.GOOD_TEXT, width=2.4),
                                 hovertemplate="S=₹%{x:,.0f}: ₹%{y:,.2f}<extra></extra>"))
        fig.add_trace(go.Scatter(x=xs, y=np.where(prof < 0, prof, np.nan), name="Loss at expiry", line=dict(color=ui.CRIT, width=2.4),
                                 hovertemplate="S=₹%{x:,.0f}: ₹%{y:,.2f}<extra></extra>"))
        fig.add_trace(go.Scatter(x=xs, y=now, name=f"Theoretical P&L with {days - hold} days left", line=dict(color=ui.SERIES[0], width=1.8, dash="dash"),
                                 hovertemplate="S=₹%{x:,.0f}: ₹%{y:,.2f}<extra></extra>"))
        fig.add_hline(y=0, line=dict(color=ui.AXIS))
        fig.add_vline(x=S, line=dict(color=ui.MUTED, dash="dot"), annotation_text="current price")
        for b in a["breakevens"]:
            if lo < b < hi:
                fig.add_vline(x=b, line=dict(color=ui.SERIES[3], dash="dash", width=1), annotation_text=f"BE {b:,.0f}", annotation_position="bottom right")
        fig.update_layout(hovermode="x unified")
        st.plotly_chart(ui.style(fig, f"{preset}: profit / loss vs underlying price", "Profit / loss (₹)", "Underlying price (₹)", 420),
                        width="stretch")
        st.caption("Solid line: payoff at expiry minus premiums (green = profit, red = loss). Dashed line: model value before expiry, "
                   "assuming volatility and rates are unchanged. Theoretical payoff is not realised profit: costs, early exercise, "
                   "liquidity and margin are ignored.")

with t4:
    st.caption("Theoretical value change of the strategy from the builder tab for combined moves in the underlying and volatility.")
    if legs:
        c = st.columns(2)
        h_days = c[0].slider("Days from now", 0, max(days, 1), min(7, days))
        moves = np.array([-0.15, -0.10, -0.05, -0.02, 0, 0.02, 0.05, 0.10, 0.15])
        vmoves = np.array([-0.10, -0.05, 0, 0.05, 0.10])
        Th = max(T - h_days / 365, 0)
        base_val = sum(l.value(S, T, r, vol, q) for l in legs)
        z = [[sum(l.value(S * (1 + m), Th, r, max(vol + dv, 0.01), q) for l in legs) - base_val for m in moves] for dv in vmoves]
        z = np.array(z)
        lim = np.abs(z).max() or 1
        fig = go.Figure(go.Heatmap(z=z, x=[f"{m:+.0%}" for m in moves], y=[f"{dv * 100:+.0f} pts" for dv in vmoves], colorscale=ui.DIVERGING,
                                   zmid=0, zmin=-lim, zmax=lim, text=[[f"{v:,.0f}" for v in row] for row in z], texttemplate="%{text}",
                                   hovertemplate="Underlying %{x}, vol %{y}: ₹%{z:,.2f}<extra></extra>", colorbar=dict(title="₹")))
        st.plotly_chart(ui.style(fig, f"Change in position value after {h_days} days (₹)", "Volatility change", "Underlying price change", 380, legend=False),
                        width="stretch")
        worst = z.min()
        ui.takeaway(f"Within these scenarios the worst theoretical change is {ui.inr(worst, 0)} and the best {ui.inr(z.max(), 0)} for the "
                    f"position above. Scenarios are illustrative stress tests, not probabilities.")
ui.footer(ds)
