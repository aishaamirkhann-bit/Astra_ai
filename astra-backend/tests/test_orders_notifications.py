from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.main import app
from app.models.user import User
from app.core.database import SessionLocal


def test_order_hub_detail_and_reorder_contract(auth_client) -> None:
    orders = auth_client.get("/api/v1/orders")
    assert orders.status_code == 200
    assert orders.json()
    order = orders.json()[0]
    assert {"placed_at", "image", "status", "seconds_left"} <= order.keys()
    detail = auth_client.get(f"/api/v1/orders/{order['order_ref']}")
    assert detail.status_code == 200
    assert detail.json()["payment_method"] in {"Wallet", "Wallet / Consent Verified"}
    assert {"seller_verified", "seller_trust_score", "unit_price", "subtotal"} <= detail.json().keys()
    reordered = auth_client.post(f"/api/v1/orders/{order['order_ref']}/reorder")
    assert reordered.status_code == 200
    assert reordered.json()["cart_total_quantity"] >= order["quantity"]


def test_another_buyer_cannot_read_or_mutate_private_order(auth_client) -> None:
    orders = auth_client.get("/api/v1/orders").json()
    assert orders
    order_ref = orders[0]["order_ref"]
    with SessionLocal() as db:
        other_buyer = db.query(User).filter(User.email != "aisha@astra.ai", User.role == "buyer").first()
        assert other_buyer is not None
        token = create_access_token(str(other_buyer.id))
    with TestClient(app, headers={"Authorization": f"Bearer {token}"}) as other_client:
        assert other_client.get(f"/api/v1/orders/{order_ref}").status_code == 404
        assert other_client.post(f"/api/v1/orders/{order_ref}/reverse").status_code == 404
        assert other_client.post(f"/api/v1/orders/{order_ref}/dispute", json={"reason": "item_damaged"}).status_code == 404


def test_notification_center_unifies_categories_and_mark_read(auth_client) -> None:
    response = auth_client.get("/api/v1/notifications")
    assert response.status_code == 200
    payload = response.json()
    assert payload["unread_count"] == sum(not item["is_read"] for item in payload["items"])
    assert all(item["category"] in {"deal_match", "order_update", "financial_alert"} for item in payload["items"])
    unread = next((item for item in payload["items"] if not item["is_read"]), None)
    if unread:
        assert auth_client.post(f"/api/v1/notifications/{unread['id']}/read").status_code == 204


def test_orders_audit_trail_lists_real_events(auth_client) -> None:
    response = auth_client.get("/api/v1/orders/audit")
    assert response.status_code == 200
    entries = response.json()
    assert isinstance(entries, list)
    for entry in entries:
        assert {"id", "type", "endpoint", "actor", "verdict", "time"} <= entry.keys()
