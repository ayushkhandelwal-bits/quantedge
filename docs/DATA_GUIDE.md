# Data Guide

## Sources

- **Yahoo Finance via `yfinance`** – daily OHLCV, adjusted for splits and dividends (`auto_adjust=True`). Free; no key. Rate limits and outages are handled with 3 attempts, exponential back-off (longer on HTTP 429), and a 4-second connectivity probe so offline sessions fail fast.
- **Risk-free rate** – Assumption: RBI policy repo rate 5.50% (Oct 2026 MPC, per press reports). Editable; verify at dbie.rbi.org.in.
- **Synthetic demo data** – regime-switching geometric Brownian motion with Student-t shocks, seeded by the symbol name (deterministic). Overnight gaps and intraday moves are drawn independently so the series contains no built-in gap-fill or trend edge. Three issues (missing volume, zero volume, duplicate row) are deliberately injected to exercise the data-quality checks. `data/sample/` holds 2021–2025 copies for inspection.

## Storage

| Folder | Contents |
|---|---|
| `data/raw/` | `<symbol>.csv` downloaded OHLCV + `<symbol>.meta.json` (source, download time, requested range) |
| `data/processed/` | reserved for derived exports |
| `data/sample/` | SYNTHETIC demo CSVs (filenames end in `_SYNTHETIC`) |
| `data/database/results.db` | SQLite history of backtest runs (inputs, data status, metrics) |

## Instrument universe

| Symbol | Name | Market | Description |
|---|---|---|---|
| `^NSEI` | NIFTY 50 | NSE index | NSE benchmark index of 50 large Indian companies |
| `RELIANCE.NS` | Reliance Industries | NSE equity | Energy, retail and telecom conglomerate |
| `ITC.NS` | ITC | NSE equity | FMCG, hotels, paperboards and agri-business |
| `HDFCBANK.NS` | HDFC Bank | NSE equity | Largest Indian private-sector bank |
| `BHARTIARTL.NS` | Bharti Airtel | NSE equity | Telecommunications services |
| `TCS.NS` | Tata Consultancy Services | NSE equity | IT services and consulting |
| `INFY.NS` | Infosys | NSE equity | IT services and consulting |
| `SBIN.NS` | State Bank of India | NSE equity | Largest Indian public-sector bank |
| `^GSPC` | S&P 500 | US index | US benchmark index of 500 large companies |

## Data dictionary

| Field | Type | Meaning | Calculation | Inputs |
|---|---|---|---|---|
| Date | Raw | Trading session date (exchange local date). | As supplied by the source; sorted ascending, duplicates removed. | — |
| Open | Raw | First traded price of the session. | Adjusted for splits and dividends (yfinance auto_adjust). | — |
| High | Raw | Highest traded price during the session. | Adjusted, as above. | — |
| Low | Raw | Lowest traded price during the session. | Adjusted, as above. | — |
| Close | Raw | Last traded (closing) price of the session. | Adjusted, as above. | — |
| Volume | Raw | Number of shares (or index units) traded. Often zero for indices on Yahoo Finance. | As supplied. | — |
| Return | Derived | Percentage price change from the previous session. | Close(t) ÷ Close(t−1) − 1 | Close |
| LogReturn | Derived | Logarithmic price change; adds up neatly over time. | ln(Close(t) ÷ Close(t−1)) | Close |
| SMA20 / SMA50 | Derived | Average closing price over the last 20 / 50 sessions. | Mean of the last n closes (blank until n sessions exist). | Close |
| EMA20 | Derived | Moving average that gives more weight to recent prices. | EMA(t) = k·Close(t) + (1−k)·EMA(t−1), k = 2/(n+1); seeded with the SMA. | Close |
| RSI14 | Derived | Momentum indicator from 0 to 100; above 70 often called 'overbought', below 30 'oversold'. | 100 − 100/(1+RS), RS = average gain ÷ average loss over 14 sessions (simple averages). | Close |
| MACD / signal / hist | Derived | Trend-momentum indicator: gap between a fast and a slow EMA. | EMA12 − EMA26; signal = EMA9 of MACD; histogram = MACD − signal. | Close |
| BB_upper / mid / lower | Derived | Bollinger Bands: a 20-session average ± 2 standard deviations. | SMA20 ± 2 × population std of the last 20 closes. | Close |
| DC_upper / DC_lower | Derived | Donchian channel: highest high and lowest low of the previous 20 sessions. | max(High) and min(Low) over t−20 … t−1 (today excluded). | High, Low |
| ATR14 | Derived | Average True Range: typical daily price movement in rupees. | Wilder average of max(High−Low, |High−prev Close|, |Low−prev Close|). | High, Low, Close |
| Vol20 | Derived | Annualised volatility: how much daily returns vary. | Std of the last 20 daily returns × √252. | Close |

## Cleaning rules (applied in order, all logged)

