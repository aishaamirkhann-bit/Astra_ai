from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.core.security import create_access_token
from app.models.cart import CartItem
from app.models.checkout import CheckoutSession
from app.models.order import Order, OrderStatus
from app.models.product import Product
from app.models.user import User
from app.models.wallet import FinancialConsentLog, UserWallet, WalletTransaction
from app.main import app


ADDRESS = "42 Consent Test Road, Lahore"
DEMO_EMAIL = "aisha@astra.ai"


def _reset(auth_client):
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == DEMO_EMAIL).one()
        sessions = db.query(CheckoutSession).filter(
            CheckoutSession.user_id == user.id,
            CheckoutSession.shipping_address == ADDRESS,
        ).all()
        for session in sessions:
            orders = list(session.orders)
            for order in orders:
                product = db.get(Product, order.product_id)
                if product:
                    product.stock_count += order.quantity
                db.query(WalletTransaction).filter(
                    WalletTransaction.reference_order_id == order.id
                ).delete(synchronize_session=False)
                db.query(FinancialConsentLog).filter(
                    FinancialConsentLog.reference_order_id == order.id
                ).delete(synchronize_session=False)
                db.delete(order)
            db.query(FinancialConsentLog).filter(
                FinancialConsentLog.reference_checkout_id == session.id
            ).delete(synchronize_session=False)
            db.delete(session)
        db.query(CartItem).filter(CartItem.user_id == user.id).delete(synchronize_session=False)
        db.commit()


def _product(auth_client):
    items = auth_client.get("/api/v1/deals", params={"page_size": 100}).json()["items"]
    return next(item for item in items if item["stock_remaining"] > 0 and item["price"] < 50_000)


def _start_checkout(auth_client):
    product = _product(auth_client)
    added = auth_client.post("/api/v1/cart/add", json={
        "product_slug": product["slug"], "quantity": 1, "size": "Consent test", "color": "Black",
    })
    assert added.status_code == 200
    response = auth_client.post("/api/v1/checkout/session", json={"shipping_address": ADDRESS})
    assert response.status_code == 201, response.text
    return response.json(), product


def _voice_consent(auth_client, session):
    response = auth_client.post("/api/v1/wallet/authorize-consent", json={
        "amount": session["total"], "auth_method": "Voice",
        "checkout_ref": session["checkout_ref"],
        "voice_transcript": f"I authorize payment of Rs. {int(session['total'])}",
    })
    assert response.status_code == 200, response.text
    return response.json()["consent_id"]


def test_checkout_requires_valid_snapshot_bound_single_use_consent(auth_client):
    _reset(auth_client)
    session, _ = _start_checkout(auth_client)
    try:
        confirm_url = f"/api/v1/checkout/session/{session['checkout_ref']}/confirm"
        assert auth_client.post(confirm_url, json={}).status_code == 428

        consent_id = _voice_consent(auth_client, session)
        # Changing the destination after approval revokes that consent.
        changed = auth_client.post("/api/v1/checkout/session", json={"shipping_address": "9 New Address, Lahore"})
        assert changed.status_code == 201
        rejected = auth_client.post(confirm_url, json={"consent_id": consent_id})
        assert rejected.status_code == 428

        fresh_consent = _voice_consent(auth_client, changed.json())
        with SessionLocal() as db:
            order = db.query(Order).filter(Order.checkout_session_id == db.query(CheckoutSession).filter(
                CheckoutSession.checkout_ref == session["checkout_ref"]
            ).one().id).one()
            order.color = "Tampered"
            db.commit()
        tampered = auth_client.post(confirm_url, json={"consent_id": fresh_consent})
        assert tampered.status_code == 409
        assert "CHECKOUT_DETAILS_CHANGED" in tampered.json()["detail"]

        # Recreate a fresh server priced checkout, approve and verify debit is idempotent.
        _reset(auth_client)
        refreshed_session, _ = _start_checkout(auth_client)
        approved_consent = _voice_consent(auth_client, refreshed_session)
        wallet_before = auth_client.get("/api/v1/wallet").json()["available_balance"]
        success = auth_client.post(
            f"/api/v1/checkout/session/{refreshed_session['checkout_ref']}/confirm",
            json={"consent_id": approved_consent},
        )
        assert success.status_code == 200, success.text
        assert success.json()["created"] is True
        replay = auth_client.post(
            f"/api/v1/checkout/session/{refreshed_session['checkout_ref']}/confirm",
            json={"consent_id": approved_consent},
        )
        assert replay.status_code == 200
        assert replay.json()["created"] is False
        assert auth_client.get("/api/v1/wallet").json()["available_balance"] == wallet_before - refreshed_session["total"]
        with SessionLocal() as db:
            checkout = db.query(CheckoutSession).filter(
                CheckoutSession.checkout_ref == refreshed_session["checkout_ref"]
            ).one()
            orders = list(checkout.orders)
            assert all(order.status == OrderStatus.REVERSAL_WINDOW_OPEN for order in orders)
            assert db.query(WalletTransaction).filter(
                WalletTransaction.reference_order_id.in_([order.id for order in orders]),
                WalletTransaction.txn_type == "Debit",
            ).count() == len(orders)
            assert db.query(FinancialConsentLog).filter(
                FinancialConsentLog.consent_id == approved_consent,
                FinancialConsentLog.consumed_at.is_not(None),
            ).count() == 1
    finally:
        with SessionLocal() as db:
            user = db.query(User).filter(User.email == DEMO_EMAIL).one()
            sessions = db.query(CheckoutSession).filter(
                CheckoutSession.user_id == user.id,
                CheckoutSession.status.in_(["awaiting_consent", "reversal_window_open"]),
            ).all()
            refs = [order.order_ref for session in sessions for order in session.orders]
        for ref in refs:
            auth_client.post(f"/api/v1/orders/{ref}/reverse")
        _reset(auth_client)


