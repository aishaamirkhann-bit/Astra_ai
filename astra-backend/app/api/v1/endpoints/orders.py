from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.api.v1.endpoints.approval import _release_order_reservation
from app.models.order import Order, OrderStatus
from app.models.pipeline import AuditLog
from app.models.user import User
from app.models.cart import CartItem
from app.models.notification import Notification
from app.models.wallet import FinancialConsentLog
from app.realtime.notifications_ws import manager as notification_events
from app.models.budget import UserBudget
from app.models.wallet import UserWallet, WalletTransaction
from app.realtime.wallet_ws import manager as wallet_events
from app.schemas.order import OrderDetailOut, OrderOut, ReorderResponse, ReverseOrderResponse
from app.services.audit import record_audit
from app.utils.helpers import as_aware_utc

router = APIRouter(prefix="/orders", tags=["Orders"])


def _seconds_left(order: Order) -> int:
    deadline = order.approval_deadline if order.status == OrderStatus.PENDING_APPROVAL else order.reversal_deadline
    if not deadline:
        return 0
    return max(0, int((as_aware_utc(deadline) - datetime.now(timezone.utc)).total_seconds()))


@router.get("/audit")
def audit_trail(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    entries = db.query(AuditLog).order_by(AuditLog.id.desc()).limit(30).all()
    return [
        {
            "id": entry.event_ref,
            "type": entry.event_type,
            "endpoint": entry.endpoint,
            "actor": entry.actor,
            "verdict": entry.verdict,
            "time": as_aware_utc(entry.created_at).isoformat() if entry.created_at else None,
        }
        for entry in entries
    ]


@router.get("", response_model=list[OrderOut])
def list_orders(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    orders = db.query(Order).filter(Order.user_id == current_user.id).order_by(Order.created_at.desc()).all()
    return [OrderOut(
        order_ref=order.order_ref, product_name=order.product.title,
        price=order.price, quantity=order.quantity, size=order.size, color=order.color, storage=order.storage,
        status=order.status.value, seconds_left=_seconds_left(order), placed_at=order.created_at,
        image=order.product.image_url,
    ) for order in orders]


@router.get("/{order_ref}", response_model=OrderDetailOut)
def order_detail(order_ref: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    order = db.query(Order).filter(Order.order_ref == order_ref, Order.user_id == current_user.id).first()
    if not order: raise HTTPException(status_code=404, detail="Order not found")
    consent = db.query(FinancialConsentLog).filter(FinancialConsentLog.reference_order_id == order.id, FinancialConsentLog.consumed_at.is_not(None)).first()
    return OrderDetailOut(order_ref=order.order_ref, product_name=order.product.title, product_id=order.product_id, price=order.price, unit_price=round(order.price / order.quantity, 2), subtotal=order.price, quantity=order.quantity, size=order.size, color=order.color, storage=order.storage, status=order.status.value, seconds_left=_seconds_left(order), placed_at=order.created_at, image=order.product.image_url, seller_name=order.product.seller_name, seller_verified=order.product.is_verified_seller, seller_trust_score=order.product.trust, payment_method="Wallet / Consent Verified" if consent else "Wallet", consent_method=consent.auth_method if consent else None, shipped_at=order.shipped_at, delivered_at=order.delivered_at)


@router.post("/{order_ref}/reorder", response_model=ReorderResponse)
def reorder(order_ref: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    order = db.query(Order).filter(Order.order_ref == order_ref, Order.user_id == current_user.id).first()
    if not order: raise HTTPException(status_code=404, detail="Order not found")
    item = db.query(CartItem).filter(CartItem.user_id == current_user.id, CartItem.product_id == order.product_id, CartItem.size == order.size, CartItem.color == order.color, CartItem.storage == order.storage).first()
    if item: item.quantity += order.quantity
    else: db.add(CartItem(user_id=current_user.id, product_id=order.product_id, quantity=order.quantity, size=order.size, color=order.color, storage=order.storage))
    db.flush(); total = sum(q for (q,) in db.query(CartItem.quantity).filter(CartItem.user_id == current_user.id).all()); db.commit()
    return ReorderResponse(order_ref=order_ref, cart_total_quantity=total, message=f"{order.product.title} added to cart again")


@router.post("/{order_ref}/reverse", response_model=ReverseOrderResponse)
async def reverse_order(order_ref: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    order = db.query(Order).filter(Order.order_ref == order_ref, Order.user_id == current_user.id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status != OrderStatus.REVERSAL_WINDOW_OPEN or _seconds_left(order) <= 0:
        raise HTTPException(status_code=409, detail="Order is no longer reversible")
    _release_order_reservation(db, order, "reversal_requested")
    debit = db.query(WalletTransaction).filter(WalletTransaction.reference_order_id == order.id, WalletTransaction.txn_type == "Debit").first()
    refund = db.query(WalletTransaction).filter(WalletTransaction.reference_order_id == order.id, WalletTransaction.txn_type == "Refund").first()
    wallet = db.query(UserWallet).filter(UserWallet.user_id == current_user.id).with_for_update().one()
    if debit and not refund:
        wallet.available_balance += order.price
        db.add(WalletTransaction(wallet_id=wallet.id, amount=order.price, txn_type="Refund", description=f"Refund - {order.product.title}", reference_order_id=order.id))
        budget = db.get(UserBudget, current_user.id)
        if budget:
            budget.current_spent = max(0, budget.current_spent - order.price)
    order.status = OrderStatus.CANCELLED
    db.add(Notification(user_id=current_user.id, message=f"{order.order_ref} was reversed and refunded."))
    record_audit(
        db,
        event_type="order.reversal",
        endpoint=f"/api/v1/orders/{order.order_ref}/reverse",
        verdict="cancelled",
        actor=f"user:{current_user.email}",
    )
    db.commit()
    if debit and not refund:
        await wallet_events.balance_updated(current_user.id, wallet.available_balance, "Refund")
    await notification_events.broadcast(current_user.id, {"type": "order_update", "order_ref": order.order_ref, "status": "cancelled", "message": "Order reversed and refunded"})
    return ReverseOrderResponse(order_ref=order.order_ref, status="cancelled", message="Order reversed and stock restored")
