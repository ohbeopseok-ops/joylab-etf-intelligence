r"""JoyLab personal analyst — CLI skeleton (TASK: Investment Engine, phase 1).

Usage:
    .\.venv\Scripts\python.exe scripts\analyst.py <symbol>

What this does live, from real KIS data:
    - current price (quotations/inquire-price)
    - individual/foreign/institution net-buy today (quotations/inquire-investor)
    - matches config/investment_decision_rules.json watch_rules, checks staleness
    - computes Price / Flow(partial) / Data-Confidence gates via decision_engine

Portfolio Gate (added in phase 2) uses the real account balance via
KIS_ACCOUNT_NO/PRODUCT_CODE. It only computes a Cluster Gate for symbols
in the "semiconductor" cluster, because that is the only cluster with a
policy cap defined in config/portfolio_policy.json today. For any other
cluster (e.g. power_equipment) this script reports DATA_GAP instead of
inventing a cap -- CLAUDE.md §4 requires a backtest/rationale before any
concentration policy value is set, and none exists yet for those clusters.

What this deliberately does NOT compute yet (printed as open questions instead
of guessed, per AGENTS.md "no guessing" rule):
    - Relative Strength vs KOSPI (not wired)
    - Governance / Effective Shareholder Return (needs current disclosure, not
      available from KIS market-data endpoints)
    - AI Power Gate rotation checklist (needs sector-wide judgment)
    - Thesis state (needs a human/LLM call, this is intentionally qualitative)

Pension-specific net-buy (연기금) is not available from any KIS retail
endpoint found in the official reference repo — only the user's own pension
*account* endpoints exist, not market-wide pension flow. That gate stays
UNKNOWN unless sourced elsewhere.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from joylab_etf.config import Settings
from joylab_etf.config_v014 import Settings as AccountSettings
from joylab_etf.kis.client import KISClient
from joylab_etf.kis.client_v0142 import KISClient as AccountClient
from joylab_etf.kis.investor import KISInvestorAdapter
from joylab_etf.kis.account import KISAccountAdapter
from joylab_etf.kis.etf_v015 import KISETFAdapter
from joylab_etf.kis.buying_power import KISBuyingPowerAdapter
from joylab_etf.intelligence.decision_engine import (
    InstrumentObservation,
    InstrumentWatchRule,
    InvestmentDecisionConfig,
    evaluate_instrument_rule,
    load_decision_config,
)
from joylab_etf.intelligence.true_exposure_v015 import build_true_exposure_report
from joylab_etf.intelligence.portfolio_gate import evaluate_portfolio_gate
from joylab_etf.intelligence.portfolio_gate_models import GateInput, PortfolioGatePolicy

DEFAULT_RULES_PATH = ROOT / "config" / "investment_decision_rules.json"
INSTRUMENTS_PATH = ROOT / "config" / "instruments.json"
AI_POWER_UNIVERSE_PATH = ROOT / "config" / "ai_power_universe.json"
PORTFOLIO_POLICY_PATH = ROOT / "config" / "portfolio_policy.json"


def load_etf_and_cluster_membership() -> tuple[set[str], dict[str, str]]:
    """ETF symbol set + {member_symbol: cluster_name} from the two config files.

    Only "semiconductor" has a cap in portfolio_policy.json, so that's the
    only cluster_name this script will ever pass to evaluate_portfolio_gate.
    """
    instruments = json.loads(INSTRUMENTS_PATH.read_text(encoding="utf-8"))
    ai_power = json.loads(AI_POWER_UNIVERSE_PATH.read_text(encoding="utf-8"))

    etf_symbols = set(instruments.get("etfs", []))
    etf_symbols |= {etf["symbol"] for etf in ai_power.get("etfs", [])}

    cluster_membership: dict[str, str] = {}
    for cluster_name, symbols in instruments.get("clusters", {}).items():
        for symbol in symbols:
            cluster_membership[symbol] = cluster_name
    for cluster_name, symbols in ai_power.get("clusters", {}).items():
        for symbol in symbols:
            cluster_membership.setdefault(symbol, cluster_name)

    return etf_symbols, cluster_membership


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
    print("=== Portfolio Gate (실계좌) ===")
    try:
        account_settings = AccountSettings.from_env()
    except Exception as exc:
        print(f"[SKIP] account settings not configured: {type(exc).__name__}: {exc}")
        account_settings = None

    if account_settings is not None:
        account_client = AccountClient(account_settings)
        account = KISAccountAdapter(account_client, account_settings)
        etf_adapter = KISETFAdapter(account_client)
        buying_power = KISBuyingPowerAdapter(account_client, account_settings)

        etf_symbols, cluster_membership = load_etf_and_cluster_membership()
        policy = PortfolioGatePolicy(
            **json.loads(PORTFOLIO_POLICY_PATH.read_text(encoding="utf-8"))
        )

        positions, summary = account.get_balance()
        total_account_value = summary.total_evaluation

        etf_snapshots = {}
        for p in positions:
            if p.symbol in etf_symbols and p.quantity > 0:
                time.sleep(0.3)
                etf_snapshots[p.symbol] = etf_adapter.get_components(p.symbol)

        semiconductor_symbols = {
            symbol
            for symbol, cluster in cluster_membership.items()
            if cluster == "semiconductor"
        }
        exposure_report = build_true_exposure_report(
            positions=positions,
            etf_snapshots=etf_snapshots,
            semiconductor_symbols=semiconductor_symbols,
            total_account_evaluation=total_account_value,
        )

        target_row = next(
            (row for row in exposure_report.rows if row.symbol == args.symbol),
            None,
        )
        true_exposure_value = target_row.total_value if target_row else 0.0
        direct_value = target_row.direct_value if target_row else 0.0
        indirect_value = target_row.indirect_value if target_row else 0.0

        cluster_name = cluster_membership.get(args.symbol)
        if total_account_value is None:
            print("[SKIP] KIS 계좌 총평가금액(tot_evlu_amt)을 받지 못했습니다.")
        elif cluster_name != "semiconductor":
            reported_cluster = cluster_name or "(미분류)"
            print(
                f"[DATA_GAP] '{reported_cluster}' 클러스터는 portfolio_policy.json에 "
                "한도(%) 가 정의되어 있지 않습니다. 근거/백테스트 없이 캡을 임의로 "
                "만들지 않으므로 Cluster/Single-Stock Gate 계산을 생략합니다."
            )
        else:
            time.sleep(0.3)
            bp = buying_power.inquire(
                symbol=args.symbol,
                reference_price=quote.price,
            )
            gate_input = GateInput(
                symbol=args.symbol,
                name=target_row.name if target_row else args.symbol,
                current_price=quote.price,
                direct_value=direct_value,
                indirect_value=indirect_value,
                true_exposure_value=true_exposure_value,
                total_account_value=total_account_value,
                securities_value=exposure_report.securities_value,
                cluster_name=cluster_name,
                cluster_value=exposure_report.semiconductor_value,
                kis_buyable_qty=int(bp.no_credit_buy_qty or 0),
                kis_buyable_amount=bp.no_credit_buy_amount or 0.0,
            )
            gate_result = evaluate_portfolio_gate(gate_input, policy)

            print(
                f"[TRUE_EXPOSURE] direct={direct_value:,.0f} "
                f"indirect={indirect_value:,.0f} total={true_exposure_value:,.0f} "
                f"({gate_result.true_weight_before_pct}% of account)"
            )
            print(
                f"[CLUSTER] {cluster_name} "
                f"{exposure_report.semiconductor_value:,.0f} "
                f"({gate_result.cluster_weight_before_pct}% of account, "
                f"cap {policy.cluster_max_pct_of_total_account[cluster_name]}%)"
            )
            print(
                f"[FINAL_ALLOWED_QTY] {gate_result.final_allowed_qty}주 "
                f"({gate_result.buy_amount:,.0f}원) action={gate_result.action}"
            )
            if gate_result.blocking_reasons:
                print(f"[PORTFOLIO_BLOCKS] {', '.join(gate_result.blocking_reasons)}")

    print()
    print("=== 아직 코드로 계산 안 되는 항목 (대화로 채워야 최종 사자/보류/팔자 확정) ===")
    print("- Relative Strength: KOSPI 대비 상대강도")
    print("- Governance / Effective Shareholder Return")
    print("- AI Power Gate rotation checklist (해당 종목이면)")
    print("- Thesis state: INTACT / WEAKENING / BROKEN")


if __name__ == "__main__":
    main()
