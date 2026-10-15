# Business Outcomes Report

Generated 2026-10-15 13:55 by `scripts/generate_report.py --mode cache`. Period requested 2021-10-15 → 2026-10-15; capital ₹1,000,000; next-open execution; long-only; published delivery cost schedule + 5 bps slippage; risk-free 5.50%; default parameters.

## Results by instrument and strategy

| Instrument    | Data   | Strategy                                          | Net return   | CAGR   |   Sharpe | Max DD   |   Trades |   Costs (₹) | OOS Sharpe   | Classification                 |
|:--------------|:-------|:--------------------------------------------------|:-------------|:-------|---------:|:---------|---------:|------------:|:-------------|:-------------------------------|
| ^NSEI         | CACHED | SMA Crossover                                     | +8.9%        | +1.7%  |    -0.33 | -16.0%   |       12 |      38,739 | -1.02        | Weak under current assumptions |
| ^NSEI         | CACHED | Bollinger Band Mean Reversion                     | +20.2%       | +3.7%  |    -0.23 | -9.8%    |       14 |      51,353 | -0.17        | Weak under current assumptions |
| ^NSEI         | CACHED | Donchian Breakout                                 | -0.3%        | -0.1%  |    -0.52 | -20.2%   |       15 |      50,070 | -1.79        | Weak under current assumptions |
| ^NSEI         | CACHED | RSI Divergence                                    | +20.7%       | +3.8%  |    -0.11 | -15.5%   |       21 |      76,975 | -0.48        | Weak under current assumptions |
| ^NSEI         | CACHED | Gap Fill (open-to-close)                          | -25.3%       | -5.7%  |    -2.2  | -25.9%   |      203 |     251,046 | -2.95        | Weak under current assumptions |
| ^NSEI         | CACHED | Candlestick Reversal (Hammer / Bullish Engulfing) | -7.5%        | -1.6%  |    -1.04 | -14.5%   |       46 |     144,265 | -0.96        | Weak under current assumptions |
| ^NSEI         | CACHED | Buy & Hold (benchmark)                            | +23.1%       | +4.3%  |    -0.02 | -17.7%   |        1 |       3,555 | —            | benchmark                      |
| RELIANCE.NS   | CACHED | SMA Crossover                                     | -6.7%        | -1.4%  |    -0.42 | -25.3%   |       16 |      48,863 | -0.51        | Weak under current assumptions |
| RELIANCE.NS   | CACHED | Bollinger Band Mean Reversion                     | +29.6%       | +5.3%  |     0.02 | -12.5%   |       14 |      53,458 | -0.37        | Weak under current assumptions |
| RELIANCE.NS   | CACHED | Donchian Breakout                                 | -22.5%       | -5.0%  |    -0.68 | -27.9%   |       13 |      36,395 | -1.18        | Weak under current assumptions |
| RELIANCE.NS   | CACHED | RSI Divergence                                    | +0.2%        | +0.0%  |    -0.29 | -21.8%   |       23 |      78,562 | -0.10        | Weak under current assumptions |
| RELIANCE.NS   | CACHED | Gap Fill (open-to-close)                          | -46.1%       | -11.6% |    -1.62 | -49.6%   |      282 |     327,371 | -1.60        | Weak under current assumptions |
| RELIANCE.NS   | CACHED | Candlestick Reversal (Hammer / Bullish Engulfing) | -23.4%       | -5.2%  |    -1.14 | -30.7%   |       43 |     126,291 | -1.52        | Weak under current assumptions |
| RELIANCE.NS   | CACHED | Buy & Hold (benchmark)                            | -1.9%        | -0.4%  |    -0.15 | -27.1%   |        1 |       3,205 | —            | benchmark                      |
| ITC.NS        | CACHED | SMA Crossover                                     | +74.9%       | +11.9% |     0.51 | -19.4%   |        7 |      39,772 | -1.55        | Weak under current assumptions |
| ITC.NS        | CACHED | Bollinger Band Mean Reversion                     | +5.5%        | +1.1%  |    -0.58 | -12.7%   |       10 |      33,477 | -1.14        | Weak under current assumptions |
| ITC.NS        | CACHED | Donchian Breakout                                 | +49.7%       | +8.4%  |     0.26 | -39.8%   |       10 |      60,012 | -0.93        | Weak under current assumptions |
| ITC.NS        | CACHED | RSI Divergence                                    | +31.5%       | +5.6%  |     0.07 | -23.5%   |       17 |      72,988 | -0.74        | Weak under current assumptions |
| ITC.NS        | CACHED | Gap Fill (open-to-close)                          | -9.6%        | -2.0%  |    -0.88 | -22.0%   |      163 |     236,384 | -1.56        | Weak under current assumptions |
| ITC.NS        | CACHED | Candlestick Reversal (Hammer / Bullish Engulfing) | +1.3%        | +0.3%  |    -0.54 | -13.2%   |       40 |     133,044 | -1.12        | Weak under current assumptions |
| ITC.NS        | CACHED | Buy & Hold (benchmark)                            | +28.4%       | +5.1%  |     0.08 | -45.0%   |        1 |       3,673 | —            | benchmark                      |
| HDFCBANK.NS   | CACHED | SMA Crossover                                     | -28.8%       | -6.6%  |    -0.77 | -36.6%   |       16 |      42,592 | -1.00        | Weak under current assumptions |
| HDFCBANK.NS   | CACHED | Bollinger Band Mean Reversion                     | +15.2%       | +2.9%  |    -0.25 | -16.8%   |       13 |      49,635 | -0.63        | Weak under current assumptions |
| HDFCBANK.NS   | CACHED | Donchian Breakout                                 | -18.0%       | -3.9%  |    -0.58 | -32.4%   |       15 |      38,182 | -1.16        | Weak under current assumptions |
| HDFCBANK.NS   | CACHED | RSI Divergence                                    | -4.5%        | -0.9%  |    -0.39 | -25.8%   |       21 |      75,044 | -0.25        | Weak under current assumptions |
| HDFCBANK.NS   | CACHED | Gap Fill (open-to-close)                          | +1.4%        | +0.3%  |    -0.52 | -12.6%   |      363 |     518,114 | -1.83        | Weak under current assumptions |
| HDFCBANK.NS   | CACHED | Candlestick Reversal (Hammer / Bullish Engulfing) | -21.0%       | -4.6%  |    -0.71 | -35.1%   |       62 |     201,138 | -0.56        | Weak under current assumptions |
| HDFCBANK.NS   | CACHED | Buy & Hold (benchmark)                            | -7.7%        | -1.6%  |    -0.23 | -31.0%   |        1 |       3,117 | —            | benchmark                      |
| BHARTIARTL.NS | CACHED | SMA Crossover                                     | +83.0%       | +12.9% |     0.49 | -22.3%   |       11 |      50,175 | 0.30         | Requires more validation       |
| BHARTIARTL.NS | CACHED | Bollinger Band Mean Reversion                     | +8.3%        | +1.6%  |    -0.66 | -7.7%    |        7 |      24,301 | 0.15         | Requires more validation       |
| BHARTIARTL.NS | CACHED | Donchian Breakout                                 | +62.2%       | +10.2% |     0.34 | -25.3%   |       12 |      49,296 | 0.37         | Requires more validation       |
| BHARTIARTL.NS | CACHED | RSI Divergence                                    | -15.7%       | -3.4%  |    -0.71 | -27.3%   |       22 |      64,591 | 0.16         | Weak under current assumptions |
| BHARTIARTL.NS | CACHED | Gap Fill (open-to-close)                          | +23.4%       | +4.3%  |    -0.08 | -18.1%   |      274 |     434,944 | -1.17        | Weak under current assumptions |
| BHARTIARTL.NS | CACHED | Candlestick Reversal (Hammer / Bullish Engulfing) | +8.9%        | +1.7%  |    -0.27 | -15.1%   |       61 |     212,449 | -0.16        | Weak under current assumptions |
| BHARTIARTL.NS | CACHED | Buy & Hold (benchmark)                            | +175.1%      | +22.5% |     0.81 | -18.8%   |        1 |       5,932 | —            | benchmark                      |
| TCS.NS        | CACHED | SMA Crossover                                     | -25.9%       | -5.8%  |    -0.73 | -33.8%   |       15 |      41,360 | -0.72        | Weak under current assumptions |
| TCS.NS        | CACHED | Bollinger Band Mean Reversion                     | -7.5%        | -1.6%  |    -0.6  | -27.1%   |       13 |      41,200 | -0.01        | Weak under current assumptions |
| TCS.NS        | CACHED | Donchian Breakout                                 | -18.4%       | -4.0%  |    -0.61 | -31.6%   |       15 |      45,762 | -1.17        | Weak under current assumptions |
| TCS.NS        | CACHED | RSI Divergence                                    | +7.5%        | +1.5%  |    -0.13 | -41.3%   |       23 |      89,748 | -0.32        | Weak under current assumptions |
| TCS.NS        | CACHED | Gap Fill (open-to-close)                          | -33.0%       | -7.7%  |    -1.32 | -41.3%   |      298 |     395,314 | -1.17        | Weak under current assumptions |
| TCS.NS        | CACHED | Candlestick Reversal (Hammer / Bullish Engulfing) | -22.4%       | -5.0%  |    -0.85 | -35.8%   |       48 |     126,003 | -0.68        | Weak under current assumptions |
| TCS.NS        | CACHED | Buy & Hold (benchmark)                            | -26.0%       | -5.9%  |    -0.4  | -53.4%   |        1 |       2,837 | —            | benchmark                      |
| INFY.NS       | CACHED | SMA Crossover                                     | -21.6%       | -4.8%  |    -0.53 | -38.7%   |       13 |      33,612 | -0.70        | Weak under current assumptions |
| INFY.NS       | CACHED | Bollinger Band Mean Reversion                     | -34.3%       | -8.1%  |    -1.04 | -40.0%   |       14 |      38,133 | -0.47        | Weak under current assumptions |
| INFY.NS       | CACHED | Donchian Breakout                                 | -9.2%        | -1.9%  |    -0.34 | -41.1%   |       14 |      49,883 | -0.49        | Weak under current assumptions |
| INFY.NS       | CACHED | RSI Divergence                                    | -49.6%       | -12.8% |    -0.89 | -58.2%   |       21 |      59,211 | -1.14        | Weak under current assumptions |
| INFY.NS       | CACHED | Gap Fill (open-to-close)                          | -60.9%       | -17.2% |    -2.35 | -61.7%   |      334 |     322,017 | -1.34        | Weak under current assumptions |
| INFY.NS       | CACHED | Candlestick Reversal (Hammer / Bullish Engulfing) | -16.0%       | -3.4%  |    -0.73 | -26.1%   |       50 |     151,967 | -0.47        | Weak under current assumptions |
| INFY.NS       | CACHED | Buy & Hold (benchmark)                            | -29.9%       | -6.9%  |    -0.36 | -48.1%   |        1 |       2,776 | —            | benchmark                      |
| SBIN.NS       | CACHED | SMA Crossover                                     | +41.0%       | +7.1%  |     0.18 | -29.2%   |       10 |      32,468 | 0.25         | Requires more validation       |
| SBIN.NS       | CACHED | Bollinger Band Mean Reversion                     | +21.2%       | +3.9%  |    -0.1  | -12.0%   |       15 |      58,216 | -0.78        | Weak under current assumptions |
| SBIN.NS       | CACHED | Donchian Breakout                                 | +15.0%       | +2.8%  |    -0.04 | -23.4%   |       16 |      52,817 | 0.05         | Requires more validation       |
| SBIN.NS       | CACHED | RSI Divergence                                    | +18.2%       | +3.4%  |    -0.05 | -28.1%   |       20 |      87,374 | -0.58        | Weak under current assumptions |
| SBIN.NS       | CACHED | Gap Fill (open-to-close)                          | -17.0%       | -3.7%  |    -0.78 | -29.4%   |      194 |     262,181 | -1.96        | Weak under current assumptions |
| SBIN.NS       | CACHED | Candlestick Reversal (Hammer / Bullish Engulfing) | -19.6%       | -4.3%  |    -0.76 | -27.0%   |       48 |     146,045 | -0.88        | Weak under current assumptions |
| SBIN.NS       | CACHED | Buy & Hold (benchmark)                            | +109.3%      | +15.9% |     0.51 | -23.9%   |        1 |       4,918 | —            | benchmark                      |
| ^GSPC         | CACHED | SMA Crossover                                     | +6.9%        | +1.3%  |    -0.32 | -29.6%   |       12 |      33,214 | 0.65         | Requires more validation       |
| ^GSPC         | CACHED | Bollinger Band Mean Reversion                     | +39.4%       | +6.9%  |     0.17 | -9.5%    |       15 |      55,978 | -0.28        | Weak under current assumptions |
| ^GSPC         | CACHED | Donchian Breakout                                 | +34.2%       | +6.1%  |     0.09 | -12.8%   |       15 |      53,031 | 0.45         | Requires more validation       |
| ^GSPC         | CACHED | RSI Divergence                                    | +13.2%       | +2.5%  |    -0.17 | -20.5%   |       18 |      64,664 | -0.09        | Weak under current assumptions |
| ^GSPC         | CACHED | Gap Fill (open-to-close)                          | -50.7%       | -13.2% |    -2.31 | -51.0%   |      240 |     222,681 | -3.97        | Weak under current assumptions |
| ^GSPC         | CACHED | Candlestick Reversal (Hammer / Bullish Engulfing) | -14.2%       | -3.0%  |    -0.94 | -26.8%   |       58 |     157,408 | 0.11         | Weak under current assumptions |
| ^GSPC         | CACHED | Buy & Hold (benchmark)                            | +72.2%       | +11.5% |     0.41 | -25.4%   |        1 |       4,341 | —            | benchmark                      |

## How to read this

- *Classification* applies the transparent rules on the Business Outcomes page (net result, buy-and-hold comparison, Sharpe ≥ 0.5, drawdown ≤ 25%, walk-forward out-of-sample Sharpe > 0 and ≥ 50% of in-sample, costs ≤ 30% of gross profit, ≥ 10 trades).
- Synthetic rows are never classified.
- Historical results are not forecasts; see the Methodology page for limitations.
