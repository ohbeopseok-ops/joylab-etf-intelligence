from __future__ import annotations

from datetime import datetime
from enum import Enum
from pydantic import BaseModel


class FlowStatus(str, Enum):
    ESTIMATED = "estimated"
    CONFIRMED = "confirmed"
    UNAVAILABLE = "unavailable"


class SignalConfidence(str, Enum):
    PRIMARY = "primary"
    AUXILIARY = "auxiliary"
    NONE = "none"


class InvestorFlowSnapshot(BaseModel):
    symbol: str
    name: str | None = None
    market: str = "KRX"

    foreign_net_buy_qty: int | None = None
    foreign_net_buy_amount: int | None = None
    institution_net_buy_qty: int | None = None
    institution_net_buy_amount: int | None = None
    individual_net_buy_qty: int | None = None
    individual_net_buy_amount: int | None = None

    status: FlowStatus
    confidence: SignalConfidence = SignalConfidence.PRIMARY
    source: str = "KIS"
    source_tr_id: str
    observed_at: datetime
    source_updated_at: datetime | None = None
    is_stale: bool = False
    stale_minutes: int | None = None


class ProgramTradeSnapshot(BaseModel):
    symbol: str
    market: str = "KRX"
    program_net_buy_qty: int | None = None
    program_net_buy_amount: int | None = None
    source: str = "KIS"
    source_tr_id: str = "FHPPG04650101"
    observed_at: datetime
    confidence: SignalConfidence = SignalConfidence.AUXILIARY


class AuxiliaryFlowSignal(BaseModel):
    symbol: str
    program_trade: ProgramTradeSnapshot | None = None
    foreign_broker_net_buy_qty: int | None = None
    foreign_broker_net_buy_amount: int | None = None
    observed_at: datetime

    # 외국계 창구는 외국인 전체 수급과 동일하지 않으므로 보조 신호로만 사용한다.
    confidence: SignalConfidence = SignalConfidence.AUXILIARY
