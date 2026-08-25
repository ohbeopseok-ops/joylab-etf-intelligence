from __future__ import annotations

import re
import time
from datetime import date
from pathlib import Path
from typing import Any, Protocol

from joylab_etf.intelligence.decision_engine import (
    AIPowerGateResult,
    DecisionAction,
    DecisionInput,
    ExitTrigger,
    InstrumentObservation,
    InstrumentWatchRule,
    InvestmentDecisionConfig,
    SignalState,
    ThesisState,
    ValuationGateResult,
    ValuationInput,
    evaluate_ai_power_gate,
    evaluate_instrument_rule,
    evaluate_investment_decision,
    evaluate_valuation_gate,
)
from joylab_etf.intelligence.portfolio_state import PortfolioDataUnavailable, PortfolioStateProvider

SYMBOL_PATTERN = re.compile(r"^[0-9A-Z]{6}$")

CASH_PATTERN = re.compile(r"^현금\s*(얼마|있어)")
AFFORD_PATTERN = re.compile(r"^(.+?)\s*(\d+)\s*만\s*원?\s*추가매수\s*가능")
QUANTITY_PATTERN = re.compile(r"^(?:내\s*)?(.+?)\s*몇\s*주\s*(있어|보유)?")
AVG_PRICE_PATTERN = re.compile(r"^(?:내\s*)?(.+?)\s*평단은?\b")
WEIGHT_PATTERN = re.compile(r"^(?:내\s*)?(.+?)\s*(?:현재\s*)?비중은?\b")
ORDERABLE_PATTERN = re.compile(r"^(?:(.+?)\s*)?주문가능금액")

ACTION_EMOJI = {
    DecisionAction.BUY: "🟢",
    DecisionAction.HOLD: "🟡",
    DecisionAction.SELL: "🔴",
}

# Gates this codebase never actually computes for any ticker (always
# UNKNOWN, regardless of live data or config) -- listing them as
# "reasons" in a report is noise, not information. Kept in one place so
# the day one of them becomes real (a rule starts setting it), removing
# it here is a one-line change.
STRUCTURALLY_UNIMPLEMENTED_GATES = {
    "FUNDAMENTAL_EPS",
    "STRATEGY",
    "SEMICONDUCTOR",
    "KOREA_TRANSLATION",
    "PENSION_ROTATION",
}

REASON_LABELS: list[tuple[str, str]] = [
    ("PRICE_GATE", "가격"),
    ("FLOW_GATE", "수급"),
    ("RELATIVE_STRENGTH_GATE", "상대강도"),
    ("VALUATION_", "밸류에이션"),
    ("DATA_CONFIDENCE_GATE", "데이터 최신성"),
    ("STALE_STRATEGY_RULE", "데이터 최신성"),
    ("GOVERNANCE_ESR_GATE", "지배구조/주주환원"),
    ("AI_POWER_GATE", "AI Power 로테이션"),
    ("THESIS_", "투자논지"),
    ("PORTFOLIO_", "계좌 한도"),
]


def _short_reason_labels(blocking_reasons: list[str]) -> list[str]:
    labels: list[str] = []
    for reason in blocking_reasons:
        if any(reason.startswith(f"{gate}_GATE") for gate in STRUCTURALLY_UNIMPLEMENTED_GATES):
            continue
        for prefix, label in REASON_LABELS:
            if reason.startswith(prefix):
                if label not in labels:
                    labels.append(label)
                break
    return labels


GATE_EMOJI = {
    SignalState.PASS: "✅",
    SignalState.FAIL: "❌",
    SignalState.UNKNOWN: "❔",
    SignalState.NOT_APPLICABLE: "➖",
}

THESIS_EMOJI = {
    ThesisState.INTACT: "✅",
    ThesisState.WEAKENING: "⚠️",
    ThesisState.BROKEN: "❌",
    ThesisState.UNKNOWN: "➖",
}

EXIT_TRIGGER_LABELS = {
    ExitTrigger.THESIS_BROKEN: "투자논지 훼손",
    ExitTrigger.LEVERAGE_RISK: "레버리지 리스크",
    ExitTrigger.DAMAGE_EXPANDING: "손실 확대",
}


class QuoteClient(Protocol):
    def get_domestic_quote(self, symbol: str) -> Any: ...


class InvestorFlowClient(Protocol):
    def get_investor_flow(self, symbol: str) -> list[Any]: ...


