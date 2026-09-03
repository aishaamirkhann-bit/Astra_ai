import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.deal import MarketPriceHistory
from app.models.negotiation import NegotiationRound, NegotiationSession
from app.models.product import Product
from app.models.user import User
from app.services.audit import record_audit
from app.services.groq_negotiation import request_groq_decision

router = APIRouter(prefix="/negotiation", tags=["AI Negotiator"])
MAX_ROUNDS = 6


class NegotiationOffer(BaseModel):
    offer_price: float = Field(gt=0)
    round: int = Field(default=1, ge=1, le=MAX_ROUNDS + 1)
    session_id: int | None = Field(default=None, ge=1)


class NegotiationRoundOut(BaseModel):
    session_id: int
    product_id: str
    round: int
    status: str
    seller_ask: float
    counter_offer: float | None = None
    final_price: float | None = None
    market_average: float
    reasoning: list[str]


def _market_average(db: Session, product_id: str, fallback: float) -> float:
    average = db.query(func.avg(MarketPriceHistory.price)).filter(MarketPriceHistory.product_id == product_id).scalar()
    return float(average) if average else fallback


def _get_session(db: Session, user_id: int, product_id: str, session_id: int | None) -> NegotiationSession:
    if session_id is not None:
        session = db.get(NegotiationSession, session_id)
        if session is None or session.user_id != user_id or session.product_id != product_id:
            raise HTTPException(status_code=404, detail="Negotiation session not found")
        if session.status != "active":
            raise HTTPException(status_code=409, detail="Negotiation session is already closed")
        return session
    session = NegotiationSession(user_id=user_id, product_id=product_id, status="active")
    db.add(session)
    db.flush()
    return session


@router.post("/{product_id}/offer", response_model=NegotiationRoundOut)
def submit_offer(product_id: str, payload: NegotiationOffer, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    market_average = _market_average(db, product_id, product.base_price * 1.08)
    floor_pct = 0.10 + (100 - product.trust) / 200
    floor = round(market_average * (1 - floor_pct), 2)
    ask = max(floor, round(product.base_price * (1 - 0.02 * (payload.round - 1)), 2))
    session = _get_session(db, current_user.id, product_id, payload.session_id)
    reasoning = [
        f"Market average (30d) Rs. {market_average:,.0f}; listing Rs. {product.base_price:,.0f}.",
        f"Seller trust {product.trust}/100 sets a {floor_pct:.0%} max discount floor (Rs. {floor:,.0f}).",
        f"Round {payload.round}: seller ask softened to Rs. {ask:,.0f}.",
    ]
    status, counter, final_price, provider = "counter", None, None, "rules"
    if payload.round > MAX_ROUNDS:
        status = "rejected"
        reasoning.append("Negotiation window exhausted — seller walked away.")
    elif payload.offer_price >= ask:
        status, final_price = "accepted", payload.offer_price
        reasoning.append(f"Offer Rs. {payload.offer_price:,.0f} meets the ask — deal settled.")
    else:
        groq = request_groq_decision({
            "product": product.title, "round": payload.round, "buyer_offer": payload.offer_price,
            "seller_ask": ask, "seller_floor": floor, "market_average": market_average, "seller_trust": product.trust,
        })
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
        seller_ask=ask, counter_offer=counter, final_price=final_price, market_average=market_average, reasoning=reasoning,
    )
