from __future__ import annotations
from pydantic import BaseModel


class BuyingPower(BaseModel):
    symbol: str
    reference_price: float
    order_possible_cash: float | None = None
    no_credit_buy_amount: float | None = None
    no_credit_buy_qty: float | None = None
    max_buy_amount: float | None = None
    max_buy_qty: float | None = None
    calc_price: float | None = None
