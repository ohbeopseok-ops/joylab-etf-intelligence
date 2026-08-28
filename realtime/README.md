# JoyLab KIS Realtime Market Adapter V0.2

READ-ONLY 한국투자증권 KIS Open API 실시간 시장 어댑터.

## Scope
- REST: KOSPI, 국내주식 현재가, 종목별 외국인/기관 추정수급
- WebSocket: 국내주식 실시간 체결가(H0STCNT0)
- Watchlist: 삼성전자, SK하이닉스, **삼성전기(009150)**, KB금융, LS ELECTRIC, 현대차, LG전자
- JoyLab: KOSPI 상대강도, 개별 수급, 장중 고점 대비 이탈률, 실행 Gate
- Dashboard: FastAPI + browser UI
- Safety: READ_ONLY=true / ORDER_ENABLED=false. 주문 API 미구현.

## 삼성전기 Execution Gate
- G1: KOSPI 대비 RS >= +3.0%p
- G2: 외국인/기관 추정수급 Flow PASS
- G3: 장중 고점 대비 이탈률 >= -2.5%
- G4: 당일 +6.0% 이상 추격 금지
- Hard block: 고점 대비 -4% 이하 + Flow FAIL
- UNKNOWN != PASS

## Run
```bash
cd realtime
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
copy .env.example .env
python -m app.main
```

기본값은 DATA_MODE=mock. 실전은 로컬 .env에 KIS_APP_KEY/KIS_APP_SECRET을 넣고 DATA_MODE=real.

## Data caveat
종목별 외국인/기관 추정수급은 틱 실시간이 아니다. KIS 장중 추정 누계 업데이트 시점 사이에는 동일 값이 유지될 수 있으므로 source_time/confidence를 함께 본다.

## Test
```bash
pytest -q
```
