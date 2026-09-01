from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.core.security import create_access_token
from app.main import app
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
