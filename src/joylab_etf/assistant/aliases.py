from __future__ import annotations

import json
from pathlib import Path


def load_ticker_universe_aliases(path: str | Path) -> dict[str, str]:
    """Name -> symbol map from a curated ticker universe file.

    Deliberately carries no price/flow thresholds. A symbol with no matching
    watch_rule in investment_decision_rules.json still reports quote + flow
    only and defaults to 보류/0주 -- this file only lets the assistant
    resolve a Korean name to a symbol, nothing more.
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    aliases: dict[str, str] = {}
    for item in data.get("tickers", []):
        symbol = item.get("symbol")
        name = item.get("name")
        if isinstance(symbol, str) and isinstance(name, str):
            aliases[name] = symbol
            for extra_name in item.get("aliases", []):
                if isinstance(extra_name, str):
                    aliases[extra_name] = symbol
    return aliases


def load_core8_aliases(ai_power_universe_path: str | Path) -> dict[str, str]:
    """Name -> symbol map for the Core8 entries in the TASK-001 AI Power universe file."""
    data = json.loads(Path(ai_power_universe_path).read_text(encoding="utf-8"))
    aliases: dict[str, str] = {}
    for item in data.get("core8", []):
        symbol = item.get("symbol")
        name = item.get("name")
        if isinstance(symbol, str) and isinstance(name, str):
            aliases[name] = symbol
    return aliases
