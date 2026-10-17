from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.database import SessionLocal
from app.main import app
from app.models.cart import CartItem
from app.models.checkout import CheckoutSession
from app.models.order import Order, OrderStatus
from app.models.payment import SellerPayoutLedger, StripeCheckoutPayment, StripeConnectAccount, StripeRefund, StripeWebhookEvent
from app.models.product import Product
from app.models.seller_profile import SellerProfile
from app.models.user import User
from app.models.wallet import FinancialConsentLog
from app.services import payment_gateway, stripe_checkout
from app.services.checkout_fsm import abandon_checkout_session, expire_checkout_sessions, release_checkout_session
from app.services.seller_payouts import (
    payout_amounts,
    process_order_payout,
    record_order_payouts,
    start_connect_onboarding,
)
from app.utils.helpers import as_aware_utc


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
            for order in orders:
                if order.status.value != "cancelled":
                    product = db.get(Product, order.product_id)
                    if product:
                        product.stock_count += order.quantity
            for payout in db.query(SellerPayoutLedger).filter(SellerPayoutLedger.order_id.in_([order.id for order in orders])).all():
                db.delete(payout)
            for order in orders:
                db.delete(order)
            for payment in db.query(StripeCheckoutPayment).filter(StripeCheckoutPayment.checkout_session_id == checkout.id).all():
                db.delete(payment)
            db.delete(checkout)
        product = db.get(Product, product_id)
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
    checkout_response = auth_client.post("/api/v1/checkout/session", json={"shipping_address": "42 Test Checkout Road"})
    assert checkout_response.status_code == 201, checkout_response.text
    checkout_ref = checkout_response.json()["checkout_ref"]
    total = checkout_response.json()["total"]
    consent = auth_client.post("/api/v1/wallet/authorize-consent", json={
        "amount": total,
        "auth_method": "Voice",
        "voice_transcript": f"I authorize payment of Rs. {int(total)}",
        "checkout_ref": checkout_ref,
    })
    assert consent.status_code == 200, consent.text
    consent_id = consent.json()["consent_id"]
    monkeypatch.setattr(payment_gateway, "stripe_checkout_configured", lambda: True)
    monkeypatch.setattr(payment_gateway, "create_checkout_session", lambda **kwargs: (stripe_session_id, "https://checkout.stripe.test/session"))
    response = auth_client.post("/api/v1/payments/checkout", json={
        "shipping_address": "42 Test Checkout Road",
        "checkout_ref": checkout_ref,
        "consent_id": consent_id,
    })
    assert response.status_code == 200, response.text
    with SessionLocal() as db:
        checkout = db.query(CheckoutSession).filter(CheckoutSession.checkout_ref == checkout_ref).one()
        assert db.get(FinancialConsentLog, consent_id).consumed_at is not None
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

    checkout_response = auth_client.post("/api/v1/checkout/session", json={"shipping_address": "42 Test Checkout Road"})
    assert checkout_response.status_code == 201, checkout_response.text
    checkout_ref = checkout_response.json()["checkout_ref"]
    total = checkout_response.json()["total"]
    consent = auth_client.post("/api/v1/wallet/authorize-consent", json={
        "amount": total,
        "auth_method": "Voice",
        "voice_transcript": f"I authorize payment of Rs. {int(total)}",
        "checkout_ref": checkout_ref,
    })
    assert consent.status_code == 200, consent.text
    consent_id = consent.json()["consent_id"]

    monkeypatch.setattr(payment_gateway, "stripe_checkout_configured", lambda: True)
    monkeypatch.setattr(payment_gateway, "create_checkout_session", lambda **kwargs: (calls.append(kwargs) or (stripe_session_id, "https://checkout.stripe.test/session")))
    try:
        response = auth_client.post("/api/v1/payments/checkout", json={
            "shipping_address": "42 Test Checkout Road",
            "checkout_ref": checkout_ref,
            "consent_id": consent_id,
        })
        assert response.status_code == 200, response.text
        checkout_ref = response.json()["checkout_ref"]
        assert response.json()["checkout_url"] == "https://checkout.stripe.test/session"
        assert calls[0]["metadata"]["checkout_ref"] == checkout_ref
        assert calls[0]["line_items"][0]["quantity"] == 1
        assert calls[0]["idempotency_key"] == f"astra-checkout-{checkout_ref}"
        with SessionLocal() as db:
            payment = db.query(StripeCheckoutPayment).filter(StripeCheckoutPayment.stripe_session_id == stripe_session_id).one()
            assert payment.amount > 0
            assert db.get(FinancialConsentLog, consent_id).consumed_at is not None
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
    paid_at = datetime.now(timezone.utc)
    monkeypatch.setattr(stripe_checkout, "_now", lambda: paid_at)
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
            assert as_aware_utc(payment.paid_at) == paid_at
            assert as_aware_utc(checkout.orders[0].reversal_deadline) == paid_at + timedelta(
                seconds=settings.APPROVAL_WINDOW_SECONDS
            )
            assert db.get(StripeWebhookEvent, event_id) is not None
            payout = db.query(SellerPayoutLedger).filter(SellerPayoutLedger.order_id == checkout.orders[0].id).one()
            assert payout.gross_amount == pytest.approx(total)
            assert payout.platform_fee == pytest.approx(total * settings.PLATFORM_FEE_PERCENT / 100)
            assert payout.seller_amount + payout.platform_fee == pytest.approx(total)
            order_ref = checkout.orders[0].order_ref
            order_id = checkout.orders[0].id
            quantity = sum(order.quantity for order in checkout.orders)
        status = auth_client.get(f"/api/v1/payments/checkout/by-session/{stripe_session_id}")
        assert status.status_code == 200 and status.json()["stripe_session_id"] == stripe_session_id
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
    response = auth_client.post("/api/v1/payments/checkout", json={
        "shipping_address": "42 Test Checkout Road",
        "checkout_ref": "CHK-TEST-00000001",
        "consent_id": "unused-test-consent",
    })
    assert response.status_code == 503
    assert response.json()["detail"] == "Payments not configured"


