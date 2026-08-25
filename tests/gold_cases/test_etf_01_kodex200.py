from datetime import datetime, timezone

from joylab_etf.kis.etf_models import ETFComponentSnapshot, ETFConstituent
from joylab_etf.intelligence.lookthrough import calculate_target_exposures


def fixture_snapshot() -> ETFComponentSnapshot:
    return ETFComponentSnapshot(
        etf_symbol="069500",
        timestamp=datetime.now(timezone.utc),
        constituents=[
            ETFConstituent(
                symbol="005930",
                name="삼성전자",
                weight_pct=24.5,
                current_price=257500,
                valuation_amount=1000000,
            ),
            ETFConstituent(
                symbol="000660",
                name="SK하이닉스",
                weight_pct=15.0,
                current_price=1686000,
                valuation_amount=700000,
            ),
            ETFConstituent(
                symbol="005380",
                name="현대차",
                weight_pct=3.0,
                current_price=300000,
                valuation_amount=100000,
            ),
        ],
    )


def test_etf_01_targets_exist():
    snapshot = fixture_snapshot()

    assert snapshot.find("005930") is not None
    assert snapshot.find("000660") is not None


def test_etf_01_weight_normalization():
    snapshot = fixture_snapshot()

    assert snapshot.find("005930").weight_pct == 24.5
    assert snapshot.find("000660").weight_pct == 15.0


def test_etf_01_lookthrough_math():
    snapshot = fixture_snapshot()

    rows = calculate_target_exposures(
        snapshot=snapshot,
        etf_market_value=1_000_000,
        target_symbols=["005930", "000660"],
    )

    samsung = next(x for x in rows if x.symbol == "005930")
    hynix = next(x for x in rows if x.symbol == "000660")

    assert samsung.exposure_value == 245_000
    assert hynix.exposure_value == 150_000


def test_etf_01_missing_symbol_is_safe():
    snapshot = fixture_snapshot()

    rows = calculate_target_exposures(
        snapshot=snapshot,
        etf_market_value=1_000_000,
        target_symbols=["999999"],
    )

    assert rows == []
