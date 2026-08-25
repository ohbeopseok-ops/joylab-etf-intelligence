from datetime import date
from pathlib import Path

import pytest

from joylab_etf.intelligence.decision_engine import (
    AIPowerPolicy,
    AIPowerScoreInput,
    AIPowerScorePolicy,
    AIPowerWatchInput,
    DecisionAction,
    DecisionInput,
    EffectiveShareholderReturnInput,
    EvidenceItem,
    EvidenceStatus,
    ExitTrigger,
    InstrumentObservation,
    OpportunityPolicy,
    OpportunityScoreInput,
    RotationLevel,
    SignalState,
    ThesisState,
    calculate_ai_power_score,
    calculate_effective_shareholder_return,
    calculate_opportunity_score,
    evaluate_ai_power_gate,
    evaluate_data_confidence,
    evaluate_instrument_rule,
    evaluate_investment_decision,
    evaluate_rule_based_decision,
    evaluate_valuation_gate,
    load_decision_config,
    ValuationInput,
    ValuationPolicy,
)


def decision_input(**overrides) -> DecisionInput:
    data = {
        "symbol": "005930",
        "name": "삼성전자",
        "price_gate": SignalState.PASS,
        "flow_gate": SignalState.PASS,
        "relative_strength_gate": SignalState.PASS,
        "strategy_gate": SignalState.PASS,
        "data_confidence_gate": SignalState.PASS,
        "thesis_state": ThesisState.INTACT,
        "valuation_gate": SignalState.PASS,
        "fundamental_eps_gate": SignalState.PASS,
        "governance_esr_gate": SignalState.PASS,
        "semiconductor_gate": SignalState.PASS,
        "ai_power_gate": SignalState.PASS,
        "korea_translation_gate": SignalState.PASS,
        "pension_rotation_gate": SignalState.PASS,
        "portfolio_allowed_qty": 2,
    }
    data.update(overrides)
    return DecisionInput(**data)


def full_ai_power_watch(**overrides) -> AIPowerWatchInput:
    data = {
        "ls_electric_relative_strength": True,
        "peer_strength_confirmed": True,
        "sector_breadth_confirmed": True,
        "institutional_rotation_confirmed": True,
        "semiconductor_weak_power_strong": True,
        "etf_outperforms_kospi": True,
        "order_backlog": SignalState.PASS,
        "revenue_recognition": SignalState.PASS,
        "operating_margin": SignalState.PASS,
        "eps_revision": SignalState.PASS,
    }
    data.update(overrides)
    return AIPowerWatchInput(**data)


def load_rules():
    root = Path(__file__).resolve().parents[2]
    return load_decision_config(root / "config" / "investment_decision_rules.json")


def find_rule(symbol: str):
    return next(rule for rule in load_rules().watch_rules if rule.symbol == symbol)


def test_buy_requires_every_gate_and_positive_portfolio_quantity():
    result = evaluate_investment_decision(decision_input())
    assert result.action == DecisionAction.BUY
    assert result.recommended_qty == 2


def test_falling_price_is_not_a_buy_signal():
    result = evaluate_investment_decision(
        decision_input(price_gate=SignalState.FAIL)
    )
    assert result.action == DecisionAction.HOLD
    assert result.recommended_qty == 0
    assert "PRICE_GATE_FAIL" in result.blocking_reasons


def test_unknown_flow_or_data_forces_hold():
    result = evaluate_investment_decision(
        decision_input(
            flow_gate=SignalState.UNKNOWN,
            data_confidence_gate=SignalState.UNKNOWN,
        )
    )
    assert result.action == DecisionAction.HOLD
    assert "FLOW_GATE_UNKNOWN" in result.blocking_reasons
    assert "DATA_CONFIDENCE_GATE_UNKNOWN" in result.blocking_reasons


