from __future__ import annotations

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
import requests

from joylab_etf.assistant.stock_assistant import StockAssistantService
from joylab_etf.assistant.telegram import (
    TelegramAssistantApp,
    TelegramBotClient,
    TelegramSettings,
)
from joylab_etf.intelligence.decision_engine import load_decision_config
from joylab_etf.kis.models import MarketQuote

ROOT = Path(__file__).resolve().parents[2]


class FakeQuoteClient:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def get_domestic_quote(self, symbol: str) -> MarketQuote:
        self.calls.append(symbol)
        return MarketQuote(
            symbol=symbol,
            price=250_000,
            change=-1_000,
            change_pct=-0.4,
            timestamp=datetime(2026, 8, 25, 9, 0),
        )


class FakeInvestorClient:
    def get_investor_flow(self, symbol: str) -> list[SimpleNamespace]:
        return [
            SimpleNamespace(
                business_date="20260825",
                individual_net_buy_qty=10,
                foreign_net_buy_qty=-20,
                institution_net_buy_qty=10,
            )
        ]


def build_service() -> tuple[StockAssistantService, FakeQuoteClient]:
    quote = FakeQuoteClient()
    service = StockAssistantService(
        quote,
        FakeInvestorClient(),
        load_decision_config(ROOT / "config" / "investment_decision_rules.json"),
    )
    return service, quote


def test_registered_name_resolves_but_missing_gates_force_hold_zero_qty() -> None:
    service, quote = build_service()

    result = service.handle("/analyze 삼성전자")

    assert quote.calls == ["005930"]
    assert "삼성전자 (005930)" in result
    assert "🟡 보류 / 0주" in result
    assert "❌가격" in result
    assert "확인 필요" in result


def test_exact_unregistered_ticker_is_quoted_but_never_given_buy_signal() -> None:
    service, quote = build_service()

    result = service.handle("123456")

    assert quote.calls == ["123456"]
    assert "판단: 🟡 보류 / 추천수량 0주" in result
    assert "저장된 전략 규칙" in result


def test_invalid_ticker_is_not_guessed_or_queried() -> None:
    service, quote = build_service()

    result = service.handle("삼전")

    assert quote.calls == []
    assert "티커를 추측하지 않습니다" in result


class FakeBotClient:
    def __init__(self, updates: list[dict]) -> None:
        self.updates = updates
        self.sent: list[tuple[int, str]] = []

    def get_updates(self, offset: int | None = None) -> list[dict]:
        return self.updates

    def send_message(self, chat_id: int, text: str) -> None:
        self.sent.append((chat_id, text))


class EchoAssistant:
    def handle(self, text: str) -> str:
        return f"handled:{text}"


def test_telegram_allowlist_silently_ignores_unknown_chat() -> None:
    client = FakeBotClient(
        [
            {"update_id": 1, "message": {"chat": {"id": 999}, "text": "005930"}},
            {"update_id": 2, "message": {"chat": {"id": 123}, "text": "005930"}},
        ]
    )
    app = TelegramAssistantApp(client, EchoAssistant(), frozenset({123}))

    offset = app.run_once()

    assert offset == 3
    assert client.sent == [(123, "handled:005930")]


class FailingSession:
    def request(self, *args, **kwargs):
        raise requests.ConnectionError("secret URL might otherwise leak")


def test_telegram_transport_error_does_not_leak_bot_token() -> None:
    token = "123456:VERY_SECRET_TOKEN"
    client = TelegramBotClient(
        TelegramSettings(token, frozenset({123})),
        session=FailingSession(),
    )

    with pytest.raises(RuntimeError) as exc_info:
        client.get_updates()

    assert token not in str(exc_info.value)
    assert token not in repr(client.settings)
    assert "연결에 실패" in str(exc_info.value)


def test_telegram_settings_require_private_allowlist() -> None:
    with pytest.raises(RuntimeError, match="ALLOWED_CHAT_IDS"):
        TelegramSettings("token", frozenset())
