from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_seller, get_current_user, get_db
from app.api.v1.endpoints.seller import _seller_slug
from app.models.cod_risk import CodRiskEvent
from app.models.order import Order, OrderStatus
from app.models.order_return import OrderReturnRequest
from app.models.product import Product
from app.models.user import User
from app.services.cod_risk_engine import score_cod_risk
from app.services.localization import cross_border_advisory, localized, normalize_locale, normalize_multilingual_text

router = APIRouter(prefix="/cod-risk", tags=["Advisory COD Risk"])


def _owned_order(ref: str, seller: User, db: Session) -> Order:
    order = db.query(Order).join(Product).filter(
        Order.order_ref == ref, Product.seller_id == _seller_slug(seller)
    ).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


def _assessment(order: Order, db: Session):
    history = db.query(Order).filter(Order.user_id == order.user_id, Order.id != order.id).all()
    delivered = sum(item.status == OrderStatus.DELIVERED for item in history)
    returned = db.query(OrderReturnRequest).filter(
        OrderReturnRequest.user_id == order.user_id,
        OrderReturnRequest.status.in_(["approved", "completed", "returned"]),
    ).count()
    average = sum(item.price for item in history if item.status == OrderStatus.DELIVERED) / delivered if delivered else None
    # This schema has no validated address-risk or phone-verification fields.
    return score_cod_risk(delivered_orders=delivered, return_count=returned,
                          order_total=order.price, historical_average=average,
                          route_risk=None, phone_verified=None)


@router.get("/orders/{order_ref}")
def get_order_risk(order_ref: str, seller: User = Depends(get_current_active_seller), db: Session = Depends(get_db)):
    order = _owned_order(order_ref, seller, db)
    risk = _assessment(order, db)
    event = db.query(CodRiskEvent).filter(CodRiskEvent.order_id == order.id).order_by(CodRiskEvent.id.desc()).first()
    buyer = db.get(User, order.user_id)
    international = bool(buyer and (order.product.origin_country or "PK").upper() != (buyer.country or "PK").upper())
    border_advisory = cross_border_advisory(order.product.origin_country or "PK", buyer.country if buyer else None, order.price, buyer.preferred_language if buyer else None)
    return {"order_ref": order.order_ref, "cod_status": "unrecorded", "score": risk.score, "level": risk.level,
            "factors": risk.factors, "signals": risk.signals,
            "payment_method_recorded": False, "cod_applicability": "not_recorded",
            "advisory_only": True, "confirmation_state": event.state if event else None,
            "cross_border_advisory": border_advisory,
            "settlement_guidance": "prepayment_or_escrow_review_recommended" if international else "domestic_cod_review",
            "settlement_automatically_changed": False}


class TriggerInput(BaseModel):
    language: str = Field(default="roman_urdu", min_length=2, max_length=32)

    @field_validator("language")
    @classmethod
    def supported_language(cls, value: str) -> str:
        raw = value.strip().lower().replace("-", "_")
        normalized = normalize_locale(value)
        valid = {"en", "english", "ur", "urdu", "ur_pk", "roman_urdu", "roman urdu", "pa", "punjabi", "pa_pk",
                 "ps", "pashto", "ps_pk", "sd", "sindhi", "sd_pk", "fa", "persian", "farsi", "fa_ir",
                 "zh", "chinese", "mandarin", "zh_cn", "ar", "arabic", "ar_ae"}
        if raw not in valid:
            raise ValueError("Unsupported confirmation language")
        if normalized not in {"en", "ur", "roman_urdu", "pa", "ps", "sd", "fa", "zh", "ar"}:
            raise ValueError("Unsupported confirmation language")
        return normalized


class ManualReviewInput(BaseModel):
    reason: str = Field(min_length=3, max_length=240)


@router.post("/orders/{order_ref}/confirmation")
def trigger_confirmation(order_ref: str, payload: TriggerInput,
                         seller: User = Depends(get_current_active_seller), db: Session = Depends(get_db)):
    order = _owned_order(order_ref, seller, db)
    risk = _assessment(order, db)
    if risk.score <= 70:
        raise HTTPException(status_code=409, detail="Confirmation trigger is available only above 70% risk")
    locale = normalize_locale(payload.language)
    prompt = localized(locale, "cod", amount=f"{order.price:,.0f}")
    buyer = db.get(User, order.user_id)
    border_advisory = cross_border_advisory(order.product.origin_country or "PK", buyer.country if buyer else None,
                                             order.price, locale)
    if border_advisory:
        prompt = f"{prompt}\n{border_advisory['message']}"
    event = CodRiskEvent(order_id=order.id, buyer_id=order.user_id,
                         seller_id=_seller_slug(seller), state="pending", prompt=prompt)
    db.add(event)
    db.commit()
    return {"state": event.state, "channel": "voice_or_whatsapp_payload", "prompt": prompt,
            "cross_border_advisory": border_advisory,
            "settlement_guidance": "prepayment_or_escrow_review_recommended" if border_advisory else "domestic_cod_review",
            "settlement_automatically_changed": False,
            "advisory_only": True, "delivery_status": "not_sent_no_provider_configured"}


@router.post("/orders/{order_ref}/manual-review")
def record_manual_review(order_ref: str, payload: ManualReviewInput,
                         seller: User = Depends(get_current_active_seller), db: Session = Depends(get_db)):
    order = _owned_order(order_ref, seller, db)
    event = CodRiskEvent(order_id=order.id, buyer_id=order.user_id,
                         seller_id=_seller_slug(seller), state="merchant_reviewed",
                         prompt=f"Merchant review: {payload.reason.strip()}")
    db.add(event)
    db.commit()
    return {"state": event.state, "order_ref": order.order_ref, "advisory_only": True}


class BuyerConfirmation(BaseModel):
    confirmed: bool
    phrase: str = Field(min_length=2, max_length=20)


@router.post("/orders/{order_ref}/voice-confirmation")
def confirm_by_buyer(order_ref: str, payload: BuyerConfirmation,
                     buyer: User = Depends(get_current_user), db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.order_ref == order_ref, Order.user_id == buyer.id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    event = db.query(CodRiskEvent).filter(CodRiskEvent.order_id == order.id, CodRiskEvent.state == "pending").order_by(CodRiskEvent.id.desc()).first()
    if not event:
        raise HTTPException(status_code=409, detail="No pending confirmation")
    confirmation = normalize_multilingual_text(payload.phrase).strip().casefold()
    if not payload.confirmed or confirmation not in {"yes", "confirm"}:
        raise HTTPException(status_code=422, detail="Explicit Yes/Haan confirmation is required")
    event.state = "VERIFIED"
    event.confirmed_at = datetime.now(timezone.utc)
    db.commit()
    return {"state": "VERIFIED", "order_ref": order.order_ref, "advisory_only": True}
