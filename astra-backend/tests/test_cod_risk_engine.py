from app.services.cod_risk_engine import score_cod_risk


def test_low_risk_with_history_and_verified_phone():
    result = score_cod_risk(delivered_orders=8, return_count=0, order_total=5000,
                            historical_average=7000, route_risk="low", phone_verified=True)
    assert result.level == "LOW"
    assert result.score == 20


def test_high_risk_threshold_for_first_order_and_large_unverified_order():
    result = score_cod_risk(delivered_orders=0, return_count=0, order_total=85000,
                            historical_average=30000, route_risk="high", phone_verified=False)
    assert result.level == "HIGH"
    assert result.score > 70
    assert "First-time buyer" in result.factors


def test_missing_risk_inputs_are_reported_as_unknown():
    result = score_cod_risk(delivered_orders=0, return_count=0, order_total=8500,
                            historical_average=None, route_risk=None, phone_verified=None)
    assert result.signals["route_risk"] is None
    assert result.signals["phone_verified"] is None
    assert result.level != "HIGH"


def test_recorded_repeat_returns_and_large_order_can_cross_trigger_threshold():
    result = score_cod_risk(delivered_orders=2, return_count=1, order_total=25000,
                            historical_average=10000, route_risk=None, phone_verified=None)
    assert result.score > 70
    assert result.level == "HIGH"


def test_risk_details_endpoint_requires_authentication(anonymous_client):
    response = anonymous_client.get("/api/v1/cod-risk/orders/ORD-private")
    assert response.status_code == 401


def test_buyer_cannot_query_seller_risk_details(auth_client):
    response = auth_client.get("/api/v1/cod-risk/orders/ORD-private")
    assert response.status_code == 403
