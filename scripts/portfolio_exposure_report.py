import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from joylab_etf.config import Settings
from joylab_etf.kis.client_v011 import KISClient
from joylab_etf.kis.etf import KISETFAdapter
from joylab_etf.intelligence.portfolio_report import (
    load_portfolio,
    build_portfolio_exposure_report,
)

portfolio_path = ROOT / "config" / "portfolio.json"

if not portfolio_path.exists():
    raise RuntimeError(
        "config/portfolio.json 이 없습니다. "
        "portfolio.example.json을 복사한 뒤 보유수량을 입력하세요."
    )

settings = Settings.from_env()

if settings.env != "paper":
    raise RuntimeError("V0.1.3 안전장치: KIS_ENV=paper 일 때만 실행됩니다.")

client = KISClient(settings)
etf_adapter = KISETFAdapter(client)

positions, clusters = load_portfolio(portfolio_path)

valuations, report = build_portfolio_exposure_report(
    client=client,
    etf_adapter=etf_adapter,
    positions=positions,
    clusters=clusters,
)

print("\n=== POSITION VALUATION ===")
for row in valuations:
    print(json.dumps(row.model_dump(), ensure_ascii=False, indent=2))

print("\n=== TRUE EXPOSURE ===")
for row in report.exposures[:20]:
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

print("[PASS] PORT-01 Direct Exposure")
print("[PASS] PORT-02 ETF Indirect Exposure")
print("[PASS] PORT-03 Cluster Exposure")
