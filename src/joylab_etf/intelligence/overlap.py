from __future__ import annotations

import json
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, Field

from joylab_etf.kis.etf_models import ETFComponentSnapshot


class ConstituentAdapter(Protocol):
    def get_components(self, etf_symbol: str) -> ETFComponentSnapshot: ...


class LoadStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    UNSUPPORTED = "UNSUPPORTED"


class ETFDescriptor(BaseModel):
    symbol: str
    name: str
    ticker_source_url: str
    kis_constituents_verified: bool = False


class SecurityDescriptor(BaseModel):
    symbol: str
    name: str


class AIPowerUniverse(BaseModel):
    verified_on: str
    etfs: list[ETFDescriptor]
    core8: list[SecurityDescriptor]
    clusters: dict[str, list[str]]
    security_source_urls: list[str] = Field(default_factory=list)


class NormalizedHolding(BaseModel):
    symbol: str
    name: str
    weight_pct: float = Field(ge=0)


class NormalizedETFHoldings(BaseModel):
    etf_symbol: str
    etf_name: str
    source: str
    timestamp: datetime
    holdings: list[NormalizedHolding]

    @property
    def weight_sum(self) -> float:
        return round(sum(item.weight_pct for item in self.holdings), 6)

    def find(self, symbol: str) -> NormalizedHolding | None:
        return next((item for item in self.holdings if item.symbol == symbol), None)


class ETFLoadResult(BaseModel):
    descriptor: ETFDescriptor
    status: LoadStatus
    holdings: NormalizedETFHoldings | None = None
    error_message: str | None = None


class OverlapCell(BaseModel):
    status: LoadStatus
    overlap_pct: float | None
    coverage_a_pct: float | None
    coverage_b_pct: float | None


class WeightedOverlapMatrix(BaseModel):
    etf_symbols: list[str]
    cells: dict[str, dict[str, OverlapCell]]

    def cell(self, symbol_a: str, symbol_b: str) -> OverlapCell:
        return self.cells[symbol_a][symbol_b]


class CommonHoldingRow(BaseModel):
    symbol: str
    name: str
    etf_count: int
    total_weight_pct: float
    max_weight_pct: float
    weights_by_etf: dict[str, float]


class CommonHoldingsReport(BaseModel):
    rows: list[CommonHoldingRow]
    included_etfs: list[str]
    unavailable_etfs: dict[str, LoadStatus]


class ETFPosition(BaseModel):
    etf_symbol: str
    market_value: float = Field(ge=0)


class LookThroughRow(BaseModel):
    symbol: str
    name: str
    exposures_by_etf: dict[str, float]
    total_exposure: float
    weight_pct_of_etf_portfolio: float


class LookThroughReport(BaseModel):
    total_etf_market_value: float
    covered_etf_market_value: float
    rows: list[LookThroughRow]
    unavailable_etfs: dict[str, LoadStatus]


class ClusterExposure(BaseModel):
    cluster_name: str
    exposure_value: float
    weight_pct_of_etf_portfolio: float
    rows: list[LookThroughRow]
    unavailable_etfs: dict[str, LoadStatus]


class ConcentrationSummary(BaseModel):
    total_etf_market_value: float
    disclosed_underlying_value: float
    disclosed_coverage_pct: float
    top1_weight_pct: float
    top5_weight_pct: float
    hhi: float
    top_holdings: list[LookThroughRow]
    unavailable_etfs: dict[str, LoadStatus]


def load_ai_power_universe(path: str | Path) -> AIPowerUniverse:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return AIPowerUniverse(**data)


def normalize_snapshot(
    snapshot: ETFComponentSnapshot,
    etf_name: str,
) -> NormalizedETFHoldings:
    aggregated: dict[str, NormalizedHolding] = {}
    for item in snapshot.constituents:
        existing = aggregated.get(item.symbol)
        if existing is None:
            aggregated[item.symbol] = NormalizedHolding(
                symbol=item.symbol,
                name=item.name,
                weight_pct=item.weight_pct,
            )
        else:
            existing.weight_pct = round(existing.weight_pct + item.weight_pct, 6)
            if not existing.name and item.name:
                existing.name = item.name

    return NormalizedETFHoldings(
        etf_symbol=snapshot.etf_symbol,
        etf_name=etf_name,
        source=snapshot.source,
        timestamp=snapshot.timestamp,
        holdings=sorted(aggregated.values(), key=lambda item: item.symbol),
    )


