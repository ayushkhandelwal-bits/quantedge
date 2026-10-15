import math
from typing import List

def total_return(values: List[float]) -> float:
    """Calculates total percentage return."""
    if not values or values[0] == 0:
        return 0.0
    start = values[0]
    end = values[-1]
    return ((end - start) / start) * 100.0

def cagr(values: List[float], trading_days: int = 252) -> float:
    """Calculates Compound Annual Growth Rate as a percentage."""
    if not values or values[0] == 0:
        return 0.0
    start = values[0]
    end = values[-1]
    years = len(values) / trading_days
    
    if years <= 0:
        return 0.0
        
    return (math.pow(end / start, 1 / years) - 1.0) * 100.0

def max_drawdown(values: List[float]) -> float:
    """Calculates maximum peak-to-trough drop (as a positive percentage)."""
    if not values:
        return 0.0
        
    peak = values[0]
    max_dd = 0.0
    
    for val in values:
        if val > peak:
            peak = val
        drawdown = (peak - val) / peak
        if drawdown > max_dd:
            max_dd = drawdown
            
    return max_dd * 100.0

def sharpe_ratio(values: List[float], annual_risk_free_rate: float = 0.04) -> float:
    """Calculates the annualized Sharpe Ratio of the portfolio relative returns."""
    if len(values) < 2:
        return 0.0
        
    daily_returns = []
    for i in range(1, len(values)):
        prev = values[i - 1]
        curr = values[i]
        ret = (curr - prev) / prev if prev != 0 else 0
        daily_returns.append(ret)
        
    daily_rf = annual_risk_free_rate / 252.0
    
    # Mean of returns
    mean_return = sum(daily_returns) / len(daily_returns)
    
    # Standard deviation of returns (population variance)
    variance_sum = sum((r - mean_return) ** 2 for r in daily_returns)
    variance = variance_sum / len(daily_returns)
    std_dev = math.sqrt(variance)
    
    if std_dev == 0:
        return 0.0
        
    daily_sharpe = (mean_return - daily_rf) / std_dev
    return daily_sharpe * math.sqrt(252)

# ============================================================================
# EXPANDED METRICS
# ============================================================================

def sortino_ratio(values: List[float], risk_free_rate: float = 0.07, target: float = 0.0) -> float:
    """
    Like Sharpe but only penalises downside volatility.
    Accepts portfolio values (same as sharpe_ratio), converts to daily returns internally.
    Sortino = (Mean Return - Risk Free) / Downside Deviation
    """
    if len(values) < 2:
        return 0.0

    daily_returns = []
    for i in range(1, len(values)):
        prev = values[i - 1]
        curr = values[i]
        daily_returns.append((curr - prev) / prev if prev != 0 else 0)

    daily_rf = risk_free_rate / 252.0
    mean_return = sum(daily_returns) / len(daily_returns)

    downside_returns = [r - daily_rf for r in daily_returns if r < daily_rf]
    if not downside_returns:
        return float('inf')

    downside_variance = sum(r**2 for r in downside_returns) / len(daily_returns)
    downside_dev = math.sqrt(downside_variance)

    if downside_dev == 0:
        return 0.0

    daily_sortino = (mean_return - daily_rf) / downside_dev
    return daily_sortino * math.sqrt(252)

def calmar_ratio(values: List[float], max_drawdown_pct: float) -> float:
    """
    Calmar = CAGR / |Max Drawdown|
    Accepts portfolio values and max drawdown as a percentage.
    """
    if max_drawdown_pct == 0 or len(values) < 2:
        return 0.0

    cagr_val = cagr(values)
    return cagr_val / abs(max_drawdown_pct)

def win_rate(trades: List[dict]) -> float:
    """% of trades with positive P&L after all costs"""
    if not trades: 
        return 0.0
    wins = [t for t in trades if (t.get('pnl', 0) if isinstance(t, dict) else t) > 0]
    return len(wins) / len(trades)

def average_win_loss_ratio(trades: List[dict]) -> float:
    """avg_win / avg_loss — must be > 1/(win_rate) to be profitable"""
    if not trades: 
        return 0.0
    
    wins = [t for t in trades if (t.get('pnl', 0) if isinstance(t, dict) else t) > 0]
    losses = [t for t in trades if (t.get('pnl', 0) if isinstance(t, dict) else t) <= 0]
    
    avg_win = (sum(w.get('pnl', 0) if isinstance(w, dict) else w for w in wins) / len(wins)) if wins else 0.0
    avg_loss = (sum(abs(l.get('pnl', 0) if isinstance(l, dict) else l) for l in losses) / len(losses)) if losses else 0.0
    
    if avg_loss == 0.0:
        return float('inf')
    return avg_win / avg_loss

