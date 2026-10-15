import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import config
from src import candlestick_patterns as cp
from src import pattern_validation as pv
from src import transaction_costs as tc
from src import ui

ui.header("Candlestick Pattern Validation",
          "Do classic candlestick patterns predict what happens next – across stocks, market regimes and correlation environments?")
s = st.session_state
ds = ui.dataset()
ui.after_load()

STOCKS = [k for k, v in config.INSTRUMENTS.items() if v["tradable"]]
default_stocks = [x for x in ["RELIANCE.NS", "HDFCBANK.NS", "ITC.NS", "TCS.NS"] if x in STOCKS]

with st.container(border=True):
    c = st.columns([3, 3, 2, 2])
    stocks = c[0].multiselect("Stocks", STOCKS, default_stocks, format_func=ui.short_name)
    pats = c[1].multiselect("Patterns", list(cp.PATTERNS), list(cp.PATTERNS))
    horizons = c[2].multiselect("Horizons (sessions)", [1, 3, 5, 10], [1, 3, 5, 10])
    entry = c[3].radio("Entry price", ["next_open", "close"], format_func={"next_open": "Next open (realistic)",
                                                                           "close": "Signal close (textbook)"}.get)
    c = st.columns(4)
    default_cost = tc.round_trip_cost_pct(1000, 1000, tc.CostSchedule(slippage_bps=s.slippage_bps))
    cost = c[0].number_input("Round-trip cost (%)", 0.0, 2.0, round(default_cost, 3), 0.01,
                             help="Default: published delivery charges + sidebar slippage, both sides, on a ₹10 lakh trade.") / 100
    oos = c[1].slider("Out-of-sample share (latest %)", 10, 50, 30, 5) / 100
    min_n = int(c[2].number_input("Minimum sample to judge", 5, 100, pv.MIN_SAMPLE, 5))
    with c[3].popover("Pattern thresholds"):
        pp = cp.PatternParams(
            doji_body_max=st.slider("Doji: max body / range", 0.02, 0.3, 0.10, 0.01),
            shadow_ratio=st.slider("Hammer / Star: shadow ≥ × body", 1.5, 4.0, 2.0, 0.25),
            marubozu_body_min=st.slider("Marubozu: min body / range", 0.7, 1.0, 0.90, 0.01),
            long_body_min=st.slider("Long candle: min body / range", 0.3, 0.9, 0.60, 0.05),
            star_body_max=st.slider("Star: middle body ≤ × first body", 0.1, 0.6, 0.30, 0.05),
            require_trend=st.checkbox("Require prior trend (reversal patterns)", True),
        )

if not stocks or not pats or not horizons:
    st.info("Select at least one stock, pattern and horizon.")
    st.stop()
horizons = sorted(horizons)

ev_all, bases, status = ui.pattern_events(stocks, pp, entry, cost, oos)
ui.synthetic_notice(status)
if ev_all.empty:
    st.warning("No pattern occurrences found with these settings.")
    st.stop()
ev = ev_all[ev_all["Pattern"].isin(pats)].copy()
H = st.select_slider("Horizon for the detailed analysis below", horizons, horizons[min(len(horizons) - 1, 2)] if len(horizons) > 2 else horizons[-1])

summ = pv.summarise(ev, bases, H, min_sample=min_n)
summ["Verdict"] = summ.apply(pv.verdict, axis=1)
direc = summ[summ["Bias"].isin(["Bullish", "Bearish"])]
c = st.columns(4)
ui.kpi(c[0], "Pattern occurrences", f"{len(ev):,}", f"{len(stocks)} stocks · {ev['Pattern'].nunique()} patterns")
ui.kpi(c[1], "Directional patterns with enough data", f"{(direc['Occurrences'] >= min_n).sum()} / {len(direc)}", f"n ≥ {min_n} at {H} sessions")
ui.kpi(c[2], "Show a reliable edge after costs", f"{(direc['Verdict'] == 'Edge, survives costs').sum()}",
       "hit-rate interval above base rate, q < 0.10, net > 0")
ui.kpi(c[3], "Assumed round-trip cost", f"{cost:.2%}", "deducted from every directional return")

t1, t2, t3, t4, t5, t6 = st.tabs(["Scorecard", "By stock", "By regime & correlation", "Out-of-sample check", "Annotated chart", "Event explorer"])

