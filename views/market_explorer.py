import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

import config
from src import data_sources as dsrc
from src import glossary, indicators, ui

ui.header("Market Explorer & Data Understanding", "Know the data before trusting any result built on it.")
ds = ui.dataset()
ui.after_load()
ui.data_status_banner(ds)
s = st.session_state
b, clean, rep = ds.bundle, ds.clean, ds.report
info = config.INSTRUMENTS[s.symbol]
cov = rep.coverage

tabs = st.tabs(["Dataset overview", "Price & indicators", "Data dictionary", "Data quality", "Correlation", "Financial glossary"])

# ------------------------------------------------------------------ overview
with tabs[0]:
    c = st.columns(4)
    ui.kpi(c[0], "Instrument", info["name"], f"{s.symbol} · {info['market']}")
    ui.kpi(c[1], "Observations", f"{len(clean):,}", f"{len(b.df):,} raw rows · {b.df.shape[1] + 1} columns")
    ui.kpi(c[2], "Coverage", f"{cov['years']} years", f"{cov['actual_start']} → {cov['actual_end']}")
    ui.kpi(c[3], "Data status", b.status, b.source)
    st.write("")
    summary = pd.DataFrame([
        ("Data source", b.source),
        ("Instrument description", info["desc"] + (" (index level – not directly tradable; treated as a proxy for an index fund)" if not info["tradable"] else "")),
        ("Currency", info["ccy"]),
        ("Frequency", "Daily (one row per trading session)"),
        ("Requested period", f"{s.start} → {s.end}"),
        ("Actual first / last observation", f"{cov['actual_start']} / {cov['actual_end']}"),
        ("Shortfall vs request", f"{cov['short_of_request_days']} days at start, {cov['short_at_end_days']} days at end (weekends/holidays explain a few days)"),
        ("Trading sessions (after cleaning)", f"{cov['sessions']:,}"),
        ("Missing values (raw)", f"{int(b.df.isna().sum().sum())}"),
        ("Duplicate timestamps (raw)", f"{int(b.df.index.duplicated().sum())}"),
        ("Price adjustment", "Adjusted for splits and dividends" if not b.is_synthetic else "n/a – simulated"),
        ("Last successful download", b.fetched_at or "never (no live download in this dataset)"),
    ], columns=["Item", "Value"])
    st.dataframe(summary, hide_index=True, width="stretch", height=36 * (len(summary) + 1) + 4)
    if cov["years"] < 4.5 and not b.is_synthetic:
        st.info(f"The source returned about {cov['years']} years, less than the ~5 years targeted. Results cover only this period.")
    st.markdown("### Data preview")
    c1, c2 = st.columns(2)
    fmt = {k: "{:,.2f}" for k in ["Open", "High", "Low", "Close"]} | {"Volume": "{:,.0f}"}
    c1.caption("First 5 sessions")
    c1.dataframe(clean.head().rename(index=lambda d: d.date()).style.format(fmt, na_rep="—"), width="stretch")
    c2.caption("Last 5 sessions")
    c2.dataframe(clean.tail().rename(index=lambda d: d.date()).style.format(fmt, na_rep="—"), width="stretch")
    cached = dsrc.list_cached()
    with st.expander(f"Locally stored real data ({len(cached)} instruments)"):
        if cached:
            st.dataframe(pd.DataFrame(cached), hide_index=True, width="stretch")
            st.caption("Select any of these in the sidebar with *Stored data only (offline)* to work without internet.")
        else:
            st.write("No downloaded data yet. Use **Refresh from Yahoo Finance** in the sidebar when online; files are saved in `data/raw/`.")