def test_cancel_does_not_release_reservation_for_paid_stripe_session(auth_client, monkeypatch) -> None:
    checkout_ref, product_id, total, variant, _ = _create_test_checkout(auth_client, monkeypatch)
    monkeypatch.setattr(payment_gateway, "retrieve_checkout_session", lambda _: {
        "status": "complete",
        "payment_status": "paid",
        "amount_total": int(round(total * 100)),
        "payment_intent": "pi_cancel_race",
    })
    try:
        response = auth_client.post(f"/api/v1/payments/checkout/{checkout_ref}/cancel")
        assert response.status_code == 200, response.text
        assert response.json()["payment_status"] == "paid"
        with SessionLocal() as db:
            checkout = db.query(CheckoutSession).filter(CheckoutSession.checkout_ref == checkout_ref).one()
            payment = db.query(StripeCheckoutPayment).filter(StripeCheckoutPayment.checkout_session_id == checkout.id).one()
            assert checkout.status == "reversal_window_open"
            assert payment.status == "paid"
            assert all(order.status.value == "reversal_window_open" for order in checkout.orders)
            quantity = sum(order.quantity for order in checkout.orders)
    finally:
        _remove_checkout(checkout_ref, product_id, quantity, variant)


def test_payout_calculation_applies_configured_platform_fee() -> None:
    fee, seller_amount = payout_amounts(1000, 12.5)
    assert fee == 125
    assert seller_amount == 875