def test_unknown_fundamental_or_governance_cannot_buy():
    result = evaluate_investment_decision(
        decision_input(
            fundamental_eps_gate=SignalState.UNKNOWN,
            governance_esr_gate=SignalState.UNKNOWN,
        )
    )
    assert result.action == DecisionAction.HOLD
    assert "FUNDAMENTAL_EPS_GATE_UNKNOWN" in result.blocking_reasons
    assert "GOVERNANCE_ESR_GATE_UNKNOWN" in result.blocking_reasons


def test_not_applicable_gate_does_not_block():
    result = evaluate_investment_decision(
        decision_input(ai_power_gate=SignalState.NOT_APPLICABLE)
    )
    assert result.action == DecisionAction.BUY
    assert "AI_POWER" in result.not_applicable_gates


def test_omitted_extended_gates_default_to_unknown_and_block():
    result = evaluate_investment_decision(
        DecisionInput(
            symbol="TEST",
            name="테스트",
            price_gate=SignalState.PASS,
            flow_gate=SignalState.PASS,
            relative_strength_gate=SignalState.PASS,
            strategy_gate=SignalState.PASS,
            data_confidence_gate=SignalState.PASS,
            thesis_state=ThesisState.INTACT,
            portfolio_allowed_qty=1,
        )
    )
    assert result.action == DecisionAction.HOLD
    assert "VALUATION_GATE_UNKNOWN" in result.blocking_reasons
    assert "GOVERNANCE_ESR_GATE_UNKNOWN" in result.blocking_reasons


def test_portfolio_concentration_blocks_but_does_not_sell():
    result = evaluate_investment_decision(
        decision_input(
            portfolio_allowed_qty=0,
            portfolio_blocking_reasons=["SINGLE_STOCK_MAX_BLOCK"],
        )
    )
    assert result.action == DecisionAction.HOLD
    assert result.recommended_qty == 0
    assert result.exit_reasons == []


def test_broken_thesis_is_explicit_sell_signal():
    result = evaluate_investment_decision(
        decision_input(thesis_state=ThesisState.BROKEN)
    )
    assert result.action == DecisionAction.SELL
    assert result.recommended_qty == 0
    assert result.exit_reasons == [ExitTrigger.THESIS_BROKEN]


def test_leverage_risk_is_explicit_sell_signal():
    result = evaluate_investment_decision(
        decision_input(exit_triggers=[ExitTrigger.LEVERAGE_RISK])
    )
    assert result.action == DecisionAction.SELL
    assert result.exit_reasons == [ExitTrigger.LEVERAGE_RISK]


@pytest.mark.parametrize(
    ("score", "level"),
    [
        (0, RotationLevel.WEAK),
        (1, RotationLevel.WEAK),
        (2, RotationLevel.WATCH),
        (3, RotationLevel.POSSIBLE),
        (4, RotationLevel.STRONG),
        (5, RotationLevel.CONFIRMED),
    ],
)
def test_ai_power_rotation_levels(score, level):
    values = [True] * score + [False] * (5 - score)
    watch = full_ai_power_watch(
        ls_electric_relative_strength=values[0],
        peer_strength_confirmed=values[1],
        sector_breadth_confirmed=values[2],
        institutional_rotation_confirmed=values[3],
        semiconductor_weak_power_strong=values[4],
    )
    assert evaluate_ai_power_gate(watch, AIPowerPolicy()).rotation_level == level


def test_power_news_or_rotation_alone_cannot_pass_revenue_translation():
    result = evaluate_ai_power_gate(
        full_ai_power_watch(
            order_backlog=SignalState.UNKNOWN,
            revenue_recognition=SignalState.UNKNOWN,
            operating_margin=SignalState.UNKNOWN,
            eps_revision=SignalState.UNKNOWN,
        ),
        AIPowerPolicy(),
    )
    assert result.rotation_level == RotationLevel.CONFIRMED
    assert result.state == SignalState.UNKNOWN
    assert "REVENUE_TRANSLATION_UNKNOWN" in result.blocking_reasons


