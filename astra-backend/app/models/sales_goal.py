from sqlalchemy import CheckConstraint, Column, Float, ForeignKey, Integer, String

from app.core.database import Base


class SalesGoal(Base):
    __tablename__ = "seller_sales_goals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    seller_id = Column(Integer, ForeignKey("seller_profiles.user_id", ondelete="CASCADE"), nullable=False, index=True)
    source_goal_id = Column(Integer, ForeignKey("goals.id", ondelete="SET NULL"), nullable=True, unique=True)
    target_title = Column(String(100), nullable=False)
    target_amount = Column(Float, nullable=False)
    current_amount = Column(Float, nullable=False, default=0)
    deadline = Column(String(20), nullable=True)

    __table_args__ = (
        CheckConstraint("target_amount > 0", name="ck_seller_sales_goal_target"),
        CheckConstraint("current_amount >= 0", name="ck_seller_sales_goal_current"),
    )
