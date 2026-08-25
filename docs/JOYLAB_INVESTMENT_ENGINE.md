# JoyLab Investment Engine — Design Handoff

> Scope note (2026-08-25): 2026-08-24~25 대화에서 정리된 JoyLab Investment Engine 전체 설계.
> 이 문서는 코드가 아니라 **설계/의사결정 기록**이다. 여기 담긴 Gate·Case·Rule을
> 구현할 때는 `AGENTS.md`의 "추측 금지 / Gold Test 필수 / secret 금지" 원칙을 그대로 적용한다.
> TASK-001(AI Power ETF Overlap + Core8 Look-through, `tasks/TASK_001_AI_POWER_OVERLAP.md`)은
> 이 엔진의 한 조각(멀티 ETF Look-through)이며, 이미 구현·라이브 검증·커밋 완료됨 (dev/v0.2).
> 아래 Gate 중 다수(AI Power Gate, Governance/ESR, Pension Flow 등)는 **아직 별도 TASK로
> 분리되지 않은 설계 초안**이다. 구현 전 반드시 새 TASK 문서로 스코프를 확정할 것.

## 0. 전체 난이도 요약

이 설계는 다음 5개가 동시에 진행된 결과다.

1. 실시간 장중 투자판단
2. 삼성전자 급락 Gold Case 검증 (GOLD-001)
3. Core 8 포트폴리오 의사결정 엔진 설계
4. Overnight Semiconductor Model 개선
5. AI Power Gate라는 신규 Macro/Theme Gate 추가

단순 종목 분석이 아니라: 실전 시세 → 판단 → 검증 → 모델 수정 → 프롬프트화 → 자동화 구조화까지
이어진 투자 시스템 설계다.

## 1. 핵심 문제의식

출발점: "삼성전자가 급락했다. 싸진 것 같은데 사야 하나?"

바뀐 질문: "가격이 싸졌다는 이유만으로 매수하는 모델은 위험하지 않은가? 수급·상대강도·섹터
Rotation·포트폴리오 집중도까지 반영한 판단 엔진을 만들 수 있는가?"

핵심 원칙:

```text
Falling Price ≠ Better Buy
```

가격 하락은 매수 신호가 아니라 검증 대상이다.

## 2. GOLD-001 — 삼성전자 급락 Case

Case ID: `GOLD-001 — Falling Price ≠ Better Buy`

### Day-0 (2026-08-24) 장중 흐름

```text
08:30  삼성전자 272,500원 / -3.20%
10:30  삼성전자 263,500원 / -6.39%
11:00  삼성전자 260,000원 / -7.64%
12:30  삼성전자 257,500원 / -8.53%
종가   삼성전자 257,000원 / -8.70%
```

Price-only 모델이었다면 가격이 내려갈수록 매수 강도가 올라갔을 가능성이 크다. 하지만 JoyLab
판단은 계속 `🟡 보류`였다.

### 보류 이유

- KOSPI 대비 상대약세 심화
- 외국인·기관 매도
- 연기금 삼성전자 -909억 순매도
- 삼성전자우도 순매도
- 금산법 10% 룰과 자사주 소각 딜레마
- 주주환원 발표의 Effective Shareholder Return 품질 의심
- 260K 회복 실패
- 급락 후 반등이 데드캣 바운스일 수 있음

### 실제 행동

```text
기존 삼성전자 3주 유지
추가매수 0주
```

### T+1 결과 (2026-08-25)

```text
삼성전자 257,000원 / 0.00%
KOSPI 6746.37 / +0.74%

삼성전자 절대수익률: 0.00%
KOSPI 대비 초과수익률: -0.74%p
장중 저점: 248,000원
WAIT 판단: 중립~소폭 성공
```

종가 기준으로 큰 손실 회피는 아니었지만, 장중 248K까지 밀렸기 때문에 Falling Knife를 피한
효과는 있었다.

## 3. 삼성전자 Governance / 주주환원 분석

### 핵심 이슈

삼성전자가 90~110조원 주주환원 계획을 발표했지만, 시장은 이를 긍정적으로만 보지 않았다.

삼성생명·삼성화재가 삼성전자 지분을 합산 약 10% 근처 보유 중이고, 금산법 10% 룰 때문에
삼성전자가 보통주를 대규모 소각하면 보험계열사의 지분율이 10%를 넘을 수 있다. 따라서 삼성전자는
보통주 자사주 소각을 공격적으로 하기 어렵다.