def test_ai_power_requires_etf_relative_strength():
    result = evaluate_ai_power_gate(
        full_ai_power_watch(etf_outperforms_kospi=False),
        AIPowerPolicy(),
    )
    assert result.state == SignalState.FAIL
    assert "ETF_RELATIVE_STRENGTH_BLOCK" in result.blocking_reasons


def test_ai_power_passes_only_with_rotation_and_revenue_translation():
    result = evaluate_ai_power_gate(full_ai_power_watch(), AIPowerPolicy())
    assert result.state == SignalState.PASS
    assert result.rotation_score == 5
    assert result.revenue_translation_state == SignalState.PASS


def test_data_confidence_requires_confirmed_evidence():
    result = evaluate_data_confidence(
        evidence=[
            EvidenceItem(key="price", status=EvidenceStatus.CONFIRMED),
            EvidenceItem(key="flow", status=EvidenceStatus.ESTIMATED),
        ],
        required_keys=["price", "flow", "eps"],
    )
    assert result.state == SignalState.FAIL
    assert result.confirmed == ["price"]
    assert result.estimated == ["flow"]
    assert result.unverified_or_missing == ["eps"]


def test_estimated_evidence_is_unknown_not_pass():
    result = evaluate_data_confidence(
        evidence=[EvidenceItem(key="eps", status=EvidenceStatus.ESTIMATED)],
        required_keys=["eps"],
    )
    assert result.state == SignalState.UNKNOWN


def test_effective_shareholder_return_requires_complete_same_unit_inputs():
    incomplete = calculate_effective_shareholder_return(
        EffectiveShareholderReturnInput(
            unit="score",
            cash_dividend=10,
            genuine_cancellation=5,
        )
    )
    assert incomplete.state == SignalState.UNKNOWN
    assert incomplete.effective_shareholder_return is None

    complete = calculate_effective_shareholder_return(
        EffectiveShareholderReturnInput(
            unit="score",
            cash_dividend=10,
            genuine_cancellation=5,
            net_buyback=4,
            employee_equity_compensation=3,
            governance_constraint_discount=2,
        )
    )
    assert complete.state == SignalState.PASS
    assert complete.effective_shareholder_return == 14
    assert complete.accounting_formula is False


def test_opportunity_score_ranks_but_never_auto_buys():
    result = calculate_opportunity_score(
        OpportunityScoreInput(base_score=79, pension_flow_adjustment=5),
        OpportunityPolicy(),
    )
    assert result.adjusted_score == 84
    assert result.ranking_candidate is True
    assert result.automatic_buy is False


def test_pension_adjustment_is_limited_to_five_points():
    with pytest.raises(ValueError, match="pension_flow_adjustment"):
        calculate_opportunity_score(
            OpportunityScoreInput(base_score=80, pension_flow_adjustment=6),
            OpportunityPolicy(),
        )


def maximum_ai_power_score(**overrides) -> AIPowerScoreInput:
    data = {
        "hyperscaler_capex": 25,
        "gpu_hbm_demand": 25,
        "electricity_grid_constraint": 20,
        "data_center_energization": 15,
        "cooling_power_equipment": 15,
        "order_backlog_growth": SignalState.PASS,
        "operating_margin_improvement": SignalState.PASS,
        "valuation_not_overheated": SignalState.PASS,
        "ai_data_center_revenue_share_clear": SignalState.PASS,
    }
    data.update(overrides)
    return AIPowerScoreInput(**data)


def test_ai_power_score_caps_without_backlog_or_margin_confirmation():
    backlog = calculate_ai_power_score(
        maximum_ai_power_score(order_backlog_growth=SignalState.UNKNOWN),
        AIPowerScorePolicy(),
    )
    assert backlog.raw_score == 100
    assert backlog.capped_score == 79
    assert "ORDER_BACKLOG_80_CAP" in backlog.caps_applied

    margin = calculate_ai_power_score(
        maximum_ai_power_score(operating_margin_improvement=SignalState.FAIL),
        AIPowerScorePolicy(),
    )
    assert margin.capped_score == 84
    assert "OPERATING_MARGIN_85_CAP" in margin.caps_applied


