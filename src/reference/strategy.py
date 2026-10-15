from typing import List, Dict
import math
from src.reference.indicators import sma, rsi, bollinger_bands, vwap
SQUAREOFF_TIME = "15:15"  # NSE intraday square-off time (originally imported from a config module)

def sma_crossover_strategy(rows: List[Dict], short_window: int = 20, long_window: int = 50) -> List[Dict]:
    """
    SMA Crossover strategy.
    signal = 1 if SMA(short) > SMA(long)
    signal = 0 if SMA(short) < SMA(long)
    """
    prices = [row["close"] for row in rows]
    short_sma = sma(prices, short_window)
    long_sma = sma(prices, long_window)
    
    signals = []
    current_signal = 0
    
    for i in range(len(rows)):
        s_val = short_sma[i]
        l_val = long_sma[i]
        
        if s_val is not None and l_val is not None:
            if s_val > l_val:
                current_signal = 1
            elif s_val < l_val:
                current_signal = 0
                
        signals.append({
            "date": rows[i].get("timestamp") or rows[i]["date"],
            "signal": current_signal,
            "price": rows[i]["close"],
            "reason": "CROSSOVER"
        })
        
    return signals


# STRATEGY 1: Opening Range Breakout (ORB)
def orb_strategy(ohlcv_intraday: List[Dict], config: Dict) -> List[Dict]:
    """
    Parameters:
        orb_window_minutes: 15  (default)
        buffer_pct: 0.001       (0.1% above/below range)
        stop_pct: 0.003         (stop at range opposite)
        target_multiplier: 1.0  (target = 1x range size)
    
    Logic:
        1. Identify first orb_window_minutes candles (9:15-9:30)
        2. orb_high = max(high) in window, orb_low = min(low) in window
        3. Buy signal when close > orb_high x (1 + buffer_pct)
        4. Sell signal when close < orb_low x (1 - buffer_pct)
        5. Only one signal per day
        6. Force exit at SQUAREOFF_TIME
    """
    orb_window_minutes = config.get("orb_window_minutes", 15)
    buffer_pct = config.get("buffer_pct", 0.001)
    
    signals = []
    current_day = None
    orb_high = None
    orb_low = None
    current_signal = 0
    traded_today = False
    
    for row in ohlcv_intraday:
        date_time = row.get("timestamp") or row.get("date")
        day = date_time.split(" ")[0] if " " in date_time else date_time
        time_part = date_time.split(" ")[1][:5] if " " in date_time else "00:00"
        
        if current_day != day:
            current_day = day
            orb_high = row["high"]
            orb_low = row["low"]
            current_signal = 0
            traded_today = False
        
        try:
            h, m = map(int, time_part.split(":"))
            mins_from_open = (h * 60 + m) - (9 * 60 + 15)
        except ValueError:
            mins_from_open = 999 
        
        if mins_from_open < orb_window_minutes:
            orb_high = max(orb_high, row["high"])
            orb_low = min(orb_low, row["low"])
        elif time_part >= SQUAREOFF_TIME:
            current_signal = 0
        elif not traded_today:
            if row["close"] > orb_high * (1 + buffer_pct):
                current_signal = 1
                traded_today = True
            elif row["close"] < orb_low * (1 - buffer_pct):
                current_signal = -1
                traded_today = True
                
        signals.append({"date": date_time, "signal": current_signal, "price": row["close"], "reason": "ORB"})
    return signals


# STRATEGY 2: Bollinger Band Mean Reversion
def bollinger_mean_reversion(ohlcv: List[Dict], config: Dict) -> List[Dict]:
    """
    Parameters: window: 20, num_std: 2.0, rsi_period: 14, rsi_oversold: 30, rsi_overbought: 70
    Logic: 
        Buy: close < lower_band AND RSI < rsi_oversold
        Sell: close > upper_band AND RSI > rsi_overbought
        Exit: close crosses middle band
    """
    window = config.get("window", 20)
    num_std = config.get("num_std", 2.0)
    rsi_period = config.get("rsi_period", 14)
    rsi_oversold = config.get("rsi_oversold", 30)
    rsi_overbought = config.get("rsi_overbought", 70)
    
    closes = [r["close"] for r in ohlcv]
    bands = bollinger_bands(closes, window, num_std)
    rsi_vals = rsi(closes, rsi_period)
    
    signals = []
    current_signal = 0
    
    for i in range(len(ohlcv)):
        b = bands[i]
        r = rsi_vals[i]
        c = closes[i]
        date_time = ohlcv[i].get("timestamp") or ohlcv[i]["date"]
        
        if b is not None and r is not None:
            upper, middle, lower = b
            if current_signal == 0:
                if c < lower and r < rsi_oversold:
                    current_signal = 1
                elif c > upper and r > rsi_overbought:
                    current_signal = -1
            elif current_signal == 1:
                if c >= middle:
                    current_signal = 0
            elif current_signal == -1:
                if c <= middle:
                    current_signal = 0
                    
        signals.append({"date": date_time, "signal": current_signal, "price": c, "reason": "BB_REVERSION"})
    return signals


