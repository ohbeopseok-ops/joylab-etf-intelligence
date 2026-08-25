from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

TOKEN_DIR = Path("tokens")
TOKEN_PATH = TOKEN_DIR / "kis_token.json"

@dataclass
class CachedToken:
    access_token: str
    expires_at: datetime

    @property
    def is_valid(self) -> bool:
        return datetime.now(timezone.utc) < self.expires_at

def load_token() -> CachedToken | None:
    if not TOKEN_PATH.exists():
        return None

    try:
        data = json.loads(TOKEN_PATH.read_text(encoding="utf-8"))
        token = data["access_token"]
        expires_at = datetime.fromisoformat(data["expires_at"])
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        cached = CachedToken(access_token=token, expires_at=expires_at)
        return cached if cached.is_valid else None
    except Exception:
        return None

def save_token(access_token: str, expires_at: datetime) -> None:
    TOKEN_DIR.mkdir(parents=True, exist_ok=True)
    TOKEN_PATH.write_text(
        json.dumps(
            {
                "access_token": access_token,
                "expires_at": expires_at.astimezone(timezone.utc).isoformat(),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
