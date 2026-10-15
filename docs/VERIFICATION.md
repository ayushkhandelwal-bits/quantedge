# Verification and Testing

This document records how the application was tested and what has and has not been verified.

## Automated tests

Run with `python -m pytest -q`. **65 tests** cover:

* **Data.**
  * yfinance download standardisation, local caching and cache reuse.
  * Retries with back-off, rate-limit handling, and a fast failure when offline.
  * Fallback order: cache first, then labelled synthetic data.
  * Deterministic synthetic data.
  * The cleaning log: sorting, duplicates, missing and invalid prices.
* **Leakage.**
  * Indicators, candlestick patterns, every enabled strategy, regimes and pattern events stay unchanged when future
    rows are appended.
  * Forward returns start after the signal.
* **Backtesting.**
  * Next-open execution arithmetic.
  * Exact cost and slippage accounting.
  * The shorting switch.
  * Forced exit at the end of the data.
  * Gap-strategy open-to-close execution.
  * Reproducibility.
* **Costs.** Order charges match the published schedule (STT, exchange, SEBI, stamp duty, GST, DP).
* **Metrics.**
  * Known values.
  * Sharpe matches its definition.
  * Edge cases return "n/a" instead of ∞.
  * Chronological, non-overlapping walk-forward windows.
* **Patterns.**
  * Hand-built candles for all 11 patterns.
  * The five original definitions are unchanged.
  * Entry, cost and adverse-excursion arithmetic.
  * Bearish sign handling.
  * The chronological out-of-sample split.
  * Wilson intervals and Benjamini–Hochberg q-values.
* **Correlation.**
  * Fisher confidence intervals and difference tests.
  * Pairwise date alignment without forward-filling.
  * Regime splits.
  * Diversification ratio: √4 for four independent assets and 1 at perfect correlation.
* **Spreads.** Calendar and butterfly formulas, and CSV validation.
* **Options.**
  * Black–Scholes against a textbook value, and put–call parity.
  * Black-76 agreement.
  * Greeks against finite differences.
  * Implied-volatility round trip.
  * Payoff shapes.
* **Business rules.** The classification logic.

## Dashboard checks

* All 10 pages were run headlessly with Streamlit's `AppTest` for every enabled strategy and several setting
  combinations: shorting, same-close fills, costs off, S&P 500, short date ranges, Spearman correlation, close-entry
  patterns, regime and correlation splits, and rare-pattern selections. **0 exceptions.**
* The running app was reviewed in a headless browser, including the CSV-upload flow for calendar spreads and
  butterflies, which was tested with a clearly labelled test file.

## Real-data run (Windows, Python 3.13)

* A fresh install from the README completed, and all tests passed.
* `python scripts/download_data.py` downloaded all 9 instruments from Yahoo Finance.
* The dashboard ran on the cached data, with every page showing the **CACHED** badge.
* `python scripts/generate_report.py` produced `docs/business_outcomes_report.md` from real data, with 0 synthetic
  instruments.
* Split and bonus adjustment was checked on the Data-quality tab: HDFC Bank and Reliance show no ~−50% overnight gaps.

## Not verified / out of scope

* Historical options backtesting, intraday strategies and multi-asset portfolio strategies are disabled; they need data
  or engines that are not freely available.
* No interest-rate-futures data is bundled. The spread and butterfly analysis runs only on uploaded contract prices.
* NSE derivatives reports and RBI DBIE are not integrated. The risk-free rate is an editable assumption.
* All results describe historical data and are not forecasts.
