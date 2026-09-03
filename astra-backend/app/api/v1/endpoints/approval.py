from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.models.notification import Notification
from app.models.order import Order, OrderStatus
from app.models.user import User
from app.realtime.notifications_ws import manager as notification_events
from app.realtime.wallet_ws import manager as wallet_events
from app.schemas.approval import ApprovalActionRequest, ApprovalActionResponse, ApprovalStatusOut
from app.services.audit import record_audit
from app.services.checkout_fsm import approve_pending_order, cancel_pending_order
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
    order = (
        db.query(Order)
        .filter(
            Order.user_id == current_user.id,
            Order.checkout_session_id.is_(None),
            Order.status == OrderStatus.PENDING_APPROVAL,
        )
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
    wallet_balance = approve_pending_order(db, current_user, order, payload.consent_id)
    db.add(Notification(user_id=current_user.id, message=f"{order.order_ref} approved. Your order is being prepared."))
    db.commit()
    await wallet_events.balance_updated(current_user.id, wallet_balance, "Debit")
    await notification_events.broadcast(
        current_user.id,
        {"type": "order_update", "order_ref": order.order_ref, "status": order.status.value, "message": "Payment approved and the reversal window is open"},
    )
    return ApprovalActionResponse(order_ref=order.order_ref, status="approved", message="Transaction approved")


@router.post("/cancel", response_model=ApprovalActionResponse)
def cancel_transaction(
    payload: ApprovalActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = _get_owned_pending_order(db, current_user, payload.order_ref)
    cancel_pending_order(db, order, "order_cancelled")
    record_audit(
        db,
        event_type="human.cancellation",
        endpoint=f"/api/v1/approval/cancel?order_ref={order.order_ref}",
        verdict="cancelled",
        actor=f"user:{current_user.email}",
    )
    db.commit()
    return ApprovalActionResponse(order_ref=order.order_ref, status="cancelled", message="Order cancelled — stock released")


def _get_owned_pending_order(db: Session, user: User, order_ref: str) -> Order:
    order = (
        db.query(Order)
        .filter(
            Order.order_ref == order_ref,
            Order.user_id == user.id,
            Order.checkout_session_id.is_(None),
        )
        .with_for_update()
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status != OrderStatus.PENDING_APPROVAL:
        raise HTTPException(status_code=409, detail="Order is no longer pending approval")
    return order