# STRATEGY 3: VWAP Mean Reversion (Intraday)
def vwap_mean_reversion(ohlcv_intraday: List[Dict], config: Dict) -> List[Dict]:
    """
    Param: vwap_std_multiplier: 1.5, min_volume_ratio: 1.2
    Logic: Buy > multiplier*std below VWAP + vol spike. Sell if above. Exit on return to VWAP. Reset 9:15.
    """
    vwap_std_multiplier = config.get("vwap_std_multiplier", 1.5)
    min_vol_ratio = config.get("min_volume_ratio", 1.2)
    
    signals = []
    current_day = None
    current_signal = 0
    cum_pv = 0.0
    cum_v = 0.0
    day_prices = []
    
    for row in ohlcv_intraday:
        date_time = row.get("timestamp") or row.get("date")
        day = date_time.split(" ")[0] if " " in date_time else date_time
        
        if current_day != day:
            current_day = day
            cum_pv = 0.0
            cum_v = 0.0
            day_prices = []
            current_signal = 0
            
        tp = (row["high"] + row["low"] + row["close"]) / 3.0
        cum_pv += tp * row["volume"]
        cum_v += row["volume"]
        vw = cum_pv / cum_v if cum_v > 0 else tp
        
        day_prices.append(row["close"])
        
        if len(day_prices) > 1:
            mean = sum(day_prices) / len(day_prices)
            variance = sum((x - mean) ** 2 for x in day_prices) / len(day_prices)
            std = math.sqrt(variance)
        else:
            std = 0.0
            
        upper = vw + vwap_std_multiplier * std
        lower = vw - vwap_std_multiplier * std
        c = row["close"]
        
        avg_vol = (cum_v / len(day_prices)) if len(day_prices) > 0 else 1
        vol_spike = row["volume"] > avg_vol * min_vol_ratio
        
        if current_signal == 0:
            if c < lower and vol_spike:
                current_signal = 1
            elif c > upper and vol_spike:
                current_signal = -1
        else:
            if current_signal == 1 and c >= vw:
                current_signal = 0
            elif current_signal == -1 and c <= vw:
                current_signal = 0
                
        signals.append({"date": date_time, "signal": current_signal, "price": c, "reason": "VWAP_REVERSION"})
    return signals


# STRATEGY 4: Momentum (Cross-Sectional)
def cross_sectional_momentum(multi_stock_data: Dict[str, List[Dict]], config: Dict) -> Dict[str, List[Dict]]:
    """
    Parameters: lookback_days=126, skip_days=21, top_percentile=0.2, bottom_percentile=0.2, rebalance=21
    Rank stocks by MOM (return over lookback discounting latest skip_days). Go long top, short bottom.
    """
    lookback_days = config.get("lookback_days", 126)
    skip_days = config.get("skip_days", 21)
    top_p = config.get("top_percentile", 0.2)
    bottom_p = config.get("bottom_percentile", 0.2)
    rebalance_freq = config.get("rebalance_frequency", 21)
    
    symbols = list(multi_stock_data.keys())
    if not symbols: return {}
    base_sym = symbols[0]
    num_days = len(multi_stock_data[base_sym])
    
    signals = {sym: [] for sym in symbols}
    target_positions = {sym: 0 for sym in symbols}
    
    for i in range(num_days):
        date_val = multi_stock_data[base_sym][i].get("timestamp") or multi_stock_data[base_sym][i]["date"]
        
        if i >= lookback_days and i % rebalance_freq == 0:
            moms = {}
            for sym in symbols:
                c_data = multi_stock_data[sym]
                if len(c_data) > i:
                    p_recent = c_data[i - skip_days]["close"]
                    p_old = c_data[i - lookback_days]["close"]
                    if p_old > 0:
                        moms[sym] = (p_recent / p_old) - 1.0
            
            if moms:
                sorted_syms = sorted(moms.items(), key=lambda x: x[1], reverse=True)
                top_count = max(1, int(len(sorted_syms) * top_p))
                bottom_count = max(1, int(len(sorted_syms) * bottom_p))
                
                top_syms = [x[0] for x in sorted_syms[:top_count]]
                bottom_syms = [x[0] for x in sorted_syms[-bottom_count:]]
                
                for sym in symbols:
                    if sym in top_syms:
                        target_positions[sym] = 1
                    elif sym in bottom_syms:
                        target_positions[sym] = -1
                    else:
                        target_positions[sym] = 0
                        
        for sym in symbols:
            if i < len(multi_stock_data[sym]):
                signals[sym].append({
                    "date": date_val,
                    "signal": target_positions[sym],
                    "price": multi_stock_data[sym][i]["close"],
                    "reason": "CROSS_MOMENTUM"
                })
    return signals


