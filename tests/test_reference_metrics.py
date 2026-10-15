from src.reference.metrics import total_return, cagr, max_drawdown, sharpe_ratio

def test_total_return():
    values = [100.0, 110.0, 150.0]
    expected = ((150.0 - 100.0) / 100.0) * 100.0
    assert total_return(values) == expected

def test_cagr():
    # 2 years of data
    start = 100.0
    end = 200.0 # Doubled in 2 years
    values = [start] + [150.0]*(2*252 - 2) + [end] # Len = 504
    
    # Should be about ~41.4%
    result = cagr(values, trading_days=252)
    assert abs(result - 41.42) < 0.1

def test_flat_sharpe():
    values = [100.0, 100.0, 100.0, 100.0, 100.0]
    result = sharpe_ratio(values)
    # std == 0 -> sharpe == 0
    assert result == 0

def test_max_drawdown():
    # [100, 120, 80, 90]
    # Peak = 120
    # Drop = 120 -> 80
    # Drawdown = (120 - 80) / 120 = 40 / 120 = 0.3333333333% -> 33.33%
    values = [100.0, 120.0, 80.0, 90.0]
    result = max_drawdown(values)
    
    # 33.33%
    assert abs(result - 33.33) < 0.01
