from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.v1.endpoints import auth
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.security import create_otp_token, hash_otp, hash_password
from app.main import app
from app.models.user import User


def _pending_user(*, code: str = "804271", attempts: int = 0, expired: bool = False) -> tuple[int, str, str]:
    email = f"otp-{uuid4().hex}@example.com"
    user = User(
        name="OTP Test",
        email=email,
        hashed_password=hash_password("AstraTest123"),
        role="buyer",
        otp_code_hash=hash_otp(code),
        otp_expires_at=datetime.now(timezone.utc) - timedelta(seconds=1) if expired else datetime.now(timezone.utc) + timedelta(minutes=5),
        otp_attempts=attempts,
    )
    with SessionLocal() as db:
        db.add(user)
        db.commit()
        db.refresh(user)
        return user.id, email, create_otp_token(user.id)


def _delete_user(user_id: int) -> None:
    with SessionLocal() as db:
        db.query(User).filter(User.id == user_id).delete()
        db.commit()


def test_valid_generated_otp_completes_login_and_is_cleared(monkeypatch) -> None:
    monkeypatch.setattr(settings, "APP_ENV", "test")
    user_id, _, otp_token = _pending_user()
    try:
        with TestClient(app) as client:
            response = client.post("/api/v1/auth/verify-otp", json={"otp_token": otp_token, "code": "804271"})
        assert response.status_code == 200, response.text
        with SessionLocal() as db:
            user = db.get(User, user_id)
            assert user.otp_code_hash is None
            assert user.otp_expires_at is None
    finally:
        _delete_user(user_id)


def test_wrong_otp_increments_attempts() -> None:
    user_id, _, otp_token = _pending_user()
    try:
        with TestClient(app) as client:
            response = client.post("/api/v1/auth/verify-otp", json={"otp_token": otp_token, "code": "111111"})
        assert response.status_code == 400
        with SessionLocal() as db:
            assert db.get(User, user_id).otp_attempts == 1
    finally:
        _delete_user(user_id)


def test_expired_otp_is_rejected() -> None:
    user_id, _, otp_token = _pending_user(expired=True)
    try:
        with TestClient(app) as client:
            response = client.post("/api/v1/auth/verify-otp", json={"otp_token": otp_token, "code": "804271"})
        assert response.status_code == 400
        assert "expired" in response.json()["detail"].lower()
    finally:
        _delete_user(user_id)


def test_otp_attempt_limit_blocks_further_checks() -> None:
    user_id, _, otp_token = _pending_user(attempts=5)
    try:
        with TestClient(app) as client:
            response = client.post("/api/v1/auth/verify-otp", json={"otp_token": otp_token, "code": "804271"})
        assert response.status_code == 429
    finally:
        _delete_user(user_id)


def test_123456_shortcut_is_not_allowed_in_production(monkeypatch) -> None:
    monkeypatch.setattr(settings, "APP_ENV", "production")
    user_id, _, otp_token = _pending_user()
    try:
        with TestClient(app) as client:
            response = client.post("/api/v1/auth/verify-otp", json={"otp_token": otp_token, "code": "123456"})
        assert response.status_code == 400
    finally:
        _delete_user(user_id)


def test_resend_otp_enforces_cooldown(monkeypatch) -> None:
    from app.services import email_service

    monkeypatch.setattr(settings, "APP_ENV", "test")
    monkeypatch.setattr(settings, "EMAIL_PROVIDER", "console")
    monkeypatch.setattr(settings, "OTP_RESEND_COOLDOWN_SECONDS", 60)
    user_id, _, otp_token = _pending_user()
    try:
        with SessionLocal() as db:
            user = db.get(User, user_id)
            user.otp_sent_at = datetime.now(timezone.utc)
            db.commit()
        with TestClient(app) as client:
            response = client.post("/api/v1/auth/resend-otp", json={"otp_token": otp_token})
        assert response.status_code == 429
        assert "wait" in response.json()["detail"].lower()
    finally:
        _delete_user(user_id)