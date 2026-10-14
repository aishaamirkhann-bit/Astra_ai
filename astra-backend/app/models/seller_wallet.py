from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import CheckConstraint, Column, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import relationship

from app.core.database import Base


class SellerWallet(Base):
    """Seller-only settlement balance; never aliases the buyer UserWallet."""

    __tablename__ = "seller_wallets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    seller_id = Column(Integer, ForeignKey("seller_profiles.user_id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    available_balance = Column(Float, nullable=False, default=0, server_default="0")
    pending_payouts = Column(Float, nullable=False, default=0, server_default="0")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    ledger_entries = relationship("SellerWalletEntry", back_populates="wallet", cascade="all, delete-orphan")
    __table_args__ = (
        CheckConstraint("available_balance >= 0", name="ck_seller_wallet_available_balance"),
        CheckConstraint("pending_payouts >= 0", name="ck_seller_wallet_pending_payouts"),
    )


class SellerWalletEntry(Base):
    __tablename__ = "seller_wallet_entries"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    seller_wallet_id = Column(Integer, ForeignKey("seller_wallets.id", ondelete="CASCADE"), nullable=False, index=True)
    amount = Column(Float, nullable=False)
    entry_type = Column(String(24), nullable=False)
    description = Column(String(240), nullable=False)
    reference = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), index=True)

    wallet = relationship("SellerWallet", back_populates="ledger_entries")
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_seller_wallet_entry_amount"),
        CheckConstraint(
            "entry_type IN ('sale_credit', 'payout_requested', 'payout_paid', 'adjustment')",
            name="ck_seller_wallet_entry_type",
        ),
    )
