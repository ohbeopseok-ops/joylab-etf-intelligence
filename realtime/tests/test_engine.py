from datetime import datetime
from app.engine import evaluate,evaluate_ead
from app.models import FlowSnapshot,MarketSnapshot,StockSnapshot

def snap(kbf=100,kbi=100,skpct=-.8,sspct=-1.1,kpct=-.7,skf=-100,ski=-100,seflow=(200,50),sepct=3.5,sedraw=-1.0):
    return MarketSnapshot(timestamp=datetime.now(),source="test",kospi=6865,kospi_change_pct=kpct,stocks=[
      StockSnapshot(ticker="105560",name="KB금융",price=168400,change_pct=.1,relative_to_kospi=.8,flow=FlowSnapshot(foreign_net_qty=kbf,institution_net_qty=kbi)),
      StockSnapshot(ticker="005930",name="삼성전자",price=263000,change_pct=sspct,relative_to_kospi=sspct-kpct),
      StockSnapshot(ticker="000660",name="SK하이닉스",price=1716000,change_pct=skpct,relative_to_kospi=skpct-kpct,relative_to_peer=skpct-sspct,flow=FlowSnapshot(foreign_net_qty=skf,institution_net_qty=ski)),
      StockSnapshot(ticker="009150",name="삼성전기",price=1385000,change_pct=sepct,high_price=1400000,drawdown_from_high_pct=sedraw,relative_to_kospi=sepct-kpct,flow=FlowSnapshot(foreign_net_qty=seflow[0],institution_net_qty=seflow[1])),
      StockSnapshot(ticker="064400",name="LG씨엔에스",price=74100,change_pct=1.5,high_price=74800,drawdown_from_high_pct=-.94,relative_to_kospi=2.2,flow=FlowSnapshot(foreign_net_qty=120,institution_net_qty=80)),
      StockSnapshot(ticker="018260",name="삼성SDS",price=229000,change_pct=1.8,high_price=232000,drawdown_from_high_pct=-1.29,relative_to_kospi=2.5,flow=FlowSnapshot(foreign_net_qty=90,institution_net_qty=30)),
      StockSnapshot(ticker="307950",name="현대오토에버",price=198500,change_pct=.9,high_price=201500,drawdown_from_high_pct=-1.49,relative_to_kospi=1.6,flow=FlowSnapshot(foreign_net_qty=20,institution_net_qty=-10)),
      StockSnapshot(ticker="053800",name="안랩",price=81200,change_pct=2.4,high_price=82500,drawdown_from_high_pct=-1.58,relative_to_kospi=3.1,flow=FlowSnapshot(foreign_net_qty=40,institution_net_qty=20)),
      StockSnapshot(ticker="263860",name="지니언스",price=16800,change_pct=3.1,high_price=17100,drawdown_from_high_pct=-1.75,relative_to_kospi=3.8,flow=FlowSnapshot(foreign_net_qty=55,institution_net_qty=15)),
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
def test_ead_has_five_ranked_candidates():
    d=evaluate_ead(snap())
    assert len(d.decisions)==5
    assert {x.ticker for x in d.decisions}=={"064400","018260","307950","053800","263860"}
def test_ead_candidates_remain_hold_until_certified():
    assert all(x.action=="HOLD" for x in evaluate_ead(snap()).decisions)
