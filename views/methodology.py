import pandas as pd
import streamlit as st

import config
from src import transaction_costs as tc
from src import ui

st.markdown(ui.CSS, unsafe_allow_html=True)
st.markdown("# Methodology & Project Guide")
st.markdown("<div class='ql-sub'>How every number in this dashboard is produced, what it assumes, and where it can mislead.</div>",
            unsafe_allow_html=True)

st.markdown("## Analytical workflow")
st.graphviz_chart("""
digraph G {
  rankdir=LR; bgcolor="transparent";
  node [shape=box, style="rounded,filled", fillcolor="#f3f7fd", color="#86b6ef", fontname="Helvetica", fontsize=11, margin="0.15,0.08"];
  edge [color="#898781", arrowsize=0.7];
  a [label="1. Data collection\\nYahoo Finance → local cache\\n(synthetic fallback, labelled)"];
  b [label="2. Validation\\nsort · de-duplicate\\ninvalid / missing checks"];
  c [label="3. Indicators\\nSMA, RSI, Bollinger,\\nDonchian, ATR (causal)"];
  d [label="4. Signals\\ntarget position at close t"];
  e [label="5. Backtest\\nfill at open t+1\\ninteger shares"];
  f [label="6. Costs\\ncharges per side\\n+ slippage"];
  g [label="7. Performance\\nreturn, risk, trade stats"];
  h [label="8. Walk-forward\\ntrain → unseen test,\\nrolling"];
  i [label="9. Business view\\ngross→net, scenarios,\\nclassification", fillcolor="#e7f5e7", color="#0ca30c"];
  a -> b -> c -> d -> e -> f -> g -> h -> i;
}
""", width="stretch")

st.markdown("## How to use this dashboard")
st.markdown("""
1. **Choose an instrument, dates and a data source** in the sidebar. The badge on each page shows whether the data is **LIVE**, **CACHED** or **SYNTHETIC**.
2. **Market Explorer** – check coverage, cleaning steps and data quality; look up any term in the glossary.
3. **Correlation & Regimes** – how stocks move with each other and with NIFTY 50, how that changes in bullish, bearish and high-volatility markets, and what it means for diversification.
4. **Strategy Lab** – pick a strategy, tune its parameters and see exactly where it bought and sold, and why.
5. **Pattern Validation** – test 11 candlestick patterns across several stocks with confidence intervals, costs, regimes, correlation environments and an out-of-sample check.
6. **Backtesting** – compare all strategies under identical assumptions; inspect drawdowns, monthly returns and cost drag.
7. **Risk & Robustness** – walk-forward results, parameter and cost sensitivity, regimes.
8. **Derivatives** – price options, view Greeks and build multi-leg payoffs (theoretical values).
9. **Business Outcomes** – gross vs net, capital scenarios, the audit-able classification and a downloadable executive summary.
""")

st.markdown("## Key formulas (plain language)")
f = pd.DataFrame([
    ("Daily return", "rₜ = Vₜ / Vₜ₋₁ − 1", "Percentage change in portfolio value from one session to the next."),
    ("Total return", "V_end / V_start − 1", "Overall gain or loss after all costs."),
    ("CAGR", "(V_end / V_start)^(1/years) − 1, years = calendar days / 365.25", "Equivalent steady yearly growth rate."),
    ("Volatility", "stdev(rₜ) × √252", "Typical size of fluctuations, annualised."),
    ("Sharpe ratio", "(mean(rₜ) − r_f/252) / stdev(rₜ) × √252", "Excess return per unit of total risk. n/a if volatility is zero or < 20 sessions."),
    ("Sortino ratio", "mean(rₜ − r_f/252) / √mean(min(rₜ − r_f/252, 0)²) × √252", "Excess return per unit of downside risk. n/a if no down days."),
    ("Drawdown", "Vₜ / max(V₀…Vₜ) − 1", "Fall from the highest value reached so far."),
    ("Win rate", "winning trades / completed trades", "Trades with net P&L > 0 after costs."),
    ("Profit factor", "Σ profits of winners / Σ losses of losers", "n/a when there are no losing trades (not shown as ∞)."),
    ("Expectancy", "win rate × avg win − loss rate × |avg loss|", "Average net P&L per trade."),
    ("Gross P&L", "Σ (exit price − entry price) × qty × direction", "Using reference prices before slippage and charges."),
    ("Net P&L", "Gross P&L − charges − slippage", "What the investor actually keeps."),
    ("Black–Scholes call", "S·e^(−qT)·N(d₁) − K·e^(−rT)·N(d₂)", "d₁ = [ln(S/K) + (r − q + σ²/2)T] / σ√T, d₂ = d₁ − σ√T."),
], columns=["Measure", "Formula", "Meaning"])
st.dataframe(f, hide_index=True, width="stretch")

