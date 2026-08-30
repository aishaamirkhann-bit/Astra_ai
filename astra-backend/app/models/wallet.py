from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import CheckConstraint, Column, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship, synonym
from app.core.database import Base


class UserWallet(Base):
    __tablename__ = "user_wallets"

    wallet_id = Column(Integer, primary_key=True, autoincrement=True)
    id = synonym("wallet_id")
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    currency = Column(String(3), nullable=False, default="PKR")
    available_balance = Column(Float, nullable=False, default=0)
    frozen_balance = Column(Float, nullable=False, default=0)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    owner = relationship("User", back_populates="wallet")
    ledger_entries = relationship("WalletTransaction", back_populates="wallet", cascade="all, delete-orphan")
    __table_args__ = (
        CheckConstraint("available_balance >= 0", name="ck_wallet_available_balance"),
        CheckConstraint("frozen_balance >= 0", name="ck_wallet_frozen_balance"),
    )


class WalletTransaction(Base):
    __tablename__ = "wallet_transactions"

    txn_id = Column(Text, primary_key=True, default=lambda: str(uuid4()))
    wallet_id = Column(Integer, ForeignKey("user_wallets.wallet_id", ondelete="CASCADE"), nullable=False)
    amount = Column(Float, nullable=False)
    txn_type = Column(String(10), nullable=False)
    description = Column(String(240), nullable=False)
    reference_order_id = Column(Integer, ForeignKey("orders.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    wallet = relationship("UserWallet", back_populates="ledger_entries")
    id = synonym("txn_id")

    @property
    def label(self) -> str:
        return self.description

    @property
    def entry_type(self) -> str:
        return "credit" if self.txn_type in {"Credit", "Refund"} else "debit"

    @property
    def transaction_type(self) -> str:
        return self.txn_type

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_wallet_transaction_amount"),
        CheckConstraint("txn_type IN ('Credit', 'Debit', 'Refund')", name="ck_wallet_transaction_type"),
        Index("ix_wallet_transactions_wallet_created", "wallet_id", "created_at"),
        UniqueConstraint("reference_order_id", "txn_type", name="uq_wallet_order_transaction_type"),
    )


class FinancialConsentLog(Base):
    __tablename__ = "financial_consent_logs"

    consent_id = Column(Text, primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    amount = Column(Float, nullable=False)
    auth_method = Column(String(10), nullable=False)
    voice_transcript = Column(Text, nullable=True)
    status = Column(String(10), nullable=False)
    reference_order_id = Column(Integer, ForeignKey("orders.id", ondelete="SET NULL"), nullable=True)
    otp_code_hash = Column(Text, nullable=True)
    otp_expires_at = Column(DateTime(timezone=True), nullable=True)
    otp_attempts = Column(Integer, nullable=False, default=0)
    consumed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_financial_consent_amount"),
        CheckConstraint("auth_method IN ('Voice', 'OTP')", name="ck_financial_consent_method"),
        CheckConstraint("status IN ('Approved', 'Rejected', 'Flagged')", name="ck_financial_consent_status"),
        Index("ix_financial_consent_user_created", "user_id", "created_at"),
        Index("ix_financial_consent_order_status", "reference_order_id", "status", "consumed_at"),
    )


Wallet = UserWallet
WalletLedgerEntry = WalletTransaction
