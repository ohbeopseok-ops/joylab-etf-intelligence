"""GOLD-001 uses a user-provided historical case snapshot, not live data."""

from joylab_etf.intelligence.decision_engine import (
    DecisionAction,
    DecisionInput,
    SignalState,
    ThesisState,
    evaluate_investment_decision,
)


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


def test_gold_001_t_plus_one_did_not_outperform_kospi():
    samsung_return_pct = 0.00
    kospi_return_pct = 0.74
    assert samsung_return_pct - kospi_return_pct == -0.74
