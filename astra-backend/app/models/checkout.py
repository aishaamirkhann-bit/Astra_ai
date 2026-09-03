from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import CheckConstraint, Column, DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import relationship

from app.core.database import Base


class CheckoutSession(Base):
    __tablename__ = "checkout_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    checkout_ref = Column(String(40), unique=True, nullable=False, default=lambda: f"CHK-{uuid4().hex[:16].upper()}")
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    total = Column(Float, nullable=False)
    shipping_address = Column(String(500), nullable=False)
    status = Column(String(30), nullable=False, default="awaiting_consent")
    expires_at = Column(DateTime(timezone=True), nullable=False)
    confirmed_at = Column(DateTime(timezone=True), nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    owner = relationship("User", back_populates="checkout_sessions")
    orders = relationship("Order", back_populates="checkout_session")

    __table_args__ = (
        CheckConstraint("total > 0", name="ck_checkout_session_total"),
        CheckConstraint(
            "status IN ('awaiting_consent', 'reversal_window_open', 'confirmed', 'cancelled', 'expired')",
            name="ck_checkout_session_status",
        ),
        Index("ix_checkout_sessions_user_status", "user_id", "status"),
        Index("ix_checkout_sessions_expires_at", "expires_at"),
    )