@pytest.mark.parametrize(
    ("event_type", "payment_status", "checkout_status"),
    [
        ("checkout.session.expired", "expired", "expired"),
        ("checkout.session.async_payment_failed", "failed", "cancelled"),
        ("payment_intent.payment_failed", "failed", "cancelled"),
    ],
)
def test_failed_and_expired_webhooks_release_checkout(
    auth_client, monkeypatch, event_type: str, payment_status: str, checkout_status: str,
) -> None:
    checkout_ref, product_id, _, variant, stripe_session_id = _create_test_checkout(auth_client, monkeypatch)
    event_id = f"evt_failure_{uuid4().hex}"
    with SessionLocal() as db:
        checkout = db.query(CheckoutSession).filter(CheckoutSession.checkout_ref == checkout_ref).one()
        checkout_id = checkout.id
        order_ref = checkout.orders[0].order_ref
    if event_type == "payment_intent.payment_failed":
        stripe_object = {
            "id": f"pi_failed_{uuid4().hex}",
            "metadata": {"checkout_session_id": str(checkout_id)},
        }
    else:
        stripe_object = {
            "id": stripe_session_id,
            "status": "expired" if event_type == "checkout.session.expired" else "complete",
            "payment_status": "unpaid",
        }
    event = {"id": event_id, "type": event_type, "data": {"object": stripe_object}}
    monkeypatch.setattr(payment_gateway, "construct_webhook_event", lambda *_: event)
    try:
        response = auth_client.post("/webhooks/stripe", content=b"{}", headers={"stripe-signature": "test"})
        assert response.status_code == 200, response.text
        with SessionLocal() as db:
            checkout = db.query(CheckoutSession).filter(CheckoutSession.checkout_ref == checkout_ref).one()
            payment = db.query(StripeCheckoutPayment).filter(StripeCheckoutPayment.stripe_session_id == stripe_session_id).one()
            order = db.query(Order).filter(Order.order_ref == order_ref).one()
            cart_item = db.query(CartItem).filter(
                CartItem.user_id == checkout.user_id,
                CartItem.product_id == product_id,
                CartItem.size == variant,
            ).first()
            assert checkout.status == checkout_status
            assert payment.status == payment_status
            assert order.status.value == "cancelled"
            assert cart_item is not None and cart_item.quantity == 1
    finally:
        with SessionLocal() as db:
            db.query(StripeWebhookEvent).filter(StripeWebhookEvent.event_id == event_id).delete()
            db.commit()
        _remove_checkout(checkout_ref, product_id, 1, variant)


def test_async_payment_succeeded_settles_checkout(auth_client, monkeypatch) -> None:
    checkout_ref, product_id, total, variant, stripe_session_id = _create_test_checkout(auth_client, monkeypatch)
    event_id = f"evt_async_paid_{uuid4().hex}"
    event = {"id": event_id, "type": "checkout.session.async_payment_succeeded", "data": {"object": {
        "id": stripe_session_id,
        "payment_status": "paid",
        "amount_total": int(round(total * 100)),
        "payment_intent": f"pi_async_{uuid4().hex}",
    }}}
    monkeypatch.setattr(payment_gateway, "construct_webhook_event", lambda *_: event)
    try:
        response = auth_client.post("/webhooks/stripe", content=b"{}", headers={"stripe-signature": "test"})
        assert response.status_code == 200, response.text
        with SessionLocal() as db:
            checkout = db.query(CheckoutSession).filter(CheckoutSession.checkout_ref == checkout_ref).one()
            payment = db.query(StripeCheckoutPayment).filter(StripeCheckoutPayment.stripe_session_id == stripe_session_id).one()
            assert checkout.status == "reversal_window_open"
            assert payment.status == "paid"
    finally:
        with SessionLocal() as db:
            db.query(StripeWebhookEvent).filter(StripeWebhookEvent.event_id == event_id).delete()
            db.commit()
        _remove_checkout(checkout_ref, product_id, 1, variant)


