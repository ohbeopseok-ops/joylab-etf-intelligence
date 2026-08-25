# TASK-001 — AI Power ETF 5 Overlap Matrix + Core8 Look-through

## Objective
Extend JoyLab ETF Intelligence from single-ETF look-through to multi-ETF overlap and Core8 exposure intelligence.

## Read first
- `SPEC.md`
- `AGENTS.md`
- `TASKS.md`
- `CODEX_HANDOFF.md`

## Scope

### ETF universe
1. KODEX AI전력핵심설비
2. HANARO 전력설비투자
3. TIGER 코리아AI전력기기TOP3플러스
4. RISE AI전력인프라
5. HANARO 원자력iSelect

Before coding production identifiers, verify each exact ticker and whether KIS provides constituent data for it. Do not infer ticker codes from memory.

### Core8
- 삼성전자
- SK하이닉스
- LS ELECTRIC
- LG전자
- SK텔레콤
- 현대차
- 한화오션
- KB금융

## Deliverables
1. normalized multi-ETF holdings model
2. reusable constituent loader
3. weighted overlap engine
4. pairwise overlap matrix
5. common holdings / Top shared holdings report
6. Core8 look-through report
7. Semiconductor cluster report
8. Power Equipment cluster report
9. concentration summary
10. Gold Tests

## Required metric
`Weighted Overlap(A,B) = Σ min(weight_A_i, weight_B_i)`

Do not silently normalize incomplete source data to 100% unless the behavior is explicitly designed, documented and tested.

## Required tests
- identical ETF holdings
- disjoint ETF holdings
- partial overlap
- missing constituent data
- incomplete holding-weight sum
- matrix symmetry
- existing v0.1.6 regression tests remain green

## Acceptance criteria
- all 5 ETF names have verified production ticker/source status
- unsupported or unavailable constituent retrieval emits explicit status
- no guessed ticker, KIS TR ID or raw field
- overlap matrix symmetric
- common holdings are deterministic
- Core8 look-through separately visible
- cluster calculations reuse normalized models
- no live trading/order code
- `python -m pytest tests/gold_cases -q` PASS
- `python -m pytest -q` PASS

## Completion report
Return:
- repository audit summary
- verified ticker/source table
- implementation plan
- changed files
- formula/normalization decisions
- test results
- unresolved assumptions / source gaps
- recommendation for next PR/task
