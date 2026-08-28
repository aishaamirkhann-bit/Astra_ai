import enum
from sqlalchemy import Column, Integer, Float, String, Text, ForeignKey, DateTime, Enum, func
from sqlalchemy.orm import relationship
from app.core.database import Base


class OrderStatus(str, enum.Enum):
    PENDING_APPROVAL = "pending_approval"          # HumanApprovalWidget shows the countdown
    REVERSAL_WINDOW_OPEN = "reversal_window_open"  # approved, but still cancellable
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    order_ref = Column(String(30), unique=True, nullable=False)   # "ORD-88213"
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    product_id = Column(Text, ForeignKey("products.id"), nullable=False)  # text now, matches products.id
    price = Column(Float, nullable=False)
    status = Column(Enum(OrderStatus), default=OrderStatus.PENDING_APPROVAL)

    # Reversible checkout window bookkeeping
    approval_deadline = Column(DateTime(timezone=True), nullable=True)
    reversal_deadline = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    owner = relationship("User", back_populates="orders")
    product = relationship("Product")
