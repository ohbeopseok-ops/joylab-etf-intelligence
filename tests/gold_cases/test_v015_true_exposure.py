from types import SimpleNamespace

from joylab_etf.kis.etf_models import ETFComponentSnapshot, ETFConstituent
from joylab_etf.intelligence.true_exposure_v015 import build_true_exposure_report


def test_direct_plus_indirect():
    positions = [
        SimpleNamespace(
            symbol="005930",
            name="삼성전자",
            market_value=771000.0,
        ),
        SimpleNamespace(
            symbol="069500",
            name="KODEX 200",
            market_value=213590.0,
        ),
    ]

    snapshot = ETFComponentSnapshot(
        etf_symbol="069500",
        timestamp="2026-08-25T00:00:00+09:00",
        constituents=[
            ETFConstituent(
                symbol="005930",
                name="삼성전자",
                weight_pct=20.0,
            ),
            ETFConstituent(
                symbol="000660",
                name="SK하이닉스",
                weight_pct=10.0,
            ),
        ],
    )

    report = build_true_exposure_report(
        positions=positions,
        etf_snapshots={"069500": snapshot},
        semiconductor_symbols={"005930", "000660"},
        total_account_evaluation=1921547,
    )

    samsung = next(r for r in report.rows if r.symbol == "005930")
    hynix = next(r for r in report.rows if r.symbol == "000660")

    assert samsung.direct_value == 771000
    assert samsung.indirect_value == 42718
    assert samsung.total_value == 813718

    assert hynix.direct_value == 0
    assert hynix.indirect_value == 21359
    assert hynix.total_value == 21359

    assert report.securities_value == 984590
    assert report.semiconductor_value == 835077
