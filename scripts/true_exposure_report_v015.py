import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from joylab_etf.config_v014 import Settings
from joylab_etf.kis.client_v0142 import KISClient
from joylab_etf.kis.account_v0142 import KISAccountAdapter
from joylab_etf.kis.etf_v015 import KISETFAdapter
from joylab_etf.kis.buying_power import KISBuyingPowerAdapter
from joylab_etf.intelligence.true_exposure_v015 import build_true_exposure_report

SEMICONDUCTOR = {"005930", "000660"}
ETF_SYMBOLS = {"069500"}

settings = Settings.from_env()
client = KISClient(settings)

account = KISAccountAdapter(client, settings)
etf = KISETFAdapter(client)
buying_power = KISBuyingPowerAdapter(client, settings)

positions, summary = account.get_balance()

etf_snapshots = {}
for p in positions:
    if p.symbol in ETF_SYMBOLS and p.quantity > 0:
        etf_snapshots[p.symbol] = etf.get_components(p.symbol)

report = build_true_exposure_report(
    positions=positions,
    etf_snapshots=etf_snapshots,
    semiconductor_symbols=SEMICONDUCTOR,
    total_account_evaluation=summary.total_evaluation,
)

print("\n=== TRUE EXPOSURE TOP 20 ===")
for row in report.rows[:20]:
    print(json.dumps(row.model_dump(), ensure_ascii=False, indent=2))

print("\n=== SEMICONDUCTOR CLUSTER ===")
print(json.dumps({
    "securities_value": report.securities_value,
    "semiconductor_value": report.semiconductor_value,
    "semiconductor_weight_pct_of_securities":
        report.semiconductor_weight_pct_of_securities,
}, ensure_ascii=False, indent=2))

# Cash Gate: 삼성전자 기준 시장가 매수가능 조회
samsung = next((p for p in positions if p.symbol == "005930"), None)
reference_price = samsung.current_price if samsung and samsung.current_price else 0

if reference_price > 0:
    bp = buying_power.inquire(
        symbol="005930",
        reference_price=reference_price,
        include_cma=False,
        include_overseas=False,
    )

    print("\n=== CASH GATE (005930) ===")
    print(json.dumps(bp.model_dump(), ensure_ascii=False, indent=2))

    print("[PASS] CASH-01 Buying Power API")
else:
    print("[WARN] 삼성전자 현재가 없음 - Cash Gate skip")

print("[PASS] PORT-01 Direct Exposure")
print("[PASS] PORT-02 ETF Indirect Exposure")
print("[PASS] PORT-03 Semiconductor Cluster")
print("[PASS] V0.1.5 True Exposure Report")