class IndexClient(Protocol):
    def get_index_price(self, index_code: str) -> Any: ...


class StockAssistantService:
    """Conservative chat facade over verified KIS data and stored rules."""

    def __init__(
        self,
        quote_client: QuoteClient,
        investor_client: InvestorFlowClient,
        decision_config: InvestmentDecisionConfig,
        aliases: dict[str, str] | None = None,
        request_delay_sec: float = 0.0,
        index_client: IndexClient | None = None,
        portfolio_provider: PortfolioStateProvider | None = None,
    ) -> None:
        self.quote_client = quote_client
        self.investor_client = investor_client
        self.decision_config = decision_config
        self.request_delay_sec = max(0.0, request_delay_sec)
        self.index_client = index_client
        self.portfolio_provider = portfolio_provider
        self.rules = {rule.symbol: rule for rule in decision_config.watch_rules}
        self.aliases = {
            rule.name.strip().casefold(): rule.symbol
            for rule in decision_config.watch_rules
        }
        for name, symbol in (aliases or {}).items():
            self.aliases[name.strip().casefold()] = symbol

    def handle(self, text: str) -> str:
        raw = text.strip()
        if not raw or raw in {"/start", "/help"}:
            return self.help_text()

        if raw in {"/portfolio", "/계좌", "/포트폴리오", "내 계좌", "내 계좌 보여줘", "포트폴리오"}:
            return self.portfolio_summary()

        if CASH_PATTERN.match(raw):
            return self._cash_query()

        match = AFFORD_PATTERN.match(raw)
        if match:
            return self._afford_query(match.group(1), match.group(2))

        match = QUANTITY_PATTERN.match(raw)
        if match:
            return self._quantity_query(match.group(1))

        match = AVG_PRICE_PATTERN.match(raw)
        if match:
            return self._avg_price_query(match.group(1))

        match = WEIGHT_PATTERN.match(raw)
        if match:
            return self._weight_query(match.group(1))

        match = ORDERABLE_PATTERN.match(raw)
        if match:
            name_query = match.group(1)
            if not name_query:
                return "어느 종목 기준 주문가능금액인지 알려주세요 (예: 삼성전자 주문가능금액 얼마야?)."
            return self._orderable_query(name_query)

        parts = raw.split(maxsplit=1)
        command = parts[0].split("@", 1)[0].lower()
        if command in {"/analyze", "/decision", "/분석", "/판단"}:
            if len(parts) == 1:
                return "분석할 정확한 6자리 티커 또는 등록 종목명을 입력해 주세요."
            query = parts[1]
        elif command.startswith("/"):
            return self.help_text()
        else:
            query = raw

        symbol = self.resolve_symbol(query)
        if symbol is None:
            return (
                "티커를 추측하지 않습니다. 정확한 6자리 영문·숫자 티커 또는 "
                "등록된 종목명을 입력해 주세요."
            )
        return self.analyze(symbol)

    def resolve_symbol(self, query: str) -> str | None:
        value = query.strip()
        upper = value.upper()
        if SYMBOL_PATTERN.fullmatch(upper):
            return upper
        return self.aliases.get(value.casefold())

    def analyze(self, symbol: str) -> str:
        quote = self.quote_client.get_domestic_quote(symbol)
        if self.request_delay_sec:
            time.sleep(self.request_delay_sec)
        try:
            flow = self.investor_client.get_investor_flow(symbol)
        except Exception:
            flow = []

        rule = self.rules.get(symbol)
        if rule is None:
            return self._unruled_report(symbol, quote, flow)

        relative_strength_pass, kospi_change_pct = self._relative_strength(quote)

        observation = InstrumentObservation(
            observed_on=date.today(),
            current_price=quote.price,
            # A current quote and one flow snapshot do not prove confirmation
            # or trend easing -- those stay unknown. Relative strength is
            # computed live (today's change % vs KOSPI's) when an index
            # client is configured; otherwise it stays unknown too.
            price_confirmation_pass=None,
            flow_confirmation_pass=None,
            foreign_selling_easing=None,
            institutional_selling_easing=None,
            pension_selling_easing=None,
            relative_strength_pass=relative_strength_pass,
        )
        signals = evaluate_instrument_rule(rule, observation)
        gate_result, portfolio_fallback_reason = self._portfolio_gate(symbol, rule.name, quote.price)
        portfolio_allowed_qty = gate_result.final_allowed_qty if gate_result else 0
        portfolio_blocking_reasons = (
            gate_result.blocking_reasons if gate_result else [portfolio_fallback_reason]
        )

        ai_power_result: AIPowerGateResult | None = None
        if rule.ai_power_watch is not None:
            # etf_outperforms_kospi is live-computed the same way stock
            # relative strength is (today's change% vs KOSPI's) whenever an
            # index client is configured, overriding whatever stale value
            # sits in the stored watch file -- the 5-item rotation checklist
            # and revenue-translation fields stay as last hand-set, though.
            watch = rule.ai_power_watch
            if relative_strength_pass is not None:
                watch = watch.model_copy(update={"etf_outperforms_kospi": relative_strength_pass})
            ai_power_result = evaluate_ai_power_gate(watch, self.decision_config.ai_power_policy)
            ai_power_gate = ai_power_result.state
        else:
            ai_power_gate = rule.ai_power_gate

        valuation_result = evaluate_valuation_gate(
            ValuationInput(
                per=quote.per,
                pbr=quote.pbr,
                eps=quote.eps,
                bps=quote.bps,
                week52_high=quote.week52_high,
                week52_low=quote.week52_low,
            ),
            self.decision_config.valuation_policy,
        )

        decision = evaluate_investment_decision(
            DecisionInput(
                symbol=symbol,
                name=rule.name,
                price_gate=signals.price_gate,
                flow_gate=signals.flow_gate,
                relative_strength_gate=signals.relative_strength_gate,
                strategy_gate=SignalState.UNKNOWN,
                data_confidence_gate=signals.data_confidence_gate,
                valuation_gate=valuation_result.state,
                governance_esr_gate=rule.governance_esr_gate,
                ai_power_gate=ai_power_gate,
                thesis_state=rule.thesis_state,
                portfolio_allowed_qty=portfolio_allowed_qty,
                portfolio_blocking_reasons=portfolio_blocking_reasons,
            )
        )
        return self._ruled_report(
            rule, quote, flow, signals, decision, kospi_change_pct, gate_result, ai_power_result, valuation_result
        )

    def portfolio_summary(self) -> str:
        if self.portfolio_provider is None:
            return "실계좌 연동이 설정되지 않았습니다 (KIS_ACCOUNT_NO/PRODUCT_CODE 미설정)."
        try:
            report, _positions, summary = self.portfolio_provider.get_exposure_report()
        except PortfolioDataUnavailable as exc:
            return f"실계좌 연동이 설정되지 않았습니다: {exc}"
        except Exception as exc:
            return f"계좌 조회 중 오류가 발생했습니다: {type(exc).__name__}"

        if summary.total_evaluation is None:
            return "계좌 총평가금액을 KIS에서 받지 못했습니다 (UNKNOWN)."

        lines = [
            "내 계좌",
            f"총평가금액: {summary.total_evaluation:,.0f}원",
            (
                f"현금: {summary.cash:,.0f}원"
                if summary.cash is not None
                else "현금: UNKNOWN"
            ),
        ]
        top_rows = sorted(report.rows, key=lambda row: row.total_value, reverse=True)[:10]
        if not top_rows:
            lines.append("보유/노출 종목 없음")
        else:
            lines.append("보유/노출 상위 종목 (직접 + ETF 간접 합산):")
            for row in top_rows:
                lines.append(
                    f"  {row.name} ({row.symbol}): {row.total_value:,.0f}원 "
                    f"({row.portfolio_weight_pct}%, 직접 {row.direct_value:,.0f} + "
                    f"간접 {row.indirect_value:,.0f})"
                )
        lines.append(
            f"반도체 클러스터 노출: {report.semiconductor_value:,.0f}원 "
            f"({report.semiconductor_weight_pct_of_securities}% of 보유증권가치)"
        )
        return "\n".join(lines)

    def _exposure_report(self) -> tuple[Any, list[Any], Any] | str:
        """(report, positions, summary) or an error string to return directly."""
        if self.portfolio_provider is None:
            return "실계좌 연동이 설정되지 않았습니다 (KIS_ACCOUNT_NO/PRODUCT_CODE 미설정)."
        try:
            return self.portfolio_provider.get_exposure_report()
        except PortfolioDataUnavailable as exc:
            return f"실계좌 연동이 설정되지 않았습니다: {exc}"
        except Exception as exc:
            return f"계좌 조회 중 오류가 발생했습니다: {type(exc).__name__}"

    def _resolve_or_message(self, name_query: str) -> str:
        symbol = self.resolve_symbol(name_query)
        if symbol is None:
            return (
                "티커를 추측하지 않습니다. 정확한 6자리 영문·숫자 티커 또는 "
                "등록된 종목명을 입력해 주세요."
            )
        return symbol

    def _cash_query(self) -> str:
        result = self._exposure_report()
        if isinstance(result, str):
            return result
        _report, _positions, summary = result
        if summary.cash is None:
            return "현금 잔고를 KIS에서 받지 못했습니다 (UNKNOWN)."
        return f"현금: {summary.cash:,.0f}원"

    def _quantity_query(self, name_query: str) -> str:
        symbol = self._resolve_or_message(name_query)
        if not SYMBOL_PATTERN.fullmatch(symbol):
            return symbol  # was an error message
        result = self._exposure_report()
        if isinstance(result, str):
            return result
        _report, positions, _summary = result
        position = next((p for p in positions if p.symbol == symbol), None)
        if position is None:
            return f"{name_query} 직접 보유 수량: 0주 (미보유, ETF 내 간접 보유는 별도)"
        return f"{position.name} ({position.symbol}) 직접 보유수량: {position.quantity:,.0f}주"

    def _avg_price_query(self, name_query: str) -> str:
        symbol = self._resolve_or_message(name_query)
        if not SYMBOL_PATTERN.fullmatch(symbol):
            return symbol
        result = self._exposure_report()
        if isinstance(result, str):
            return result
        _report, positions, _summary = result
        position = next((p for p in positions if p.symbol == symbol), None)
        if position is None or position.avg_price is None:
            return f"{name_query} 직접 보유가 없어 평단이 없습니다 (또는 KIS 미제공/UNKNOWN)."
        return f"{position.name} ({position.symbol}) 평단: {position.avg_price:,.0f}원"

    def _weight_query(self, name_query: str) -> str:
        symbol = self._resolve_or_message(name_query)
        if not SYMBOL_PATTERN.fullmatch(symbol):
            return symbol
        result = self._exposure_report()
        if isinstance(result, str):
            return result
        report, _positions, summary = result
        row = next((r for r in report.rows if r.symbol == symbol), None)
        if row is None:
            return f"{name_query} 노출 없음 (직접+ETF 간접 합산 0)"
        if summary.total_evaluation:
            weight_of_total = row.total_value / summary.total_evaluation * 100
            return (
                f"{row.name} ({row.symbol}) 비중: 계좌 총평가금액 대비 {weight_of_total:.2f}%, "
                f"보유증권가치 대비 {row.portfolio_weight_pct}% "
                f"(직접 {row.direct_value:,.0f}원 + 간접 {row.indirect_value:,.0f}원)"
            )
        return f"{row.name} ({row.symbol}) 비중(보유증권가치 대비): {row.portfolio_weight_pct}%"

    def _orderable_query(self, name_query: str) -> str:
        symbol = self._resolve_or_message(name_query)
        if not SYMBOL_PATTERN.fullmatch(symbol):
            return symbol
        if self.portfolio_provider is None:
            return "실계좌 연동이 설정되지 않았습니다."
        try:
            quote = self.quote_client.get_domestic_quote(symbol)
            if self.request_delay_sec:
                time.sleep(self.request_delay_sec)
            bp = self.portfolio_provider.get_buying_power(symbol, quote.price)
        except PortfolioDataUnavailable as exc:
            return f"실계좌 연동이 설정되지 않았습니다: {exc}"
        except Exception as exc:
            return f"매수가능금액 조회 중 오류가 발생했습니다: {type(exc).__name__}"
        if bp.no_credit_buy_qty is None or bp.no_credit_buy_amount is None:
            return "매수가능금액을 KIS에서 받지 못했습니다 (UNKNOWN)."
        return (
            f"{symbol} 기준 미수 없는 매수가능금액: {bp.no_credit_buy_amount:,.0f}원 "
            f"({int(bp.no_credit_buy_qty):,}주, 기준가 {quote.price:,}원)"
        )

    def _afford_query(self, name_query: str, amount_10k_str: str) -> str:
        symbol = self._resolve_or_message(name_query)
        if not SYMBOL_PATTERN.fullmatch(symbol):
            return symbol
        amount = int(amount_10k_str) * 10_000
        try:
            quote = self.quote_client.get_domestic_quote(symbol)
        except Exception as exc:
            return f"시세 조회 중 오류가 발생했습니다: {type(exc).__name__}"
        if self.request_delay_sec:
            time.sleep(self.request_delay_sec)
        gate_result, fallback_reason = self._portfolio_gate(symbol, symbol, quote.price)
        if gate_result is None:
            return (
                f"{amount:,}원 추가매수 가능 여부를 판단할 수 없습니다 ({fallback_reason}). "
                "이 종목의 클러스터에는 portfolio_policy.json 한도가 없거나 계좌 데이터가 없습니다."
            )
        requested_qty = int(amount // quote.price) if quote.price > 0 else 0
        can_afford = requested_qty > 0 and requested_qty <= gate_result.final_allowed_qty
        return (
            f"{symbol} {amount:,}원 추가매수: {'가능' if can_afford else '불가'} "
            f"(요청 {requested_qty}주 필요, Portfolio Gate 허용 {gate_result.final_allowed_qty}주, "
            f"현재가 {quote.price:,}원)"
        )

    def _portfolio_gate(self, symbol: str, name: str, current_price: float) -> tuple[Any, str]:
        """(GateResult|None, fallback_reason). fallback_reason is only
        meaningful when the result is None -- never a guessed qty dressed
        up as a real gate."""
        if self.portfolio_provider is None:
            return None, "PORTFOLIO_DATA_UNAVAILABLE"
        try:
            gate_result = self.portfolio_provider.get_gate_result(symbol, name, current_price)
        except PortfolioDataUnavailable:
            return None, "PORTFOLIO_DATA_UNAVAILABLE"
        except Exception:
            return None, "PORTFOLIO_GATE_ERROR"
        if gate_result is None:
            return None, "PORTFOLIO_CLUSTER_POLICY_UNDEFINED"
        return gate_result, ""

    def _relative_strength(self, quote: Any) -> tuple[bool | None, float | None]:
        """(pass, kospi_change_pct). True if today's change % beats KOSPI's.

        This is a same-day excess-return comparison, not a multi-day RS
        line. Returns (None, None) if no index client is configured or the
        index fetch fails -- never guessed.
        """
        if self.index_client is None or quote.change_pct is None:
            return None, None
        if self.request_delay_sec:
            time.sleep(self.request_delay_sec)
        try:
            kospi = self.index_client.get_index_price("0001")
        except Exception:
            return None, None
        return quote.change_pct > kospi.change_pct, kospi.change_pct

    @staticmethod
    def help_text() -> str:
        return (
            "JoyLab 주식 비서 (조회·판단 전용)\n"
            "/analyze 005930 또는 삼성전자\n"
            "/decision 005930\n"
            "주문·자동매매는 지원하지 않습니다. 미확인 데이터는 PASS가 아니라 "
            "UNKNOWN이며, 부족하면 보류·0주로 답합니다."
        )

    def _unruled_report(self, symbol: str, quote: Any, flow: list[Any]) -> str:
        return "\n".join(
            [
                f"{symbol} 분석",
                self._quote_line(quote),
                self._flow_line(flow),
                "판단: 🟡 보류 / 추천수량 0주",
                "근거: 저장된 전략 규칙·기업가치·상대강도·논지·포트폴리오 데이터가 없습니다.",
                "다음 조건: 검증된 종목명/규칙과 필수 Gate 데이터가 등록되어야 합니다.",
                "주의: 시세 조회 결과만으로 매수 신호를 만들지 않습니다.",
            ]
        )

    def _ruled_report(
        self,
        rule: InstrumentWatchRule,
        quote: Any,
        flow: list[Any],
        signals: Any,
        decision: Any,
        kospi_change_pct: float | None,
        gate_result: Any = None,
        ai_power_result: AIPowerGateResult | None = None,
        valuation_result: ValuationGateResult | None = None,
    ) -> str:
        lines = [
            f"{rule.name} ({rule.symbol})",
            self._quote_line(quote),
            self._flow_line(flow),
            f"{ACTION_EMOJI[decision.action]} {decision.action.value} / {decision.recommended_qty}주",
            self._reason_line(decision),
            self._checklist_line(
                rule, quote, signals, kospi_change_pct, gate_result, ai_power_result, valuation_result
            ),
        ]
        if ai_power_result is not None and ai_power_result.unknown_rotation_checks:
            lines.append(
                f"AI Power 미확인 체크리스트: {', '.join(ai_power_result.unknown_rotation_checks)}"
            )
        if gate_result is not None:
            lines.append(
                f"실계좌 노출: {gate_result.true_weight_before_pct}% "
                f"(클러스터 {gate_result.cluster_weight_before_pct}%)"
            )
        return "\n".join(lines)

    @staticmethod
    def _reason_line(decision: Any) -> str:
        if decision.action == DecisionAction.BUY:
            return "매수 조건 충족"
        if decision.action == DecisionAction.SELL:
            labels = [EXIT_TRIGGER_LABELS.get(r, r.value) for r in decision.exit_reasons]
            return "청산 신호: " + ("·".join(labels) if labels else "사유 미상")
        labels = _short_reason_labels(decision.blocking_reasons)
        if not labels:
            return "판단 보류"
        return "확인 필요: " + "·".join(labels[:4])

    @staticmethod
    def _price_detail(rule: InstrumentWatchRule, quote: Any) -> str:
        if rule.price is None:
            return ""
        if rule.price.recovery_min is not None:
            arrow = "↑" if quote.price >= rule.price.recovery_min else "↓"
            return f"(회복선 {rule.price.recovery_min:,.0f}원{arrow})"
        if rule.price.buy_zone_min is not None and rule.price.buy_zone_max is not None:
            return f"(매수구간 {rule.price.buy_zone_min:,.0f}~{rule.price.buy_zone_max:,.0f})"
        if rule.price.no_chase_above is not None:
            return f"(상한 {rule.price.no_chase_above:,.0f})"
        return ""

    @staticmethod
    def _valuation_detail(valuation_result: ValuationGateResult) -> str:
        percentiles = [
            p
            for p in (valuation_result.per_percentile, valuation_result.pbr_percentile)
            if p is not None
        ]
        if not percentiles:
            return ""
        avg = sum(percentiles) / len(percentiles)
        return f"(52주밴드 {avg * 100:.0f}%)"

    def _checklist_line(
        self,
        rule: InstrumentWatchRule,
        quote: Any,
        signals: Any,
        kospi_change_pct: float | None,
        gate_result: Any,
        ai_power_result: AIPowerGateResult | None,
        valuation_result: ValuationGateResult | None = None,
    ) -> str:
        rs_detail = f"(KOSPI {kospi_change_pct:+.2f}%)" if kospi_change_pct is not None else ""
        entries = [
            f"{GATE_EMOJI[signals.relative_strength_gate]}상대강도{rs_detail}",
            f"{GATE_EMOJI[signals.price_gate]}가격{self._price_detail(rule, quote)}",
            f"{GATE_EMOJI[signals.flow_gate]}수급",
        ]
        if valuation_result is not None:
            entries.append(
                f"{GATE_EMOJI[valuation_result.state]}밸류{self._valuation_detail(valuation_result)}"
            )
        if rule.governance_esr_gate != SignalState.NOT_APPLICABLE:
            entries.append(f"{GATE_EMOJI[rule.governance_esr_gate]}지배구조")
        if ai_power_result is not None:
            entries.append(f"{GATE_EMOJI[ai_power_result.state]}AI Power")
        elif rule.ai_power_gate != SignalState.NOT_APPLICABLE:
            entries.append(f"{GATE_EMOJI[rule.ai_power_gate]}AI Power")
        entries.append(f"{THESIS_EMOJI[rule.thesis_state]}논지")
        if gate_result is not None:
            portfolio_emoji = "✅" if gate_result.final_allowed_qty > 0 else "❌"
            entries.append(f"{portfolio_emoji}계좌한도")
        else:
            entries.append("➖계좌한도")
        return "  ".join(entries)

    @staticmethod
    def _quote_line(quote: Any) -> str:
        change = "미확인" if quote.change_pct is None else f"{quote.change_pct:+.2f}%"
        stamp = getattr(quote, "timestamp", None)
        return f"확인 시세: {quote.price:,}원 / 등락률 {change} / 기준 {stamp}"

    @staticmethod
    def _flow_line(flow: list[Any]) -> str:
        if not flow:
            return "수급: DATA_GAP"
        latest = flow[0]
        return (
            f"당일 수급({latest.business_date}): "
            f"개인 {latest.individual_net_buy_qty:,}, "
            f"외국인 {latest.foreign_net_buy_qty:,}, "
            f"기관 {latest.institution_net_buy_qty:,}"
        )
