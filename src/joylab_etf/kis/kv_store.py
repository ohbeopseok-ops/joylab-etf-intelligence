"""Thin wrapper over the Upstash Redis REST API (kv_KV_REST_API_URL /
kv_KV_REST_API_TOKEN -- see Vercel Storage -> Upstash for Redis integration
on this project, custom prefix "kv"). Exists to share KIS token cache and
a request-throttle timestamp across Vercel's stateless per-invocation
serverless processes, which a local file (or /tmp) cannot do.

Every function here degrades by raising KVUnavailable rather than
crashing the caller -- KV is an optimization, not a hard dependency.
Callers (token_store.py, token_store_v0142.py, KIS clients) must catch
KVUnavailable and fall back to their pre-KV behavior (file cache,
in-process throttle).
"""

from __future__ import annotations

import os
import time

import requests

KV_URL_ENV = "kv_KV_REST_API_URL"
KV_TOKEN_ENV = "kv_KV_REST_API_TOKEN"


class KVUnavailable(Exception):
    """KV isn't configured, or a request to it failed. Never fatal to the
    caller -- always fall back to the pre-KV behavior."""


def _base_url_and_token() -> tuple[str, str]:
    url = os.getenv(KV_URL_ENV, "").strip()
    token = os.getenv(KV_TOKEN_ENV, "").strip()
    if not url or not token:
        raise KVUnavailable(f"{KV_URL_ENV}/{KV_TOKEN_ENV}가 설정되지 않았습니다.")
    return url.rstrip("/"), token


def kv_get(key: str) -> str | None:
    url, token = _base_url_and_token()
    try:
        response = requests.get(
            f"{url}/get/{key}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=5,
        )
        response.raise_for_status()
        body = response.json()
    except Exception as exc:
        raise KVUnavailable(f"KV GET 실패: {type(exc).__name__}") from None
    if "error" in body:
        raise KVUnavailable(f"KV GET 오류: {body['error']}")
    return body.get("result")


def kv_set(key: str, value: str, ex_seconds: int | None = None) -> None:
    url, token = _base_url_and_token()
    params = {"EX": ex_seconds} if ex_seconds else None
    try:
        response = requests.post(
            f"{url}/set/{key}",
            data=value.encode("utf-8"),
            headers={"Authorization": f"Bearer {token}"},
            params=params,
            timeout=5,
        )
        response.raise_for_status()
        body = response.json()
    except Exception as exc:
        raise KVUnavailable(f"KV SET 실패: {type(exc).__name__}") from None
    if "error" in body:
        raise KVUnavailable(f"KV SET 오류: {body['error']}")


def kv_del(key: str) -> None:
    url, token = _base_url_and_token()
    try:
        response = requests.get(
            f"{url}/del/{key}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=5,
        )
        response.raise_for_status()
        body = response.json()
    except Exception as exc:
        raise KVUnavailable(f"KV DEL 실패: {type(exc).__name__}") from None
    if "error" in body:
        raise KVUnavailable(f"KV DEL 오류: {body['error']}")


def throttle(key: str, min_interval_sec: float) -> None:
    """Best-effort cross-invocation throttle: sleeps just enough so that
    calls sharing `key` (across separate Vercel invocations, via KV) are
    at least min_interval_sec apart. Silently does nothing if KV isn't
    configured or a request to it fails -- the caller's own in-process
    throttle (if any) is the fallback in that case, same as before KV
    existed.
    """
    try:
        raw = kv_get(key)
    except KVUnavailable:
        return

    now = time.time()
    if raw is not None:
        try:
            elapsed = now - float(raw)
        except ValueError:
            elapsed = min_interval_sec
        if elapsed < min_interval_sec:
            time.sleep(min_interval_sec - elapsed)

    try:
        kv_set(key, str(time.time()), ex_seconds=60)
    except KVUnavailable:
        pass
