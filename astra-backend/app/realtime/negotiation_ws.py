"""A2A engine: buyer agent vs seller agent negotiating live over WebSocket.

The room streams every round (buyer proposal → seller counter) together with
the agents' target parameters and a convergence progress value, then settles
the deal deterministically within MAX_ROUNDS. The settled session is
persisted through the existing NegotiationSession/NegotiationRound models.
"""
import asyncio
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import func

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.security import decode_access_token
from app.models.deal import MarketPriceHistory
from app.models.negotiation import NegotiationRound, NegotiationSession
from app.models.product import Product
from app.models.wallet import UserWallet
from app.models.user import User
from app.services.shopping_memory import get_user_shopping_preferences, negotiation_preferences
from app.services.localization import detect_locale, mirror_language_text

router = APIRouter()

MAX_ROUNDS = 6
ROUND_PAUSE_SECONDS = 0.45


def _load_context(product_id: str, user_id: int, quantity: int, size: str, color: str, storage: str) -> dict | None:
    db = SessionLocal()
    try:
        product = db.get(Product, product_id)
        if product is None or product.listing_status != "active" or quantity < 1 or quantity > product.stock_count:
            return None
        average = db.query(func.avg(MarketPriceHistory.price)).filter(MarketPriceHistory.product_id == product_id).scalar()
        wallet = db.query(UserWallet).filter(UserWallet.user_id == user_id).first()
        user = db.get(User, user_id)
        if wallet is None:
            return None
        market_average = float(average) if average is not None else None
        floor_pct = 0.10 + (100 - product.trust) / 200
        return {
            "product": product,
            "list_price": product.base_price,
            "market_average": round(market_average, 2) if market_average is not None else None,
            "floor": round(max(product.base_price * (1 - floor_pct), product.base_price * 0.75), 2),
            # Negotiation uses a conservative 7% cap below list price, further
            # bounded by the buyer's actual available wallet balance.
            "buyer_budget": round(min(wallet.available_balance / quantity, product.base_price * 0.93), 2),
            "quantity": quantity,
            "size": size,
            "color": color,
            "storage": storage,
            "buyer_preferences": negotiation_preferences(get_user_shopping_preferences(db, user_id)),
            "preferred_language": user.preferred_language if user else "en",
        }
    finally:
        db.close()


def _persist_session(product_id: str, user_id: int, context: dict, rounds: list[dict], final_price: float) -> int:
    db = SessionLocal()
    try:
        product = context["product"]
        session = NegotiationSession(
            user_id=user_id, product_id=product_id, seller_id=product.seller_id,
            quantity=context["quantity"], size=context["size"], color=context["color"],
            storage=context["storage"], status="accepted", final_price=final_price,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
        )
        db.add(session)
        db.flush()
        for index, round_data in enumerate(rounds, start=1):
            db.add(NegotiationRound(
                session_id=session.id, round_number=index,
                buyer_offer=round_data["buyer"], seller_ask=round_data["seller"],
                counter_offer=round_data["seller"], status="accepted" if index == len(rounds) else "counter",
                provider="a2a", reasoning_json="[]",
            ))
        db.commit()
        return session.id
    finally:
        db.close()


