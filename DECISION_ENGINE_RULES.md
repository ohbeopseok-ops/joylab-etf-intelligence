# JoyLab 투자 판단 엔진 규칙

이 결정 레이어는 기존 Portfolio Gate의 허용수량을 입력으로 사용하며 주문을
실행하지 않는다. Portfolio Gate와 V0.1.6 공식은 변경하지 않는다.

## 최종 판정

`사자`는 적용 대상인 다음 조건이 모두 충족될 때만 반환한다.

1. 가격 확인 PASS
2. 밸류에이션 PASS
3. 외국인·기관 등 수급 확인 PASS
4. 시장 대비 상대강도 PASS
5. Fundamental / EPS Revision PASS
6. Thesis INTACT
7. Governance / ESR PASS
8. Portfolio Gate 최종 허용수량 > 0
9. 데이터 신뢰도 PASS
10. Semiconductor Gate PASS
11. AI Power Gate PASS
12. Korea Translation Gate PASS
13. Pension Rotation Gate PASS

종목에 적용되지 않는 Gate는 `NOT_APPLICABLE`로 명시할 수 있다. 적용되는
Gate를 `NOT_APPLICABLE`로 우회해서는 안 된다. 산식이 확정되지 않은 Korea
Translation·Semiconductor·Pension Rotation은 코드가 값을 추정하지 않고 호출자가
근거와 함께 `PASS/FAIL/UNKNOWN`을 전달해야 한다.

하나라도 실패하거나 알 수 없으면 `보류`이며 추천수량은 0이다. 가격 하락은
가격 Gate를 통과시키지 않으므로 저가라는 이유만으로 `사자`가 될 수 없다.

`팔자`는 Thesis 훼손, 레버리지 위험, 손상 확대 중 하나가 명시적으로 입력된
경우만 반환한다. 과비중이나 허용수량 0만으로는 `팔자`가 아니라 `보류`다.

## AI Power Gate

Rotation 점수는 다음 5개 확인 항목의 참 개수다.

1. LS ELECTRIC의 KOSPI 대비 상대강도
2. HD현대일렉트릭·효성중공업 동반 강세
3. 단일 뉴스가 아닌 섹터 확산
4. 외국인·기관의 전력기기 이동
5. 반도체 약세와 전력기기 강세 동시 발생

0~1은 WEAK, 2는 WATCH, 3은 POSSIBLE, 4는 STRONG, 5는 CONFIRMED다.
기본 전략 Gate가 PASS하려면 점수 3 이상, AI Power ETF의 KOSPI 대비 강세,
그리고 아래 Revenue Translation 네 항목이 모두 PASS여야 한다.

- 수주잔고
- 매출 인식
- 영업이익률
- EPS Revision

따라서 전력 부족 뉴스나 Rotation 점수만으로는 `사자`가 되지 않는다.

### AI Power 100점 산식과 Hard Cap

- Hyperscaler CAPEX: 25
- GPU/HBM Demand: 25
- Electricity/Grid Constraint: 20
- Data Center Energization: 15
- Cooling/Power Equipment: 15

점수는 순위용이며 자동매수 신호가 아니다. 수주잔고 증가가 PASS가 아니면
최대 79점, 영업이익률 개선이 PASS가 아니면 최대 84점이다. 밸류에이션 과열
해소 또는 AI 데이터센터 매출비중이 확인되지 않으면 최대 판단은 `보류`다.

## Opportunity Score

Opportunity Score는 후보 순위를 정할 뿐 최종 Action을 만들지 않는다.
기본 후보선은 80점이고 연기금 보정은 -5~+5점으로 제한한다. 1위 또는 80점
이상이어도 EPS, 수급, 밸류에이션, 가격, Thesis, Portfolio Gate 중 하나가
미확인이면 `사자`가 될 수 없다.

## Governance / Effective Shareholder Return

다음 식은 JoyLab 판단 프레임이며 회계 공식이 아니다.

`Cash Dividend + Genuine Cancellation + Net Buyback
- Employee Equity Compensation - Governance Constraint Discount`

모든 입력은 동일 단위여야 하며 하나라도 누락되면 결과는 `UNKNOWN`이다.
계산 가능하다는 사실만으로 Governance Gate가 자동 PASS되지는 않는다.

## Data Confidence

- `CONFIRMED`: 확인
- `ESTIMATED`: 추정, 최종 Gate는 `UNKNOWN`
- `UNVERIFIED` 또는 필수 데이터 누락: `FAIL`

`UNKNOWN ≠ PASS`를 강제하며 확인되지 않은 PER/PBR, 시계열 없는 기술지표,
임의 목표가를 생성하지 않는다.

## GOLD-001

`tests/gold_cases/test_gold_001_falling_price.py`는 사용자 제공 2026-08-24~25
삼성전자 급락 사례를 회귀 계약으로 사용한다. 가격이 272,500원에서 257,000원으로
낮아져도 수급·상대강도·Governance 등 적용 Gate가 실패/미확인이면 계속 `보류`,
추천수량 0이어야 한다. 공개 fixture에는 실제 보유수량을 저장하지 않는다.

## 날짜가 있는 전략 규칙

`config/investment_decision_rules.json`의 회복선·눌림 구간·수급 연속일 조건은
사용자가 제공한 2026-08-25 전략 스냅샷이다. 영구 펀더멘털 값이 아니며
`valid_through` 이후 관측에는 `STALE_STRATEGY_RULE`을 반환한다. 갱신되지 않은
가격 기준으로 자동 판단하지 않는다.

설정에는 실제 보유수량, 계좌잔고, 고객정보나 인증정보를 저장하지 않는다.
