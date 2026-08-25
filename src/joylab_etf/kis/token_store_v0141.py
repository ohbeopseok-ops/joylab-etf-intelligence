from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

TOKEN_DIR = Path("tokens")


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


def load_token(env: str) -> CachedToken | None:
    path = token_path(env)

    if not path.exists():
        return None

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        expires_at = datetime.fromisoformat(data["expires_at"])
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        token = CachedToken(
            access_token=data["access_token"],
            expires_at=expires_at,
        )
        return token if token.is_valid else None
    except Exception:
        return None


def save_token(env: str, access_token: str, expires_at: datetime) -> None:
    TOKEN_DIR.mkdir(parents=True, exist_ok=True)
    path = token_path(env)

    path.write_text(
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