# ------------------------------------------------------------------ price
with tabs[1]:
    feat = indicators.feature_frame(clean)
    show = st.multiselect("Overlays", ["SMA20", "SMA50", "Bollinger Bands", "Donchian channel"], ["SMA20", "SMA50"])
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, row_heights=[0.6, 0.2, 0.2], vertical_spacing=0.04,
                        subplot_titles=("", "Volume", "RSI (14)"))
    fig.add_trace(go.Candlestick(x=clean.index, open=clean.Open, high=clean.High, low=clean.Low, close=clean.Close, name="Price",
                                 increasing=dict(line=dict(color=ui.GOOD, width=1), fillcolor=ui.GOOD),
                                 decreasing=dict(line=dict(color=ui.CRIT, width=1), fillcolor=ui.CRIT)), 1, 1)
    over = {}
    if "SMA20" in show: over["SMA 20"] = feat["SMA20"]
    if "SMA50" in show: over["SMA 50"] = feat["SMA50"]
    if "Bollinger Bands" in show:
        over["Upper band"], over["Lower band"] = feat["BB_upper"], feat["BB_lower"]
    if "Donchian channel" in show:
        over["Channel high"], over["Channel low"] = feat["DC_upper"], feat["DC_lower"]
    for i, (n, ser) in enumerate(over.items()):
        fig.add_trace(go.Scatter(x=ser.index, y=ser, name=n, line=dict(width=1.4, color=ui.SERIES[i % 8])), 1, 1)
    fig.add_trace(go.Bar(x=clean.index, y=clean.Volume, name="Volume", marker_color=ui.SEQ[2], showlegend=False), 2, 1)
    fig.add_trace(go.Scatter(x=feat.index, y=feat.RSI14, name="RSI", line=dict(color=ui.SERIES[6], width=1.4), showlegend=False), 3, 1)
    for lvl in (30, 70):
        fig.add_hline(y=lvl, line=dict(color=ui.AXIS, dash="dot", width=1), row=3, col=1)
    fig.update_layout(xaxis_rangeslider_visible=False)
    st.plotly_chart(ui.style(fig, f"{info['name']} – daily price, volume and momentum", "Price", height=660).update_layout(margin_t=84), width="stretch")
    r = feat["Return"].dropna()
    c = st.columns(4)
    ui.kpi(c[0], "Annualised volatility", ui.pct(r.std() * np.sqrt(252)), "std of daily returns × √252")
    ui.kpi(c[1], "Best day", ui.pct(r.max(), 2, True), f"{r.idxmax().date()}")
    ui.kpi(c[2], "Worst day", ui.pct(r.min(), 2, True), f"{r.idxmin().date()}")
    ui.kpi(c[3], "Up days", ui.pct((r > 0).mean(), 0), f"of {len(r):,} sessions")
    hist = go.Figure(go.Histogram(x=r, nbinsx=80, marker_color=ui.SERIES[0], hovertemplate="Return %{x:.2%}<br>Days %{y}<extra></extra>"))
    hist.update_xaxes(tickformat=".1%")
    st.plotly_chart(ui.style(hist, "Distribution of daily returns", "Number of sessions", "Daily return", 300, legend=False), width="stretch")
    ui.takeaway("Fat tails – more extreme days than a normal distribution would predict – are why drawdown and worst-day figures matter "
                "as much as average return.")

# ------------------------------------------------------------------ dictionary
with tabs[2]:
    st.caption("Raw fields come from the data source; derived fields are calculated by the app using only past and current observations.")
    dd = pd.DataFrame(glossary.DATA_DICTIONARY, columns=["Field", "Type", "Meaning", "Calculation", "Input columns"])
    st.dataframe(dd, hide_index=True, width="stretch", height=600)

