from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func

from app.core.database import Base


class OrderReturnRequest(Base):
    __tablename__ = "order_return_requests"

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    request_type = Column(String(16), nullable=False, default="return", server_default="return")
    reason = Column(Text, nullable=False)
    status = Column(String(24), nullable=False, default="pending_review", server_default="pending_review")
    requested_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
