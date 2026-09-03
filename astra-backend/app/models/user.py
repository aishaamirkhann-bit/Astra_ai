from sqlalchemy import Column, Integer, String, DateTime, Boolean, func
from sqlalchemy.orm import relationship

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(80), nullable=False)              # Authenticated display name shown in TopBar
    email = Column(String(120), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    preferred_language = Column(String(20), default="Roman Urdu")  # English / اردو / Roman Urdu

    # --- Dynamic role, chosen by the user at signup ---
    # "buyer" | "seller" today; kept as a free string (not a DB enum) so a
    # new role can be added later without an Alembic enum migration.
    role = Column(String(20), nullable=False, default="buyer", index=True)

    # --- Email OTP (2FA) ---
    is_active = Column(Boolean, default=True)
    otp_code_hash = Column(String(255), nullable=True)       # never store the raw code
    otp_expires_at = Column(DateTime(timezone=True), nullable=True)
    otp_attempts = Column(Integer, default=0)                # brute-force guard per OTP

    # --- Password reset OTP (separate from login OTP on purpose) ---
    reset_code_hash = Column(String(255), nullable=True)
    reset_expires_at = Column(DateTime(timezone=True), nullable=True)
    reset_attempts = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    wallet = relationship("UserWallet", back_populates="owner", uselist=False)
    goals = relationship("Goal", back_populates="owner")
    orders = relationship("Order", back_populates="owner")
    checkout_sessions = relationship("CheckoutSession", back_populates="owner")
    notifications = relationship("Notification", back_populates="owner")
