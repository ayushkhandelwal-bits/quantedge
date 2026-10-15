from src.reference.indicators import sma, ema, rsi, macd

def test_sma():
    prices = [10.0, 20.0, 30.0, 40.0, 50.0]
    period = 3
    result = sma(prices, period)
    
    assert len(result) == len(prices)
    assert result == [None, None, 20.0, 30.0, 40.0]

def test_ema():
    prices = [10.0, 20.0, 30.0, 40.0, 50.0]
    period = 3
    result = ema(prices, period)
    
    assert len(result) == len(prices)
    assert result[0] is None
    assert result[1] is None
    
    # First EMA is SMA(10, 20, 30) = 20.0
    assert result[2] == 20.0
    
    # Next EMA k = 2 / (3 + 1) = 0.5
    # EMA = price * 0.5 + prev_ema * 0.5
    # For index 3 (price 40): 40 * 0.5 + 20 * 0.5 = 30.0
    assert result[3] == 30.0
    
    # For index 4 (price 50): 50 * 0.5 + 30 * 0.5 = 40.0
    assert result[4] == 40.0

def test_rsi_zeros_loss():
    # Only going up, avg_loss should be 0, rsi should be 100
    prices = [10.0, 20.0, 30.0, 40.0, 50.0]
    period = 2
    
    # changes: (0), 10, 10, 10, 10
    # for period=2:
    # at index 0: None
    # at index 1: None (i < period)
    # at index 2: avg_gain = 10, avg_loss = 0 -> RSI = 100.0
    result = rsi(prices, period)
    
    assert len(result) == len(prices)
    assert result[0] is None
    assert result[1] is None
    assert result[2] == 100.0
    assert result[3] == 100.0
    assert result[4] == 100.0

def test_rsi_zero_gains():
    # Only going down, avg_gain should be 0, rsi should be 0
    prices = [50.0, 40.0, 30.0, 20.0, 10.0]
    period = 2
    
    result = rsi(prices, period)
    
    assert len(result) == len(prices)
    assert result[0] is None
    assert result[1] is None
    assert result[2] == 0.0
    assert result[3] == 0.0
    assert result[4] == 0.0

def test_macd():
    # Dummy prices
    prices = [float(i) for i in range(10, 60, 2)] # 25 items
    
    fast = 3
    slow = 6
    signal = 3
    
    macd_line, signal_line, histogram = macd(prices, fast, slow, signal)
    
    assert len(macd_line) == len(prices)
    assert len(signal_line) == len(prices)
    assert len(histogram) == len(prices)
    
    # For index < slow - 1 (index 0 to 4), macd will be None because ema_slow is None
    for i in range(5):
        assert macd_line[i] is None
        assert signal_line[i] is None
        assert histogram[i] is None
        
    # Valid values should eventually appear
    # MACD valid starts at index 5. Signal line needs `signal` valid MACD points (3 points)
    # So signal line valid starts at index 5 + 3 - 1 = 7.
    
    assert macd_line[5] is not None
    assert signal_line[6] is None
    assert signal_line[7] is not None
    assert histogram[7] is not None
