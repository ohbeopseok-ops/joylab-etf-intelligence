from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
import requests

from joylab_etf.config import Settings
from joylab_etf.kis import kv_store
from joylab_etf.kis.models import MarketQuote
from joylab_etf.kis.token_store import load_token, save_token

KST = timezone(timedelta(hours=9))

# Cross-invocation throttle: each Vercel webhook call is a fresh process,
# so an in-process "last request time" resets every time and never
# prevents two Telegram messages seconds apart from both racing past
# KIS's per-second limit (EGW00201). Routing every quote/index/investor
# call through _auth_headers (their one shared chokepoint) and throttling
# there via KV closes that gap when KV is configured; when it isn't
# (local dev, GitHub Actions), kv_store.throttle() is a silent no-op and
# behavior is unchanged from before.
KIS_THROTTLE_KEY = "kis:last_call_ts"
KIS_MIN_INTERVAL_SEC = 0.35

class KISClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._access_token: str | None = None

    def authenticate(self) -> None:
        cached = load_token()
        if cached:
            self._access_token = cached.access_token
            return

        url = f"{self.settings.base_url}/oauth2/tokenP"
        payload = {
            "grant_type": "client_credentials",
            "appkey": self.settings.app_key,
            "appsecret": self.settings.app_secret,
        }
        response = requests.post(
            url,
            json=payload,
            headers={"content-type": "application/json"},
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()

        token = data.get("access_token")
        if not token:
            raise RuntimeError(
                f"KIS token 발급 실패: msg_cd={data.get('msg_cd')} "
                f"msg1={data.get('msg1')}"
            )

        expires_in = int(data.get("expires_in", 86400))
        expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=max(60, expires_in - 120)
        )
        save_token(token, expires_at)
        self._access_token = token

    def _auth_headers(self, tr_id: str) -> dict[str, str]:
        if not self._access_token:
            self.authenticate()

        kv_store.throttle(KIS_THROTTLE_KEY, KIS_MIN_INTERVAL_SEC)

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

        response = requests.get(
            url,
            headers=self._auth_headers("FHKST01010100"),
            params=params,
            timeout=15,
        )
        response.raise_for_status()
        data: dict[str, Any] = response.json()

        if data.get("rt_cd") != "0":
            raise RuntimeError(
                f"KIS quote 조회 실패: msg_cd={data.get('msg_cd')} "
                f"msg1={data.get('msg1')}"
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
            per=to_float(output.get("per")),
            pbr=to_float(output.get("pbr")),
            eps=to_float(output.get("eps")),
            bps=to_float(output.get("bps")),
            week52_high=to_float(output.get("w52_hgpr")),
            week52_low=to_float(output.get("w52_lwpr")),
        )
