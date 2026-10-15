"""European option pricing, Greeks, implied volatility and multi-leg payoffs.

Model: Black–Scholes–Merton with continuous dividend yield q (spot-based, European exercise).
A Black-76 model (futures-based) from ``src/reference/options_backtester.py`` (third-party,
MIT-licensed; see ``src/reference/LICENSE``) is exposed as ``black76_price`` and cross-checked in the tests: with F = S·e^{(r−q)T} both
models give the same price.

ALL VALUES HERE ARE THEORETICAL MODEL OUTPUTS, not exchange-traded prices.

Units
-----
* T in years (calendar days / 365); σ, r, q as decimals per year.
* Delta: change in option value per ₹1 change in the underlying.
* Gamma: change in delta per ₹1 change in the underlying.
* Theta: change in value per calendar day (negative = time decay).
* Vega: change in value per 1 percentage-point change in volatility.
* Rho: change in value per 1 percentage-point change in the risk-free rate.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy.optimize import brentq
from scipy.stats import norm

from src.reference.options_backtester import BlackModel


def _d1d2(S, K, T, r, sigma, q):
    d1 = (math.log(S / K) + (r - q + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
    return d1, d1 - sigma * math.sqrt(T)


def bs_price(S: float, K: float, T: float, r: float, sigma: float, kind: str = "call", q: float = 0.0) -> float:
    if T <= 0 or sigma <= 0:
        fwd_intr = max(0.0, S - K) if kind == "call" else max(0.0, K - S)
        return fwd_intr if T <= 0 else max(0.0, (S * math.exp(-q * T) - K * math.exp(-r * T)) * (1 if kind == "call" else -1))
    d1, d2 = _d1d2(S, K, T, r, sigma, q)
    if kind == "call":
        return S * math.exp(-q * T) * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)
    return K * math.exp(-r * T) * norm.cdf(-d2) - S * math.exp(-q * T) * norm.cdf(-d1)


def greeks(S, K, T, r, sigma, kind="call", q=0.0) -> dict:
    if T <= 0 or sigma <= 0:
        itm = (S > K) if kind == "call" else (S < K)
        return {"delta": (1.0 if itm else 0.0) * (1 if kind == "call" else -1), "gamma": 0.0, "theta": 0.0, "vega": 0.0, "rho": 0.0}
    d1, d2 = _d1d2(S, K, T, r, sigma, q)
    pdf = norm.pdf(d1)
    disc_q, disc_r = math.exp(-q * T), math.exp(-r * T)
    gamma = disc_q * pdf / (S * sigma * math.sqrt(T))
    vega = S * disc_q * pdf * math.sqrt(T) / 100
    if kind == "call":
        delta = disc_q * norm.cdf(d1)
        theta = (-S * disc_q * pdf * sigma / (2 * math.sqrt(T)) - r * K * disc_r * norm.cdf(d2) + q * S * disc_q * norm.cdf(d1)) / 365
        rho = K * T * disc_r * norm.cdf(d2) / 100
    else:
        delta = -disc_q * norm.cdf(-d1)
        theta = (-S * disc_q * pdf * sigma / (2 * math.sqrt(T)) + r * K * disc_r * norm.cdf(-d2) - q * S * disc_q * norm.cdf(-d1)) / 365
        rho = -K * T * disc_r * norm.cdf(-d2) / 100
    return {"delta": delta, "gamma": gamma, "theta": theta, "vega": vega, "rho": rho}


def implied_vol(price: float, S, K, T, r, kind="call", q=0.0) -> float | None:
    """Volatility that reproduces ``price`` under BSM (Brent root-finding on [0.1%, 500%]).
    Returns None when the price is outside no-arbitrage bounds."""
    if T <= 0 or price <= 0:
        return None
    lo_px = bs_price(S, K, T, r, 1e-3, kind, q)
    hi_px = bs_price(S, K, T, r, 5.0, kind, q)
    if not (lo_px - 1e-9 <= price <= hi_px + 1e-9):
        return None
    try:
        return brentq(lambda s: bs_price(S, K, T, r, s, kind, q) - price, 1e-3, 5.0, xtol=1e-8)
    except ValueError:
        return None


def black76_price(F, K, T, r, sigma, kind="call") -> float:
    """Black-76 implementation from src/reference (unchanged)."""
    return BlackModel.price(F, K, T, r, sigma, kind)


# --------------------------------------------------------------------------- payoffs
@dataclass
class Leg:
    kind: str          # "call" | "put" | "stock"
    side: int          # +1 long, -1 short
    strike: float = 0.0
    premium: float = 0.0   # per unit; for stock = purchase price
    qty: float = 1.0

    def payoff(self, ST: np.ndarray) -> np.ndarray:
        if self.kind == "call":
            v = np.maximum(ST - self.strike, 0)
        elif self.kind == "put":
            v = np.maximum(self.strike - ST, 0)
        else:
            v = ST
        return self.side * self.qty * v

    def profit(self, ST: np.ndarray) -> np.ndarray:
        return self.payoff(ST) - self.side * self.qty * self.premium

    def value(self, S, T, r, sigma, q=0.0) -> float:
        if self.kind == "stock":
            return self.side * self.qty * S
        return self.side * self.qty * bs_price(S, self.strike, T, r, sigma, self.kind, q)


def build_strategy(name: str, S: float, T: float, r: float, sigma: float, q: float = 0.0,
                   k1: float | None = None, k2: float | None = None, qty: float = 1.0) -> list[Leg]:
    """Preset strategies with model (theoretical) premiums. k1 < k2 where two strikes are used."""
    atm = k1 if k1 is not None else S
    k2 = k2 if k2 is not None else atm * 1.05
    lowk, highk = min(atm, k2), max(atm, k2)
    p = lambda K, kind: bs_price(S, K, T, r, sigma, kind, q)  # noqa: E731
    if name == "Long call":
        return [Leg("call", +1, atm, p(atm, "call"), qty)]
    if name == "Long put":
        return [Leg("put", +1, atm, p(atm, "put"), qty)]
    if name == "Covered call":
        return [Leg("stock", +1, 0, S, qty), Leg("call", -1, highk, p(highk, "call"), qty)]
    if name == "Protective put":
        return [Leg("stock", +1, 0, S, qty), Leg("put", +1, lowk, p(lowk, "put"), qty)]
    if name == "Bull call spread":
        return [Leg("call", +1, lowk, p(lowk, "call"), qty), Leg("call", -1, highk, p(highk, "call"), qty)]
    if name == "Bear put spread":
        return [Leg("put", +1, highk, p(highk, "put"), qty), Leg("put", -1, lowk, p(lowk, "put"), qty)]
    if name == "Long straddle":
        return [Leg("call", +1, atm, p(atm, "call"), qty), Leg("put", +1, atm, p(atm, "put"), qty)]
    if name == "Long strangle":
        put_k, call_k = lowk * (0.95 if k1 is None else 1), highk
        return [Leg("put", +1, put_k, p(put_k, "put"), qty), Leg("call", +1, call_k, p(call_k, "call"), qty)]
    raise ValueError(f"Unknown strategy {name}")


PRESETS = ["Long call", "Long put", "Covered call", "Protective put", "Bull call spread", "Bear put spread",
           "Long straddle", "Long strangle"]


def analyse_payoff(legs: list[Leg], S: float) -> dict:
    """Net premium, max profit/loss (None if unlimited) and break-evens at expiry."""
    strikes = [l.strike for l in legs if l.kind != "stock"] + [S]
    hi = max(strikes) * 3
    grid = np.linspace(0, hi, 6001)
    prof = sum(l.profit(grid) for l in legs)
    # slope beyond the largest strike decides whether upside is bounded
    slope_up = sum((l.side * l.qty) for l in legs if l.kind in ("call", "stock"))
    net_premium = -sum(l.side * l.qty * l.premium for l in legs if l.kind != "stock")   # + credit / − debit
    max_profit = None if slope_up > 0 else float(prof.max())
    max_loss = None if slope_up < 0 else float(prof.min())
    be = []
    s = np.sign(prof)
    for i in np.where(np.diff(s) != 0)[0]:
        x0, x1, y0, y1 = grid[i], grid[i + 1], prof[i], prof[i + 1]
        be.append(float(x0 - y0 * (x1 - x0) / (y1 - y0)) if y1 != y0 else float(x0))
    be = sorted({round(b, 2) for b in be if 0 < b < hi * 0.999})
    return {"net_premium": net_premium, "max_profit": max_profit, "max_loss": max_loss, "breakevens": be,
            "grid": grid, "profit": prof}
