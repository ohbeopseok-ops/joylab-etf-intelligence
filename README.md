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

## V0.1.7 Investor Flow smoke

브랜치: `feature/investor-flow-v017`

```powershell
git fetch origin
git switch feature/investor-flow-v017
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python scripts\smoke_auth.py
python scripts\smoke_investor_flow_kb.py
pytest -q
```

장중 외국인/기관 가집계는 `estimated` 데이터이며, 프로그램매매는 보조 신호입니다. 데이터가 없을 때 0으로 대체하지 않습니다.

주의: APP KEY / SECRET은 Git, 채팅, 스크린샷에 노출하지 않습니다.
