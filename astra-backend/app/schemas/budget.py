from typing import Literal

from pydantic import BaseModel, Field


class BudgetOut(BaseModel):
    monthly_limit: float
    current_spent: float
    rollover_savings: float
    available_safe_balance: float
    spending_percent: float
    active_goals: int
    total_goal_savings: float
    total_ai_deal_savings: float


class BudgetUpdate(BaseModel):
    monthly_limit: float = Field(gt=0)
    current_spent: float | None = Field(default=None, ge=0)
    rollover_savings: float | None = Field(default=None, ge=0)


class ShoppingGoalCreate(BaseModel):
    target_title: str = Field(min_length=2, max_length=160)
    target_price: float = Field(gt=0)
    category: str = Field(min_length=2, max_length=80)
    priority_level: Literal["Low", "Medium", "High"] = "Medium"
    deadline: str | None = None


class ShoppingGoalUpdate(BaseModel):
    target_price: float | None = Field(default=None, gt=0)
    deposit_amount: float | None = Field(default=None, gt=0)
    status: Literal["Active", "Completed", "Paused"] | None = None
    priority_level: Literal["Low", "Medium", "High"] | None = None
    deadline: str | None = None


class ShoppingGoalOut(BaseModel):
    goal_id: int
    target_title: str
    target_price: float
    saved_amount: float
    remaining_amount: float
    percent_funded: float
    category: str
    priority_level: str
    status: str
    deadline: str | None
    image_url: str | None


class BudgetAlertOut(BaseModel):
    alert_id: str
    goal_id: int | None
    deal_id: str | None
    alert_type: Literal["Deal_Matched", "Budget_Warning"]
    message: str
    created_at: str


class MatchedDealOut(BaseModel):
    deal_id: str
    goal_id: int
    product_id: str
    product_name: str
    image: str
    category: str
    listing_price: float
    target_price: float
    saved_amount: float
    savings_vs_target: float
    trust_score: float
    within_monthly_budget: bool
    can_buy_with_allocated_savings: bool
    suggested_installment: float | None
    alert_type: Literal["Deal_Matched", "Budget_Warning"]
    message: str


class RestockForecastOut(BaseModel):
    product_id: str | None = None
    product_name: str
    image: str | None = None
    category: str | None = None
    last_purchased: str | None = None
    avg_interval_days: int
    predicted_next_date: str
    days_until_restock: int
    confidence: float
    estimated_price: float
    message: str


class BudgetDashboardOut(BaseModel):
    budget: BudgetOut
    goals: list[ShoppingGoalOut]
    alerts: list[BudgetAlertOut]
    restock_forecasts: list[RestockForecastOut] = Field(default_factory=list)