### JoyLab Governance Rule

```text
Buyback ≠ Shareholder Return
```

자사주 매입은 다음을 구분해야 한다.

```text
1. 현금배당
2. 실제 소각
3. 임직원 보상용 자사주
4. M&A용 자사주
5. 지배구조 제약으로 인한 제한적 소각
```

### Effective Shareholder Return (JoyLab 투자 판단용 프레임, 회계 공식 아님)

```text
Effective Shareholder Return =
  Cash Dividend
  + Genuine Cancellation
  + Net Buyback
  - Employee Equity Compensation
  - Governance Constraint Discount
```

### 삼성전자 현재 결론

```text
삼성전자 = 장기 Thesis 완전 훼손 아님
그러나 단기 추가매수는 보류
260K 회복 + 수급 Peak-out 확인 전까지 사자 금지
```

## 4. SK하이닉스 vs 삼성전자 재정렬

8/25 종가: 삼성전자 257,000원(0.00%) vs SK하이닉스 1,686,000원(+0.90%).

연기금: 삼성전자 -675억(2일 연속 순매도) vs SK하이닉스 +329억(6일 연속 순매수).

결론: `반도체 안에서는 SK하이닉스 > 삼성전자`. 단, 하이닉스도 바로 사자는 아니다.

### 하이닉스 조건

```text
170만원 회복
외국인 매도 둔화
미국 메모리 약세 완화
MU–SOXX 상대강도 개선
```

이 조건 전까지는 `🟡 상위 보류`.

## 5. KODEX200 판단 변화

처음에는 105~106K 구간에서 1주 매수 후보였으나 보류로 바뀌었다.

8/24 장중 수급: 외국인 대규모 순매도, 기관 순매도, 프로그램 순매도, 개인 순매수.

시장 내부 구조: KOSPI -3%대인데 상승종목 수 > 하락종목 수 — 즉 시장 전체가 무너진 게 아니라
대형주(특히 삼성전자) 중심 지수 매도였다.

KODEX200은 대형주 비중이 크므로, 가격이 싸졌다고 바로 사면 삼성전자 수급 부담을 그대로
떠안는다.

```text
결론: KODEX200 기존 1주 유지, 추가 1주 보류
외국인/기관 수급 반전 확인 전까지 사자 금지
```

## 6. Core 8 Universe와 Opportunity Score

### Core 8

```text
1. 삼성전자
2. SK하이닉스
3. LS ELECTRIC
4. LG전자
5. SK텔레콤
6. 현대차
7. 한화오션
8. KB금융
```

### 추가 Watch / Challenger

```text
NAVER, 삼성SDI, 현대건설, GS건설, 삼성물산, 삼성전자우,
HD현대일렉트릭, 효성중공업, 두산에너빌리티, AI Power ETF 5종
```

### Opportunity Score 특징

점수가 높아도 자동 매수하지 않는다.

```text
Ranking #1 ≠ BUY
```

점수 80 이상이어도 다음 중 하나라도 미확인이면 `🟢 사자` 불가:

```text
EPS Revision, 수급, 밸류에이션, 가격대, 포트폴리오 비중, Thesis
```

```text
Score는 후보 선별
Decision은 Gate 통과 후 결정
```

## 7. 3단계 사용자 표시 체계

내부적으로는 BUY / BUY WATCH / WAIT / BUY BLOCK 등 세분화된 단계가 있었으나, 사용자-facing
판단은 단순화했다.

```text
🟢 사자
🟡 보류
🔴 팔자
```

단순화는 출력용일 뿐이고 내부 판단은 복잡하게 유지된다.

### 내부 판단 구조

```text
Price, Flow, Relative Strength, Fundamental/EPS Revision,
Thesis, Governance/ESR, Portfolio Gate, Data Confidence
```

### 사용자 출력

```text
종목 | 현재가 | 판단 | 지금 행동 | 수량 | 판단 변경조건
```

## 8. Data Confidence / UNKNOWN Rule

핵심 규칙: `UNKNOWN ≠ PASS` — 확인되지 않은 정보는 통과로 보지 않는다.

### 태그 체계

```text
🟢 확인
🟡 추정
⚠️ 미확인
```

### 금지사항

