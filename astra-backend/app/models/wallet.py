from sqlalchemy import Column, Integer, Float, String, ForeignKey, DateTime, func
from sqlalchemy.orm import relationship
from app.core.database import Base


class Wallet(Base):
    __tablename__ = "wallets"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    available_balance = Column(Float, default=0)   # "Available to spend" on GoalsWalletRail

    owner = relationship("User", back_populates="wallet")
    ledger_entries = relationship("WalletLedgerEntry", back_populates="wallet")


class WalletLedgerEntry(Base):
    __tablename__ = "wallet_ledger_entries"

    id = Column(Integer, primary_key=True, index=True)
    wallet_id = Column(Integer, ForeignKey("wallets.id"), nullable=False)
    label = Column(String(200), nullable=False)
    amount = Column(Float, nullable=False)          # positive = credit, negative = debit
    entry_type = Column(String(10), nullable=False)  # "credit" | "debit"
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    wallet = relationship("Wallet", back_populates="ledger_entries")
