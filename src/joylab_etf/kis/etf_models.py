from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class ETFConstituent(BaseModel):
    symbol: str
    name: str
    weight_pct: float = Field(ge=0)
    valuation_amount: float | None = None
    current_price: int | None = None


class ETFComponentSnapshot(BaseModel):
    etf_symbol: str
    source: str = "KIS"
    timestamp: datetime
    constituents: list[ETFConstituent]

    @property
    def weight_sum(self) -> float:
        return round(sum(item.weight_pct for item in self.constituents), 6)

    def find(self, symbol: str) -> ETFConstituent | None:
        for item in self.constituents:
            if item.symbol == symbol:
                return item
        return None
