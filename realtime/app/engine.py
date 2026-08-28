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
    se=by.get("009150")
    if se:
        fs=flow_state(se)
        rs=se.relative_to_kospi if se.relative_to_kospi is not None else -999
        draw=se.drawdown_from_high_pct if se.drawdown_from_high_pct is not None else -999
        g1=rs>=3.0
        g2=fs=="PASS"
        g3=draw>=-2.5
        g4=se.change_pct<6.0
        buy=g1 and g2 and g3 and g4
        hard_block=se.change_pct>=6.0 or (draw<=-4.0 and fs=="FAIL")
        action="HOLD" if hard_block or not buy else "BUY"
        label="🟢 사자" if action=="BUY" else "🟡 보류"
        out.append(Decision(ticker=se.ticker,name=se.name,action=action,label=label,score=89 if buy else 76,reasons=[f"KOSPI RS {rs:+.2f}%p",f"Flow {fs}",f"고점이탈 {draw:+.2f}%" if draw!=-999 else "고점이탈 UNKNOWN",f"당일등락 {se.change_pct:+.2f}%"]))
    ls=by.get("010120")
    if ls:
        rs=ls.relative_to_kospi or 0; fs=flow_state(ls); buy=rs>=2 and fs=="PASS" and ls.change_pct<=5
        out.append(Decision(ticker=ls.ticker,name=ls.name,action="BUY" if buy else "HOLD",label="🟢 사자" if buy else "🟡 보류",score=84 if buy else 69,reasons=[f"KOSPI RS {rs:+.2f}%p",f"Flow {fs}"]))
    return DecisionPack(timestamp=m.timestamp,market_action="조건 충족 종목 1개만 실행" if any(d.action=="BUY" for d in out) else "현금 유지 / 확인 대기",decisions=out)
