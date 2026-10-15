from urllib.parse import parse_qs, urlparse
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.v1.endpoints import auth
from app.core.config import settings
from app.core.database import SessionLocal
from app.main import app
from app.models.seller_profile import SellerProfile
from app.models.seller_wallet import SellerWallet
from app.models.user import User
from app.models.wallet import UserWallet


class _GoogleResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


class _GoogleClient:
    def __init__(self, **kwargs):
        self.timeout = kwargs.get("timeout")

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def post(self, url: str, data: dict):
        assert url == auth.GOOGLE_TOKEN_URL
        assert data["grant_type"] == "authorization_code"
        return _GoogleResponse({"access_token": "google-test-token"})

    def get(self, url: str, headers: dict):
        assert url == auth.GOOGLE_USERINFO_URL
        assert headers["Authorization"] == "Bearer google-test-token"
        return _GoogleResponse({
            "email": "aisha@astra.ai",
            "email_verified": True,
            "name": "Aisha",
        })


def test_google_start_sets_signed_state_cookie(monkeypatch) -> None:
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "test-client-id")
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setattr(settings, "GOOGLE_REDIRECT_URI", "http://localhost:8000/api/v1/auth/google/callback")

    with TestClient(app, follow_redirects=False) as client:
        response = client.get("/api/v1/auth/google/start")

    assert response.status_code == 307
    state = parse_qs(urlparse(response.headers["location"]).query)["state"][0]
    cookie = response.cookies.get(auth.GOOGLE_STATE_COOKIE)
    assert cookie == state
    assert "httponly" in response.headers["set-cookie"].lower()


def test_google_start_preserves_seller_choice_in_signed_state(monkeypatch) -> None:
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "test-client-id")
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "test-client-secret")

    with TestClient(app, follow_redirects=False) as client:
        response = client.get("/api/v1/auth/google/start?role=seller")

    state = parse_qs(urlparse(response.headers["location"]).query)["state"][0]
    assert response.status_code == 307
    assert auth._valid_google_state(state)
    assert auth._google_state_role(state) == "seller"


def test_google_signup_creates_seller_account_when_requested(monkeypatch) -> None:
    email = f"google-seller-{uuid4().hex}@example.com"
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "test-client-id")
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setattr(settings, "GOOGLE_REDIRECT_URI", "http://localhost:8000/api/v1/auth/google/callback")
    monkeypatch.setattr(settings, "FRONTEND_URL", "http://localhost:3000")

    class SellerGoogleClient(_GoogleClient):
        def get(self, url: str, headers: dict):
            assert url == auth.GOOGLE_USERINFO_URL
            return _GoogleResponse({"email": email, "email_verified": True, "name": "Google Seller"})

    monkeypatch.setattr(auth.httpx, "Client", SellerGoogleClient)
    state = auth._google_state("seller")
    user_id = None

    try:
        with TestClient(app, follow_redirects=False) as client:
            client.cookies.set(auth.GOOGLE_STATE_COOKIE, state)
            response = client.get(
                "/api/v1/auth/google/callback",
                params={"code": "google-auth-code", "state": state},
            )
            assert response.status_code == 307
            profile = client.get("/api/v1/auth/me")
            assert profile.status_code == 200, profile.text
            assert profile.json()["role"] == "seller"

        with SessionLocal() as db:
            user = db.query(User).filter(User.email == email).one()
            user_id = user.id
            assert db.query(SellerProfile).filter(SellerProfile.user_id == user.id).one()
            assert db.query(SellerWallet).filter(SellerWallet.seller_id == user.id).one()
    finally:
        if user_id is not None:
            with SessionLocal() as db:
                db.query(SellerWallet).filter(SellerWallet.seller_id == user_id).delete()
                db.query(SellerProfile).filter(SellerProfile.user_id == user_id).delete()
                db.query(UserWallet).filter(UserWallet.user_id == user_id).delete()
                db.query(User).filter(User.id == user_id).delete()
                db.commit()


def test_google_callback_exchanges_code_sets_session_and_redirects(monkeypatch) -> None:
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "test-client-id")
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setattr(settings, "GOOGLE_REDIRECT_URI", "http://localhost:8000/api/v1/auth/google/callback")
    monkeypatch.setattr(settings, "FRONTEND_URL", "http://localhost:3000")
    monkeypatch.setattr(auth.httpx, "Client", _GoogleClient)
    monkeypatch.setattr(auth, "_valid_google_state", lambda value: value == "valid-test-state")

    with TestClient(app, follow_redirects=False) as client:
        client.cookies.set(auth.GOOGLE_STATE_COOKIE, "valid-test-state")
        response = client.get(
            "/api/v1/auth/google/callback",
            params={"code": "google-auth-code", "state": "valid-test-state"},
        )
        assert response.status_code == 307
        assert response.headers["location"] == "http://localhost:3000/auth/callback"
        assert "astra_token=" in response.headers["set-cookie"]
        assert "httponly" in response.headers["set-cookie"].lower()
        assert response.cookies.get(auth.GOOGLE_STATE_COOKIE) is None

        profile = client.get("/api/v1/auth/me")
        assert profile.status_code == 200
        assert profile.json()["email"] == "aisha@astra.ai"


def test_google_callback_rejects_state_not_bound_to_browser(monkeypatch) -> None:
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "test-client-id")
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setattr(auth, "_valid_google_state", lambda value: bool(value))

    with TestClient(app, follow_redirects=False) as client:
        response = client.get(
            "/api/v1/auth/google/callback",
            params={"code": "google-auth-code", "state": "valid-test-state"},
        )

    assert response.status_code == 307
    assert "oauth_error=invalid_state" in response.headers["location"]


def test_google_start_returns_user_to_login_when_not_configured(monkeypatch) -> None:
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "")
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "")

    with TestClient(app, follow_redirects=False) as client:
        response = client.get("/api/v1/auth/google/start")

    assert response.status_code == 307
    assert response.headers["location"] == "http://localhost:3000/login?oauth_error=not_configured"


def test_google_id_token_login_verifies_mocked_token_and_sets_session(monkeypatch) -> None:
    email = f"google-id-{uuid4().hex}@example.com"
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "test-client-id")
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setattr(auth, "verify_google_id_token", lambda token: {
        "email": email,
        "email_verified": True,
        "name": "Google ID User",
    } if token == "mocked-id-token" else {})
    user_id = None

    try:
        with TestClient(app) as client:
            response = client.post("/api/v1/auth/google", json={"id_token": "mocked-id-token", "role": "buyer"})
            assert response.status_code == 200, response.text
            assert response.json()["user"]["email"] == email
            assert "astra_token=" in response.headers["set-cookie"]
            assert client.get("/api/v1/auth/me").json()["email"] == email

        with SessionLocal() as db:
            user = db.query(User).filter(User.email == email).one()
            user_id = user.id
    finally:
        if user_id is not None:
            with SessionLocal() as db:
                db.query(UserWallet).filter(UserWallet.user_id == user_id).delete()
                db.query(User).filter(User.id == user_id).delete()
                db.commit()


def test_google_id_token_login_returns_503_when_not_configured(monkeypatch) -> None:
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "")
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "")
    with TestClient(app) as client:
        response = client.post("/api/v1/auth/google", json={"id_token": "unused"})
    assert response.status_code == 503
    assert response.json()["detail"] == "Google login not configured"
