from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, Text

from app.core.database import Base


class SellerVerification(Base):
    __tablename__ = "seller_verifications"

    seller_id = Column(Text, primary_key=True)
    seller_name = Column(Text, nullable=False, unique=True, index=True)
    business_name = Column(Text, nullable=False, default="")
    verification_status = Column(Text, nullable=False, default="pending")
    business_identity_verified = Column(Boolean, nullable=False, default=False)
    fulfillment_rate = Column(Float, nullable=False, default=0)
    return_rate = Column(Float, nullable=False, default=0)
    dispute_rate = Column(Float, nullable=False, default=0)
    trust_index = Column(Float, nullable=False, default=0)
    review_sentiment_score = Column(Float, nullable=False, default=0)
    price_stability_score = Column(Float, nullable=False, default=0)
    is_flagged = Column(Boolean, nullable=False, default=False)
    last_verified_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class TrustAuditLog(Base):
    __tablename__ = "trust_audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    audit_id = Column(Text, nullable=False, unique=True, index=True)
    product_id = Column(Text, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    seller_id = Column(Text, nullable=False, index=True)
    action = Column(Text, nullable=False)
    previous_score = Column(Float, nullable=True)
    computed_score = Column(Float, nullable=False)
    final_score = Column(Float, nullable=False)
    calculated_trust_score = Column(Float, nullable=False)
    authenticity_flag = Column(Boolean, nullable=False, default=False)
    price_anomaly_detected = Column(Boolean, nullable=False, default=False)
    reasoning_summary = Column(Text, nullable=False, default="")
    components = Column(JSON, nullable=False)
    reason = Column(Text, nullable=False, default="Automated ASTRA inspection")
    actor_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
    inspected_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), index=True)


class PlatformTrustMetric(Base):
    __tablename__ = "platform_trust_metrics"

    id = Column(Integer, primary_key=True, default=1)
    verified_sellers_count = Column(Integer, nullable=False, default=0)
    flagged_listings_count = Column(Integer, nullable=False, default=0)
    avg_trust_score = Column(Float, nullable=False, default=0)
    active_ai_scans = Column(Integer, nullable=False, default=0)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
