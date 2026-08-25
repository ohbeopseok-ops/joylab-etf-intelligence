from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
import time
import requests

from joylab_etf.config import Settings
from joylab_etf.kis.models import MarketQuote
from joylab_etf.kis.token_store_v141 import load_token, save_token
from joylab_etf.kis.http_utils import safe_kis_error

KST = timezone(timedelta(hours=9))


class KISClient:
    def __init__(self, settings: Settings, min_interval_sec: float = 0.25):
        self.settings = settings
        self._access_token: str | None = None
        self._last_request_at = 0.0
        self.min_interval_sec = min_interval_sec

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.min_interval_sec:
            time.sleep(self.min_interval_sec - elapsed)
        self._last_request_at = time.monotonic()

    def authenticate(self) -> str:
        cached = load_token(self.settings.env)

        if cached:
            self._access_token = cached.access_token
            print(f"[PASS] cached KIS token reused env={self.settings.env}")
            return self._access_token

        url = f"{self.settings.base_url}/oauth2/tokenP"
        payload = {
            "grant_type": "client_credentials",
            "appkey": self.settings.app_key,
            "appsecret": self.settings.app_secret,
        }

        self._throttle()
        response = requests.post(
            url,
            json=payload,
            headers={"content-type": "application/json"},
            timeout=15,
        )

        if not response.ok:
            raise safe_kis_error(response, "KIS token 발급 실패")

        data = response.json()
        token = data.get("access_token")

        if not token:
            raise RuntimeError(
                f"KIS token 응답 이상: "
                f"msg_cd={data.get('msg_cd')} msg1={data.get('msg1')}"
            )

        expires_in = int(data.get("expires_in", 86400))
        expires_at = (
            datetime.now(timezone.utc)
            + timedelta(seconds=max(60, expires_in - 120))
        )

        save_token(
            self.settings.env,
            token,
            expires_at,
        )

        self._access_token = token
        print(f"[PASS] new KIS token issued and cached env={self.settings.env}")
        return token

    def _auth_headers(self, tr_id: str) -> dict[str, str]:
        if not self._access_token:
            self.authenticate()

        return {
            "Content-Type": "application/json; charset=utf-8",
            "authorization": f"Bearer {self._access_token}",
            "appkey": self.settings.app_key,
            "appsecret": self.settings.app_secret,
            "tr_id": tr_id,
            "custtype": "P",
        }

    def get_domestic_quote(self, symbol: str, market: str = "J") -> MarketQuote:
        url = (
            f"{self.settings.base_url}"
            "/uapi/domestic-stock/v1/quotations/inquire-price"
        )
        params = {
            "FID_COND_MRKT_DIV_CODE": market,
            "FID_INPUT_ISCD": symbol,
        }

        self._throttle()
        response = requests.get(
            url,
            headers=self._auth_headers("FHKST01010100"),
            params=params,
            timeout=15,
        )

        if not response.ok:
            raise safe_kis_error(response, f"KIS quote 조회 실패 symbol={symbol}")

        data: dict[str, Any] = response.json()

        if data.get("rt_cd") != "0":
            raise RuntimeError(
                f"KIS quote 조회 실패 symbol={symbol}: "
                f"msg_cd={data.get('msg_cd')} msg1={data.get('msg1')}"
            )

        output = data["output"]

        def to_int(value: Any) -> int | None:
            if value in (None, ""):
                return None
            try:
                return int(float(str(value).replace(",", "")))
            except ValueError:
                return None

        def to_float(value: Any) -> float | None:
            if value in (None, ""):
                return None
            try:
                return float(str(value).replace(",", ""))
            except ValueError:
                return None

        price = to_int(output.get("stck_prpr"))
        if price is None:
            raise RuntimeError("현재가(stck_prpr)가 응답에 없습니다.")

        return MarketQuote(
            symbol=symbol,
            price=price,
            change=to_int(output.get("prdy_vrss")),
            change_pct=to_float(output.get("prdy_ctrt")),
            volume=to_int(output.get("acml_vol")),
            timestamp=datetime.now(KST),
        )
