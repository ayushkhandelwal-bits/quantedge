import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import config
from src import correlation as co
from src import pattern_validation as pv
from src import spreads, ui

ui.header("Correlation & Regime Dynamics",
          "How the stocks move with each other and with the NIFTY 50 – and how that changes in bull, bear and high-volatility markets.")
s = st.session_state
ds = ui.dataset()
ui.after_load()

BENCH = "^NSEI"
universe = [k for k, v in config.INSTRUMENTS.items() if v["ccy"] == "INR"]
with st.container(border=True):
    c = st.columns([4, 2, 2, 2])
    sel = c[0].multiselect("Instruments", universe, universe, format_func=ui.short_name)
    method = c[1].radio("Method", ["pearson", "spearman"], format_func={"pearson": "Pearson (linear)", "spearman": "Spearman (rank)"}.get)
    window = c[2].select_slider("Rolling window (sessions)", [21, 42, 63, 126, 252], 63)
    inc_sp = c[3].checkbox("Include S&P 500", False, help="Different trading calendar and currency: only dates when both markets traded are used.")
if BENCH not in sel:
    sel = [BENCH] + sel
if inc_sp:
    sel = sel + ["^GSPC"]
if len(sel) < 2:
    st.info("Select at least one instrument besides NIFTY 50.")
    st.stop()

closes, status = ui.closes(sel)
ui.synthetic_notice(status)
rets = co.returns_panel(closes)
names = {k: ui.short_name(k) for k in rets.columns}
regime = pv.market_regime(closes[BENCH])
reg_counts = regime.reindex(rets.index).value_counts()

c = st.columns(4)
corr_full = co.corr_matrix(rets, method)
avg_corr = corr_full.where(~np.eye(len(corr_full), dtype=bool)).stack().mean()
vb = co.vs_benchmark(rets, BENCH, method)
ui.kpi(c[0], "Instruments", f"{len(rets.columns)}", f"{rets.index.min().date()} → {rets.index.max().date()}")
ui.kpi(c[1], "Average pairwise correlation", ui.num(avg_corr), f"{method.title()}, daily returns")
ui.kpi(c[2], "Highest correlation with NIFTY", ui.short_name(vb.loc[vb["Correlation"].idxmax(), "Instrument"]) if vb["Correlation"].notna().any() else "n/a",
       f"ρ = {ui.num(vb['Correlation'].max())}")
ui.kpi(c[3], "Regime sessions (NIFTY)", " / ".join(str(int(reg_counts.get(k, 0))) for k in ["Bullish", "Bearish", "High volatility"]),
       "Bullish / Bearish / High-volatility")

t1, t2, t3, t4, t5 = st.tabs(["Correlation matrix", "Rolling correlation & beta", "Regime dynamics", "Diversification", "Rates futures & spreads"])

with t1:
    nmat = co.pair_n(rets)
    lab = [names[c_] for c_ in corr_full.columns]
    fig = go.Figure(go.Heatmap(z=corr_full.values, x=lab, y=lab, zmin=-1, zmax=1, colorscale=ui.DIVERGING,
                               text=np.round(corr_full.values, 2), texttemplate="%{text}", customdata=nmat.reindex_like(corr_full).values,
                               hovertemplate="%{y} vs %{x}: ρ = %{z:.2f}<br>n = %{customdata} shared sessions<extra></extra>",
                               colorbar=dict(title="ρ")))
    fig.update_yaxes(autorange="reversed")
    st.plotly_chart(ui.style(fig, f"Correlation of daily returns ({method.title()}), full period", height=150 + 46 * len(lab), legend=False), width="stretch")
    st.markdown("#### Relationship with NIFTY 50")
    st.dataframe(vb.assign(Instrument=vb["Instrument"].map(names)).style.format(
        {"Correlation": ui.num, "CI low": ui.num, "CI high": ui.num, "p-value": lambda x: "<0.001" if x == x and x < 0.001 else ui.num(x, 3),
         "Beta": ui.num, "R²": lambda x: ui.pct(x, 0)}, na_rep="n/a"), hide_index=True, width="stretch")
    st.caption("Beta: average % move of the stock for a 1% move in NIFTY. R²: share of the stock's daily variance that moves with NIFTY. "
               "95% intervals use the Fisher z-transform. Pairs use only dates where both instruments traded (n shown on hover).")
    miss = pd.DataFrame({"Instrument": [names[c_] for c_ in rets.columns], "Sessions with a return": rets.notna().sum().values,
                         "Missing vs union of dates": rets.isna().sum().values})
    with st.expander("Missing-data handling"):
        st.dataframe(miss, hide_index=True, width="stretch")
        st.markdown("Returns are computed on each instrument's own trading days. Dates are aligned without forward-filling, and every "
                    "coefficient uses only the sessions where both series have a return (pairwise-complete), so holiday differences "
                    "never create artificial zero returns.")

