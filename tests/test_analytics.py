import math

import numpy as np
import pandas as pd
import pytest

from src import candlestick_patterns as cp
from src import indicators as ind
from src import performance_metrics as pm
from src.backtester import BacktestConfig, run_backtest
from src.reference import metrics as ref_metrics
from src.strategies import ENABLED, REGISTRY
from src.transaction_costs import CostSchedule, order_charges
from src.walk_forward import walk_forward
from tests.conftest import make_df

ZERO = CostSchedule.zero()


# ----------------------------------------------------------------- indicators
def test_indicators_on_known_values():
    c = pd.Series([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], dtype=float, index=pd.bdate_range("2024-01-01", periods=10))
    assert ind.sma(c, 3).iloc[2] == pytest.approx(2.0)
    assert ind.sma(c, 3).iloc[-1] == pytest.approx(9.0)
    assert math.isnan(ind.sma(c, 3).iloc[1])
    assert ind.rsi(c, 5).iloc[-1] == pytest.approx(100.0)          # only gains
    e = ind.ema(c, 3)
    assert e.iloc[2] == pytest.approx(2.0) and e.iloc[3] == pytest.approx(3.0)
    bb = ind.bollinger(pd.Series([5.0] * 25, index=pd.bdate_range("2024-01-01", periods=25)))
    assert bb["BB_upper"].iloc[-1] == bb["BB_lower"].iloc[-1] == 5.0


def test_indicators_are_causal(synth):
    """Value at t must not change when future rows are appended."""
    full = ind.feature_frame(synth)
    part = ind.feature_frame(synth.iloc[:400])
    cols = ["SMA20", "SMA50", "EMA20", "RSI14", "MACD", "BB_upper", "ATR14", "Vol20", "DC_upper"]
    pd.testing.assert_frame_equal(full[cols].iloc[:400], part[cols], check_exact=False, rtol=1e-12)


# ----------------------------------------------------------------- patterns
def test_patterns_detect_textbook_candles():
    idx = pd.bdate_range("2024-01-01", periods=14)
    o = [110, 109, 108, 107, 106, 105, 104, 103, 102, 101, 100.0, 96.0, 99.0, 100.0]
    c = [109, 108, 107, 106, 105, 104, 103, 102, 101, 100, 97.0, 100.5, 99.05, 100.0]
    h = [111, 110, 109, 108, 107, 106, 105, 104, 103, 102, 100.5, 101.0, 101.0, 100.2]
    l = [108, 107, 106, 105, 104, 103, 102, 101, 100, 99, 96.5, 95.5, 97.0, 99.8]
    df = pd.DataFrame({"Open": o, "High": h, "Low": l, "Close": c, "Volume": 1.0}, index=idx)
    det = cp.detect(df)
    assert det["Bullish Engulfing"].iloc[11]       # bearish day 10 engulfed by bullish day 11
    assert det["Doji"].iloc[12]                      # body 0.05 of range 4
    hammer = pd.DataFrame({"Open": [99.5], "High": [100.2], "Low": [96.0], "Close": [100.1], "Volume": [1.0]},
                          index=[pd.Timestamp("2024-02-01")])
    assert cp.detect(hammer, cp.PatternParams(require_trend=False))["Hammer"].iloc[0]


def test_pattern_detection_does_not_use_future(synth):
    full = cp.detect(synth)
    part = cp.detect(synth.iloc[:300])
    pd.testing.assert_frame_equal(full.iloc[:300], part)


def test_forward_returns_start_after_signal():
    c = pd.Series([100.0, 110.0, 121.0], index=pd.bdate_range("2024-01-01", periods=3))
    f = cp.forward_returns(c, (1, 2))
    assert f["fwd_1d"].iloc[0] == pytest.approx(0.10)
    assert f["fwd_2d"].iloc[0] == pytest.approx(0.21)
    assert math.isnan(f["fwd_1d"].iloc[-1])


