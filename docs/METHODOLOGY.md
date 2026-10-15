# Methodology

## Workflow

Data collection → validation → indicators → signals → backtest (next-open fills) → costs → performance metrics → walk-forward validation → business interpretation.

## Leakage controls

- Indicators at date *t* use data up to the close of *t* only (tested: values unchanged when future rows are appended).
- Strategy targets decided at the close of *t* are filled at the open of *t+1*; Gap Fill uses only the open of *t* and the previous close, and trades open→close of *t*.
- Candlestick forward returns start at the close of the signal day.
- Walk-forward: parameters are chosen on the training window only and applied to the next, non-overlapping test window, which starts flat.

## Performance metrics

| Metric | Definition | Edge cases |
|---|---|---|
| Total return | V_end / V_start − 1 | n/a if fewer than 2 points |
| CAGR | (V_end/V_start)^(365.25/days) − 1 | n/a if non-positive values |
| Volatility | stdev(daily returns, ddof=1) × √252 | |
| Sharpe | (mean(r) − r_f/252) / stdev(r) × √252 | n/a if zero volatility or < 20 sessions |
| Sortino | mean(r − r_f/252) / downside deviation × √252 | n/a if no downside |
| Max drawdown | max over t of 1 − V_t / max(V_0..V_t) | |
| Win rate | net P&L > 0 / completed trades | n/a with no trades |
| Profit factor | Σ winning P&L / Σ |losing P&L| | n/a with no losing trades |
| Expectancy | win rate × avg win − loss rate × |avg loss| | |
| Gross P&L | Σ (exit ref − entry ref) × qty × direction | before slippage and charges |
| Net P&L | Gross − charges − slippage | equals the change in equity |

## Transaction costs (Rates per zerodha.com/charges (checked Oct 2026). Approximations; verify before relying on them.)

Delivery: brokerage ₹0; STT 0.1% each side; NSE 0.00307%; SEBI ₹10/crore; stamp 0.015% on buys; GST 18% on brokerage+exchange+SEBI; DP ₹15.34 per sell. Intraday (Gap Fill): brokerage min(₹20, 0.03%); STT 0.025% on sells; stamp 0.003% on buys. Slippage 5 bps per side (configurable).

## Options

Black–Scholes–Merton with continuous dividend yield; Greeks analytic (theta per calendar day, vega per vol point, rho per 1% rate); implied volatility by Brent's method within [0.1%, 500%]. Model values are theoretical. Historical options backtesting is disabled without real contract prices.

## Classification (Business Outcomes)

Weak if net return ≤ 0 or walk-forward OOS Sharpe ≤ 0; Worth further investigation only if every criterion passes (net > 0, beats buy-and-hold, Sharpe ≥ 0.5, max DD ≤ 25%, OOS Sharpe > 0, OOS/IS ≥ 0.5, costs ≤ 30% of gross profit, ≥ 10 trades); otherwise Requires more validation; synthetic data is never classified. Thresholds are editable in the app.

## Limitations

Single historical path; survivorship bias; parameter-selection bias reduced but not removed by walk-forward; fixed slippage; no capital-gains tax, margin or borrow costs; indices treated as fund proxies; option values theoretical; regime change.

## Pattern validation (Pattern Validation page)

Eleven rule-based patterns (five original definitions unchanged; Bullish/Bearish Marubozu, Morning/Evening Star, Three White Soldiers/Black Crows added) using only the signal session and up to two before it. Entry at the next open by default; outcomes at 1/3/5/10 sessions; directional, after-cost and adverse-excursion measures; hit rates compared with each stock's base rate using Wilson intervals, exact binomial tests and Benjamini–Hochberg q-values; t-intervals for mean returns; breakdowns by stock, NIFTY regime, stock trend/volatility and 63-session correlation with NIFTY (all measured as of the signal date); chronological in-sample vs out-of-sample comparison. Overlapping events make intervals somewhat optimistic.

## Correlation & regime dynamics (Correlation & Regimes page)

Daily returns aligned without forward-filling; pairwise-complete Pearson or Spearman correlations with n; Fisher-z intervals and p-values; beta to NIFTY; rolling correlation and beta on trailing windows; NIFTY regimes (Bullish/Bearish by 200-session average; High volatility when 20-session volatility exceeds the 75th percentile of its history to date); Fisher z-tests of regime vs all-days correlation; equal-weight portfolio volatility and diversification ratio, including scenarios that apply each regime's correlation matrix. Calendar spreads (near − far) and butterflies (front − 2 × middle + back) are computed only from user-uploaded contract prices. Correlation is not causation.

