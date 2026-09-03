"""Pitch-feature coverage: password reset, negotiation, authenticity, escrow timeline, AI dispute, metrics."""
from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.main import app
from app.models.user import User
from app.models.wallet import UserWallet
from app.models.negotiation import NegotiationRound, NegotiationSession


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


def test_forgot_and_reset_password_flow() -> None:
    anonymous = TestClient(app)
    requested = anonymous.post("/api/v1/auth/forgot-password", json={"email": "aisha@astra.ai"})
    assert requested.status_code == 200
    # Enumeration safety: unknown emails get the same shape/response code.
    unknown = anonymous.post("/api/v1/auth/forgot-password", json={"email": "nobody@astra.ai"})
    assert unknown.status_code == 200

    wrong = anonymous.post("/api/v1/auth/reset-password", json={"email": "aisha@astra.ai", "code": "000000", "new_password": "demo1234"})
    assert wrong.status_code == 400

    reset = anonymous.post("/api/v1/auth/reset-password", json={"email": "aisha@astra.ai", "code": "123456", "new_password": "demo1234"})
    assert reset.status_code == 200
    # Login still works with the (unchanged) password after reset.
    again = anonymous.post("/api/v1/auth/login", json={"email": "aisha@astra.ai", "password": "demo1234"})
    assert again.status_code == 200


def test_negotiation_counters_then_accepts() -> None:
    buyer = _login("aisha@astra.ai")
    first = buyer.post("/api/v1/negotiation/samsung-galaxy-s25-ultra/offer", json={"offer_price": 100000, "round": 1})
    assert first.status_code == 200
    body = first.json()
    assert body["status"] == "counter"
    assert body["counter_offer"] is not None
    assert body["market_average"] > 0
    assert body["reasoning"]

    accepted = buyer.post("/api/v1/negotiation/samsung-galaxy-s25-ultra/offer", json={
        "offer_price": body["seller_ask"], "round": 2, "session_id": body["session_id"],
    })
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "accepted"
    assert accepted.json()["final_price"] == body["seller_ask"]
    with SessionLocal() as db:
        session = db.get(NegotiationSession, body["session_id"])
        assert session is not None
        assert session.status == "accepted"
        assert db.query(NegotiationRound).filter(NegotiationRound.session_id == session.id).count() == 2


def test_authenticity_audit_returns_hash_and_checks() -> None:
    buyer = _login("aisha@astra.ai")
    response = buyer.get("/api/v1/products/samsung-galaxy-s25-ultra/authenticity")
    assert response.status_code == 200
    audit = response.json()
    assert len(audit["listing_hash"]) == 64
    assert audit["risk_band"] in {"low", "medium", "high"}
    assert {check["id"] for check in audit["checks"]} >= {"listing_hash", "seller_identity", "review_sentiment", "price_stability"}


def test_timeline_and_ai_dispute_refund_flow() -> None:
    buyer = _login("aisha@astra.ai")
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

    timeline = buyer.get(f"/api/v1/orders/{order_ref}/timeline")
    assert timeline.status_code == 200
    payload = timeline.json()
    assert payload["escrow_status"] == "HELD"
    assert payload["stages"] and payload["reasoning"]

    with SessionLocal() as db:
        user = db.query(User).filter(User.email == "aisha@astra.ai").first()
        balance_before = db.query(UserWallet).filter(UserWallet.user_id == user.id).one().available_balance

    disputed = buyer.post(f"/api/v1/orders/{order_ref}/dispute", json={"reason": "item_not_received"})
    assert disputed.status_code == 200, disputed.text
    result = disputed.json()
    assert result["decision"] == "refunded"
    assert result["escrow_status"] == "REFUNDED"
    assert result["risk_score"] >= 50

    with SessionLocal() as db:
        user = db.query(User).filter(User.email == "aisha@astra.ai").first()
        wallet = db.query(UserWallet).filter(UserWallet.user_id == user.id).one()
        assert wallet.available_balance == balance_before + deal["price"]
        wallet.available_balance = balance_before
        db.commit()

    replay = buyer.post(f"/api/v1/orders/{order_ref}/dispute", json={"reason": "item_damaged"})
    assert replay.status_code == 409

    # Cleanup the demo order + reservation like the deals tests do.
    from app.models.deal import DealReservation
    from app.models.order import Order
    from app.models.wallet import WalletTransaction, FinancialConsentLog
    with SessionLocal() as db:
        order = db.query(Order).filter(Order.order_ref == order_ref).first()
        reservation_id = order.reservation_id
        db.query(WalletTransaction).filter(WalletTransaction.reference_order_id == order.id).delete()
        db.query(FinancialConsentLog).filter(FinancialConsentLog.reference_order_id == order.id).delete()
        db.delete(order)
        db.flush()
        if reservation_id:
            db.query(DealReservation).filter(DealReservation.id == reservation_id).delete()
        db.commit()


def test_metrics_reports_db_and_latency() -> None:
    anonymous = TestClient(app)
    anonymous.get("/api/v1/home")
    response = anonymous.get("/metrics")
    assert response.status_code == 200
    metrics = response.json()
    assert metrics["database"]["connected"] is True
    assert metrics["uptime_seconds"] >= 0
    assert "p95" in metrics["requests"]["latency_ms"]
    health = anonymous.get("/health")
    assert health.json() == {"status": "ok", "db": "connected"}
