from __future__ import annotations

from pydantic import BaseModel, Field


class PortfolioGatePolicy(BaseModel):
    single_stock_max_pct_of_total_account: float = Field(gt=0, le=100)
    cluster_max_pct_of_total_account: dict[str, float]
    split_buy: list[float]
    default_split_stage: int = 1
    use_no_credit_buying_power: bool = True
    minimum_order_qty: int = 1


class GateInput(BaseModel):
    symbol: str
    name: str
    current_price: float
    direct_value: float
    indirect_value: float
    true_exposure_value: float
    total_account_value: float
    securities_value: float
    cluster_name: str
    cluster_value: float
    kis_buyable_qty: int
    kis_buyable_amount: float


class GateResult(BaseModel):
    symbol: str
    name: str

    current_price: float

    true_exposure_before: float
    true_weight_before_pct: float

    cluster_value_before: float
    cluster_weight_before_pct: float

    single_stock_room_value: float
    single_stock_room_qty: int

    cluster_room_value: float
    cluster_room_qty: int

    kis_buyable_qty: int
    split_stage: int
    split_fraction: float
    split_allowed_qty: int

    final_allowed_qty: int
    buy_amount: float

    true_exposure_after: float
    true_weight_after_pct: float

    cluster_value_after: float
    cluster_weight_after_pct: float

    action: str
    blocking_reasons: list[str]
