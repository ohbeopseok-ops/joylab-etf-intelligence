from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel,Field

class FlowSnapshot(BaseModel):
    foreign_net_qty:int|None=None
    institution_net_qty:int|None=None
    source_time:str|None=None
    confidence:str="UNKNOWN"

class StockSnapshot(BaseModel):
    ticker:str
    name:str
    price:int
    change_pct:float
    volume:int|None=None
    relative_to_kospi:float|None=None
    relative_to_peer:float|None=None
    flow:FlowSnapshot=Field(default_factory=FlowSnapshot)

class MarketSnapshot(BaseModel):
    timestamp:datetime
    source:str
    kospi:float
    kospi_change_pct:float
    stocks:list[StockSnapshot]

class Decision(BaseModel):
    ticker:str
    name:str
    action:str
    label:str
    score:int
    reasons:list[str]
    quantity_candidate:int|None=None

class DecisionPack(BaseModel):
    timestamp:datetime
    market_action:str
    decisions:list[Decision]
