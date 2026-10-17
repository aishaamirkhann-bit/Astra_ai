"""Card payment rails: Stripe top-ups that settle into the wallet ledger."""
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.models.payment import CardTopUp, StripeCheckoutPayment, StripeWebhookEvent
from app.models.checkout import CheckoutSession
from app.models.order import Order
from app.models.user import User
from app.models.wallet import UserWallet, WalletTransaction
from app.realtime.wallet_ws import manager as wallet_events
from app.services import payment_gateway
from app.services.audit import record_audit
from app.services.checkout_fsm import (
    abandon_checkout_session,
    get_owned_checkout_session,
    require_card_checkout_consent,
    release_checkout_session,
)
from app.services.stripe_checkout import (
    mark_checkout_payment_failed,
    reconcile_charge_refund,
    reconcile_refund_object,
    settle_paid_checkout,
)

log = logging.getLogger("astra.payments")
router = APIRouter(prefix="/payments", tags=["Payments"])

MIN_TOPUP = 500.0
MAX_TOPUP = 500_000.0


class CardTopUpRequest(BaseModel):
    amount: float = Field(ge=MIN_TOPUP, le=MAX_TOPUP)


class CardCheckoutRequest(BaseModel):
    shipping_address: str = Field(min_length=8, max_length=500)
    checkout_ref: str = Field(min_length=8, max_length=40)
    consent_id: str = Field(min_length=1)


def _stripe_unconfigured() -> HTTPException:
    return HTTPException(status_code=503, detail="Payments not configured")


@router.get("/methods")
def payment_methods():
    methods = ["wallet"]
    if payment_gateway.stripe_configured():
        methods.append("card")
    return {"methods": methods, "stripe_publishable_key": settings.STRIPE_PUBLISHABLE_KEY or None}


