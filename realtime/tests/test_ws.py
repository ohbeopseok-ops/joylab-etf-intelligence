from app.ws import KISWebSocketClient
def test_subscription():
    s=KISWebSocketClient.subscription_message("x","005930")
    assert "H0STCNT0" in s and "005930" in s
def test_parse():
    v=["005930","100701","263000","5","-3000","-1.13","0","266000","267000","262000","263500","263000","15","123456"]+["0"]*40
    t=KISWebSocketClient.parse_execution_message("0|H0STCNT0|1|"+"^".join(v))
    assert t and t.price==263000 and t.change_pct==-1.13
