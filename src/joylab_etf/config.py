from __future__ import annotations

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

PAPER_BASE_URL = "https://openapivts.koreainvestment.com:29443"
REAL_BASE_URL = "https://openapi.koreainvestment.com:9443"

@dataclass(frozen=True)
class Settings:
    app_key: str
    app_secret: str
    env: str
    base_url: str

    @classmethod
    def from_env(cls) -> "Settings":
        app_key = os.getenv("KIS_APP_KEY", "").strip()
        app_secret = os.getenv("KIS_APP_SECRET", "").strip()
        env = os.getenv("KIS_ENV", "paper").strip().lower()

        if not app_key or not app_secret:
            raise RuntimeError(
                "KIS_APP_KEY / KIS_APP_SECRET가 비어 있습니다. "
                ".env 파일에 값을 입력하세요."
            )

        if env not in {"paper", "real"}:
            raise RuntimeError("KIS_ENV는 paper 또는 real 이어야 합니다.")

        base_url = PAPER_BASE_URL if env == "paper" else REAL_BASE_URL
        return cls(
            app_key=app_key,
            app_secret=app_secret,
            env=env,
            base_url=base_url,
        )