@router.post("/card/topup")
async def create_card_topup(
    payload: CardTopUpRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not payment_gateway.stripe_configured():
        raise _stripe_unconfigured()
    intent = payment_gateway.create_topup_intent(payload.amount, current_user.id, f"topup:{current_user.id}")
    db.add(CardTopUp(intent_id=intent.intent_id, user_id=current_user.id, amount=payload.amount))
    db.commit()
    record_audit(db, event_type="payments.intent_created", endpoint="/api/v1/payments/card/topup", verdict="created", actor=f"user:{current_user.email}")
    db.commit()
    return {"intent_id": intent.intent_id, "client_secret": intent.client_secret, "amount": intent.amount, "currency": intent.currency}


@router.post("/checkout")
def create_order_checkout(
    payload: CardCheckoutRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not payment_gateway.stripe_checkout_configured():
        raise _stripe_unconfigured()
    checkout = get_owned_checkout_session(db, current_user, payload.checkout_ref, lock=True)
    if checkout.status != "awaiting_consent":
        raise HTTPException(status_code=409, detail="Checkout session is no longer active")
    existing = db.query(StripeCheckoutPayment).filter(
        StripeCheckoutPayment.checkout_session_id == checkout.id,
        StripeCheckoutPayment.status == "pending",
    ).first()
    if existing:
        return {"checkout_ref": checkout.checkout_ref, "checkout_url": existing.checkout_url, "status": existing.status}

    consent = require_card_checkout_consent(db, current_user, checkout, payload.consent_id)
    checkout.shipping_address = payload.shipping_address
    now = datetime.now(timezone.utc)
    checkout.expires_at = now + timedelta(minutes=30)
    orders = db.query(Order).filter(Order.checkout_session_id == checkout.id).order_by(Order.id).all()
    for order in orders:
        order.approval_deadline = checkout.expires_at
    line_items = [{
        "price_data": {
            "currency": "pkr",
            "product_data": {"name": order.product.title},
            "unit_amount": int(round((order.price / order.quantity) * 100)),
        },
        "quantity": order.quantity,
    } for order in orders]
    metadata = {
        "checkout_ref": checkout.checkout_ref,
        "checkout_session_id": str(checkout.id),
        "user_id": str(current_user.id),
    }
    origin = settings.primary_frontend_url
    try:
        stripe_session_id, checkout_url = payment_gateway.create_checkout_session(
            line_items=line_items,
            metadata=metadata,
            success_url=f"{origin}/checkout/success?checkout_ref={checkout.checkout_ref}&session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{origin}/checkout/cancel?checkout_ref={checkout.checkout_ref}",
            expires_at=int(checkout.expires_at.timestamp()),
            idempotency_key=f"astra-checkout-{checkout.checkout_ref}",
        )
    except Exception as exc:
        abandon_checkout_session(db, checkout, f"stripe-error:{current_user.email}")
        db.commit()
        raise HTTPException(status_code=502, detail="Could not start Stripe Checkout") from exc
    consent.consumed_at = datetime.now(timezone.utc)
    payment = StripeCheckoutPayment(
        stripe_session_id=stripe_session_id,
        checkout_session_id=checkout.id,
        checkout_url=checkout_url,
        amount=checkout.total,
    )
    db.add(payment)
    db.commit()
    return {"checkout_ref": checkout.checkout_ref, "checkout_url": checkout_url, "status": payment.status}


@router.get("/checkout/{checkout_ref}")
def order_checkout_status(
    checkout_ref: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    checkout = db.query(CheckoutSession).filter(
        CheckoutSession.checkout_ref == checkout_ref,
        CheckoutSession.user_id == current_user.id,
    ).first()
    if checkout is None:
        raise HTTPException(status_code=404, detail="Checkout not found")
    payment = db.query(StripeCheckoutPayment).filter(
        StripeCheckoutPayment.checkout_session_id == checkout.id,
    ).first()
    return {
        "checkout_ref": checkout.checkout_ref,
        "checkout_status": checkout.status,
        "payment_status": payment.status if payment else "not_started",
        "order_refs": [order.order_ref for order in checkout.orders],
    }


@router.get("/checkout/by-session/{stripe_session_id}")
def order_checkout_status_by_stripe_session(
    stripe_session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    payment = db.query(StripeCheckoutPayment).filter(
        StripeCheckoutPayment.stripe_session_id == stripe_session_id,
    ).first()
    if payment is None:
        raise HTTPException(status_code=404, detail="Stripe checkout session not found")
    checkout = db.query(CheckoutSession).filter(
        CheckoutSession.id == payment.checkout_session_id,
        CheckoutSession.user_id == current_user.id,
    ).first()
    if checkout is None:
        raise HTTPException(status_code=404, detail="Checkout not found")
    return {
        "checkout_ref": checkout.checkout_ref,
        "stripe_session_id": payment.stripe_session_id,
        "checkout_status": checkout.status,
        "payment_status": payment.status,
        "order_refs": [order.order_ref for order in checkout.orders],
    }


@router.post("/checkout/{checkout_ref}/cancel")
def cancel_order_checkout(
    checkout_ref: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    checkout = db.query(CheckoutSession).filter(
        CheckoutSession.checkout_ref == checkout_ref,
        CheckoutSession.user_id == current_user.id,
    ).with_for_update().first()
    if checkout is None:
        raise HTTPException(status_code=404, detail="Checkout not found")
    payment = db.query(StripeCheckoutPayment).filter(
        StripeCheckoutPayment.checkout_session_id == checkout.id,
    ).first()
    if payment and payment.status != "pending":
        return {"checkout_ref": checkout_ref, "payment_status": payment.status}
    if payment and payment.status == "pending":
        try:
            stripe_session = payment_gateway.retrieve_checkout_session(payment.stripe_session_id)
        except Exception as exc:
            raise HTTPException(status_code=502, detail="Could not verify Stripe Checkout status; reserved items were kept") from exc
        if stripe_session.get("payment_status") == "paid":
            settle_paid_checkout(db, payment, stripe_session, actor=f"stripe:cancel-reconciliation:{checkout_ref}")
            db.commit()
            return {"checkout_ref": checkout_ref, "payment_status": payment.status}
        if stripe_session.get("status") == "complete":
            payment.status = "pending_payment"
            db.commit()
            return {"checkout_ref": checkout_ref, "payment_status": payment.status}
        if stripe_session.get("status") == "open":
            try:
                payment_gateway.expire_checkout_session(payment.stripe_session_id)
            except Exception as exc:
                raise HTTPException(status_code=502, detail="Could not close Stripe Checkout; reserved items were kept") from exc
        payment.status = "expired" if stripe_session.get("status") == "expired" else "cancelled"
    if payment and payment.status == "expired":
        release_checkout_session(db, checkout, "expired")
    else:
        abandon_checkout_session(db, checkout, f"stripe-cancel:{current_user.email}")
    db.commit()
    return {"checkout_ref": checkout_ref, "payment_status": payment.status if payment else "cancelled"}


@router.post("/webhook")
async def stripe_webhook(request: Request, stripe_signature: str = Header(default="")):
    if not payment_gateway.stripe_configured():
        raise _stripe_unconfigured()
    body = await request.body()
    try:
        event = payment_gateway.construct_webhook_event(body, stripe_signature)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    if event["type"] == "payment_intent.succeeded":
        intent = event["data"]["object"]
        db: Session = next(get_db())
        try:
            topup = db.get(CardTopUp, intent["id"])
            if topup is None or topup.status == "succeeded":
                return {"received": True}
            wallet = db.query(UserWallet).filter(UserWallet.user_id == topup.user_id).with_for_update().first()
            if wallet is None:
                log.error("webhook: no wallet for user %s on intent %s", topup.user_id, topup.intent_id)
                return {"received": True}
            wallet.available_balance += topup.amount
            db.add(WalletTransaction(
                wallet_id=wallet.wallet_id, amount=topup.amount, txn_type="Credit",
                description=f"Card top-up via Stripe ({topup.intent_id})",
            ))
            topup.status = "succeeded"
            topup.settled_at = datetime.now(timezone.utc)
            db.commit()
            record_audit(db, event_type="payments.topup_settled", endpoint="/api/v1/payments/webhook", verdict="settled", actor=f"stripe:{topup.intent_id}")
            db.commit()
            await wallet_events.balance_updated(topup.user_id, wallet.available_balance, "Credit")
        finally:
            db.close()
    return {"received": True}


@router.post("/webhooks/stripe")
async def stripe_order_webhook(
    request: Request,
    stripe_signature: str = Header(default=""),
    db: Session = Depends(get_db),
):
    if not payment_gateway.stripe_checkout_configured():
        raise _stripe_unconfigured()
    try:
        event = payment_gateway.construct_webhook_event(await request.body(), stripe_signature)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid webhook signature") from exc

    event_id = event.get("id")
    event_type = event.get("type")
    if not event_id or not event_type:
        raise HTTPException(status_code=400, detail="Invalid Stripe event")
    if db.get(StripeWebhookEvent, event_id):
        return {"received": True, "duplicate": True}
    db.add(StripeWebhookEvent(event_id=event_id, event_type=event_type))
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        if db.get(StripeWebhookEvent, event_id):
            return {"received": True, "duplicate": True}
        raise

    stripe_object = event.get("data", {}).get("object", {})
    if event_type in {"checkout.session.completed", "checkout.session.async_payment_succeeded"}:
        stripe_session = stripe_object
        payment = db.query(StripeCheckoutPayment).filter(
            StripeCheckoutPayment.stripe_session_id == stripe_session.get("id"),
        ).with_for_update().first()
        if payment:
            if stripe_session.get("payment_status") != "paid":
                payment.status = "pending_payment"
            else:
                settle_paid_checkout(db, payment, stripe_session, actor=f"stripe:{event_id}")
    elif event_type in {"checkout.session.expired", "checkout.session.async_payment_failed"}:
        payment = db.query(StripeCheckoutPayment).filter(
            StripeCheckoutPayment.stripe_session_id == stripe_object.get("id"),
        ).with_for_update().first()
        if payment:
            if stripe_object.get("payment_status") == "paid":
                settle_paid_checkout(db, payment, stripe_object, actor=f"stripe:{event_id}")
            else:
                mark_checkout_payment_failed(
                    db,
                    payment,
                    "expired" if event_type == "checkout.session.expired" else "failed",
                    actor=f"stripe:{event_id}",
                )
    elif event_type == "payment_intent.payment_failed":
        intent = stripe_object
        metadata = intent.get("metadata") or {}
        checkout_id = metadata.get("checkout_session_id")
        payment = None
        if checkout_id:
            try:
                checkout_id = int(checkout_id)
            except (TypeError, ValueError):
                checkout_id = None
            if checkout_id is not None:
                payment = db.query(StripeCheckoutPayment).filter(
                    StripeCheckoutPayment.checkout_session_id == checkout_id,
                ).with_for_update().first()
        if payment is None:
            payment = db.query(StripeCheckoutPayment).filter(
                StripeCheckoutPayment.payment_intent_id == intent.get("id"),
            ).with_for_update().first()
        if payment:
            payment.payment_intent_id = intent.get("id")
            mark_checkout_payment_failed(db, payment, "failed", actor=f"stripe:{event_id}")
        topup = db.get(CardTopUp, intent.get("id"))
        if topup and topup.status != "succeeded":
            topup.status = "failed"
    elif event_type == "charge.refunded":
        reconcile_charge_refund(db, stripe_object)
    elif event_type == "refund.updated":
        reconcile_refund_object(db, stripe_object)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        if db.get(StripeWebhookEvent, event_id):
            return {"received": True, "duplicate": True}
        raise
    return {"received": True}
