"""Indian equity transaction costs, computed per order side.

Components: brokerage, Securities Transaction Tax, exchange transaction charge, SEBI fee,
stamp duty, GST and depository (DP) charges.

* Rates are configurable (``CostSchedule``) and shown in the UI, because statutory and broker
  rates change. Defaults were checked against Zerodha's published charges page
  (https://zerodha.com/charges) in October 2026: NSE transaction charge 0.00307%, stamp duty
  on delivery buys 0.015%, DP charge ₹15.34 per scrip sold from demat.
* Costs are computed per side (buy at entry, sell at exit) so the equity curve reflects
  costs when they are actually paid, instead of only at the exit.
* Slippage is modelled separately as an adverse fill-price adjustment (basis points).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

SOURCE_NOTE = "Rates per zerodha.com/charges (checked Oct 2026). Approximations; verify before relying on them."


@dataclass
class CostSchedule:
    brokerage_delivery_flat: float = 0.0         # ₹ per order (retail delivery = zero at Zerodha)
    brokerage_intraday_flat: float = 20.0        # ₹ per order cap
    brokerage_intraday_pct: float = 0.0003       # 0.03% of order value, whichever lower
    stt_delivery: float = 0.001                  # 0.1% buy and sell
    stt_intraday_sell: float = 0.00025           # 0.025% sell side only
    exchange_txn: float = 0.0000307              # NSE 0.00307% of turnover
    sebi_fee: float = 0.000001                   # ₹10 per crore
    stamp_delivery_buy: float = 0.00015          # 0.015% buy side
    stamp_intraday_buy: float = 0.00003          # 0.003% buy side
    gst: float = 0.18                            # on brokerage + exchange + SEBI
    dp_charge_per_sell: float = 15.34            # ₹ per scrip per delivery sell
    slippage_bps: float = 5.0                    # adverse fill vs reference price, basis points
    enabled: bool = True                         # False -> frictionless (for cost-impact comparison)

    def scaled(self, factor: float) -> "CostSchedule":
        """Every charge multiplied by ``factor`` (used for cost-sensitivity analysis)."""
        d = asdict(self)
        for k, v in d.items():
            if isinstance(v, float) and k != "gst":
                d[k] = v * factor
        return CostSchedule(**d)

    @staticmethod
    def zero() -> "CostSchedule":
        return CostSchedule(enabled=False, slippage_bps=0.0)


def order_charges(side: str, price: float, qty: float, product: str, cs: CostSchedule) -> dict:
    """Statutory + broker charges for ONE order.

    side: "buy" | "sell";  product: "delivery" | "intraday"
    Returns the components and their total in ₹ (slippage excluded; see ``slippage_cost``).
    """
    zero = {"brokerage": 0.0, "stt": 0.0, "exchange": 0.0, "sebi": 0.0, "stamp": 0.0, "gst": 0.0, "dp": 0.0, "total": 0.0}
    if not cs.enabled or qty <= 0:
        return zero
    value = price * qty
    if product == "intraday":
        brokerage = min(cs.brokerage_intraday_flat, value * cs.brokerage_intraday_pct)
        stt = value * cs.stt_intraday_sell if side == "sell" else 0.0
        stamp = value * cs.stamp_intraday_buy if side == "buy" else 0.0
        dp = 0.0
    else:
        brokerage = cs.brokerage_delivery_flat
        stt = value * cs.stt_delivery
        stamp = value * cs.stamp_delivery_buy if side == "buy" else 0.0
        dp = cs.dp_charge_per_sell if side == "sell" else 0.0
    exchange = value * cs.exchange_txn
    sebi = value * cs.sebi_fee
    gst = (brokerage + exchange + sebi) * cs.gst
    total = brokerage + stt + exchange + sebi + stamp + gst + dp
    return {"brokerage": brokerage, "stt": stt, "exchange": exchange, "sebi": sebi, "stamp": stamp,
            "gst": gst, "dp": dp, "total": total}


def fill_price(ref_price: float, side: str, cs: CostSchedule) -> float:
    """Adverse fill: buys pay more, sells receive less, by ``slippage_bps``."""
    adj = cs.slippage_bps / 10_000 if cs.enabled else 0.0
    return ref_price * (1 + adj) if side == "buy" else ref_price * (1 - adj)


def round_trip_cost_pct(price: float, qty: float, cs: CostSchedule, product: str = "delivery") -> float:
    """Charges + slippage for a buy and a sell at the same price, as % of one side's value."""
    if qty <= 0 or price <= 0:
        return 0.0
    b = order_charges("buy", price, qty, product, cs)["total"]
    s = order_charges("sell", price, qty, product, cs)["total"]
    slip = 2 * price * qty * (cs.slippage_bps / 10_000 if cs.enabled else 0)
    return (b + s + slip) / (price * qty) * 100
