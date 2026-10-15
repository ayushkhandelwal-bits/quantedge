import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src import candlestick_patterns as cp
from src import indicators, ui
from src.strategies import REGISTRY

ui.header("Trading Strategy Lab", "How each trading rule turns prices into buy and sell decisions.")
ds = ui.dataset()
ui.after_load()
ui.data_status_banner(ds)
s = st.session_state
df = ds.clean
strat = REGISTRY[s.strategy]
r = ui.run()
ui.log_run(r, ds)
res = r.result

tab1, tab2, tab3 = st.tabs(["Signals & trades", "Candlestick patterns", "Strategy catalogue"])

with tab1:
    c1, c2 = st.columns([2, 3])
    with c1:
        st.markdown(f"### {strat.name}")
        st.markdown(f"**Objective.** {strat.objective}\n\n**Rule.** {strat.rule}\n\n**Entry.** {strat.entry}  \n**Exit.** {strat.exit}\n\n"
                    f"**Struggles when.** {strat.struggles}")
        st.caption(f"Parameters: {', '.join(f'{k} = {v:g}' for k, v in r.params.items()) or 'none'}")
    with c2:
        m = r.metrics
        c = st.columns(3)
        ui.kpi(c[0], "Completed trades", m["trades"], f"avg holding {ui.num(m['avg_holding_days'], 0)} days")
        ui.kpi(c[1], "Win rate", ui.pct(m["win_rate"], 0), "share of trades profitable after costs")
        ui.kpi(c[2], "Net return", ui.pct(m["total_return"], 1, True), f"costs paid {ui.inr(m['total_costs'])}")
        st.write("")
        exe = {"next_open": "filled at the next session's open", "same_close": "filled at the signal day's close (optimistic)"}[s.execution]
        if strat.execution == "open_to_close":
            exe = "entered at the open of the gap day and closed at that day's close"
        st.info(f"Orders are {exe}. Short signals are {'traded' if s.allow_short else 'treated as “stay flat”'}"
                f"{' (this strategy uses short signals)' if strat.uses_short else ''}.")

    feat = indicators.feature_frame(df)
    ov = {}
    if s.strategy == "sma_crossover":
        ov = {f"SMA {int(r.params['short_window'])}": indicators.sma(df.Close, int(r.params["short_window"])),
              f"SMA {int(r.params['long_window'])}": indicators.sma(df.Close, int(r.params["long_window"]))}
    elif s.strategy == "bollinger_mr":
        bb = indicators.bollinger(df.Close, int(r.params["window"]), float(r.params["num_std"]))
        ov = {"Upper band": bb.BB_upper, "Middle band": bb.BB_mid, "Lower band": bb.BB_lower}
    elif s.strategy == "donchian":
        dc = indicators.donchian(df, int(r.params["window"]))
        ov = {"Channel high": dc.DC_upper, "Channel low": dc.DC_lower}
    else:
        ov = {"SMA 50": feat.SMA50}
    mk = ui.trade_markers(res.trades, df)
    st.plotly_chart(ui.candle_fig(df, f"{s.symbol} with {strat.name} signals", ov, mk), width="stretch")
    st.caption("▲ buy (long entry) · ▼ sell (short entry) · ● exit. Hover a marker for price, reason and net result.")

    if s.strategy in ("bollinger_mr", "rsi_divergence"):
        rsi_p = int(r.params.get("rsi_period", 14))
        rs = indicators.rsi(df.Close, rsi_p)
        fig = go.Figure(go.Scatter(x=rs.index, y=rs, name=f"RSI {rsi_p}", line=dict(color=ui.SERIES[6], width=1.4)))
        for lvl in (30, 70):
            fig.add_hline(y=lvl, line=dict(color=ui.AXIS, dash="dot"))
        st.plotly_chart(ui.style(fig, f"RSI ({rsi_p}) – momentum context", "RSI", height=230, legend=False), width="stretch")

    st.markdown("### Signal history")
    sig = res.signals.copy()
    changes = sig[sig["target"].diff().fillna(sig["target"]) != 0].copy()
    changes["New target position"] = changes["target"].map({1: "Long", 0: "Flat", -1: "Short"})
    changes["Close"] = df["Close"].reindex(changes.index)
    changes.index = changes.index.date
    st.dataframe(changes[["New target position", "reason", "Close"]].rename(columns={"reason": "Reason"}).iloc[::-1]
                 .style.format({"Close": "{:,.2f}"}), width="stretch", height=240)
    st.caption("Each row is a date on which the rule's desired position changed (decided at that day's close).")

    st.markdown("### Trade log")
    if len(res.trades):
        t = res.trades.copy()
        t["Entry date"], t["Exit date"] = t["Entry date"].dt.date, t["Exit date"].dt.date
        st.dataframe(t.style.format({"Entry price": "{:,.2f}", "Exit price": "{:,.2f}", "Quantity": "{:,.0f}", "Gross P&L": ui.inr,
                                     "Charges": ui.inr, "Slippage": ui.inr, "Net P&L": ui.inr, "Return %": "{:+.2f}%"}),
                     width="stretch", hide_index=True, height=320)
        st.download_button("Download trade log (CSV)", res.trades.to_csv(index=False), f"trades_{s.symbol}_{s.strategy}.csv", "text/csv")
    else:
        st.info("No completed trades with these settings.")

