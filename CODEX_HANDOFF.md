# CODEX_HANDOFF.md

## Why this file exists
This file transfers the working context from the prior design/debug session into Codex. It contains only non-secret engineering context suitable for a public repository.

## Repository state
- repository: `ohbeopseok-ops/joylab-etf-intelligence`
- protected baseline tag: `v0.1.6-baseline`
- active development branch: `dev/v0.2`
- do not modify `main` while implementing TASK-001

## What was built before handoff
The project started as a local KIS integration prototype and progressed through these milestones:

### V0.1.0
- KIS OAuth
- domestic current-price smoke tests
- Samsung Electronics, SK hynix, KODEX200
- read-only architecture

### V0.1.1
- token cache
- request throttling
- fixed repeated-token issuance / 403 problem

### V0.1.2
- KODEX200 component adapter
- ETF constituent normalization
- Samsung Electronics / SK hynix look-through
- ETF Gold Case

### V0.1.3
- Direct Exposure
- ETF Indirect Exposure
- cluster exposure report

### V0.1.4
- KIS real account balance adapter
- normalized account positions
- account summary

### V0.1.4.1
- real/paper token separation
- safer KIS error reporting
- real-account environment diagnosis

### V0.1.4.2
- automatic recovery for KIS `EGW00123` expired token
- delete stale cache, issue new token, retry original request once
- no infinite retry loop

### V0.1.5
- real account → KODEX200 look-through pipeline
- True Exposure for underlying securities
- Semiconductor cluster exposure
- KIS buying-power query
- no-credit buying amount/quantity as default Cash Gate

### V0.1.6
- Portfolio Gate
- Single Stock Max Gate
- Semiconductor Cluster Gate
- 30/30/40 Split Buy Gate
- post-buy True/Cluster weight calculations
- deterministic `사자 / 보류` decision input

## Baseline validation
Before GitHub/Codex handoff, local tests passed:
- Gold tests: 16 passed
- Full tests: 17 passed

The live functional test demonstrated an important invariant:
KIS could report positive buying capacity while portfolio concentration gates returned `보류` and final allowed quantity 0. Preserve this behavior.

## Core engineering decisions
1. Read-only first. No live order execution.
2. Live KIS account data is primary for holdings when available.
3. True Exposure = Direct + ETF indirect exposure.
4. Single-stock risk limit uses True Exposure, not direct holding only.
5. Hard-gate denominator is Total Account Value, not securities-only value.
6. Securities-only cluster concentration may be displayed as diagnostics.
7. KIS `nrcvb_buy_amt` / `nrcvb_buy_qty` are the default no-credit buying-power gate.
8. Portfolio policy must remain configurable.
9. Current baseline policy: single stock 30%, Semiconductor cluster 50% configurable baseline, split buy 30/30/40.
10. Portfolio concentration alone normally yields `보류`, not automatic `팔자`.

## Security history / lessons
During setup, the account API initially failed because of environment/account configuration and later because a cached token had expired. These cases were used to harden the client.

Public repository rules:
- never write account numbers to repository files
- never write actual portfolio balances or account screenshots into the repo
- never commit APP Key / APP Secret / tokens
- `.env` and `tokens/` stay ignored

## Current code quality note
The local-development phase created version-suffixed modules such as `*_v0142.py` and `*_v015.py`. Do not create more suffix variants. As V0.2 work stabilizes, plan a safe canonical-name refactor (`client.py`, `account.py`, `etf.py`, `exposure.py`, etc.) while preserving all baseline tests.

## Immediate next task
Implement only `TASK-001 — AI Power ETF 5 Overlap Matrix + Core8 Look-through`.

Start with a repository audit and ticker/data-source verification before implementation.

## Expected first Codex response
Do not start by guessing code. First report:
1. repository audit;
2. existing reusable modules;
3. verified ETF ticker/source status;
4. implementation plan;
5. files expected to change/add;
6. risks or source gaps.

Then implement TASK-001 and run both Gold and full tests.
