from __future__ import annotations
import asyncio,json,threading
from dataclasses import dataclass
from typing import Callable,Iterable
import requests,websockets
from .config import settings

@dataclass
class Tick:
    ticker:str
    price:int
    change_pct:float|None=None
    volume:int|None=None
    source_time:str|None=None

class KISWebSocketClient:
    TR_ID="H0STCNT0"
    WS_URL_REAL="ws://ops.koreainvestment.com:21000"
    def __init__(self,tickers:Iterable[str],on_tick:Callable[[Tick],None]):
        self.tickers=list(dict.fromkeys(tickers)); self.on_tick=on_tick; self.stop_evt=threading.Event(); self.thread=None
    def approval_key(self):
        r=requests.post(settings.base_url+"/oauth2/Approval",json={"grant_type":"client_credentials","appkey":settings.app_key,"secretkey":settings.app_secret},timeout=10)
        r.raise_for_status(); return r.json()["approval_key"]
    @staticmethod
    def subscription_message(key,ticker,tr_type="1"):
        return json.dumps({"header":{"approval_key":key,"custtype":"P","tr_type":tr_type,"content-type":"utf-8"},"body":{"input":{"tr_id":"H0STCNT0","tr_key":ticker}}})
    @staticmethod
    def parse_execution_message(data):
        if not data or data[0] not in {"0","1"}:return None
        p=data.split("|",3)
        if len(p)!=4 or p[1]!="H0STCNT0":return None
        v=p[3].split("^")
        if len(v)<14:return None
        try:return Tick(v[0],int(float(v[2])),float(v[5]) if v[5] else None,int(float(v[13])) if v[13] else None,v[1])
        except:return None
    async def _run(self):
        key=self.approval_key()
        async with websockets.connect(self.WS_URL_REAL,ping_interval=None) as ws:
            for ticker in self.tickers:
                await ws.send(self.subscription_message(key,ticker)); await asyncio.sleep(.06)
            while not self.stop_evt.is_set():
                try:data=await asyncio.wait_for(ws.recv(),timeout=1)
                except asyncio.TimeoutError:continue
                if isinstance(data,bytes):data=data.decode(errors="ignore")
                tick=self.parse_execution_message(data)
                if tick:self.on_tick(tick)
    def start(self):
        settings.validate_safety()
        if settings.data_mode!="real":raise RuntimeError("DATA_MODE=real required")
        self.thread=threading.Thread(target=lambda:asyncio.run(self._run()),daemon=True); self.thread.start()
    def stop(self):
        self.stop_evt.set()
