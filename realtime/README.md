# JoyLab KIS Realtime Market Adapter V0.2

READ-ONLY 한국투자증권 KIS Open API 실시간 시장 어댑터.

## Scope
- REST: KOSPI, 국내주식 현재가, 종목별 외국인/기관 추정수급
- WebSocket: 국내주식 실시간 체결가(H0STCNT0)
- JoyLab: KOSPI 상대강도, 삼성전자 대비 SK하이닉스 상대강도, 실행 Gate
- Dashboard: FastAPI + browser UI
- Safety: READ_ONLY=true / ORDER_ENABLED=false. 주문 API 미구현.

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
종목별 외국인/기관 추정가집계는 틱 실시간이 아니다. KIS 공식 예제 기준 외국인은 통상 09:30/11:20/13:20/14:30, 기관은 10:00/11:20/13:20/14:30 입력되는 장중 추정 누계다.

## Test
```bash
pytest -q
```
