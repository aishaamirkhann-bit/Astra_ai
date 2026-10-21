import json
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.deal import MarketPriceHistory
from app.models.negotiation import NegotiationRound, NegotiationSession
from app.models.product import Product
from app.models.user import User
from app.models.wallet import UserWallet
from app.services.audit import record_audit
from app.services.groq_negotiation import request_groq_decision
from app.services.shopping_memory import get_user_shopping_preferences, negotiation_preferences
from app.services.checkout_fsm import _money
from app.services.order_operations import calculate_bundle_offer
from app.services.localization import detect_locale, mirror_language_text
from app.utils.helpers import as_aware_utc

router = APIRouter(prefix="/negotiation", tags=["AI Negotiator"])
MAX_ROUNDS = 6


class NegotiationOffer(BaseModel):
    offer_price: float = Field(gt=0)
    round: int = Field(default=1, ge=1, le=MAX_ROUNDS + 1)
    session_id: int | None = Field(default=None, ge=1)
    quantity: int = Field(default=1, ge=1, le=100)
    size: str = Field(default="", max_length=80)
    color: str = Field(default="", max_length=80)
    storage: str = Field(default="", max_length=80)
    locale: str | None = Field(default=None, max_length=30)


class NegotiationRoundOut(BaseModel):
    session_id: int
    product_id: str
    round: int
    status: str
    seller_ask: float
    counter_offer: float | None = None
    final_price: float | None = None
    market_average: float | None
    buyer_budget: float
    quantity: int
    final_total: float | None = None
    reasoning: list[str]


class BundleItemIn(BaseModel):
    product_id: str = Field(min_length=1, max_length=160)
    quantity: int = Field(ge=1, le=20)


class BundleOfferIn(BaseModel):
    items: list[BundleItemIn] = Field(min_length=1, max_length=10)


