from joylab_etf.intelligence.portfolio_gate_models import (
    PortfolioGatePolicy,
    GateInput,
)
from joylab_etf.intelligence.portfolio_gate import evaluate_portfolio_gate


def policy():
    return PortfolioGatePolicy(
        single_stock_max_pct_of_total_account=30.0,
        cluster_max_pct_of_total_account={"semiconductor": 50.0},
        split_buy=[0.30, 0.30, 0.40],
        default_split_stage=1,
        use_no_credit_buying_power=True,
        minimum_order_qty=1,
    )


def test_single_stock_gate_blocks_overweight():
    inp = GateInput(
        symbol="005930",
        name="삼성전자",
        current_price=250000,
        direct_value=600000,
        indirect_value=0,
        true_exposure_value=600000,
        total_account_value=1_000_000,
        securities_value=800000,
        cluster_name="semiconductor",
        cluster_value=600000,
        kis_buyable_qty=2,
        kis_buyable_amount=500000,
    )

    result = evaluate_portfolio_gate(inp, policy())

    assert result.single_stock_room_qty == 0
    assert result.final_allowed_qty == 0
    assert "SINGLE_STOCK_MAX_BLOCK" in result.blocking_reasons


def test_cluster_gate_blocks_even_if_single_stock_has_room():
    inp = GateInput(
        symbol="005930",
        name="삼성전자",
        current_price=100000,
        direct_value=100000,
        indirect_value=0,
        true_exposure_value=100000,
        total_account_value=1_000_000,
        securities_value=500000,
        cluster_name="semiconductor",
        cluster_value=500000,
        kis_buyable_qty=5,
        kis_buyable_amount=500000,
    )

    result = evaluate_portfolio_gate(inp, policy())

    assert result.cluster_room_qty == 0
    assert result.final_allowed_qty == 0
    assert "CLUSTER_MAX_BLOCK" in result.blocking_reasons


def test_split_buy_is_more_conservative_than_hard_gate():
    inp = GateInput(
        symbol="005930",
        name="삼성전자",
        current_price=100000,
        direct_value=0,
        indirect_value=0,
        true_exposure_value=0,
        total_account_value=2_000_000,
        securities_value=0,
        cluster_name="semiconductor",
        cluster_value=0,
        kis_buyable_qty=10,
        kis_buyable_amount=1_000_000,
    )

    result = evaluate_portfolio_gate(inp, policy())

    # single room = 600k => 6 shares
    # cluster room = 1m => 10 shares
    # risk qty = 6
    # stage1 30% => floor(1.8) = 1
    assert result.single_stock_room_qty == 6
    assert result.cluster_room_qty == 10
    assert result.split_allowed_qty == 1
    assert result.final_allowed_qty == 1


def test_kis_limit_is_final_hard_cap():
    inp = GateInput(
        symbol="005930",
        name="삼성전자",
        current_price=100000,
        direct_value=0,
        indirect_value=0,
        true_exposure_value=0,
        total_account_value=10_000_000,
        securities_value=0,
        cluster_name="semiconductor",
        cluster_value=0,
        kis_buyable_qty=1,
        kis_buyable_amount=100000,
    )

    result = evaluate_portfolio_gate(inp, policy(), split_stage=3)

    assert result.final_allowed_qty == 1


def test_post_buy_weights_do_not_use_securities_as_denominator():
    inp = GateInput(
        symbol="005930",
        name="삼성전자",
        current_price=100000,
        direct_value=100000,
        indirect_value=0,
        true_exposure_value=100000,
        total_account_value=1_000_000,
        securities_value=200000,
        cluster_name="semiconductor",
        cluster_value=100000,
        kis_buyable_qty=1,
        kis_buyable_amount=100000,
    )

    result = evaluate_portfolio_gate(inp, policy(), split_stage=3)

    assert result.true_weight_before_pct == 10.0
    assert result.cluster_weight_before_pct == 10.0