@pytest.mark.parametrize("event_type", ["refund.updated", "charge.refunded"])
def test_refund_webhooks_reconcile_stored_status(auth_client, monkeypatch, event_type: str) -> None:
    checkout_ref, product_id, total, variant, stripe_session_id = _create_test_checkout(auth_client, monkeypatch)
    paid_event_id = f"evt_paid_for_refund_{uuid4().hex}"
    refund_event_id = f"evt_refund_{uuid4().hex}"
    payment_intent_id = f"pi_refund_{uuid4().hex}"
    current_event = {"event": {
        "id": paid_event_id,
        "type": "checkout.session.completed",
        "data": {"object": {
            "id": stripe_session_id,
            "payment_status": "paid",
            "amount_total": int(round(total * 100)),
            "payment_intent": payment_intent_id,
        }},
    }}
    monkeypatch.setattr(payment_gateway, "construct_webhook_event", lambda *_: current_event["event"])
    try:
        paid = auth_client.post("/webhooks/stripe", content=b"{}", headers={"stripe-signature": "test"})
        assert paid.status_code == 200, paid.text
        with SessionLocal() as db:
            payment = db.query(StripeCheckoutPayment).filter(StripeCheckoutPayment.stripe_session_id == stripe_session_id).one()
            order_id = db.query(Order.id).filter(Order.checkout_session_id == payment.checkout_session_id).scalar()
            db.add(StripeRefund(
                refund_id=f"re_test_{checkout_ref}",
                stripe_checkout_payment_id=payment.id,
                order_id=order_id,
                amount_paisa=int(round(total * 100)),
                status="requested",
            ))
            db.commit()
        refund_obj = {
            "id": f"re_test_{checkout_ref}",
            "payment_intent": payment_intent_id,
            "amount": int(round(total * 100)),
            "status": "succeeded",
        }
        if event_type == "refund.updated":
            current_event["event"] = {"id": refund_event_id, "type": event_type, "data": {"object": refund_obj}}
        else:
            current_event["event"] = {"id": refund_event_id, "type": event_type, "data": {"object": {
                "id": f"ch_test_{uuid4().hex}",
                "payment_intent": payment_intent_id,
                "amount_refunded": int(round(total * 100)),
                "refunds": {"data": [refund_obj]},
            }}}
        response = auth_client.post("/webhooks/stripe", content=b"{}", headers={"stripe-signature": "test"})
        assert response.status_code == 200, response.text
        with SessionLocal() as db:
            payment = db.query(StripeCheckoutPayment).filter(StripeCheckoutPayment.stripe_session_id == stripe_session_id).one()
            refund = db.get(StripeRefund, refund_obj["id"])
            assert refund is not None and refund.status == "succeeded"
            assert payment.status == "refunded"
    finally:
        with SessionLocal() as db:
            db.query(StripeWebhookEvent).filter(StripeWebhookEvent.event_id.in_([paid_event_id, refund_event_id])).delete(synchronize_session=False)
            db.commit()
        _remove_checkout(checkout_ref, product_id, 1, variant)


def test_late_paid_checkout_requests_checkout_keyed_refund(auth_client, monkeypatch) -> None:
    checkout_ref, product_id, total, variant, stripe_session_id = _create_test_checkout(auth_client, monkeypatch)
    event_id = f"evt_late_paid_{uuid4().hex}"
    with SessionLocal() as db:
        checkout = db.query(CheckoutSession).filter(CheckoutSession.checkout_ref == checkout_ref).one()
        release_checkout_session(db, checkout, "expired")
        payment = db.query(StripeCheckoutPayment).filter(StripeCheckoutPayment.checkout_session_id == checkout.id).one()
        payment.status = "expired"
        db.commit()
    refund_calls: list[dict] = []
    monkeypatch.setattr(
        payment_gateway,
        "refund_payment_intent",
        lambda payment_intent_id, order_id, amount_paisa, **kwargs: (
            refund_calls.append({"payment_intent_id": payment_intent_id, "order_id": order_id, "amount_paisa": amount_paisa, **kwargs})
            or "re_late_refund"
        ),
    )
    event = {"id": event_id, "type": "checkout.session.completed", "data": {"object": {
        "id": stripe_session_id,
        "payment_status": "paid",
        "amount_total": int(round(total * 100)),
        "payment_intent": "pi_late_paid",
    }}}
    monkeypatch.setattr(payment_gateway, "construct_webhook_event", lambda *_: event)
    try:
        response = auth_client.post("/webhooks/stripe", content=b"{}", headers={"stripe-signature": "test"})
        assert response.status_code == 200, response.text
        assert refund_calls == [{
            "payment_intent_id": "pi_late_paid",
            "order_id": None,
            "amount_paisa": int(round(total * 100)),
            "idempotency_key": checkout_ref,
            "checkout_ref": checkout_ref,
        }]
        with SessionLocal() as db:
            payment = db.query(StripeCheckoutPayment).filter(StripeCheckoutPayment.stripe_session_id == stripe_session_id).one()
            refund = db.get(StripeRefund, "re_late_refund")
            assert payment.status == "refund_pending"
            assert refund is not None and refund.amount_paisa == int(round(total * 100))
    finally:
        with SessionLocal() as db:
            db.query(StripeWebhookEvent).filter(StripeWebhookEvent.event_id == event_id).delete()
            db.commit()
        _remove_checkout(checkout_ref, product_id, 1, variant)


