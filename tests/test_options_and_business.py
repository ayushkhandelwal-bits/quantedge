import math

import numpy as np
import pytest

from src import options_pricing as op
from src.business_outcomes import Thresholds, evaluate

S, K, T, r, v = 100.0, 100.0, 1.0, 0.05, 0.20


def test_bs_textbook_value():
    # Hull: S=K=100, T=1, r=5%, σ=20% → call ≈ 10.4506, put ≈ 5.5735
    assert op.bs_price(S, K, T, r, v, "call") == pytest.approx(10.4506, abs=1e-3)
    assert op.bs_price(S, K, T, r, v, "put") == pytest.approx(5.5735, abs=1e-3)


@pytest.mark.parametrize("q", [0.0, 0.02])
def test_put_call_parity(q):
    c = op.bs_price(S, 95, 0.5, r, 0.3, "call", q)
    p = op.bs_price(S, 95, 0.5, r, 0.3, "put", q)
    assert c - p == pytest.approx(S * math.exp(-q * 0.5) - 95 * math.exp(-r * 0.5), abs=1e-9)


def test_matches_reference_black76():
    F = S * math.exp(r * T)
    assert op.black76_price(F, K, T, r, v, "call") == pytest.approx(op.bs_price(S, K, T, r, v, "call"), abs=1e-4)


def test_greeks_against_finite_differences():
    h = 1e-3
    g = op.greeks(S, 105, 0.5, r, v, "call", 0.01)
    f = lambda **kw: op.bs_price(kw.get("S", S), 105, kw.get("T", 0.5), kw.get("r", r), kw.get("v", v), "call", 0.01)  # noqa: E731
    assert g["delta"] == pytest.approx((f(S=S + h) - f(S=S - h)) / (2 * h), rel=1e-4)
    assert g["gamma"] == pytest.approx((f(S=S + h) - 2 * f() + f(S=S - h)) / h**2, rel=1e-2)
    assert g["vega"] == pytest.approx((f(v=v + h) - f(v=v - h)) / (2 * h) / 100, rel=1e-4)
    assert g["rho"] == pytest.approx((f(r=r + h) - f(r=r - h)) / (2 * h) / 100, rel=1e-4)
    assert g["theta"] == pytest.approx(-(f(T=0.5 + h) - f(T=0.5 - h)) / (2 * h) / 365, rel=1e-3)
    gp = op.greeks(S, 105, 0.5, r, v, "put", 0.01)
    assert 0 < g["delta"] < 1 and -1 < gp["delta"] < 0 and g["gamma"] == pytest.approx(gp["gamma"])


def test_implied_vol_round_trip_and_bounds():
    px = op.bs_price(S, 110, 0.25, r, 0.35, "put")
    assert op.implied_vol(px, S, 110, 0.25, r, "put") == pytest.approx(0.35, abs=1e-6)
    assert op.implied_vol(0.0001, S, 50, 0.25, r, "call") is None     # below intrinsic → no solution


def test_payoff_analysis_known_shapes():
    legs = [op.Leg("call", +1, 100, 5.0)]
    a = op.analyse_payoff(legs, 100)
    assert a["max_profit"] is None and a["max_loss"] == pytest.approx(-5.0)
    assert a["breakevens"] == [pytest.approx(105.0, abs=0.05)]
    spread = [op.Leg("call", +1, 100, 6.0), op.Leg("call", -1, 110, 2.0)]
    s = op.analyse_payoff(spread, 100)
    assert s["max_profit"] == pytest.approx(6.0) and s["max_loss"] == pytest.approx(-4.0)
    assert s["net_premium"] == pytest.approx(-4.0)
    straddle = op.build_strategy("Long straddle", 100, 0.25, r, 0.2)
    st = op.analyse_payoff(straddle, 100)
    assert len(st["breakevens"]) == 2 and st["max_profit"] is None
    for name in op.PRESETS:
        res = op.analyse_payoff(op.build_strategy(name, 100, 0.25, r, 0.2), 100)
        assert np.isfinite(res["profit"]).all()


def _m(**kw):
    base = {"total_return": 0.4, "sharpe": 1.2, "max_drawdown": 0.15, "trades": 30, "gross_pnl": 100000,
            "total_costs": 10000, "turnover": 5e6}
    return base | kw


class WF:
    oos_sharpe_avg, degradation = 0.8, 0.7


def test_classification_rules():
    assert evaluate(_m(), 0.2, WF(), Thresholds(), False)["label"] == "Worth further investigation"
    assert evaluate(_m(total_return=-0.1), 0.2, WF(), Thresholds(), False)["label"].startswith("Weak")
    assert evaluate(_m(max_drawdown=0.5), 0.2, WF(), Thresholds(), False)["label"] == "Requires more validation"
    assert evaluate(_m(), 0.2, WF(), Thresholds(), True)["label"].startswith("Not assessable")
    out = evaluate(_m(trades=3), 0.2, None, Thresholds(), False)
    assert out["label"] == "Requires more validation"
    assert any(c["Result"] == "n/a" for c in out["criteria"])
