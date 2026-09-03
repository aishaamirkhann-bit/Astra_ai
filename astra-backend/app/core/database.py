"""
SQLAlchemy engine + session factory + declarative Base.
Dev me SQLite chalta hai (zero setup), production me sirf DATABASE_URL
badal ke Postgres pe switch ho jayega — code kahin nahi badalna padega.
"""
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings


def resolve_database_url(database_url: str) -> str:
    """Resolve relative SQLite files from the backend root, not the shell cwd."""
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    sqlite_relative_prefix = "sqlite:///./"
    if not database_url.startswith(sqlite_relative_prefix):
        return database_url

    backend_root = Path(__file__).resolve().parents[2]
    relative_path = database_url.removeprefix(sqlite_relative_prefix)
    return f"sqlite:///{(backend_root / relative_path).as_posix()}"

database_url = resolve_database_url(settings.DATABASE_URL)
connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}

engine_options = {"pool_pre_ping": True}
if database_url.startswith("postgresql"):
    engine_options.update({"pool_size": 10, "max_overflow": 20, "pool_recycle": 1800})

engine = create_engine(database_url, connect_args=connect_args, **engine_options)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency — har request ke liye ek DB session deta hai aur end pe close karta hai."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
