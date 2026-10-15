import math

import numpy as np
import pandas as pd
import pytest

from src import candlestick_patterns as cp
from src import correlation as co
from src import pattern_validation as pv
from src import spreads


def frame(rows, start="2024-01-01"):
    idx = pd.bdate_range(start, periods=len(rows), name="Date")
    return pd.DataFrame(rows, columns=["Open", "High", "Low", "Close"], index=idx).assign(Volume=1.0)


NO_TREND = cp.PatternParams(require_trend=False)


# ----------------------------------------------------------------- new pattern definitions
def test_marubozu():
    df = frame([[100, 110.2, 99.9, 110], [110, 110.1, 100, 100.1]])
    det = cp.detect(df)
    assert det["Bullish Marubozu"].iloc[0] and not det["Bearish Marubozu"].iloc[0]
    assert det["Bearish Marubozu"].iloc[1]


def test_morning_and_evening_star():
    ms = frame([[110, 110.5, 99.5, 100], [99, 99.6, 97.5, 98.8], [99, 106.5, 98.8, 106]])
    assert cp.detect(ms, NO_TREND)["Morning Star"].iloc[2]
    es = frame([[100, 110.5, 99.5, 110], [111, 112.5, 110.6, 111.3], [111, 111.2, 103.5, 104]])
    assert cp.detect(es, NO_TREND)["Evening Star"].iloc[2]
    # third candle not closing past the midpoint -> no pattern
    weak = frame([[110, 110.5, 99.5, 100], [99, 99.6, 97.5, 98.8], [99, 104.6, 98.8, 104]])
    assert not cp.detect(weak, NO_TREND)["Morning Star"].iloc[2]


def test_three_soldiers_and_crows():
    up = frame([[100, 104.2, 99.8, 104], [102, 106.2, 101.8, 106], [104, 108.2, 103.8, 108]])
    det = cp.detect(up)
    assert det["Three White Soldiers"].iloc[2] and not det["Three White Soldiers"].iloc[1]
    dn = frame([[108, 108.2, 103.8, 104], [106, 106.2, 101.8, 102], [104, 104.2, 99.8, 100]])
    assert cp.detect(dn)["Three Black Crows"].iloc[2]
    # an opening outside the previous body breaks the sequence
    gap = frame([[100, 104.2, 99.8, 104], [105, 109.2, 104.8, 109], [107, 111.2, 106.8, 111]])
    assert not cp.detect(gap)["Three White Soldiers"].iloc[2]


def test_original_pattern_definitions_unchanged(synth):
    det = cp.detect(synth)
    # recompute the original five with the original formulas
    o, h, l, c = synth.Open, synth.High, synth.Low, synth.Close
    rng = (h - l).replace(0, np.nan)
    body = (c - o).abs()
    doji = (body <= 0.10 * rng).fillna(False)
    assert (det["Doji"] == doji).all()
    assert cp.ORIGINAL_PATTERNS == ["Doji", "Hammer", "Shooting Star", "Bullish Engulfing", "Bearish Engulfing"]


def test_all_patterns_causal(synth):
    full = cp.detect(synth, NO_TREND)
    part = cp.detect(synth.iloc[:400], NO_TREND)
    pd.testing.assert_frame_equal(full.iloc[:400], part)
    for name in cp.PATTERNS:
        assert cp.describe_rule(name, cp.PatternParams())


# ----------------------------------------------------------------- validation statistics
def test_wilson_and_mean_ci():
    lo, hi = pv.wilson_ci(50, 100)
    assert lo == pytest.approx(0.4038, abs=1e-3) and hi == pytest.approx(0.5962, abs=1e-3)
    assert all(math.isnan(x) for x in pv.wilson_ci(0, 0))
    lo, hi = pv.mean_ci(pd.Series([1.0, 2.0, 3.0, 4.0]))
    assert lo < 2.5 < hi


def test_bh_adjustment_monotone():
    q = pv.benjamini_hochberg(pd.Series([0.01, 0.04, 0.03, np.nan, 0.5]))
    assert math.isnan(q.iloc[3])
    assert (q.dropna() >= pd.Series([0.01, 0.04, 0.03, 0.5]).values).all()
    assert q.iloc[0] == pytest.approx(0.04)


def test_events_use_only_future_window_and_costs():
    # Bullish marubozu on day 0; prices after are known
    df = frame([[100, 110.1, 99.95, 110], [111, 115, 105, 112], [112, 113, 108, 109], [109, 120, 108, 118]])
    ev = pv.stock_events(df, "X", NO_TREND, horizons=(1, 2), entry="next_open", cost_pct=0.01, patterns=["Bullish Marubozu"])
    r = ev.iloc[0]
    assert r["Entry price"] == 111                       # next session's open
    assert r["ret_1d"] == pytest.approx(112 / 111 - 1)
    assert r["dir_2d"] == pytest.approx(109 / 111 - 1)
    assert r["net_2d"] == pytest.approx(109 / 111 - 1 - 0.01)
    assert r["mae_2d"] == pytest.approx(105 / 111 - 1)   # lowest low of sessions t+1..t+2
    ev_c = pv.stock_events(df, "X", NO_TREND, horizons=(1,), entry="close", patterns=["Bullish Marubozu"])
    assert ev_c.iloc[0]["ret_1d"] == pytest.approx(112 / 110 - 1)


def test_bearish_direction_sign():
    df = frame([[110, 110.05, 99.9, 100], [100, 101, 95, 96], [96, 97, 90, 91]])
    ev = pv.stock_events(df, "X", NO_TREND, horizons=(1,), entry="close", patterns=["Bearish Marubozu"])
    r = ev.iloc[0]
    assert r["ret_1d"] < 0 and r["dir_1d"] == pytest.approx(-r["ret_1d"])
    assert r["mae_1d"] == pytest.approx(-(101 / 100 - 1))


