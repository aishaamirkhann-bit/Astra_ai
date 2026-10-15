from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.database import SessionLocal
from app.main import app
from app.models.cart import CartItem
from app.models.checkout import CheckoutSession
from app.models.order import Order
from app.models.payment import SellerPayoutLedger, StripeCheckoutPayment, StripeWebhookEvent
from app.models.product import Product
from app.models.user import User
from app.services import payment_gateway
from app.services.checkout_fsm import abandon_checkout_session
from app.services.seller_payouts import payout_amounts


def _reset_demo_checkout() -> None:
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == "aisha@astra.ai").one()
        pending = db.query(CheckoutSession).filter(
            CheckoutSession.user_id == user.id,
            CheckoutSession.status == "awaiting_consent",
        ).with_for_update().all()
        for checkout in pending:
            abandon_checkout_session(db, checkout, "test:stripe_checkout_reset")
        db.query(CartItem).filter(CartItem.user_id == user.id).delete(synchronize_session=False)
        db.commit()


def _remove_checkout(checkout_ref: str, product_id: str, quantity: int, variant: str) -> None:
    with SessionLocal() as db:
        checkout = db.query(CheckoutSession).filter(CheckoutSession.checkout_ref == checkout_ref).first()
        user_id = checkout.user_id if checkout else None
        if checkout:
            orders = list(checkout.orders)
            for payout in db.query(SellerPayoutLedger).filter(SellerPayoutLedger.order_id.in_([order.id for order in orders])).all():
                db.delete(payout)
            for order in orders:
                db.delete(order)
            for payment in db.query(StripeCheckoutPayment).filter(StripeCheckoutPayment.checkout_session_id == checkout.id).all():
                db.delete(payment)
            db.delete(checkout)
        product = db.get(Product, product_id)
        if product:
            product.stock_count += quantity
        if user_id:
            db.query(CartItem).filter(
                CartItem.user_id == user_id,
                CartItem.product_id == product_id,
                CartItem.size == variant,
            ).delete(synchronize_session=False)
        db.commit()


def _create_test_checkout(auth_client, monkeypatch) -> tuple[str, str, float, str, str]:
    _reset_demo_checkout()
    variant = f"stripe-{uuid4().hex}"
    stripe_session_id = f"cs_test_{uuid4().hex}"
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == "aisha@astra.ai").one()
        product = db.query(Product).filter(Product.stock_count > 0).first()
        db.add(CartItem(user_id=user.id, product_id=product.id, quantity=1, size=variant, color="", storage=""))
        product_id = product.id
        db.commit()
    monkeypatch.setattr(payment_gateway, "stripe_checkout_configured", lambda: True)
    monkeypatch.setattr(payment_gateway, "create_checkout_session", lambda **kwargs: (stripe_session_id, "https://checkout.stripe.test/session"))
    response = auth_client.post("/api/v1/payments/checkout", json={"shipping_address": "42 Test Checkout Road"})
    assert response.status_code == 200, response.text
    with SessionLocal() as db:
        checkout = db.query(CheckoutSession).filter(CheckoutSession.checkout_ref == response.json()["checkout_ref"]).one()
        return checkout.checkout_ref, product_id, checkout.total, variant, stripe_session_id


def test_checkout_session_uses_cart_amount_metadata_and_idempotency(auth_client, monkeypatch) -> None:
    _reset_demo_checkout()
    calls: list[dict] = []
    variant = f"stripe-{uuid4().hex}"
    stripe_session_id = f"cs_test_{uuid4().hex}"
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == "aisha@astra.ai").one()
        product = db.query(Product).filter(Product.stock_count > 0).first()
        product_id = product.id
        db.add(CartItem(user_id=user.id, product_id=product.id, quantity=1, size=variant, color="", storage=""))
        db.commit()

    monkeypatch.setattr(payment_gateway, "stripe_checkout_configured", lambda: True)
    monkeypatch.setattr(payment_gateway, "create_checkout_session", lambda **kwargs: (calls.append(kwargs) or (stripe_session_id, "https://checkout.stripe.test/session")))
    checkout_ref = ""
    try:
        response = auth_client.post("/api/v1/payments/checkout", json={"shipping_address": "42 Test Checkout Road"})
        assert response.status_code == 200, response.text
        checkout_ref = response.json()["checkout_ref"]
        assert response.json()["checkout_url"] == "https://checkout.stripe.test/session"
        assert calls[0]["metadata"]["checkout_ref"] == checkout_ref
        assert calls[0]["line_items"][0]["quantity"] == 1
        assert calls[0]["idempotency_key"] == f"astra-checkout-{checkout_ref}"
        with SessionLocal() as db:
            payment = db.query(StripeCheckoutPayment).filter(StripeCheckoutPayment.stripe_session_id == stripe_session_id).one()
            assert payment.amount > 0
    finally:
        if checkout_ref:
            with SessionLocal() as db:
                checkout = db.query(CheckoutSession).filter(CheckoutSession.checkout_ref == checkout_ref).one()
                quantity = sum(order.quantity for order in checkout.orders)
            _remove_checkout(checkout_ref, product_id, quantity, variant)


