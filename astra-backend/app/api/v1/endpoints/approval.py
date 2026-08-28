from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.models.order import Order, OrderStatus
from app.models.user import User
from app.schemas.approval import ApprovalActionRequest, ApprovalActionResponse, ApprovalStatusOut
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
def approve_transaction(
    payload: ApprovalActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = _get_owned_pending_order(db, current_user, payload.order_ref)
    order.status = OrderStatus.REVERSAL_WINDOW_OPEN
    order.reversal_deadline = datetime.now(timezone.utc) + timedelta(
        seconds=settings.APPROVAL_WINDOW_SECONDS
    )
    db.commit()
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
    order.status = OrderStatus.CANCELLED
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
