"""
SQLAlchemy engine + session factory + declarative Base.
Dev me SQLite chalta hai (zero setup), production me sirf DATABASE_URL
badal ke Postgres pe switch ho jayega — code kahin nahi badalna padega.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings

connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(settings.DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency — har request ke liye ek DB session deta hai aur end pe close karta hai."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
