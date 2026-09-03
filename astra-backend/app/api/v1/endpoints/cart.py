from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.budget import UserBudget
from app.models.cart import CartItem
from app.models.notification import Notification
from app.models.product import Product
from app.models.user import User
from app.realtime.notifications_ws import manager as notification_events
from app.realtime.wallet_ws import manager as wallet_events
from app.schemas.ai_assistant import (
    AddToCartRequest,
    AddToCartResponse,
    CartCheckoutRequest,
    CartCheckoutResponse,
    CartItemOut,
    CartResponse,
    CartUpdateRequest,
)
from app.services.checkout_fsm import confirm_checkout_session, create_or_reuse_checkout_session

router = APIRouter(prefix="/cart", tags=["Cart"])


def _cart(db: Session, user: User) -> CartResponse:
    items = db.query(CartItem).filter(CartItem.user_id == user.id).order_by(CartItem.created_at).all()
    budget = db.get(UserBudget, user.id)
    subtotal = sum(item.product.price * item.quantity for item in items)
    monthly_limit = budget.monthly_limit if budget else 0
    current_spent = budget.current_spent if budget else 0
    return CartResponse(
        items=[CartItemOut(id=item.id, product_slug=item.product_id, name=item.product.title, quantity=item.quantity, size=item.size, color=item.color, storage=item.storage, unit_price=item.product.price, image=item.product.image_url, seller_name=item.product.seller_name, seller_verified=item.product.is_verified_seller, stock_count=item.product.stock_count) for item in items],
        total_quantity=sum(item.quantity for item in items), subtotal=round(subtotal, 2), monthly_budget_limit=monthly_limit,
        current_spent=current_spent, exceeds_budget=bool(budget and current_spent + subtotal > monthly_limit + budget.rollover_savings),
    )


@router.get("", response_model=CartResponse)
def get_cart(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return _cart(db, current_user)


@router.post("/add", response_model=AddToCartResponse)
def add(payload: AddToCartRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    product = db.get(Product, payload.product_slug)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    item = db.query(CartItem).filter(CartItem.user_id == current_user.id, CartItem.product_id == product.id, CartItem.size == payload.size, CartItem.color == payload.color, CartItem.storage == payload.storage).first()
    requested = payload.quantity + (item.quantity if item else 0)
    if requested > product.stock_count:
        raise HTTPException(status_code=409, detail="Requested quantity exceeds live stock")
    if item:
        item.quantity = requested
    else:
        item = CartItem(user_id=current_user.id, product_id=product.id, quantity=payload.quantity, size=payload.size, color=payload.color, storage=payload.storage)
        db.add(item)
    db.flush()
    total = sum(quantity for (quantity,) in db.query(CartItem.quantity).filter(CartItem.user_id == current_user.id).all())
    db.commit()
    return AddToCartResponse(message=f"{product.title} added to cart", quantity=item.quantity, cart_total_quantity=total)


@router.put("/{item_id}", response_model=CartResponse)
def update_item(item_id: int, payload: CartUpdateRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    item = db.query(CartItem).filter(CartItem.id == item_id, CartItem.user_id == current_user.id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Cart item not found")
    if payload.quantity > item.product.stock_count:
        raise HTTPException(status_code=409, detail="Requested quantity exceeds live stock")
    item.quantity = payload.quantity
    db.commit()
    return _cart(db, current_user)


@router.delete("/{item_id}", response_model=CartResponse)
def remove_item(item_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    item = db.query(CartItem).filter(CartItem.id == item_id, CartItem.user_id == current_user.id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Cart item not found")
    db.delete(item)
    db.commit()
    return _cart(db, current_user)


@router.post("/checkout", response_model=CartCheckoutResponse)
async def checkout(payload: CartCheckoutRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    checkout_session = create_or_reuse_checkout_session(db, current_user, payload.shipping_address)
    if not payload.consent_id:
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_428_PRECONDITION_REQUIRED,
            detail=f"FINANCIAL_CONSENT_REQUIRED:{checkout_session.checkout_ref}",
        )

    result = confirm_checkout_session(db, current_user, checkout_session, payload.consent_id)
    if result.created:
        for order_ref in result.order_refs:
            db.add(Notification(user_id=current_user.id, message=f"{order_ref} approved. Your order is being prepared."))
    db.commit()

    if result.created:
        await wallet_events.balance_updated(current_user.id, result.wallet_balance, "Debit")
        await notification_events.broadcast(
            current_user.id,
            {
                "type": "order_update",
                "checkout_ref": result.session.checkout_ref,
                "order_refs": result.order_refs,
                "status": result.session.status,
                "message": "Payment approved and the reversal window is open",
            },
        )
    return CartCheckoutResponse(
        checkout_ref=result.session.checkout_ref,
        order_refs=result.order_refs,
        total=result.session.total,
        status="confirmed",
    )
