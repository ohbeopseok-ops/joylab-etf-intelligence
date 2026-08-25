from __future__ import annotations

import math

from joylab_etf.intelligence.portfolio_gate_models import (
    PortfolioGatePolicy,
    GateInput,
    GateResult,
)


def _floor_qty(value: float, price: float) -> int:
    if price <= 0 or value <= 0:
        return 0
    return max(0, math.floor(value / price))


def evaluate_portfolio_gate(
    gate_input: GateInput,
    policy: PortfolioGatePolicy,
    split_stage: int | None = None,
) -> GateResult:
    stage = split_stage or policy.default_split_stage

    if stage < 1 or stage > len(policy.split_buy):
        raise ValueError(
            f"split_stage must be between 1 and {len(policy.split_buy)}"
        )

    split_fraction = policy.split_buy[stage - 1]

    total = gate_input.total_account_value
    if total <= 0:
        raise ValueError("total_account_value must be > 0")

    current_price = gate_input.current_price
    if current_price <= 0:
        raise ValueError("current_price must be > 0")

    true_weight_before = gate_input.true_exposure_value / total * 100.0
    cluster_weight_before = gate_input.cluster_value / total * 100.0

    # Single-stock room based on TRUE EXPOSURE, not direct holding only.
    single_limit_value = (
        total * policy.single_stock_max_pct_of_total_account / 100.0
    )
    single_room_value = max(
        0.0,
        single_limit_value - gate_input.true_exposure_value,
    )
    single_room_qty = _floor_qty(single_room_value, current_price)

    # Cluster room assumes buying this stock increases the target cluster 1:1.
    cluster_limit_pct = policy.cluster_max_pct_of_total_account.get(
        gate_input.cluster_name
    )
    if cluster_limit_pct is None:
        raise ValueError(
            f"cluster policy missing: {gate_input.cluster_name}"
        )

    cluster_limit_value = total * cluster_limit_pct / 100.0
    cluster_room_value = max(
        0.0,
        cluster_limit_value - gate_input.cluster_value,
    )
    cluster_room_qty = _floor_qty(cluster_room_value, current_price)

    # Split-buy applies to the most restrictive risk budget before KIS limit.
    raw_risk_qty = min(single_room_qty, cluster_room_qty)
    split_allowed_qty = math.floor(raw_risk_qty * split_fraction)

    # If risk budget is enough for at least 1 share but fractional split rounds
    # to 0, preserve the configured minimum order quantity only if it remains
    # inside all hard gates.
    if (
        split_allowed_qty == 0
        and raw_risk_qty >= policy.minimum_order_qty
    ):
        split_allowed_qty = policy.minimum_order_qty

    final_qty = min(
        gate_input.kis_buyable_qty,
        single_room_qty,
        cluster_room_qty,
        split_allowed_qty,
    )

    final_qty = max(0, final_qty)
    buy_amount = final_qty * current_price

    true_after = gate_input.true_exposure_value + buy_amount
    cluster_after = gate_input.cluster_value + buy_amount

    true_weight_after = true_after / total * 100.0
    cluster_weight_after = cluster_after / total * 100.0

    reasons: list[str] = []

    if gate_input.kis_buyable_qty <= 0:
        reasons.append("KIS_BUYING_POWER_BLOCK")

    if single_room_qty <= 0:
        reasons.append("SINGLE_STOCK_MAX_BLOCK")

    if cluster_room_qty <= 0:
        reasons.append("CLUSTER_MAX_BLOCK")

    if split_allowed_qty <= 0:
        reasons.append("SPLIT_BUY_BLOCK")

    if final_qty > 0:
        action = "사자"
    elif (
        gate_input.true_exposure_value > single_limit_value
        or gate_input.cluster_value > cluster_limit_value
    ):
        action = "보류"
    else:
        action = "보류"

    return GateResult(
        symbol=gate_input.symbol,
        name=gate_input.name,
        current_price=round(current_price, 2),

        true_exposure_before=round(gate_input.true_exposure_value, 2),
        true_weight_before_pct=round(true_weight_before, 2),

        cluster_value_before=round(gate_input.cluster_value, 2),
        cluster_weight_before_pct=round(cluster_weight_before, 2),

        single_stock_room_value=round(single_room_value, 2),
        single_stock_room_qty=single_room_qty,

        cluster_room_value=round(cluster_room_value, 2),
        cluster_room_qty=cluster_room_qty,

        kis_buyable_qty=gate_input.kis_buyable_qty,
        split_stage=stage,
        split_fraction=split_fraction,
        split_allowed_qty=split_allowed_qty,

        final_allowed_qty=final_qty,
        buy_amount=round(buy_amount, 2),

        true_exposure_after=round(true_after, 2),
        true_weight_after_pct=round(true_weight_after, 2),

        cluster_value_after=round(cluster_after, 2),
        cluster_weight_after_pct=round(cluster_weight_after, 2),

        action=action,
        blocking_reasons=reasons,
    )