def test_expiry_monitor_settles_stripe_session_that_is_already_paid(auth_client, monkeypatch) -> None:
    checkout_ref, product_id, total, variant, stripe_session_id = _create_test_checkout(auth_client, monkeypatch)
    monkeypatch.setattr(payment_gateway, "retrieve_checkout_session", lambda _: {
        "id": stripe_session_id,
        "status": "complete",
        "payment_status": "paid",
        "amount_total": int(round(total * 100)),
        "payment_intent": "pi_expiry_race",
    })
    try:
        with SessionLocal() as db:
            checkout = db.query(CheckoutSession).filter(CheckoutSession.checkout_ref == checkout_ref).one()
            checkout.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
            assert expire_checkout_sessions(db) == 0
        with SessionLocal() as db:
            checkout = db.query(CheckoutSession).filter(CheckoutSession.checkout_ref == checkout_ref).one()
            payment = db.query(StripeCheckoutPayment).filter(StripeCheckoutPayment.stripe_session_id == stripe_session_id).one()
            assert checkout.status == "reversal_window_open"
            assert payment.status == "paid"
    finally:
        _remove_checkout(checkout_ref, product_id, 1, variant)


def test_unknown_event_is_recorded_and_concurrent_duplicate_is_acknowledged(auth_client, monkeypatch) -> None:
    monkeypatch.setattr(payment_gateway, "stripe_checkout_configured", lambda: True)
    event_id = f"evt_unknown_{uuid4().hex}"
    event = {"id": event_id, "type": "test.unknown_event", "data": {"object": {}}}
    monkeypatch.setattr(payment_gateway, "construct_webhook_event", lambda *_: event)

    def deliver():
        return auth_client.post("/webhooks/stripe", content=b"{}", headers={"stripe-signature": "test"})

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            responses = list(executor.map(lambda _: deliver(), range(2)))
        assert all(response.status_code == 200 for response in responses)
        assert sum(response.json().get("duplicate") is True for response in responses) == 1
        with SessionLocal() as db:
            assert db.get(StripeWebhookEvent, event_id) is not None
    finally:
        with SessionLocal() as db:
            db.query(StripeWebhookEvent).filter(StripeWebhookEvent.event_id == event_id).delete()
            db.commit()


def _new_released_order(db, price: float = 1000.0) -> tuple[Order, User]:
    product = db.query(Product).filter(Product.seller_id != "").first()
    seller_profile = db.query(SellerProfile).filter(SellerProfile.seller_key == product.seller_id).one()
    seller = db.get(User, seller_profile.user_id)
    buyer = db.query(User).filter(User.email == "aisha@astra.ai").one()
    order = Order(
        order_ref=f"ORD-PAYOUT-{uuid4().hex[:12].upper()}",
        user_id=buyer.id,
        product_id=product.id,
        quantity=1,
        price=price,
        status=OrderStatus.CONFIRMED,
        escrow_status="RELEASED",
    )
    db.add(order)
    db.flush()
    return order, seller


def _cleanup_payout_order(db, order: Order, seller: User) -> None:
    db.query(SellerPayoutLedger).filter(SellerPayoutLedger.order_id == order.id).delete()
    db.query(StripeConnectAccount).filter(StripeConnectAccount.seller_user_id == seller.id).delete()
    db.delete(order)
    db.commit()


