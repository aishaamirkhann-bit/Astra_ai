from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.core.security import create_access_token
from app.main import app
from app.models.notification import Notification
from app.models.order import Order, OrderStatus
from app.models.pipeline import AuditLog
from app.models.product import Product
from app.models.user import User


def _seller_client() -> TestClient:
    with SessionLocal() as db:
        seller = db.query(User).filter(User.role == "seller").first()
        assert seller is not None
        token = create_access_token(str(seller.id), {"role": "seller"})
    return TestClient(app, headers={"Authorization": f"Bearer {token}"})


def test_buyer_cannot_manage_seller_inventory(auth_client) -> None:
    assert auth_client.get("/api/v1/seller/inventory").status_code == 403


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
