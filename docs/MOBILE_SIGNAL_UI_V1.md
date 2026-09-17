# Mobile Signal UI V1

## 목적
PC/모바일에서 동일한 JoyLab Gate 데이터를 사용하되 모바일에서는 상태를 3초 안에 이해할 수 있게 표시한다.

## 상태 규칙

### PRIMARY
- 의미: 최신 장중 외국인/기관 가집계가 존재하고 stale 아님
- 표시: PRIMARY
- 색상 의미: 긍정/부정은 값 방향으로 구분하고 상태 자체는 정상 수집 상태
- 예: `PRIMARY · 11:20`

### AUXILIARY
- 의미: Primary가 아직 없거나 stale인 시간대에 프로그램매매 등 보조신호만 존재
- 표시: AUXILIARY
- 이 상태만으로 ENTRY READY 금지
- 예: `AUX · PROGRAM +38억`

### STALE
- 의미: 예정된 집계 시각 이후 최신 가집계가 갱신되지 않음
- 표시: STALE + 마지막 갱신 시각
- 점수 사용 금지, WAIT 고정
- 예: `STALE · last 09:30`

### UNAVAILABLE
- 의미: 응답 목록에 종목이 없거나 데이터 수신 실패
- 0으로 대체 금지
- WAIT 또는 NO ENTRY

## 모바일 카드 우선순위
1. 종목/현재가/등락률
2. Entry score + decision
3. Flow status (PRIMARY/AUXILIARY/STALE)
4. 외국인/기관/프로그램
5. RS/거래량
6. blocking reason

## KB 예시

```text
KB금융 105560
181,900  +2.9%

ENTRY 87  READY
PRIMARY · 11:20

외국인   +42억
기관     +17억
프로그램 +51억
RS       +1.6%p
거래량   1.31x

Portfolio Gate: +1주 허용
```

Primary 미확인 예시:

```text
KB금융 105560
181,900  +2.9%

ENTRY 72  WAIT
AUXILIARY

프로그램 +38억
외국인   미집계
기관     미집계

Blocking: primary flow unavailable
```

## 원칙
- `estimated`와 `confirmed`를 혼용하지 않는다.
- 프로그램매매는 외국인 수급 대체값이 아니다.
- 데이터 없음은 0이 아니다.
- 모바일에서 매수 버튼은 제공하지 않는다. Read-only 판정만 제공한다.
