from datetime import datetime
from app.engine import evaluate
from app.models import FlowSnapshot,MarketSnapshot,StockSnapshot

def snap(kbf=100,kbi=100,skpct=-.8,sspct=-1.1,kpct=-.7,skf=-100,ski=-100):
    return MarketSnapshot(timestamp=datetime.now(),source="test",kospi=6865,kospi_change_pct=kpct,stocks=[
      StockSnapshot(ticker="105560",name="KB금융",price=168400,change_pct=.1,relative_to_kospi=.8,flow=FlowSnapshot(foreign_net_qty=kbf,institution_net_qty=kbi)),
      StockSnapshot(ticker="005930",name="삼성전자",price=263000,change_pct=sspct,relative_to_kospi=sspct-kpct),
      StockSnapshot(ticker="000660",name="SK하이닉스",price=1716000,change_pct=skpct,relative_to_kospi=skpct-kpct,relative_to_peer=skpct-sspct,flow=FlowSnapshot(foreign_net_qty=skf,institution_net_qty=ski)),
      StockSnapshot(ticker="010120",name="LS ELECTRIC",price=216500,change_pct=-1,relative_to_kospi=-.3,flow=FlowSnapshot(foreign_net_qty=100,institution_net_qty=100))])
def test_kb_buy(): assert next(x for x in evaluate(snap()).decisions if x.ticker=="105560").action=="BUY"
def test_unknown_never_pass(): assert next(x for x in evaluate(snap(None,None)).decisions if x.ticker=="105560").action=="HOLD"
def test_sk_hold(): assert next(x for x in evaluate(snap()).decisions if x.ticker=="000660").action=="HOLD"
def test_sk_buy_all_gates(): assert next(x for x in evaluate(snap(skpct=.2,sspct=-.2,kpct=-.1,skf=100,ski=100)).decisions if x.ticker=="000660").action=="BUY"
