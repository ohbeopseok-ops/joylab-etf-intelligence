import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from joylab_etf.config import Settings
from joylab_etf.kis.client_v011 import KISClient

settings = Settings.from_env()

if settings.env != "paper":
    raise RuntimeError("V0.1.1 안전장치: KIS_ENV=paper 일 때만 실행됩니다.")

client = KISClient(settings)

symbols = {
    "005930": "삼성전자",
    "000660": "SK하이닉스",
    "069500": "KODEX200",
}

for symbol, name in symbols.items():
    quote = client.get_domestic_quote(symbol)
    data = quote.model_dump(mode="json")
    data["name"] = name
    print(json.dumps(data, ensure_ascii=False, indent=2))