# ------------------------------------------------------------------ quality
with tabs[3]:
    st.markdown("### How the data was cleaned")
    st.caption("Every check that ran, how many rows it affected and what was done. Prices are never invented or forward-filled.")
    st.dataframe(rep.as_frame(), hide_index=True, width="stretch")
    if b.is_synthetic and b.meta.get("injected_issues"):
        st.caption("Synthetic data contains deliberately injected issues to demonstrate the checks: " + "; ".join(b.meta["injected_issues"]) + ".")
    fl = rep.flags
    c1, c2 = st.columns(2)
    with c1:
        miss = b.df.isna().sum()
        fig = go.Figure(go.Bar(x=miss.index, y=miss.values, marker_color=ui.SERIES[0], text=miss.values, textposition="outside",
                               hovertemplate="%{x}: %{y} missing<extra></extra>"))
        st.plotly_chart(ui.style(fig, "Missing values by column (raw data)", "Rows", legend=False, height=300), width="stretch")
    with c2:
        req = pd.Timestamp(s.start), pd.Timestamp(s.end)
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=list(req), y=["Requested", "Requested"], mode="lines+markers", line=dict(color=ui.MUTED, width=8), name="Requested"))
        fig.add_trace(go.Scatter(x=[pd.Timestamp(cov["actual_start"]), pd.Timestamp(cov["actual_end"])], y=["Available", "Available"],
                                 mode="lines+markers", line=dict(color=ui.SERIES[0], width=8), name="Available"))
        fig.update_layout(hovermode="closest")
        st.plotly_chart(ui.style(fig, "Requested vs available dates", height=300, legend=False), width="stretch")
    gaps = fl[fl["price_gap"]]
    fig = go.Figure(go.Scatter(x=fl.index, y=fl["gap_pct"], mode="lines", line=dict(color=ui.SEQ[3], width=1), name="Overnight gap",
                               hovertemplate="%{x|%d %b %Y}: %{y:.2f}%<extra></extra>"))
    if len(gaps):
        fig.add_trace(go.Scatter(x=gaps.index, y=gaps["gap_pct"], mode="markers", marker=dict(color=ui.CRIT, size=9), name="Gap > 5%"))
    st.plotly_chart(ui.style(fig, "Overnight price gaps (open vs previous close)", "Gap (%)", height=300), width="stretch")
    vol = clean["Volume"]
    spikes = fl[fl["volume_spike"] | fl["volume_zero"] | fl["volume_missing"]]
    fig = go.Figure(go.Scatter(x=vol.index, y=vol, mode="lines", line=dict(color=ui.SEQ[3], width=1), name="Volume"))
    if len(spikes):
        fig.add_trace(go.Scatter(x=spikes.index, y=vol.reindex(spikes.index).fillna(0), mode="markers",
                                 marker=dict(color=ui.SERIES[1], size=9, symbol="diamond"), name="Anomaly (spike / zero / missing)"))
    st.plotly_chart(ui.style(fig, "Volume with flagged anomalies", "Volume", height=300), width="stretch")
    with st.expander(f"Flagged rows ({int((fl[['price_gap', 'volume_missing', 'volume_zero', 'volume_spike']].any(axis=1)).sum())})"):
        st.dataframe(fl[fl[["price_gap", "volume_missing", "volume_zero", "volume_spike"]].any(axis=1)], width="stretch")

# ------------------------------------------------------------------ correlation
with tabs[4]:
    st.caption("Correlation of daily returns across the instrument universe over the selected period. Loads every instrument, "
               "so it runs on request.")
    if st.button("Load universe and compute correlations"):
        st.session_state.show_corr = True
    if st.session_state.get("show_corr"):
        rets, labels = {}, []
        synth_any = False
        for sym in config.INSTRUMENTS:
            d = ui.dataset(sym)
            synth_any |= d.bundle.is_synthetic
            rets[config.INSTRUMENTS[sym]["name"]] = d.clean["Close"].pct_change()
        corr = pd.DataFrame(rets).dropna(how="all").corr()
        fig = go.Figure(go.Heatmap(z=corr.values, x=corr.columns, y=corr.index, zmin=-1, zmax=1, colorscale=ui.DIVERGING,
                                   text=np.round(corr.values, 2), texttemplate="%{text}", hovertemplate="%{y} vs %{x}: %{z:.2f}<extra></extra>",
                                   colorbar=dict(title="ρ")))
        st.plotly_chart(ui.style(fig, "Correlation of daily returns", height=520, legend=False), width="stretch")
        if synth_any:
            st.warning("At least one series is synthetic; synthetic series are generated independently, so their correlations are near zero by construction.")
        ui.takeaway("Highly correlated holdings fall together; diversification benefit comes from low-correlation pairs. Correlations also rise in crises.")

# ------------------------------------------------------------------ glossary
with tabs[5]:
    q = st.text_input("Search the glossary", placeholder="e.g. drawdown, delta, walk-forward")
    items = [g for g in glossary.GLOSSARY if not q or q.lower() in (" ".join(g)).lower()]
    st.caption(f"{len(items)} of {len(glossary.GLOSSARY)} terms")
    for term, d, why, how, ex in items:
        with st.expander(term):
            st.markdown(f"**What it is.** {d}\n\n**Why it matters.** {why}\n\n**How this app uses it.** {how}" + (f"\n\n**Example.** {ex}" if ex else ""))
ui.footer(ds)
