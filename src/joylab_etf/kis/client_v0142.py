from __future__ import annotations

from datetime import datetime, timedelta, timezone
import time
import requests

from joylab_etf.kis import kv_store
from joylab_etf.kis.token_store_v0142 import load_token, save_token, delete_token

KST = timezone(timedelta(hours=9))

# See kis/client.py's KIS_THROTTLE_KEY comment: the in-process
# _last_request_at below only helps within one invocation (multiple
# account calls handling a single request); the KV throttle is what
# actually spaces out calls across separate Vercel invocations. Uses a
# different key from the quote-side client so account and market-data
# calls don't unnecessarily wait on each other.
KIS_THROTTLE_KEY_ACCOUNT = "kis:last_call_ts:account"


class KISClient:
    def __init__(self, settings, min_interval_sec: float = 0.25):
        self.settings = settings
        self._access_token: str | None = None
        self._last_request_at = 0.0
        self.min_interval_sec = min_interval_sec

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.min_interval_sec:
            time.sleep(self.min_interval_sec - elapsed)
        self._last_request_at = time.monotonic()
        kv_store.throttle(KIS_THROTTLE_KEY_ACCOUNT, self.min_interval_sec)

    def authenticate(self, force_refresh: bool = False) -> str:
        if force_refresh:
            delete_token(self.settings.env)
            self._access_token = None

        if not force_refresh:
            cached = load_token(self.settings.env)
            if cached:
                self._access_token = cached.access_token
                print(f"[PASS] cached KIS token reused ({self.settings.env})")
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
            raise RuntimeError(
                f"KIS OAuth HTTP {response.status_code}: {response.text[:500]}"
            )

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

        save_token(self.settings.env, token, expires_at)
        self._access_token = token
        print(f"[PASS] new KIS token issued and cached ({self.settings.env})")
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

    def authorized_get(
        self,
        url: str,
        tr_id: str,
        params: dict,
        retry_on_expired_token: bool = True,
    ) -> requests.Response:
        self._throttle()

        response = requests.get(
            url,
            headers=self._auth_headers(tr_id),
            params=params,
            timeout=15,
        )

        expired = False

        try:
            body = response.json()
            expired = body.get("msg_cd") == "EGW00123"
        except Exception:
            body = {}

        if expired and retry_on_expired_token:
            print("[INFO] expired token detected -> refreshing")
            self.authenticate(force_refresh=True)

            self._throttle()
            response = requests.get(
                url,
                headers=self._auth_headers(tr_id),
                params=params,
                timeout=15,
            )

        return response