```text
확인하지 못한 PER/PBR 지어내기 금지
시계열 없이 RSI/MACD/상관계수 계산 금지
목표가 제시 금지
가격 하락만으로 매수추천 금지
```

## 9. Grok 프롬프트 분석과 JoyLab 프롬프트 분리

Grok으로 만든 한국 증시 포트폴리오 분석 프롬프트 평가: Deep Research용으로는 좋음, 장중 실전
판단용으로는 너무 무거움.

### 분리 구조 (3개 프롬프트)

```text
1. JoyLab Intraday Decision Prompt   — 장중 = 빠른 판단
2. JoyLab Close Review Prompt        — 마감 후 = 검증
3. JoyLab Deep Portfolio Research Prompt — 주말 = 깊은 리서치
```

이후 LLM이 역할별로 다르게 작동하도록 설계한 것.

## 10. AI Power Gate

기존 모델은 Overnight Semiconductor Model 중심이었다 (Nasdaq, SOXX, SOXL, NVDA, MU, MU–NVDA
Spread, MU–SOXX Relative, USD/KRW, 삼성전자, SK하이닉스).

AI CAPEX를 GPU/HBM만으로 보면 부족하다는 판단에서 AI Power Gate가 나왔다.

### 핵심 가설

```text
AI CAPEX 사이클은 단순히 GPU/HBM 수요만으로 판단하지 않는다.
AI 인프라 투자는 다음 3단계로 나눠 추적한다.

1. Compute Demand — GPU, HBM, DRAM, 서버 수요
2. Physical Deployment — 데이터센터 착공, 전력 인입, 냉각, 변압기, 배전반, UPS
3. Revenue Translation — 수주잔고, 매출 인식, 영업이익률, EPS Revision

GPU/HBM 수요가 강해도 전력망·데이터센터 전력 인입이 병목이면,
주가 반응은 반도체보다 전력 인프라 종목에서 먼저 나타날 수 있다.
```

### AI Power Gate 100점 산식 초안

```text
Hyperscaler CAPEX             25
GPU/HBM Demand                25
Electricity/Grid Constraint   20
Data Center Energization      15
Cooling/Power Equipment       15
```

이 산식은 바로 매수로 연결하지 않는다.

### Hard Rule

```text
전력 부족 뉴스만으로 사자 금지
수주잔고 증가 없으면 80점 이상 금지
영업이익률 개선 없으면 85점 이상 금지
밸류에이션 과열이면 사자 자동승격 금지
AI 데이터센터 매출 비중 불명확하면 최대 🟡 보류
```

순서: `전력 부족 → 수주 → 매출 → 마진 → EPS Revision`

### AI Power Watch 장중 체크리스트

```text
1. LS ELECTRIC이 KOSPI 대비 +2%p 이상 강한가?
2. HD현대일렉트릭·효성중공업도 같이 강한가?
3. 전력기기 강세가 단일 뉴스가 아니라 섹터 동반인가?
4. 외국인/기관이 전력기기 쪽으로 이동하는가?
5. 반도체 약세와 전력기기 강세가 동시에 나타나는가?
```

판정: 0~1개 약함 / 2개 관찰 / 3개 Rotation 가능성 / 4개 강함 / 5개 Rotation 확정급.

실제 적용 (8/25 오전, KODEX AI전력핵심설비 ETF): `-4.79%` → AI Power Rotation 아직 미확인.

### AI Power ETF Watchlist V0.1

```text
1. KODEX AI전력핵심설비 (487240)
2. HANARO 전력설비투자 (491820)
3. TIGER 코리아AI전력기기TOP3플러스 (0117V0)
4. RISE AI전력인프라 (0101N0)
5. HANARO 원자력iSelect (434730)
```

> 위 5개 심볼은 TASK-001에서 KIS 라이브 API로 실제 검증 완료 (`config/ai_power_universe.json`
> 의 `live_kis_verification` 참고).

KODEX AI전력핵심설비 구성 (당시 확인): 효성중공업 ~21.44%, LS ELECTRIC ~20.89%,
HD현대일렉트릭 ~17.38%, LS ~13.20%, 대한전선 ~8.24%.

```text
결론: AI Power ETF는 Watchlist 1순위
하지만 32,500원 회복 전까지 신규매수 금지
```

## 11. Rotation Framework

시장을 단순 상승/하락이 아니라 Rotation으로 본다.

