from datetime import datetime, timezone
from math import ceil

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.budget import BudgetAlert, ShoppingGoal, UserBudget
from app.models.deal import Deal
from app.models.goal import Goal
from app.models.order import Order, OrderStatus
from app.models.product import Product
from app.models.user import User
from app.models.wallet import WalletLedgerEntry
from app.schemas.budget import BudgetAlertOut, BudgetDashboardOut, BudgetOut, MatchedDealOut, SavingPlanOut, ShoppingGoalCreate, ShoppingGoalOut, ShoppingGoalUpdate
from app.services import astra_agents
from app.services.deals_pipeline import CATEGORY_MAP


def _goal_out(goal: ShoppingGoal) -> ShoppingGoalOut:
    remaining = max(goal.target_price - goal.saved_amount, 0)
    return ShoppingGoalOut(
        goal_id=goal.goal_id, target_title=goal.target_title, target_price=goal.target_price,
        saved_amount=goal.saved_amount, remaining_amount=remaining,
        percent_funded=round(min(goal.saved_amount / goal.target_price * 100, 100), 1),
        category=goal.category, priority_level=goal.priority_level, status=goal.status,
        deadline=goal.deadline, image_url=goal.image_url,
    )


def ensure_budget_profile(db: Session, user: User) -> UserBudget:
    budget = db.get(UserBudget, user.id)
    if budget is None:
        budget = UserBudget(user_id=user.id, monthly_limit=50000, current_spent=32000, rollover_savings=0)
        db.add(budget); db.flush()
    existing = db.scalar(select(func.count()).select_from(ShoppingGoal).where(ShoppingGoal.user_id == user.id)) or 0
    if existing == 0:
        legacy = db.scalars(select(Goal).where(Goal.user_id == user.id)).all()
        for goal in legacy:
            db.add(ShoppingGoal(
                user_id=user.id, target_title=goal.name, target_price=goal.target_amount,
                saved_amount=goal.allocated_amount, category="Tech", priority_level="Medium",
                status="Completed" if goal.allocated_amount >= goal.target_amount else "Active",
                deadline=goal.deadline,
            ))
    db.commit(); db.refresh(budget)
    return budget


def create_shopping_goal(db: Session, user: User, payload: ShoppingGoalCreate) -> ShoppingGoalOut:
    ensure_budget_profile(db, user)
    goal = ShoppingGoal(user_id=user.id, **payload.model_dump())
    db.add(goal); db.commit(); db.refresh(goal)
    return _goal_out(goal)


def update_shopping_goal(db: Session, user: User, goal_id: int, payload: ShoppingGoalUpdate) -> ShoppingGoalOut:
    goal = db.scalar(select(ShoppingGoal).where(ShoppingGoal.goal_id == goal_id, ShoppingGoal.user_id == user.id))
    if not goal:
        raise HTTPException(status_code=404, detail="Shopping goal not found")
    values = payload.model_dump(exclude_unset=True)
    deposit = values.pop("deposit_amount", None)
    if deposit:
        if not user.wallet or deposit > user.wallet.available_balance:
            raise HTTPException(status_code=409, detail="Deposit exceeds available wallet balance")
        user.wallet.available_balance -= deposit
        goal.saved_amount = min(goal.saved_amount + deposit, goal.target_price)
        db.add(WalletLedgerEntry(wallet_id=user.wallet.id, description=f"Goal deposit - {goal.target_title}", amount=deposit, txn_type="Debit"))
    for field, value in values.items():
        setattr(goal, field, value)
    if goal.saved_amount >= goal.target_price:
        goal.status = "Completed"
    db.commit(); db.refresh(goal)
    return _goal_out(goal)


def _active_matches(db: Session, user_id: int) -> list[tuple[ShoppingGoal, Deal, Product]]:
    goals = db.scalars(select(ShoppingGoal).where(ShoppingGoal.user_id == user_id, ShoppingGoal.status == "Active")).all()
    deals = db.execute(select(Deal, Product).join(Product, Product.id == Deal.product_id).where(Deal.is_active.is_(True), Deal.trust_score >= 75)).all()
    matches = []
    for goal in goals:
        for deal, product in deals:
            category = CATEGORY_MAP.get(product.category, product.category)
            if category.casefold() == goal.category.casefold() and deal.listing_price <= goal.target_price:
                matches.append((goal, deal, product))
    return matches


