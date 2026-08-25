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
client.authenticate()

print("[PASS] KIS OAuth 인증 성공")
print(f"[INFO] env={settings.env}")
print(f"[INFO] base_url={settings.base_url}")
print("[SAFE] APP KEY / SECRET / ACCESS TOKEN 미출력")