def test_ai_power_score_never_auto_buys_and_can_be_capped_at_hold():
    result = calculate_ai_power_score(
        maximum_ai_power_score(
            valuation_not_overheated=SignalState.FAIL,
            ai_data_center_revenue_share_clear=SignalState.UNKNOWN,
        ),
        AIPowerScorePolicy(),
    )
    assert result.raw_score == 100
    assert result.maximum_action == DecisionAction.HOLD
    assert result.automatic_buy is False
    assert "VALUATION_AUTO_PROMOTION_BLOCK" in result.caps_applied
    assert "AI_REVENUE_SHARE_HOLD_CEILING" in result.caps_applied


def test_samsung_rule_requires_260k_and_all_flow_easing():
    rule = find_rule("005930")
    below = evaluate_instrument_rule(
        rule,
        InstrumentObservation(
            observed_on=date(2026, 8, 25),
            current_price=259000,
            price_confirmation_pass=True,
            flow_confirmation_pass=True,
            foreign_selling_easing=True,
            institutional_selling_easing=True,
            pension_selling_easing=True,
            relative_strength_pass=True,
        ),
    )
    assert below.price_gate == SignalState.FAIL

    confirmed = evaluate_instrument_rule(
        rule,
        InstrumentObservation(
            observed_on=date(2026, 8, 25),
            current_price=260000,
            price_confirmation_pass=True,
            flow_confirmation_pass=True,
            foreign_selling_easing=True,
            institutional_selling_easing=True,
            pension_selling_easing=True,
            relative_strength_pass=True,
        ),
    )
    assert confirmed.price_gate == SignalState.PASS
    assert confirmed.flow_gate == SignalState.PASS


def test_rule_observation_and_portfolio_gate_form_one_decision_pipeline():
    rule = find_rule("005930")
    observation = InstrumentObservation(
        observed_on=date(2026, 8, 25),
        current_price=260000,
        price_confirmation_pass=True,
        flow_confirmation_pass=True,
        foreign_selling_easing=True,
        institutional_selling_easing=True,
        pension_selling_easing=True,
        relative_strength_pass=True,
    )
    result = evaluate_rule_based_decision(
        rule=rule,
        observation=observation,
        strategy_gate=SignalState.PASS,
        thesis_state=ThesisState.INTACT,
        portfolio_allowed_qty=1,
        valuation_gate=SignalState.PASS,
        fundamental_eps_gate=SignalState.PASS,
        governance_esr_gate=SignalState.PASS,
        semiconductor_gate=SignalState.PASS,
        ai_power_gate=SignalState.NOT_APPLICABLE,
        korea_translation_gate=SignalState.PASS,
        pension_rotation_gate=SignalState.PASS,
    )
    assert result.action == DecisionAction.BUY
    assert result.recommended_qty == 1


def test_hyundai_rule_rejects_chasing_and_accepts_buy_zone():
    rule = find_rule("005380")
    chasing = evaluate_instrument_rule(
        rule,
        InstrumentObservation(
            observed_on=date(2026, 8, 25),
            current_price=421000,
            price_confirmation_pass=True,
            flow_confirmation_pass=True,
            relative_strength_pass=True,
        ),
    )
    assert chasing.price_gate == SignalState.FAIL

    buy_zone = evaluate_instrument_rule(
        rule,
        InstrumentObservation(
            observed_on=date(2026, 8, 25),
            current_price=410000,
            price_confirmation_pass=True,
            flow_confirmation_pass=True,
            relative_strength_pass=True,
        ),
    )
    assert buy_zone.price_gate == SignalState.PASS


def test_naver_rule_requires_three_day_pension_streak():
    rule = find_rule("035420")
    two_days = evaluate_instrument_rule(
        rule,
        InstrumentObservation(
            observed_on=date(2026, 8, 25),
            current_price=100000,
            price_confirmation_pass=True,
            flow_confirmation_pass=True,
            pension_net_buy_streak_days=2,
            relative_strength_pass=True,
        ),
    )
    assert two_days.flow_gate == SignalState.FAIL


