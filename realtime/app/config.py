from __future__ import annotations
import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

ROOT=Path(__file__).resolve().parents[1]
load_dotenv(ROOT/".env")

@dataclass(frozen=True)
class Settings:
    app_key:str=os.getenv("KIS_APP_KEY","").strip()
    app_secret:str=os.getenv("KIS_APP_SECRET","").strip()
    data_mode:str=os.getenv("DATA_MODE","mock").strip().lower()
    poll_ms:int=int(os.getenv("POLL_MS","3000"))
    read_only:bool=os.getenv("READ_ONLY","true").lower()=="true"
    order_enabled:bool=os.getenv("ORDER_ENABLED","false").lower()=="true"
    @property
    def base_url(self)->str:
        return "https://openapi.koreainvestment.com:9443"
    def validate_safety(self)->None:
        if not self.read_only: raise RuntimeError("READ_ONLY must remain true")
        if self.order_enabled: raise RuntimeError("ORDER_ENABLED must remain false")
        if self.data_mode=="real" and (not self.app_key or not self.app_secret):
            raise RuntimeError("DATA_MODE=real requires KIS_APP_KEY/KIS_APP_SECRET")
settings=Settings()
