from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.v1.endpoints import auth
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.security import create_access_token
from app.main import app
from app.models.budget import ShoppingGoal
from app.models.seller_profile import SellerProfile
from app.models.seller_wallet import SellerWallet
from app.models.user import User
from app.models.wallet import UserWallet


@pytest.mark.parametrize("role", ["buyer", "seller"])
def test_registration_completes_otp_and_preserves_selected_dashboard(role, monkeypatch) -> None:
    delivered: list[str] = []
    monkeypatch.setattr(settings, "APP_ENV", "development")
    monkeypatch.setattr(settings, "OTP_DEBUG_LOG", True)
    monkeypatch.setattr(settings, "RESEND_API_KEY", "")
    monkeypatch.setattr(settings, "SMTP_HOST", "")
    monkeypatch.setattr(settings, "SMTP_USERNAME", "")
    monkeypatch.setattr(settings, "SMTP_USER", "")
    monkeypatch.setattr(auth, "send_otp_email", lambda **kwargs: delivered.append(kwargs["to_email"]))
    email = f"signup-{uuid4().hex}@example.com"
    user_id = None

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/auth/register",
                json={
                    "name": "Signup Test",
                    "email": email.upper(),
                    "password": "AstraTest123",
                    "role": role,
                },
            )
            assert response.status_code == 201, response.text
            challenge = response.json()
            assert challenge["email"] == email
            assert "Use 123456 to verify" in challenge["message"]
            assert delivered == [email]

            verified = client.post(
                "/api/v1/auth/verify-otp",
                json={"otp_token": challenge["otp_token"], "code": "123456"},
            )
            assert verified.status_code == 200, verified.text
            assert verified.json()["user"]["role"] == role

        with SessionLocal() as db:
            user = db.query(User).filter(User.email == email).one()
            user_id = user.id
            seller_profile = db.query(SellerProfile).filter(SellerProfile.user_id == user.id).first()
            seller_wallet = db.query(SellerWallet).filter(SellerWallet.seller_id == user.id).first()
            if role == "seller":
                assert seller_profile is not None
                assert seller_wallet is not None
                assert seller_wallet.available_balance == 0
            else:
                assert seller_profile is None
                assert seller_wallet is None
    finally:
        if user_id is not None:
            with SessionLocal() as db:
                db.query(SellerWallet).filter(SellerWallet.seller_id == user_id).delete()
                db.query(SellerProfile).filter(SellerProfile.user_id == user_id).delete()
                db.query(UserWallet).filter(UserWallet.user_id == user_id).delete()
                db.query(User).filter(User.id == user_id).delete()
                db.commit()


def test_registration_email_delivery_failure_returns_retryable_error_and_rolls_back_user(monkeypatch) -> None:
    email = f"signup-failed-{uuid4().hex}@example.com"

    def fail_delivery(**kwargs) -> None:
        raise RuntimeError("mail provider unavailable")

    monkeypatch.setattr(auth, "send_otp_email", fail_delivery)
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/register",
            json={"name": "Signup Test", "email": email, "password": "AstraTest123", "role": "buyer"},
        )

    assert response.status_code == 503
    with SessionLocal() as db:
        assert db.query(User).filter(User.email == email).first() is None


def test_category_product_goal_is_visible_in_my_goals() -> None:
    title = f"Goal from category {uuid4().hex[:8]}"
    with SessionLocal() as db:
        buyer = db.query(User).filter(User.email == "aisha@astra.ai").one()
        assert buyer.role == "buyer"
        token = create_access_token(str(buyer.id), {"role": "buyer"})

    goal_id = None
    try:
        with TestClient(app, headers={"Authorization": f"Bearer {token}"}) as client:
            created = client.post("/api/v1/goals/create", json={
                "target_title": title,
                "target_price": 90000,
                "category": "Mobiles",
                "priority_level": "High",
            })
            assert created.status_code == 201, created.text
            goal_id = created.json()["goal_id"]
            assert created.json()["category"] == "Mobiles"

            dashboard = client.get("/api/v1/goals/budget")
            assert dashboard.status_code == 200, dashboard.text
            assert any(
                goal["goal_id"] == goal_id
                and goal["target_title"] == title
                and goal["category"] == "Mobiles"
                for goal in dashboard.json()["goals"]
            )
    finally:
        if goal_id is not None:
            with SessionLocal() as db:
                db.query(ShoppingGoal).filter(ShoppingGoal.goal_id == goal_id).delete()
                db.commit()
