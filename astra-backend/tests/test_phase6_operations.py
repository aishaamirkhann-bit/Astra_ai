from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.core.security import create_access_token
from app.main import app
from app.models.order import Order
from app.models.product import Product
from app.models.user import User
from app.models.wallet import FinancialConsentLog, UserWallet, WalletTransaction
from app.services.order_operations import calculate_bundle_offer, parse_bundle_request, parse_order_operation, return_eligibility


def test_order_intent_extracts_english_and_roman_urdu():
    assert parse_order_operation("Where is my order now?").action == "track"
    assert parse_order_operation("Mera order kahan tak pohncha?").action == "track"
    intent = parse_order_operation("Pichli shirt return karni hai")
    assert intent.action == "return_request"
    assert intent.product_hint == "shirt"
    assert parse_order_operation("I need an exchange for my previous shirt").action == "exchange_request"


def test_return_window_requires_delivery_and_expires_after_thirty_days():
    now = datetime(2026, 10, 21, tzinfo=timezone.utc)
    assert return_eligibility("shipped", now, now)[0] is False
    assert return_eligibility("delivered", None, now)[0] is False
    assert return_eligibility("delivered", now - timedelta(days=29), now)[0] is True
    eligible, message = return_eligibility("delivered", now - timedelta(days=31), now)
    assert eligible is False
    assert "30-day" in message


def test_bundle_discount_respects_each_seller_floor():
    quote = calculate_bundle_offer([
        {"product_id": "shirt", "title": "Shirt", "quantity": 2, "price": 1000, "seller_price_floor": 970},
        {"product_id": "shoes", "title": "Shoes", "quantity": 1, "price": 2000, "seller_price_floor": 1500},
    ])
    assert [line["offered_unit_price"] for line in quote["items"]] == [970, 1900]
    assert all(line["offered_unit_price"] >= line["seller_floor"] for line in quote["items"])
    assert quote["list_total"] == 4000
    assert quote["offer_total"] == 3840
    assert quote["binding"] is False
    assert quote["requires_buyer_approval"] is True


def test_roman_urdu_bundle_phrase_extracts_multi_item_quantities():
    assert parse_bundle_request("Agar main yeh 2 shirts aur 1 shoes aik sath loon toh kya discount milega?") == [
        {"product_hint": "shirt", "quantity": 2},
        {"product_hint": "shoes", "quantity": 1},
    ]


def test_track_endpoint_is_buyer_scoped(auth_client, demo_user_id):
    with SessionLocal() as db:
        order = db.query(Order).filter(Order.user_id == demo_user_id).first()
        other = db.query(User).filter(User.role == "buyer", User.id != demo_user_id).first()
        assert order and other
        order_ref = order.order_ref
        other_token = create_access_token(str(other.id))
    tracked = auth_client.get("/api/v1/orders/track", params={"order_ref": order_ref})
    assert tracked.status_code == 200
    assert tracked.json()["orders"][0]["order_ref"] == order_ref
    with TestClient(app, headers={"Authorization": f"Bearer {other_token}"}) as other_client:
        assert other_client.get("/api/v1/orders/track", params={"order_ref": order_ref}).status_code == 404
        assert other_client.post("/api/v1/orders/return-request", json={
            "order_ref": order_ref, "reason": "Changed my mind", "confirmed": True,
        }).status_code == 404


def test_chat_roman_urdu_order_query_returns_a_status_timeline(auth_client, demo_user_id):
    with SessionLocal() as db:
        order = db.query(Order).filter(Order.user_id == demo_user_id).order_by(Order.created_at.desc()).first()
        assert order
        order_ref = order.order_ref
    response = auth_client.post("/api/v1/chat/message", data={"message": "Mera order kahan tak pohncha?"})
    assert response.status_code == 200, response.text
    assert response.json()["card_type"] == "order_tracking"
    assert response.json()["card"]["order_ref"] == order_ref
    assert [stage["label"] for stage in response.json()["card"]["timeline"]] == [
        "Processing", "Shipped", "Out for Delivery", "Delivered",
    ]


def test_return_request_requires_explicit_confirmation_and_never_refunds(auth_client, demo_user_id):
    with SessionLocal() as db:
        order = db.query(Order).filter(Order.user_id == demo_user_id).first()
        wallet = db.query(UserWallet).filter(UserWallet.user_id == demo_user_id).one()
        assert order
        order_ref = order.order_ref
        balance = wallet.available_balance
        status = order.status.value
    response = auth_client.post("/api/v1/orders/return-request", json={
        "order_ref": order_ref, "reason": "Does not fit", "confirmed": False,
    })
    assert response.status_code == 409
    with SessionLocal() as db:
        assert db.query(UserWallet).filter(UserWallet.user_id == demo_user_id).one().available_balance == balance
        assert db.query(Order).filter(Order.order_ref == order_ref).one().status.value == status


def test_bundle_advisory_does_not_create_orders_or_change_wallet(auth_client, demo_user_id):
    with SessionLocal() as db:
        products = db.query(Product).filter(Product.listing_status == "active", Product.stock_count > 0).limit(2).all()
        assert len(products) == 2
        items = [{"product_id": product.id, "quantity": 1} for product in products]
        order_count = db.query(Order).filter(Order.user_id == demo_user_id).count()
        wallet = db.query(UserWallet).filter(UserWallet.user_id == demo_user_id).one()
        balance = wallet.available_balance
        ledger_count = db.query(WalletTransaction).filter(WalletTransaction.wallet_id == wallet.wallet_id).count()
        consent_count = db.query(FinancialConsentLog).filter(FinancialConsentLog.user_id == demo_user_id).count()
    response = auth_client.post("/api/v1/negotiation/bundle/advisory", json={"items": items})
    assert response.status_code == 200, response.text
    quote = response.json()
    assert quote["binding"] is False
    assert all(line["offered_unit_price"] >= line["seller_floor"] for line in quote["items"])
    with SessionLocal() as db:
        assert db.query(Order).filter(Order.user_id == demo_user_id).count() == order_count
        wallet = db.query(UserWallet).filter(UserWallet.user_id == demo_user_id).one()
        assert wallet.available_balance == balance
        assert db.query(WalletTransaction).filter(WalletTransaction.wallet_id == wallet.wallet_id).count() == ledger_count
        assert db.query(FinancialConsentLog).filter(FinancialConsentLog.user_id == demo_user_id).count() == consent_count
