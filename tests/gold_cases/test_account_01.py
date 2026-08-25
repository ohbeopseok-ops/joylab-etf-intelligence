from joylab_etf.kis.account_models import AccountPosition


def test_account_position_normalization():
    p = AccountPosition(
        symbol="005930",
        name="삼성전자",
        quantity=3,
        sellable_quantity=3,
        avg_price=285000,
        purchase_amount=855000,
        current_price=257500,
        market_value=772500,
        profit_loss=-82500,
        profit_loss_pct=-9.65,
    )

    assert p.symbol == "005930"
    assert p.quantity == 3
    assert p.market_value == 772500


def test_zero_quantity_can_be_filtered_upstream():
    p = AccountPosition(
        symbol="000660",
        name="SK하이닉스",
        quantity=0,
    )
    assert p.quantity == 0
