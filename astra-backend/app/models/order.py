import enum
from sqlalchemy import Column, Integer, Float, String, Text, ForeignKey, DateTime, Enum, func
from sqlalchemy.orm import relationship
from app.core.database import Base


class OrderStatus(str, enum.Enum):
    PENDING_APPROVAL = "pending_approval"          # HumanApprovalWidget shows the countdown
    REVERSAL_WINDOW_OPEN = "reversal_window_open"  # approved, but still cancellable
    CONFIRMED = "confirmed"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    order_ref = Column(String(30), unique=True, nullable=False)   # "ORD-88213"
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    product_id = Column(Text, ForeignKey("products.id"), nullable=False)  # text now, matches products.id
    reservation_id = Column(Text, ForeignKey("deal_reservations.id"), nullable=True, unique=True)
    quantity = Column(Integer, nullable=False, default=1)
    size = Column(Text, nullable=False, default="")
    color = Column(Text, nullable=False, default="")
    storage = Column(Text, nullable=False, default="")
    price = Column(Float, nullable=False)
    checkout_session_id = Column(Integer, ForeignKey("checkout_sessions.id", ondelete="SET NULL"), nullable=True, index=True)
    status = Column(Enum(OrderStatus), default=OrderStatus.PENDING_APPROVAL)
    # Escrow lifecycle: HELD while funds sit in reversible checkout,
    # RELEASED to the seller once confirmed, REFUNDED on reversal/dispute.
    escrow_status = Column(String(20), nullable=False, default="HELD", server_default="HELD")

    # Reversible checkout window bookkeeping
    approval_deadline = Column(DateTime(timezone=True), nullable=True)
    reversal_deadline = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    shipped_at = Column(DateTime(timezone=True), nullable=True)
    delivered_at = Column(DateTime(timezone=True), nullable=True)

    owner = relationship("User", back_populates="orders")
    product = relationship("Product")
    checkout_session = relationship("CheckoutSession", back_populates="orders")