### 주요 Rotation 축

```text
1. Semiconductor Weak — 삼성전자, SK하이닉스, IT레버 약세
2. Auto/Defensive Strength — 현대차 강세
3. Pension Flow Rotation — 삼성전자 매도 → SK하이닉스, NAVER, 현대건설, 고려아연 등 매수
4. AI Power Watch — 전력기기·전력설비 ETF 확인
5. Construction Rotation — 현대건설, GS건설 연기금 매집
```

핵심 해석: "시장이 무너졌는가? 아니면 돈이 이동했는가?" — 8/24~8/25 결론은 후자에 가까웠다.
삼성전자/대형 반도체에서 빠진 돈이 SK하이닉스, NAVER, 건설, 일부 방어주로 이동.

## 12. 연기금 Flow

### 8/24

```text
삼성전자 -909억
삼성전자우 -185억
NAVER +559억
삼성SDI +487억
엘앤에프 +241억
```

### 8/25

```text
삼성전자 -675억 (2일 연속)
삼성전자우 -197억 (3일 연속)
SK하이닉스 +329억 (6일 연속)
NAVER +231억 (2일 연속)
현대건설 +372억
GS건설 18일 연속 매집
```

결론: 연기금은 시장을 떠난 게 아니라 종목을 교체 중 — 삼성전자에서 빼서 SK하이닉스, NAVER,
건설, 비철 등으로 이동. 연기금 Flow는 Opportunity Score에 최대 ±5점 정도로 반영하는 규칙 논의.

## 13. 2026-08-25 기준 최종 투자판 (스냅샷 — 시점 데이터, 자동 갱신 아님)

```text
🟢 사자: 없음

🟡 상위 보류: SK하이닉스, 현대차, NAVER, LS ELECTRIC/AI Power ETF,
             현대건설/GS건설 Rotation Watch

🟡 보류 강화: 삼성전자, 삼성전자우, LG전자, KODEX200, AI Power ETF 단기 하락 시

🔴 팔자/축소: IT레버, SOXL류, 레버리지 반도체 ETF, 과비중 반도체 레버리지
```

## 14. 현재 모델의 진짜 의미

```text
JoyLab Investment Engine
= 실시간 시세 입력
+ 수급/상대강도 판단
+ 섹터 Rotation 감지
+ 포트폴리오 비중 제어
+ Gold Case 검증
+ Prompt Engineering
+ LLM Handoff 가능 문서화
```

## 15. 다음 세션(LLM/Codex/Claude)이 이어받아야 할 핵심

```text
1. 사자/보류/팔자 출력은 단순하지만 내부 판단은 다층 Gate 구조다.
2. 삼성전자 급락은 Gold Case이며, Price-only 모델을 버리는 근거다.
3. AI CAPEX는 Semiconductor Gate와 AI Power Gate로 분리해야 한다.
4. 연기금 Flow는 단기 Rotation 감지에 중요한 보조지표다.
5. KODEX200, ETF, 개별주 모두 Look-through로 봐야 한다.
6. 모든 매수 판단은 포트폴리오 비중과 섹터 집중도를 통과해야 한다.
7. 장중/마감/주말 프롬프트는 분리해야 한다.
```

## 16. Gate 목록 (구현 상태 추적용, 2026-08-25 야간 갱신)