@router.websocket("/ws/negotiation/{product_id}")
async def a2a_negotiation(websocket: WebSocket, product_id: str) -> None:
    token = websocket.cookies.get(settings.AUTH_COOKIE_NAME)
    payload = decode_access_token(token) if token else None
    if not payload:
        await websocket.close(code=1008, reason="Valid access token required")
        return
    try:
        user_id = int(payload.get("sub", 0) or 0)
    except (TypeError, ValueError):
        await websocket.close(code=1008, reason="Valid access token required")
        return
    if user_id <= 0:
        await websocket.close(code=1008, reason="Valid access token required")
        return

    await websocket.accept()
    try:
        start_message = await asyncio.wait_for(websocket.receive_json(), timeout=5)
        quantity = int(start_message.get("quantity", 1))
        size = str(start_message.get("size", ""))[:80]
        color = str(start_message.get("color", ""))[:80]
        storage = str(start_message.get("storage", ""))[:80]
        requested_locale = str(start_message.get("locale", ""))[:30]
        if start_message.get("type") != "start" or not 1 <= quantity <= 100:
            raise ValueError("invalid start message")
    except (asyncio.TimeoutError, ValueError, TypeError, AttributeError):
        await websocket.close(code=1008, reason="Valid negotiation details required")
        return
    context = await asyncio.to_thread(_load_context, product_id, user_id, quantity, size, color, storage)
    if context is None:
        await websocket.close(code=1008, reason="Product unavailable for requested quantity")
        return

    product = context["product"]
    response_locale = detect_locale("", requested_locale or context.get("preferred_language"))

    async def send_localized(message: dict) -> None:
        translated = dict(message)
        for key in ("message", "reason"):
            if isinstance(translated.get(key), str):
                translated[key] = await asyncio.to_thread(mirror_language_text, translated[key], response_locale)
        await websocket.send_json(translated)
    list_price = context["list_price"]
    market_average = context["market_average"]
    floor = context["floor"]

    buyer_budget = context["buyer_budget"]
    buyer_opening = round(min(buyer_budget * 0.95, list_price * 0.93))
    seller_ask = round(list_price * 0.985)
    initial_gap = max(seller_ask - buyer_opening, 1)
    delay_threshold_ms = 900

    await send_localized({
        "type": "a2a_started",
        "product_id": product_id,
        "product_name": product.title,
            "quantity": quantity,
            "final_total": None,
        "params": {
            "buyer_agent": "ASTRA-Buyer",
            "seller_agent": f"{product.seller_name} · Seller-Agent",
            "buyer_budget": buyer_budget,
            "buyer_opening_offer": buyer_opening,
            "delay_threshold_ms": delay_threshold_ms,
            "seller_ask": seller_ask,
            "seller_floor": floor,
            "market_average": market_average,
            "market_data_available": market_average is not None,
            "max_rounds": MAX_ROUNDS,
            "buyer_preferences": context["buyer_preferences"],
        },
    })

    if buyer_budget < floor:
        await send_localized({
            "type": "deal_rejected", "status": "rejected", "proposed_offer": buyer_opening,
            "seller_floor": floor, "buyer_budget": buyer_budget,
            "reason": "Available wallet balance does not meet the deterministic seller-floor estimate.",
        })
        return

    buyer_offer = buyer_opening
    rounds: list[dict] = []
    final_price: float | None = None
    try:
        for round_number in range(1, MAX_ROUNDS + 1):
            gap = seller_ask - buyer_offer
            progress = round(min(max(1 - gap / initial_gap, 0), 1), 3)
            await send_localized({
                "type": "buyer_offer", "round": round_number, "agent": "ASTRA-Buyer",
                "offer": buyer_offer, "progress": progress,
                "message": f"Available wallet balance Rs. {buyer_budget:,.0f}; offering Rs. {buyer_offer:,}." + (f" Observed market average Rs. {market_average:,.0f}." if market_average is not None else " No market history is available."),
            })
            await asyncio.sleep(ROUND_PAUSE_SECONDS)

            if round_number >= MAX_ROUNDS or gap <= initial_gap * 0.08:
                final_price = round((buyer_offer + seller_ask) / 2 / 50) * 50
                if floor > buyer_budget:
                    await send_localized({
                        "type": "deal_rejected", "status": "rejected", "proposed_offer": buyer_offer,
                        "seller_floor": floor, "buyer_budget": buyer_budget,
                        "reason": "The seller-floor estimate exceeds the buyer wallet balance.",
                    })
                    return
                final_price = min(max(final_price, floor), buyer_budget)
                rounds.append({"buyer": buyer_offer, "seller": seller_ask})
                break

            seller_next = round(buyer_offer + gap * 0.72 / 50) * 50
            seller_next = max(seller_next, floor)
            await send_localized({
                "type": "seller_counter", "round": round_number, "agent": "Seller-Agent",
                "ask": seller_next, "progress": progress,
                "message": f"Floor protected at Rs. {floor:,}; countering at Rs. {seller_next:,}.",
            })
            rounds.append({"buyer": buyer_offer, "seller": seller_next})
            buyer_offer = min(buyer_budget, round(buyer_offer + (seller_next - buyer_offer) * 0.48 / 50) * 50)
            seller_ask = seller_next
            await asyncio.sleep(ROUND_PAUSE_SECONDS)
        else:
            final_price = round((buyer_offer + seller_ask) / 2 / 50) * 50

        negotiation_session_id = await asyncio.to_thread(_persist_session, product_id, user_id, context, rounds, final_price)
        await send_localized({
            "type": "deal_settled", "final_price": final_price, "rounds": len(rounds),
            "session_id": negotiation_session_id, "quantity": quantity,
            "final_total": round(final_price * quantity, 2),
            "list_price": list_price,
            "savings_vs_list": round(list_price - final_price, 2),
            "message": f"A2A handshake complete — deal sealed at Rs. {final_price:,} after {len(rounds)} rounds.",
        })
        while True:
            message = await websocket.receive_text()
            if message == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        return
