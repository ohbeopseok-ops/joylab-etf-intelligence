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
    account_no: str
    account_product_code: str

    @classmethod
    def from_env(cls) -> "Settings":
        app_key = os.getenv("KIS_APP_KEY", "").strip()
        app_secret = os.getenv("KIS_APP_SECRET", "").strip()
        env = os.getenv("KIS_ENV", "paper").strip().lower()

        account_no = os.getenv("KIS_ACCOUNT_NO", "").strip().replace("-", "")
        product_code = os.getenv("KIS_ACCOUNT_PRODUCT_CODE", "").strip()

        if not app_key or not app_secret:
            raise RuntimeError("KIS_APP_KEY / KIS_APP_SECRET가 비어 있습니다.")

        if env not in {"paper", "real"}:
            raise RuntimeError("KIS_ENV는 paper 또는 real 이어야 합니다.")

        # 10자리 전체 계좌번호를 KIS_ACCOUNT_NO 하나에 넣어도 자동 분리
        if len(account_no) == 10 and not product_code:
            account_no, product_code = account_no[:8], account_no[8:]

        if len(account_no) != 8:
            raise RuntimeError(
                "KIS_ACCOUNT_NO는 종합계좌번호 앞 8자리여야 합니다. "
                "또는 10자리 전체 번호를 입력하면 자동 분리합니다."
            )

        if len(product_code) != 2:
            raise RuntimeError(
                "KIS_ACCOUNT_PRODUCT_CODE는 계좌상품코드 뒤 2자리여야 합니다."
            )

        base_url = PAPER_BASE_URL if env == "paper" else REAL_BASE_URL

        return cls(
            app_key=app_key,
            app_secret=app_secret,
            env=env,
            base_url=base_url,
            account_no=account_no,
            account_product_code=product_code,
        )
