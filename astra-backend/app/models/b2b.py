from datetime import datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from app.core.database import Base


class B2BBid(Base):
    __tablename__ = "b2b_bids"

    id = Column(Integer, primary_key=True, autoincrement=True)
    buyer_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(160), nullable=False)
    description = Column(Text, nullable=False, default="")
    category = Column(String(80), nullable=False)
    quantity = Column(Integer, nullable=False)
    target_budget = Column(Float, nullable=False)
    delivery_days = Column(Integer, nullable=False)
    status = Column(String(20), nullable=False, default="open", server_default="open")
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    closes_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_b2b_bid_quantity"),
        CheckConstraint("target_budget > 0", name="ck_b2b_bid_target_budget"),
        CheckConstraint("delivery_days > 0", name="ck_b2b_bid_delivery_days"),
        CheckConstraint("status IN ('open', 'awarded', 'cancelled', 'closed')", name="ck_b2b_bid_status"),
        Index("ix_b2b_bids_status_created", "status", "created_at"),
    )


class VendorQuote(Base):
    __tablename__ = "vendor_quotes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    bid_id = Column(Integer, ForeignKey("b2b_bids.id", ondelete="CASCADE"), nullable=False, index=True)
    vendor_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    offered_price = Column(Float, nullable=False)
    delivery_days = Column(Integer, nullable=False)
    ai_match_score = Column(Float, nullable=False, default=0)
    commission_rate = Column(Float, nullable=False)
    commission_amount = Column(Float, nullable=False)
    vendor_net_payout = Column(Float, nullable=False)
    is_featured = Column(Boolean, nullable=False, default=False, server_default="false")
    status = Column(String(20), nullable=False, default="submitted", server_default="submitted")
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    bid = relationship("B2BBid")
    vendor = relationship("User")

    __table_args__ = (
        CheckConstraint("offered_price > 0", name="ck_vendor_quote_price"),
        CheckConstraint("delivery_days > 0", name="ck_vendor_quote_delivery_days"),
        CheckConstraint("ai_match_score >= 0 AND ai_match_score <= 100", name="ck_vendor_quote_match_score"),
        CheckConstraint("commission_rate >= 0.01 AND commission_rate <= 0.02", name="ck_vendor_quote_commission_rate"),
        CheckConstraint("commission_amount >= 0 AND vendor_net_payout >= 0", name="ck_vendor_quote_commission_amounts"),
        CheckConstraint("status IN ('submitted', 'awarded', 'declined', 'withdrawn')", name="ck_vendor_quote_status"),
        UniqueConstraint("bid_id", "vendor_id", name="uq_vendor_quote_bid_vendor"),
        Index("ix_vendor_quotes_bid_score", "bid_id", "ai_match_score"),
    )


class DistributionLedger(Base):
    __tablename__ = "distribution_ledger"

    id = Column(Integer, primary_key=True, autoincrement=True)
    distributor_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    retailer_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = Column(Text, ForeignKey("products.id", ondelete="SET NULL"), nullable=True, index=True)
    entry_type = Column(String(24), nullable=False, default="sale", server_default="sale")
    platform_commission_rate = Column(Float, nullable=False, default=0.01)
    commission_amount = Column(Float, nullable=False, default=0)
    credit_amount = Column(Float, nullable=False, default=0)
    khata_amount = Column(Float, nullable=False, default=0)
    credit_limit = Column(Float, nullable=False, default=0)
    reference = Column(String(120), nullable=False, default="")
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        CheckConstraint("platform_commission_rate >= 0.01 AND platform_commission_rate <= 0.02", name="ck_distribution_commission_rate"),
        CheckConstraint("entry_type IN ('sale', 'repayment')", name="ck_distribution_entry_type"),
        CheckConstraint("commission_amount >= 0 AND credit_amount >= 0 AND khata_amount >= 0 AND credit_limit >= 0", name="ck_distribution_nonnegative_amounts"),
        Index("ix_distribution_retailer_created", "retailer_id", "created_at"),
    )


class VendorSubscription(Base):
    __tablename__ = "vendor_subscriptions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    vendor_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    tier = Column(String(20), nullable=False)
    monthly_price = Column(Float, nullable=False)
    status = Column(String(20), nullable=False, default="pending_payment", server_default="pending_payment")
    started_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    ended_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint("tier IN ('Basic', 'Pro', 'Enterprise')", name="ck_vendor_subscription_tier"),
        CheckConstraint("monthly_price >= 0", name="ck_vendor_subscription_price"),
        CheckConstraint("status IN ('active', 'pending_payment', 'cancelled')", name="ck_vendor_subscription_status"),
        Index("ix_vendor_subscription_vendor_status", "vendor_id", "status"),
    )