fmt_pct = lambda x: ui.pct(x, 1)  # noqa: E731
fmt_pct2 = lambda x: ui.pct(x, 2, True)  # noqa: E731
fmt_p = lambda x: "n/a" if x is None or x != x else (f"{x:.3f}" if x >= 0.001 else "<0.001")  # noqa: E731

with t1:
    st.markdown(f"#### Directional patterns – {H}-session horizon (all selected stocks pooled)")
    if len(direc):
        show = direc[["Pattern", "Bias", "Occurrences", "Hit rate", "Hit rate CI low", "Hit rate CI high", "Base-rate hit", "Hit-rate p-value",
                      "q-value (BH)", "Avg directional return", "Avg net return (after costs)", "Success rate (net > 0)",
                      "Avg adverse excursion", "Return / risk (mean ÷ sd)", "Verdict"]].sort_values("Occurrences", ascending=False)
        st.dataframe(show.style.format({"Hit rate": fmt_pct, "Hit rate CI low": fmt_pct, "Hit rate CI high": fmt_pct, "Base-rate hit": fmt_pct,
                                        "Hit-rate p-value": fmt_p, "q-value (BH)": fmt_p, "Avg directional return": fmt_pct2,
                                        "Avg net return (after costs)": fmt_pct2, "Success rate (net > 0)": fmt_pct,
                                        "Avg adverse excursion": fmt_pct2, "Return / risk (mean ÷ sd)": lambda x: ui.num(x)}, na_rep="n/a"),
                     hide_index=True, width="stretch")
        fig = go.Figure()
        d = direc.sort_values("Avg directional return")
        err_hi = (d["Return CI high"] - d["Avg directional return"]).fillna(0)
        err_lo = (d["Avg directional return"] - d["Return CI low"]).fillna(0)
        fig.add_trace(go.Scatter(x=d["Avg directional return"], y=d["Pattern"], mode="markers", name="Mean (before costs)",
                                 marker=dict(size=10, color=ui.SERIES[0]),
                                 error_x=dict(type="data", array=err_hi, arrayminus=err_lo, color=ui.SERIES[0], thickness=1.5),
                                 customdata=np.c_[d["Occurrences"]], hovertemplate="%{y}: %{x:.2%} (n=%{customdata[0]})<extra></extra>"))
        fig.add_trace(go.Scatter(x=d["Avg net return (after costs)"], y=d["Pattern"], mode="markers", name="Mean after costs",
                                 marker=dict(size=9, color=ui.SERIES[1], symbol="diamond"), hovertemplate="%{y}: %{x:.2%} after costs<extra></extra>"))
        fig.add_vline(x=0, line=dict(color=ui.INK2, width=1))
        fig.update_xaxes(tickformat=".1%")
        fig.update_layout(hovermode="closest")
        st.plotly_chart(ui.style(fig, f"Average {H}-session return in the pattern's direction, with 95% confidence interval",
                                 "", "Directional return", height=120 + 34 * len(d)), width="stretch")
        st.caption("A bar that crosses zero means the data cannot distinguish the pattern from no effect. 'Directional' = sign flipped for "
                   "bearish patterns, so positive always means the pattern was right.")
    neutral = summ[~summ["Bias"].isin(["Bullish", "Bearish"])]
    if len(neutral):
        st.markdown("#### Neutral pattern (Doji): does indecision precede larger moves?")
        st.dataframe(neutral[["Pattern", "Occurrences", "Avg absolute move", "Typical absolute move", "Move ratio", "Move p-value", "Verdict"]]
                     .style.format({"Avg absolute move": lambda x: ui.pct(x, 2), "Typical absolute move": lambda x: ui.pct(x, 2), "Move ratio": ui.num, "Move p-value": fmt_p},
                                   na_rep="n/a"), hide_index=True, width="stretch")
    st.markdown("#### All horizons at a glance")
    rows = []
    for hz in horizons:
        sm = pv.summarise(ev, bases, hz, min_sample=min_n)
        sm = sm[sm["Bias"].isin(["Bullish", "Bearish"])]
        for _, r in sm.iterrows():
            rows.append({"Pattern": r["Pattern"], "Horizon": f"{hz}d", "edge": r["Hit rate"] - r["Base-rate hit"], "n": r["Occurrences"]})
    if rows:
        g = pd.DataFrame(rows).pivot(index="Pattern", columns="Horizon", values="edge")[[f"{h}d" for h in horizons]]
        nn = pd.DataFrame(rows).pivot(index="Pattern", columns="Horizon", values="n")[[f"{h}d" for h in horizons]]
        txt = [[(f"{v:+.0%}<br>n={int(n)}" if n >= min_n else f"n={int(n)}<br>too few") if np.isfinite(v) else "" for v, n in zip(rv, rn)]
               for rv, rn in zip(g.values, nn.values)]
        g = g.where(nn >= min_n)            # small samples are not coloured, so they cannot dominate the scale
        lim = float(np.nanmax(np.abs(g.values))) if np.isfinite(g.values).any() else 0.1
        fig = go.Figure(go.Heatmap(z=g.values, x=g.columns, y=g.index, colorscale=ui.DIVERGING, zmid=0, zmin=-lim, zmax=lim,
                                   text=txt,
                                   texttemplate="%{text}", hovertemplate="%{y}, %{x}: hit rate − base rate %{z:+.1%}<extra></extra>",
                                   colorbar=dict(title="Edge", tickformat="+.0%")))
        st.plotly_chart(ui.style(fig, f"Hit rate minus base rate, by horizon (blue = better than chance; uncoloured = fewer than {min_n} cases)", height=110 + 38 * len(g), legend=False),
                        width="stretch")
    ui.takeaway("Read the confidence intervals and q-values, not just the hit rate: with 11 patterns × 4 horizons, a few 'significant' "
                "results are expected by chance alone. A pattern is only interesting if its edge is larger than the round-trip cost "
                "and it holds up out-of-sample.")

