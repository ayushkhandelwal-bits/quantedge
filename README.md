<p align="left"><img src="assets/quantedge_logo.svg" alt="QuantEdge" height="40"></p>

# QuantEdge – Quantitative Trading & Derivatives Analytics

By **Ayush Khandelwal**, BITS Pilani · [Email](mailto:ayushkhandelwal.connect@gmail.com) · [LinkedIn](https://www.linkedin.com/in/ayushjhanginiya/)

An MBA Business Analytics project that turns free historical market data into evidence about trading strategies:
returns, risk, robustness, transaction costs, derivatives pricing and business outcomes. It runs locally, costs nothing and
works offline.

**Core question:** which trading strategies offer the most attractive balance of return, risk, robustness and transaction
costs on historical data? The dashboard is built to answer that question honestly. It does not promise profits.

---

## 1. Quick start

Requirements: Python 3.10+ (tested on 3.13) and internet access for the first data download. No API keys and no paid services.

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate

# 2. Install dependencies (all free / open source)
pip install -r requirements.txt

# 3. (Recommended) download ~5 years of daily data for the 9-instrument universe
python scripts/download_data.py

# 4. Launch the dashboard
streamlit run app.py                 # opens http://localhost:8501
```

Skipping step 3 is fine. The app downloads data on demand and caches it in `data/raw/`. If Yahoo Finance cannot be
reached and nothing is cached, it falls back to **synthetic demo data**, which is clearly labelled on every page.

### Run the tests

```bash
python -m pytest -q
```

### Regenerate the business-outcomes report

```bash
python scripts/generate_report.py            # uses stored real data; synthetic rows are flagged
```

---

## 2. Data sources

| Data | Source | Cost | Status in this build |
|---|---|---|---|
| Daily OHLCV for `^NSEI`, `RELIANCE.NS`, `ITC.NS`, `HDFCBANK.NS`, `BHARTIARTL.NS`, `TCS.NS`, `INFY.NS`, `SBIN.NS`, `^GSPC` | Yahoo Finance via `yfinance` (split- and dividend-adjusted) | Free | Implemented with retries, back-off, rate-limit handling, CSV cache and metadata. **Not live-tested in the build environment** (Yahoo was blocked there); the path is unit-tested with simulated responses. |
| Risk-free rate | User-editable assumption. The default of 5.50% is the RBI policy repo rate from the October 2026 MPC, per press reports. | Free | Shown as an assumption; verify at <https://dbie.rbi.org.in/>. |
| Historical options prices | NSE | n/a | **Not used.** No reliable free historical options feed exists, so historical options backtesting is disabled. |
| Interest-rate futures (STIR), calendar spreads, butterflies | **User upload only** (CSV) | Free | No free multi-year contract-level history exists, so none is bundled; the analysis activates only with uploaded data. |
| Offline demo data | Deterministic synthetic generator (`src/data_sources.synthetic_ohlcv`) | Free | Always available; labelled **SYNTHETIC** everywhere. |

Data status labels:

* **LIVE**: downloaded in this session.
* **CACHED**: real data read from `data/raw/`.
* **SYNTHETIC**: simulated prices, used for demonstration only.

See `docs/DATA_GUIDE.md` for the data dictionary and the cleaning rules.

---

## 3. What the dashboard contains

| Page | What it answers |
|---|---|
| **Executive Overview** | What did the strategy achieve, how much risk did it take, and is it worth investigating? Shows KPIs, an equity curve against buy-and-hold and the index, a return-vs-risk chart, recent trades and a classification. |
| **Market Explorer & Data** | Dataset overview and preview, price and indicators, data dictionary, data-quality checks with the cleaning log, a correlation heatmap and a searchable glossary of 47 terms. |
| **Correlation & Regimes** | Correlation heatmap with sample sizes, correlation and beta versus NIFTY with 95% intervals, rolling correlation and beta, correlations in bullish, bearish and high-volatility regimes, a diversification analysis, and a CSV upload for interest-rate futures calendar spreads and butterflies. |
| **Trading Strategy Lab** | Candlestick chart with buy/sell/exit markers and indicator overlays, signal history and trade log (CSV download). Also rule-based candlestick pattern analysis with forward returns compared against base rates, and a strategy catalogue. |
| **Pattern Validation** | 11 rule-based candlestick patterns tested across several stocks at 1/3/5/10-session horizons. Shows hit rate vs base rate with confidence intervals, p- and q-values, average and after-cost returns, adverse excursion and return/risk. Includes breakdowns by stock, market regime and correlation environment, a chronological out-of-sample check, an annotated chart and a filterable event table. |
| **Backtesting & Performance** | Comparison table of all strategies under identical assumptions. Equity and drawdown curves, monthly-return heatmap, return distributions, cost impact, and run history stored in SQLite. |
| **Risk & Robustness** | Rolling walk-forward validation (in-sample vs out-of-sample), parameter-sensitivity heatmap, cost stress tests (0×–3×), next-open vs same-close execution, market regimes, and the limits of the evidence. |
| **Derivatives Analytics** | Black–Scholes–Merton pricing, Greeks, implied-volatility solver, payoff builder for 8 preset strategies with editable legs, and a scenario heatmap. All values are theoretical. |
| **Business Outcomes** | Gross → net P&L waterfall, risk-adjusted ranking, capital and loss scenarios, a transparent classification with editable thresholds, and a downloadable executive summary. |
| **Methodology & Guide** | Process-flow diagram, formulas, assumptions, cost schedule, pattern and correlation methods, and limitations. |

### Strategies

| Strategy | Status | Notes |
|---|---|---|
| SMA Crossover | ✅ | Trend following |
| Bollinger Band Mean Reversion | ✅ | Mean reversion with RSI confirmation |
| Donchian Breakout | ✅ | Channel breakout |
| RSI Divergence | ✅ | Momentum reversal |
| Gap Fill | ✅ | Executed open-to-close on the gap day with intraday costs |
| Candlestick Reversal (Hammer / Bullish Engulfing) | ✅ | Pattern-based, fixed holding period |
| Buy & Hold | ✅ | Benchmark |
| VWAP Mean Reversion, Opening Range Breakout | ⛔ | Need multi-year intraday data, which is not freely available |
| Cross-Sectional Momentum, Pairs Trading | ⛔ | Need a multi-asset / two-leg portfolio engine, which is not built |
| Weekly Short Straddle | ⛔ | Needs genuine historical option prices; model-priced backtests would manufacture returns |

Unavailable strategies appear in the catalogue with the reason they are disabled. They are never shown as working selectors.

---

## 4. Project structure

```
app.py                     Streamlit entry point (navigation, sidebar, QuantEdge logo)
assets/                    QuantEdge logo and icon (SVG)
config.py                  Universe, paths, defaults, risk-free assumption
requirements.txt
src/
  reference/               Third-party MIT-licensed modules (indicators, strategy signals, metrics, Black-76); see its LICENSE
  data_sources.py          yfinance download, retries, cache, synthetic fallback, connectivity probe
  data_validation.py       Cleaning with an auditable report and anomaly flags
  indicators.py            pandas wrappers around src/reference indicators (+ Donchian, volatility)
  candlestick_patterns.py  Rule-based patterns, forward returns, base-rate comparison
  strategies.py            Strategy registry (metadata, parameters, availability)
  backtester.py            Next-open execution, per-side costs, slippage, whole shares
  transaction_costs.py     Configurable Indian equity cost schedule
  performance_metrics.py   Metrics with explicit conventions; n/a instead of ±inf
  walk_forward.py          Walk-forward, sensitivity, cost stress, regimes
  options_pricing.py       BSM price, Greeks, IV, payoffs (+ reference Black-76)
  pattern_validation.py    Multi-stock pattern statistics, intervals, tests, regimes, out-of-sample split
  correlation.py           Correlation, Fisher intervals, rolling beta, regime correlations, diversification
  spreads.py               User-uploaded futures contracts: calendar spreads and butterflies
  business_outcomes.py     Gross/net, classification rules, scenarios, interpretation
  analysis.py, storage.py, glossary.py, ui.py
views/                     One file per dashboard page (10); named views/ so Streamlit does not switch to its legacy multipage mode
tests/                     pytest suite (data, analytics, leakage, patterns, correlation, options, business rules)
scripts/                   download_data.py, generate_report.py
data/raw | processed | sample | database
docs/                      DATA_GUIDE.md, METHODOLOGY.md, VERIFICATION.md, business_outcomes_report.md
```

---

## 5. Key assumptions (details in the Methodology page)

* **Execution timing.** A signal is decided at the close and filled at the **next session's open**. Fills are in whole
  shares, with 100% of equity in one position.
* **Costs.** Per-side charges follow the published Zerodha schedule (checked October 2026): STT 0.1%, NSE 0.00307%,
  SEBI ₹10/crore, stamp duty 0.015% on buys, GST 18%, DP charge ₹15.34 per sell. Slippage defaults to 5 bps per side.
* **Shorting** is off by default.
* **Open positions** are closed at the final close.
* **Metrics** are computed on daily returns and annualised with 252 sessions. CAGR uses calendar time. Undefined metrics
  are shown as n/a, never as ∞.
* **Indices** are treated as a proxy for an index fund.

## 6. Limitations

* Results are historical and do not forecast future performance.
* The universe has survivorship bias.
* Capital-gains tax is not modelled.
* Option values are theoretical.
* Intraday, portfolio and options-backtest strategies are not enabled.
* Rare candlestick patterns occur only a few times per stock, so their statistics are very uncertain.
* No interest-rate-futures data is included; that analysis needs uploaded contract prices.
* Synthetic data is for demonstration only.

## 7. Third-party code, data and licences

* **`src/reference/`** contains third-party Python modules used under the **MIT License**: technical indicators,
  five strategy signal functions, several performance-metric functions and a Black-76 option model. They are included
  with import-path changes only. The copyright and permission notice that the licence requires is kept in
  `src/reference/LICENSE`. Everything else in this repository was written for this project.
* **Libraries:** Streamlit, pandas, NumPy, SciPy, Plotly, yfinance, requests, tabulate and pytest, each under its own
  open-source licence.
* **Market data:** retrieved from Yahoo Finance through the open-source `yfinance` library for personal and educational
  use. Downloaded data is stored locally and **excluded from version control** (see `.gitignore`); each user downloads
  their own copy with `python scripts/download_data.py`.

## 8. Publishing notes

* No API keys or secrets are needed. `.env` files and `.streamlit/secrets.toml` are ignored by Git in case you add
  any later.
* `data/raw/`, `data/processed/` and `data/database/` are ignored by Git. `data/sample/` holds only clearly labelled
  synthetic files.

*Educational analysis only; not investment advice.*
