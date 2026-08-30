from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.notification import Notification
from app.models.order import Order, OrderStatus
from app.models.user import User
from app.schemas.home import HeroSuggestion, HomePageOut
from app.services.consent_orchestrator import ConsentOrchestrator
from app.services.finance_engine import FinanceEngine
from app.services.pipeline_engine import PipelineEngine
from app.services.recommendation_engine import RecommendationEngine
from app.services.trust_engine import TrustEngine
from app.schemas.ai_assistant import AiAssistantSuggestion
from app.schemas.approval import ApprovalStatusOut
from app.schemas.goal import GoalOut, GoalsWalletRailOut, WalletOut
from app.schemas.product import ProductOut
from app.core.config import settings
from app.utils.helpers import format_pkr, as_aware_utc
from app.models.goal import Goal
from app.models.budget import BudgetAlert
from app.schemas.user import UserOut

router = APIRouter(prefix="/home", tags=["Home"])


def _product_out(product, wallet) -> ProductOut:
    return ProductOut(
        slug=product.id,
        name=product.title,
        price_display=format_pkr(product.price),
        price=product.price,
        rating=product.rating,
        tag=product.badge,
        fit=FinanceEngine.classify_fit(product.price, wallet),
        seller=product.seller_name,
        trust=product.trust,
        category=product.category,
        image=product.image_url,
        description=product.description,
    )


@router.get("", response_model=HomePageOut)
def get_home_page(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Single call that hydrates the entire Home page (page.tsx) in one round-trip:
    HeroBanner suggestions, ProductGrid, AstraCheckWidget, AiAssistantWidget,
    HumanApprovalWidget, PipelineBar, GoalsWalletRail, and the notification badge.
    """
    wallet = current_user.wallet

    # --- Recommended products (ProductGrid) ---
    recommended = RecommendationEngine.get_recommended(db, limit=4)
    recommended_out = [_product_out(p, wallet) for p in recommended]

    # --- Best match (AI Assistant + ASTRA Check both use this) ---
    best = RecommendationEngine.best_match(db, wallet)
    astra_check = ConsentOrchestrator.run_astra_check(best, wallet) if best else None
    trust_verdict, _ = TrustEngine.seller_trust_check(best) if best else ("Warning", "No catalog")
    ai_assistant = AiAssistantSuggestion(
        message="Yeh product aapke liye best match hai:",
        product=_product_out(best, wallet),
        fits_budget=FinanceEngine.classify_fit(best.price, wallet) == "Fits your budget",
        verified_seller=trust_verdict == "Good",
    ) if best else None

    # --- Pending approval + pipeline (both keyed off the same active order) ---
    active_order = (
        db.query(Order)
        .filter(Order.user_id == current_user.id)
        .filter(Order.status.in_([OrderStatus.PENDING_APPROVAL, OrderStatus.REVERSAL_WINDOW_OPEN]))
        .order_by(Order.created_at.desc())
        .first()
    )
    approval = None
    if active_order and active_order.status == OrderStatus.PENDING_APPROVAL:
        if active_order.approval_deadline:
            deadline = as_aware_utc(active_order.approval_deadline)
            remaining = max(int((deadline - datetime.now(timezone.utc)).total_seconds()), 0)
        else:
            remaining = settings.APPROVAL_WINDOW_SECONDS
        approval = ApprovalStatusOut(
            order_ref=active_order.order_ref,
            status="pending",
            seconds_left=remaining,
            window_seconds=settings.APPROVAL_WINDOW_SECONDS,
            amount=active_order.price,
        )
    pipeline_state = PipelineEngine.build_state(active_order)

    # --- Goals + Wallet rail ---
    primary_goal = db.query(Goal).filter(Goal.user_id == current_user.id).order_by(Goal.id.asc()).first()
    goals_wallet = GoalsWalletRailOut(
        primary_goal=GoalOut.model_validate(primary_goal) if primary_goal else None,
        wallet=WalletOut(
            available_balance=wallet.available_balance,
            available_balance_display=format_pkr(wallet.available_balance),
        ),
    )

    # --- Notifications badge ---
    unread = (
        db.query(Notification)
        .filter(Notification.user_id == current_user.id, Notification.is_read.is_(False))
        .count()
        + db.query(BudgetAlert).filter(BudgetAlert.user_id == current_user.id, BudgetAlert.is_read.is_(False)).count()
    )

    return HomePageOut(
        hero_suggestions=[
            HeroSuggestion(label="Laptop 150k ke under", href="/explore?q=laptop+150k+ke+under"),
            HeroSuggestion(label="Best phone under 100k", href="/explore?q=best+phone+under+100k"),
            HeroSuggestion(label="Mera budget check karo", href="/my-goals"),
        ],
        recommended_products=recommended_out,
        astra_check=astra_check,
        ai_assistant=ai_assistant,
        approval=approval,
        pipeline=pipeline_state,
        goals_wallet=goals_wallet,
        unread_notifications=unread,
        user=UserOut.model_validate(current_user),
    )