def test_events_unchanged_by_future_rows(synth):
    a = pv.stock_events(synth, "X", horizons=(1,))
    b = pv.stock_events(synth.iloc[:600], "X", horizons=(1,))
    cutoff = synth.index[598]
    left = a[a["Date"] < cutoff][["Date", "Pattern", "ret_1d"]].reset_index(drop=True)
    right = b[b["Date"] < cutoff][["Date", "Pattern", "ret_1d"]].reset_index(drop=True)
    pd.testing.assert_frame_equal(left, right)


def test_summary_and_oos_split(synth):
    bench = synth["Close"] * 1.0
    ev = pv.stock_events(synth, "X", bench_close=bench, oos_fraction=0.3)
    split = synth.index[int(len(synth) * 0.7)]
    assert (ev.loc[ev["Period"] == "In-sample", "Date"] < split).all()
    assert (ev.loc[ev["Period"] == "Out-of-sample", "Date"] >= split).all()
    s = pv.summarise(ev, {"X": pv.base_rates(synth)}, 5)
    d = s[s["Bias"].isin(["Bullish", "Bearish"])]
    assert ((d["Hit rate CI low"] <= d["Hit rate"]) & (d["Hit rate"] <= d["Hit rate CI high"])).all()
    assert "q-value (BH)" in s
    assert set(s.apply(pv.verdict, axis=1)) <= {"Edge, survives costs", "Edge before costs only", "Worse than chance", "No reliable edge",
                                               "Too few cases to judge", "Larger moves follow", "No reliable difference", "Not enough data"}
    assert len(pv.oos_comparison(ev, {"X": pv.base_rates(synth)}, 5))


def test_regimes_and_rolling_corr_causal(synth):
    c = synth["Close"]
    full = pv.market_regime(c)
    part = pv.market_regime(c.iloc[:500])
    assert (full.iloc[:500] == part).all()
    rc_full = pv.rolling_corr(c, c * 1.01)
    assert rc_full.dropna().round(6).eq(1.0).all()


# ----------------------------------------------------------------- correlation
def _panel(rho=0.6, n=800, seed=1):
    rng = np.random.default_rng(seed)
    x = rng.normal(0, 0.01, n)
    y = rho * x + math.sqrt(1 - rho**2) * rng.normal(0, 0.01, n)
    idx = pd.bdate_range("2020-01-01", periods=n)
    return pd.DataFrame({"B": x, "A": y}, index=idx)


def test_vs_benchmark_ci_contains_truth():
    r = co.vs_benchmark(_panel(0.6), "B").iloc[0]
    assert r["CI low"] < 0.6 < r["CI high"] and r["Observations"] == 800 and r["p-value"] < 1e-6
    assert r["Beta"] == pytest.approx(r["Correlation"] * _panel().A.std() / _panel().B.std(), rel=1e-6)


def test_pairwise_alignment_no_fill():
    idx = pd.bdate_range("2024-01-01", periods=6)
    closes = {"A": pd.Series([1, 2, 3, 4, 5, 6.0], idx), "B": pd.Series([1, 2, 4, 8.0], idx[[0, 1, 3, 5]])}
    r = co.returns_panel(closes)
    assert r["B"].isna().sum() >= 2              # no forward-filled zero returns
    assert co.pair_n(r).loc["A", "B"] == r.dropna().shape[0]


def test_fisher_diff_and_regimes():
    assert co.fisher_diff_test(0.8, 500, 0.2, 500) < 1e-6
    assert co.fisher_diff_test(0.5, 500, 0.5, 500) == pytest.approx(1.0)
    p = _panel(0.5)
    reg = pd.Series(np.where(np.arange(len(p)) < 400, "Bullish", "Bearish"), index=p.index)
    br = co.by_regime(p, reg, "B")
    assert set(br["Regime"]) == {"Bullish", "Bearish"} and br["Observations"].sum() == len(p)


def test_portfolio_diversification_math():
    rng = np.random.default_rng(3)
    p = pd.DataFrame(rng.normal(0, 0.01, (5000, 4)), columns=list("WXYZ"), index=pd.bdate_range("2000-01-01", periods=5000))
    res = co.portfolio_risk(p)
    assert res["diversification_ratio"] == pytest.approx(2.0, rel=0.05)     # √4 for independent equal-vol assets
    one = co.portfolio_risk(p, corr=pd.DataFrame(1.0, index=p.columns, columns=p.columns))
    assert one["diversification_ratio"] == pytest.approx(1.0, rel=1e-6)    # perfect correlation: no benefit


# ----------------------------------------------------------------- spreads (user data only)
def test_spread_parsing_and_formulas():
    csv = "Date,Contract,Close\n" + "\n".join(
        f"2024-01-{d:02d},{c},{v}" for d in range(1, 11) for c, v in (("M1", 95 + d * 0.01), ("M2", 95.2), ("M3", 95.5)))
    wide, msgs = spreads.parse_contracts(csv)
    assert list(wide.columns) == ["M1", "M2", "M3"] and len(wide) == 10
    cal = spreads.calendar_spread(wide, "M1", "M2")
    assert cal.iloc[0] == pytest.approx(95.01 - 95.2)
    bf = spreads.butterfly(wide, "M1", "M2", "M3")
    assert bf.iloc[0] == pytest.approx(95.01 - 2 * 95.2 + 95.5)
    assert any("Only" in m for m in msgs)
    with pytest.raises(ValueError):
        spreads.parse_contracts("Date,Price\n2024-01-01,1")
    tpl, _ = spreads.parse_contracts(spreads.TEMPLATE)
    assert tpl.shape[1] == 3
