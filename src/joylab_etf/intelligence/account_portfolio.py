from __future__ import annotations

import json
from pathlib import Path

from joylab_etf.kis.account_models import AccountBalanceSnapshot
from joylab_etf.intelligence.portfolio_models import PositionInput


def load_instrument_registry(path: str | Path) -> tuple[set[str], dict[str, list[str]]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    etfs = set(data.get("etfs", []))
    clusters = data.get("clusters", {})
    return etfs, clusters


def balance_to_positions(
    balance: AccountBalanceSnapshot,
    etf_symbols: set[str],
) -> list[PositionInput]:
    results: list[PositionInput] = []

    for p in balance.positions:
        results.append(
            PositionInput(
                symbol=p.symbol,
                name=p.name,
                quantity=p.quantity,
                type="etf" if p.symbol in etf_symbols else "stock",
            )
        )

    return results