def profit_factor(trades: List[dict]) -> float:
    """Gross profit / Gross loss — target > 1.5"""
    if not trades: 
        return 0.0
    
    gross_profit = sum(t.get('pnl', 0) if isinstance(t, dict) else t for t in trades if (t.get('pnl', 0) if isinstance(t, dict) else t) > 0)
    gross_loss = sum(abs(t.get('pnl', 0) if isinstance(t, dict) else t) for t in trades if (t.get('pnl', 0) if isinstance(t, dict) else t) < 0)
    
    if gross_loss == 0.0:
        return float('inf')
    return gross_profit / gross_loss

def max_consecutive_losses(trades: List[dict]) -> int:
    """Longest losing streak — psychological and risk management metric"""
    max_streak = 0
    current_streak = 0
    for t in trades:
        val = t.get('pnl', 0) if isinstance(t, dict) else t
        if val <= 0:
            current_streak += 1
            if current_streak > max_streak:
                max_streak = current_streak
        else:
            current_streak = 0
    return max_streak

def trade_expectancy(trades: List[dict]) -> float:
    """
    Expected P&L per trade:
    E = (Win Rate × Avg Win) - (Loss Rate × Avg Loss)
    """
    if not trades: 
        return 0.0
    wins = [t for t in trades if (t.get('pnl', 0) if isinstance(t, dict) else t) > 0]
    losses = [t for t in trades if (t.get('pnl', 0) if isinstance(t, dict) else t) <= 0]
    
    win_rt = len(wins) / len(trades)
    loss_rt = len(losses) / len(trades)
    
    avg_win = (sum(w.get('pnl', 0) if isinstance(w, dict) else w for w in wins) / len(wins)) if wins else 0.0
    avg_loss = (sum(abs(l.get('pnl', 0) if isinstance(l, dict) else l) for l in losses) / len(losses)) if losses else 0.0
    
    return (win_rt * avg_win) - (loss_rt * avg_loss)

def rolling_sharpe(returns: List[float], window: int = 63, annual_rf: float = 0.065) -> List[tuple]:
    """
    63-day (quarterly) rolling Sharpe.
    Returns list of (index/date, sharpe) tuples.
    """
    results = []
    daily_rf = annual_rf / 252.0
    
    for i in range(len(returns)):
        is_dict = isinstance(returns[i], dict)
        date_key = returns[i].get("date") if is_dict else i
        
        if i < window - 1:
            results.append((date_key, None))
            continue
             
        w = returns[i - window + 1: i + 1]
        vals = [x.get("return", x.get("value", 0)) if isinstance(x, dict) else x for x in w]
        
        mean = sum(vals) / window
        var = sum((x - mean)**2 for x in vals) / window
        std = math.sqrt(var)
        
        if std == 0:
            sh = 0.0
        else:
            sh = ((mean - daily_rf) / std) * math.sqrt(252)
            
        results.append((date_key, sh))
             
    return results

def underwater_curve(equity_curve: List[float]) -> List[float]:
    """
    % drawdown at each point in time. 
    Shows how long strategy spends in drawdown.
    """
    if not equity_curve: 
        return []
    
    drawdowns = []
    peak = equity_curve[0] if not isinstance(equity_curve[0], dict) else equity_curve[0].get("value", 0)
    
    for item in equity_curve:
        val = item if not isinstance(item, dict) else item.get("value", 0)
        
        if val > peak:
            peak = val
            
        if peak == 0:
            drawdowns.append(0.0)
        else:
            dd = (peak - val) / peak
            drawdowns.append(dd * 100.0) # Percentage
            
    return drawdowns

def kelly_fraction(win_rate: float, avg_win: float, avg_loss: float) -> float:
    """Optimal fraction of capital to risk per trade"""
    if avg_loss == 0:
        return 0.0
    b = avg_win / avg_loss
    if b == 0:
        return 0.0
    f = (b * win_rate - (1.0 - win_rate)) / b
    return max(0.0, f)
