"""Card payment rails: Stripe top-ups that settle into the wallet ledger."""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.models.payment import CardTopUp
from app.models.user import User
from app.models.wallet import UserWallet, WalletTransaction
from app.realtime.wallet_ws import manager as wallet_events
from app.services import payment_gateway
from app.services.audit import record_audit

log = logging.getLogger("astra.payments")
router = APIRouter(prefix="/payments", tags=["Payments"])

MIN_TOPUP = 500.0
MAX_TOPUP = 500_000.0


class CardTopUpRequest(BaseModel):
    amount: float = Field(ge=MIN_TOPUP, le=MAX_TOPUP)


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
        raise HTTPException(status_code=503, detail="Card payments are not configured on this deployment")
    intent = payment_gateway.create_topup_intent(payload.amount, current_user.id, f"topup:{current_user.id}")
    db.add(CardTopUp(intent_id=intent.intent_id, user_id=current_user.id, amount=payload.amount))
    db.commit()
    record_audit(db, event_type="payments.intent_created", endpoint="/api/v1/payments/card/topup", verdict="created", actor=f"user:{current_user.email}")
    db.commit()
    return {"intent_id": intent.intent_id, "client_secret": intent.client_secret, "amount": intent.amount, "currency": intent.currency}


@router.post("/webhook")
async def stripe_webhook(request: Request, stripe_signature: str = Header(default="")):
    if not payment_gateway.stripe_configured():
        raise HTTPException(status_code=503, detail="Card payments are not configured on this deployment")
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
