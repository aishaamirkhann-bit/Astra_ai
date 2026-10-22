"""Shared fixtures bound to an isolated, local pytest database."""
import os
import tempfile
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

if os.environ.get("APP_ENV", "").lower() == "production" or os.environ.get("ENVIRONMENT", "").lower() == "production":
    raise RuntimeError("Refusing to run tests with APP_ENV=production")

import app.core.config as app_config
from app.core.config import Settings

configured_settings = Settings()
if configured_settings.APP_ENV.lower() == "production":
    raise RuntimeError("Refusing to run tests with APP_ENV=production")

REMOTE_DATABASE_HOST_MARKERS = ("neon.tech", "render.com", "amazonaws", "supabase")


def _assert_local_database(database_url: str, setting_name: str) -> None:
    hostname = (urlparse(database_url).hostname or "").lower()
    if any(marker in hostname for marker in REMOTE_DATABASE_HOST_MARKERS):
        raise RuntimeError(f"Refusing to run tests: {setting_name} points to remote host {hostname}")


_assert_local_database(configured_settings.DATABASE_URL, "DATABASE_URL")
test_database_url = os.environ.get("TEST_DATABASE_URL", "").strip()
if test_database_url:
    _assert_local_database(test_database_url, "TEST_DATABASE_URL")
else:
    temporary_database = Path(tempfile.gettempdir()) / f"astra-pytest-{uuid4().hex}.db"
    test_database_url = f"sqlite:///{temporary_database.as_posix()}"
os.environ["DATABASE_URL"] = test_database_url
os.environ["APP_ENV"] = "test"
os.environ["STRIPE_MODE"] = "test"
os.environ["STRIPE_SECRET_KEY"] = ""
os.environ["STRIPE_PUBLISHABLE_KEY"] = ""
os.environ["STRIPE_WEBHOOK_SECRET"] = ""
os.environ["STRIPE_CONNECT_ENABLED"] = "false"
app_config.settings.DATABASE_URL = test_database_url
app_config.settings.APP_ENV = "test"
app_config.settings.STRIPE_MODE = "test"
app_config.settings.STRIPE_SECRET_KEY = ""
app_config.settings.STRIPE_PUBLISHABLE_KEY = ""
app_config.settings.STRIPE_WEBHOOK_SECRET = ""
app_config.settings.STRIPE_CONNECT_ENABLED = False

import struct
import zlib

import pytest
from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.core.rate_limit import reset_rate_limit_state
from app.core.security import create_access_token
from app.main import app
from app.models.user import User
from app.models.budget import UserBudget
from app.models.wallet import UserWallet

DEMO_EMAIL = "aisha@astra.ai"


@pytest.fixture(scope="session", autouse=True)
def seed_isolated_test_database():
    from app.db.seed import seed

    seed()


@pytest.fixture
def valid_png_bytes() -> bytes:
    """Build a CRC-correct 1x1 RGBA PNG for image validation tests."""
    def chunk(kind: bytes, data: bytes) -> bytes:
        checksum = zlib.crc32(kind + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", checksum)

    header = struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0)
    pixel = zlib.compress(b"\x00\xff\x00\x00\xff")
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", pixel) + chunk(b"IEND", b"")


@pytest.fixture(autouse=True)
def isolated_rate_limiter():
    reset_rate_limit_state()
    # Keep checkout tests independent even when a prior assertion aborts cleanup.
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == DEMO_EMAIL).first()
        if user:
            wallet = db.query(UserWallet).filter(UserWallet.user_id == user.id).first()
            if wallet:
                wallet.available_balance = 650_000
            budget = db.query(UserBudget).filter(UserBudget.user_id == user.id).first()
            if budget:
                budget.monthly_limit = 150_000
                budget.current_spent = 42_000
                budget.rollover_savings = 5_000
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