def test_expired_consent_cannot_confirm_checkout(auth_client):
    _reset(auth_client)
    session, _ = _start_checkout(auth_client)
    try:
        consent_id = _voice_consent(auth_client, session)
        with SessionLocal() as db:
            consent = db.query(FinancialConsentLog).filter(FinancialConsentLog.consent_id == consent_id).one()
            consent.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            db.commit()
        response = auth_client.post(
            f"/api/v1/checkout/session/{session['checkout_ref']}/confirm",
            json={"consent_id": consent_id},
        )
        assert response.status_code == 428
    finally:
        _reset(auth_client)


def test_another_buyer_cannot_read_or_confirm_checkout(auth_client):
    _reset(auth_client)
    session, _ = _start_checkout(auth_client)
    email = f"checkout-owner-{uuid4().hex}@example.test"
    other_id = None
    try:
        with SessionLocal() as db:
            other = User(name="Other Buyer", email=email, hashed_password="unused", role="buyer", is_active=True)
            db.add(other)
            db.flush()
            other_id = other.id
            token = create_access_token(str(other.id))
            db.commit()
        with TestClient(app, headers={"Authorization": f"Bearer {token}"}) as other_client:
            assert other_client.get(f"/api/v1/checkout/session/{session['checkout_ref']}").status_code == 404
            assert other_client.post(
                f"/api/v1/checkout/session/{session['checkout_ref']}/confirm", json={}
            ).status_code == 404
    finally:
        _reset(auth_client)
        if other_id:
            with SessionLocal() as db:
                db.query(User).filter(User.id == other_id).delete(synchronize_session=False)
                db.commit()


def test_concurrent_checkout_confirms_settle_only_once(auth_client):
    _reset(auth_client)
    session, _ = _start_checkout(auth_client)
    try:
        consent_id = _voice_consent(auth_client, session)
        url = f"/api/v1/checkout/session/{session['checkout_ref']}/confirm"
        headers = {"Authorization": auth_client.headers["Authorization"]}

        def confirm():
            with TestClient(app, headers=headers) as client:
                return client.post(url, json={"consent_id": consent_id})

        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(lambda _: confirm(), range(2)))
        assert all(response.status_code in {200, 409} for response in responses), [
            (response.status_code, response.text) for response in responses
        ]
        completed = [response for response in responses if response.status_code == 200 and response.json()["created"]]
        assert len(completed) == 1
        with SessionLocal() as db:
            checkout = db.query(CheckoutSession).filter(
                CheckoutSession.checkout_ref == session["checkout_ref"]
            ).one()
            orders = list(checkout.orders)
            assert db.query(WalletTransaction).filter(
                WalletTransaction.reference_order_id.in_([order.id for order in orders]),
                WalletTransaction.txn_type == "Debit",
            ).count() == len(orders)
    finally:
        _reset(auth_client)
