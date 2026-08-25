from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel

class MarketQuote(BaseModel):
    symbol: str
    price: int
    change: int | None = None
    change_pct: float | None = None
    volume: int | None = None
    source: str = "KIS"
    timestamp: datetime