| # | Gate | 상태 | 코드 위치 |
|---|------|------|-----------|
| 1 | Price / Valuation | 부분 구현 (라이브) | `intelligence/portfolio_gate.py`, `intelligence/true_exposure_v015.py`, `assistant/stock_assistant.py`(watch_rule 기반) |
| 2 | Flow (수급) | 부분 구현 (라이브, 당일치만) | `kis/investor.py` — 개인/외국인/기관 순매수 라이브 조회. 다일 추세·연기금은 여전히 미구현 |
| 3 | Relative Strength | **구현됨 (라이브)** | `kis/index.py`(KOSPI 지수 조회) + `assistant/stock_assistant.py::_relative_strength` — 당일 등락률 vs KOSPI 당일 등락률 비교. 다일 RS 라인 아님, 단순 당일 초과수익 비교임을 문서화함 |
| 4 | Fundamental / EPS Revision | 미구현 | `decision_engine.py`에 `fundamental_eps_gate` 필드는 있으나 항상 NOT_APPLICABLE |
| 5 | Thesis | 미구현 | `ThesisState` enum 존재, 항상 UNKNOWN으로 전달 |
| 6 | Governance / Effective Shareholder Return | 계산기만 구현, 미연결 | `decision_engine.py::calculate_effective_shareholder_return`는 순수 함수로 존재하나 `StockAssistantService.analyze()`에서 호출 안 됨 — 입력값(배당/소각/자사주 금액)을 KIS에서 못 가져오므로 수동 입력 스키마 필요 |
| 7 | Portfolio Concentration | 구현됨 (CLI만, 봇 미연결) | `intelligence/portfolio_gate.py`, `scripts/analyst.py`에서 실계좌 연동 확인됨. 텔레그램 봇에는 아직 미연결 (`portfolio_allowed_qty=0` 하드코딩) |
| 8 | Data Confidence | 부분 구현 | `decision_engine.py::evaluate_data_confidence`, `InstrumentWatchRule.valid_through` 기반 STALE_STRATEGY_RULE 체크는 실제 작동 중 |
| 9 | Semiconductor Gate | 부분 구현 | `ai_power_universe.json` clusters.semiconductor + `overlap.py` |
| 10 | AI Power Gate | 계산기만 구현, 미연결 | `decision_engine.py::evaluate_ai_power_gate`, `calculate_ai_power_score` 존재하나 봇에서 호출 안 됨 — rotation checklist 5개 항목이 정성 판단이라 대화형 입력 필요 |
| 11 | Korea Translation Gate | 미정의 | 명칭만 언급, 세부 설계 없음 |
| 12 | Pension Flow Rotation | 미구현 (KIS에 없음, 확인됨) | KIS 리테일 API에 종목별 연기금 순매수 엔드포인트가 없음을 라이브 확인 (`kis-open-trading-api-reference` 전수 검색) — 외부 소스 필요 |

**텔레그램 봇 실사용 경로**: `joyfin_bot` → Vercel 웹훅(`feature/telegram-vercel-webhook`) → 라이브 시세+수급+상대강도 → `investment_decision_rules.json` watch_rule 매칭 → 🟡 보류/사자 답장. Core8 + AI Power ETF 5종 + 사용자 지정 32개 종목(`config/ticker_universe.json`)까지 한글 이름으로 조회 가능. Governance/AI Power Gate는 다음 단계.

## 17. LLM에게 넘길 핵심 지시문 (원문 보존)

```text
너는 JoyLab Investment Engine을 이어받는다.

사용자는 단순 종목 추천을 원하지 않는다.
사용자는 실시간 시장 데이터를 기반으로 사자/보류/팔자를 판단하는 투자 의사결정 엔진을 만들고 있다.

최종 출력은 단순해야 한다.
그러나 내부 판단은 다음 Gate를 모두 반영해야 한다.

1. Price / Valuation
2. Flow
3. Relative Strength
4. Fundamental / EPS Revision
5. Thesis
6. Governance / Effective Shareholder Return
7. Portfolio Concentration
8. Data Confidence
9. Semiconductor Gate
10. AI Power Gate
11. Korea Translation Gate
12. Pension Flow Rotation

특히 삼성전자 급락 Case인 GOLD-001을 기억하라.

GOLD-001의 교훈:
가격이 하락할수록 매수 강도가 올라가는 Price-only 모델은 위험하다.
삼성전자 257K에서도 수급·상대강도·주주환원 품질이 통과하지 못했기 때문에 추가매수하지 않았다.
T+1에서도 삼성전자는 KOSPI를 이기지 못했다.

AI CAPEX 분석에서는 GPU/HBM만 보지 말고 AI Power Gate를 별도로 추적하라.
전력망, 데이터센터 전력 인입, 냉각, 변압기, 배전반, UPS, 수주잔고, 매출 인식, 영업이익률,
EPS Revision을 확인하라.

최종 판단은 항상:
🟢 사자
🟡 보류
🔴 팔자
중 하나로 출력하라.
```

## 18. 한 줄 요약

이 프로젝트는 "삼성전자 빠졌네, 살까?"가 아니라, 반도체 급락장에서 가격·수급·상대강도·
주주환원 품질·연기금 Rotation·AI CAPEX 병목·전력 인프라 수혜·포트폴리오 집중도를 통합해,
LLM이 반복 실행 가능한 투자 판단 엔진을 만드는 것이다.
