from __future__ import annotations

import json
from datetime import date
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field, model_validator


class DecisionAction(str, Enum):
    BUY = "사자"
    HOLD = "보류"
    SELL = "팔자"


class SignalState(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class EvidenceStatus(str, Enum):
    CONFIRMED = "CONFIRMED"
    ESTIMATED = "ESTIMATED"
    UNVERIFIED = "UNVERIFIED"


class ThesisState(str, Enum):
    UNKNOWN = "UNKNOWN"
    INTACT = "INTACT"
    WEAKENING = "WEAKENING"
    BROKEN = "BROKEN"


class ExitTrigger(str, Enum):
    THESIS_BROKEN = "THESIS_BROKEN"
    LEVERAGE_RISK = "LEVERAGE_RISK"
    DAMAGE_EXPANDING = "DAMAGE_EXPANDING"


class RotationLevel(str, Enum):
    WEAK = "WEAK"
    WATCH = "WATCH"
    POSSIBLE = "POSSIBLE"
    STRONG = "STRONG"
    CONFIRMED = "CONFIRMED"


class PriceRule(BaseModel):
    recovery_min: float | None = Field(default=None, gt=0)
    buy_zone_min: float | None = Field(default=None, gt=0)
    buy_zone_max: float | None = Field(default=None, gt=0)
    no_chase_above: float | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_zone(self) -> "PriceRule":
        if (self.buy_zone_min is None) != (self.buy_zone_max is None):
            raise ValueError("buy zone requires both minimum and maximum")
        if (
            self.buy_zone_min is not None
            and self.buy_zone_max is not None
            and self.buy_zone_min > self.buy_zone_max
        ):
            raise ValueError("buy_zone_min must not exceed buy_zone_max")
        return self


class FlowRule(BaseModel):
    require_foreign_selling_easing: bool = False
    require_institutional_selling_easing: bool = False
    require_pension_selling_easing: bool = False
    min_pension_net_buy_streak_days: int | None = Field(default=None, ge=1)


class InstrumentWatchRule(BaseModel):
    symbol: str
    name: str
    as_of_date: date
    valid_through: date
    ticker_source_url: str
    price: PriceRule | None = None
    flow: FlowRule = Field(default_factory=FlowRule)
    require_relative_strength: bool = True
    notes: list[str] = Field(default_factory=list)
    # Qualitative gates: KIS has no live source for these, so a human/LLM
    # sets them explicitly during conversation and they ride the same
    # as_of_date/valid_through staleness check as price/flow. Default
    # NOT_APPLICABLE means "not yet assessed", not "passes".
    governance_esr_gate: SignalState = SignalState.NOT_APPLICABLE
    ai_power_gate: SignalState = SignalState.NOT_APPLICABLE
    # When set, ai_power_gate above is ignored and recomputed live via
    # evaluate_ai_power_gate(ai_power_watch, ai_power_policy) instead --
    # this is the actual Gate 10 formula, not a hand-set label.
    ai_power_watch: "AIPowerWatchInput | None" = None
    # Same pattern as governance_esr_gate: no live source, human/LLM-set,
    # rides as_of_date/valid_through staleness. Default UNKNOWN matches the
    # prior hardcoded behavior in StockAssistantService.analyze() before
    # this field existed -- INTACT is never assumed by default.
    thesis_state: ThesisState = ThesisState.UNKNOWN

    @model_validator(mode="after")
    def validate_dates(self) -> "InstrumentWatchRule":
        if self.valid_through < self.as_of_date:
            raise ValueError("valid_through must not precede as_of_date")
        return self


class InstrumentObservation(BaseModel):
    observed_on: date
    current_price: float = Field(gt=0)
    price_confirmation_pass: bool | None = None
    flow_confirmation_pass: bool | None = None
    foreign_selling_easing: bool | None = None
    institutional_selling_easing: bool | None = None
    pension_selling_easing: bool | None = None
    pension_net_buy_streak_days: int | None = Field(default=None, ge=0)
    relative_strength_pass: bool | None = None


class InstrumentSignalResult(BaseModel):
    symbol: str
    price_gate: SignalState
    flow_gate: SignalState
    relative_strength_gate: SignalState
    data_confidence_gate: SignalState
    reasons: list[str]


class DecisionInput(BaseModel):
    symbol: str
    name: str
    price_gate: SignalState
    flow_gate: SignalState
    relative_strength_gate: SignalState
    strategy_gate: SignalState
    data_confidence_gate: SignalState
    thesis_state: ThesisState
    valuation_gate: SignalState = SignalState.UNKNOWN
    fundamental_eps_gate: SignalState = SignalState.UNKNOWN
    governance_esr_gate: SignalState = SignalState.UNKNOWN
    semiconductor_gate: SignalState = SignalState.UNKNOWN
    ai_power_gate: SignalState = SignalState.UNKNOWN
    korea_translation_gate: SignalState = SignalState.UNKNOWN
    pension_rotation_gate: SignalState = SignalState.UNKNOWN
    portfolio_allowed_qty: int = Field(ge=0)
    portfolio_blocking_reasons: list[str] = Field(default_factory=list)
    exit_triggers: list[ExitTrigger] = Field(default_factory=list)


class DecisionResult(BaseModel):
    symbol: str
    name: str
    action: DecisionAction
    portfolio_allowed_qty: int
    recommended_qty: int
    blocking_reasons: list[str]
    exit_reasons: list[ExitTrigger]
    passed_gates: list[str]
    not_applicable_gates: list[str]


class EvidenceItem(BaseModel):
    key: str
    status: EvidenceStatus
    source: str | None = None


class DataConfidenceResult(BaseModel):
    state: SignalState
    confirmed: list[str]
    estimated: list[str]
    unverified_or_missing: list[str]


class EffectiveShareholderReturnInput(BaseModel):
    unit: str
    cash_dividend: float | None = Field(default=None, ge=0)
    genuine_cancellation: float | None = Field(default=None, ge=0)
    net_buyback: float | None = None
    employee_equity_compensation: float | None = Field(default=None, ge=0)
    governance_constraint_discount: float | None = Field(default=None, ge=0)


class EffectiveShareholderReturnResult(BaseModel):
    state: SignalState
    unit: str
    effective_shareholder_return: float | None
    missing_components: list[str]
    accounting_formula: bool = False


class OpportunityPolicy(BaseModel):
    candidate_threshold: float = Field(default=80, ge=0, le=100)
    pension_adjustment_max_abs: float = Field(default=5, ge=0, le=100)


class OpportunityScoreInput(BaseModel):
    base_score: float = Field(ge=0, le=100)
    pension_flow_adjustment: float = 0


class OpportunityScoreResult(BaseModel):
    adjusted_score: float
    ranking_candidate: bool
    automatic_buy: bool = False


class AIPowerScorePolicy(BaseModel):
    order_backlog_missing_cap: float = Field(default=79, ge=0, lt=80)
    margin_missing_cap: float = Field(default=84, ge=0, lt=85)


class AIPowerScoreInput(BaseModel):
    hyperscaler_capex: float = Field(ge=0, le=25)
    gpu_hbm_demand: float = Field(ge=0, le=25)
    electricity_grid_constraint: float = Field(ge=0, le=20)
    data_center_energization: float = Field(ge=0, le=15)
    cooling_power_equipment: float = Field(ge=0, le=15)
    order_backlog_growth: SignalState = SignalState.UNKNOWN
    operating_margin_improvement: SignalState = SignalState.UNKNOWN
    valuation_not_overheated: SignalState = SignalState.UNKNOWN
    ai_data_center_revenue_share_clear: SignalState = SignalState.UNKNOWN


class AIPowerScoreResult(BaseModel):
    raw_score: float
    capped_score: float
    maximum_action: DecisionAction
    caps_applied: list[str]
    automatic_buy: bool = False


class AIPowerWatchInput(BaseModel):
    ls_electric_relative_strength: bool | None = None
    peer_strength_confirmed: bool | None = None
    sector_breadth_confirmed: bool | None = None
    institutional_rotation_confirmed: bool | None = None
    semiconductor_weak_power_strong: bool | None = None
    etf_outperforms_kospi: bool | None = None
    order_backlog: SignalState = SignalState.UNKNOWN
    revenue_recognition: SignalState = SignalState.UNKNOWN
    operating_margin: SignalState = SignalState.UNKNOWN
    eps_revision: SignalState = SignalState.UNKNOWN


InstrumentWatchRule.model_rebuild()


class AIPowerPolicy(BaseModel):
    min_rotation_checks: int = Field(default=3, ge=1, le=5)
    require_etf_outperformance: bool = True
    require_revenue_translation: bool = True


class AIPowerGateResult(BaseModel):
    state: SignalState
    rotation_score: int
    rotation_level: RotationLevel
    revenue_translation_state: SignalState
    unknown_rotation_checks: list[str]
    blocking_reasons: list[str]


class InvestmentDecisionConfig(BaseModel):
    snapshot_name: str
    ai_power_policy: AIPowerPolicy
    ai_power_score_policy: AIPowerScorePolicy = Field(
        default_factory=AIPowerScorePolicy
    )
    opportunity_policy: OpportunityPolicy = Field(default_factory=OpportunityPolicy)
    watch_rules: list[InstrumentWatchRule]


def load_decision_config(path: str | Path) -> InvestmentDecisionConfig:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return InvestmentDecisionConfig(**data)


def evaluate_data_confidence(
    evidence: list[EvidenceItem],
    required_keys: list[str],
) -> DataConfidenceResult:
    by_key = {item.key: item for item in evidence}
    confirmed: list[str] = []
    estimated: list[str] = []
    unverified_or_missing: list[str] = []

    for key in required_keys:
        item = by_key.get(key)
        if item is None or item.status == EvidenceStatus.UNVERIFIED:
            unverified_or_missing.append(key)
        elif item.status == EvidenceStatus.ESTIMATED:
            estimated.append(key)
        else:
            confirmed.append(key)

    if unverified_or_missing:
        state = SignalState.FAIL
    elif estimated:
        state = SignalState.UNKNOWN
    else:
        state = SignalState.PASS

    return DataConfidenceResult(
        state=state,
        confirmed=confirmed,
        estimated=estimated,
        unverified_or_missing=unverified_or_missing,
    )


def calculate_effective_shareholder_return(
    inputs: EffectiveShareholderReturnInput,
) -> EffectiveShareholderReturnResult:
    component_names = [
        "cash_dividend",
        "genuine_cancellation",
        "net_buyback",
        "employee_equity_compensation",
        "governance_constraint_discount",
    ]
    missing = [name for name in component_names if getattr(inputs, name) is None]
    if missing:
        return EffectiveShareholderReturnResult(
            state=SignalState.UNKNOWN,
            unit=inputs.unit,
            effective_shareholder_return=None,
            missing_components=missing,
        )

    assert inputs.cash_dividend is not None
    assert inputs.genuine_cancellation is not None
    assert inputs.net_buyback is not None
    assert inputs.employee_equity_compensation is not None
    assert inputs.governance_constraint_discount is not None
    value = (
        inputs.cash_dividend
        + inputs.genuine_cancellation
        + inputs.net_buyback
        - inputs.employee_equity_compensation
        - inputs.governance_constraint_discount
    )
    return EffectiveShareholderReturnResult(
        state=SignalState.PASS,
        unit=inputs.unit,
        effective_shareholder_return=round(value, 6),
        missing_components=[],
    )


def calculate_opportunity_score(
    score_input: OpportunityScoreInput,
    policy: OpportunityPolicy,
) -> OpportunityScoreResult:
    if abs(score_input.pension_flow_adjustment) > policy.pension_adjustment_max_abs:
        raise ValueError("pension_flow_adjustment exceeds policy maximum")
    adjusted = min(
        100.0,
        max(0.0, score_input.base_score + score_input.pension_flow_adjustment),
    )
    return OpportunityScoreResult(
        adjusted_score=round(adjusted, 6),
        ranking_candidate=adjusted >= policy.candidate_threshold,
    )


def calculate_ai_power_score(
    score_input: AIPowerScoreInput,
    policy: AIPowerScorePolicy,
) -> AIPowerScoreResult:
    raw_score = (
        score_input.hyperscaler_capex
        + score_input.gpu_hbm_demand
        + score_input.electricity_grid_constraint
        + score_input.data_center_energization
        + score_input.cooling_power_equipment
    )
    capped_score = raw_score
    caps: list[str] = []

    if score_input.order_backlog_growth != SignalState.PASS and raw_score >= 80:
        capped_score = min(capped_score, policy.order_backlog_missing_cap)
        caps.append("ORDER_BACKLOG_80_CAP")
    if (
        score_input.operating_margin_improvement != SignalState.PASS
        and raw_score >= 85
    ):
        capped_score = min(capped_score, policy.margin_missing_cap)
        caps.append("OPERATING_MARGIN_85_CAP")

    maximum_action = DecisionAction.BUY
    if score_input.valuation_not_overheated != SignalState.PASS:
        maximum_action = DecisionAction.HOLD
        caps.append("VALUATION_AUTO_PROMOTION_BLOCK")
    if score_input.ai_data_center_revenue_share_clear != SignalState.PASS:
        maximum_action = DecisionAction.HOLD
        caps.append("AI_REVENUE_SHARE_HOLD_CEILING")

    return AIPowerScoreResult(
        raw_score=round(raw_score, 6),
        capped_score=round(capped_score, 6),
        maximum_action=maximum_action,
        caps_applied=caps,
    )


def _combine_checks(checks: list[bool | None]) -> SignalState:
    if any(check is False for check in checks):
        return SignalState.FAIL
    if not checks or any(check is None for check in checks):
        return SignalState.UNKNOWN
    return SignalState.PASS


def evaluate_instrument_rule(
    rule: InstrumentWatchRule,
    observation: InstrumentObservation,
) -> InstrumentSignalResult:
    reasons: list[str] = []

    price_checks: list[bool | None] = [observation.price_confirmation_pass]
    if rule.price is not None:
        if rule.price.recovery_min is not None:
            price_checks.append(observation.current_price >= rule.price.recovery_min)
        if rule.price.buy_zone_min is not None and rule.price.buy_zone_max is not None:
            price_checks.append(
                rule.price.buy_zone_min
                <= observation.current_price
                <= rule.price.buy_zone_max
            )
        if rule.price.no_chase_above is not None:
            price_checks.append(observation.current_price <= rule.price.no_chase_above)
    price_gate = _combine_checks(price_checks)
    if price_gate != SignalState.PASS:
        reasons.append(f"PRICE_GATE_{price_gate.value}")

    flow_checks: list[bool | None] = [observation.flow_confirmation_pass]
    if rule.flow.require_foreign_selling_easing:
        flow_checks.append(observation.foreign_selling_easing)
    if rule.flow.require_institutional_selling_easing:
        flow_checks.append(observation.institutional_selling_easing)
    if rule.flow.require_pension_selling_easing:
        flow_checks.append(observation.pension_selling_easing)
    if rule.flow.min_pension_net_buy_streak_days is not None:
        flow_checks.append(
            None
            if observation.pension_net_buy_streak_days is None
            else observation.pension_net_buy_streak_days
            >= rule.flow.min_pension_net_buy_streak_days
        )
    flow_gate = _combine_checks(flow_checks)
    if flow_gate != SignalState.PASS:
        reasons.append(f"FLOW_GATE_{flow_gate.value}")

    relative_strength_gate = (
        _combine_checks([observation.relative_strength_pass])
        if rule.require_relative_strength
        else SignalState.PASS
    )
    if relative_strength_gate != SignalState.PASS:
        reasons.append(f"RELATIVE_STRENGTH_GATE_{relative_strength_gate.value}")

    data_confidence_gate = (
        SignalState.PASS
        if rule.as_of_date <= observation.observed_on <= rule.valid_through
        else SignalState.FAIL
    )
    if data_confidence_gate != SignalState.PASS:
        reasons.append("STALE_STRATEGY_RULE")

    return InstrumentSignalResult(
        symbol=rule.symbol,
        price_gate=price_gate,
        flow_gate=flow_gate,
        relative_strength_gate=relative_strength_gate,
        data_confidence_gate=data_confidence_gate,
        reasons=reasons,
    )


def evaluate_investment_decision(decision_input: DecisionInput) -> DecisionResult:
    exit_reasons = list(dict.fromkeys(decision_input.exit_triggers))
    if (
        decision_input.thesis_state == ThesisState.BROKEN
        and ExitTrigger.THESIS_BROKEN not in exit_reasons
    ):
        exit_reasons.append(ExitTrigger.THESIS_BROKEN)

    if exit_reasons:
        return DecisionResult(
            symbol=decision_input.symbol,
            name=decision_input.name,
            action=DecisionAction.SELL,
            portfolio_allowed_qty=decision_input.portfolio_allowed_qty,
            recommended_qty=0,
            blocking_reasons=[],
            exit_reasons=exit_reasons,
            passed_gates=[],
            not_applicable_gates=[],
        )

    gates = {
        "PRICE": decision_input.price_gate,
        "VALUATION": decision_input.valuation_gate,
        "FLOW": decision_input.flow_gate,
        "RELATIVE_STRENGTH": decision_input.relative_strength_gate,
        "FUNDAMENTAL_EPS": decision_input.fundamental_eps_gate,
        "GOVERNANCE_ESR": decision_input.governance_esr_gate,
        "STRATEGY": decision_input.strategy_gate,
        "DATA_CONFIDENCE": decision_input.data_confidence_gate,
        "SEMICONDUCTOR": decision_input.semiconductor_gate,
        "AI_POWER": decision_input.ai_power_gate,
        "KOREA_TRANSLATION": decision_input.korea_translation_gate,
        "PENSION_ROTATION": decision_input.pension_rotation_gate,
    }
    blocking_reasons = [
        f"{name}_GATE_{state.value}"
        for name, state in gates.items()
        if state in {SignalState.FAIL, SignalState.UNKNOWN}
    ]
    passed_gates = [name for name, state in gates.items() if state == SignalState.PASS]
    not_applicable_gates = [
        name for name, state in gates.items() if state == SignalState.NOT_APPLICABLE
    ]

    if decision_input.thesis_state != ThesisState.INTACT:
        blocking_reasons.append(f"THESIS_{decision_input.thesis_state.value}")
    else:
        passed_gates.append("THESIS")

    if decision_input.portfolio_allowed_qty <= 0:
        blocking_reasons.append("PORTFOLIO_GATE_BLOCK")
        blocking_reasons.extend(decision_input.portfolio_blocking_reasons)
    else:
        passed_gates.append("PORTFOLIO")

    blocking_reasons = list(dict.fromkeys(blocking_reasons))
    action = DecisionAction.BUY if not blocking_reasons else DecisionAction.HOLD
    return DecisionResult(
        symbol=decision_input.symbol,
        name=decision_input.name,
        action=action,
        portfolio_allowed_qty=decision_input.portfolio_allowed_qty,
        recommended_qty=(
            decision_input.portfolio_allowed_qty
            if action == DecisionAction.BUY
            else 0
        ),
        blocking_reasons=blocking_reasons,
        exit_reasons=[],
        passed_gates=passed_gates,
        not_applicable_gates=not_applicable_gates,
    )


def evaluate_rule_based_decision(
    rule: InstrumentWatchRule,
    observation: InstrumentObservation,
    strategy_gate: SignalState,
    thesis_state: ThesisState,
    portfolio_allowed_qty: int,
    portfolio_blocking_reasons: list[str] | None = None,
    exit_triggers: list[ExitTrigger] | None = None,
    valuation_gate: SignalState = SignalState.UNKNOWN,
    fundamental_eps_gate: SignalState = SignalState.UNKNOWN,
    governance_esr_gate: SignalState = SignalState.UNKNOWN,
    semiconductor_gate: SignalState = SignalState.UNKNOWN,
    ai_power_gate: SignalState = SignalState.UNKNOWN,
    korea_translation_gate: SignalState = SignalState.UNKNOWN,
    pension_rotation_gate: SignalState = SignalState.UNKNOWN,
) -> DecisionResult:
    signals = evaluate_instrument_rule(rule, observation)
    return evaluate_investment_decision(
        DecisionInput(
            symbol=rule.symbol,
            name=rule.name,
            price_gate=signals.price_gate,
            flow_gate=signals.flow_gate,
            relative_strength_gate=signals.relative_strength_gate,
            strategy_gate=strategy_gate,
            data_confidence_gate=signals.data_confidence_gate,
            thesis_state=thesis_state,
            valuation_gate=valuation_gate,
            fundamental_eps_gate=fundamental_eps_gate,
            governance_esr_gate=governance_esr_gate,
            semiconductor_gate=semiconductor_gate,
            ai_power_gate=ai_power_gate,
            korea_translation_gate=korea_translation_gate,
            pension_rotation_gate=pension_rotation_gate,
            portfolio_allowed_qty=portfolio_allowed_qty,
            portfolio_blocking_reasons=portfolio_blocking_reasons or [],
            exit_triggers=exit_triggers or [],
        )
    )


def _rotation_level(score: int) -> RotationLevel:
    if score <= 1:
        return RotationLevel.WEAK
    if score == 2:
        return RotationLevel.WATCH
    if score == 3:
        return RotationLevel.POSSIBLE
    if score == 4:
        return RotationLevel.STRONG
    return RotationLevel.CONFIRMED


def _combine_signal_states(states: list[SignalState]) -> SignalState:
    applicable = [state for state in states if state != SignalState.NOT_APPLICABLE]
    if not applicable:
        return SignalState.NOT_APPLICABLE
    if any(state == SignalState.FAIL for state in applicable):
        return SignalState.FAIL
    if any(state == SignalState.UNKNOWN for state in applicable):
        return SignalState.UNKNOWN
    return SignalState.PASS


def evaluate_ai_power_gate(
    watch: AIPowerWatchInput,
    policy: AIPowerPolicy,
) -> AIPowerGateResult:
    rotation_checks = {
        "LS_ELECTRIC_RELATIVE_STRENGTH": watch.ls_electric_relative_strength,
        "PEER_STRENGTH": watch.peer_strength_confirmed,
        "SECTOR_BREADTH": watch.sector_breadth_confirmed,
        "INSTITUTIONAL_ROTATION": watch.institutional_rotation_confirmed,
        "SEMICONDUCTOR_WEAK_POWER_STRONG": watch.semiconductor_weak_power_strong,
    }
    score = sum(value is True for value in rotation_checks.values())
    unknown = [name for name, value in rotation_checks.items() if value is None]
    revenue_state = _combine_signal_states(
        [
            watch.order_backlog,
            watch.revenue_recognition,
            watch.operating_margin,
            watch.eps_revision,
        ]
    )

    blockers: list[str] = []
    if score < policy.min_rotation_checks:
        blockers.append("ROTATION_SCORE_BELOW_MINIMUM")
    if policy.require_etf_outperformance and watch.etf_outperforms_kospi is not True:
        blockers.append(
            "ETF_RELATIVE_STRENGTH_UNKNOWN"
            if watch.etf_outperforms_kospi is None
            else "ETF_RELATIVE_STRENGTH_BLOCK"
        )
    if policy.require_revenue_translation and revenue_state != SignalState.PASS:
        blockers.append(f"REVENUE_TRANSLATION_{revenue_state.value}")

    if not blockers:
        state = SignalState.PASS
    elif (
        watch.etf_outperforms_kospi is False
        or revenue_state == SignalState.FAIL
        or score + len(unknown) < policy.min_rotation_checks
    ):
        state = SignalState.FAIL
    else:
        state = SignalState.UNKNOWN

    return AIPowerGateResult(
        state=state,
        rotation_score=score,
        rotation_level=_rotation_level(score),
        revenue_translation_state=revenue_state,
        unknown_rotation_checks=unknown,
        blocking_reasons=blockers,
    )
