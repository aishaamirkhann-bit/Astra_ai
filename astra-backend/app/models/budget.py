from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, Float, ForeignKey, Index, Integer, Text, UniqueConstraint

from app.core.database import Base


class UserBudget(Base):
    __tablename__ = "user_budgets"

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    monthly_limit = Column(Float, nullable=False, default=0)
    current_spent = Column(Float, nullable=False, default=0)
    rollover_savings = Column(Float, nullable=False, default=0)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        CheckConstraint("monthly_limit >= 0", name="ck_user_budget_monthly_limit"),
        CheckConstraint("current_spent >= 0", name="ck_user_budget_current_spent"),
        CheckConstraint("rollover_savings >= 0", name="ck_user_budget_rollover"),
    )


class ShoppingGoal(Base):
    __tablename__ = "shopping_goals"

    goal_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    target_title = Column(Text, nullable=False)
    target_price = Column(Float, nullable=False)
    saved_amount = Column(Float, nullable=False, default=0)
    category = Column(Text, nullable=False)
    priority_level = Column(Text, nullable=False, default="Medium")
    status = Column(Text, nullable=False, default="Active")
    deadline = Column(Text, nullable=True)
    image_url = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        CheckConstraint("target_price > 0", name="ck_shopping_goal_target_price"),
        CheckConstraint("saved_amount >= 0", name="ck_shopping_goal_saved_amount"),
        CheckConstraint("priority_level IN ('Low', 'Medium', 'High')", name="ck_shopping_goal_priority"),
        CheckConstraint("status IN ('Active', 'Completed', 'Paused')", name="ck_shopping_goal_status"),
        Index("ix_shopping_goals_user_status", "user_id", "status"),
    )


class BudgetAlert(Base):
    __tablename__ = "budget_alerts"

    alert_id = Column(Text, primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    goal_id = Column(Integer, ForeignKey("shopping_goals.goal_id", ondelete="CASCADE"), nullable=True)
    deal_id = Column(Text, ForeignKey("deals.id", ondelete="CASCADE"), nullable=True)
    alert_type = Column(Text, nullable=False)
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        CheckConstraint("alert_type IN ('Deal_Matched', 'Budget_Warning')", name="ck_budget_alert_type"),
        Index("ix_budget_alerts_user_created", "user_id", "created_at"),
        UniqueConstraint("user_id", "goal_id", "deal_id", "alert_type", name="uq_budget_alert_match"),
    )
