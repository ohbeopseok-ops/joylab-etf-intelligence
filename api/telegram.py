"""Vercel serverless webhook for the JoyLab Telegram stock assistant.

This is a thin transport adapter only. All KIS/decision logic lives in
src/joylab_etf/assistant/stock_assistant.py and
src/joylab_etf/assistant/telegram.py (same modules the local long-polling
scripts/telegram_assistant.py uses) -- nothing here duplicates that logic.
Point Telegram's setWebhook at this deployment's /api/telegram URL instead
of running the local polling script.

Env vars required (set in the Vercel project's Environment Variables UI,
never committed and never entered by an agent):
    KIS_APP_KEY, KIS_APP_SECRET, KIS_ENV
    TELEGRAM_BOT_TOKEN, TELEGRAM_ALLOWED_CHAT_IDS
Optional:
    TELEGRAM_WEBHOOK_SECRET -- if set, incoming requests must carry a
    matching X-Telegram-Bot-Api-Secret-Token header (the same value passed
    as secret_token to Telegram's setWebhook call). Requests without a
    match get 401 and are never handed to the assistant.

No order/trading code exists anywhere in this call path.
"""

from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from joylab_etf.assistant.stock_assistant import StockAssistantService
from joylab_etf.assistant.telegram import TelegramBotClient, TelegramSettings
from joylab_etf.config import Settings
from joylab_etf.intelligence.decision_engine import load_decision_config
from joylab_etf.kis.client import KISClient
from joylab_etf.kis.investor import KISInvestorAdapter

RULES_PATH = ROOT / "config" / "investment_decision_rules.json"
AI_POWER_PATH = ROOT / "config" / "ai_power_universe.json"


def load_verified_etf_aliases(path: Path = AI_POWER_PATH) -> dict[str, str]:
    """Load names only for ETFs explicitly marked KIS-verified in TASK-001 data."""
    data = json.loads(path.read_text(encoding="utf-8"))
    aliases: dict[str, str] = {}
    for item in data.get("etfs", []):
        if item.get("kis_constituents_verified") is not True:
            continue
        symbol = item.get("symbol")
        name = item.get("name")
        if isinstance(symbol, str) and isinstance(name, str):
            aliases[name] = symbol
    return aliases


def build_service_and_client() -> tuple[StockAssistantService, TelegramBotClient, TelegramSettings]:
    telegram_settings = TelegramSettings.from_env()
    kis_client = KISClient(Settings.from_env())
    service = StockAssistantService(
        quote_client=kis_client,
        investor_client=KISInvestorAdapter(kis_client),
        decision_config=load_decision_config(RULES_PATH),
        aliases=load_verified_etf_aliases(),
        request_delay_sec=0.35,
    )
    client = TelegramBotClient(telegram_settings)
    return service, client, telegram_settings


class handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # health check for deploy verification
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"JoyLab telegram webhook: ok")

    def do_POST(self) -> None:
        configured_secret = os.getenv("TELEGRAM_WEBHOOK_SECRET", "").strip()
        if configured_secret:
            provided = self.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
            if provided != configured_secret:
                self.send_response(401)
                self.end_headers()
                return

        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length) if length > 0 else b"{}"

        try:
            update = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            update = None

        # Ack 200 immediately regardless of payload shape so Telegram does
        # not retry-storm a malformed or irrelevant update.
        self.send_response(200)
        self.end_headers()

        message = update.get("message") if isinstance(update, dict) else None
        chat = message.get("chat") if isinstance(message, dict) else None
        text = message.get("text") if isinstance(message, dict) else None
        chat_id = chat.get("id") if isinstance(chat, dict) else None
        print(f"[diag] incoming chat_id={chat_id!r} text={text!r}")

        if not isinstance(chat_id, int) or not isinstance(text, str):
            print(f"[diag] skip: chat_id_type={type(chat_id).__name__} text_type={type(text).__name__}")
            return

        try:
            service, client, telegram_settings = build_service_and_client()
        except Exception as exc:
            print(f"[diag] build_service_and_client failed: {type(exc).__name__}: {exc}")
            return  # misconfigured env vars -- nothing safe to reply with

        if chat_id not in telegram_settings.allowed_chat_ids:
            print(f"[diag] chat_id {chat_id} not in allowlist {sorted(telegram_settings.allowed_chat_ids)}")
            return

        try:
            response = service.handle(text)
            print(f"[diag] service.handle ok, response_len={len(response)}")
        except Exception as exc:  # keep credentials/internal errors out of chat
            print(f"[diag] service.handle failed: {type(exc).__name__}: {exc}")
            response = (
                "분석 중 오류가 발생했습니다. 로그에는 비밀값을 남기지 않았습니다. "
                "데이터 연결 상태를 확인해 주세요."
            )

        try:
            client.send_message(chat_id, response)
            print("[diag] send_message ok")
        except Exception as exc:
            print(f"[diag] send_message failed: {type(exc).__name__}: {exc}")
