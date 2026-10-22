import re
from datetime import datetime, timedelta, timezone

from app.core.database import SessionLocal
from app.core.security import create_access_token
from app.models.budget import UserBudget
from app.models.checkout import CheckoutSession
from app.models.negotiation import NegotiationSession
from app.models.order import Order
from app.models.product import Product
from app.models.user import User
from app.models.wallet import WalletTransaction


def _seller_slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _accepted_offer(auth_client, *, quantity: int = 1) -> tuple[int, float, str]:
    with SessionLocal() as db:
        seller_ids = {_seller_slug(user.name) for user in db.query(User).filter(User.role == "seller").all()}
        products = db.query(Product).filter(
            Product.stock_count >= quantity, Product.listing_status == "active",
        ).order_by(Product.base_price).all()
        product = next((item for item in products if item.base_price > 0 and item.seller_id in seller_ids), None)
        assert product is not None
        slug, unit_cap, seller_id = product.id, round(product.base_price * 0.93, 2), product.seller_id
    response = auth_client.post(f"/api/v1/negotiation/{slug}/offer", json={
        "offer_price": unit_cap, "round": 1, "quantity": quantity,
        "size": "Negotiated size", "color": "Negotiated color", "storage": "Negotiated storage",
    })
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "accepted", response.json()
    return response.json()["session_id"], response.json()["final_price"], seller_id


def _approve_checkout(auth_client, session_id: int):
    approval = auth_client.post(f"/api/v1/negotiation/sessions/{session_id}/approve")
    assert approval.status_code == 200, approval.text
    assert approval.json()["status"] == "buyer_approved"
    checkout = auth_client.post("/api/v1/checkout/session", json={
        "shipping_address": "71 Negotiated Order Road, Lahore",
        "negotiation_session_id": session_id,
    })
    assert checkout.status_code == 201, checkout.text
    return checkout.json()


def test_negotiated_offer_requires_buyer_approval_and_cannot_be_reused(auth_client):
    session_id, unit_price, seller_id = _accepted_offer(auth_client, quantity=2)
    blocked = auth_client.post("/api/v1/checkout/session", json={
        "shipping_address": "71 Negotiated Order Road, Lahore",
        "negotiation_session_id": session_id,
    })
    assert blocked.status_code == 409
    assert "Buyer approval" in blocked.json()["detail"]

    checkout = _approve_checkout(auth_client, session_id)
    expected_total = round(unit_price * 2, 2)
    assert checkout["total"] == expected_total
    duplicate = auth_client.post("/api/v1/checkout/session", json={
        "shipping_address": "71 Negotiated Order Road, Lahore",
        "negotiation_session_id": session_id,
    })
    assert duplicate.status_code == 409
    with SessionLocal() as db:
        orders = db.query(Order).filter(Order.negotiation_session_id == session_id).all()
        assert len(orders) == 1
        assert orders[0].price == expected_total
        assert orders[0].quantity == 2
        order_ref = orders[0].order_ref

    consent = auth_client.post("/api/v1/wallet/authorize-consent", json={
        "amount": expected_total, "auth_method": "Voice", "checkout_ref": checkout["checkout_ref"],
        "voice_transcript": f"I authorize payment of Rs. {int(expected_total)}",
    })
    assert consent.status_code == 200, consent.text
    confirm_url = f"/api/v1/checkout/session/{checkout['checkout_ref']}/confirm"
    completed = auth_client.post(confirm_url, json={"consent_id": consent.json()["consent_id"]})
    assert completed.status_code == 200, completed.text
    assert completed.json()["created"] is True
    replay = auth_client.post(confirm_url, json={"consent_id": consent.json()["consent_id"]})
    assert replay.status_code == 200
    assert replay.json()["created"] is False
    with SessionLocal() as db:
        order = db.query(Order).filter(Order.order_ref == order_ref).one()
        assert db.query(WalletTransaction).filter(
            WalletTransaction.reference_order_id == order.id,
            WalletTransaction.txn_type == "Debit",
        ).count() == 1
        seller = next(
            candidate for candidate in db.query(User).filter(User.role == "seller").all()
            if _seller_slug(candidate.name) == seller_id
        )
        seller_token = create_access_token(str(seller.id))
    buyer_auth = auth_client.headers["Authorization"]
    try:
        auth_client.headers["Authorization"] = f"Bearer {seller_token}"
        visible = auth_client.get("/api/v1/seller/orders")
        assert visible.status_code == 200
        seller_order = next(item for item in visible.json() if item["order_ref"] == order_ref)
        assert seller_order["total"] == expected_total
        assert seller_order["quantity"] == 2
    finally:
        auth_client.headers["Authorization"] = buyer_auth
    auth_client.post(f"/api/v1/orders/{order_ref}/reverse")


