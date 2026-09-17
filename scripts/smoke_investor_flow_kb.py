import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from joylab_etf.config_v014 import Settings
from joylab_etf.kis.client import KISClient
from joylab_etf.kis.investor_flow_intraday import KISIntradayInvestorFlowAdapter
from joylab_etf.kis.program_trade import KISProgramTradeAdapter


KB_SYMBOL = "105560"
KB_NAME = "KB금융"


settings = Settings.from_env()
client = KISClient(settings)

flow_adapter = KISIntradayInvestorFlowAdapter(client)
program_adapter = KISProgramTradeAdapter(client)

flow = flow_adapter.get_symbol(KB_SYMBOL, name=KB_NAME, market_index_code="0001")
program = program_adapter.get_latest(KB_SYMBOL, market="J")

print("\n=== KB INVESTOR FLOW ===")
print(json.dumps(flow.model_dump(mode="json"), ensure_ascii=False, indent=2))

print("\n=== KB PROGRAM TRADE AUXILIARY ===")
print(json.dumps(program.model_dump(mode="json"), ensure_ascii=False, indent=2))

if flow.status.value == "unavailable":
    print("[WAIT] KB가 장중 가집계 목록에 없습니다. 순매수 0으로 해석하지 않습니다.")
else:
    print("[PASS] KIS intraday investor flow response parsed")

print("[PASS] Program trade auxiliary response parsed")
