from __future__ import annotations

from pydantic import BaseModel


class InvestorFlowSnapshot(BaseModel):
    symbol: str
    business_date: str
    individual_net_buy_qty: int
    foreign_net_buy_qty: int
    institution_net_buy_qty: int
