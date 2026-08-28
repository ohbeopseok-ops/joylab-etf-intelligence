# JoyLab CI Standard V1.0 Adoption — ETF Intelligence

## Status
CANDIDATE until the adoption PR completes its repository-native CI.

## Canonical stage model
`C0 Import → C1 Collection → C2 Unit → C3 Schema/Contract → C4 Gold Case → C5 E2E`

This repository adopts the execution model defined by `joylab-core8-engine/docs/CI_STANDARD_V1.0.md` while keeping repository-specific commands local.

## Repository mapping
- C0 Import: `import joylab_etf`
- C1 Collection: `pytest --collect-only -q`
- C2 Unit: all `tests/` except `tests/gold_cases/`
- C3 Schema/Contract: `NOT_APPLICABLE` for the adoption baseline because no frozen repository-native schema/contract suite exists yet
- C4 Gold Case: `pytest -q tests/gold_cases`
- C5 E2E: `NOT_APPLICABLE` for the adoption baseline because no repository-native E2E suite exists yet

## N/A policy
`NOT_APPLICABLE` is explicit and temporary. It is not PASS-by-absence. When a durable schema/contract or E2E runtime is introduced, C3 or C5 must be replaced with an executable gate in the same change that introduces that behavior.

## Existing workflow preservation
`.github/workflows/gate_scan.yml` remains independent and authoritative for its existing scope. This adoption does not delete or weaken it.

## Promotion rule
The adoption is VERIFIED only after the new `ci-standard-v1` workflow succeeds on its own PR. CI GREEN does not itself certify investment logic or Gold Case promotion status.
