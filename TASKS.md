# TASKS.md

> Full JoyLab Investment Engine design (Gates 1-12, GOLD-001, AI Power Gate formula,
> Governance/ESR, Pension Flow) lives in `docs/JOYLAB_INVESTMENT_ENGINE.md`. TASK-002+
> below should be scoped against that document, not re-derived from scratch.

## Baseline — V0.1.6
Status: protected baseline.

Validated locally before GitHub handoff:
- Gold tests: 16 passed
- Full tests: 17 passed
- functional Portfolio Gate PASS

Do not modify `main` while implementing V0.2.

## TASK-001 — AI Power ETF 5 Overlap Matrix + Core8 Look-through
Priority: P0
Status: READY

Goal: extend single-ETF look-through into multi-ETF overlap and Core8 exposure intelligence.

ETF universe names:
1. KODEX AI전력핵심설비
2. HANARO 전력설비투자
3. TIGER 코리아AI전력기기TOP3플러스
4. RISE AI전력인프라
5. HANARO 원자력iSelect

Important: verify exact live ticker codes before production ingestion. Do not guess.

Core8:
- 삼성전자
- SK하이닉스
- LS ELECTRIC
- LG전자
- SK텔레콤
- 현대차
- 한화오션
- KB금융

Deliverables:
- normalized multi-ETF holdings model
- ETF constituent fetch pipeline
- pairwise weighted overlap matrix
- common-security report
- Top shared holdings
- Core8 look-through table
- Semiconductor cluster exposure
- Power Equipment cluster exposure
- concentration summary
- Gold Tests

Weighted overlap:
`Overlap(A,B) = Σ min(weight_A_i, weight_B_i)`

Acceptance:
- ticker/source verification is explicit
- matrix symmetric
- missing/unsupported ETF data explicitly marked, never silently converted to 0%
- diagonal behavior documented based on holding coverage
- identical/disjoint/partial/missing/incomplete-weight tests
- existing v0.1.6 Gold Tests remain green
- `python -m pytest tests/gold_cases -q` PASS
- `python -m pytest -q` PASS
- no trading/order API added

## TASK-002 — Cluster Policy Calibration
Compare Semiconductor cluster caps 30/40/50% with historical simulation. Do not change production default before review.

## TASK-003 — Decision Presenter
Deterministic formatter for action, allowed qty, buy amount, post-buy True Weight, post-buy Cluster Weight and blocking reasons.

## TASK-004 — Data Confidence Gate
Add freshness/missing-data checks for quote, balance and ETF constituent snapshots. Required stale data should force `보류`.

## TASK-005 — Decision Journal
Persist inputs, decision, gates and later outcome without credentials.
