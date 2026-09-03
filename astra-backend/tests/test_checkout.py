from datetime import datetime, timedelta, timezone

import pytest

from app.core.database import SessionLocal
from app.models.budget import UserBudget
from app.models.cart import CartItem
from app.models.checkout import CheckoutSession
from app.models.product import Product
from app.models.user import User
from app.models.wallet import FinancialConsentLog, UserWallet, WalletTransaction
from app.services.checkout_fsm import abandon_checkout_session, expire_checkout_sessions, finalize_reversal_orders


ADDRESS = "42 Checkout Lane, Lahore"
DEMO_EMAIL = "aisha@astra.ai"


def _deal(auth_client, *, min_stock: int = 1, max_price: float | None = None) -> dict:
    deals = auth_client.get("/api/v1/deals", params={"page_size": 100}).json()["items"]
    return next(
        item
        for item in deals
        if item["stock_remaining"] >= min_stock
        and (max_price is None or item["price"] < max_price)
    )


def _clear_cart(auth_client) -> None:
    cart = auth_client.get("/api/v1/cart")
    assert cart.status_code == 200
    for item in cart.json()["items"]:
        response = auth_client.delete(f"/api/v1/cart/{item['id']}")
        assert response.status_code == 200


def _reset_checkout_state(auth_client) -> None:
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == DEMO_EMAIL).one()
        sessions = db.query(CheckoutSession).filter(
            CheckoutSession.user_id == user.id,
            CheckoutSession.status == "awaiting_consent",
        ).all()
        for session in sessions:
            abandon_checkout_session(db, session, "test:checkout")
        db.commit()
    _clear_cart(auth_client)


def _add_variant(auth_client, product_slug: str, size: str) -> None:
    response = auth_client.post("/api/v1/cart/add", json={
        "product_slug": product_slug,
        "quantity": 1,
        "size": size,
        "color": "Graphite",
    })
    assert response.status_code == 200


def _create_session(auth_client) -> dict:
    response = auth_client.post("/api/v1/checkout/session", json={"shipping_address": ADDRESS})
    assert response.status_code == 201
    return response.json()


def _voice_consent(auth_client, session: dict) -> str:
    response = auth_client.post("/api/v1/wallet/authorize-consent", json={
        "amount": session["total"],
        "auth_method": "Voice",
        "checkout_ref": session["checkout_ref"],
        "voice_transcript": f"I authorize payment of Rs. {int(session['total'])}",
    })
    assert response.status_code == 200
    return response.json()["consent_id"]


def test_low_value_multiline_checkout_requires_consent_and_is_idempotent(auth_client) -> None:
    _reset_checkout_state(auth_client)
    order_refs: list[str] = []
    try:
        deal = _deal(auth_client, min_stock=2, max_price=50_000)
        _add_variant(auth_client, deal["slug"], "Checkout one")
        _add_variant(auth_client, deal["slug"], "Checkout two")
        wallet_before = auth_client.get("/api/v1/wallet").json()["available_balance"]

        session = _create_session(auth_client)
        assert session["status"] == "awaiting_consent"
        assert session["total"] == pytest.approx(deal["price"] * 2)
        assert len(session["order_refs"]) == 2

        blocked = auth_client.post(f"/api/v1/checkout/session/{session['checkout_ref']}/confirm", json={})
        assert blocked.status_code == 428
        assert blocked.json()["detail"] == f"FINANCIAL_CONSENT_REQUIRED:{session['checkout_ref']}"

        consent_id = _voice_consent(auth_client, session)
        confirmed = auth_client.post(
            f"/api/v1/checkout/session/{session['checkout_ref']}/confirm",
            json={"consent_id": consent_id},
        )
        assert confirmed.status_code == 200
        payload = confirmed.json()
        assert payload["created"] is True
        assert payload["status"] == "reversal_window_open"
        order_refs = payload["order_refs"]

        retry = auth_client.post(
            f"/api/v1/checkout/session/{session['checkout_ref']}/confirm",
            json={"consent_id": consent_id},
        )
        assert retry.status_code == 200
        assert retry.json()["created"] is False
        assert retry.json()["wallet_balance"] == payload["wallet_balance"]
        assert payload["wallet_balance"] == pytest.approx(wallet_before - session["total"])

        with SessionLocal() as db:
            checkout = db.query(CheckoutSession).filter(CheckoutSession.checkout_ref == session["checkout_ref"]).one()
            orders = list(checkout.orders)
            consent = db.query(FinancialConsentLog).filter(FinancialConsentLog.consent_id == consent_id).one()
            debit_count = db.query(WalletTransaction).filter(
                WalletTransaction.reference_order_id.in_([order.id for order in orders]),
                WalletTransaction.txn_type == "Debit",
            ).count()
            assert consent.reference_checkout_id == checkout.id
            assert consent.consumed_at is not None
            assert debit_count == len(orders) == 2
    finally:
        for order_ref in order_refs:
            auth_client.post(f"/api/v1/orders/{order_ref}/reverse")
        _reset_checkout_state(auth_client)