# STRATEGY 5: Pairs Trading
def pairs_trading(stock_a_prices: List[Dict], stock_b_prices: List[Dict], config: Dict) -> Dict[str, List[Dict]]:
    """
    Param: formation_window: 252, trading_window: 126, entry_z: 2.0, exit_z: 0.5, stop_z: 3.0
    1. Estimate hedge ratio beta using OLS.
    2. Spread = A - beta*B
    3. Z-score of spread, checking cointegration with ADF.
    """
    formation = config.get("formation_window", 252)
    entry_z = config.get("entry_z", 2.0)
    exit_z = config.get("exit_z", 0.5)
    stop_z = config.get("stop_z", 3.0)
    
    n = min(len(stock_a_prices), len(stock_b_prices))
    signals_a = []
    signals_b = []
    
    pos_a = 0
    pos_b = 0
    
    for i in range(n):
        date_time = stock_a_prices[i].get("timestamp") or stock_a_prices[i]["date"]
        price_a = stock_a_prices[i]["close"]
        price_b = stock_b_prices[i]["close"]
        
        if i < formation:
            signals_a.append({"date": date_time, "signal": 0, "price": price_a, "reason": "FORMING"})
            signals_b.append({"date": date_time, "signal": 0, "price": price_b, "reason": "FORMING"})
            continue
            
        w_a = [stock_a_prices[j]["close"] for j in range(i - formation, i)]
        w_b = [stock_b_prices[j]["close"] for j in range(i - formation, i)]
        
        mean_a = sum(w_a)/formation
        mean_b = sum(w_b)/formation
        
        cov_ab = sum((w_b[j] - mean_b)*(w_a[j] - mean_a) for j in range(formation))
        var_b = sum((w_b[j] - mean_b)**2 for j in range(formation))
        beta = cov_ab / var_b if var_b != 0 else 0
        
        sp_arr = [w_a[j] - beta * w_b[j] for j in range(formation)]
        mean_sp = sum(sp_arr) / formation
        var_sp = sum((s - mean_sp)**2 for s in sp_arr) / formation
        std_sp = math.sqrt(var_sp)
        
        current_spread = price_a - beta * price_b
        z = (current_spread - mean_sp) / std_sp if std_sp != 0 else 0
        
        # Simplified ADF
        diff_sp = [sp_arr[j] - sp_arr[j-1] for j in range(1, formation)]
        lag_sp = sp_arr[:-1]
        mean_diff = sum(diff_sp)/(formation-1)
        mean_lag = sum(lag_sp)/(formation-1)
        cov_diff_lag = sum((lag_sp[j] - mean_lag)*(diff_sp[j] - mean_diff) for j in range(formation-1))
        var_lag = sum((lag_sp[j] - mean_lag)**2 for j in range(formation-1))
        rho = cov_diff_lag / var_lag if var_lag != 0 else 0
        
        residuals = [diff_sp[j] - (mean_diff - rho*mean_lag) - rho*lag_sp[j] for j in range(formation-1)]
        sse = sum(r**2 for r in residuals)
        mse = sse / (formation - 3) if formation > 3 else 0
        se_rho = math.sqrt(mse / var_lag) if var_lag != 0 and mse > 0 else 1
        t_stat = rho / se_rho if se_rho != 0 else 0
        
        cointegrated = (rho < 0 and t_stat < -2.86)
        
        if cointegrated or pos_a != 0:
            if pos_a == 0:
                if z > entry_z:
                    pos_a = -1
                    pos_b = 1
                elif z < -entry_z:
                    pos_a = 1
                    pos_b = -1
            else:
                if abs(z) < exit_z or abs(z) > stop_z:
                    pos_a = 0
                    pos_b = 0
                    
        signals_a.append({"date": date_time, "signal": pos_a, "price": price_a, "reason": "PAIRS"})
        signals_b.append({"date": date_time, "signal": pos_b, "price": price_b, "reason": "PAIRS"})
        
    return {"A": signals_a, "B": signals_b}


