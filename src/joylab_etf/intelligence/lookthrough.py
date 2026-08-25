from __future__ import annotations

from pydantic import BaseModel

from joylab_etf.kis.etf_models import ETFComponentSnapshot


class LookThroughExposure(BaseModel):
    symbol: str
    name: str
    weight_pct: float
    etf_market_value: float
    exposure_value: float


def calculate_target_exposures(
    snapshot: ETFComponentSnapshot,
    etf_market_value: float,
    target_symbols: list[str],
) -> list[LookThroughExposure]:
    results: list[LookThroughExposure] = []

    for symbol in target_symbols:
        item = snapshot.find(symbol)
        if item is None:
            continue

        results.append(
            LookThroughExposure(
                symbol=item.symbol,
                name=item.name,
                weight_pct=item.weight_pct,
                etf_market_value=etf_market_value,
                exposure_value=round(
                    etf_market_value * item.weight_pct / 100.0,
                    2,
                ),
            )
        )

    return results