def test_connect_onboarding_creates_account_and_link(monkeypatch) -> None:
    monkeypatch.setattr(payment_gateway, "stripe_connect_configured", lambda: True)
    monkeypatch.setattr(payment_gateway, "create_connect_account", lambda email, seller_id: f"acct_{seller_id}_test")
    monkeypatch.setattr(payment_gateway, "create_connect_account_link", lambda account, refresh, ret: "https://connect.stripe.test/onboard")
    with SessionLocal() as db:
        seller = db.query(User).filter(User.role == "seller").first()
        url = start_connect_onboarding(db, seller, "https://astra.test/refresh", "https://astra.test/return")
        account = db.get(StripeConnectAccount, seller.id)
        assert url == "https://connect.stripe.test/onboard"
        assert account is not None and account.stripe_account_id.startswith("acct_")
        db.delete(account)
        db.commit()


def test_unonboarded_seller_payout_stays_pending(monkeypatch) -> None:
    monkeypatch.setattr(payment_gateway, "stripe_connect_configured", lambda: True)
    with SessionLocal() as db:
        order, seller = _new_released_order(db)
        record_order_payouts(db, [order])
        process_order_payout(db, order)
        entry = db.query(SellerPayoutLedger).filter(SellerPayoutLedger.order_id == order.id).one()
        assert entry.seller_user_id == seller.id
        assert entry.status == "pending_onboarding"
        _cleanup_payout_order(db, order, seller)


def test_seller_transfer_sends_net_amount_after_platform_fee(monkeypatch) -> None:
    monkeypatch.setattr(payment_gateway, "stripe_connect_configured", lambda: True)
    calls: list[dict] = []
    monkeypatch.setattr(
        payment_gateway,
        "create_seller_transfer",
        lambda amount, account, order_id, **kwargs: (
            calls.append({"amount": amount, "account": account, "order_id": order_id, **kwargs})
            or "tr_test_paid"
        ),
    )
    with SessionLocal() as db:
        order, seller = _new_released_order(db)
        db.add(StripeConnectAccount(
            seller_user_id=seller.id,
            stripe_account_id=f"acct_transfer_{uuid4().hex}",
            payouts_enabled=1,
            details_submitted=1,
            charges_enabled=1,
        ))
        db.flush()
        record_order_payouts(db, [order])
        process_order_payout(db, order)
        entry = db.query(SellerPayoutLedger).filter(SellerPayoutLedger.order_id == order.id).one()
        assert entry.platform_fee == pytest.approx(1000 * settings.PLATFORM_FEE_PERCENT / 100)
        assert entry.seller_amount + entry.platform_fee == pytest.approx(1000)
        assert calls[0]["amount"] == int(round(entry.seller_amount * 100))
        assert entry.status == "transferred"
        _cleanup_payout_order(db, order, seller)


def test_failed_seller_transfer_can_be_retried(monkeypatch) -> None:
    monkeypatch.setattr(payment_gateway, "stripe_connect_configured", lambda: True)
    transfer_calls: list[str] = []

    def create_transfer(_amount, _account, _order_id, *, idempotency_key):
        transfer_calls.append(idempotency_key)
        if len(transfer_calls) == 1:
            raise RuntimeError("temporary Stripe failure")
        return "tr_test_retry"

    monkeypatch.setattr(payment_gateway, "create_seller_transfer", create_transfer)
    with SessionLocal() as db:
        order, seller = _new_released_order(db)
        db.add(StripeConnectAccount(
            seller_user_id=seller.id,
            stripe_account_id=f"acct_retry_{uuid4().hex}",
            payouts_enabled=1,
            details_submitted=1,
            charges_enabled=1,
        ))
        db.flush()
        record_order_payouts(db, [order])
        process_order_payout(db, order)
        entry = db.query(SellerPayoutLedger).filter(SellerPayoutLedger.order_id == order.id).one()
        assert entry.status == "transfer_failed"
        assert entry.transfer_attempts == 1
        process_order_payout(db, order)
        assert entry.status == "transferred"
        assert entry.transfer_attempts == 2
        assert transfer_calls[0] != transfer_calls[1]
        _cleanup_payout_order(db, order, seller)