1. Sort chronologically.
2. Duplicate dates: keep the last record.
3. Rows with any missing Open/High/Low/Close: removed (prices are never filled).
4. Invalid prices (≤ 0, High < Low, Open/Close outside High–Low): removed.
5. Missing or zero volume: kept and flagged.
6. Overnight gaps > 5%, volume spikes (|z| > 4 on 60-day log volume) and calendar gaps > 5 days: kept and flagged (genuine market events are not removed).

## Glossary

| Term | Definition | Why it matters | Use in the app |
|---|---|---|---|
| OHLCV | Open, High, Low, Close and Volume – the five numbers recorded for each trading session. | They are the raw material for every chart, indicator and backtest. | Downloaded daily from Yahoo Finance and validated on the Market Explorer page. |
| Candlestick | A chart symbol for one session: the 'body' spans open to close, the thin 'shadows' reach the high and low. | The shape summarises who won the session – buyers or sellers. | Price charts and rule-based pattern detection (Doji, Hammer, Engulfing…). |
| Bullish / bearish signal | A rule output suggesting prices may rise (bullish) or fall (bearish). | Signals turn analysis into decisions that can be tested. | Each strategy emits +1 (long), 0 (flat) or −1 (short); shorts are off by default. |
| Moving average | The average price over a recent window, updated every session. | Smooths noise so the trend is easier to see. | SMA Crossover strategy, chart overlays. |
| RSI | Relative Strength Index – compares recent gains with recent losses on a 0–100 scale. | Flags stretched moves that may reverse. | Bollinger Mean Reversion (confirmation) and RSI Divergence. |
| MACD | Moving Average Convergence Divergence – fast EMA minus slow EMA, plus a signal line. | Shows whether short-term momentum is strengthening or fading. | Shown in the data dictionary and indicator panel. |
| Bollinger Bands | A band two standard deviations above and below a moving average. | Prices outside the bands are statistically unusual relative to recent behaviour. | Bollinger Mean Reversion strategy and chart overlay. |
| Volatility | How much returns swing around their average, usually annualised. | Higher volatility means a wider range of possible outcomes – more risk. | Risk metrics, regimes, option pricing input. |
| Correlation | How closely two return series move together, from −1 to +1. | Low correlation between holdings reduces portfolio risk. | Correlation heatmap on the Market Explorer page. |
| Market regime | A broad market condition, e.g. uptrend with low volatility. | Strategies often work in some regimes and fail in others. | Risk & Robustness: price vs 200-day average and volatility vs its median. |
| Backtesting | Replaying a trading rule on past data to see how it would have performed. | Cheap, fast evidence – but only about the past, and easy to fool yourself with. | Every strategy result in the app; trades are filled at the next session's open. |
| Look-ahead bias | Accidentally using information that was not yet available when the decision was made. | It makes backtests look far better than reality. | Signals use data up to the close; trades execute next session; tests verify this. |
| Benchmark | A passive alternative used for comparison, such as buying and holding the stock or NIFTY 50. | An active strategy is only worthwhile if it beats the simple alternative after costs and risk. | Buy & Hold line on charts; criterion in the classification. |
| CAGR | Compound Annual Growth Rate – the steady yearly return that turns the start value into the end value. | Makes periods of different length comparable. | KPI cards and comparison tables. |
| Sharpe ratio | Return above the risk-free rate divided by volatility, annualised. | Rewards return earned per unit of risk, not just return. | Ranking, walk-forward parameter selection, classification. |
| Sortino ratio | Like Sharpe, but only counts downside volatility as risk. | Investors mind losses more than upside surprises. | Comparison tables. |
| Maximum drawdown | The largest fall from a previous high to a later low. | Measures the worst loss an investor would have endured – a key reason strategies are abandoned. | KPI cards, drawdown charts, capital scenarios. |
| Win rate | Share of completed trades that made money after costs. | Useful only together with the size of wins and losses. | Trade statistics. |
| Profit factor | Gross profits of winning trades ÷ gross losses of losing trades. | Above 1 means winners outweigh losers in total. | Comparison table (n/a if there were no losing trades). |
| Trade expectancy | Average profit per trade: win rate × average win − loss rate × average loss. | Tells you what one more trade is 'worth' on average. | Trade statistics. |
| Transaction costs | Brokerage, Securities Transaction Tax, exchange fees, SEBI fee, stamp duty, GST, DP charges and slippage. | Frequent trading can turn a gross profit into a net loss. | Charged per order side; gross vs net shown on Backtesting and Business pages. |
| Slippage | The difference between the price you expected and the price you actually got. | Hidden cost that grows with trade size and in illiquid markets. | Adverse adjustment of fill prices, in basis points (default 5 bps per side). |
| Walk-forward validation | Choose parameters on one period, test them on the next unseen period, then roll forward. | Separates genuine robustness from curve-fitting. | Risk & Robustness page; out-of-sample Sharpe feeds the classification. |
| In-sample / out-of-sample | Data used to build or tune a strategy (in-sample) vs data held back to test it (out-of-sample). | Only out-of-sample results are a fair estimate of real-world behaviour. | Walk-forward table. |
| Option premium | The price paid by the buyer of an option to the seller. | It is the maximum the buyer can lose and the maximum the seller can earn. | Derivatives page (theoretical premiums from Black–Scholes). |
| Call and put | A call is the right to buy at the strike price; a put is the right to sell at the strike price. | Calls benefit from rises, puts from falls; both limit the buyer's loss to the premium. | Pricing calculator and strategy builder. |
| Strike price | The price at which the option holder may buy (call) or sell (put). | Determines whether the option has intrinsic value. | Input to pricing and payoffs. |
| Expiry | The date after which the option ceases to exist. | Less time left means less time value. | Time to expiry (days) input. |
| Delta | Change in option value for a ₹1 move in the underlying. | Shows directional exposure; also an approximate probability of finishing in the money. | Greeks panel and sensitivity charts. |
| Gamma | Change in delta for a ₹1 move in the underlying. | High gamma means exposure changes quickly – near expiry and at the money. | Greeks panel. |
| Theta | Change in option value per calendar day as time passes (time decay). | Option buyers lose theta every day; sellers collect it. | Greeks panel and time-to-expiry chart. |
| Vega | Change in option value for a 1-percentage-point change in volatility. | Options are bets on volatility as well as direction. | Greeks panel and volatility sensitivity chart. |
| Implied volatility | The volatility that makes the model price equal a given market price. | The market's consensus estimate of future volatility. | IV solver on the Derivatives page. |
| Payoff and break-even | Payoff is the option's value at expiry; break-even is the underlying price where profit is zero after the premium. | Shows the range of prices where a strategy makes or loses money. | Payoff diagrams with maximum profit, maximum loss and break-evens. |
| Marubozu | A candle with almost no shadows: it opened at one extreme of the day and closed at the other. | Signals one-sided control by buyers (bullish) or sellers (bearish) for the whole session. | Pattern Validation page. |
| Morning Star / Evening Star | Three-candle reversal patterns: a long candle, a small 'star' candle, then a strong candle in the opposite direction. | Traditionally read as a turning point after a decline (morning) or a rise (evening). | Pattern Validation page. |
| Three White Soldiers / Three Black Crows | Three consecutive long candles in the same direction, each closing beyond the previous one. | Traditionally read as strong momentum continuing or beginning. | Pattern Validation page. |
| Base rate | How often the outcome happens on any day, with no signal at all. | A signal only adds information if it beats the base rate; a 52% hit rate is unimpressive if prices rise on 52% of days anyway. | Pattern Validation compares every hit rate with the stock's own base rate. |
| Confidence interval | A range of values consistent with the data at a stated confidence level (95% here). | Shows how uncertain an estimate is; wide intervals mean few observations or noisy data. | Hit rates, mean returns and correlations. |
| p-value and q-value | p-value: probability of a result at least this extreme if there were no real effect. q-value: p-value adjusted for running many tests. | When dozens of tests are run, some look 'significant' by luck; q-values control that false-discovery rate. | Pattern Validation scorecard. |
| Adverse excursion | The worst move against a position before it is closed. | A signal that is right on average but often falls 5% first may be impossible to hold in practice. | Pattern Validation (drawdown after the signal). |
| Beta | How much a stock moves, on average, for a 1% move in the market index. | Measures market exposure: beta 1.2 tends to amplify index moves by 20%. | Correlation & Regimes page. |
| Rolling correlation | Correlation re-estimated every day over a trailing window (e.g. 63 sessions). | Reveals that relationships change over time, often rising during sell-offs. | Correlation & Regimes page. |
| Diversification ratio | Weighted average volatility of the holdings divided by the portfolio's volatility. | Above 1 means combining the holdings reduced risk; it falls towards 1 as correlations rise. | Correlation & Regimes → Diversification. |
| Correlation vs causation | Two series moving together does not mean one causes the other. | Shared drivers (rates, oil, sentiment) can create correlation without any direct link. | Shown on the Correlation & Regimes page. |
| Calendar spread / butterfly | Calendar spread: price of a near-month futures contract minus a later month. Butterfly: front − 2 × middle + back. | Used in interest-rate futures to trade the shape of the yield curve rather than its level. | Analysed only from contract prices you upload; no such data is bundled. |
| STIR futures | Short-term interest-rate futures: contracts whose price reflects expected short-term interest rates (often quoted as 100 − rate). | Used to hedge or express views on future central-bank policy. | Upload-only analysis on the Correlation & Regimes page. |

## User-uploaded futures contracts

CSV in long format with columns `Date, Contract, Close` (optional `Expiry`). Rows with unreadable dates/prices are dropped and duplicate Date/Contract rows keep the last value; both are reported. No contract data is bundled or generated.
