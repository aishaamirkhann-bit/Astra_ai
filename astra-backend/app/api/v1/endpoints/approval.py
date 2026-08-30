from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.models.order import Order, OrderStatus
from app.models.deal import Deal, DealAuditLog, DealReservation
from app.models.product import Product
from app.models.user import User
from app.models.budget import UserBudget
from app.models.wallet import FinancialConsentLog, UserWallet, WalletTransaction
from app.realtime.wallet_ws import manager as wallet_events
from app.realtime.notifications_ws import manager as notification_events
from app.models.notification import Notification
from app.schemas.approval import ApprovalActionRequest, ApprovalActionResponse, ApprovalStatusOut
from app.services.audit import record_audit
from app.utils.helpers import as_aware_utc

router = APIRouter(prefix="/approval", tags=["Human Approval"])


def _seconds_left(deadline: datetime) -> int:
    remaining = (as_aware_utc(deadline) - datetime.now(timezone.utc)).total_seconds()
    return max(int(remaining), 0)


@router.get("/pending", response_model=ApprovalStatusOut | None)
def get_pending_approval(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Powers HumanApprovalWidget.tsx's countdown card on Home."""
    order = (
        db.query(Order)
        .filter(Order.user_id == current_user.id, Order.status == OrderStatus.PENDING_APPROVAL)
        .order_by(Order.created_at.desc())
        .first()
    )
    if not order:
        return None

    return ApprovalStatusOut(
        order_ref=order.order_ref,
        status="pending",
        seconds_left=_seconds_left(order.approval_deadline),
        window_seconds=settings.APPROVAL_WINDOW_SECONDS,
    )


@router.post("/approve", response_model=ApprovalActionResponse)
async def approve_transaction(
    payload: ApprovalActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = _get_owned_pending_order(db, current_user, payload.order_ref)
    if order.approval_deadline and _seconds_left(order.approval_deadline) == 0:
        _release_order_reservation(db, order, "approval_expired")
        order.status = OrderStatus.CANCELLED
        db.commit()
        raise HTTPException(status_code=410, detail="Approval window expired; reserved stock was released")
    wallet = db.query(UserWallet).filter(UserWallet.user_id == current_user.id).with_for_update().one()
    budget = db.get(UserBudget, current_user.id)
    exceeds_monthly_budget = bool(budget and budget.current_spent + order.price > budget.monthly_limit + budget.rollover_savings)
    requires_consent = order.price > 50000 or exceeds_monthly_budget
    if requires_consent:
        consent = db.query(FinancialConsentLog).filter(
            FinancialConsentLog.consent_id == payload.consent_id,
            FinancialConsentLog.user_id == current_user.id,
            FinancialConsentLog.reference_order_id == order.id,
            FinancialConsentLog.status == "Approved",
            FinancialConsentLog.consumed_at.is_(None),
        ).with_for_update().first()
        if not consent or abs(consent.amount - order.price) > 0.01:
            reason = "monthly budget" if exceeds_monthly_budget else "Rs. 50,000 safety limit"
            raise HTTPException(status_code=428, detail=f"FINANCIAL_CONSENT_REQUIRED: This payment exceeds your {reason}.")
        consent.consumed_at = datetime.now(timezone.utc)
    if order.price > wallet.available_balance:
        raise HTTPException(status_code=409, detail="Insufficient wallet balance")
    existing_debit = db.query(WalletTransaction).filter(WalletTransaction.reference_order_id == order.id, WalletTransaction.txn_type == "Debit").first()
    if not existing_debit:
        wallet.available_balance -= order.price
        db.add(WalletTransaction(wallet_id=wallet.id, amount=order.price, txn_type="Debit", description=f"Purchase - {order.product.title}", reference_order_id=order.id))
        if budget:
            budget.current_spent += order.price
    order.status = OrderStatus.REVERSAL_WINDOW_OPEN
    order.reversal_deadline = datetime.now(timezone.utc) + timedelta(
        seconds=settings.APPROVAL_WINDOW_SECONDS
    )
    if order.reservation_id:
        reservation = db.query(DealReservation).filter(DealReservation.id == order.reservation_id).first()
        if reservation and reservation.status == "reserved":
            reservation.status = "committed"
    record_audit(
        db,
        event_type="human.approval",
        endpoint=f"/api/v1/approval/approve?order_ref={order.order_ref}",
        verdict="approved",
        actor=f"user:{current_user.email}",
    )
    db.commit()
    await wallet_events.balance_updated(current_user.id, wallet.available_balance, "Debit")
    db.add(Notification(user_id=current_user.id, message=f"{order.order_ref} approved. Your order is being prepared.")); db.commit()
    await notification_events.broadcast(current_user.id, {"type": "order_update", "order_ref": order.order_ref, "status": "confirmed", "message": "Payment approved and order is being prepared"})
    return ApprovalActionResponse(
        order_ref=order.order_ref, status="approved", message="Transaction approved"
    )


@router.post("/cancel", response_model=ApprovalActionResponse)
def cancel_transaction(
    payload: ApprovalActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = _get_owned_pending_order(db, current_user, payload.order_ref)
    _release_order_reservation(db, order, "order_cancelled")
    order.status = OrderStatus.CANCELLED
    record_audit(
        db,
        event_type="human.cancellation",
        endpoint=f"/api/v1/approval/cancel?order_ref={order.order_ref}",
        verdict="cancelled",
        actor=f"user:{current_user.email}",
    )
    db.commit()
    return ApprovalActionResponse(
        order_ref=order.order_ref, status="cancelled", message="Order cancelled — refund started"
    )


def _get_owned_pending_order(db: Session, user: User, order_ref: str) -> Order:
    order = (
        db.query(Order)
        .filter(Order.order_ref == order_ref, Order.user_id == user.id)
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status != OrderStatus.PENDING_APPROVAL:
        raise HTTPException(status_code=400, detail="Order is no longer pending approval")
    return order


def _release_order_reservation(db: Session, order: Order, reason: str) -> None:
    if not order.reservation_id:
        return
    reservation = db.query(DealReservation).filter(DealReservation.id == order.reservation_id).with_for_update().first()
    if not reservation or reservation.status not in {"reserved", "committed"}:
        return
    deal = db.query(Deal).filter(Deal.id == reservation.deal_id).with_for_update().first()
    product = db.query(Product).filter(Product.id == order.product_id).with_for_update().first()
    reservation.status = "cancelled"
    if not deal or not product:
        return
    product.stock_count += reservation.quantity
    deal.stock_remaining = product.stock_count
    if not deal.deal_expires_at or as_aware_utc(deal.deal_expires_at) > datetime.now(timezone.utc):
        deal.is_active = True
    db.add(DealAuditLog(
        deal_id=deal.id, product_id=product.id, event_type="stock_changed", decision="reservation_released",
        reasoning={"reservation_id": reservation.id, "reason": reason, "quantity_restored": reservation.quantity},
    ))
