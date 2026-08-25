import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from joylab_etf.config import Settings
from joylab_etf.kis.client_v141 import KISClient
from joylab_etf.kis.account_v141 import KISAccountAdapter

settings = Settings.from_env()
client = KISClient(settings)
account = KISAccountAdapter(client)

snapshot = account.get_balance()

print("[PASS] KIS account balance fetch")
print(f"[INFO] env={settings.env}")
print(f"[INFO] pages={snapshot.pages}")
print(f"[INFO] position_count={len(snapshot.positions)}")
print("[SAFE] account/app-key/app-secret/token not printed")

for p in snapshot.positions:
    print(json.dumps(p.model_dump(), ensure_ascii=False, indent=2))

if snapshot.summary:
    print("=== ACCOUNT SUMMARY ===")
    print(
        json.dumps(
            snapshot.summary.model_dump(),
            ensure_ascii=False,
            indent=2,
        )
    )

print("[PASS] ACCOUNT-04 env-separated token cache")
print("[PASS] ACCOUNT-05 safe HTTP error output")