with t2:
    stocks = [c_ for c_ in rets.columns if c_ != BENCH]
    pick = st.multiselect("Stocks", stocks, stocks[:4], format_func=ui.short_name, key="roll_pick")
    fig = go.Figure()
    for i, sym in enumerate(pick):
        rc = co.rolling_corr(rets, sym, BENCH, window)
        fig.add_trace(go.Scatter(x=rc.index, y=rc, name=names[sym], line=dict(width=1.7, color=ui.SERIES[i % 8]), hovertemplate="%{y:.2f}"))
    # shade high-volatility regime
    hv = (regime == "High volatility").reindex(rets.index).fillna(False)
    if hv.any():
        blocks = (hv != hv.shift()).cumsum()
        for _, grp in hv[hv].groupby(blocks[hv]):
            fig.add_vrect(x0=grp.index[0], x1=grp.index[-1], fillcolor=ui.SERIES[3], opacity=0.10, line_width=0)
    fig.add_hline(y=0, line=dict(color=ui.AXIS))
    fig.update_yaxes(range=[-1, 1])
    st.plotly_chart(ui.style(fig, f"{window}-session rolling correlation with NIFTY 50 (shaded = high-volatility regime)", "Correlation"),
                    width="stretch")
    fig = go.Figure()
    for i, sym in enumerate(pick):
        rb = co.rolling_beta(rets, sym, BENCH, window)
        fig.add_trace(go.Scatter(x=rb.index, y=rb, name=names[sym], line=dict(width=1.7, color=ui.SERIES[i % 8]), hovertemplate="%{y:.2f}"))
    fig.add_hline(y=1, line=dict(color=ui.AXIS, dash="dot"))
    st.plotly_chart(ui.style(fig, f"{window}-session rolling beta to NIFTY 50", "Beta", height=320), width="stretch")
    ui.takeaway("Correlations are not constant. When the lines rise together – often during sell-offs – the diversification you counted on "
                "shrinks exactly when it is needed most. Each point uses only the trailing window up to that date.")

with t3:
    st.caption("Regimes from NIFTY 50: **Bullish** = close above its 200-session average; **Bearish** = below; **High volatility** = 20-session "
               "volatility above the 75th percentile of its own history to date (overrides trend). The first ~200 sessions are unlabelled.")
    br = co.by_regime(rets, regime, BENCH, method)
    if len(br):
        regs = [r for r in ["Bullish", "Bearish", "High volatility"] if r in br["Regime"].unique()]
        fig = go.Figure()
        for i, rg in enumerate(regs):
            x = br[br["Regime"] == rg]
            fig.add_trace(go.Bar(x=x["Instrument"].map(names), y=x["Correlation"], name=f"{rg} (n≈{int(x['Observations'].median())})",
                                 marker_color=[ui.SERIES[0], ui.SERIES[7], ui.SERIES[3]][i],
                                 error_y=dict(type="data", array=(x["CI high"] - x["Correlation"]).fillna(0),
                                              arrayminus=(x["Correlation"] - x["CI low"]).fillna(0), color=ui.INK2, thickness=1),
                                 hovertemplate="%{x} – " + rg + ": ρ = %{y:.2f}<extra></extra>"))
        fig.update_layout(barmode="group", bargap=0.25, bargroupgap=0.06, hovermode="closest")
        st.plotly_chart(ui.style(fig, "Correlation with NIFTY 50 by market regime (95% CI)", "Correlation"), width="stretch")
        st.dataframe(br.assign(Instrument=br["Instrument"].map(names)).style.format(
            {"Correlation": ui.num, "CI low": ui.num, "CI high": ui.num, "All-days correlation": ui.num,
             "p-value vs all days": lambda x: "<0.001" if x == x and x < 0.001 else ui.num(x, 3)}, na_rep="n/a"),
            hide_index=True, width="stretch", height=340)
        st.caption("p-value vs all days: Fisher z-test of whether the regime correlation differs from the full-period figure (approximate – "
                   "the two samples overlap and returns cluster in time).")
    mats = co.regime_matrices(rets, regime, method)
    if mats:
        rtabs = st.tabs([f"{k} ({v[1]} sessions)" for k, v in mats.items()])
        for tab, (k, (m, n)) in zip(rtabs, mats.items()):
            with tab:
                lab = [names[c_] for c_ in m.columns]
                fig = go.Figure(go.Heatmap(z=m.values, x=lab, y=lab, zmin=-1, zmax=1, colorscale=ui.DIVERGING, text=np.round(m.values, 2),
                                           texttemplate="%{text}", hovertemplate="%{y} vs %{x}: %{z:.2f}<extra></extra>"))
                fig.update_yaxes(autorange="reversed")
                st.plotly_chart(ui.style(fig, f"Correlation matrix – {k}", height=130 + 44 * len(lab), legend=False), width="stretch")