def test_negotiated_checkout_consent_rejects_changed_quantity(auth_client):
    session_id, unit_price, _ = _accepted_offer(auth_client, quantity=1)
    checkout = _approve_checkout(auth_client, session_id)
    consent = auth_client.post("/api/v1/wallet/authorize-consent", json={
        "amount": checkout["total"], "auth_method": "Voice", "checkout_ref": checkout["checkout_ref"],
        "voice_transcript": f"I authorize payment of Rs. {int(checkout['total'])}",
    })
    assert consent.status_code == 200, consent.text
    with SessionLocal() as db:
        order = db.query(Order).filter(Order.negotiation_session_id == session_id).one()
        order.quantity += 1
        db.commit()
    rejected = auth_client.post(
        f"/api/v1/checkout/session/{checkout['checkout_ref']}/confirm",
        json={"consent_id": consent.json()["consent_id"]},
    )
    assert rejected.status_code == 409
    assert "CHECKOUT_PRICE_CHANGED" in rejected.json()["detail"]
    assert unit_price > 0


def test_expired_negotiation_and_foreign_buyer_are_rejected(auth_client):
    session_id, _, _ = _accepted_offer(auth_client)
    with SessionLocal() as db:
        negotiation = db.get(NegotiationSession, session_id)
        negotiation.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
    expired = auth_client.post(f"/api/v1/negotiation/sessions/{session_id}/approve")
    assert expired.status_code == 410

    # An accepted negotiation is also private to the authenticated buyer.
    session_id, _, _ = _accepted_offer(auth_client)
    with SessionLocal() as db:
        other = db.query(User).filter(User.email == "hassan@astra.ai").one()
        other_id = other.id
    buyer_auth = auth_client.headers["Authorization"]
    try:
        auth_client.headers["Authorization"] = f"Bearer {create_access_token(str(other_id))}"
        assert auth_client.post(f"/api/v1/negotiation/sessions/{session_id}/approve").status_code == 404
        assert auth_client.post("/api/v1/checkout/session", json={
            "shipping_address": "71 Negotiated Order Road, Lahore",
            "negotiation_session_id": session_id,
        }).status_code == 404
    finally:
        auth_client.headers["Authorization"] = buyer_auth


def test_negotiated_checkout_budget_and_ledger_amount_are_authoritative(auth_client):
    session_id, unit_price, seller_id = _accepted_offer(auth_client)
    approval = auth_client.post(f"/api/v1/negotiation/sessions/{session_id}/approve")
    assert approval.status_code == 200
    with SessionLocal() as db:
        buyer = db.query(User).filter(User.email == "aisha@astra.ai").one()
        buyer_id = buyer.id
        budget = db.query(UserBudget).filter(UserBudget.user_id == buyer.id).one()
        previous = (budget.monthly_limit, budget.current_spent, budget.rollover_savings)
        budget.current_spent = budget.monthly_limit + budget.rollover_savings
        db.commit()
    try:
        blocked = auth_client.post("/api/v1/checkout/session", json={
            "shipping_address": "71 Negotiated Order Road, Lahore",
            "negotiation_session_id": session_id,
        })
        assert blocked.status_code == 409
        assert blocked.json()["detail"] == "MONTHLY_BUDGET_EXCEEDED"
    finally:
        with SessionLocal() as db:
            budget = db.query(UserBudget).filter(UserBudget.user_id == buyer_id).one()
            budget.monthly_limit, budget.current_spent, budget.rollover_savings = previous
            db.commit()

