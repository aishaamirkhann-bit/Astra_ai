from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint

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


class StripeCheckoutPayment(Base):
    """External card payment state for an ASTRA checkout session."""

    __tablename__ = "stripe_checkout_payments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    stripe_session_id = Column(String(255), nullable=False, unique=True, index=True)
    checkout_session_id = Column(Integer, ForeignKey("checkout_sessions.id", ondelete="CASCADE"), nullable=False, unique=True)
    checkout_url = Column(Text, nullable=False)
    amount = Column(Float, nullable=False)
    status = Column(String(24), nullable=False, default="pending")
    payment_intent_id = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    paid_at = Column(DateTime(timezone=True), nullable=True)


class StripeRefund(Base):
    """Stripe refunds associated with an order or a late-paid checkout."""

    __tablename__ = "stripe_refunds"

    refund_id = Column(String(255), primary_key=True)
    stripe_checkout_payment_id = Column(Integer, ForeignKey("stripe_checkout_payments.id", ondelete="CASCADE"), nullable=False, index=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="SET NULL"), nullable=True, index=True)
    amount_paisa = Column(Integer, nullable=False)
    status = Column(String(32), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class StripeWebhookEvent(Base):
    """Processed Stripe event ids prevent duplicate settlement work."""

    __tablename__ = "stripe_webhook_events"

    event_id = Column(String(255), primary_key=True)
    event_type = Column(String(120), nullable=False)
    received_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class StripeConnectAccount(Base):
    __tablename__ = "stripe_connect_accounts"

    seller_user_id = Column(Integer, ForeignKey("seller_profiles.user_id", ondelete="CASCADE"), primary_key=True)
    stripe_account_id = Column(String(255), nullable=False, unique=True)
    details_submitted = Column(Integer, nullable=False, default=0)
    charges_enabled = Column(Integer, nullable=False, default=0)
    payouts_enabled = Column(Integer, nullable=False, default=0)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class SellerPayoutLedger(Base):
    """One internal payout calculation per paid order, independent of buyer funds."""

    __tablename__ = "seller_payout_ledger"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, unique=True)
    seller_user_id = Column(Integer, ForeignKey("seller_profiles.user_id", ondelete="SET NULL"), nullable=True, index=True)
    seller_key = Column(String(160), nullable=False)
    gross_amount = Column(Float, nullable=False)
    platform_fee = Column(Float, nullable=False)
    seller_amount = Column(Float, nullable=False)
    status = Column(String(32), nullable=False, default="queued")
    stripe_transfer_id = Column(String(255), nullable=True)
    transfer_attempts = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (UniqueConstraint("order_id", name="uq_seller_payout_order"),)
