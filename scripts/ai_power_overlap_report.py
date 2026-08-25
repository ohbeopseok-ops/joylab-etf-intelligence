from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from joylab_etf.config import Settings
from joylab_etf.intelligence.overlap import (
    ETFPosition,
    build_cluster_exposure,
    build_common_holdings_report,
    build_concentration_summary,
    build_lookthrough_report,
    build_weighted_overlap_matrix,
    load_ai_power_universe,
    load_multi_etf_holdings,
)
from joylab_etf.kis.client_v0142 import KISClient
from joylab_etf.kis.etf_v015 import KISETFAdapter


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read-only AI Power ETF overlap and look-through report",
    )
    parser.add_argument(
        "--config",
        default=str(ROOT / "config" / "ai_power_universe.json"),
    )
    parser.add_argument(
        "--positions",
        required=True,
        help="Private JSON with positions[{etf_symbol, market_value}]",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Private output JSON path; do not commit account-derived reports",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    universe = load_ai_power_universe(args.config)
    position_data = json.loads(Path(args.positions).read_text(encoding="utf-8"))
    positions = [ETFPosition(**item) for item in position_data.get("positions", [])]
    if not positions:
        raise RuntimeError("positions must contain at least one explicit ETF market value")

    adapter = KISETFAdapter(KISClient(Settings.from_env()))
    loaded = load_multi_etf_holdings(adapter, universe.etfs)
    matrix = build_weighted_overlap_matrix(loaded)
    common = build_common_holdings_report(loaded, min_etf_count=2, top_n=20)
    core8 = build_lookthrough_report(loaded, positions, universe.core8)
    clusters = {
        name: build_cluster_exposure(name, symbols, loaded, positions)
        for name, symbols in universe.clusters.items()
    }
    concentration = build_concentration_summary(loaded, positions)

    payload = {
        "universe_verified_on": universe.verified_on,
        "load_status": {
            symbol: result.model_dump(mode="json") for symbol, result in loaded.items()
        },
        "weighted_overlap_matrix": matrix.model_dump(mode="json"),
        "common_holdings": common.model_dump(mode="json"),
        "core8_lookthrough": core8.model_dump(mode="json"),
        "clusters": {
            name: report.model_dump(mode="json") for name, report in clusters.items()
        },
        "concentration": concentration.model_dump(mode="json"),
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[PASS] read-only report written: {output}")


if __name__ == "__main__":
    main()
