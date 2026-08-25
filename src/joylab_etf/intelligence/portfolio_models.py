from __future__ import annotations

from pydantic import BaseModel, Field


class PositionInput(BaseModel):
    symbol: str
    name: str
    quantity: float = Field(ge=0)
    type: str


class PositionValuation(BaseModel):
    symbol: str
    name: str
    quantity: float
    price: int
    market_value: float
    type: str


class ExposureRow(BaseModel):
    symbol: str
    name: str
    direct_value: float = 0
    indirect_value: float = 0

    @property
    def total_value(self) -> float:
        return round(self.direct_value + self.indirect_value, 2)


class PortfolioExposureReport(BaseModel):
    total_portfolio_value: float
    exposures: list[ExposureRow]
    cluster_values: dict[str, float]
    cluster_weights_pct: dict[str, float]
