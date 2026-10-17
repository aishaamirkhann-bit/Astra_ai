from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.core.security import create_access_token, decode_access_token
from app.core.config import settings
from app.main import app
from app.models.notification import Notification
from app.models.order import Order, OrderStatus
from app.models.pipeline import AuditLog
from app.models.product import Product
from app.models.seller_profile import SellerProfile
from app.models.user import User


def _seller_client() -> TestClient:
    with SessionLocal() as db:
        seller = db.query(User).filter(User.role == "seller").first()
        assert seller is not None
        token = create_access_token(str(seller.id), {"role": "seller"})
    return TestClient(app, headers={"Authorization": f"Bearer {token}"})


def test_buyer_cannot_manage_seller_inventory(auth_client) -> None:
    assert auth_client.get("/api/v1/seller/inventory").status_code == 403
    assert auth_client.get("/api/v1/seller/dashboard-stats").status_code == 403
    assert auth_client.post("/api/v1/seller/products/barcode-lookup", json={"barcode": "890123456001"}).status_code == 403
    assert auth_client.get("/api/v1/seller/wallet").status_code == 403


def test_account_role_can_switch_between_buyer_and_seller(auth_client) -> None:
    with SessionLocal() as db:
        buyer = db.query(User).filter(User.email == "aisha@astra.ai").one()
        buyer_id = buyer.id
        original_role = buyer.role
        buyer.role = "buyer"
        db.commit()
    try:
        switched = auth_client.post("/api/v1/auth/role", json={"role": "seller"})
        assert switched.status_code == 200, switched.text
        assert switched.json()["user"]["role"] == "seller"
        with SessionLocal() as db:
            assert db.query(SellerProfile).filter(SellerProfile.user_id == buyer_id).one().role == "seller"
        assert decode_access_token(switched.json()["access_token"])["role"] == "seller"
        assert "astra_token=" in switched.headers["set-cookie"]
        assert auth_client.get("/api/v1/seller/inventory").status_code == 200

        switched_back = auth_client.post("/api/v1/auth/role", json={"role": "buyer"})
        assert switched_back.status_code == 200, switched_back.text
        assert switched_back.json()["user"]["role"] == "buyer"
        assert decode_access_token(switched_back.json()["access_token"])["role"] == "buyer"
        assert auth_client.get("/api/v1/seller/inventory").status_code == 403
    finally:
        with SessionLocal() as db:
            buyer = db.query(User).filter(User.email == "aisha@astra.ai").one()
            buyer.role = original_role
            db.commit()


def test_cookie_session_refresh_keeps_database_role(monkeypatch) -> None:
    with SessionLocal() as db:
        seller = db.query(User).filter(User.role == "seller").first()
        assert seller is not None
        seller_id = seller.id
    monkeypatch.setattr(settings, "ACCESS_TOKEN_EXPIRE_MINUTES", 1)
    stale_claim_token = create_access_token(str(seller_id), {"role": "buyer"})
    client = TestClient(app, cookies={settings.AUTH_COOKIE_NAME: stale_claim_token})
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 200
    assert response.json()["role"] == "seller"
    refreshed = response.cookies.get(settings.AUTH_COOKIE_NAME)
    assert refreshed
    assert decode_access_token(refreshed)["role"] == "seller"


def test_seller_inventory_crud_and_order_monitor() -> None:
    client = _seller_client()
    created = client.post("/api/v1/seller/inventory", json={
        "title": "E2E Seller Test Product", "category": "Electronics",
        "price": 12999, "stock_count": 4, "description": "Temporary API test listing",
    })
    assert created.status_code == 201, created.text
    product_id = created.json()["id"]
    try:
        listing = client.get("/api/v1/seller/inventory")
        assert listing.status_code == 200
        assert any(item["id"] == product_id for item in listing.json())
        updated = client.patch(f"/api/v1/seller/inventory/{product_id}", json={"price": 11999, "stock_count": 2})
        assert updated.status_code == 200
        assert updated.json()["price"] == 11999
        orders = client.get("/api/v1/seller/orders")
        assert orders.status_code == 200
    finally:
        assert client.delete(f"/api/v1/seller/inventory/{product_id}").status_code == 204