with t4:
    stocks = [c_ for c_ in rets.columns if c_ != BENCH]
    port = st.multiselect("Equal-weight portfolio of", stocks, stocks, format_func=ui.short_name, key="port")
    if len(port) >= 2:
        full = co.portfolio_risk(rets[port])
        rows = [{"Scenario": "All days (actual)", **full}]
        for k, (m, n) in mats.items():
            if all(p_ in m.columns for p_ in port) and m.loc[port, port].notna().all().all():
                rows.append({"Scenario": f"{k} correlations", **co.portfolio_risk(rets[port], corr=m.loc[port, port])})
        pr = pd.DataFrame(rows)
        c = st.columns(3)
        ui.kpi(c[0], "Average volatility of the stocks", ui.pct(full["weighted_avg_vol"]), "annualised")
        ui.kpi(c[1], "Equal-weight portfolio volatility", ui.pct(full["portfolio_vol"]), f"{full['observations']} common sessions")
        ui.kpi(c[2], "Risk removed by diversification", ui.pct(full["risk_reduction"]), f"diversification ratio {ui.num(full['diversification_ratio'])}")
        fig = go.Figure(go.Bar(x=pr["Scenario"], y=pr["portfolio_vol"], marker_color=ui.SERIES[0],
                               text=[ui.pct(v) for v in pr["portfolio_vol"]], textposition="outside",
                               hovertemplate="%{x}: %{y:.1%}<extra></extra>"))
        fig.add_hline(y=full["weighted_avg_vol"], line=dict(color=ui.SERIES[1], dash="dash"), annotation_text="no diversification (avg stock vol)")
        fig.update_yaxes(tickformat=".0%")
        st.plotly_chart(ui.style(fig, "Portfolio volatility under each regime's correlation structure (same stock volatilities)",
                                 "Annualised volatility", height=360, legend=False), width="stretch")
        prd = pr.rename(columns={"portfolio_vol": "Portfolio volatility", "weighted_avg_vol": "Average stock volatility",
                                 "diversification_ratio": "Diversification ratio", "risk_reduction": "Risk removed",
                                 "avg_pairwise_corr": "Average pairwise correlation", "observations": "Sessions"})
        st.dataframe(prd.style.format({"Portfolio volatility": ui.pct, "Average stock volatility": ui.pct, "Diversification ratio": ui.num,
                                       "Risk removed": ui.pct, "Average pairwise correlation": ui.num}), hide_index=True, width="stretch")
        worst = pr.iloc[pr["portfolio_vol"].idxmax()]
        ui.takeaway(f"Holding these {len(port)} stocks equally cut volatility by {ui.pct(full['risk_reduction'])} versus the average single stock. "
                    f"Under the least favourable regime correlations ({worst['Scenario'].replace(' correlations', '')}), portfolio "
                    f"volatility would be {ui.pct(worst['portfolio_vol'])}. Diversification is weakest when average correlation is highest.")
        st.caption("Scenario rows hold each stock's full-period volatility fixed and swap in the regime's correlation matrix, isolating the "
                   "effect of changing correlations. In reality volatilities also rise in stressed regimes, so true risk is higher still.")
    else:
        st.info("Select at least two stocks.")

