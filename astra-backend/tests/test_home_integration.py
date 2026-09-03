def test_http_only_cookie_authenticates_home_and_profile(auth_client, demo_user_id) -> None:
    from app.core.security import create_access_token

    token = create_access_token(str(demo_user_id), {"role": "buyer"})
    auth_client.cookies.set("astra_token", token)
    try:
        profile = auth_client.get("/api/v1/auth/me")
        home = auth_client.get("/api/v1/home")
        assert profile.status_code == 200
        assert home.status_code == 200
        assert home.json()["user"]["id"] == profile.json()["id"]
        assert home.json()["unread_notifications"] >= 0
    finally:
        auth_client.cookies.clear()


def test_home_cart_alias_and_wishlist_goal_actions(auth_client) -> None:
    from app.core.database import SessionLocal
    from app.models.cart import CartItem
    from app.models.user import User

    products = auth_client.get("/api/v1/products/recommended").json()
    product = products[0]
    try:
        added = auth_client.post("/api/v1/cart/add", json={"product_slug": product["slug"], "quantity": 1})
        assert added.status_code == 200
        saved = auth_client.post("/api/v1/goals/create", json={"target_title": product["name"], "target_price": product["price"], "category": product["category"], "priority_level": "Medium"})
        assert saved.status_code == 201
    finally:
        with SessionLocal() as db:
            user = db.query(User).filter(User.email == "aisha@astra.ai").first()
            db.query(CartItem).filter(
                CartItem.user_id == user.id, CartItem.product_id == product["slug"],
                CartItem.size == "", CartItem.color == "", CartItem.storage == "",
            ).delete()
            db.commit()


def test_home_pending_approval_exposes_consent_amount(auth_client) -> None:
    response = auth_client.get("/api/v1/home")
    assert response.status_code == 200
    approval = response.json()["approval"]
    if approval is not None:
        assert approval["amount"] > 0
