from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

import requests


class AssistantHandler(Protocol):
    def handle(self, text: str) -> str: ...


@dataclass(frozen=True)
class TelegramSettings:
    bot_token: str = field(repr=False)
    allowed_chat_ids: frozenset[int]
    poll_timeout_sec: int = 30

    def __post_init__(self) -> None:
        if not self.bot_token.strip():
            raise RuntimeError("TELEGRAM_BOT_TOKEN이 비어 있습니다.")
        if not self.allowed_chat_ids:
            raise RuntimeError("TELEGRAM_ALLOWED_CHAT_IDS가 비어 있습니다.")
        if not 1 <= self.poll_timeout_sec <= 50:
            raise RuntimeError("TELEGRAM_POLL_TIMEOUT_SEC는 1~50이어야 합니다.")

    @classmethod
    def from_env(cls) -> "TelegramSettings":
        token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        raw_ids = os.getenv("TELEGRAM_ALLOWED_CHAT_IDS", "").strip()
        try:
            chat_ids = frozenset(
                int(value.strip()) for value in raw_ids.split(",") if value.strip()
            )
        except ValueError as exc:
            raise RuntimeError(
                "TELEGRAM_ALLOWED_CHAT_IDS는 쉼표로 구분한 정수여야 합니다."
            ) from exc
        try:
            timeout = int(os.getenv("TELEGRAM_POLL_TIMEOUT_SEC", "30"))
        except ValueError as exc:
            raise RuntimeError(
                "TELEGRAM_POLL_TIMEOUT_SEC는 정수여야 합니다."
            ) from exc
        return cls(token, chat_ids, timeout)


class TelegramBotClient:
    """Small Bot API client that never exposes the token in raised errors."""

    def __init__(
        self,
        settings: TelegramSettings,
        session: requests.Session | None = None,
    ) -> None:
        self.settings = settings
        self._session = session or requests.Session()

    def _url(self, method: str) -> str:
        return f"https://api.telegram.org/bot{self.settings.bot_token}/{method}"

    def _request(
        self,
        method: str,
        *,
        http_method: str,
        params: dict[str, Any] | None = None,
        payload: dict[str, Any] | None = None,
        timeout: int,
    ) -> Any:
        try:
            response = self._session.request(
                http_method,
                self._url(method),
                params=params,
                json=payload,
                timeout=timeout,
            )
        except requests.RequestException:
            raise RuntimeError("Telegram API 연결에 실패했습니다.") from None

        try:
            body = response.json()
        except (ValueError, TypeError):
            raise RuntimeError(
                f"Telegram API가 잘못된 응답을 반환했습니다 (HTTP {response.status_code})."
            ) from None

        if not response.ok or not isinstance(body, dict) or body.get("ok") is not True:
            description = str(body.get("description", "API error"))[:160]
            description = description.replace(self.settings.bot_token, "[REDACTED]")
            raise RuntimeError(
                f"Telegram API 요청이 거부되었습니다 (HTTP {response.status_code}: "
                f"{description})."
            )
        return body.get("result")

    def get_updates(self, offset: int | None = None) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "timeout": self.settings.poll_timeout_sec,
            "allowed_updates": json.dumps(["message"]),
        }
        if offset is not None:
            params["offset"] = offset
        result = self._request(
            "getUpdates",
            http_method="GET",
            params=params,
            timeout=self.settings.poll_timeout_sec + 10,
        )
        if not isinstance(result, list):
            raise RuntimeError("Telegram updates 형식이 올바르지 않습니다.")
        return [item for item in result if isinstance(item, dict)]

    def send_message(self, chat_id: int, text: str) -> None:
        for chunk in _chunk_text(text):
            self._request(
                "sendMessage",
                http_method="POST",
                payload={"chat_id": chat_id, "text": chunk},
                timeout=20,
            )


def _chunk_text(text: str, limit: int = 3500) -> list[str]:
    clean = text.strip() or "응답 내용이 없습니다."
    chunks: list[str] = []
    while len(clean) > limit:
        cut = clean.rfind("\n", 0, limit + 1)
        if cut <= 0:
            cut = limit
        chunks.append(clean[:cut].rstrip())
        clean = clean[cut:].lstrip()
    chunks.append(clean)
    return chunks


class TelegramAssistantApp:
    def __init__(
        self,
        client: TelegramBotClient,
        assistant: AssistantHandler,
        allowed_chat_ids: frozenset[int],
    ) -> None:
        self.client = client
        self.assistant = assistant
        self.allowed_chat_ids = allowed_chat_ids

    def run_once(self, offset: int | None = None) -> int | None:
        next_offset = offset
        for update in self.client.get_updates(offset):
            update_id = update.get("update_id")
            if isinstance(update_id, int):
                candidate = update_id + 1
                next_offset = max(next_offset or candidate, candidate)

            message = update.get("message")
            if not isinstance(message, dict):
                continue
            chat = message.get("chat")
            text = message.get("text")
            if not isinstance(chat, dict) or not isinstance(text, str):
                continue
            chat_id = chat.get("id")
            if not isinstance(chat_id, int) or chat_id not in self.allowed_chat_ids:
                continue

            try:
                response = self.assistant.handle(text)
            except Exception:  # keep credentials/internal errors out of chat
                response = (
                    "분석 중 오류가 발생했습니다. 로그에는 비밀값을 남기지 않았습니다. "
                    "데이터 연결 상태를 확인해 주세요."
                )
            self.client.send_message(chat_id, response)
        return next_offset

    def run_forever(self) -> None:
        offset: int | None = None
        while True:
            try:
                offset = self.run_once(offset)
            except RuntimeError as exc:
                # Transport errors are already sanitized by TelegramBotClient.
                print(f"Telegram polling retry: {exc}")
                time.sleep(3)
