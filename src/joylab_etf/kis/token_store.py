from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from joylab_etf.kis.kv_store import KVUnavailable, kv_get, kv_set

# Vercel's deployed code directory is read-only at runtime; only /tmp is
# writable, and it's local to a single (possibly short-lived) container.
# When KV is configured (kv_KV_REST_API_URL/TOKEN -- see kv_store.py) the
# token is shared across invocations there instead, which actually solves
# the per-minute token-issuance limit rather than just reducing repeat
# issuance within one cold container. The file path below stays as the
# fallback for local dev, GitHub Actions (no KV secrets there), and any
# environment where KV is unset or unreachable.
TOKEN_DIR = Path("/tmp/joylab_tokens") if os.getenv("VERCEL") else Path("tokens")
TOKEN_PATH = TOKEN_DIR / "kis_token.json"
KV_KEY = "kis:token"

@dataclass
class CachedToken:
    access_token: str
    expires_at: datetime

    @property
    def is_valid(self) -> bool:
        return datetime.now(timezone.utc) < self.expires_at

def _parse(data: dict) -> CachedToken | None:
    try:
        token = data["access_token"]
        expires_at = datetime.fromisoformat(data["expires_at"])
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        cached = CachedToken(access_token=token, expires_at=expires_at)
        return cached if cached.is_valid else None
    except Exception:
        return None

def load_token() -> CachedToken | None:
    try:
        raw = kv_get(KV_KEY)
    except KVUnavailable:
        raw = None
    else:
        if raw is not None:
            try:
                return _parse(json.loads(raw))
            except Exception:
                pass

    if not TOKEN_PATH.exists():
        return None
    try:
        return _parse(json.loads(TOKEN_PATH.read_text(encoding="utf-8")))
    except Exception:
        return None

def save_token(access_token: str, expires_at: datetime) -> None:
    payload = json.dumps(
        {
            "access_token": access_token,
            "expires_at": expires_at.astimezone(timezone.utc).isoformat(),
        },
        ensure_ascii=False,
    )
    ttl_seconds = max(60, int((expires_at - datetime.now(timezone.utc)).total_seconds()))
    try:
        kv_set(KV_KEY, payload, ex_seconds=ttl_seconds)
        return
    except KVUnavailable:
        pass

    TOKEN_DIR.mkdir(parents=True, exist_ok=True)
    TOKEN_PATH.write_text(payload, encoding="utf-8")
