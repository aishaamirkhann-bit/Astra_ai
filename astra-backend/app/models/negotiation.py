from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import relationship

from app.core.database import Base


class NegotiationSession(Base):
    __tablename__ = "negotiation_sessions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = Column(String, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="active", index=True)
    final_price = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    rounds = relationship("NegotiationRound", back_populates="session", cascade="all, delete-orphan")


class NegotiationRound(Base):
    __tablename__ = "negotiation_rounds"

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("negotiation_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    round_number = Column(Integer, nullable=False)
    buyer_offer = Column(Float, nullable=False)
    seller_ask = Column(Float, nullable=False)
    counter_offer = Column(Float, nullable=True)
    status = Column(String(20), nullable=False)
    provider = Column(String(20), nullable=False, default="rules")
    reasoning_json = Column(Text, nullable=False, default="[]")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    session = relationship("NegotiationSession", back_populates="rounds")
