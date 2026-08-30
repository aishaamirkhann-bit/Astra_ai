from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.product import Product
from app.models.user import User
from app.core.config import settings
from app.schemas.astra_check import AstraCheckOut, DashboardStatsOut, InspectRequest, SellerProfileOut, TrustActionRequest, TrustActionResponse, TrustInspectionOut
from app.services.consent_orchestrator import ConsentOrchestrator
from app.services.astra_check_service import apply_trust_action, dashboard_stats, inspect_product, seller_profile
from app.services.deal_events import deal_event_bus

router = APIRouter(prefix="/astra-check", tags=["ASTRA Check"])


def _require_admin(user: User) -> None:
    if settings.APP_ENV == "production" and user.role != "admin":
        raise HTTPException(status_code=403, detail="ASTRA Check verification actions require an admin role")


@router.get("/dashboard-stats", response_model=DashboardStatsOut)
def get_dashboard_stats(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return dashboard_stats(db)


@router.get("/stats", response_model=DashboardStatsOut)
def get_stats(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return dashboard_stats(db)


@router.get("/seller/{seller_id}", response_model=SellerProfileOut)
def get_seller_profile(seller_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return seller_profile(db, seller_id)


@router.post("/inspect", response_model=TrustInspectionOut)
async def inspect(
    payload: InspectRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result, event = inspect_product(db, payload.query, current_user.id)
    if event:
        await deal_event_bus.publish(event.as_dict())
    return result


@router.post("/actions/{action}", response_model=TrustActionResponse)
async def trust_action(
    action: str,
    payload: TrustActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    result, event = apply_trust_action(db, action, payload, current_user.id)
    if event:
        await deal_event_bus.publish(event.as_dict())
    return result


@router.post("/override", response_model=TrustActionResponse)
async def override_trust_score(
    payload: TrustActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    result, event = apply_trust_action(db, "manual_override", payload, current_user.id)
    if event:
        await deal_event_bus.publish(event.as_dict())
    return result


@router.get("", response_model=AstraCheckOut)
def get_home_astra_check(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Home page ka AstraCheckWidget featured product (best match) ke liye
    check chalata hai. Kisi specific product ke liye /astra-check/{slug} use karo.
    """
    from app.services.recommendation_engine import RecommendationEngine

    product = RecommendationEngine.best_match(db, current_user.wallet)
    if not product:
        raise HTTPException(status_code=404, detail="No product available to check")
    return ConsentOrchestrator.run_astra_check(product, current_user.wallet)


@router.get("/{slug}", response_model=AstraCheckOut)
def get_astra_check_for_product(
    slug: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    product = db.query(Product).filter(Product.id == slug).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return ConsentOrchestrator.run_astra_check(product, current_user.wallet)
