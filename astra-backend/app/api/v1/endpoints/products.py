from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.product import Product
from app.models.user import User
from app.schemas.product import ProductOut
from app.services.finance_engine import FinanceEngine
from app.services.recommendation_engine import RecommendationEngine
from app.utils.helpers import format_pkr

router = APIRouter(prefix="/products", tags=["Products"])


def _to_product_out(product: Product, wallet) -> ProductOut:
    fit = FinanceEngine.classify_fit(product.price, wallet) if wallet else "Fits your budget"
    return ProductOut(
        slug=product.slug,
        name=product.name,
        price_display=format_pkr(product.price),
        price=product.price,
        rating=product.rating,
        tag=product.tag,
        fit=fit,
        seller=product.seller_name,
        trust=product.trust_score,
        category=product.category,
        image=product.image_url,
        description=product.description,
    )


@router.get("/recommended", response_model=list[ProductOut])
def get_recommended_products(
    limit: int = 4,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Powers ProductGrid.tsx 'Recommended For You' section."""
    products = RecommendationEngine.get_recommended(db, limit=limit)
    wallet = current_user.wallet
    return [_to_product_out(p, wallet) for p in products]


@router.get("/{slug}", response_model=ProductOut)
def get_product_by_slug(
    slug: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    product = db.query(Product).filter(Product.slug == slug).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return _to_product_out(product, current_user.wallet)