with t2:
    sb = pv.summarise(ev, bases, H, by=["Pattern", "Instrument"], min_sample=min_n)
    sb = sb[sb["Bias"].isin(["Bullish", "Bearish"])]
    if len(sb):
        metric = st.radio("Metric", ["Avg net return (after costs)", "Hit rate edge"], horizontal=True)
        sb["Hit rate edge"] = sb["Hit rate"] - sb["Base-rate hit"]
        z = sb.pivot(index="Pattern", columns="Instrument", values=metric)
        nn = sb.pivot(index="Pattern", columns="Instrument", values="Occurrences").reindex_like(z)
        txt = [[(f"{v:+.2%}" if np.isfinite(v) else "") + (f"<br>n={int(n)}" if np.isfinite(n) else "") for v, n in zip(rv, rn)]
               for rv, rn in zip(z.values, nn.values)]
        z = z.where(nn >= min_n)
        lim = float(np.nanmax(np.abs(z.values))) if np.isfinite(z.values).any() else 0.01
        fig = go.Figure(go.Heatmap(z=z.values, x=[ui.short_name(c) for c in z.columns], y=z.index, colorscale=ui.DIVERGING, zmid=0,
                                   zmin=-lim, zmax=lim,
                                   text=txt,
                                   texttemplate="%{text}", hovertemplate="%{y} on %{x}: %{z:+.2%}<extra></extra>",
                                   colorbar=dict(tickformat="+.1%")))
        st.plotly_chart(ui.style(fig, f"{metric} by stock – {H}-session horizon (uncoloured = fewer than {min_n} cases)", height=130 + 40 * len(z), legend=False), width="stretch")
        st.caption("Cells with small n (see the number under each value) are unreliable; compare across stocks only where samples are adequate.")
        sb["Verdict"] = sb.apply(pv.verdict, axis=1)
        st.dataframe(sb[["Pattern", "Instrument", "Occurrences", "Hit rate", "Base-rate hit", "Hit-rate p-value", "Avg net return (after costs)",
                         "Avg adverse excursion", "Verdict"]].style.format(
            {"Hit rate": fmt_pct, "Base-rate hit": fmt_pct, "Hit-rate p-value": fmt_p, "Avg net return (after costs)": fmt_pct2,
             "Avg adverse excursion": fmt_pct2}, na_rep="n/a"), hide_index=True, width="stretch", height=360)
        consistent = sb[sb["Occurrences"] >= min_n].groupby("Pattern")["Avg net return (after costs)"].agg(lambda x: (x > 0).mean())
        if len(consistent):
            best = consistent.idxmax()
            ui.takeaway(f"Patterns rarely behave the same on every stock. Among patterns with enough cases, **{best}** had a positive "
                        f"after-cost average on {consistent.max():.0%} of the stocks where it could be measured. Differences between "
                        "stocks may reflect sector behaviour, liquidity or plain chance – they are not guaranteed to persist.")

