from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.cart import CartItem
from app.models.product import Product
from app.models.user import User
from app.schemas.ai_assistant import AddToCartRequest, AddToCartResponse, AiAssistantSuggestion, CartItemOut, CartResponse
from app.schemas.product import ProductOut
from app.services.finance_engine import FinanceEngine
from app.services.recommendation_engine import RecommendationEngine
from app.services.trust_engine import TrustEngine
from app.utils.helpers import format_pkr

router = APIRouter(prefix="/ai-assistant", tags=["AI Assistant"])


@router.get("/suggestion", response_model=AiAssistantSuggestion)
def get_ai_suggestion(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Powers AiAssistantWidget.tsx's single best-match card."""
    product = RecommendationEngine.best_match(db, current_user.wallet)
    if not product:
        raise HTTPException(status_code=404, detail="No suggestion available right now")

    fits_budget = FinanceEngine.classify_fit(product.price, current_user.wallet) == "Fits your budget"
    trust_verdict, _ = TrustEngine.seller_trust_check(product)

    return AiAssistantSuggestion(
        message="Yeh product aapke liye best match hai:",
        product=ProductOut(
            slug=product.id,
            name=product.title,
            price_display=format_pkr(product.price),
            price=product.price,
            rating=product.rating,
            tag=product.badge,
            fit=FinanceEngine.classify_fit(product.price, current_user.wallet),
            seller=product.seller_name,
            trust=product.trust,
            category=product.category,
            image=product.image_url,
            description=product.description,
        ),
        fits_budget=fits_budget,
        verified_seller=trust_verdict == "Good",
    )


@router.get("/cart", response_model=CartResponse)
def get_cart(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items = db.query(CartItem).filter(CartItem.user_id == current_user.id).all()
    return CartResponse(
        items=[CartItemOut(
            id=item.id, product_slug=item.product_id, name=item.product.title,
            quantity=item.quantity, size=item.size, color=item.color,
            unit_price=item.product.base_price,
        ) for item in items],
        total_quantity=sum(item.quantity for item in items),
        subtotal=round(sum(item.quantity * item.product.base_price for item in items), 2),
    )


@router.post("/add-to-cart", response_model=AddToCartResponse)
def add_to_cart(
    payload: AddToCartRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Called by the widget's 'Add to Cart' button."""
    product = db.query(Product).filter(Product.id == payload.product_slug).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    item = db.query(CartItem).filter(
        CartItem.user_id == current_user.id,
        CartItem.product_id == product.id,
        CartItem.size == payload.size,
        CartItem.color == payload.color,
    ).first()
    if item:
        item.quantity += payload.quantity
    else:
        item = CartItem(
            user_id=current_user.id, product_id=product.id, quantity=payload.quantity,
            size=payload.size, color=payload.color,
        )
        db.add(item)
    db.flush()
    total_quantity = sum(
        quantity for (quantity,) in db.query(CartItem.quantity).filter(CartItem.user_id == current_user.id).all()
    )
    db.commit()
    return AddToCartResponse(
        message=f"{product.title} added to cart",
        quantity=item.quantity,
        cart_total_quantity=total_quantity,
    )