def evaluate_user_matches(db: Session, user: User) -> list[MatchedDealOut]:
    budget = ensure_budget_profile(db, user)
    output: list[MatchedDealOut] = []
    for goal, deal, product in _active_matches(db, user.id):
        if not goal.image_url and product.image_url:
            goal.image_url = product.image_url
        over_budget = budget.current_spent + deal.listing_price > budget.monthly_limit
        installment = round(deal.listing_price / max(1, min(12, int(deal.listing_price / max(budget.monthly_limit - budget.current_spent, 1)) + 1)), 2) if over_budget else None
        alert_type = "Budget_Warning" if over_budget else "Deal_Matched"
        saving = max(goal.target_price - deal.listing_price, 0)
        message = (f"{product.title} matches your {goal.category} goal. Save Rs. {saving:,.0f}." if not over_budget else f"{product.title} matches your goal, but exceeds this month's safe balance. Suggested installment: Rs. {installment:,.0f}.")
        alerts_to_create = [("Deal_Matched", f"{product.title} dropped into your {goal.category} budget! Save Rs. {saving:,.0f}.")]
        if over_budget:
            alerts_to_create.append(("Budget_Warning", message))
        for kind, text in alerts_to_create:
            if not db.scalar(select(BudgetAlert).where(BudgetAlert.user_id == user.id, BudgetAlert.goal_id == goal.goal_id, BudgetAlert.deal_id == deal.id, BudgetAlert.alert_type == kind)):
                db.add(BudgetAlert(user_id=user.id, goal_id=goal.goal_id, deal_id=deal.id, alert_type=kind, message=text))
        output.append(MatchedDealOut(
            deal_id=deal.id, goal_id=goal.goal_id, product_id=product.id, product_name=product.title,
            image=product.image_url, category=goal.category, listing_price=deal.listing_price,
            target_price=goal.target_price, saved_amount=goal.saved_amount,
            savings_vs_target=saving, trust_score=deal.trust_score,
            within_monthly_budget=not over_budget,
            can_buy_with_allocated_savings=goal.saved_amount >= deal.listing_price,
            suggested_installment=installment, alert_type=alert_type, message=message,
        ))
    try: db.commit()
    except IntegrityError: db.rollback()
    return output


def _restock_forecasts(db: Session, user: User) -> list[dict]:
    orders = (
        db.scalars(
            select(Order)
            .where(Order.user_id == user.id, Order.status != OrderStatus.CANCELLED)
            .order_by(Order.created_at.desc())
            .limit(10)
        )
        .all()
    )
    fallback = []
    if not orders:
        try:
            from app.repository import product_repository

            catalog = sorted(product_repository.list_products(), key=lambda item: item["price"])
            fallback = [item for item in catalog if item["price"] <= 60000][:2]
        except Exception:
            fallback = []
    return astra_agents.restock_forecasts(orders, fallback)


def saving_plan(budget: UserBudget, goals: list[ShoppingGoal]) -> SavingPlanOut:
    remaining = round(sum(max(goal.target_price - goal.saved_amount, 0) for goal in goals if goal.status == "Active"), 2)
    capacity = max(budget.monthly_limit + budget.rollover_savings - budget.current_spent, 0)
    return SavingPlanOut(
        remaining_goal_amount=remaining,
        monthly_saving_capacity=capacity,
        recommended_monthly_deposit=min(remaining, capacity),
        estimated_months_to_fund=0 if remaining == 0 else ceil(remaining / capacity) if capacity else None,
    )


def budget_dashboard(db: Session, user: User) -> BudgetDashboardOut:
    budget = ensure_budget_profile(db, user)
    matches = evaluate_user_matches(db, user)
    goals = db.scalars(select(ShoppingGoal).where(ShoppingGoal.user_id == user.id).order_by(ShoppingGoal.created_at.desc())).all()
    alerts = db.scalars(select(BudgetAlert).where(BudgetAlert.user_id == user.id).order_by(BudgetAlert.created_at.desc()).limit(30)).all()
    active_goals = sum(goal.status == "Active" for goal in goals)
    safe = max(budget.monthly_limit + budget.rollover_savings - budget.current_spent, 0)
    return BudgetDashboardOut(
        budget=BudgetOut(monthly_limit=budget.monthly_limit, current_spent=budget.current_spent,
            rollover_savings=budget.rollover_savings, available_safe_balance=safe,
            spending_percent=round(min(budget.current_spent / budget.monthly_limit * 100, 100), 1) if budget.monthly_limit else 0,
            active_goals=active_goals, total_goal_savings=sum(goal.saved_amount for goal in goals),
            total_ai_deal_savings=round(sum(match.savings_vs_target for match in matches), 2)),
        goals=[_goal_out(goal) for goal in goals],
        alerts=[BudgetAlertOut(alert_id=alert.alert_id, goal_id=alert.goal_id, deal_id=alert.deal_id,
            alert_type=alert.alert_type, message=alert.message,
            created_at=alert.created_at.replace(tzinfo=alert.created_at.tzinfo or timezone.utc).isoformat()) for alert in alerts],
        restock_forecasts=_restock_forecasts(db, user),
        saving_plan=saving_plan(budget, goals),
    )


def evaluate_all_budget_matches(db: Session) -> list[dict]:
    events = []
    for user in db.scalars(select(User)).all():
        before = db.scalar(select(func.count()).select_from(BudgetAlert).where(BudgetAlert.user_id == user.id)) or 0
        evaluate_user_matches(db, user)
        after = db.scalar(select(func.count()).select_from(BudgetAlert).where(BudgetAlert.user_id == user.id)) or 0
        if after > before:
            events.append({"type": "budget_alert_created", "user_id": user.id, "new_alerts": after - before})
    return events