def load_multi_etf_holdings(
    adapter: ConstituentAdapter,
    descriptors: list[ETFDescriptor],
) -> dict[str, ETFLoadResult]:
    results: dict[str, ETFLoadResult] = {}
    for descriptor in descriptors:
        if not descriptor.kis_constituents_verified:
            results[descriptor.symbol] = ETFLoadResult(
                descriptor=descriptor,
                status=LoadStatus.UNSUPPORTED,
                error_message="KIS constituent support is not verified",
            )
            continue

        try:
            snapshot = adapter.get_components(descriptor.symbol)
            results[descriptor.symbol] = ETFLoadResult(
                descriptor=descriptor,
                status=LoadStatus.AVAILABLE,
                holdings=normalize_snapshot(snapshot, descriptor.name),
            )
        except Exception as exc:
            results[descriptor.symbol] = ETFLoadResult(
                descriptor=descriptor,
                status=LoadStatus.UNAVAILABLE,
                error_message=f"{type(exc).__name__}: {exc}",
            )
    return results


def _unavailable_status(a: ETFLoadResult, b: ETFLoadResult) -> LoadStatus:
    if LoadStatus.UNSUPPORTED in {a.status, b.status}:
        return LoadStatus.UNSUPPORTED
    return LoadStatus.UNAVAILABLE


def build_weighted_overlap_matrix(
    results: dict[str, ETFLoadResult],
) -> WeightedOverlapMatrix:
    symbols = list(results)
    cells: dict[str, dict[str, OverlapCell]] = {symbol: {} for symbol in symbols}

    for index_a, symbol_a in enumerate(symbols):
        for index_b in range(index_a, len(symbols)):
            symbol_b = symbols[index_b]
            result_a = results[symbol_a]
            result_b = results[symbol_b]

            if result_a.holdings is None or result_b.holdings is None:
                cell = OverlapCell(
                    status=_unavailable_status(result_a, result_b),
                    overlap_pct=None,
                    coverage_a_pct=(
                        result_a.holdings.weight_sum if result_a.holdings else None
                    ),
                    coverage_b_pct=(
                        result_b.holdings.weight_sum if result_b.holdings else None
                    ),
                )
            else:
                weights_a = {
                    item.symbol: item.weight_pct for item in result_a.holdings.holdings
                }
                weights_b = {
                    item.symbol: item.weight_pct for item in result_b.holdings.holdings
                }
                overlap = sum(
                    min(weight_a, weights_b.get(symbol, 0.0))
                    for symbol, weight_a in weights_a.items()
                )
                cell = OverlapCell(
                    status=LoadStatus.AVAILABLE,
                    overlap_pct=round(overlap, 6),
                    coverage_a_pct=result_a.holdings.weight_sum,
                    coverage_b_pct=result_b.holdings.weight_sum,
                )

            cells[symbol_a][symbol_b] = cell
            cells[symbol_b][symbol_a] = OverlapCell(
                status=cell.status,
                overlap_pct=cell.overlap_pct,
                coverage_a_pct=cell.coverage_b_pct,
                coverage_b_pct=cell.coverage_a_pct,
            )

    return WeightedOverlapMatrix(etf_symbols=symbols, cells=cells)


def _availability(results: dict[str, ETFLoadResult]) -> tuple[list[str], dict[str, LoadStatus]]:
    included = [
        symbol for symbol, result in results.items() if result.holdings is not None
    ]
    unavailable = {
        symbol: result.status
        for symbol, result in results.items()
        if result.holdings is None
    }
    return included, unavailable


def build_common_holdings_report(
    results: dict[str, ETFLoadResult],
    min_etf_count: int = 2,
    top_n: int | None = None,
) -> CommonHoldingsReport:
    combined: dict[str, dict] = {}
    included, unavailable = _availability(results)

    for etf_symbol in included:
        holdings = results[etf_symbol].holdings
        assert holdings is not None
        for item in holdings.holdings:
            row = combined.setdefault(
                item.symbol,
                {"name": item.name, "weights": {}},
            )
            row["weights"][etf_symbol] = item.weight_pct

    rows = [
        CommonHoldingRow(
            symbol=symbol,
            name=value["name"],
            etf_count=len(value["weights"]),
            total_weight_pct=round(sum(value["weights"].values()), 6),
            max_weight_pct=round(max(value["weights"].values()), 6),
            weights_by_etf=dict(sorted(value["weights"].items())),
        )
        for symbol, value in combined.items()
        if len(value["weights"]) >= min_etf_count
    ]
    rows.sort(key=lambda row: (-row.etf_count, -row.total_weight_pct, row.symbol))
    if top_n is not None:
        rows = rows[:top_n]

    return CommonHoldingsReport(
        rows=rows,
        included_etfs=included,
        unavailable_etfs=unavailable,
    )


