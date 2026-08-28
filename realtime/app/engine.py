from .models import Decision,DecisionPack,MarketSnapshot,StockSnapshot

def flow_state(s:StockSnapshot):
    f,i=s.flow.foreign_net_qty,s.flow.institution_net_qty
    if f is None and i is None:return "UNKNOWN"
    if (f or 0)>0 and (i or 0)>=0:return "PASS"
    if (f or 0)>=0 and (i or 0)>0:return "PASS"
    if (f or 0)<0 and (i or 0)<0:return "FAIL"
    return "WATCH"

def evaluate(m:MarketSnapshot):
    by={s.ticker:s for s in m.stocks}; out=[]
    kb=by.get("105560")
    if kb:
        fs=flow_state(kb); buy=166000<=kb.price<=169000 and fs=="PASS"
        out.append(Decision(ticker=kb.ticker,name=kb.name,action="BUY" if buy else "HOLD",label="🟢 사자" if buy else "🟡 보류",score=86 if buy else 72,reasons=[f"현재가 {kb.price:,}",f"Flow {fs}"],quantity_candidate=3 if buy else None))
    sk=by.get("000660")
    if sk:
        gates=[sk.price>=1700000,flow_state(sk)=="PASS",(sk.relative_to_kospi if sk.relative_to_kospi is not None else -999)>=0,(sk.relative_to_peer if sk.relative_to_peer is not None else -999)>=0]
        n=sum(gates); buy=n==4
        out.append(Decision(ticker=sk.ticker,name=sk.name,action="BUY" if buy else "HOLD",label="🟢 사자" if buy else "🟡 보류",score=88 if buy else 60+n*5,reasons=[f"G{i+1} {'PASS' if v else 'FAIL'}" for i,v in enumerate(gates)],quantity_candidate=1 if buy else None))
    ls=by.get("010120")
    if ls:
        rs=ls.relative_to_kospi or 0; fs=flow_state(ls); buy=rs>=2 and fs=="PASS" and ls.change_pct<=5
        out.append(Decision(ticker=ls.ticker,name=ls.name,action="BUY" if buy else "HOLD",label="🟢 사자" if buy else "🟡 보류",score=84 if buy else 69,reasons=[f"KOSPI RS {rs:+.2f}%p",f"Flow {fs}"]))
    return DecisionPack(timestamp=m.timestamp,market_action="조건 충족 종목 1개만 실행" if any(d.action=="BUY" for d in out) else "현금 유지 / 확인 대기",decisions=out)
