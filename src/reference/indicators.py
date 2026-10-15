from typing import List, Optional, Tuple
import math

def sma(prices: List[float], period: int) -> List[Optional[float]]:
    """
    Simple Moving Average.
    Average of the last `period` prices.
    Returns None for the first `period - 1` indexes.
    """
    result = []
    for i in range(len(prices)):
        if i < period - 1:
            result.append(None)
        else:
            window = prices[i - period + 1 : i + 1]
            result.append(sum(window) / period)
    return result

def ema(prices: List[float], period: int) -> List[Optional[float]]:
    """
    Exponential Moving Average.
    k = 2 / (period + 1)
    Seeds the first valid EMA with the SMA of the first `period` prices.
    """
    result = []
    k = 2.0 / (period + 1)
    
    for i in range(len(prices)):
        if i < period - 1:
            result.append(None)
        elif i == period - 1:
            window = prices[0 : period]
            result.append(sum(window) / period)
        else:
            prev_ema = result[-1]
            current_ema = (prices[i] * k) + (prev_ema * (1 - k))
            result.append(current_ema)
    return result

def rsi(prices: List[float], period: int = 14) -> List[Optional[float]]:
    """
    Relative Strength Index.
    Calculates the RSI based on a rolling mean of gains and losses.
    Returns None for the first `period` values.
    """
    result = []
    gains = []
    losses = []
    
    for i in range(len(prices)):
        if i == 0:
            result.append(None)
            continue
            
        change = prices[i] - prices[i - 1]
        gains.append(change if change > 0 else 0.0)
        losses.append(abs(change) if change < 0 else 0.0)
        
        # We need `period` full days of changes
        if i < period:
            result.append(None)
        else:
            # Getting the last `period` items from the gains/losses arrays
            avg_gain = sum(gains[-period:]) / period
            avg_loss = sum(losses[-period:]) / period
            
            if avg_loss == 0:
                result.append(100.0)
            else:
                rs = avg_gain / avg_loss
                result.append(100.0 - (100.0 / (1.0 + rs)))
                
    return result

