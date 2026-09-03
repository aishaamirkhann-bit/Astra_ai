from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Index, func
from sqlalchemy.orm import relationship
from app.core.database import Base


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    message = Column(String(300), nullable=False)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    owner = relationship("User", back_populates="notifications")

    __table_args__ = (Index("ix_notifications_user_created", "user_id", "created_at"),)
