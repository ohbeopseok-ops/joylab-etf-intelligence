from __future__ import annotations

from pydantic import BaseModel


class AccountPosition(BaseModel):
    symbol: str
    name: str
    quantity: float
    sellable_quantity: float | None = None
    avg_price: float | None = None
    purchase_amount: float | None = None
    current_price: float | None = None
    market_value: float | None = None
    profit_loss: float | None = None
    profit_loss_pct: float | None = None


class AccountSummary(BaseModel):
    cash: float | None = None
    securities_value: float | None = None
    total_evaluation: float | None = None
    net_asset: float | None = None
    total_purchase_amount: float | None = None
    total_profit_loss: float | None = None
