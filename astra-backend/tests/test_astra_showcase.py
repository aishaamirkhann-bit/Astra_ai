"""Showcase-feature coverage: A2A negotiation WS, authenticity/ZK/deepfake, voice intent,
micro-escrow settlements, swarm log, restock forecasts and the sub-30s dispute timeline."""
from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.main import app
from app.models.user import User
from app.models.wallet import UserWallet


def _login(email: str) -> TestClient:
    anonymous = TestClient(app)
    challenge = anonymous.post("/api/v1/auth/login", json={"email": email, "password": "demo1234"})
    assert challenge.status_code == 200, challenge.text
    verified = anonymous.post(
        "/api/v1/auth/verify-otp",
        json={"otp_token": challenge.json()["otp_token"], "code": "123456"},
    )
    assert verified.status_code == 200, verified.text
    return TestClient(app, headers={"Authorization": f"Bearer {verified.json()['access_token']}"})


def test_authenticity_includes_zk_stamp_and_deepfake_scan() -> None:
    buyer = _login("aisha@astra.ai")
    response = buyer.get("/api/v1/products/samsung-galaxy-s25-ultra/authenticity")
    assert response.status_code == 200
    audit = response.json()
    assert audit["zk_verification"]["status"] == "verified"
    assert audit["zk_verification"]["proof_id"].startswith("zk-")
    assert len(audit["seller_reputation_hash"]) == 32
    assert audit["cryptographic_stamp"]["stamp_id"].startswith("ASTRA-STAMP-")
    assert audit["cryptographic_stamp"]["signed_payload"] == audit["listing_hash"][:16]
    scan = audit["synthetic_image_scan"]
    assert scan["verdict"] == "authentic"
    assert scan["score"] < 1.0
    assert {"zk_proof", "synthetic_scan"} <= {check["id"] for check in audit["checks"]}


def test_voice_intent_resolves_buy_with_budget() -> None:
    anonymous = TestClient(app)
    result = anonymous.post("/api/v1/explore/intent", json={"query": "buy a gaming laptop under 200k"})
    assert result.status_code == 200, result.text
    intent = result.json()
    assert intent["intent"] == "buy"
    assert intent["budget"] == 200000
    assert intent["auto_checkout"] is True
    assert intent["matched_product"] is not None
    assert intent["matched_product"]["price"] <= 200000

    roman_urdu = anonymous.post("/api/v1/explore/intent", json={"query": "mujhe samsung phone kharido 150 hazar tak"})
    assert roman_urdu.status_code == 200
    urdu_intent = roman_urdu.json()
    assert urdu_intent["intent"] == "buy"
    assert urdu_intent["budget"] == 150000

    plain = anonymous.post("/api/v1/explore/intent", json={"query": "headphones"})
    assert plain.status_code == 200
    assert plain.json()["intent"] != "buy"


def test_micro_settlements_are_zero_fee_multicurrency() -> None:
    buyer = _login("aisha@astra.ai")
    response = buyer.get("/api/v1/wallet/micro-settlements", params={"amount": 50000})
    assert response.status_code == 200
    settlement = response.json()
    assert settlement["total_fee"] == 0
    assert len(settlement["routes"]) == 3
    assert {route["fee"] for route in settlement["routes"]} == {0.0}
    currencies = {route["to"] for route in settlement["routes"]}
    assert "USD" in currencies and "PKR" in currencies
    assert settlement["total_latency_ms"] < 1500


def test_remittance_context_is_static_capability_metadata() -> None:
    buyer = _login("aisha@astra.ai")
    response = buyer.get("/api/v1/wallet/remittance-context")
    assert response.status_code == 200, response.text
    context = response.json()
    assert context["reference"].startswith("wallet-")
    assert context["status"] == "stub"
    assert context["source_country"] == "PK"
    assert context["source_currency"] == "PKR"
    assert context["required_recipient_fields"] == ["full_name", "country_code", "payout_method"]
    assert context["compliance"] == {"kyc_required": True, "sanctions_screening": "not_started"}
    assert {destination["currency"] for destination in context["destinations"]} == {"AED", "SAR", "USD"}


def test_budget_dashboard_includes_restock_forecasts() -> None:
    buyer = _login("aisha@astra.ai")
    response = buyer.get("/api/v1/goals/budget")
    assert response.status_code == 200
    dashboard = response.json()
    assert "restock_forecasts" in dashboard
    forecasts = dashboard["restock_forecasts"]
    assert isinstance(forecasts, list) and forecasts
    first = forecasts[0]
    assert first["avg_interval_days"] > 0
    assert first["predicted_next_date"]
    assert 0 < first["confidence"] <= 100


