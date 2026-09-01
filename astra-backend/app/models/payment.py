from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, Text

from app.core.database import Base


class CardTopUp(Base):
    """Stripe PaymentIntents that credit the wallet once settled (idempotent webhook)."""

    __tablename__ = "card_topups"

    intent_id = Column(Text, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    amount = Column(Float, nullable=False)
    status = Column(Text, nullable=False, default="requires_payment")
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    settled_at = Column(DateTime(timezone=True), nullable=True)
