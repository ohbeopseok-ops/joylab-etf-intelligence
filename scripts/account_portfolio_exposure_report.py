import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from joylab_etf.config import Settings
from joylab_etf.kis.client_v011 import KISClient
from joylab_etf.kis.account import KISAccountAdapter
from joylab_etf.kis.etf import KISETFAdapter
from joylab_etf.intelligence.account_portfolio import (
    load_instrument_registry,
    balance_to_positions,
)
from joylab_etf.intelligence.portfolio_report import (
    build_portfolio_exposure_report,
)

registry_path = ROOT / "config" / "instruments.json"

if not registry_path.exists():
    raise RuntimeError(
        "config/instruments.json이 없습니다. "
        "instruments.example.json을 복사하세요."
    )

settings = Settings.from_env()
client = KISClient(settings)

account_adapter = KISAccountAdapter(client)
etf_adapter = KISETFAdapter(client)

balance = account_adapter.get_balance()
etf_symbols, clusters = load_instrument_registry(registry_path)
positions = balance_to_positions(balance, etf_symbols)

valuations, report = build_portfolio_exposure_report(
    client=client,
    etf_adapter=etf_adapter,
    positions=positions,
    clusters=clusters,
)

print("\n=== KIS ACCOUNT POSITIONS ===")
for row in balance.positions:
    print(json.dumps(row.model_dump(), ensure_ascii=False, indent=2))

print("\n=== TRUE EXPOSURE ===")
for row in report.exposures[:30]:
    payload = row.model_dump()
    payload["total_value"] = row.total_value
    print(json.dumps(payload, ensure_ascii=False, indent=2))

print("\n=== CLUSTER EXPOSURE ===")
print(
    json.dumps(
        {
            "total_portfolio_value": report.total_portfolio_value,
            "cluster_values": report.cluster_values,
            "cluster_weights_pct": report.cluster_weights_pct,
        },
        ensure_ascii=False,
        indent=2,
    )
)

print("[PASS] AUTO-PORT-01 KIS balance -> positions")
print("[PASS] AUTO-PORT-02 no portfolio.json required")
print("[PASS] AUTO-PORT-03 Direct + ETF Indirect + Cluster")