def test_payment_gateway_creates_checkout_with_mocked_stripe_sdk(monkeypatch) -> None:
    calls: list[dict] = []

    class MockStripeCheckoutSessions:
        def create(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(id="cs_sdk_mock", url="https://checkout.stripe.test/sdk")

    monkeypatch.setattr(
        payment_gateway,
        "_client",
        lambda: SimpleNamespace(checkout=SimpleNamespace(sessions=MockStripeCheckoutSessions())),
    )
    result = payment_gateway.create_checkout_session(
        line_items=[{"price_data": {"currency": "pkr"}, "quantity": 1}],
        metadata={"order_id": "42"},
        success_url="https://astra.test/success",
        cancel_url="https://astra.test/cancel",
        expires_at=1_900_000_000,
        idempotency_key="astra-test-42",
    )
    assert result == ("cs_sdk_mock", "https://checkout.stripe.test/sdk")
    assert calls[0]["mode"] == "payment"
    assert calls[0]["metadata"] == {"order_id": "42"}
    assert calls[0]["options"] == {"idempotency_key": "astra-test-42"}


def test_order_webhook_signature_failure_returns_400(auth_client, monkeypatch) -> None:
    monkeypatch.setattr(payment_gateway, "stripe_checkout_configured", lambda: True)
    monkeypatch.setattr(payment_gateway, "construct_webhook_event", lambda *_: (_ for _ in ()).throw(ValueError("bad signature")))
    response = auth_client.post("/webhooks/stripe", content=b"{}", headers={"stripe-signature": "invalid"})
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid webhook signature"


def test_order_webhook_settles_once_and_records_net_payout(auth_client, monkeypatch) -> None:
    checkout_ref, product_id, total, variant, stripe_session_id = _create_test_checkout(auth_client, monkeypatch)
    event_id = f"evt_test_{uuid4().hex}"
    event = {
        "id": event_id,
        "type": "checkout.session.completed",
        "data": {"object": {
            "id": stripe_session_id,
            "payment_status": "paid",
            "amount_total": int(round(total * 100)),
            "payment_intent": "pi_test_paid",
        }},
    }
    monkeypatch.setattr(payment_gateway, "construct_webhook_event", lambda *_: event)
    refunds: list[tuple[str, int, int]] = []
    monkeypatch.setattr(
        payment_gateway,
        "refund_payment_intent",
        lambda payment_intent_id, order_id, amount: refunds.append((payment_intent_id, order_id, amount)) or "re_test_refund",
    )
    try:
        first = auth_client.post("/webhooks/stripe", content=b"{}", headers={"stripe-signature": "test"})
        duplicate = auth_client.post("/webhooks/stripe", content=b"{}", headers={"stripe-signature": "test"})
        assert first.status_code == 200, first.text
        assert duplicate.status_code == 200 and duplicate.json()["duplicate"] is True
        with SessionLocal() as db:
            checkout = db.query(CheckoutSession).filter(CheckoutSession.checkout_ref == checkout_ref).one()
            payment = db.query(StripeCheckoutPayment).filter(StripeCheckoutPayment.checkout_session_id == checkout.id).one()
            assert checkout.status == "reversal_window_open"
            assert payment.status == "paid"
            assert all(order.status.value == "reversal_window_open" for order in checkout.orders)
            assert db.get(StripeWebhookEvent, event_id) is not None
            payout = db.query(SellerPayoutLedger).filter(SellerPayoutLedger.order_id == checkout.orders[0].id).one()
            assert payout.gross_amount == pytest.approx(total)
            assert payout.platform_fee == pytest.approx(total * settings.PLATFORM_FEE_PERCENT / 100)
            assert payout.seller_amount + payout.platform_fee == pytest.approx(total)
            order_ref = checkout.orders[0].order_ref
            order_id = checkout.orders[0].id
            quantity = sum(order.quantity for order in checkout.orders)
        reversed_order = auth_client.post(f"/api/v1/orders/{order_ref}/reverse")
        assert reversed_order.status_code == 200, reversed_order.text
        assert refunds == [("pi_test_paid", order_id, int(round(total * 100)))]
        with SessionLocal() as db:
            payment = db.query(StripeCheckoutPayment).filter(StripeCheckoutPayment.stripe_session_id == stripe_session_id).one()
            assert payment.status == "refunded"
        _remove_checkout(checkout_ref, product_id, quantity, variant)
    finally:
        with SessionLocal() as db:
            db.query(StripeWebhookEvent).filter(StripeWebhookEvent.event_id == event_id).delete()
            db.commit()


def test_order_checkout_returns_clear_503_when_unconfigured(auth_client, monkeypatch) -> None:
    monkeypatch.setattr(payment_gateway, "stripe_checkout_configured", lambda: False)
    response = auth_client.post("/api/v1/payments/checkout", json={"shipping_address": "42 Test Checkout Road"})
    assert response.status_code == 503
    assert response.json()["detail"] == "Payments not configured"


def test_cancel_does_not_release_reservation_for_paid_stripe_session(auth_client, monkeypatch) -> None:
    checkout_ref, product_id, _, variant, _ = _create_test_checkout(auth_client, monkeypatch)
    monkeypatch.setattr(payment_gateway, "retrieve_checkout_session", lambda _: {
        "status": "complete",
        "payment_status": "paid",
        "payment_intent": "pi_cancel_race",
    })
    try:
        response = auth_client.post(f"/api/v1/payments/checkout/{checkout_ref}/cancel")
        assert response.status_code == 200, response.text
        assert response.json()["payment_status"] == "paid_webhook_pending"
        with SessionLocal() as db:
            checkout = db.query(CheckoutSession).filter(CheckoutSession.checkout_ref == checkout_ref).one()
            payment = db.query(StripeCheckoutPayment).filter(StripeCheckoutPayment.checkout_session_id == checkout.id).one()
            assert checkout.status == "awaiting_consent"
            assert payment.status == "paid_webhook_pending"
            quantity = sum(order.quantity for order in checkout.orders)
    finally:
        _remove_checkout(checkout_ref, product_id, quantity, variant)


def test_payout_calculation_applies_configured_platform_fee() -> None:
    fee, seller_amount = payout_amounts(1000, 12.5)
    assert fee == 125
    assert seller_amount == 875