"""
Shared pytest fixtures. Protected endpoints now enforce strict JWT auth
(no demo-user fallback), so tests authenticate with a real token for the
seeded user. Run `python -m app.db.seed` before the suite.
"""
import pytest
from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.core.security import create_access_token
from app.main import app
from app.models.user import User

DEMO_EMAIL = "aisha@astra.ai"


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
def auth_client(auth_token: str) -> TestClient:
    return TestClient(app, headers={"Authorization": f"Bearer {auth_token}"})


@pytest.fixture(scope="session")
def anonymous_client() -> TestClient:
    return TestClient(app)