def test_checkout_rejects_combined_variant_quantities_above_stock(auth_client) -> None:
    _reset_checkout_state(auth_client)
    deal = _deal(auth_client)
    with SessionLocal() as db:
        product = db.get(Product, deal["slug"])
        original_stock = product.stock_count
        product.stock_count = 1
        db.commit()
    try:
        _add_variant(auth_client, deal["slug"], "Stock one")
        _add_variant(auth_client, deal["slug"], "Stock two")
        response = auth_client.post("/api/v1/checkout/session", json={"shipping_address": ADDRESS})
        assert response.status_code == 409
        assert "Insufficient stock" in response.json()["detail"]
    finally:
        _reset_checkout_state(auth_client)
        with SessionLocal() as db:
            db.get(Product, deal["slug"]).stock_count = original_stock
            db.commit()


def test_checkout_otp_consent_is_bound_to_the_session_total(auth_client) -> None:
    _reset_checkout_state(auth_client)
    order_refs: list[str] = []
    try:
        deal = _deal(auth_client)
        _add_variant(auth_client, deal["slug"], "OTP checkout")
        session = _create_session(auth_client)
        challenge = auth_client.post("/api/v1/wallet/authorize-consent", json={
            "amount": session["total"],
            "auth_method": "OTP",
            "checkout_ref": session["checkout_ref"],
        })
        assert challenge.status_code == 200
        challenge_payload = challenge.json()

        invalid = auth_client.post("/api/v1/wallet/authorize-consent", json={
            "amount": session["total"] + 1,
            "auth_method": "OTP",
            "checkout_ref": session["checkout_ref"],
            "consent_id": challenge_payload["consent_id"],
            "otp_code": challenge_payload["dev_otp"],
        })
        assert invalid.status_code == 409

        authorized = auth_client.post("/api/v1/wallet/authorize-consent", json={
            "amount": session["total"],
            "auth_method": "OTP",
            "checkout_ref": session["checkout_ref"],
            "consent_id": challenge_payload["consent_id"],
            "otp_code": challenge_payload["dev_otp"],
        })
        assert authorized.status_code == 200
        assert authorized.json()["status"] == "approved"

        confirmed = auth_client.post(
            f"/api/v1/checkout/session/{session['checkout_ref']}/confirm",
            json={"consent_id": authorized.json()["consent_id"]},
        )
        assert confirmed.status_code == 200
        order_refs = confirmed.json()["order_refs"]
    finally:
        for order_ref in order_refs:
            auth_client.post(f"/api/v1/orders/{order_ref}/reverse")
        _reset_checkout_state(auth_client)


def test_expired_checkout_releases_stock_and_restores_cart(auth_client) -> None:
    _reset_checkout_state(auth_client)
    deal = _deal(auth_client)
    with SessionLocal() as db:
        original_stock = db.get(Product, deal["slug"]).stock_count
    try:
        _add_variant(auth_client, deal["slug"], "Expiry checkout")
        session = _create_session(auth_client)
        with SessionLocal() as db:
            checkout = db.query(CheckoutSession).filter(CheckoutSession.checkout_ref == session["checkout_ref"]).one()
            checkout.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            db.commit()
            assert expire_checkout_sessions(db) == 1

        state = auth_client.get(f"/api/v1/checkout/session/{session['checkout_ref']}")
        assert state.status_code == 200
        assert state.json()["status"] == "expired"
        cart = auth_client.get("/api/v1/cart").json()
        assert any(item["product_slug"] == deal["slug"] for item in cart["items"])
        with SessionLocal() as db:
            assert db.get(Product, deal["slug"]).stock_count == original_stock
    finally:
        _reset_checkout_state(auth_client)


