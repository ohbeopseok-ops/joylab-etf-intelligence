from joylab_etf.intelligence.entry_gate import evaluate_entry_gate
from joylab_etf.intelligence.entry_gate_models import EntryDecision, EntryGateInput


def _base(**overrides):
    data = dict(
        symbol="105560",
        name="KB금융",
        current_price=181900,
        trigger_price=181600,
        hold_minutes=15,
        foreign_net_buy_amount=4_200_000_000,
        institution_net_buy_amount=1_700_000_000,
        investor_flow_status="estimated",
        investor_flow_stale=False,
        program_net_buy_amount=5_100_000_000,
        volume_ratio=1.31,
        relative_strength_pct=1.6,
        sector_relative_strength_pct=1.2,
        macro_regime_score=8,
    )
    data.update(overrides)
    return EntryGateInput(**data)


def test_gold_kb_ready_when_all_primary_conditions_confirmed():
    result = evaluate_entry_gate(_base())
    assert result.decision == EntryDecision.READY
    assert result.primary_flow_confirmed is True
    assert result.total_score >= 80
    assert result.blocking_reasons == []


def test_gold_kb_wait_when_primary_flow_unavailable_even_if_program_positive():
    result = evaluate_entry_gate(
        _base(
            foreign_net_buy_amount=None,
            institution_net_buy_amount=None,
            investor_flow_status="unavailable",
            program_net_buy_amount=8_000_000_000,
        )
    )
    assert result.decision == EntryDecision.WAIT
    assert result.primary_flow_confirmed is False
    assert "primary_investor_flow_unavailable_or_stale" in result.blocking_reasons


def test_gold_kb_wait_when_flow_is_stale():
    result = evaluate_entry_gate(_base(investor_flow_stale=True))
    assert result.decision == EntryDecision.WAIT
    assert result.primary_flow_confirmed is False


def test_gold_kb_no_entry_before_price_trigger():
    result = evaluate_entry_gate(
        _base(
            current_price=180500,
            hold_minutes=0,
            foreign_net_buy_amount=-2_000_000_000,
            institution_net_buy_amount=-1_000_000_000,
            program_net_buy_amount=-500_000_000,
            volume_ratio=0.8,
            relative_strength_pct=-0.5,
            sector_relative_strength_pct=-0.2,
            macro_regime_score=4,
        )
    )
    assert result.decision == EntryDecision.NO_ENTRY
    assert "price_trigger_not_met" in result.blocking_reasons
