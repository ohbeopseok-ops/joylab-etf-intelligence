from joylab_etf.intelligence.portfolio_models import ExposureRow


def test_total_value():
    row = ExposureRow(
        symbol="005930",
        name="삼성전자",
        direct_value=500_000,
        indirect_value=250_000,
    )
    assert row.total_value == 750_000


def test_zero_indirect():
    row = ExposureRow(
        symbol="000660",
        name="SK하이닉스",
        direct_value=100_000,
        indirect_value=0,
    )
    assert row.total_value == 100_000
