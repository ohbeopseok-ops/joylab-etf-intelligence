# JoyLab ETF Intelligence — SPEC

> Broader engine design (Gates beyond this repo's current implementation, Gold Cases,
> AI Power Gate, Governance/ESR, Pension Flow Rotation): see
> `docs/JOYLAB_INVESTMENT_ENGINE.md`. Read it alongside this file before starting new
> decision-engine work.

## Mission
Read-only investment intelligence engine on Korea Investment & Securities Open API. It reads account/market/ETF data, normalizes it, calculates direct + ETF look-through exposure, concentration and portfolio gates, then produces deterministic decision inputs. It is not an automated trading system.

## Baseline
`v0.1.6-baseline` is the protected local-development baseline.

Validated baseline capabilities:
- KIS OAuth
- real/paper endpoint separation
- environment-separated token cache
- `EGW00123` expired-token recovery with one refresh/retry
- real domestic-stock balance query
- domestic quote query
- KODEX200 constituent query
- buying-power query
- Direct Exposure
- ETF Indirect Exposure
- True Exposure
- Semiconductor Cluster Exposure
- Single Stock Max Gate
- Cluster Max Gate
- 30/30/40 Split Buy Gate
- post-buy weights

No live order execution is allowed.

## Core formulas
`Direct Exposure = held quantity × current market price`

`ETF Indirect Exposure = ETF market value × constituent weight`

`True Exposure = Direct Exposure + Σ ETF Indirect Exposure`

`Cluster Exposure = Σ True Exposure of securities assigned to the cluster`

Hard-gate weights use Total Account Value as denominator:
`True Weight = True Exposure / Total Account Value`
`Cluster Weight = Cluster Exposure / Total Account Value`

Securities-only concentration may be shown diagnostically but is not the default hard-gate denominator.

## Buying Power
Use KIS `inquire-psbl-order` read-only API.
JoyLab default uses no-credit fields:
- `nrcvb_buy_amt`
- `nrcvb_buy_qty`

Do not use account `dnca_tot_amt` as authoritative orderable cash.

## Portfolio Gate
`Final Allowed Qty = min(KIS no-credit buyable qty, Single Stock Gate qty, Cluster Gate qty, Split Buy Gate qty)`

Baseline policy:
- Single stock max: 30% of total account, based on True Exposure
- Semiconductor cluster max: configurable 50% baseline
- Split buy: 30 / 30 / 40

Ability to buy is not permission to buy. A position may have positive KIS buying power while portfolio gates return `보류`.

## Decision semantics
- `사자`: only when strategy/data confidence passes and final allowed qty > 0
- `보류`: buying power exists but risk/data/strategy gate blocks; or allowed qty is 0
- `팔자`: reserved for sell/thesis-break logic; concentration alone does not automatically mean sell

## Data priority
1. KIS live account/market API
2. official ETF constituent source
3. policy config
4. manual fixtures only for tests

## Security
Never commit or log:
- `.env`
- account numbers
- APP Key / APP Secret
- access token
- token cache files

Keep real/paper tokens separate. No infinite auth retry loops.

## Testing contract
Gold Tests are release gates and must not be deleted to make CI pass. Any change to formulas, KIS mappings or normalization requires regression tests.

## V0.2 primary milestone
`AI Power ETF 5 Overlap Matrix + Core8 Look-through`

Required:
- multi-ETF constituent ingestion
- normalized holdings
- weighted pairwise overlap
- common holdings report
- Core8 look-through
- Semiconductor cluster
- Power Equipment cluster
- concentration summary
- Gold Tests
