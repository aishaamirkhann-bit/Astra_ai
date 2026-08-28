from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.product import Product
from app.models.user import User
from app.schemas.astra_check import AstraCheckOut
from app.services.consent_orchestrator import ConsentOrchestrator

router = APIRouter(prefix="/astra-check", tags=["ASTRA Check"])


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
    product = db.query(Product).filter(Product.slug == slug).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return ConsentOrchestrator.run_astra_check(product, current_user.wallet)