with t3:
    st.markdown("#### Does the market environment change how patterns perform?")
    dim = st.radio("Split by", ["Market regime", "Stock trend", "Stock volatility", "Correlation environment"], horizontal=True,
                   help="Market regime: NIFTY 50 above/below its 200-session average, or high volatility (overrides trend). "
                        "Correlation environment: the stock's 63-session correlation with NIFTY on the signal date.")
    sr = pv.summarise(ev[ev[dim] != "Insufficient history"], bases, H, by=["Pattern", dim], min_sample=min_n)
    sr = sr[sr["Bias"].isin(["Bullish", "Bearish"])]
    if len(sr):
        sel_p = st.multiselect("Patterns to compare", sorted(sr["Pattern"].unique()),
                               sorted(sr.groupby("Pattern")["Occurrences"].sum().nlargest(4).index))
        sub = sr[sr["Pattern"].isin(sel_p)]
        cats = sorted(sub[dim].unique())
        fig = go.Figure()
        for i, cat in enumerate(cats):
            x = sub[sub[dim] == cat]
            fixed = {"Bullish": ui.SERIES[0], "Bearish": ui.SERIES[7], "High volatility": ui.SERIES[3], "Normal volatility": ui.SERIES[2]}
            fig.add_trace(go.Bar(x=x["Pattern"], y=x["Avg net return (after costs)"], name=cat, marker_color=fixed.get(cat, ui.SERIES[i % 8]),
                                 error_y=dict(type="data", array=(x["Return CI high"] - x["Avg directional return"]).fillna(0),
                                              arrayminus=(x["Avg directional return"] - x["Return CI low"]).fillna(0), color=ui.INK2, thickness=1),
                                 customdata=x[["Occurrences"]].to_numpy(),
                                 hovertemplate="%{x} – " + cat + ": %{y:.2%} after costs (n=%{customdata[0]})<extra></extra>"))
        fig.add_hline(y=0, line=dict(color=ui.INK2, width=1))
        fig.update_layout(barmode="group", bargap=0.25, bargroupgap=0.06, hovermode="closest")
        fig.update_yaxes(tickformat=".1%")
        st.plotly_chart(ui.style(fig, f"Average {H}-session net directional return by {dim.lower()} (95% CI)", "Net return"), width="stretch")
        st.dataframe(sr[["Pattern", dim, "Occurrences", "Hit rate", "Base-rate hit", "Hit-rate p-value", "Avg net return (after costs)",
                         "Avg adverse excursion", "Sample flag"]].style.format(
            {"Hit rate": fmt_pct, "Base-rate hit": fmt_pct, "Hit-rate p-value": fmt_p, "Avg net return (after costs)": fmt_pct2,
             "Avg adverse excursion": fmt_pct2}, na_rep="n/a"), hide_index=True, width="stretch", height=320)
        ui.takeaway("Splitting by environment shrinks every sample, so wide intervals are expected. Treat any regime difference as a "
                    "hypothesis to test on new data, not a rule – historical relationships between regimes and patterns need not persist.")
    st.caption("Context is measured with information available on the signal date only (trailing averages, trailing correlation).")

with t4:
    st.markdown(f"#### Chronological out-of-sample check – earliest {1 - oos:.0%} vs latest {oos:.0%} of each stock's history")
    oc = pv.oos_comparison(ev, bases, H)
    if len(oc):
        st.dataframe(oc.style.format({c: (fmt_pct if "hit" in c.lower() else fmt_pct2 if "net" in c else "{:,.0f}") for c in oc.columns
                                      if c not in ("Pattern", "Consistency")}, na_rep="n/a"), hide_index=True, width="stretch")
        counts = oc["Consistency"].value_counts()
        ui.takeaway(f"{counts.get('Edge persisted', 0)} pattern(s) kept an edge over the base rate in the later period, "
                    f"{counts.get('Edge disappeared', 0)} lost it, and {counts.get('Too few cases', 0)} had too few cases to judge. "
                    "Patterns are not tuned on the earlier period here, so this tests stability rather than over-fitting of parameters.")
    st.caption("Edge = hit rate − base rate; 'persisted' requires > 2 percentage points in both periods with at least 10 cases in each.")

