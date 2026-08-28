# JoyLab KIS Realtime Market Adapter V0.2.1

READ-ONLY 한국투자증권 KIS Open API 실시간 시장 어댑터.

## Enterprise AI Deployment live universe
- LG씨엔에스 064400
- 삼성SDS 018260
- 현대오토에버 307950
- 안랩 053800
- 지니언스 263860

각 종목에 KIS 현재가, 외국인/기관 추정수급, KOSPI RS, 장중 고가 대비 이탈률을 연결한다.

### Execution ranking overlay
Preliminary research score를 80%, 실시간 실행 데이터를 20%로 사용한다.
- Research: 80
- Flow: 10
- KOSPI RS: 5
- Price quality: 5

/api/ead-ranking 에서 5종목 실행 랭킹을 점수순으로 반환한다.

중요:
- Research score는 2026-08-28 Preliminary CANDIDATE 점수이며 Certified가 아니다.
- Gold Case certified=false 인 동안 BUY는 코드상 차단한다.
- UNKNOWN != PASS.
- Flow/RS가 강해도 펀더멘털 독립검증을 대체하지 않는다.

## Existing execution gates
### 삼성전기
- KOSPI RS >= +3.0%p
- Flow PASS
- 고점 이탈 >= -2.5%
- 당일 +6% 이상 추격 금지

## Safety
- READ_ONLY=true
- ORDER_ENABLED=false
- 주문 API 미구현

## Run
cd realtime
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python -m app.main

## Test
pytest -q
