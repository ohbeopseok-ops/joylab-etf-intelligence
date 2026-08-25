import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from joylab_etf.config import Settings
from joylab_etf.kis.client_v011 import KISClient
from joylab_etf.kis.etf import KISETFAdapter
from joylab_etf.intelligence.lookthrough import calculate_target_exposures

ETF_SYMBOL = "069500"
TARGETS = ["005930", "000660"]

settings = Settings.from_env()

if settings.env != "paper":
    raise RuntimeError("V0.1.2 안전장치: KIS_ENV=paper 일 때만 실행됩니다.")

client = KISClient(settings)
adapter = KISETFAdapter(client)

snapshot = adapter.get_components(ETF_SYMBOL)

print(f"[PASS] {ETF_SYMBOL} ETF 구성종목 조회 성공")
print(f"[INFO] constituent_count={len(snapshot.constituents)}")
print(f"[INFO] raw_weight_sum={snapshot.weight_sum:.4f}%")

for target in TARGETS:
    item = snapshot.find(target)
    if item:
        print(
            json.dumps(
                {
                    "symbol": item.symbol,
                    "name": item.name,
                    "weight_pct": item.weight_pct,
                    "current_price": item.current_price,
                    "valuation_amount": item.valuation_amount,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        print(f"[PASS] target found: {target} {item.name}")
    else:
        print(f"[FAIL] target missing: {target}")

# 실제 보유수량을 자동으로 넣기 전까지는 샘플 ETF 평가액 1,000,000원으로 계산.
sample_etf_market_value = 1_000_000

exposures = calculate_target_exposures(
    snapshot=snapshot,
    etf_market_value=sample_etf_market_value,
    target_symbols=TARGETS,
)

print("[LOOK-THROUGH] sample_etf_market_value=1,000,000 KRW")

for row in exposures:
    print(
        json.dumps(
            row.model_dump(),
            ensure_ascii=False,
            indent=2,
        )
    )

missing = [symbol for symbol in TARGETS if snapshot.find(symbol) is None]
if missing:
    raise SystemExit(f"[FAIL] missing targets={missing}")

print("[PASS] ETF-01 KODEX200 Component Adapter")
print("[PASS] ETF-01 Samsung / SK hynix weight extraction")
print("[PASS] ETF-01 Look-through calculation")