# STRATEGY 6: RSI Divergence
def rsi_divergence(ohlcv: List[Dict], config: Dict) -> List[Dict]:
    """
    Bullish divergence: Price makes lower low but RSI makes higher low
    Bearish divergence: Price makes higher high but RSI makes lower high
    """
    rsi_period = config.get("rsi_period", 14)
    lookback = config.get("lookback", 20)
    
    closes = [r["close"] for r in ohlcv]
    rsi_vals = rsi(closes, rsi_period)
    
    signals = []
    current_signal = 0
    
    for i in range(len(ohlcv)):
        c = closes[i]
        date_time = ohlcv[i].get("timestamp") or ohlcv[i]["date"]
        
        if i >= lookback and rsi_vals[i] is not None:
             w_c = closes[i-lookback:i+1]
             w_r = rsi_vals[i-lookback:i+1]

             c_minima = []
             c_maxima = []
             for j in range(1, len(w_c)-1):
                 if w_c[j] < w_c[j-1] and w_c[j] < w_c[j+1]:
                     c_minima.append(j)
                 if w_c[j] > w_c[j-1] and w_c[j] > w_c[j+1]:
                     c_maxima.append(j)

             if len(c_minima) >= 2:
                 idx1, idx2 = c_minima[-2], c_minima[-1]
                 if w_r[idx1] is not None and w_r[idx2] is not None:
                     if w_c[idx2] < w_c[idx1] and w_r[idx2] > w_r[idx1]:
                         current_signal = 1

             if len(c_maxima) >= 2:
                 idx1, idx2 = c_maxima[-2], c_maxima[-1]
                 if w_r[idx1] is not None and w_r[idx2] is not None:
                     if w_c[idx2] > w_c[idx1] and w_r[idx2] < w_r[idx1]:
                         current_signal = -1
                     
        signals.append({"date": date_time, "signal": current_signal, "price": c, "reason": "RSI_DIV"})
    return signals


# STRATEGY 7: Gap Fill
def gap_fill_strategy(ohlcv_daily: List[Dict], config: Dict) -> List[Dict]:
    """
    Gap up: Open > prev_close * (1 + min_gap_pct) and Open < prev_close * (1 + max_gap_pct) -> Short
    Signals are emitted purely to track daily state.
    """
    max_gap_pct = config.get("max_gap_pct", 0.02)
    min_gap_pct = config.get("min_gap_pct", 0.003)
    
    signals = []
    for i in range(len(ohlcv_daily)):
        row = ohlcv_daily[i]
        date_time = row.get("timestamp") or row["date"]
        o, c = row["open"], row["close"]
        
        if i == 0:
            signals.append({"date": date_time, "signal": 0, "price": o, "reason": "WAIT"})
            continue
            
        prev_close = ohlcv_daily[i-1]["close"]
        gap_up = o > prev_close * (1 + min_gap_pct) and o < prev_close * (1 + max_gap_pct)
        gap_down = o < prev_close * (1 - min_gap_pct) and o > prev_close * (1 - max_gap_pct)
        
        # Position is held for one day and returned to 0 continuously for simplistic gap.
        if gap_up:
            sig = -1
        elif gap_down:
            sig = 1
        else:
            sig = 0
            
        signals.append({"date": date_time, "signal": sig, "price": c, "reason": "GAP_FILL"})
        
    return signals


# STRATEGY 8: Donchian Breakout
def donchian_breakout(ohlcv: List[Dict], config: Dict) -> List[Dict]:
    """
    Upper = max(high, window), Lower = min(low, window)
    Buy: close > Upper, Sell: close < Lower
    """
    window = config.get("window", 20)
    
    signals = []
    current_signal = 0
    
    for i in range(len(ohlcv)):
        c = ohlcv[i]["close"]
        date_time = ohlcv[i].get("timestamp") or ohlcv[i]["date"]
        
        if i < window:
            signals.append({"date": date_time, "signal": 0, "price": c, "reason": "WAIT"})
            continue
            
        w_highs = [ohlcv[j]["high"] for j in range(i-window, i)]
        w_lows = [ohlcv[j]["low"] for j in range(i-window, i)]
        upper = max(w_highs)
        lower = min(w_lows)
        
        if c > upper:
            current_signal = 1
        elif c < lower:
            current_signal = -1
            
        signals.append({"date": date_time, "signal": current_signal, "price": c, "reason": "DONCHIAN"})
        
    return signals

