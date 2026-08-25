r"""JoyLab personal analyst — CLI skeleton (TASK: Investment Engine, phase 1).

Usage:
    .\.venv\Scripts\python.exe scripts\analyst.py <symbol>

What this does live, from real KIS data:
    - current price (quotations/inquire-price)
    - individual/foreign/institution net-buy today (quotations/inquire-investor)
    - matches config/investment_decision_rules.json watch_rules, checks staleness
    - computes Price / Flow(partial) / Data-Confidence gates via decision_engine

What this deliberately does NOT compute yet (printed as open questions instead
of guessed, per AGENTS.md "no guessing" rule):
    - Relative Strength vs KOSPI (not wired)
    - Governance / Effective Shareholder Return (needs current disclosure, not
      available from KIS market-data endpoints)
    - AI Power Gate rotation checklist (needs sector-wide judgment)
    - Thesis state (needs a human/LLM call, this is intentionally qualitative)
    - Portfolio Gate final allowed qty (needs KIS_ACCOUNT_NO/PRODUCT_CODE in
      .env, which are currently unset in this environment)

Pension-specific net-buy (연기금) is not available from any KIS retail
endpoint found in the official reference repo — only the user's own pension
*account* endpoints exist, not market-wide pension flow. That gate stays
UNKNOWN unless sourced elsewhere.
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from joylab_etf.config import Settings
from joylab_etf.kis.client import KISClient
from joylab_etf.kis.investor import KISInvestorAdapter
from joylab_etf.intelligence.decision_engine import (
    InstrumentObservation,
    InstrumentWatchRule,
    InvestmentDecisionConfig,
    evaluate_instrument_rule,
    load_decision_config,
)

DEFAULT_RULES_PATH = ROOT / "config" / "investment_decision_rules.json"


def find_watch_rule(
    config: InvestmentDecisionConfig, symbol: str
) -> InstrumentWatchRule | None:
    return next((rule for rule in config.watch_rules if rule.symbol == symbol), None)


def build_observation(
    price: int,
    flow_snapshots: list,
) -> InstrumentObservation:
    latest = flow_snapshots[0] if flow_snapshots else None

    # A single day's net-buy sign tells you today's direction, not whether a
    # multi-day selling trend is *easing* (that needs a trend comparison this
    # skeleton doesn't do yet). Using it as a same-day proxy is a deliberate
    # simplification, not a guess about historical trend -- do not read this
    # as a verified "easing" signal.
    foreign_easing = None if latest is None else latest.foreign_net_buy_qty >= 0
    institutional_easing = None if latest is None else latest.institution_net_buy_qty >= 0

    return InstrumentObservation(
        observed_on=date.today(),
        current_price=price,
        foreign_selling_easing=foreign_easing,
        institutional_selling_easing=institutional_easing,
        pension_selling_easing=None,  # no per-stock KIS endpoint exists
        relative_strength_pass=None,  # not wired yet
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="JoyLab personal analyst -- ticker in, gate status out",
    )
    parser.add_argument("symbol", help="6-digit KRX symbol, e.g. 005930")
    parser.add_argument("--rules", default=str(DEFAULT_RULES_PATH))
    args = parser.parse_args()

    settings = Settings.from_env()
    client = KISClient(settings)

    quote = client.get_domestic_quote(args.symbol)
    print(f"[QUOTE] {args.symbol} {quote.price:,}원 ({quote.change_pct}%)")

    time.sleep(0.3)  # avoid EGW00201 rate-limit back-to-back
    investor = KISInvestorAdapter(client)
    try:
        flow = investor.get_investor_flow(args.symbol)
    except Exception as exc:  # noqa: BLE001 -- surfaced to user, not swallowed
        print(f"[WARN] investor flow unavailable: {type(exc).__name__}: {exc}")
        flow = []

    if flow:
        latest = flow[0]
        print(
            f"[FLOW {latest.business_date}] "
            f"개인 {latest.individual_net_buy_qty:,} / "
            f"외국인 {latest.foreign_net_buy_qty:,} / "
            f"기관 {latest.institution_net_buy_qty:,}"
        )
    else:
        print("[FLOW] DATA_GAP -- KIS investor endpoint returned nothing usable")

    config = load_decision_config(args.rules)
    rule = find_watch_rule(config, args.symbol)

    if rule is None:
        print(
            f"[WATCH_RULE] {args.symbol}에 대한 저장된 전략 규칙이 없습니다. "
            "Price/Data Confidence Gate를 계산할 기준이 없습니다."
        )
        print(
            "[NEXT] 대화로 Governance/Thesis/AI Power 판단을 받은 뒤 "
            f"{args.rules}에 규칙을 추가하세요."
        )
        return

    observation = build_observation(quote.price, flow)
    signals = evaluate_instrument_rule(rule, observation)

    print(
        f"[GATES] price={signals.price_gate.value} "
        f"flow={signals.flow_gate.value} "
        f"relative_strength={signals.relative_strength_gate.value} "
        f"data_confidence={signals.data_confidence_gate.value}"
    )
    if signals.reasons:
        print(f"[REASONS] {', '.join(signals.reasons)}")
    if rule.notes:
        print(f"[NOTES] {'; '.join(rule.notes)}")

    print()
    print("=== 아직 코드로 계산 안 되는 항목 (대화로 채워야 최종 사자/보류/팔자 확정) ===")
    print("- Relative Strength: KOSPI 대비 상대강도")
    print("- Governance / Effective Shareholder Return")
    print("- AI Power Gate rotation checklist (해당 종목이면)")
    print("- Thesis state: INTACT / WEAKENING / BROKEN")
    print(
        "- Portfolio Gate 최종 허용수량: KIS_ACCOUNT_NO/PRODUCT_CODE가 .env에 "
        "비어 있어 실계좌 연동 불가 -- 계좌번호 입력 전까지는 수량 판단 없음"
    )


if __name__ == "__main__":
    main()