# ----------------------------------------------------------------- strategies & leakage
@pytest.mark.parametrize("key", ENABLED)
def test_signals_do_not_use_future_data(synth, key):
    strat = REGISTRY[key]
    full = strat.signals(synth)
    cut = 500
    part = strat.signals(synth.iloc[:cut])
    assert (full["target"].iloc[:cut].values == part["target"].values).all(), f"{key} signal changed when future data added"


def test_unavailable_strategies_raise_and_explain():
    for k, s in REGISTRY.items():
        if not s.available:
            assert s.unavailable_reason
            with pytest.raises(RuntimeError):
                s.signals(make_df([1, 2, 3]))


# ----------------------------------------------------------------- backtester
def sig(df, values):
    return pd.DataFrame({"target": values, "reason": ""}, index=df.index)


def test_next_open_execution_and_pnl():
    df = make_df([100, 100, 110, 120], opens=[100, 105, 108, 118])
    res = run_backtest(df, sig(df, [1, 1, 0, 0]), BacktestConfig(initial_capital=10_000, costs=ZERO))
    t = res.trades.iloc[0]
    assert t["Entry date"] == df.index[1] and t["Entry price"] == 105      # signal day 0 → open day 1
    assert t["Exit date"] == df.index[3] and t["Exit price"] == 118        # exit signal day 2 → open day 3
    q = math.floor(10_000 / (105 * 1.002))
    assert t["Quantity"] == q
    assert t["Net P&L"] == pytest.approx(q * 13)
    assert res.curve.iloc[-1] == pytest.approx(10_000 + q * 13)
    assert res.curve.iloc[0] == 10_000                                      # nothing happens on signal day


def test_same_close_mode_is_more_optimistic_on_a_rising_open_gap():
    df = make_df([100, 110, 120], opens=[100, 115, 121])
    nxt = run_backtest(df, sig(df, [1, 1, 1]), BacktestConfig(initial_capital=10_000, costs=ZERO))
    same = run_backtest(df, sig(df, [1, 1, 1]), BacktestConfig(initial_capital=10_000, costs=ZERO, execution="same_close"))
    assert same.curve.iloc[-1] > nxt.curve.iloc[-1]


def test_costs_reduce_net_and_are_accounted_exactly():
    df = make_df([100, 100, 100, 100], opens=[100, 100, 100, 100])
    cs = CostSchedule(slippage_bps=10)
    res = run_backtest(df, sig(df, [1, 1, 0, 0]), BacktestConfig(initial_capital=100_000, costs=cs))
    t = res.trades.iloc[0]
    assert t["Gross P&L"] == 0
    assert t["Net P&L"] == pytest.approx(-(t["Charges"] + t["Slippage"]))
    assert res.curve.iloc[-1] == pytest.approx(100_000 + t["Net P&L"])
    assert t["Charges"] > 0 and t["Slippage"] > 0


def test_short_signals_ignored_unless_allowed():
    df = make_df([100, 100, 90, 80], opens=[100, 100, 95, 85])
    flat = run_backtest(df, sig(df, [-1, -1, -1, -1]), BacktestConfig(costs=ZERO))
    assert len(flat.trades) == 0 and flat.curve.iloc[-1] == flat.curve.iloc[0]
    short = run_backtest(df, sig(df, [-1, -1, -1, -1]), BacktestConfig(costs=ZERO, allow_short=True))
    assert short.trades.iloc[0]["Direction"] == "Short" and short.curve.iloc[-1] > short.curve.iloc[0]


def test_open_position_is_closed_at_end_of_data():
    df = make_df([100, 101, 102])
    res = run_backtest(df, sig(df, [1, 1, 1]), BacktestConfig(costs=ZERO))
    assert res.trades.iloc[-1]["Exit reason"].startswith("End of data")


def test_gap_strategy_open_to_close():
    df = make_df([100, 101], opens=[100, 99])          # gap down on day 1, closes up
    res = run_backtest(df, sig(df, [0, 1]), BacktestConfig(initial_capital=10_000, costs=ZERO, execution="open_to_close"))
    t = res.trades.iloc[0]
    assert t["Entry price"] == 99 and t["Exit price"] == 101 and t["Holding days"] == 0


