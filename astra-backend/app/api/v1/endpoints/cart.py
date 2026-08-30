from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.models.budget import UserBudget
from app.models.cart import CartItem
from app.models.notification import Notification
from app.models.order import Order, OrderStatus
from app.models.product import Product
from app.models.user import User
from app.models.wallet import FinancialConsentLog, UserWallet, WalletTransaction
from app.realtime.notifications_ws import manager as notification_events
from app.realtime.wallet_ws import manager as wallet_events
from app.schemas.ai_assistant import AddToCartRequest, AddToCartResponse, CartCheckoutRequest, CartCheckoutResponse, CartItemOut, CartResponse, CartUpdateRequest

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
    if not product: raise HTTPException(status_code=404, detail="Product not found")
    item = db.query(CartItem).filter(CartItem.user_id == current_user.id, CartItem.product_id == product.id, CartItem.size == payload.size, CartItem.color == payload.color, CartItem.storage == payload.storage).first()
    requested = payload.quantity + (item.quantity if item else 0)
    if requested > product.stock_count: raise HTTPException(status_code=409, detail="Requested quantity exceeds live stock")
    if item: item.quantity = requested
    else:
        item = CartItem(user_id=current_user.id, product_id=product.id, quantity=payload.quantity, size=payload.size, color=payload.color, storage=payload.storage); db.add(item)
    db.flush(); total = sum(quantity for (quantity,) in db.query(CartItem.quantity).filter(CartItem.user_id == current_user.id).all()); db.commit()
    return AddToCartResponse(message=f"{product.title} added to cart", quantity=item.quantity, cart_total_quantity=total)


@router.put("/{item_id}", response_model=CartResponse)
def update_item(item_id: int, payload: CartUpdateRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    item = db.query(CartItem).filter(CartItem.id == item_id, CartItem.user_id == current_user.id).first()
    if not item: raise HTTPException(status_code=404, detail="Cart item not found")
    if payload.quantity > item.product.stock_count: raise HTTPException(status_code=409, detail="Requested quantity exceeds live stock")
    item.quantity = payload.quantity; db.commit()
    return _cart(db, current_user)


@router.delete("/{item_id}", response_model=CartResponse)
def remove_item(item_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    item = db.query(CartItem).filter(CartItem.id == item_id, CartItem.user_id == current_user.id).first()
    if not item: raise HTTPException(status_code=404, detail="Cart item not found")
    db.delete(item); db.commit()
    return _cart(db, current_user)


@router.post("/checkout", response_model=CartCheckoutResponse)
async def checkout(payload: CartCheckoutRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    items = db.query(CartItem).filter(CartItem.user_id == current_user.id).with_for_update().all()
    if not items: raise HTTPException(status_code=400, detail="Cart is empty")
    product_ids = [item.product_id for item in items]
    products = {product.id: product for product in db.query(Product).filter(Product.id.in_(product_ids)).with_for_update().all()}
    total = round(sum(products[item.product_id].price * item.quantity for item in items), 2)
    budget = db.query(UserBudget).filter(UserBudget.user_id == current_user.id).with_for_update().first()
    exceeds_budget = bool(budget and budget.current_spent + total > budget.monthly_limit + budget.rollover_savings)
    checkout_ref = f"CART-{current_user.id}-{int(total * 100)}"
    consent = None
    if total > 50000 or exceeds_budget:
        consent = db.query(FinancialConsentLog).filter(FinancialConsentLog.consent_id == payload.consent_id, FinancialConsentLog.user_id == current_user.id, FinancialConsentLog.status == "Approved", FinancialConsentLog.consumed_at.is_(None)).with_for_update().first()
        if not consent or abs(consent.amount - total) > 0.01:
            raise HTTPException(status_code=status.HTTP_428_PRECONDITION_REQUIRED, detail=f"FINANCIAL_CONSENT_REQUIRED:{checkout_ref}")
    wallet = db.query(UserWallet).filter(UserWallet.user_id == current_user.id).with_for_update().one()
    if wallet.available_balance < total: raise HTTPException(status_code=409, detail="Insufficient wallet balance")
    for item in items:
        if products[item.product_id].stock_count < item.quantity: raise HTTPException(status_code=409, detail=f"Insufficient stock for {products[item.product_id].title}")
    order_refs = []
    for item in items:
        product = products[item.product_id]; line_total = round(product.price * item.quantity, 2)
        product.stock_count -= item.quantity
        order = Order(order_ref=f"ORD-{uuid4().hex[:10].upper()}", user_id=current_user.id, product_id=product.id, quantity=item.quantity, size=item.size, color=item.color, storage=item.storage, price=line_total, status=OrderStatus.REVERSAL_WINDOW_OPEN, reversal_deadline=datetime.now(timezone.utc) + timedelta(seconds=settings.APPROVAL_WINDOW_SECONDS))
        db.add(order); db.flush(); order_refs.append(order.order_ref)
        db.add(WalletTransaction(wallet_id=wallet.id, amount=line_total, txn_type="Debit", description=f"Purchase - {product.title}", reference_order_id=order.id))
        db.add(Notification(user_id=current_user.id, message=f"{order.order_ref} placed for {product.title}."))
        db.delete(item)
        if consent and consent.reference_order_id is None: consent.reference_order_id = order.id
    wallet.available_balance -= total
    if budget: budget.current_spent += total
    if consent: consent.consumed_at = datetime.now(timezone.utc)
    db.commit()
    await wallet_events.balance_updated(current_user.id, wallet.available_balance, "Debit")
    await notification_events.broadcast(current_user.id, {"type": "order_update", "checkout_ref": checkout_ref, "order_refs": order_refs, "status": "confirmed", "message": "Cart checkout completed"})
    return CartCheckoutResponse(checkout_ref=checkout_ref, order_refs=order_refs, total=total, status="confirmed")