with t5:
    st.markdown("#### Short-term interest-rate futures, calendar spreads and butterflies")
    st.info("**No STIR or contract-level futures data is included.** Free sources do not provide multi-year history for individual "
            "(including expired) contract months, which calendar spreads and butterflies require. Upload your own contract prices to "
            "analyse them here – nothing is computed or shown without real data.", icon="ℹ️")
    st.download_button("Download CSV template (format only – placeholder values)", spreads.TEMPLATE, "contracts_template.csv", "text/csv")
    up = st.file_uploader("Upload contract prices (CSV: Date, Contract, Close; optional Expiry)", type=["csv"])
    if up is not None:
        try:
            wide, msgs = spreads.parse_contracts(up.getvalue())
        except Exception as e:  # noqa: BLE001
            st.error(f"Could not read the file: {e}")
            wide, msgs = None, []
        for m_ in msgs:
            st.caption(f"ℹ️ {m_}")
        if wide is not None and wide.shape[1] >= 2:
            st.caption(f"User-supplied data: {wide.shape[1]} contracts, {len(wide)} dates ({wide.index.min().date()} → {wide.index.max().date()}).")
            contracts = list(wide.columns)
            kind = st.radio("Structure", ["Calendar spread", "Butterfly"], horizontal=True)
            cc = st.columns(3)
            a = cc[0].selectbox("Front / near", contracts, 0)
            b = cc[1].selectbox("Middle / far", contracts, min(1, len(contracts) - 1))
            cser = None
            if kind == "Butterfly":
                if len(contracts) < 3:
                    st.warning("A butterfly needs three contracts.")
                else:
                    cc3 = cc[2].selectbox("Back", contracts, min(2, len(contracts) - 1))
                    cser = spreads.butterfly(wide, a, b, cc3)
            else:
                cser = spreads.calendar_spread(wide, a, b)
            if cser is not None:
                st_ = spreads.spread_stats(cser)
                fig = go.Figure(go.Scatter(x=cser.index, y=cser, mode="lines", line=dict(color=ui.SERIES[0], width=1.8), name=cser.name))
                st.plotly_chart(ui.style(fig, f"{kind}: {cser.name} (user-supplied data)", "Price points", height=320, legend=False), width="stretch")
                k4 = st.columns(4)
                ui.kpi(k4[0], "Observations", f"{st_['observations']}", f"{st_['first']:%d %b %Y} → {st_['last']:%d %b %Y}")
                ui.kpi(k4[1], "Mean level", ui.num(st_["mean"], 4), f"range {ui.num(st_['min'], 4)} to {ui.num(st_['max'], 4)}")
                ui.kpi(k4[2], "Std deviation", ui.num(st_["std"], 4), "of the level")
                ui.kpi(k4[3], "Daily change std", ui.num(st_["daily_change_std"], 4), "typical day-to-day move")
                ch = cser.diff().rename("spread_change")
                nifty_r = rets[BENCH]
                pair = pd.concat([ch, nifty_r], axis=1, join="inner").dropna()
                if len(pair) >= 30:
                    r = pair.iloc[:, 0].corr(pair.iloc[:, 1], method=method)
                    lo, hi = co.fisher_ci(r, len(pair))
                    st.markdown(f"Correlation of daily **changes** in the {kind.lower()} with NIFTY 50 returns: **{r:.2f}** "
                                f"(95% CI {lo:.2f} to {hi:.2f}, n = {len(pair)} shared dates).")
                else:
                    st.caption(f"Only {len(pair)} dates overlap with NIFTY data – too few for a correlation estimate (need ≥ 30).")
        elif wide is not None:
            st.warning("At least two contracts are needed for a spread.")

st.markdown("---")
st.markdown("**Correlation is not causation.** Two stocks can move together because of a shared driver – interest rates, oil, global risk "
            "appetite, sector news – without one influencing the other. Correlations estimated on past data also change over time, "
            "so these figures describe history and are not forecasts.")
ui.footer(ds)
