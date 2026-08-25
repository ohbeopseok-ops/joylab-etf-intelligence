from __future__ import annotations

from typing import Any
import requests


SENSITIVE_KEYS = {
    "CANO",
    "ACNT_PRDT_CD",
    "appkey",
    "appsecret",
    "authorization",
}


def safe_kis_error(response: requests.Response, context: str) -> RuntimeError:
    try:
        body: Any = response.json()
    except Exception:
        body = response.text[:1000]

    # KIS body 자체에는 보통 계좌번호가 없지만,
    # 혹시 포함되어도 알려진 민감 키를 제거한다.
    if isinstance(body, dict):
        safe_body = {
            k: ("***" if k in SENSITIVE_KEYS else v)
            for k, v in body.items()
        }
    else:
        safe_body = body

    return RuntimeError(
        f"{context}: HTTP {response.status_code}, body={safe_body}"
    )
