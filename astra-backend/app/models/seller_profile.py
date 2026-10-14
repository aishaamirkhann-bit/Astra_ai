from sqlalchemy import CheckConstraint, Column, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.core.database import Base


class SellerProfile(Base):
    __tablename__ = "seller_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    role = Column(String(10), nullable=False, default="seller", server_default="seller")
    trust_score = Column(Float, nullable=True)
    compliance_status = Column(String(24), nullable=False, default="pending", server_default="pending")
    authenticity_score = Column(Float, nullable=True)
    total_revenue = Column(Float, nullable=False, default=0, server_default="0")

    user = relationship("User")
    __table_args__ = (
        CheckConstraint("role = 'seller'", name="ck_seller_profile_role"),
        CheckConstraint("total_revenue >= 0", name="ck_seller_profile_revenue"),
    )
