from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.checkout import CheckoutSession
from app.models.notification import Notification
from app.models.order import Order
from app.models.user import User
from app.realtime.notifications_ws import manager as notification_events
from app.realtime.wallet_ws import manager as wallet_events
from app.schemas.checkout import (
    CheckoutSessionConfirmationOut,
    CheckoutSessionConfirmRequest,
    CheckoutSessionCreateRequest,
    CheckoutSessionOut,
)
from app.services.checkout_fsm import (
    abandon_checkout_session,
    confirm_checkout_session,
    get_owned_checkout_session,
    create_or_reuse_checkout_session,
)

router = APIRouter(prefix="/checkout", tags=["Checkout"])


def _session_out(db: Session, checkout: CheckoutSession) -> CheckoutSessionOut:
    order_refs = [
        order_ref
        for (order_ref,) in db.query(Order.order_ref)
        .filter(Order.checkout_session_id == checkout.id)
        .order_by(Order.id)
        .all()
    ]
    return CheckoutSessionOut(
        checkout_ref=checkout.checkout_ref,
        total=checkout.total,
        shipping_address=checkout.shipping_address,
        status=checkout.status,
        expires_at=checkout.expires_at,
        confirmed_at=checkout.confirmed_at,
        cancelled_at=checkout.cancelled_at,
        order_refs=order_refs,
    )


@router.post("/session", response_model=CheckoutSessionOut, status_code=status.HTTP_201_CREATED)
def create_checkout_session(
    payload: CheckoutSessionCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    checkout = create_or_reuse_checkout_session(db, current_user, payload.shipping_address)
    db.commit()
    db.refresh(checkout)
    return _session_out(db, checkout)


@router.get("/session/{checkout_ref}", response_model=CheckoutSessionOut)
def get_checkout_session(
    checkout_ref: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    checkout = get_owned_checkout_session(db, current_user, checkout_ref)
    return _session_out(db, checkout)


@router.post("/session/{checkout_ref}/confirm", response_model=CheckoutSessionConfirmationOut)
async def confirm_checkout(
    checkout_ref: str,
    payload: CheckoutSessionConfirmRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    checkout = get_owned_checkout_session(db, current_user, checkout_ref, lock=True)
    result = confirm_checkout_session(db, current_user, checkout, payload.consent_id)
    if result.created:
        for order_ref in result.order_refs:
            db.add(Notification(user_id=current_user.id, message=f"{order_ref} approved. Your order is being prepared."))
    db.commit()
    db.refresh(result.session)

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

    return CheckoutSessionConfirmationOut(
        **_session_out(db, result.session).model_dump(),
        wallet_balance=result.wallet_balance,
        created=result.created,
    )


@router.post("/session/{checkout_ref}/abandon", response_model=CheckoutSessionOut)
def abandon_checkout(
    checkout_ref: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    checkout = get_owned_checkout_session(db, current_user, checkout_ref, lock=True)
    abandon_checkout_session(db, checkout, f"user:{current_user.email}")
    db.commit()
    db.refresh(checkout)
    return _session_out(db, checkout)