def test_barcode_catalog_lookup_and_manual_listing_metadata(auth_client) -> None:
    client = _seller_client()
    known = client.get("/api/v1/seller/catalog/barcode/890123456001")
    assert known.status_code == 200, known.text
    assert known.json()["title"] == "Samsung Galaxy A35 5G"
    assert known.json()["brand"] == "Samsung"
    assert known.json()["market_price"] == 89999
    assert known.json()["verified"] is True
    assert known.json()["specifications"]["network"] == "5G"
    post_lookup = client.post("/api/v1/seller/products/barcode-lookup", json={"barcode": "890123456001"})
    assert post_lookup.status_code == 200
    assert post_lookup.json()["brand"] == "Samsung"
    stats = client.get("/api/v1/seller/dashboard-stats")
    assert stats.status_code == 200
    assert {"total_revenue", "pending_orders", "inventory_value", "revenue_series", "top_products"} <= stats.json().keys()

    unknown_barcode = "899999999999"
    unknown = client.get(f"/api/v1/seller/catalog/barcode/{unknown_barcode}")
    assert unknown.status_code == 404
    assert "New barcode detected" in unknown.json()["detail"]

    created = client.post("/api/v1/seller/inventory", json={
        "title": "Manual Barcode Test Product",
        "category": "Electronics",
        "price": 1499,
        "stock_count": 3,
        "barcode": unknown_barcode,
        "brand": "Test Brand",
        "subcategory": "Accessories",
        "color": "Black",
        "size": "One size",
        "variant": "Standard",
        "specifications": {"material": "Plastic"},
        "quality_tags": ["ASTRA Check recommended"],
    })
    assert created.status_code == 201, created.text
    listing = created.json()
    try:
        assert listing["barcode"] == unknown_barcode
        assert listing["barcode_verified"] is False
        assert listing["brand"] == "Test Brand"
        assert listing["specifications"] == {"material": "Plastic"}
        assert listing["quality_tags"] == ["ASTRA Check recommended"]
        deactivated = client.put(f"/api/v1/seller/inventory/{listing['id']}", json={"status": "inactive"})
        assert deactivated.status_code == 200
        assert deactivated.json()["status"] == "inactive"
        assert auth_client.get(f"/api/v1/products/{listing['id']}").status_code == 404
    finally:
        assert client.delete(f"/api/v1/seller/inventory/{listing['id']}").status_code == 204


def test_seller_payout_is_disabled_without_touching_buyer_wallet() -> None:
    client = _seller_client()
    before = client.get("/api/v1/seller/wallet")
    assert before.status_code == 200
    payout = client.post("/api/v1/seller/wallet/payout", json={"amount": 500})
    assert payout.status_code == 409
    assert "Manual payouts are disabled" in payout.json()["detail"]
    after = client.get("/api/v1/seller/wallet")
    assert after.status_code == 200
    assert after.json() == before.json()


def test_released_order_dispatches_and_is_delivered(auth_client) -> None:
    order_ref = f"ORD-DELIVERY-{uuid4().hex[:12].upper()}"
    dispatch_endpoint = f"/api/v1/seller/orders/{order_ref}/dispatch"
    delivery_endpoint = f"/api/v1/orders/{order_ref}/confirm-delivery"
    with SessionLocal() as db:
        buyer = db.query(User).filter(User.email == "aisha@astra.ai").one()
        product, seller = (
            db.query(Product, User)
            .join(User, User.name == Product.seller_name)
            .filter(User.role == "seller")
            .first()
        )
        order = Order(
            order_ref=order_ref,
            user_id=buyer.id,
            product_id=product.id,
            quantity=1,
            price=product.price,
            status=OrderStatus.CONFIRMED,
            escrow_status="HELD",
        )
        db.add(order)
        db.commit()
        seller_token = create_access_token(str(seller.id), {"role": "seller"})

    seller_client = TestClient(app, headers={"Authorization": f"Bearer {seller_token}"})
    try:
        assert auth_client.post(dispatch_endpoint).status_code == 403
        assert auth_client.post(delivery_endpoint).status_code == 409
        assert seller_client.post(dispatch_endpoint).status_code == 409

        with SessionLocal() as db:
            order = db.query(Order).filter(Order.order_ref == order_ref).one()
            order.escrow_status = "RELEASED"
            db.commit()

        dispatched = seller_client.post(dispatch_endpoint)
        assert dispatched.status_code == 200, dispatched.text
        assert dispatched.json() == {
            "order_ref": order_ref,
            "order_status": "shipped",
            "escrow_status": "RELEASED",
        }
        assert seller_client.post(dispatch_endpoint).status_code == 409

        delivered = auth_client.post(delivery_endpoint)
        assert delivered.status_code == 200, delivered.text
        assert delivered.json()["order_ref"] == order_ref
        assert delivered.json()["status"] == "delivered"
        assert delivered.json()["delivered_at"] is not None
        assert auth_client.post(delivery_endpoint).status_code == 409

        with SessionLocal() as db:
            order = db.query(Order).filter(Order.order_ref == order_ref).one()
            assert order.status == OrderStatus.DELIVERED
            assert order.shipped_at is not None
            assert order.delivered_at is not None
            assert {
                audit.event_type
                for audit in db.query(AuditLog).filter(
                    AuditLog.endpoint.in_([dispatch_endpoint, delivery_endpoint])
                )
            } == {"seller.dispatch", "order.delivery_confirmed"}
    finally:
        with SessionLocal() as db:
            db.query(Notification).filter(
                Notification.message == f"Delivery confirmed for {order_ref}."
            ).delete()
            db.query(AuditLog).filter(
                AuditLog.endpoint.in_([dispatch_endpoint, delivery_endpoint])
            ).delete()
            db.query(Order).filter(Order.order_ref == order_ref).delete()
            db.commit()
