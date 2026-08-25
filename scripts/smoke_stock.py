import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from joylab_etf.config import Settings
from joylab_etf.kis.client import KISClient

settings = Settings.from_env()

if settings.env != "paper":
    raise RuntimeError("V0.1 안전장치: KIS_ENV=paper 일 때만 실행됩니다.")

client = KISClient(settings)

symbols = ["005930", "000660", "069500"]

for symbol in symbols:
    quote = client.get_domestic_quote(symbol)
    print(json.dumps(quote.model_dump(mode="json"), ensure_ascii=False, indent=2))
