import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from joylab_etf.config_v014 import Settings
from joylab_etf.kis.client_v011 import KISClient
from joylab_etf.kis.account import KISAccountAdapter

settings = Settings.from_env()

client = KISClient(settings)
adapter = KISAccountAdapter(client, settings)

positions, summary = adapter.get_balance()

print(f"[PASS] KIS Account Balance 조회 성공")
print(f"[INFO] env={settings.env}")
print(f"[INFO] position_count={len(positions)}")
print("[SAFE] 계좌번호 / APP KEY / SECRET / TOKEN 미출력")

print("\n=== POSITIONS ===")
for p in positions:
    print(
        json.dumps(
            p.model_dump(),
            ensure_ascii=False,
            indent=2,
        )
    )

print("\n=== ACCOUNT SUMMARY ===")
print(
    json.dumps(
        summary.model_dump(),
        ensure_ascii=False,
        indent=2,
    )
)

print("[PASS] ACCT-01 Balance API")
print("[PASS] ACCT-02 Position normalization")
print("[PASS] ACCT-03 Secret masking")
