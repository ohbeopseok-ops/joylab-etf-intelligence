import json
from pathlib import Path
from .models import Decision,DecisionPack,MarketSnapshot,StockSnapshot

def flow_state(s:StockSnapshot):
    f,i=s.flow.foreign_net_qty,s.flow.institution_net_qty
    if f is None and i is None:return "UNKNOWN"
    if (f or 0)>0 and (i or 0)>=0:return "PASS"
    if (f or 0)>=0 and (i or 0)>0:return "PASS"
    if (f or 0)<0 and (i or 0)<0:return "FAIL"
    return "WATCH"

def _load_json(name):
    p=Path(__file__).resolve().parents[1]/"config"/name
    return json.loads(p.read_text(encoding="utf-8"))

def _ead_execution_score(s:StockSnapshot):
    cfg=_load_json("ead_execution_overlay.json")
    meta=cfg["research_scores"][s.ticker]
    rules=cfg["rules"]
    research_component=round(meta["research_score"]*.8,1)
    fs=flow_state(s)
    flow_points={"PASS":10,"WATCH":5,"FAIL":0,"UNKNOWN":0}[fs]
    rs=s.relative_to_kospi if s.relative_to_kospi is not None else -999
    rs_points=5 if rs>=rules["rs_pass_min_pctp"] else 2.5 if rs>=0 else 0
    draw=s.drawdown_from_high_pct if s.drawdown_from_high_pct is not None else -999
    price_points=5 if draw>=-1.5 else 2.5 if draw>=rules["high_drawdown_limit_pct"] else 0
    total=round(research_component+flow_points+rs_points+price_points,1)
    chase_block=s.change_pct>=rules["chase_block_pct"]
    certified=bool(meta["certified"])
    buy=(certified and fs=="PASS" and rs>=rules["rs_pass_min_pctp"] and draw>=rules["high_drawdown_limit_pct"] and not chase_block)
    reasons=[
        f"Execution Score {total:.1f}/100",
        f"Research {meta['research_score']}/100 → {research_component:.1f}/80",
        f"Flow {fs} {flow_points}/10",
        f"KOSPI RS {rs:+.2f}%p {rs_points}/5",
        f"고점이탈 {draw:+.2f}% {price_points}/5" if draw!=-999 else "고점이탈 UNKNOWN",
        f"Evidence {meta['confidence']}",
        "Gold Case NOT CERTIFIED → BUY BLOCK" if not certified else "Gold Case CERTIFIED"
    ]
    if chase_block:reasons.append("당일 +6% 이상 → CHASE BLOCK")
    return total,Decision(ticker=s.ticker,name=s.name,action="BUY" if buy else "HOLD",label="🟢 사자" if buy else "🟡 보류",score=int(round(total)),reasons=reasons)

def evaluate_ead(m:MarketSnapshot):
    tickers=["064400","018260","263860","053800","307950"]
    by={s.ticker:s for s in m.stocks}
    ranked=[]
    for t in tickers:
        s=by.get(t)
        if s:
            score,d=_ead_execution_score(s)
            ranked.append((score,d))
    ranked.sort(key=lambda x:x[0],reverse=True)
    return DecisionPack(timestamp=m.timestamp,market_action="Enterprise AI Deployment 실행 랭킹 — CANDIDATE 단계",decisions=[d for _,d in ranked])

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
        fs=flow_state(se); rs=se.relative_to_kospi if se.relative_to_kospi is not None else -999; draw=se.drawdown_from_high_pct if se.drawdown_from_high_pct is not None else -999
        g1=rs>=3.0; g2=fs=="PASS"; g3=draw>=-2.5; g4=se.change_pct<6.0
        buy=g1 and g2 and g3 and g4
        hard_block=se.change_pct>=6.0 or (draw<=-4.0 and fs=="FAIL")
        action="HOLD" if hard_block or not buy else "BUY"
        out.append(Decision(ticker=se.ticker,name=se.name,action=action,label="🟢 사자" if action=="BUY" else "🟡 보류",score=89 if buy else 76,reasons=[f"KOSPI RS {rs:+.2f}%p",f"Flow {fs}",f"고점이탈 {draw:+.2f}%" if draw!=-999 else "고점이탈 UNKNOWN",f"당일등락 {se.change_pct:+.2f}%"]))
    out.extend(evaluate_ead(m).decisions)
    ls=by.get("010120")
    if ls:
        rs=ls.relative_to_kospi or 0; fs=flow_state(ls); buy=rs>=2 and fs=="PASS" and ls.change_pct<=5
        out.append(Decision(ticker=ls.ticker,name=ls.name,action="BUY" if buy else "HOLD",label="🟢 사자" if buy else "🟡 보류",score=84 if buy else 69,reasons=[f"KOSPI RS {rs:+.2f}%p",f"Flow {fs}"]))
    return DecisionPack(timestamp=m.timestamp,market_action="조건 충족 종목 1개만 실행" if any(d.action=="BUY" for d in out) else "현금 유지 / 확인 대기",decisions=out)
