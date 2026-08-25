from __future__ import annotations

import re
import time
from datetime import date
from pathlib import Path
from typing import Any, Protocol

from joylab_etf.intelligence.decision_engine import (
    DecisionInput,
    InstrumentObservation,
    InstrumentWatchRule,
    InvestmentDecisionConfig,
    SignalState,
    ThesisState,
    evaluate_instrument_rule,
    evaluate_investment_decision,
)

SYMBOL_PATTERN = re.compile(r"^[0-9A-Z]{6}$")


class QuoteClient(Protocol):
    def get_domestic_quote(self, symbol: str) -> Any: ...


class InvestorFlowClient(Protocol):
    def get_investor_flow(self, symbol: str) -> list[Any]: ...


class StockAssistantService:
    """Conservative chat facade over verified KIS data and stored rules."""

    def __init__(
        self,
        quote_client: QuoteClient,
        investor_client: InvestorFlowClient,
        decision_config: InvestmentDecisionConfig,
        aliases: dict[str, str] | None = None,
        request_delay_sec: float = 0.0,
    ) -> None:
        self.quote_client = quote_client
        self.investor_client = investor_client
        self.decision_config = decision_config
        self.request_delay_sec = max(0.0, request_delay_sec)
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

        observation = InstrumentObservation(
            observed_on=date.today(),
            current_price=quote.price,
            # A current quote and one flow snapshot do not prove confirmation,
            # trend easing, relative strength, or an intact thesis.
            price_confirmation_pass=None,
            flow_confirmation_pass=None,
            foreign_selling_easing=None,
            institutional_selling_easing=None,
            pension_selling_easing=None,
            relative_strength_pass=None,
        )
        signals = evaluate_instrument_rule(rule, observation)
        decision = evaluate_investment_decision(
            DecisionInput(
                symbol=symbol,
                name=rule.name,
                price_gate=signals.price_gate,
                flow_gate=signals.flow_gate,
                relative_strength_gate=signals.relative_strength_gate,
                strategy_gate=SignalState.UNKNOWN,
                data_confidence_gate=signals.data_confidence_gate,
                thesis_state=ThesisState.UNKNOWN,
                portfolio_allowed_qty=0,
                portfolio_blocking_reasons=["PORTFOLIO_DATA_UNAVAILABLE"],
            )
        )
        return self._ruled_report(rule, quote, flow, signals, decision)

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
    ) -> str:
        notes = "; ".join(rule.notes) if rule.notes else "등록된 추가 조건 없음"
        blockers = ", ".join(decision.blocking_reasons[:8])
        return "\n".join(
            [
                f"{rule.name} ({rule.symbol})",
                self._quote_line(quote),
                self._flow_line(flow),
                f"판단: 🟡 {decision.action.value} / 추천수량 {decision.recommended_qty}주",
                (
                    "Gate: "
                    f"Price={signals.price_gate.value}, Flow={signals.flow_gate.value}, "
                    f"상대강도={signals.relative_strength_gate.value}, "
                    f"데이터={signals.data_confidence_gate.value}"
                ),
                f"차단 근거: {blockers}",
                f"변경 조건/규칙: {notes}",
                (
                    "미확인: 다일 수급 추세, 연기금, 상대강도, 기업가치·EPS, "
                    "지배구조, 투자논지, 실계좌 포트폴리오"
                ),
                f"규칙 유효기간: {rule.as_of_date}~{rule.valid_through}",
            ]
        )

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