with t5:
    sym = st.selectbox("Stock", stocks, format_func=ui.short_name)
    d = ui.dataset(sym).clean
    evs = ev[ev["Instrument"] == sym]
    psel = st.multiselect("Show patterns", sorted(evs["Pattern"].unique()), sorted(evs["Pattern"].unique())[:3])
    last_n = st.slider("Sessions shown (most recent)", 60, len(d), min(250, len(d)), 10)
    win = d.iloc[-last_n:]
    fig = ui.candle_fig(win, f"{ui.short_name(sym)} – detected patterns (marker colour = outcome at {H} sessions)", height=520)
    shown = evs[evs["Pattern"].isin(psel) & (evs["Date"] >= win.index[0])]
    for kind, col, sym_m in (("Right", ui.GOOD_TEXT, "triangle-up"), ("Wrong", ui.CRIT, "x"), ("Neutral / pending", ui.MUTED, "circle")):
        if kind == "Right":
            m = shown[shown[f"dir_{H}d"] > 0]
        elif kind == "Wrong":
            m = shown[shown[f"dir_{H}d"] <= 0]
        else:
            m = shown[shown[f"dir_{H}d"].isna()]
        if len(m):
            ys = [win.at[x, "Low"] * 0.98 for x in m["Date"]]
            txt = [f"{r.Pattern} ({r.Bias}) – {H}d return {ui.pct(getattr(r, f'ret_{H}d'), 2, True)}" for r in m.itertuples()]
            fig.add_trace(go.Scatter(x=m["Date"], y=ys, mode="markers", name=kind, text=txt, hovertemplate="%{text}<extra></extra>",
                                     marker=dict(symbol=sym_m, size=10, color=col, line=dict(color="white", width=1))))
    st.plotly_chart(fig, width="stretch")
    st.caption("Right = moved in the pattern's direction over the horizon (before costs); Wrong = did not; grey = neutral pattern or outcome "
               "not yet observable. Hover for details.")

with t6:
    c = st.columns(4)
    f_st = c[0].multiselect("Stock", stocks, stocks, format_func=ui.short_name, key="f_st")
    f_pt = c[1].multiselect("Pattern", sorted(ev["Pattern"].unique()), sorted(ev["Pattern"].unique()), key="f_pt")
    f_rg = c[2].multiselect("Market regime", sorted(ev["Market regime"].unique()), sorted(ev["Market regime"].unique()), key="f_rg")
    f_pd = c[3].multiselect("Period", ["In-sample", "Out-of-sample"], ["In-sample", "Out-of-sample"], key="f_pd")
    x = ev[ev["Instrument"].isin(f_st) & ev["Pattern"].isin(f_pt) & ev["Market regime"].isin(f_rg) & ev["Period"].isin(f_pd)].copy()
    cols = ["Date", "Instrument", "Pattern", "Bias", "Period", "Market regime", "Stock trend", "Correlation environment", "Corr with NIFTY",
            "Entry price"] + [f"ret_{h}d" for h in horizons] + [f"net_{h}d" for h in horizons] + [f"mae_{h}d" for h in horizons]
    x = x[[c_ for c_ in cols if c_ in x.columns]].sort_values("Date", ascending=False)
    st.caption(f"{len(x):,} events. ret = raw return from entry; net = directional return after costs; mae = worst adverse move within the horizon.")
    st.dataframe(x.assign(Date=x["Date"].dt.date).style.format(
        {**{c_: fmt_pct2 for c_ in x.columns if c_.startswith(("ret_", "net_", "mae_"))}, "Corr with NIFTY": ui.num, "Entry price": "{:,.2f}"},
        na_rep="—"), hide_index=True, width="stretch", height=420)
    st.download_button("Download events (CSV)", x.to_csv(index=False), "pattern_events.csv", "text/csv")

with st.expander("Method, assumptions and limitations"):
    st.markdown(f"""
- **Detection** uses only the signal session and the two before it (three-candle patterns). Thresholds are editable above.
- **Entry** at the next session's open by default (a pattern is only known after the close). **Outcome** = close *h* sessions after the signal ÷ entry − 1.
- **Directional return** flips the sign for bearish patterns. **Adverse excursion** = worst intraday move against the pattern before the horizon ends.
- **Base rate** = how often the same stock moved in that direction over the same horizon on *any* day – the "no information" benchmark.
- **Uncertainty**: Wilson 95% interval for hit rates, t-based 95% interval for mean returns, exact binomial test vs base rate, Benjamini–Hochberg q-values for multiple testing.
- **Costs**: round-trip {cost:.2%} deducted from each directional return (net).
- **Overlap**: events within *h* sessions of each other share price moves, so they are not fully independent – intervals are somewhat optimistic.
- **Not a trading system**: no position sizing or compounding; see Strategy Lab / Backtesting for a full backtest of a pattern strategy.
""")
ui.footer(ds)
