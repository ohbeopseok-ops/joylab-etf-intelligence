r"""Run the private JoyLab Telegram stock assistant with long polling.

Usage:
    .\.venv\Scripts\python.exe scripts\telegram_assistant.py

This process provides analysis only. It has no order/trading code.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from joylab_etf.assistant.aliases import (
    load_core8_aliases,
    load_ticker_universe_aliases,
)
from joylab_etf.assistant.stock_assistant import StockAssistantService
from joylab_etf.assistant.telegram import (
    TelegramAssistantApp,
    TelegramBotClient,
    TelegramSettings,
)
from joylab_etf.config import Settings
from joylab_etf.intelligence.decision_engine import load_decision_config
from joylab_etf.intelligence.portfolio_state import PortfolioStateProvider
from joylab_etf.kis.client import KISClient
from joylab_etf.kis.index import KISIndexAdapter
from joylab_etf.kis.investor import KISInvestorAdapter

RULES_PATH = ROOT / "config" / "investment_decision_rules.json"
AI_POWER_PATH = ROOT / "config" / "ai_power_universe.json"
TICKER_UNIVERSE_PATH = ROOT / "config" / "ticker_universe.json"
CONFIG_DIR = ROOT / "config"


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


def load_all_aliases() -> dict[str, str]:
    aliases: dict[str, str] = {}
    aliases.update(load_ticker_universe_aliases(TICKER_UNIVERSE_PATH))
    aliases.update(load_core8_aliases(AI_POWER_PATH))
    aliases.update(load_verified_etf_aliases())
    return aliases


def build_app() -> TelegramAssistantApp:
    telegram_settings = TelegramSettings.from_env()
    kis_client = KISClient(Settings.from_env())
    service = StockAssistantService(
        quote_client=kis_client,
        investor_client=KISInvestorAdapter(kis_client),
        decision_config=load_decision_config(RULES_PATH),
        aliases=load_all_aliases(),
        request_delay_sec=0.35,
        index_client=KISIndexAdapter(kis_client),
        portfolio_provider=PortfolioStateProvider(CONFIG_DIR),
    )
    client = TelegramBotClient(telegram_settings)
    return TelegramAssistantApp(
        client=client,
        assistant=service,
        allowed_chat_ids=telegram_settings.allowed_chat_ids,
    )


def main() -> None:
    app = build_app()
    print(
        "JoyLab Telegram assistant started: analysis-only, private allowlist, "
        "no trading/order API"
    )
    try:
        app.run_forever()
    except KeyboardInterrupt:
        print("JoyLab Telegram assistant stopped.")


if __name__ == "__main__":
    main()
