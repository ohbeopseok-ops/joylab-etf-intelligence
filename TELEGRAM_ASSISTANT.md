# JoyLab Telegram 주식 비서 MVP

이 기능은 개인용 조회·판단 인터페이스입니다. 주문, 자동매매, 주문 API는 구현하지
않습니다. 현재가와 KIS 당일 투자자 수급을 조회하고, 저장된 JoyLab 판단 규칙에
대입합니다. 확인되지 않은 조건은 `PASS`로 간주하지 않으며 최종 응답은 보수적으로
`보류 / 0주`가 됩니다.

## 준비

1. Telegram의 공식 BotFather에서 개인 봇을 만들고 토큰을 발급합니다.
2. 봇과 개인 대화를 시작한 뒤 Telegram Bot API `getUpdates` 응답에서 본인의
   `message.chat.id`를 확인합니다.
3. 저장소 루트의 `.env`에 다음 값을 넣습니다. 실제 값은 커밋하지 않습니다.

```dotenv
KIS_APP_KEY=...
KIS_APP_SECRET=...
KIS_ENV=paper
TELEGRAM_BOT_TOKEN=...
TELEGRAM_ALLOWED_CHAT_IDS=123456789
TELEGRAM_POLL_TIMEOUT_SEC=30
```

여러 개인 ID를 허용하려면 쉼표로 구분합니다. 허용 목록에 없는 채팅은 아무 응답도
받지 않습니다. 이 MVP는 공개 HTTPS 서버가 필요 없는 long polling 방식이며, 같은
봇에 webhook이 설정되어 있으면 Telegram 정책상 `getUpdates`와 함께 사용할 수
없으므로 기존 webhook을 먼저 해제해야 합니다.

## 실행

```powershell
.\.venv\Scripts\python.exe scripts\telegram_assistant.py
```

지원 입력:

- `/analyze 005930`
- `/decision 삼성전자`
- `005930`
- `/help`

6자리 티커는 그대로 조회할 수 있지만, 저장된 전략 규칙이 없는 종목은 시세만으로
매수 판단을 만들지 않습니다. 종목명은 규칙 또는 검증 완료된 AI Power ETF 목록에
정확히 등록된 이름만 허용하며 별칭을 추측하지 않습니다.

## 현재 데이터 경계

- 확인: KIS 현재가, 등락률, 당일 개인·외국인·기관 순매수량
- 미확인: 다일 매도세 완화, 연기금 종목별 수급, 시장 대비 상대강도, 기업가치와
  EPS, 지배구조/ESR, 투자논지, 실계좌 포트폴리오 허용 수량
- 따라서 이 MVP는 “분석 대화창”이며 매수 승인기가 아닙니다.

Telegram Bot API 공식 문서:
<https://core.telegram.org/bots/api>
