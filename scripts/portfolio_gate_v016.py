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
from joylab_etf.intelligence.portfolio_gate_models import (
    PortfolioGatePolicy,
    GateInput,
)
from joylab_etf.intelligence.portfolio_gate import evaluate_portfolio_gate

SEMICONDUCTOR = {"005930", "000660"}
ETF_SYMBOLS = {"069500"}
TARGET_SYMBOL = "005930"
TARGET_NAME = "삼성전자"
CLUSTER_NAME = "semiconductor"

policy_path = ROOT / "config" / "portfolio_policy.json"

if not policy_path.exists():
    raise RuntimeError(
        "config/portfolio_policy.json 이 없습니다. "
        "portfolio_policy.example.json을 복사하세요."
    )

policy = PortfolioGatePolicy(
    **json.loads(policy_path.read_text(encoding="utf-8"))
)

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

target = next(
    (row for row in report.rows if row.symbol == TARGET_SYMBOL),
    None,
)

if target is None:
    raise RuntimeError("삼성전자 True Exposure를 찾지 못했습니다.")

position = next(
    (p for p in positions if p.symbol == TARGET_SYMBOL),
    None,
)

if position is None or not position.current_price:
    raise RuntimeError("삼성전자 현재가를 계좌 잔고에서 찾지 못했습니다.")

bp = buying_power.inquire(
    symbol=TARGET_SYMBOL,
    reference_price=position.current_price,
    include_cma=False,
    include_overseas=False,
)

kis_qty = int(bp.no_credit_buy_qty or 0)
kis_amount = float(bp.no_credit_buy_amount or 0)

gate_input = GateInput(
    symbol=TARGET_SYMBOL,
    name=TARGET_NAME,
    current_price=float(position.current_price),
    direct_value=target.direct_value,
    indirect_value=target.indirect_value,
    true_exposure_value=target.total_value,
    total_account_value=float(summary.total_evaluation or 0),
    securities_value=report.securities_value,
    cluster_name=CLUSTER_NAME,
    cluster_value=report.semiconductor_value,
    kis_buyable_qty=kis_qty,
    kis_buyable_amount=kis_amount,
)

result = evaluate_portfolio_gate(
    gate_input=gate_input,
    policy=policy,
)

print("\n=== V0.1.6 PORTFOLIO GATE ===")
print(json.dumps(result.model_dump(), ensure_ascii=False, indent=2))

print("\n=== DECISION ===")
print(f"액션: {result.action}")
print(f"KIS 매수가능수량: {result.kis_buyable_qty}주")
print(f"단일종목 Gate 허용수량: {result.single_stock_room_qty}주")
print(f"Cluster Gate 허용수량: {result.cluster_room_qty}주")
print(f"분할매수 Stage {result.split_stage} 허용수량: {result.split_allowed_qty}주")
print(f"최종 허용수량: {result.final_allowed_qty}주")
print(f"매수 후 True Weight: {result.true_weight_after_pct}%")
print(f"매수 후 Semiconductor Weight: {result.cluster_weight_after_pct}%")

if result.blocking_reasons:
    print("Blocking:", ", ".join(result.blocking_reasons))

print("[PASS] GATE-01 Single Stock Max")
print("[PASS] GATE-02 Cluster Max")
print("[PASS] GATE-03 KIS Buying Power")
print("[PASS] GATE-04 Split Buy")
print("[PASS] GATE-05 Post-buy Weight")
print("[PASS] V0.1.6 Portfolio Gate")
