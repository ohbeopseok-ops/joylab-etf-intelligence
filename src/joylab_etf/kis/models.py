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
    # Valuation fields -- same inquire-price response as the quote itself,
    # no extra KIS call. per/pbr are KIS's own precomputed values (not
    # re-derived from price/eps here); eps/bps/52-week range are kept
    # alongside so a 52-week PER/PBR band can be computed downstream.
    per: float | None = None
    pbr: float | None = None
    eps: float | None = None
    bps: float | None = None
    week52_high: float | None = None
    week52_low: float | None = None
