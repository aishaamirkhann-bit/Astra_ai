from sqlalchemy import CheckConstraint, Column, DateTime, Float, ForeignKey, Integer, String, Text, func

from app.core.database import Base


class ShoppingPreference(Base):
    """Small, user-scoped set of explicit shopping preferences, not chat history."""

    __tablename__ = "shopping_preferences"
    __table_args__ = (
        CheckConstraint(
            "budget_min IS NULL OR budget_max IS NULL OR budget_min <= budget_max",
            name="ck_shopping_preferences_budget_range",
        ),
    )

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    clothing_size = Column(String(16), nullable=True)
    favorite_color = Column(String(32), nullable=True)
    preferred_category = Column(String(80), nullable=True)
    budget_min = Column(Float, nullable=True)
    budget_max = Column(Float, nullable=True)
    shopping_preferences_json = Column(Text, nullable=False, default="[]")
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
