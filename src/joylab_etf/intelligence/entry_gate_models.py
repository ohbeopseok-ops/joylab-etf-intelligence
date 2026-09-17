from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, Field


class EntryDecision(str, Enum):
    READY = "ready"
    WAIT = "wait"
    NO_ENTRY = "no_entry"


class EntryGateInput(BaseModel):
    symbol: str
    name: str | None = None
    current_price: float
    trigger_price: float
    hold_minutes: int = 0

    foreign_net_buy_amount: int | None = None
    institution_net_buy_amount: int | None = None
    investor_flow_status: str = "unavailable"
    investor_flow_stale: bool = False

    program_net_buy_amount: int | None = None

    volume_ratio: float | None = None
    relative_strength_pct: float | None = None
    sector_relative_strength_pct: float | None = None
    macro_regime_score: int = Field(default=0, ge=0, le=10)


class EntryGateResult(BaseModel):
    symbol: str
    total_score: int
    decision: EntryDecision
    primary_flow_confirmed: bool
    auxiliary_positive: bool
    blocking_reasons: list[str] = []
    score_breakdown: dict[str, int]
