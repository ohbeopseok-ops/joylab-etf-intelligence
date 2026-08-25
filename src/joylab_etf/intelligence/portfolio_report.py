from __future__ import annotations

import json
from pathlib import Path

from joylab_etf.kis.client_v011 import KISClient
from joylab_etf.kis.etf import KISETFAdapter
from joylab_etf.intelligence.portfolio_models import (
    PositionInput,
    PositionValuation,
    ExposureRow,
    PortfolioExposureReport,
)


def load_portfolio(path: str | Path) -> tuple[list[PositionInput], dict[str, list[str]]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    positions = [PositionInput(**x) for x in data.get("positions", [])]
    clusters = data.get("clusters", {})
    return positions, clusters


def build_portfolio_exposure_report(
    client: KISClient,
    etf_adapter: KISETFAdapter,
    positions: list[PositionInput],
    clusters: dict[str, list[str]],
) -> tuple[list[PositionValuation], PortfolioExposureReport]:
    valuations: list[PositionValuation] = []

    for p in positions:
        if p.quantity <= 0:
            continue
        quote = client.get_domestic_quote(p.symbol)
        valuations.append(
            PositionValuation(
                symbol=p.symbol,
                name=p.name,
                quantity=p.quantity,
                price=quote.price,
                market_value=round(p.quantity * quote.price, 2),
                type=p.type,
            )
        )

    exposures: dict[str, ExposureRow] = {}

    # Direct stock exposure
    for v in valuations:
        if v.type != "stock":
            continue
        row = exposures.setdefault(
            v.symbol,
            ExposureRow(symbol=v.symbol, name=v.name),
        )
        row.direct_value = round(row.direct_value + v.market_value, 2)

    # ETF look-through exposure
    for v in valuations:
        if v.type != "etf":
            continue

        snapshot = etf_adapter.get_components(v.symbol)

        for c in snapshot.constituents:
            indirect = round(v.market_value * c.weight_pct / 100.0, 2)
            row = exposures.setdefault(
                c.symbol,
                ExposureRow(symbol=c.symbol, name=c.name),
            )
            row.indirect_value = round(row.indirect_value + indirect, 2)

    total_portfolio_value = round(sum(v.market_value for v in valuations), 2)

    cluster_values: dict[str, float] = {}
    cluster_weights_pct: dict[str, float] = {}

    for cluster_name, symbols in clusters.items():
        value = round(
            sum(
                exposures[s].total_value
                for s in symbols
                if s in exposures
            ),
            2,
        )
        cluster_values[cluster_name] = value
        cluster_weights_pct[cluster_name] = (
            round(value / total_portfolio_value * 100.0, 2)
            if total_portfolio_value > 0
            else 0.0
        )

    report = PortfolioExposureReport(
        total_portfolio_value=total_portfolio_value,
        exposures=sorted(
            exposures.values(),
            key=lambda x: x.total_value,
            reverse=True,
        ),
        cluster_values=cluster_values,
        cluster_weights_pct=cluster_weights_pct,
    )

    return valuations, report
