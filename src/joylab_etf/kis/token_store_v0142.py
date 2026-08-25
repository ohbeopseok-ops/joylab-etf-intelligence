from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from joylab_etf.kis.kv_store import KVUnavailable, kv_del, kv_get, kv_set

# See kis/token_store.py for why this must not be a relative path on Vercel
# (deployed code directory is read-only at runtime; only /tmp is writable)
# and for why KV (when configured) is tried first: it actually shares the
# token across invocations instead of just reducing repeat issuance within
# one cold container.
TOKEN_DIR = Path("/tmp/joylab_tokens") if os.getenv("VERCEL") else Path("tokens")


@dataclass
class CachedToken:
    access_token: str
    expires_at: datetime

    @property
    def is_valid(self) -> bool:
        return datetime.now(timezone.utc) < self.expires_at


def token_path(env: str) -> Path:
    safe_env = "real" if env == "real" else "paper"
    return TOKEN_DIR / f"kis_{safe_env}_token.json"


def _kv_key(env: str) -> str:
    safe_env = "real" if env == "real" else "paper"
    return f"kis:token:v0142:{safe_env}"


def _parse(data: dict) -> CachedToken | None:
    try:
        expires_at = datetime.fromisoformat(data["expires_at"])
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        token = CachedToken(access_token=data["access_token"], expires_at=expires_at)
        return token if token.is_valid else None
    except Exception:
        return None


def load_token(env: str) -> CachedToken | None:
    try:
        raw = kv_get(_kv_key(env))
    except KVUnavailable:
        raw = None
    else:
        if raw is not None:
            try:
                return _parse(json.loads(raw))
            except Exception:
                pass

    path = token_path(env)
    if not path.exists():
        return None
    try:
        return _parse(json.loads(path.read_text(encoding="utf-8")))
    except Exception:
        return None


def save_token(env: str, access_token: str, expires_at: datetime) -> None:
    payload = json.dumps(
        {
            "access_token": access_token,
            "expires_at": expires_at.astimezone(timezone.utc).isoformat(),
        },
        ensure_ascii=False,
    )
    ttl_seconds = max(60, int((expires_at - datetime.now(timezone.utc)).total_seconds()))
    try:
        kv_set(_kv_key(env), payload, ex_seconds=ttl_seconds)
        return
    except KVUnavailable:
        pass

    TOKEN_DIR.mkdir(parents=True, exist_ok=True)
    token_path(env).write_text(payload, encoding="utf-8")


def delete_token(env: str) -> None:
    try:
        kv_del(_kv_key(env))
    except KVUnavailable:
        pass

    path = token_path(env)
    if path.exists():
        path.unlink()