with tab2:
    st.info("For multi-stock statistics with confidence intervals, costs, regimes and an out-of-sample check, open **Pattern Validation**.", icon="🕯️")
    st.caption("Explicit OHLC rules – no machine learning or image recognition. Forward returns are measured from the signal day's "
               "close to the close 1, 5 and 10 sessions later, so the outcome window never overlaps the information used for detection.")
    c = st.columns(4)
    pp = cp.PatternParams(
        doji_body_max=c[0].slider("Doji: max body / range", 0.02, 0.3, 0.10, 0.01),
        shadow_ratio=c[1].slider("Long shadow ≥ × body", 1.5, 4.0, 2.0, 0.25),
        small_shadow_max=c[2].slider("Short shadow ≤ × range", 0.05, 0.4, 0.25, 0.05),
        require_trend=c[3].checkbox("Require prior trend", True, help="Hammer after a decline; Shooting Star after a rise"),
    )
    ev = cp.events(df, s.symbol, pp)
    summ = cp.summary(ev, df["Close"])
    st.markdown("#### Pattern definitions used")
    st.dataframe(pd.DataFrame([{"Pattern": n, "Bias": cp.PATTERNS[n]["bias"], "Rule": cp.describe_rule(n, pp)} for n in cp.PATTERNS]),
                 hide_index=True, width="stretch")
    h = st.radio("Evaluation horizon (sessions after the signal)", [1, 5, 10], index=1, horizontal=True)
    sh = summ[summ["Horizon (sessions)"] == h]
    st.dataframe(sh.drop(columns=["Horizon (sessions)"]).style.format(
        {"Hit rate": lambda x: ui.pct(x, 0), "Base-rate hit": lambda x: ui.pct(x, 0), "Avg return": lambda x: ui.pct(x, 2, True),
         "Avg return, all days": lambda x: ui.pct(x, 2, True), "Median return": lambda x: ui.pct(x, 2, True)}, na_rep="n/a"),
        hide_index=True, width="stretch")
    st.caption("Hit rate: share of occurrences where price moved in the pattern's direction (up for bullish, down for bearish). "
               "Base-rate hit: the same for *every* day – a pattern only adds information if it beats its base rate. Doji is neutral, so no hit rate.")
    fig = go.Figure()
    for i, (_, row) in enumerate(sh.iterrows()):
        fig.add_trace(go.Bar(x=[row["Pattern"]], y=[row["Avg return"]], name=row["Pattern"], marker_color=ui.SERIES[i % len(ui.SERIES)],
                             hovertemplate=f"{row['Pattern']}: %{{y:.2%}} avg over {h} sessions ({row['Occurrences']} cases)<extra></extra>"))
    fig.add_hline(y=sh["Avg return, all days"].iloc[0], line=dict(color=ui.INK2, dash="dash"),
                  annotation_text="all-days average", annotation_position="top left")
    fig.update_yaxes(tickformat=".1%")
    st.plotly_chart(ui.style(fig, f"Average {h}-session return after each pattern vs all days", "Average forward return", legend=False, height=330),
                    width="stretch")
    if len(ev):
        pick = st.selectbox("Inspect an occurrence", ev.index[::-1], format_func=lambda i: f"{ev.at[i, 'Date'].date()} – {ev.at[i, 'Pattern']}")
        d0 = ev.at[pick, "Date"]
        pos = df.index.get_loc(d0)
        win = df.iloc[max(0, pos - 15): pos + 11]
        fig = ui.candle_fig(win, f"{ev.at[pick, 'Pattern']} on {d0.date()} – 15 sessions before, 10 after", height=360)
        fig.add_vrect(x0=d0 - pd.Timedelta(hours=14), x1=d0 + pd.Timedelta(hours=14), fillcolor=ui.SERIES[0], opacity=0.12, line_width=0)
        st.plotly_chart(fig, width="stretch")
        rr = ev.loc[pick]
        st.caption(f"Rule: {cp.describe_rule(rr['Pattern'], pp)} · Subsequent returns: 1d {ui.pct(rr['fwd_1d'], 2, True)}, "
                   f"5d {ui.pct(rr['fwd_5d'], 2, True)}, 10d {ui.pct(rr['fwd_10d'], 2, True)}")
        with st.expander(f"All {len(ev)} detected occurrences"):
            st.dataframe(ev.assign(Date=ev.Date.dt.date).iloc[::-1], hide_index=True, width="stretch")
    ui.takeaway("Judge a pattern by whether it beats the all-days base rate across many occurrences – and remember a 5-session edge of a "
                "fraction of a percent can disappear once round-trip costs (~0.3% for delivery trades) are paid.")

with tab3:
    st.caption("Strategies considered for this application and their status.")
    rows = []
    for k, st_ in REGISTRY.items():
        rows.append({"Strategy": st_.name, "Type": st_.family, "Status": "✅ Available" if st_.available else "⛔ Not enabled",
                     "Data required": st_.data_required, "Why not / notes": st_.unavailable_reason or st_.struggles})
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch", height=470)
    sel = st.selectbox("Details", [k for k in REGISTRY if REGISTRY[k].available], format_func=lambda k: REGISTRY[k].name)
    x = REGISTRY[sel]
    st.markdown(f"**Objective:** {x.objective}  \n**Signal rule:** {x.rule}  \n**Entry:** {x.entry}  \n**Exit:** {x.exit}  \n"
                f"**Required data:** {x.data_required}  \n**Parameters:** {', '.join(p.label for p in x.params) or 'none'}  \n"
                f"**Known limitations:** {x.struggles}  \n**Suitable evaluation metrics:** {x.metrics}")
ui.footer(ds)