st.markdown("## Assumptions")
st.markdown(f"""
- **Data:** daily OHLCV from Yahoo Finance (via `yfinance`, prices adjusted for splits and dividends), cached in `data/raw/`. No paid data or API keys.
- **No look-ahead:** indicators use data up to the signal date's close; trades execute at the **next session's open**. Automated tests check that signals do not change when future data is added.
- **Position sizing:** 100% of current equity in whole shares; one position at a time per strategy; no leverage.
- **Shorting:** off by default (overnight shorting of Indian cash equities is not generally available to retail investors). Short signals then mean "stay flat".
- **Open positions** at the end of the data are closed at the final close and charged, so all statistics refer to completed trades.
- **Indices** (NIFTY 50, S&P 500) are not directly tradable; results treat them as a proxy for a low-cost index fund, with equity delivery costs.
- **Risk-free rate:** {config.RISK_FREE_SOURCE}.
- **Annualisation:** 252 trading sessions per year.
""")
st.markdown("**Transaction-cost schedule (equity delivery, per order side)** – " + tc.SOURCE_NOTE)
cs = tc.CostSchedule()
st.dataframe(pd.DataFrame([
    ("Brokerage (delivery)", f"₹{cs.brokerage_delivery_flat:g} per order"),
    ("Brokerage (intraday, gap strategy)", f"min(₹{cs.brokerage_intraday_flat:g}, {cs.brokerage_intraday_pct:.2%} of order value)"),
    ("Securities Transaction Tax (delivery)", f"{cs.stt_delivery:.1%} on buy and sell"),
    ("STT (intraday)", f"{cs.stt_intraday_sell:.3%} on sell"),
    ("NSE transaction charge", f"{cs.exchange_txn:.5%} of turnover"),
    ("SEBI fee", "₹10 per crore"),
    ("Stamp duty", f"{cs.stamp_delivery_buy:.3%} on delivery buys, {cs.stamp_intraday_buy:.3%} on intraday buys"),
    ("GST", f"{cs.gst:.0%} on brokerage + exchange + SEBI charges"),
    ("DP charge", f"₹{cs.dp_charge_per_sell:g} per delivery sell"),
    ("Slippage", f"{cs.slippage_bps:g} basis points per side by default (sidebar)"),
], columns=["Component", "Rate"]), hide_index=True, width="stretch")

st.markdown("## Pattern validation method")
st.markdown("""
- **Eleven rule-based patterns**: Doji, Hammer, Shooting Star, Bullish/Bearish Engulfing (original definitions, unchanged), plus Bullish/Bearish Marubozu, Morning/Evening Star and Three White Soldiers/Black Crows. Each uses only the signal session and up to two sessions before it.
- **Entry** at the next session's open (default); **outcome** = close *h* sessions after the signal ÷ entry − 1, for h = 1, 3, 5, 10.
- **Directional return** flips the sign for bearish patterns; **net** subtracts a round-trip cost; **adverse excursion** is the worst intraday move against the pattern before the horizon ends.
- **Benchmark**: the stock's own base rate (share of up/down moves over the same horizon on any day).
- **Uncertainty**: Wilson 95% intervals for hit rates, t-intervals for mean returns, exact binomial tests vs base rate, Benjamini–Hochberg q-values across all pattern × horizon tests. Results with fewer than 20 cases are flagged.
- **Context** (stock trend and volatility, NIFTY regime, 63-session rolling correlation with NIFTY) is measured with data up to the signal date only.
- **Out-of-sample**: each stock's history is split chronologically; the edge is compared between the earlier and later periods.
- **Caveat**: events closer than the horizon share price moves, so they are not independent and intervals are somewhat optimistic.
""")
st.markdown("## Correlation & regime method")
st.markdown("""
- Daily simple returns per instrument on its own trading days, aligned by date **without forward-filling**; each coefficient uses pairwise-complete observations and reports n.
- Pearson (linear) or Spearman (rank) correlation; Fisher-z 95% intervals and p-values; beta = cov(stock, NIFTY) / var(NIFTY).
- Rolling correlation and beta over a trailing window (21–252 sessions).
- **Regimes from NIFTY 50**: Bullish (close above 200-session average), Bearish (below), High volatility (20-session volatility above the 75th percentile of its own history to date; overrides trend).
- Regime-specific correlations are compared with the full-period figure using a Fisher z-test (approximate, because the samples overlap and returns cluster).
- **Diversification**: equal-weight portfolio volatility vs average stock volatility; scenarios swap in each regime's correlation matrix while holding volatilities fixed.
- **Interest-rate futures, calendar spreads, butterflies**: analysed only from contract prices the user uploads (CSV). No such data is bundled, and nothing is shown without it.
- Correlation measures co-movement, **not causation**.
""")
st.markdown("## Important limitations")
st.markdown("""
- Backtests describe one historical path; they do not predict future returns.
- The instrument universe is today's large-caps (survivorship bias).
- Intraday, multi-asset portfolio and historical options strategies are documented but not enabled (see Strategy Lab → Strategy catalogue).
- Rare candlestick patterns (stars, soldiers/crows) occur only a handful of times per stock, so their statistics are highly uncertain even when pooled.
- No interest-rate-futures or spread data is included; that analysis requires uploading genuine contract prices.
- Option values are theoretical (constant volatility, European exercise); real NSE stock options are physically settled and trade with bid–ask spreads.
- Capital-gains tax, margin, borrow costs and corporate-action cash flows are not modelled separately.
- Synthetic demo data exists only so the app works offline; it is never a basis for conclusions.
""")

