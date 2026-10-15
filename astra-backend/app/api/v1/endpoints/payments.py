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
from app.models.budget import UserBudget
from app.models.checkout import CheckoutSession
from app.models.order import Order, OrderStatus
from app.models.user import User
from app.models.wallet import UserWallet, WalletTransaction
from app.realtime.wallet_ws import manager as wallet_events
from app.services import payment_gateway
from app.services.audit import record_audit
from app.services.checkout_fsm import abandon_checkout_session, create_or_reuse_checkout_session
from app.services.seller_payouts import record_order_payouts

log = logging.getLogger("astra.payments")
router = APIRouter(prefix="/payments", tags=["Payments"])

MIN_TOPUP = 500.0
MAX_TOPUP = 500_000.0


class CardTopUpRequest(BaseModel):
    amount: float = Field(ge=MIN_TOPUP, le=MAX_TOPUP)


class CardCheckoutRequest(BaseModel):
    shipping_address: str = Field(min_length=8, max_length=500)


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
    checkout = create_or_reuse_checkout_session(db, current_user, payload.shipping_address)
    if checkout.status != "awaiting_consent":
        raise HTTPException(status_code=409, detail="Checkout session is no longer active")
    existing = db.query(StripeCheckoutPayment).filter(
        StripeCheckoutPayment.checkout_session_id == checkout.id,
        StripeCheckoutPayment.status == "pending",
    ).first()
    if existing:
        return {"checkout_ref": checkout.checkout_ref, "checkout_url": existing.checkout_url, "status": existing.status}

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
    if payment and payment.status == "paid":
        return {"checkout_ref": checkout_ref, "payment_status": payment.status}
    if payment and payment.status == "pending":
        try:
            stripe_session = payment_gateway.retrieve_checkout_session(payment.stripe_session_id)
        except Exception as exc:
            raise HTTPException(status_code=502, detail="Could not verify Stripe Checkout status; reserved items were kept") from exc
        if stripe_session.get("payment_status") == "paid":
            payment.status = "paid_webhook_pending"
            payment.payment_intent_id = stripe_session.get("payment_intent")
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
        payment.status = "cancelled"
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

    if event_type == "checkout.session.completed":
        stripe_session = event["data"]["object"]
        payment = db.query(StripeCheckoutPayment).filter(
            StripeCheckoutPayment.stripe_session_id == stripe_session.get("id"),
        ).with_for_update().first()
        if payment and payment.status != "paid":
            checkout = db.query(CheckoutSession).filter(
                CheckoutSession.id == payment.checkout_session_id,
            ).with_for_update().first()
            orders = db.query(Order).filter(Order.checkout_session_id == checkout.id).with_for_update().all() if checkout else []
            paid_total = stripe_session.get("amount_total")
            if stripe_session.get("payment_status") != "paid":
                payment.status = "pending_payment"
            elif checkout and paid_total is not None and int(paid_total) != int(round(checkout.total * 100)):
                payment.status = "amount_mismatch"
            elif checkout and orders and checkout.status == "awaiting_consent" and all(order.status == OrderStatus.PENDING_APPROVAL for order in orders):
                now = datetime.now(timezone.utc)
                payment.status = "paid"
                payment.payment_intent_id = stripe_session.get("payment_intent")
                payment.paid_at = now
                checkout.status = "reversal_window_open"
                checkout.confirmed_at = now
                budget = db.query(UserBudget).filter(UserBudget.user_id == checkout.user_id).with_for_update().first()
                if budget:
                    budget.current_spent += checkout.total
                for order in orders:
                    order.status = OrderStatus.REVERSAL_WINDOW_OPEN
                    order.reversal_deadline = now + timedelta(seconds=settings.APPROVAL_WINDOW_SECONDS)
                record_order_payouts(db, orders)
                record_audit(
                    db,
                    event_type="payments.checkout_settled",
                    endpoint="/webhooks/stripe",
                    verdict="paid",
                    actor=f"stripe:{event_id}",
                )
            elif checkout:
                payment.status = "paid_review"
                payment.payment_intent_id = stripe_session.get("payment_intent")
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        if db.get(StripeWebhookEvent, event_id):
            return {"received": True, "duplicate": True}
        raise
    return {"received": True}
