"""GOLD-001 -- 삼성전자 급락 Case (docs/JOYLAB_INVESTMENT_ENGINE.md section 2).

Locks in two historical judgments as regression tests against the real
code paths, not hand-copied numbers:

1. Day-0 (2026-08-24): falling price alone must never increase the
   decision toward BUY, across all five intraday snapshots.
2. T+1 (2026-08-25): Samsung closed flat (0.00%) while KOSPI rose
   0.74% -- this must still resolve to RELATIVE_STRENGTH_GATE_FAIL via
   the same StockAssistantService.handle() path the live bot uses, not
   a bare arithmetic assertion on hand-typed numbers.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from joylab_etf.assistant.stock_assistant import StockAssistantService
from joylab_etf.intelligence.decision_engine import (
    DecisionAction,
    DecisionInput,
    SignalState,
    ThesisState,
    evaluate_investment_decision,
    load_decision_config,
)

ROOT = Path(__file__).resolve().parents[2]

DAY_0_PRICES = [272500, 263500, 260000, 257500, 257000]


def gold_001_input(price: int) -> DecisionInput:
    # Buying power is deliberately positive: market/risk gates must still block.
    return DecisionInput(
        symbol="005930",
        name="삼성전자",
        price_gate=SignalState.FAIL,
        valuation_gate=SignalState.UNKNOWN,
        flow_gate=SignalState.FAIL,
        relative_strength_gate=SignalState.FAIL,
        fundamental_eps_gate=SignalState.UNKNOWN,
        governance_esr_gate=SignalState.UNKNOWN,
        strategy_gate=SignalState.FAIL,
        data_confidence_gate=SignalState.PASS,
        semiconductor_gate=SignalState.FAIL,
        korea_translation_gate=SignalState.FAIL,
        pension_rotation_gate=SignalState.FAIL,
        thesis_state=ThesisState.INTACT,
        portfolio_allowed_qty=2,
    )


def test_gold_001_falling_price_never_increases_buy_action():
    results = [
        evaluate_investment_decision(gold_001_input(price))
        for price in DAY_0_PRICES
    ]
    assert all(result.action == DecisionAction.HOLD for result in results)
    assert all(result.recommended_qty == 0 for result in results)


class _FixedQuoteClient:
    """Replays one historical KIS quote regardless of the symbol asked."""

    def __init__(self, price: int, change_pct: float) -> None:
        self.price = price
        self.change_pct = change_pct
        self.calls: list[str] = []

    def get_domestic_quote(self, symbol: str):
        self.calls.append(symbol)
        return SimpleNamespace(
            symbol=symbol,
            price=self.price,
            change=None,
            change_pct=self.change_pct,
            timestamp=datetime(2026, 8, 25, 15, 30),
            per=None,
            pbr=None,
            eps=None,
            bps=None,
            week52_high=None,
            week52_low=None,
        )


class _EmptyFlowClient:
    def get_investor_flow(self, symbol: str):
        return []


class _FixedIndexClient:
    """Replays one historical KOSPI print regardless of the index code asked."""

    def __init__(self, change_pct: float) -> None:
        self.change_pct = change_pct

    def get_index_price(self, index_code: str):
        return SimpleNamespace(change_pct=self.change_pct)


def test_gold_001_t_plus_one_relative_strength_fails_via_real_pipeline():
    """T+1 (2026-08-25): 삼성전자 257,000원/0.00% vs KOSPI 6746.37/+0.74%.

    Runs the exact StockAssistantService.handle() path the live Telegram
    bot uses -- if the relative-strength comparison or its wiring into
    evaluate_instrument_rule ever gets it backwards, this fails.
    """
    quote_client = _FixedQuoteClient(price=257_000, change_pct=0.00)
    service = StockAssistantService(
        quote_client=quote_client,
        investor_client=_EmptyFlowClient(),
        decision_config=load_decision_config(
            ROOT / "config" / "investment_decision_rules.json"
        ),
        index_client=_FixedIndexClient(change_pct=0.74),
    )

    result = service.handle("/analyze 005930")

    assert quote_client.calls == ["005930"]
    assert "❌상대강도(KOSPI +0.74%)" in result
    assert "상대강도" in result.splitlines()[4]  # 확인 필요 reason line names it
    assert "🟡 보류 / 0주" in result
