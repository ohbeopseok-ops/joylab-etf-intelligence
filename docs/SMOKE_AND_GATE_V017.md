# JoyLab Investor Flow V0.1.7 Runbook

## 1. Branch

```powershell
git fetch origin
git switch feature/investor-flow-v017
```

## 2. Environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Required `.env` values:

```text
KIS_APP_KEY=...
KIS_APP_SECRET=...
KIS_ENV=real
KIS_ACCOUNT_NO=...
KIS_ACCOUNT_PRODUCT_CODE=...
```

Never commit or paste real keys/secrets.

## 3. Smoke

```powershell
python scripts\smoke_auth.py
python scripts\smoke_investor_flow_kb.py
```

Expected checks:

- KB symbol is `105560`
- flow status is `estimated` or explicitly `unavailable`
- `source_tr_id` is `FHPTJ04400000`
- missing list membership is NOT interpreted as net buy 0
- program trade is returned separately as auxiliary signal

## 4. GOLD tests

```powershell
pytest tests\gold_cases\test_entry_gate_kb.py -q
pytest -q
```

Expected GOLD behavior:

- price >= 181,600 and hold >= 15m + fresh primary flow + score >= 80 => READY
- primary flow unavailable/stale => never READY
- positive program trade alone => WAIT at most
- price trigger not met with weak flow => NO_ENTRY

## 5. Gateway

Run from repo root with `src` on `PYTHONPATH`:

```powershell
$env:PYTHONPATH = "$PWD\src"
uvicorn joylab_etf.api.app:app --host 0.0.0.0 --port 8787
```

Health:

```powershell
Invoke-RestMethod http://127.0.0.1:8787/health
```

KB snapshot:

```powershell
Invoke-RestMethod "http://127.0.0.1:8787/v1/market/105560/snapshot?name=KB금융"
```

Useful endpoints:

- `/health`
- `/v1/market/{symbol}/quote`
- `/v1/market/{symbol}/investor-flow`
- `/v1/market/{symbol}/program-trade`
- `/v1/market/{symbol}/snapshot`

## 6. PC / Mobile architecture rule

The browser/PWA must never receive `KIS_APP_KEY` or `KIS_APP_SECRET`.
Only the Gateway talks to KIS. PC and mobile consume the Gateway API.

## 7. Release gate

Do not merge PR #2 until:

1. live KIS smoke response parsed successfully,
2. field mapping verified against actual payload,
3. KB GOLD tests green,
4. full pytest green,
5. API health + KB snapshot verified locally.
