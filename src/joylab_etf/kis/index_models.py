from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel


class IndexQuote(BaseModel):
    index_code: str
    price: float | None = None
    change_pct: float
    timestamp: datetime
