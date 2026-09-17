from __future__ import annotations

from joylab_etf.intelligence.entry_gate_models import (
    EntryDecision,
    EntryGateInput,
    EntryGateResult,
)


def _score_price(x: EntryGateInput) -> int:
    if x.current_price >= x.trigger_price and x.hold_minutes >= 15:
        return 20
    if x.current_price >= x.trigger_price:
        return 12
    return 0


def _score_foreign(x: EntryGateInput) -> int:
    if x.investor_flow_status != "estimated" or x.investor_flow_stale:
        return 0
    if x.foreign_net_buy_amount is None:
        return 0
    if x.foreign_net_buy_amount > 0:
        return 25
    if x.foreign_net_buy_amount < 0:
        return 0
    return 10


def _score_institution(x: EntryGateInput) -> int:
    if x.institution_net_buy_amount is None:
        return 0
    if x.institution_net_buy_amount > 0:
        return 10
    if x.institution_net_buy_amount == 0:
        return 5
    return 0


def _score_volume(x: EntryGateInput) -> int:
    if x.volume_ratio is None:
        return 0
    if x.volume_ratio >= 1.2:
        return 10
    if x.volume_ratio >= 1.0:
        return 6
    return 0


def _score_rs(x: EntryGateInput) -> int:
    if x.relative_strength_pct is None:
        return 0
    if x.relative_strength_pct >= 1.0:
        return 15
    if x.relative_strength_pct >= 0.5:
        return 10
    if x.relative_strength_pct > 0:
        return 5
    return 0


def _score_sector(x: EntryGateInput) -> int:
    if x.sector_relative_strength_pct is None:
        return 0
    if x.sector_relative_strength_pct > 0:
        return 10
    return 0


def evaluate_entry_gate(x: EntryGateInput) -> EntryGateResult:
    breakdown = {
        "price": _score_price(x),
        "foreign": _score_foreign(x),
        "institution": _score_institution(x),
        "volume": _score_volume(x),
        "relative_strength": _score_rs(x),
        "sector_strength": _score_sector(x),
        "macro_regime": x.macro_regime_score,
    }
    total = sum(breakdown.values())

    primary_flow_confirmed = (
        x.investor_flow_status == "estimated"
        and not x.investor_flow_stale
        and x.foreign_net_buy_amount is not None
    )
    auxiliary_positive = (
        x.program_net_buy_amount is not None and x.program_net_buy_amount > 0
    )

    blocking: list[str] = []
    if not primary_flow_confirmed:
        blocking.append("primary_investor_flow_unavailable_or_stale")
    if x.current_price < x.trigger_price:
        blocking.append("price_trigger_not_met")
    if x.hold_minutes < 15:
        blocking.append("hold_time_not_met")

    if not primary_flow_confirmed:
        decision = EntryDecision.WAIT if auxiliary_positive or total >= 65 else EntryDecision.NO_ENTRY
    elif total >= 80 and not blocking:
        decision = EntryDecision.READY
    elif total >= 65:
        decision = EntryDecision.WAIT
    else:
        decision = EntryDecision.NO_ENTRY

    return EntryGateResult(
        symbol=x.symbol,
        total_score=total,
        decision=decision,
        primary_flow_confirmed=primary_flow_confirmed,
        auxiliary_positive=auxiliary_positive,
        blocking_reasons=blocking,
        score_breakdown=breakdown,
    )
