"""
Shared pytest fixtures. Protected endpoints now enforce strict JWT auth
(no demo-user fallback), so tests authenticate with a real token for the
seeded user. Run `python -m app.db.seed` before the suite.

The clients are context-managed so the app lifespan (deals bootstrap,
background monitors) runs even on a fresh database.
"""
import pytest
from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.core.rate_limit import reset_rate_limit_state
from app.core.security import create_access_token
from app.main import app
from app.models.user import User
from app.models.wallet import UserWallet

DEMO_EMAIL = "aisha@astra.ai"


@pytest.fixture(autouse=True)
def isolated_rate_limiter():
    reset_rate_limit_state()
    # Tests share the configured PostgreSQL database; restore the seeded buyer
    # balance so a failed/aborted checkout cannot poison a later test.
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == DEMO_EMAIL).first()
        if user:
            wallet = db.query(UserWallet).filter(UserWallet.user_id == user.id).first()
            if wallet:
                wallet.available_balance = 650_000
                db.commit()
    yield
    reset_rate_limit_state()


@pytest.fixture(scope="session")
def demo_user_id() -> int:
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == DEMO_EMAIL).first()
    if not user:
        pytest.exit("Seed the database first: python -m app.db.seed", returncode=1)
    return user.id


@pytest.fixture(scope="session")
def auth_token(demo_user_id: int) -> str:
    return create_access_token(str(demo_user_id))


@pytest.fixture(scope="session")
def auth_client(auth_token: str):
    with TestClient(app, headers={"Authorization": f"Bearer {auth_token}"}) as client:
        yield client


@pytest.fixture(scope="session")
def anonymous_client():
    with TestClient(app) as client:
        yield client
