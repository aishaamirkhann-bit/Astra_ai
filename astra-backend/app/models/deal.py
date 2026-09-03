from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Index, Integer, JSON, Text, UniqueConstraint

from app.core.database import Base


def _uuid() -> str:
    return str(uuid4())


class SellerMetric(Base):
    __tablename__ = "seller_metrics"

    seller_id = Column(Text, primary_key=True)
    seller_name = Column(Text, nullable=False, unique=True)
    seller_rating = Column(Float, nullable=False)
    fulfillment_rate = Column(Float, nullable=False)
    authenticity_sentiment = Column(Float, nullable=False)
    price_stability = Column(Float, nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class MarketPriceHistory(Base):
    __tablename__ = "market_price_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Text, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    competitor = Column(Text, nullable=False)
    price = Column(Float, nullable=False)
    observed_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), index=True)

    __table_args__ = (Index("ix_market_price_product_observed", "product_id", "observed_at"),)


class Deal(Base):
    __tablename__ = "deals"

    id = Column(Text, primary_key=True, default=_uuid)
    product_id = Column(Text, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    listing_price = Column(Float, nullable=False)
    market_avg_price = Column(Float, nullable=False)
    discount_pct = Column(Float, nullable=False)
    trust_score = Column(Float, nullable=False)
    seller_fulfillment_score = Column(Float, nullable=False)
    authenticity_sentiment_score = Column(Float, nullable=False)
    price_stability_score = Column(Float, nullable=False)
    badge_type = Column(Text, nullable=False)
    stock_remaining = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True)
    deal_expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_deals_active_trust_discount", "is_active", "trust_score", "discount_pct"),
    )


class DealReservation(Base):
    __tablename__ = "deal_reservations"

    id = Column(Text, primary_key=True, default=_uuid)
    deal_id = Column(Text, ForeignKey("deals.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    quantity = Column(Integer, nullable=False)
    status = Column(Text, nullable=False, default="reserved")
    reserved_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime(timezone=True), nullable=False)
    size = Column(Text, nullable=False, default="")
    color = Column(Text, nullable=False, default="")

    __table_args__ = (UniqueConstraint("id", "deal_id", name="uq_deal_reservation_id_deal"),)


class DealAuditLog(Base):
    __tablename__ = "deal_audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    deal_id = Column(Text, ForeignKey("deals.id", ondelete="SET NULL"), nullable=True, index=True)
    product_id = Column(Text, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(Text, nullable=False)
    decision = Column(Text, nullable=False)
    reasoning = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), index=True)

    __table_args__ = (Index("ix_deal_audit_product_created", "product_id", "created_at"),)
