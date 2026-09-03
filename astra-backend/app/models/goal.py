from sqlalchemy import Column, Integer, Float, String, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base


class Goal(Base):
    __tablename__ = "goals"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(100), nullable=False)      # e.g. "Laptop Goal"
    target_amount = Column(Float, nullable=False)
    allocated_amount = Column(Float, default=0)

    deadline = Column(String(20), nullable=True)          # ISO date, e.g. "2026-12-31"
    cadence_amount = Column(Float, nullable=True)          # e.g. 8000
    cadence_period = Column(String(10), nullable=True)     # "weekly" | "monthly"

    owner = relationship("User", back_populates="goals")

    @property
    def remaining_amount(self) -> float:
        return max(self.target_amount - self.allocated_amount, 0)

    @property
    def percent_funded(self) -> float:
        if self.target_amount <= 0:
            return 0
        return round((self.allocated_amount / self.target_amount) * 100, 1)
