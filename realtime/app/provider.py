from datetime import datetime
from zoneinfo import ZoneInfo
from .config import settings
from .kis import KISClient
from .models import FlowSnapshot,MarketSnapshot,StockSnapshot

KST=ZoneInfo("Asia/Seoul")
WATCH={"005930":"삼성전자","000660":"SK하이닉스","009150":"삼성전기","064400":"LG씨엔에스","105560":"KB금융","010120":"LS ELECTRIC","005380":"현대차","066570":"LG전자"}

class MarketProvider:
    def __init__(self): self.kis=KISClient() if settings.data_mode=="real" else None
    def snapshot(self): return self._real() if settings.data_mode=="real" else self._mock()
    def _real(self):
        idx=self.kis.kospi_index(); kospi,kpct=self.kis.parse_index(idx); raw={}; flows={}
        for t in WATCH:
            raw[t]=self.kis.parse_price(self.kis.current_price(t))
            try:flows[t]=self.kis.parse_flow(self.kis.investor_trend_estimate(t))
            except:flows[t]=FlowSnapshot()
        ss=raw["005930"][1]; stocks=[]
        for t,n in WATCH.items():
            p,pct,vol,high,draw=raw[t]
            stocks.append(StockSnapshot(ticker=t,name=n,price=p,change_pct=pct,high_price=high,drawdown_from_high_pct=draw,volume=vol,relative_to_kospi=round(pct-kpct,2),relative_to_peer=round(pct-ss,2) if t=="000660" else None,flow=flows[t]))
        return MarketSnapshot(timestamp=datetime.now(KST),source="KIS Open API",kospi=kospi,kospi_change_pct=kpct,stocks=stocks)
    def _mock(self):
        kpct=-1.36
        data={"005930":(261000,-2.26,264000),"000660":(1705000,-1.45,1730000),"009150":(1385000,3.54,1400000),"064400":(74100,1.51,74800),"105560":(168400,.2,169400),"010120":(216500,-1.37,221000)}
        flows={"005930":(None,None),"000660":(-100,-100),"009150":(200,50),"064400":(120,80),"105560":(100,100),"010120":(100,100)}
        ss=data["005930"][1]; stocks=[]
        for t,n in WATCH.items():
            p,pct,high=data.get(t,(0,0,None)); f,i=flows.get(t,(None,None))
            draw=round((p/high-1)*100,2) if high else None
            stocks.append(StockSnapshot(ticker=t,name=n,price=p,change_pct=pct,high_price=high,drawdown_from_high_pct=draw,relative_to_kospi=round(pct-kpct,2),relative_to_peer=round(pct-ss,2) if t=="000660" else None,flow=FlowSnapshot(foreign_net_qty=f,institution_net_qty=i,confidence="MEDIUM" if f is not None or i is not None else "UNKNOWN")))
        return MarketSnapshot(timestamp=datetime.now(KST),source="MOCK",kospi=6818.0,kospi_change_pct=kpct,stocks=stocks)