def test_expired_strategy_snapshot_forces_data_confidence_fail():
    rule = find_rule("005930")
    result = evaluate_instrument_rule(
        rule,
        InstrumentObservation(
            observed_on=date(2026, 8, 27),
            current_price=260000,
            price_confirmation_pass=True,
            flow_confirmation_pass=True,
            foreign_selling_easing=True,
            institutional_selling_easing=True,
            pension_selling_easing=True,
            relative_strength_pass=True,
        ),
    )
    assert result.data_confidence_gate == SignalState.FAIL
    assert "STALE_STRATEGY_RULE" in result.reasons


def test_ai_power_etf_rule_requires_32500_recovery():
    rule = find_rule("487240")
    below = evaluate_instrument_rule(
        rule,
        InstrumentObservation(
            observed_on=date(2026, 8, 25),
            current_price=32450,
            price_confirmation_pass=True,
            flow_confirmation_pass=True,
            relative_strength_pass=True,
        ),
    )
    assert below.price_gate == SignalState.FAIL

    recovered = evaluate_instrument_rule(
        rule,
        InstrumentObservation(
            observed_on=date(2026, 8, 25),
            current_price=32500,
            price_confirmation_pass=True,
            flow_confirmation_pass=True,
            relative_strength_pass=True,
        ),
    )
    assert recovered.price_gate == SignalState.PASS


def test_valuation_gate_passes_when_per_and_pbr_near_52week_low():
    result = evaluate_valuation_gate(
        ValuationInput(
            per=11, pbr=2.2, eps=1000, bps=5000, week52_low=10000, week52_high=20000
        ),
        ValuationPolicy(),
    )
    assert result.state == SignalState.PASS
    assert result.per_percentile == pytest.approx(0.1)
    assert result.pbr_percentile == pytest.approx(0.1)
    assert result.blocking_reasons == []


def test_valuation_gate_fails_when_per_and_pbr_near_52week_high():
    result = evaluate_valuation_gate(
        ValuationInput(
            per=19, pbr=3.8, eps=1000, bps=5000, week52_low=10000, week52_high=20000
        ),
        ValuationPolicy(),
    )
    assert result.state == SignalState.FAIL
    assert result.blocking_reasons == ["VALUATION_RICH_VS_52W_RANGE"]


def test_valuation_gate_unknown_in_the_middle_of_the_band():
    result = evaluate_valuation_gate(
        ValuationInput(
            per=15, pbr=3.0, eps=1000, bps=5000, week52_low=10000, week52_high=20000
        ),
        ValuationPolicy(),
    )
    assert result.state == SignalState.UNKNOWN
    assert result.blocking_reasons == ["VALUATION_MID_RANGE"]


def test_valuation_gate_unknown_never_guessed_when_data_missing():
    result = evaluate_valuation_gate(ValuationInput(), ValuationPolicy())
    assert result.state == SignalState.UNKNOWN
    assert result.per_percentile is None
    assert result.pbr_percentile is None
    assert result.blocking_reasons == ["VALUATION_DATA_UNAVAILABLE"]


def test_valuation_gate_degenerate_band_treated_as_missing_data():
    result = evaluate_valuation_gate(
        ValuationInput(
            per=15, pbr=3.0, eps=1000, bps=5000, week52_low=15000, week52_high=15000
        ),
        ValuationPolicy(),
    )
    assert result.per_percentile is None
    assert result.pbr_percentile is None
    assert result.state == SignalState.UNKNOWN
    assert result.blocking_reasons == ["VALUATION_DATA_UNAVAILABLE"]


def test_public_rule_config_contains_no_portfolio_quantity_or_balance():
    root = Path(__file__).resolve().parents[2]
    text = (root / "config" / "investment_decision_rules.json").read_text(
        encoding="utf-8"
    )
    assert "quantity" not in text.lower()
    assert "account" not in text.lower()
    assert "holding" not in text.lower()
