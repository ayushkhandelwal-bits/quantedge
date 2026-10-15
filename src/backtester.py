"""Event-driven daily backtester with explicit execution timing and per-side costs.

Design:

* **Execution timing.** A target decided at the close of day t is filled at the OPEN of day
  t+1 (default ``execution="next_open"``). Filling at the close of the same bar that produced
  the signal is optimistic; that convention is available as ``"same_close"`` for comparison
  and is labelled as such in the UI.
* **Costs per side** (buy costs at entry, sell costs at exit) plus slippage on the fill price.
* **Integer share quantities** and an explicit end-of-data liquidation rule.
* **Shorting is optional.** Overnight short selling of Indian cash equities is not generally
  available to retail investors, so by default short signals are treated as "go flat".
* Gross P&L, charges and slippage are tracked separately so gross vs net can be reported.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from src.transaction_costs import CostSchedule, fill_price, order_charges


@dataclass
class BacktestConfig:
    initial_capital: float = 1_000_000.0
    allocation: float = 1.0                 # fraction of current equity deployed per position
    allow_short: bool = False
    execution: str = "next_open"            # next_open | same_close | open_to_close
    costs: CostSchedule = field(default_factory=CostSchedule)
    whole_shares: bool = True


@dataclass
class BacktestResult:
    equity: pd.DataFrame          # Date-indexed: equity, cash, position, gross_equity, costs_cum, exposure
    trades: pd.DataFrame          # one row per round trip
    config: BacktestConfig
    signals: pd.DataFrame         # target/reason as supplied (after short filtering)

    @property
    def curve(self) -> pd.Series:
        return self.equity["equity"]


TRADE_COLS = ["Direction", "Entry date", "Entry price", "Exit date", "Exit price", "Quantity", "Holding days",
              "Gross P&L", "Charges", "Slippage", "Net P&L", "Return %", "Entry reason", "Exit reason"]


def run_backtest(df: pd.DataFrame, signals: pd.DataFrame, cfg: BacktestConfig | None = None) -> BacktestResult:
    cfg = cfg or BacktestConfig()
    if df.empty:
        raise ValueError("No price data to backtest")
    sig = signals.reindex(df.index)
    target = sig["target"].fillna(0).astype(int)
    if not cfg.allow_short:
        target = target.clip(lower=0)
    reasons = sig["reason"].fillna("") if "reason" in sig else pd.Series("", index=df.index)
    if cfg.execution == "open_to_close":
        return _run_intraday(df, target, reasons, cfg)

    cs = cfg.costs
    o = df["Open"].to_numpy(float)
    c = df["Close"].to_numpy(float)
    dates = df.index
    n = len(df)

    cash, qty, direction = cfg.initial_capital, 0.0, 0
    entry = None   # dict of open-trade details
    costs_cum = 0.0
    gross_pnl_cum = 0.0
    trades, rows = [], []

    def open_pos(i, px_ref, d, why):
        nonlocal cash, qty, direction, entry, costs_cum
        equity_now = cash  # flat when opening
        side = "buy" if d > 0 else "sell"
        px = fill_price(px_ref, side, cs)
        budget = equity_now * cfg.allocation
        q = budget / (px * (1 + 0.002))      # small headroom for charges
        q = math.floor(q) if cfg.whole_shares else q
        if q <= 0:
            return
        ch = order_charges(side, px, q, "delivery", cs)
        slip = abs(px - px_ref) * q
        if d > 0:
            cash -= px * q + ch["total"]
        else:
            cash += px * q - ch["total"]
        qty, direction = q, d
        costs_cum += ch["total"] + slip
        entry = {"i": i, "date": dates[i], "ref": px_ref, "px": px, "q": q, "charges": ch["total"], "slip": slip, "why": why}

    def close_pos(i, px_ref, why):
        nonlocal cash, qty, direction, entry, costs_cum, gross_pnl_cum
        side = "sell" if direction > 0 else "buy"
        px = fill_price(px_ref, side, cs)
        ch = order_charges(side, px, qty, "delivery", cs)
        slip = abs(px - px_ref) * qty
        if direction > 0:
            cash += px * qty - ch["total"]
        else:
            cash -= px * qty + ch["total"]
        gross = (px_ref - entry["ref"]) * qty * direction
        charges = entry["charges"] + ch["total"]
        slippage = entry["slip"] + slip
        net = gross - charges - slippage
        costs_cum += ch["total"] + slip
        gross_pnl_cum += gross
        trades.append({"Direction": "Long" if direction > 0 else "Short", "Entry date": entry["date"],
                       "Entry price": entry["px"], "Exit date": dates[i], "Exit price": px, "Quantity": qty,
                       "Holding days": (dates[i] - entry["date"]).days, "Gross P&L": gross, "Charges": charges,
                       "Slippage": slippage, "Net P&L": net,
                       "Return %": net / (entry["px"] * qty) * 100, "Entry reason": entry["why"], "Exit reason": why})
        qty, direction, entry = 0.0, 0, None

    pending = 0          # target decided at previous close, to execute at today's open
    pending_reason = ""
    for i in range(n):
        if cfg.execution == "next_open" and i > 0 and pending != direction:
            if direction != 0:
                close_pos(i, o[i], "Signal" if pending == 0 else "Reversal")
            if pending != 0:
                open_pos(i, o[i], pending, pending_reason or "Signal")
        if cfg.execution == "same_close" and target.iloc[i] != direction:
            if direction != 0:
                close_pos(i, c[i], "Signal" if target.iloc[i] == 0 else "Reversal")
            if target.iloc[i] != 0:
                open_pos(i, c[i], int(target.iloc[i]), reasons.iloc[i] or "Signal")
        if i == n - 1 and direction != 0:
            close_pos(i, c[i], "End of data (forced exit)")
        mtm = qty * c[i] * direction if direction != 0 else 0.0
        equity = cash + mtm
        rows.append({"Date": dates[i], "equity": equity, "cash": cash, "position": direction * qty,
                     "exposure": abs(mtm) / equity if equity > 0 else 0.0, "costs_cum": costs_cum})
        pending = int(target.iloc[i])
        pending_reason = reasons.iloc[i]

    eq = pd.DataFrame(rows).set_index("Date")
    eq["gross_equity"] = eq["equity"] + eq["costs_cum"]
    tr = pd.DataFrame(trades, columns=TRADE_COLS)
    return BacktestResult(eq, tr, cfg, pd.DataFrame({"target": target, "reason": reasons}))


def _run_intraday(df, target, reasons, cfg: BacktestConfig) -> BacktestResult:
    """Open-to-close execution for same-session strategies (Gap Fill): enter at the open of
    the signal day (the signal only uses that open and the previous close), exit at its close.
    Intraday cost schedule applies; intraday shorting is permitted in Indian cash equities, so
    short signals are honoured only if ``allow_short`` is set."""
    cs = cfg.costs
    cash = cfg.initial_capital
    costs_cum = 0.0
    trades, rows = [], []
    for i, d in enumerate(df.index):
        t = int(target.iloc[i])
        o, cl = float(df["Open"].iloc[i]), float(df["Close"].iloc[i])
        mtm_note = 0.0
        if t != 0 and i > 0:
            side_in, side_out = ("buy", "sell") if t > 0 else ("sell", "buy")
            px_in, px_out = fill_price(o, side_in, cs), fill_price(cl, side_out, cs)
            q = cash * cfg.allocation / (px_in * 1.002)
            q = math.floor(q) if cfg.whole_shares else q
            if q > 0:
                ch = order_charges(side_in, px_in, q, "intraday", cs)["total"] + order_charges(side_out, px_out, q, "intraday", cs)["total"]
                slip = (abs(px_in - o) + abs(px_out - cl)) * q
                gross = (cl - o) * q * t
                net = gross - ch - slip
                cash += net
                costs_cum += ch + slip
                trades.append({"Direction": "Long" if t > 0 else "Short", "Entry date": d, "Entry price": px_in,
                               "Exit date": d, "Exit price": px_out, "Quantity": q, "Holding days": 0,
                               "Gross P&L": gross, "Charges": ch, "Slippage": slip, "Net P&L": net,
                               "Return %": net / (px_in * q) * 100, "Entry reason": reasons.iloc[i] or "Gap",
                               "Exit reason": "Session close"})
                mtm_note = 1.0
        rows.append({"Date": d, "equity": cash, "cash": cash, "position": 0.0, "exposure": mtm_note, "costs_cum": costs_cum})
    eq = pd.DataFrame(rows).set_index("Date")
    eq["gross_equity"] = eq["equity"] + eq["costs_cum"]
    return BacktestResult(eq, pd.DataFrame(trades, columns=TRADE_COLS), cfg,
                          pd.DataFrame({"target": target, "reason": reasons}))


def buy_and_hold_curve(close: pd.Series, capital: float) -> pd.Series:
    """Frictionless buy-and-hold value of ``capital`` (benchmark line)."""
    close = close.dropna()
    return (close / close.iloc[0] * capital).rename("Benchmark")
