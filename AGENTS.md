# AGENTS.md — JoyLab ETF Intelligence

## Mission
Improve this repository without weakening financial safety, data integrity, portfolio gates, tests, or secret handling.

## Absolute prohibitions
DO NOT:
1. implement live buy/sell/order execution unless an explicit approved task says so;
2. commit `.env`, token files, account numbers, APP Key, APP Secret, cookies, or credentials;
3. log secrets;
4. delete Gold Tests to make CI pass;
5. change True Exposure math without tests;
6. guess KIS TR IDs, endpoint paths, parameter names, response fields, or ETF tickers;
7. silently change portfolio denominators or `사자/보류/팔자` semantics;
8. replace live KIS positions with stale manual data in production code.

## Evidence rule
For every KIS integration change, verify endpoint, TR ID, params and response fields from official KIS Open Trading API material. If uncertain, document the uncertainty and do not invent a mapping.

## Required workflow
1. Read `SPEC.md`.
2. Read `AGENTS.md`.
3. Read `TASKS.md` and the current task file.
4. Inspect existing code before editing.
5. Identify affected Gold Tests.
6. Implement the smallest coherent change.
7. Add/adjust tests.
8. Run `python -m pytest tests/gold_cases -q`.
9. Run `python -m pytest -q`.
10. Report changed files, test results, risks and unresolved assumptions.

## Architecture rule
Move toward canonical production names rather than creating more version suffixes. Preferred shape:

```text
src/joylab_etf/
  config.py
  kis/
    token_store.py
    client.py
    account.py
    quote.py
    etf.py
    buying_power.py
    models.py
  intelligence/
    lookthrough.py
    exposure.py
    overlap.py
    clusters.py
    portfolio_gate.py
```

Do not create `client_final2.py`, `client_v017.py`, `account_new.py`, etc. Version history belongs in Git.

## Domain invariants
- True Exposure = Direct + ETF Indirect
- Single-stock limits use True Exposure
- hard-gate denominator = Total Account Value unless SPEC explicitly changes
- default buying power = `nrcvb_buy_amt` / `nrcvb_buy_qty`
- final quantity never exceeds any upstream cap
- `보류` is valid even when KIS says the account can buy

## Testing expectations
Preserve tests for:
- real/paper token separation
- expired-token refresh
- balance normalization
- ETF constituent normalization
- direct + indirect exposure
- cluster exposure
- single-stock max block
- cluster max block
- KIS cap
- split-buy cap
- post-buy weights

Add negative tests for missing data/policy and stale/unsupported data where relevant.

## Definition of done
A task is DONE only when code + tests + documentation are consistent, all required tests pass, no secrets are introduced, and task acceptance criteria are satisfied.