def test_price_change_cancels_checkout_without_consuming_consent(auth_client) -> None:
    _reset_checkout_state(auth_client)
    deal = _deal(auth_client)
    original_price = 0.0
    try:
        _add_variant(auth_client, deal["slug"], "Price change")
        session = _create_session(auth_client)
        consent_id = _voice_consent(auth_client, session)
        with SessionLocal() as db:
            product = db.get(Product, deal["slug"])
            original_price = product.price
            product.price += 1
            db.commit()

        response = auth_client.post(
            f"/api/v1/checkout/session/{session['checkout_ref']}/confirm",
            json={"consent_id": consent_id},
        )
        assert response.status_code == 409
        assert "CHECKOUT_PRICE_CHANGED" in response.json()["detail"]
        with SessionLocal() as db:
            checkout = db.query(CheckoutSession).filter(CheckoutSession.checkout_ref == session["checkout_ref"]).one()
            consent = db.query(FinancialConsentLog).filter(FinancialConsentLog.consent_id == consent_id).one()
            assert checkout.status == "cancelled"
            assert consent.consumed_at is None
    finally:
        if original_price:
            with SessionLocal() as db:
                db.get(Product, deal["slug"]).price = original_price
                db.commit()
        _reset_checkout_state(auth_client)


def test_reversal_finalization_updates_checkout_session_status(auth_client) -> None:
    _reset_checkout_state(auth_client)
    checkout_ref = ""
    wallet_before = 0.0
    budget_before: float | None = None
    try:
        deal = _deal(auth_client, max_price=50_000)
        _add_variant(auth_client, deal["slug"], "Finalization checkout")
        session = _create_session(auth_client)
        checkout_ref = session["checkout_ref"]
        consent_id = _voice_consent(auth_client, session)
        confirmed = auth_client.post(
            f"/api/v1/checkout/session/{checkout_ref}/confirm",
            json={"consent_id": consent_id},
        )
        assert confirmed.status_code == 200

        with SessionLocal() as db:
            user = db.query(User).filter(User.email == DEMO_EMAIL).one()
            wallet = db.query(UserWallet).filter(UserWallet.user_id == user.id).one()
            budget = db.query(UserBudget).filter(UserBudget.user_id == user.id).first()
            wallet_before = wallet.available_balance + session["total"]
            budget_before = budget.current_spent - session["total"] if budget else None
            checkout = db.query(CheckoutSession).filter(CheckoutSession.checkout_ref == checkout_ref).one()
            orders = list(checkout.orders)
            for order in orders:
                order.reversal_deadline = datetime.now(timezone.utc) - timedelta(seconds=1)
            db.commit()

            finalized = finalize_reversal_orders(db)
            assert {order.order_ref for order in finalized} == set(session["order_refs"])
            db.refresh(checkout)
            assert checkout.status == "confirmed"
            assert all(order.status.value == "confirmed" for order in checkout.orders)
            assert all(order.escrow_status == "RELEASED" for order in checkout.orders)

        state = auth_client.get(f"/api/v1/checkout/session/{checkout_ref}")
        assert state.status_code == 200
        assert state.json()["status"] == "confirmed"
    finally:
        if checkout_ref:
            with SessionLocal() as db:
                checkout = db.query(CheckoutSession).filter(CheckoutSession.checkout_ref == checkout_ref).first()
                if checkout:
                    orders = list(checkout.orders)
                    product_quantities: dict[str, int] = {}
                    for order in orders:
                        product_quantities[order.product_id] = product_quantities.get(order.product_id, 0) + order.quantity
                    order_ids = [order.id for order in orders]
                    db.query(WalletTransaction).filter(WalletTransaction.reference_order_id.in_(order_ids)).delete(synchronize_session=False)
                    db.query(FinancialConsentLog).filter(FinancialConsentLog.reference_checkout_id == checkout.id).delete(synchronize_session=False)
                    for product_id, quantity in product_quantities.items():
                        db.get(Product, product_id).stock_count += quantity
                    for order in orders:
                        db.delete(order)
                    db.flush()
                    db.delete(checkout)
                    user = db.query(User).filter(User.email == DEMO_EMAIL).one()
                    db.query(UserWallet).filter(UserWallet.user_id == user.id).one().available_balance = wallet_before
                    budget = db.query(UserBudget).filter(UserBudget.user_id == user.id).first()
                    if budget and budget_before is not None:
                        budget.current_spent = budget_before
                    db.commit()
        _reset_checkout_state(auth_client)