@router.post("/bundle/advisory")
def bundle_advisory(
    payload: BundleOfferIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Quote a non-binding, seller-floor-bounded bundle; this route writes nothing."""
    quantities: dict[str, int] = {}
    for requested in payload.items:
        quantities[requested.product_id] = quantities.get(requested.product_id, 0) + requested.quantity
    products = []
    for product_id, quantity in quantities.items():
        product = db.get(Product, product_id)
        if not product:
            raise HTTPException(status_code=404, detail=f"Product {product_id} not found")
        if product.listing_status != "active" or quantity > product.stock_count:
            raise HTTPException(status_code=409, detail=f"Requested quantity unavailable for {product.title}")
        floor = float(product.seller_price_floor or product.base_price)
        if floor <= 0 or floor > product.base_price:
            raise HTTPException(status_code=409, detail=f"Seller floor is not configured correctly for {product.title}")
        products.append({
            "product_id": product.id,
            "title": product.title,
            "quantity": quantity,
            "price": product.base_price,
            "seller_price_floor": floor,
        })
    try:
        quote = calculate_bundle_offer(products)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    quote["review_required"] = True
    quote["next_step"] = "Buyer may review this estimate, then use ordinary checkout with explicit financial consent."
    return quote


def _market_average(db: Session, product_id: str) -> float | None:
    average = db.query(func.avg(MarketPriceHistory.price)).filter(MarketPriceHistory.product_id == product_id).scalar()
    return float(average) if average is not None else None


def _get_session(db: Session, user_id: int, product: Product, payload: NegotiationOffer) -> NegotiationSession:
    product_id = product.id
    if product.listing_status != "active" or payload.quantity > product.stock_count:
        raise HTTPException(status_code=409, detail="Requested quantity is unavailable")
    if payload.session_id is not None:
        session = db.query(NegotiationSession).filter(NegotiationSession.id == payload.session_id).with_for_update().first()
        if session is None or session.user_id != user_id or session.product_id != product_id:
            raise HTTPException(status_code=404, detail="Negotiation session not found")
        if session.status != "active":
            raise HTTPException(status_code=409, detail="Negotiation session is already closed")
        if session.expires_at and as_aware_utc(session.expires_at) <= datetime.now(timezone.utc):
            session.status = "expired"
            raise HTTPException(status_code=410, detail="Negotiation session expired")
        if (session.seller_id != product.seller_id or session.quantity != payload.quantity
                or session.size != payload.size or session.color != payload.color or session.storage != payload.storage):
            raise HTTPException(status_code=409, detail="Negotiation product or quantity changed; start a new negotiation")
        expected_round = db.query(func.count(NegotiationRound.id)).filter(
            NegotiationRound.session_id == session.id
        ).scalar() + 1
        if payload.round != expected_round:
            raise HTTPException(status_code=409, detail="Negotiation round is out of sequence")
        return session
    if payload.quantity > product.stock_count or product.listing_status != "active":
        raise HTTPException(status_code=409, detail="Requested quantity is unavailable")
    session = NegotiationSession(
        user_id=user_id, product_id=product_id, seller_id=product.seller_id,
        quantity=payload.quantity, size=payload.size, color=payload.color, storage=payload.storage,
        status="active", expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
    )
    db.add(session)
    db.flush()
    return session


@router.post("/{product_id}/offer", response_model=NegotiationRoundOut)
def submit_offer(product_id: str, payload: NegotiationOffer, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    market_average = _market_average(db, product_id)
    wallet = db.query(UserWallet).filter(UserWallet.user_id == current_user.id).first()
    if wallet is None:
        raise HTTPException(status_code=409, detail="Buyer wallet is unavailable")
    buyer_budget = round(min(wallet.available_balance / payload.quantity, product.base_price * 0.93), 2)
    floor_pct = 0.10 + (100 - product.trust) / 200
    floor = round(max(product.base_price * (1 - floor_pct), product.base_price * 0.75), 2)
    ask = min(buyer_budget, max(floor, round(product.base_price * (1 - 0.02 * (payload.round - 1)), 2)))
    session = _get_session(db, current_user.id, product, payload)
    reasoning = [
        f"Observed 30-day market average Rs. {market_average:,.0f}." if market_average is not None else "No observed 30-day market history is available.",
        f"Deterministic seller-floor estimate uses listing price and trust ({product.trust}/100): Rs. {floor:,.0f}; it is not a seller-configured policy.",
        f"Buyer negotiation cap is Rs. {buyer_budget:,.0f}, bounded by current wallet balance.",
        f"Round {payload.round}: seller ask softened to Rs. {ask:,.0f}.",
    ]
    buyer_preferences = negotiation_preferences(get_user_shopping_preferences(db, current_user.id))
    response_locale = detect_locale("", payload.locale or current_user.preferred_language)
    if buyer_preferences:
        reasoning.append("Advisory buyer shopping preferences: " + json.dumps(buyer_preferences, ensure_ascii=False))
    status, counter, final_price, provider = "counter", None, None, "rules"
    if buyer_budget < floor:
        status = "rejected"
        reasoning.append("Available wallet balance is below the deterministic seller-floor estimate.")
    elif payload.round > MAX_ROUNDS:
        status = "rejected"
        reasoning.append("Negotiation window exhausted — seller walked away.")
    elif payload.offer_price > buyer_budget:
        status = "rejected"
        reasoning.append("Offer exceeds the buyer's available negotiation cap.")
    elif payload.offer_price >= ask:
        status, final_price = "accepted", payload.offer_price
        reasoning.append(f"Offer Rs. {payload.offer_price:,.0f} meets the ask — deal settled.")
    else:
        groq = request_groq_decision({
            "product": product.title, "round": payload.round, "buyer_offer": payload.offer_price,
            "seller_ask": ask, "seller_floor": floor, "market_average": market_average, "seller_trust": product.trust,
            "buyer_preferences": buyer_preferences,
            "response_locale": response_locale,
        })
        if groq and groq["status"] == "accepted" and not floor <= payload.offer_price <= ask:
            groq = None
        if groq is not None:
            provider, status = "groq", groq["status"]
            reasoning.extend(str(item) for item in groq["reasoning"][:4])
            if status == "accepted":
                final_price = payload.offer_price
            elif status == "counter":
                counter = round(max(floor, min(ask, float(groq.get("counter_offer") or ask))), 2)
        elif payload.offer_price < floor:
            reasoning.append(f"Offer Rs. {payload.offer_price:,.0f} is below the seller's Rs. {floor:,.0f} floor.")
            counter = max(floor, round((ask + floor) / 2 / 50) * 50)
        else:
            counter = max(floor, round((ask + payload.offer_price) / 2 / 50) * 50)
            reasoning.append(f"Counter-offer Rs. {counter:,.0f} splits the gap toward the buyer's Rs. {payload.offer_price:,.0f}.")
    if provider == "rules" and response_locale != "en":
        translated_reasoning = mirror_language_text("\n".join(reasoning), response_locale).splitlines()
        if len(translated_reasoning) == len(reasoning):
            reasoning = translated_reasoning
    db.add(NegotiationRound(
        session_id=session.id, round_number=payload.round, buyer_offer=payload.offer_price,
        seller_ask=ask, counter_offer=counter, status=status, provider=provider, reasoning_json=json.dumps(reasoning),
    ))
    if status in {"accepted", "rejected"}:
        session.status, session.final_price = status, final_price
        record_audit(
            db, event_type="negotiation.session", endpoint=f"/api/v1/negotiation/{product_id}/offer",
            verdict="approved" if status == "accepted" else "rejected", actor=f"user:{current_user.email}",
        )
    db.commit()
    return NegotiationRoundOut(
        session_id=session.id, product_id=product_id, round=payload.round, status=status,
        seller_ask=ask, counter_offer=counter, final_price=final_price, market_average=market_average,
        buyer_budget=buyer_budget, quantity=session.quantity,
        final_total=round(final_price * session.quantity, 2) if final_price is not None else None,
        reasoning=reasoning,
    )


class NegotiationApprovalOut(BaseModel):
    session_id: int
    status: str
    product_id: str
    seller_id: str
    quantity: int
    unit_price: float
    total: float


@router.post("/sessions/{session_id}/approve", response_model=NegotiationApprovalOut)
def approve_negotiated_offer(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = db.query(NegotiationSession).filter(
        NegotiationSession.id == session_id,
        NegotiationSession.user_id == current_user.id,
    ).with_for_update().first()
    if not session:
        raise HTTPException(status_code=404, detail="Negotiation session not found")
    if session.status not in {"accepted", "buyer_approved"} or session.final_price is None:
        raise HTTPException(status_code=409, detail="Only a valid accepted offer can be buyer-approved")
    if not session.expires_at or as_aware_utc(session.expires_at) <= datetime.now(timezone.utc):
        session.status = "expired"
        db.commit()
        raise HTTPException(status_code=410, detail="Negotiation offer expired; negotiate again")
    product = db.query(Product).filter(Product.id == session.product_id).first()
    if (
        not product or product.listing_status != "active"
        or product.seller_id != session.seller_id
        or session.quantity < 1 or session.quantity > product.stock_count
        or _money(session.final_price) > _money(product.price)
    ):
        raise HTTPException(status_code=409, detail="Negotiated offer details are no longer valid")
    session.status = "buyer_approved"
    session.buyer_approved_at = datetime.now(timezone.utc)
    db.commit()
    return NegotiationApprovalOut(
        session_id=session.id, status=session.status, product_id=session.product_id,
        seller_id=session.seller_id, quantity=session.quantity, unit_price=session.final_price,
        total=round(session.final_price * session.quantity, 2),
    )
