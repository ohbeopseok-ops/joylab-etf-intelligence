from datetime import datetime, timezone
from pathlib import Path

from joylab_etf.intelligence.overlap import (
    ETFDescriptor,
    ETFLoadResult,
    ETFPosition,
    LoadStatus,
    SecurityDescriptor,
    build_cluster_exposure,
    build_common_holdings_report,
    build_concentration_summary,
    build_lookthrough_report,
    build_weighted_overlap_matrix,
    load_multi_etf_holdings,
    load_ai_power_universe,
    normalize_snapshot,
)
from joylab_etf.kis.etf_models import ETFComponentSnapshot, ETFConstituent


NOW = datetime(2026, 8, 25, tzinfo=timezone.utc)


def descriptor(symbol: str, verified: bool = True) -> ETFDescriptor:
    return ETFDescriptor(
        symbol=symbol,
        name=f"ETF {symbol}",
        ticker_source_url="https://example.test/official",
        kis_constituents_verified=verified,
    )


def snapshot(symbol: str, holdings: list[tuple[str, str, float]]) -> ETFComponentSnapshot:
    return ETFComponentSnapshot(
        etf_symbol=symbol,
        timestamp=NOW,
        constituents=[
            ETFConstituent(symbol=code, name=name, weight_pct=weight)
            for code, name, weight in holdings
        ],
    )


def available(symbol: str, holdings: list[tuple[str, str, float]]) -> ETFLoadResult:
    return ETFLoadResult(
        descriptor=descriptor(symbol),
        status=LoadStatus.AVAILABLE,
        holdings=normalize_snapshot(snapshot(symbol, holdings), f"ETF {symbol}"),
    )


def test_identical_etfs_overlap_uses_sum_of_min_weights():
    results = {
        "A": available("A", [("X", "X", 60), ("Y", "Y", 40)]),
        "B": available("B", [("X", "X", 60), ("Y", "Y", 40)]),
    }
    matrix = build_weighted_overlap_matrix(results)
    assert matrix.cell("A", "B").overlap_pct == 100


def test_disjoint_etfs_overlap_is_zero():
    results = {
        "A": available("A", [("X", "X", 100)]),
        "B": available("B", [("Y", "Y", 100)]),
    }
    assert build_weighted_overlap_matrix(results).cell("A", "B").overlap_pct == 0


def test_partial_overlap_and_matrix_symmetry():
    results = {
        "A": available("A", [("X", "X", 60), ("Y", "Y", 30)]),
        "B": available("B", [("X", "X", 20), ("Z", "Z", 60)]),
    }
    matrix = build_weighted_overlap_matrix(results)
    assert matrix.cell("A", "B").overlap_pct == 20
    assert matrix.cell("B", "A").overlap_pct == 20
    assert matrix.cell("A", "B").coverage_a_pct == 90
    assert matrix.cell("A", "B").coverage_b_pct == 80
    assert matrix.cell("B", "A").coverage_a_pct == 80
    assert matrix.cell("B", "A").coverage_b_pct == 90


def test_missing_constituent_data_is_not_zero_overlap():
    results = {
        "A": available("A", [("X", "X", 100)]),
        "B": ETFLoadResult(
            descriptor=descriptor("B"),
            status=LoadStatus.UNAVAILABLE,
            error_message="source unavailable",
        ),
    }
    cell = build_weighted_overlap_matrix(results).cell("A", "B")
    assert cell.status == LoadStatus.UNAVAILABLE
    assert cell.overlap_pct is None


def test_incomplete_weight_sum_is_preserved_on_diagonal():
    results = {"A": available("A", [("X", "X", 50), ("Y", "Y", 30)])}
    cell = build_weighted_overlap_matrix(results).cell("A", "A")
    assert cell.coverage_a_pct == 80
    assert cell.overlap_pct == 80


def test_loader_marks_unverified_and_failed_sources_explicitly():
    class Adapter:
        def get_components(self, etf_symbol: str):
            raise RuntimeError("not available today")

    results = load_multi_etf_holdings(
        Adapter(),
        [descriptor("A", verified=False), descriptor("B")],
    )
    assert results["A"].status == LoadStatus.UNSUPPORTED
    assert results["B"].status == LoadStatus.UNAVAILABLE


def test_common_holdings_are_deterministic():
    results = {
        "A": available("A", [("X", "Shared", 30), ("Y", "Y", 70)]),
        "B": available("B", [("X", "Shared", 20), ("Z", "Z", 80)]),
    }
    report = build_common_holdings_report(results)
    assert [row.symbol for row in report.rows] == ["X"]
    assert report.rows[0].total_weight_pct == 50
    assert report.rows[0].weights_by_etf == {"A": 30, "B": 20}


def test_core8_cluster_and_concentration_share_normalized_holdings():
    results = {
        "A": available(
            "A",
            [("005930", "삼성전자", 20), ("010120", "LS ELECTRIC", 30), ("X", "X", 50)],
        ),
        "B": available(
            "B",
            [("005930", "삼성전자", 10), ("010120", "LS ELECTRIC", 40), ("Y", "Y", 50)],
        ),
    }
    positions = [ETFPosition(etf_symbol="A", market_value=1000), ETFPosition(etf_symbol="B", market_value=2000)]
    core = build_lookthrough_report(
        results,
        positions,
        [
            SecurityDescriptor(symbol="005930", name="삼성전자"),
            SecurityDescriptor(symbol="010120", name="LS ELECTRIC"),
        ],
    )
    assert core.rows[0].total_exposure == 400
    assert core.rows[1].total_exposure == 1100

    semiconductor = build_cluster_exposure(
        "semiconductor", ["005930"], results, positions
    )
    power = build_cluster_exposure(
        "power_equipment", ["010120"], results, positions
    )
    assert semiconductor.exposure_value == 400
    assert power.exposure_value == 1100

    concentration = build_concentration_summary(results, positions)
    assert concentration.disclosed_coverage_pct == 100
    assert concentration.top1_weight_pct == round(1100 / 3000 * 100, 6)


def test_duplicate_constituents_are_aggregated_without_renormalizing():
    normalized = normalize_snapshot(
        snapshot("A", [("X", "X", 25), ("X", "X", 15), ("Y", "Y", 30)]),
        "ETF A",
    )
    assert normalized.find("X").weight_pct == 40
    assert normalized.weight_sum == 70


def test_production_universe_contains_only_verified_task_001_etfs():
    root = Path(__file__).resolve().parents[2]
    universe = load_ai_power_universe(root / "config" / "ai_power_universe.json")
    assert [item.symbol for item in universe.etfs] == [
        "487240",
        "491820",
        "0117V0",
        "0101N0",
        "434730",
    ]
    assert all(item.kis_constituents_verified for item in universe.etfs)
    assert all(item.ticker_source_url.startswith("https://") for item in universe.etfs)
    assert len(universe.core8) == 8
