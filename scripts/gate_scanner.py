r"""Scheduled gate-flip scanner for proactive Telegram alerts.

Runs the same live gate computations StockAssistantService.analyze() does
for every symbol in config/investment_decision_rules.json's watch_rules,
compares them against the previous scan's snapshot (state/gate_state.json),
and pushes a Telegram message only for symbols whose gate state actually
changed since the last run.

Deliberately does NOT touch the Portfolio Gate: analyze()'s
portfolio_allowed_qty<=0 always adds PORTFOLIO_GATE_BLOCK, and
strategy_gate is hardcoded UNKNOWN in analyze() itself -- together those
mean DecisionAction.BUY is currently unreachable, so a scanner watching
for "action flipped to BUY" would never fire. Watching individual gates
(PRICE/FLOW/RELATIVE_STRENGTH/DATA_CONFIDENCE/VALUATION/AI_POWER)
instead surfaces the same live signal analyze() would show, without
requiring KIS account credentials in this workflow's secrets.

Usage:
    python scripts/gate_scanner.py

Env vars required (see .github/workflows/gate_scan.yml):
    KIS_APP_KEY, KIS_APP_SECRET, KIS_ENV
    TELEGRAM_BOT_TOKEN, TELEGRAM_ALLOWED_CHAT_IDS
"""

from __future__ import annotations

import json
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from joylab_etf.assistant.telegram import TelegramBotClient, TelegramSettings
from joylab_etf.config import Settings
from joylab_etf.intelligence.decision_engine import (
    InstrumentObservation,
    InstrumentWatchRule,
    InvestmentDecisionConfig,
    ValuationInput,
    evaluate_ai_power_gate,
    evaluate_instrument_rule,
    evaluate_valuation_gate,
    load_decision_config,
)
from joylab_etf.kis.client import KISClient
from joylab_etf.kis.index import KISIndexAdapter
from joylab_etf.kis.investor import KISInvestorAdapter

RULES_PATH = ROOT / "config" / "investment_decision_rules.json"
STATE_PATH = ROOT / "state" / "gate_state.json"
REQUEST_DELAY_SEC = 0.5


def _relative_strength(
    quote: object, index_client: KISIndexAdapter
) -> tuple[bool | None, float | None]:
    change_pct = getattr(quote, "change_pct", None)
    if change_pct is None:
        return None, None
    time.sleep(REQUEST_DELAY_SEC)
    try:
        kospi = index_client.get_index_price("0001")
    except Exception:
        return None, None
    return change_pct > kospi.change_pct, kospi.change_pct


def scan_symbol(
    rule: InstrumentWatchRule,
    kis_client: KISClient,
    investor_client: KISInvestorAdapter,
    index_client: KISIndexAdapter,
    config: InvestmentDecisionConfig,
) -> dict[str, str]:
    quote = kis_client.get_domestic_quote(rule.symbol)
    time.sleep(REQUEST_DELAY_SEC)

    relative_strength_pass, _kospi_change_pct = _relative_strength(quote, index_client)

    observation = InstrumentObservation(
        observed_on=date.today(),
        current_price=quote.price,
        price_confirmation_pass=None,
        flow_confirmation_pass=None,
        foreign_selling_easing=None,
        institutional_selling_easing=None,
        pension_selling_easing=None,
        relative_strength_pass=relative_strength_pass,
    )
    signals = evaluate_instrument_rule(rule, observation)

    valuation_result = evaluate_valuation_gate(
        ValuationInput(
            per=quote.per,
            pbr=quote.pbr,
            eps=quote.eps,
            bps=quote.bps,
            week52_high=quote.week52_high,
            week52_low=quote.week52_low,
        ),
        config.valuation_policy,
    )

    snapshot = {
        "PRICE": signals.price_gate.value,
        "FLOW": signals.flow_gate.value,
        "RELATIVE_STRENGTH": signals.relative_strength_gate.value,
        "DATA_CONFIDENCE": signals.data_confidence_gate.value,
        "VALUATION": valuation_result.state.value,
    }

    if rule.ai_power_watch is not None:
        watch = rule.ai_power_watch
        if relative_strength_pass is not None:
            watch = watch.model_copy(update={"etf_outperforms_kospi": relative_strength_pass})
        ai_result = evaluate_ai_power_gate(watch, config.ai_power_policy)
        snapshot["AI_POWER"] = ai_result.state.value

    return snapshot


def diff_snapshot(
    name: str, symbol: str, previous: dict[str, str], current: dict[str, str]
) -> list[str]:
    lines = []
    for gate_name, new_value in current.items():
        old_value = previous.get(gate_name)
        if old_value is None or old_value == new_value:
            continue
        if new_value == "PASS":
            direction = "\U0001f7e2 개선"
        elif old_value == "PASS":
            direction = "\U0001f534 악화"
        else:
            direction = "\U0001f504 변경"
        lines.append(f"{direction} {name}({symbol}) {gate_name}: {old_value} -> {new_value}")
    return lines


def main() -> int:
    config = load_decision_config(RULES_PATH)
    kis_client = KISClient(Settings.from_env())
    investor_client = KISInvestorAdapter(kis_client)
    index_client = KISIndexAdapter(kis_client)

    is_first_run = not STATE_PATH.exists()
    previous_state: dict[str, dict[str, str]] = {}
    if not is_first_run:
        previous_state = json.loads(STATE_PATH.read_text(encoding="utf-8"))

    current_state: dict[str, dict[str, str]] = {}
    alerts: list[str] = []

    for rule in config.watch_rules:
        prev_snapshot = previous_state.get(rule.symbol, {})
        try:
            snapshot = scan_symbol(rule, kis_client, investor_client, index_client, config)
        except Exception as exc:
            print(f"[gate_scanner] {rule.symbol} 스캔 실패, 이전 상태 유지: {type(exc).__name__}: {exc}")
            current_state[rule.symbol] = prev_snapshot
            continue

        current_state[rule.symbol] = snapshot
        if not is_first_run:
            alerts.extend(diff_snapshot(rule.name, rule.symbol, prev_snapshot, snapshot))
        time.sleep(REQUEST_DELAY_SEC)

    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(
        json.dumps(current_state, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    if is_first_run:
        print("[gate_scanner] 첫 실행 -- 기준 상태만 저장, 알림 없음.")
        return 0

    if not alerts:
        print("[gate_scanner] 변경 없음.")
        return 0

    message = "\n".join(["게이트 변경 감지", *alerts])
    _safe_print(f"[gate_scanner] {len(alerts)}건 변경, Telegram 발송:\n{message}")

    telegram_settings = TelegramSettings.from_env()
    client = TelegramBotClient(telegram_settings)
    for chat_id in telegram_settings.allowed_chat_ids:
        client.send_message(chat_id, message)

    return 0


def _safe_print(text: str) -> None:
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode(sys.stdout.encoding or "utf-8", errors="replace").decode(sys.stdout.encoding or "utf-8", errors="replace"))


if __name__ == "__main__":
    raise SystemExit(main())