# ----------------------------------------------------------------- costs
def test_order_charges_match_published_schedule():
    cs = CostSchedule()
    buy = order_charges("buy", 1000, 100, "delivery", cs)        # ₹1,00,000 order
    assert buy["stt"] == pytest.approx(100.0)                     # 0.1%
    assert buy["stamp"] == pytest.approx(15.0)                    # 0.015%
    assert buy["exchange"] == pytest.approx(3.07)
    assert buy["gst"] == pytest.approx(0.18 * (3.07 + 0.10))
    sell = order_charges("sell", 1000, 100, "delivery", cs)
    assert sell["stamp"] == 0 and sell["dp"] == pytest.approx(15.34)
    intr = order_charges("buy", 1000, 100, "intraday", cs)
    assert intr["brokerage"] == pytest.approx(20.0) and intr["stt"] == 0
    assert order_charges("buy", 1000, 100, "delivery", CostSchedule.zero())["total"] == 0


# ----------------------------------------------------------------- metrics
def test_metrics_known_values_and_reference_agreement():
    idx = pd.bdate_range("2024-01-01", periods=4)
    eq = pd.Series([100.0, 120.0, 80.0, 90.0], index=idx)
    assert pm.max_drawdown(eq) == pytest.approx(40 / 120)
    assert pm.total_return(eq) == pytest.approx(-0.10)
    assert pm.max_drawdown(eq) * 100 == pytest.approx(ref_metrics.max_drawdown(eq.tolist()))
    yr = pd.Series([100.0, 121.0], index=pd.to_datetime(["2020-01-01", "2022-01-01"]))
    assert pm.cagr(yr) == pytest.approx(0.10, abs=2e-3)


def test_metrics_edge_cases_are_none_not_inf():
    flat = pd.Series(100.0, index=pd.bdate_range("2024-01-01", periods=60))
    assert pm.sharpe(flat) is None and pm.sortino(flat) is None
    rising = pd.Series(np.linspace(100, 130, 60), index=pd.bdate_range("2024-01-01", periods=60))
    assert pm.sortino(rising) is None                               # no downside days
    winners = pd.DataFrame({"Net P&L": [10.0, 5.0], "Holding days": [1, 2]})
    st = pm.trade_stats(winners)
    assert st["profit_factor"] is None and st["win_rate"] == 1.0
    assert pm.trade_stats(winners.iloc[0:0])["win_rate"] is None


def test_sharpe_matches_definition():
    rng = np.random.default_rng(0)
    r = rng.normal(0.0005, 0.01, 500)
    eq = pd.Series(100 * np.cumprod(1 + r), index=pd.bdate_range("2020-01-01", periods=500))
    rr = eq.pct_change().dropna()
    expected = (rr.mean() - 0.05 / 252) / rr.std(ddof=1) * np.sqrt(252)
    assert pm.sharpe(eq, 0.05) == pytest.approx(expected)


# ----------------------------------------------------------------- walk-forward
def test_walk_forward_windows_are_chronological_and_disjoint(synth):
    cfg = BacktestConfig(costs=CostSchedule())
    res = walk_forward(synth, REGISTRY["sma_crossover"], cfg, 0.05, train_years=1.5, test_months=6)
    assert len(res.splits) >= 3
    prev_test_end = None
    for _, row in res.splits.iterrows():
        tr_s, tr_e = [pd.Timestamp(x) for x in row["Train"].split(" → ")]
        te_s, te_e = [pd.Timestamp(x) for x in row["Test"].split(" → ")]
        assert tr_s < tr_e < te_s <= te_e                       # train strictly before test
        if prev_test_end is not None:
            assert te_s > prev_test_end                         # test windows never overlap
        prev_test_end = te_e
    assert res.oos_equity.index.is_monotonic_increasing


def test_reproducible(synth):
    cfg = BacktestConfig()
    a = run_backtest(synth, REGISTRY["donchian"].signals(synth), cfg)
    b = run_backtest(synth, REGISTRY["donchian"].signals(synth), cfg)
    pd.testing.assert_series_equal(a.curve, b.curve)