def _create_order(buyer: TestClient) -> tuple[str, float]:
    deals = buyer.get("/api/v1/deals", params={"page_size": 100}).json()["items"]
    deal = next(item for item in deals if item["price"] <= 50000 and item["stock_remaining"] >= 1)
    reserved = buyer.post(f"/api/v1/deals/{deal['id']}/reserve", json={"quantity": 1}).json()
    order_ref = reserved["order_ref"]
    from app.models.budget import UserBudget

    with SessionLocal() as db:
        user = db.query(User).filter(User.email == "aisha@astra.ai").first()
        budget = db.get(UserBudget, user.id)
        spent_before = budget.current_spent if budget else 0
        if budget:
            budget.current_spent = 0
            db.commit()
    try:
        consent = buyer.post("/api/v1/wallet/authorize-consent", json={
            "amount": deal["price"],
            "auth_method": "Voice",
            "order_ref": order_ref,
            "voice_transcript": f"I authorize payment of Rs. {int(deal['price'])}",
        })
        assert consent.status_code == 200, consent.text
        approved = buyer.post("/api/v1/approval/approve", json={
            "order_ref": order_ref,
            "consent_id": consent.json()["consent_id"],
        })
        assert approved.status_code == 200, approved.text
    finally:
        with SessionLocal() as db:
            user = db.query(User).filter(User.email == "aisha@astra.ai").first()
            budget = db.get(UserBudget, user.id)
            if budget:
                budget.current_spent = spent_before
                db.commit()
    return order_ref, deal["price"]


def _cleanup_order(order_ref: str) -> None:
    from app.models.deal import DealReservation
    from app.models.order import Order
    from app.models.wallet import FinancialConsentLog, WalletTransaction

    with SessionLocal() as db:
        order = db.query(Order).filter(Order.order_ref == order_ref).first()
        if order is None:
            return
        reservation_id = order.reservation_id
        db.query(WalletTransaction).filter(WalletTransaction.reference_order_id == order.id).delete()
        db.query(FinancialConsentLog).filter(FinancialConsentLog.reference_order_id == order.id).delete()
        db.delete(order)
        db.flush()
        if reservation_id:
            db.query(DealReservation).filter(DealReservation.id == reservation_id).delete()
        db.commit()


def test_swarm_log_and_sub_30s_resolution_timeline() -> None:
    buyer = _login("aisha@astra.ai")
    order_ref, price = _create_order(buyer)
    try:
        swarm = buyer.get(f"/api/v1/orders/{order_ref}/swarm")
        assert swarm.status_code == 200
        trace = swarm.json()
        assert trace["order_ref"] == order_ref
        assert {agent["agent"] for agent in trace["agents"]} == {"pricing-agent", "risk-agent", "logistics-agent"}
        assert all(task["end_ms"] > task["start_ms"] for agent in trace["agents"] for task in agent["tasks"])
        assert trace["total_ms"] < 2000

        with SessionLocal() as db:
            user = db.query(User).filter(User.email == "aisha@astra.ai").first()
            balance_before = db.query(UserWallet).filter(UserWallet.user_id == user.id).one().available_balance

        disputed = buyer.post(f"/api/v1/orders/{order_ref}/dispute", json={"reason": "item_not_received"})
        assert disputed.status_code == 200, disputed.text
        result = disputed.json()
        assert result["decision"] == "refunded"
        timeline = result["resolution_timeline"]
        assert timeline["resolved_ms"] < timeline["sla_seconds"] * 1000
        assert [step["phase"] for step in timeline["steps"]] == [
            "Proof Scan", "Risk Evaluation", "Escrow Refunded", "Instant Wallet Credit",
        ]

        replay_timeline = buyer.get(f"/api/v1/orders/{order_ref}/timeline").json()
        assert replay_timeline["escrow_status"] == "REFUNDED"
        assert replay_timeline["resolution_timeline"]["order_ref"] == order_ref

        with SessionLocal() as db:
            user = db.query(User).filter(User.email == "aisha@astra.ai").first()
            wallet = db.query(UserWallet).filter(UserWallet.user_id == user.id).one()
            wallet.available_balance = balance_before
            db.commit()
    finally:
        _cleanup_order(order_ref)


def test_a2a_negotiation_websocket_settles(auth_token: str) -> None:
    with TestClient(app) as client:
        with client.websocket_connect(f"/ws/negotiation/samsung-galaxy-s25-ultra?token={auth_token}") as websocket:
            started = websocket.receive_json()
            assert started["type"] == "a2a_started"
            params = started["params"]
            assert params["buyer_budget"] < params["seller_ask"]
            assert params["delay_threshold_ms"] > 0

            settled = None
            for _ in range(40):
                event = websocket.receive_json()
                if event["type"] == "deal_settled":
                    settled = event
                    break
                assert event["type"] in {"buyer_offer", "seller_counter"}
                assert 0 <= event["progress"] <= 1
            assert settled is not None
            assert settled["final_price"] <= params["seller_ask"]
            assert settled["rounds"] >= 1
            websocket.close()