def macd(prices: List[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[List[Optional[float]], List[Optional[float]], List[Optional[float]]]:
    """
    Moving Average Convergence Divergence.
    MACD Line = EMA(fast) - EMA(slow)
    Signal Line = EMA(MACD Line, signal)
    Histogram = MACD Line - Signal Line
    """
    ema_fast = ema(prices, fast)
    ema_slow = ema(prices, slow)
    
    macd_line = []
    for i in range(len(prices)):
        if ema_fast[i] is None or ema_slow[i] is None:
            macd_line.append(None)
        else:
            macd_line.append(ema_fast[i] - ema_slow[i])
            
    # Calculate Signal Line
    # We strip the leading Nones from the MACD line to feed it safely into the EMA
    valid_macd = [x for x in macd_line if x is not None]
    
    if not valid_macd:
        return (
            [None] * len(prices),
            [None] * len(prices),
            [None] * len(prices),
        )
        
    signal_valid = ema(valid_macd, signal)
    
    # Pad the Nones back in
    num_nones = len(prices) - len(valid_macd)
    signal_line = ([None] * num_nones) + signal_valid
    
    # Histogram
    histogram = []
    for i in range(len(prices)):
        if macd_line[i] is None or signal_line[i] is None:
            histogram.append(None)
        else:
            histogram.append(macd_line[i] - signal_line[i])
            
    return macd_line, signal_line, histogram

# ============================================================================
# NEW EXPANDED INDICATORS
# ============================================================================

def rolling_std(prices: List[float], window: int) -> List[Optional[float]]:
    result = []
    for i in range(len(prices)):
        if i < window - 1:
            result.append(None)
        else:
            w = prices[i - window + 1: i + 1]
            mean = sum(w) / window
            variance = sum((x - mean) ** 2 for x in w) / window
            result.append(math.sqrt(variance))
    return result

def bollinger_bands(prices: List[float], window: int = 20, num_std: float = 2.0) -> List[Optional[Tuple[float, float, float]]]:
    """
    Returns list of (upper, middle, lower) tuples
    """
    middle = sma(prices, window)
    std = rolling_std(prices, window)
    
    result = []
    for i in range(len(prices)):
        if middle[i] is None or std[i] is None:
            result.append(None)
        else:
            m = middle[i]
            s = std[i]
            upper = m + num_std * s
            lower = m - num_std * s
            result.append((upper, m, lower))
    return result

def atr(highs: List[float], lows: List[float], closes: List[float], window: int = 14) -> List[Optional[float]]:
    """
    Average True Range with Wilder's smoothing.
    """
    if len(highs) == 0:
        return []
        
    tr = []
    for i in range(len(highs)):
        if i == 0:
            tr.append(highs[i] - lows[i])
        else:
            h_l = highs[i] - lows[i]
            h_pc = abs(highs[i] - closes[i - 1])
            l_pc = abs(lows[i] - closes[i - 1])
            tr.append(max(h_l, h_pc, l_pc))
            
    result = []
    for i in range(len(tr)):
        if i < window - 1:
            result.append(None)
        elif i == window - 1:
            result.append(sum(tr[:window]) / window)
        else:
            prev_atr = result[-1]
            current_atr = (prev_atr * (window - 1) + tr[i]) / window
            result.append(current_atr)
    return result

def stochastic(highs: List[float], lows: List[float], closes: List[float], k_period: int = 14, d_period: int = 3) -> List[Optional[Tuple[float, float]]]:
    """
    Returns list of (%K, %D) tuples
    """
    percent_k = []
    for i in range(len(closes)):
        if i < k_period - 1:
            percent_k.append(None)
        else:
            window_highs = highs[i - k_period + 1: i + 1]
            window_lows = lows[i - k_period + 1: i + 1]
            hh = max(window_highs)
            ll = min(window_lows)
            
            if hh - ll == 0:
                percent_k.append(0.0)
            else:
                k_val = ((closes[i] - ll) / (hh - ll)) * 100.0
                percent_k.append(k_val)
                
    valid_k = [x for x in percent_k if x is not None]
    if not valid_k:
        return [None] * len(closes)
        
    percent_d_valid = sma(valid_k, d_period)
    percent_d = ([None] * (len(closes) - len(valid_k))) + percent_d_valid
    
    result = []
    for i in range(len(closes)):
        if percent_k[i] is None or percent_d[i] is None:
            result.append(None)
        else:
            result.append((percent_k[i], percent_d[i]))
    return result

def vwap(highs: List[float], lows: List[float], closes: List[float], volumes: List[float]) -> List[float]:
    """
    Volume Weighted Average Price.
    Returns: list of vwap values
    Note: Must be reset daily for true accuracy (run this only on single-day intraday data arrays).
    """
    result = []
    cum_pv = 0.0
    cum_v = 0.0
    for i in range(len(closes)):
        tp = (highs[i] + lows[i] + closes[i]) / 3.0
        cum_pv += tp * volumes[i]
        cum_v += volumes[i]
        
        if cum_v == 0:
            result.append(tp)
        else:
            result.append(cum_pv / cum_v)
    return result

def zscore(prices: List[float], window: int = 20) -> List[Optional[float]]:
    """
    Z-Score of price over a rolling window.
    """
    middle = sma(prices, window)
    std = rolling_std(prices, window)
    
    result = []
    for i in range(len(prices)):
        if middle[i] is None or std[i] is None or std[i] == 0:
            result.append(None)
        else:
            z = (prices[i] - middle[i]) / std[i]
            result.append(z)
    return result

def hurst_exponent(prices: List[float], max_lag: int = 100) -> float:
    """
    Approximated Hurst Exponent using Rescaled Range (R/S) analysis.
    Returns: float H where:
        H < 0.5 = mean-reverting
        H = 0.5 = random walk  
        H > 0.5 = trending
    """
    if len(prices) < max_lag * 2:
        return 0.5 # Default to random walk if not enough data
        
    returns = [prices[i] - prices[i-1] for i in range(1, len(prices))]
    
    lags = []
    rs_vals = []
    
    # Calculate R/S for different lags
    for lag in range(2, max_lag + 1, max(1, max_lag // 10)):
        if len(returns) < lag:
            break
            
        rs_avg = []
        for i in range(0, len(returns) - lag + 1, lag):
            chunk = returns[i : i+lag]
            m = sum(chunk) / lag
            centered = [x - m for x in chunk]
            
            cum_dev = []
            c = 0.0
            for x in centered:
                c += x
                cum_dev.append(c)
                
            R = max(cum_dev) - min(cum_dev)
            variance = sum(x**2 for x in centered) / lag
            S = math.sqrt(variance)
            
            if S > 0:
                rs_avg.append(R / S)
                
        if rs_avg:
            mean_rs = sum(rs_avg) / len(rs_avg)
            lags.append(math.log(lag))
            rs_vals.append(math.log(mean_rs))
            
    if len(lags) < 2:
        return 0.5
        
    # Linear regression to find slope (H)
    n = len(lags)
    sum_x = sum(lags)
    sum_y = sum(rs_vals)
    sum_xy = sum(lags[i] * rs_vals[i] for i in range(n))
    sum_x2 = sum(lags[i] ** 2 for i in range(n))
    
    denominator = (n * sum_x2 - sum_x ** 2)
    if denominator == 0:
         return 0.5
         
    slope = (n * sum_xy - sum_x * sum_y) / denominator
    return slope

def rolling_volatility(returns: List[float], window: int = 20, annualize: bool = True) -> List[Optional[float]]:
    """
    Rolling Volatility. Assuming daily returns by default (periods_per_year=252).
    """
    std = rolling_std(returns, window)
    
    result = []
    multiplier = math.sqrt(252) if annualize else 1.0
    for i in range(len(returns)):
        if std[i] is None:
            result.append(None)
        else:
            result.append(std[i] * multiplier)
    return result

def vix_signal(vix_values: List[float], low_threshold: float = 14.0, high_threshold: float = 20.0) -> List[str]:
    """
    India VIX integration signal.
    """
    result = []
    for val in vix_values:
        if val < low_threshold:
            result.append("low_vol")
        elif val > high_threshold:
            result.append("high_vol")
        else:
            result.append("normal")
    return result
