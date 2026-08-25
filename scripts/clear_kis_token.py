import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from joylab_etf.config import Settings
from joylab_etf.kis.token_store_v141 import clear_token

settings = Settings.from_env()

deleted = clear_token(settings.env)

if deleted:
    print(f"[PASS] cleared token env={settings.env}")
else:
    print(f"[INFO] no cached token env={settings.env}")
