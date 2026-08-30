from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.main import app

client = TestClient(app)


def test_http_only_cookie_authenticates_home_and_profile() -> None:
    token = create_access_token("1", {"role": "buyer"})
    client.cookies.set("astra_token", token)
    profile = client.get("/api/v1/auth/me")
    home = client.get("/api/v1/home")
    assert profile.status_code == 200
    assert home.status_code == 200
    assert home.json()["user"]["id"] == profile.json()["id"]
    assert home.json()["unread_notifications"] >= 0


def test_home_cart_alias_and_wishlist_goal_actions() -> None:
    products = client.get("/api/v1/products/recommended").json()
    product = products[0]
    added = client.post("/api/v1/cart/add", json={"product_slug": product["slug"], "quantity": 1})
    assert added.status_code == 200
    saved = client.post("/api/v1/goals/create", json={"target_title": product["name"], "target_price": product["price"], "category": product["category"], "priority_level": "Medium"})
    assert saved.status_code == 201


def test_home_pending_approval_exposes_consent_amount() -> None:
    response = client.get("/api/v1/home")
    assert response.status_code == 200
    approval = response.json()["approval"]
    if approval is not None:
        assert approval["amount"] > 0
