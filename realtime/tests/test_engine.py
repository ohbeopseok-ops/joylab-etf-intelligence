from datetime import datetime
from app.engine import evaluate
from app.models import FlowSnapshot,MarketSnapshot,StockSnapshot

def snap(kbf=100,kbi=100,skpct=-.8,sspct=-1.1,kpct=-.7,skf=-100,ski=-100,seflow=(200,50),sepct=3.5,sedraw=-1.0):
    return MarketSnapshot(timestamp=datetime.now(),source="test",kospi=6865,kospi_change_pct=kpct,stocks=[
      StockSnapshot(ticker="105560",name="KB금융",price=168400,change_pct=.1,relative_to_kospi=.8,flow=FlowSnapshot(foreign_net_qty=kbf,institution_net_qty=kbi)),
      StockSnapshot(ticker="005930",name="삼성전자",price=263000,change_pct=sspct,relative_to_kospi=sspct-kpct),
      StockSnapshot(ticker="000660",name="SK하이닉스",price=1716000,change_pct=skpct,relative_to_kospi=skpct-kpct,relative_to_peer=skpct-sspct,flow=FlowSnapshot(foreign_net_qty=skf,institution_net_qty=ski)),
      StockSnapshot(ticker="009150",name="삼성전기",price=1385000,change_pct=sepct,high_price=1400000,drawdown_from_high_pct=sedraw,relative_to_kospi=sepct-kpct,flow=FlowSnapshot(foreign_net_qty=seflow[0],institution_net_qty=seflow[1])),
      StockSnapshot(ticker="010120",name="LS ELECTRIC",price=216500,change_pct=-1,relative_to_kospi=-.3,flow=FlowSnapshot(foreign_net_qty=100,institution_net_qty=100))])

def dec(m,t): return next(x for x in evaluate(m).decisions if x.ticker==t)
def test_kb_buy(): assert dec(snap(),"105560").action=="BUY"
def test_unknown_never_pass(): assert dec(snap(None,None),"105560").action=="HOLD"
def test_sk_hold(): assert dec(snap(),"000660").action=="HOLD"
def test_sk_buy_all_gates(): assert dec(snap(skpct=.2,sspct=-.2,kpct=-.1,skf=100,ski=100),"000660").action=="BUY"
def test_samsung_electro_buy_when_all_gates_pass(): assert dec(snap(),"009150").action=="BUY"
def test_samsung_electro_unknown_flow_blocks(): assert dec(snap(seflow=(None,None)),"009150").action=="HOLD"
def test_samsung_electro_chase_block(): assert dec(snap(sepct=6.1),"009150").action=="HOLD"
def test_samsung_electro_high_drawdown_blocks(): assert dec(snap(sedraw=-4.2,seflow=(-10,-20)),"009150").action=="HOLD"
