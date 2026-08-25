from __future__ import annotations

from pydantic import BaseModel


class TrueExposureRow(BaseModel):
    symbol: str
    name: str
    direct_value: float
    indirect_value: float
    total_value: float
    portfolio_weight_pct: float


class TrueExposureReport(BaseModel):
    securities_value: float
    total_account_evaluation: float | None
    rows: list[TrueExposureRow]
    semiconductor_value: float
    semiconductor_weight_pct_of_securities: float


def build_true_exposure_report(
    positions,
    etf_snapshots: dict[str, object],
    semiconductor_symbols: set[str],
    total_account_evaluation: float | None = None,
) -> TrueExposureReport:
    exposure: dict[str, dict] = {}

    securities_value = sum((p.market_value or 0) for p in positions)

    for p in positions:
        if p.symbol in etf_snapshots:
            continue
        exposure[p.symbol] = {
            "name": p.name,
            "direct": p.market_value or 0.0,
            "indirect": 0.0,
        }

    for p in positions:
        snapshot = etf_snapshots.get(p.symbol)
        if snapshot is None:
            continue

        etf_value = p.market_value or 0.0

        for c in snapshot.constituents:
            row = exposure.setdefault(
                c.symbol,
                {"name": c.name, "direct": 0.0, "indirect": 0.0},
            )
            row["indirect"] += etf_value * c.weight_pct / 100.0

    rows: list[TrueExposureRow] = []

    for symbol, values in exposure.items():
        total = values["direct"] + values["indirect"]
        weight = (total / securities_value * 100.0) if securities_value > 0 else 0.0
        rows.append(
            TrueExposureRow(
                symbol=symbol,
                name=values["name"],
                direct_value=round(values["direct"], 2),
                indirect_value=round(values["indirect"], 2),
                total_value=round(total, 2),
                portfolio_weight_pct=round(weight, 2),
            )
        )

    rows.sort(key=lambda x: x.total_value, reverse=True)

    semiconductor_value = round(
        sum(row.total_value for row in rows if row.symbol in semiconductor_symbols),
        2,
    )
    semiconductor_weight = (
        semiconductor_value / securities_value * 100.0
        if securities_value > 0
        else 0.0
    )

    return TrueExposureReport(
        securities_value=round(securities_value, 2),
        total_account_evaluation=total_account_evaluation,
        rows=rows,
        semiconductor_value=semiconductor_value,
        semiconductor_weight_pct_of_securities=round(semiconductor_weight, 2),
    )
