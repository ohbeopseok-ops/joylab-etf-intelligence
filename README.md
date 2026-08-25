# JoyLab ETF Intelligence

V0.1 목표:
1. 한국투자증권 Open API 모의투자 인증
2. 국내주식/ETF 현재가 조회
3. JoyLab 공통 MarketQuote 정규화
4. 주문 기능 미구현(Read-only)

## Setup

```powershell
copy .env.example .env
notepad .env
```

`.env`:

```text
KIS_APP_KEY=발급받은_앱키
KIS_APP_SECRET=발급받은_앱시크리트
KIS_ENV=paper
```

실행:

```powershell
python scripts/smoke_auth.py
python scripts/smoke_stock.py
pytest -q
```

주의: APP KEY / SECRET은 Git, 채팅, 스크린샷에 노출하지 않습니다.