def build_lookthrough_report(
    results: dict[str, ETFLoadResult],
    positions: list[ETFPosition],
    targets: list[SecurityDescriptor],
) -> LookThroughReport:
    position_values: dict[str, float] = {}
    for position in positions:
        position_values[position.etf_symbol] = round(
            position_values.get(position.etf_symbol, 0.0) + position.market_value,
            2,
        )

    total_value = round(sum(position_values.values()), 2)
    covered_value = round(
        sum(
            value
            for symbol, value in position_values.items()
            if symbol in results and results[symbol].holdings is not None
        ),
        2,
    )
    unavailable = {
        symbol: (
            results[symbol].status if symbol in results else LoadStatus.UNAVAILABLE
        )
        for symbol in position_values
        if symbol not in results or results[symbol].holdings is None
    }

    rows: list[LookThroughRow] = []
    for target in targets:
        exposures: dict[str, float] = {}
        for etf_symbol, market_value in position_values.items():
            result = results.get(etf_symbol)
            if result is None or result.holdings is None:
                continue
            holding = result.holdings.find(target.symbol)
            if holding is not None:
                exposures[etf_symbol] = round(
                    market_value * holding.weight_pct / 100.0,
                    2,
                )
        total_exposure = round(sum(exposures.values()), 2)
        rows.append(
            LookThroughRow(
                symbol=target.symbol,
                name=target.name,
                exposures_by_etf=dict(sorted(exposures.items())),
                total_exposure=total_exposure,
                weight_pct_of_etf_portfolio=(
                    round(total_exposure / total_value * 100.0, 6)
                    if total_value > 0
                    else 0.0
                ),
            )
        )

    return LookThroughReport(
        total_etf_market_value=total_value,
        covered_etf_market_value=covered_value,
        rows=rows,
        unavailable_etfs=unavailable,
    )


def build_cluster_exposure(
    cluster_name: str,
    cluster_symbols: list[str],
    results: dict[str, ETFLoadResult],
    positions: list[ETFPosition],
) -> ClusterExposure:
    names: dict[str, str] = {}
    for result in results.values():
        if result.holdings is None:
            continue
        for item in result.holdings.holdings:
            names.setdefault(item.symbol, item.name)

    targets = [
        SecurityDescriptor(symbol=symbol, name=names.get(symbol, symbol))
        for symbol in cluster_symbols
    ]
    report = build_lookthrough_report(results, positions, targets)
    value = round(sum(row.total_exposure for row in report.rows), 2)
    return ClusterExposure(
        cluster_name=cluster_name,
        exposure_value=value,
        weight_pct_of_etf_portfolio=(
            round(value / report.total_etf_market_value * 100.0, 6)
            if report.total_etf_market_value > 0
            else 0.0
        ),
        rows=[row for row in report.rows if row.total_exposure > 0],
        unavailable_etfs=report.unavailable_etfs,
    )


def build_concentration_summary(
    results: dict[str, ETFLoadResult],
    positions: list[ETFPosition],
    top_n: int = 10,
) -> ConcentrationSummary:
    symbols: dict[str, SecurityDescriptor] = {}
    for result in results.values():
        if result.holdings is None:
            continue
        for item in result.holdings.holdings:
            symbols.setdefault(
                item.symbol,
                SecurityDescriptor(symbol=item.symbol, name=item.name),
            )

    report = build_lookthrough_report(
        results,
        positions,
        list(symbols.values()),
    )
    ranked = sorted(
        (row for row in report.rows if row.total_exposure > 0),
        key=lambda row: (-row.total_exposure, row.symbol),
    )
    disclosed = round(sum(row.total_exposure for row in ranked), 2)
    denominator = report.total_etf_market_value
    weights = [
        row.total_exposure / denominator * 100.0 for row in ranked
    ] if denominator > 0 else []

    return ConcentrationSummary(
        total_etf_market_value=denominator,
        disclosed_underlying_value=disclosed,
        disclosed_coverage_pct=(
            round(disclosed / denominator * 100.0, 6) if denominator > 0 else 0.0
        ),
        top1_weight_pct=round(weights[0], 6) if weights else 0.0,
        top5_weight_pct=round(sum(weights[:5]), 6),
        hhi=round(sum(weight * weight for weight in weights), 6),
        top_holdings=ranked[:top_n],
        unavailable_etfs=report.unavailable_etfs,
    )
