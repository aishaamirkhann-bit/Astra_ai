import json
import math
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal, engine
from app.data import PRODUCTS
from app.models.deal import Deal, DealAuditLog, DealReservation, MarketPriceHistory, SellerMetric
from app.models.product import Product
from app.models.order import Order, OrderStatus
from app.schemas.deal import (
    DealDetail,
    DealListResponse,
    DealReservationResponse,
    DealSummary,
    PriceHistoryPoint,
    ReserveDealRequest,
    TrustScoreBreakdown,
)
from app.utils.helpers import format_pkr

MINIMUM_DISCOUNT_PERCENT = 15.0
MINIMUM_TRUST_SCORE = 75.0

CATEGORY_MAP = {
    "Mobiles": "Tech",
    "Laptops & Computers": "Tech",
    "Home Appliances": "Tech",
    "Clothing & Fashion": "Fashion",
    "Makeup & Beauty": "Fashion",
    "Audio & Wearables": "Audio",
    "Jewelry": "Accessories",
}
SEED_DISCOUNTS = {"Deal": 24.0, "Bestseller": 18.0, "New": 16.0}
STOCK_BY_SLUG = {
    "samsung-galaxy-s25-ultra": 3,
    "xiaomi-14-civi": 7,
    "anker-soundcore-q45": 3,
    "gold-plated-jhumka-earrings": 5,
    "embroidered-lawn-3pc-suit": 8,
    "matte-liquid-lipstick-set": 4,
}


@dataclass(frozen=True)
class DealDomainEvent:
    type: str
    deal_id: str
    product_id: str
    stock_remaining: int | None = None

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"type": self.type, "deal_id": self.deal_id, "product_id": self.product_id}
        if self.stock_remaining is not None:
            payload["stock_remaining"] = self.stock_remaining
        return payload


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def bootstrap_deals_data(db: Session) -> None:
    """Idempotently synchronize catalog, metrics, and initial market observations."""
    now = datetime.now(timezone.utc)

    # Pass 1 — upsert products, then flush so FK-dependent rows below can
    # reference them. (SQLite never enforced the FK, which masked this order.)
    for item in PRODUCTS:
        seller_id = _slug(item["seller_name"])
        product = db.get(Product, item["id"])
        values = {
            "title": item["title"], "category": item["category"], "base_price": item["price"],
            "rating": item["rating"], "total_reviews": item["total_reviews"],
            "seller_name": item["seller_name"], "seller_id": seller_id,
            "is_verified_seller": item["is_verified_seller"], "badge": item["badge"],
            "image_url": item["image_url"], "semantic_tags": json.dumps(item["semantic_tags"]),
            "description": item["description"], "fit": item["fit"], "trust": item["trust"],
            "search_terms": item["search_terms"],
        }
        if product is None:
            product = Product(id=item["id"], stock_count=STOCK_BY_SLUG.get(item["id"], 10), **values)
            db.add(product)
        else:
            for key, value in values.items():
                setattr(product, key, value)
            reservation_count = db.scalar(
                select(func.count(DealReservation.id)).join(Deal, Deal.id == DealReservation.deal_id)
                .where(Deal.product_id == item["id"])
            ) or 0
            if product.stock_count is None or (product.stock_count == 10 and reservation_count == 0):
                product.stock_count = STOCK_BY_SLUG.get(item["id"], 10)
    db.flush()

    # Pass 2 — seller metrics + initial market price observations.
    for item in PRODUCTS:
        seller_id = _slug(item["seller_name"])
        metric = db.get(SellerMetric, seller_id)
        target = float(item["trust"])
        seller_rating = min(100.0, target + (2.0 if item["is_verified_seller"] else -1.0))
        fulfillment = min(100.0, target + (1.0 if item["is_verified_seller"] else -2.0))
        seller_component = (seller_rating + fulfillment) / 2
        authenticity = min(100.0, target + (1.0 if item["rating"] >= 4.5 else -1.0))
        stability = max(0.0, min(100.0, (target - 0.4 * seller_component - 0.4 * authenticity) / 0.2))
        if metric is None:
            metric = SellerMetric(seller_id=seller_id, seller_name=item["seller_name"])
            db.add(metric)
        metric.seller_rating = seller_rating
        metric.fulfillment_rate = fulfillment
        metric.authenticity_sentiment = authenticity
        metric.price_stability = stability
        metric.updated_at = now

        observation_count = db.scalar(
            select(func.count(MarketPriceHistory.id)).where(MarketPriceHistory.product_id == item["id"])
        ) or 0
        if observation_count == 0:
            discount = SEED_DISCOUNTS.get(str(item.get("badge")), 8.0)
            market_average = float(item["price"]) / (1 - discount / 100)
            for days, multiplier, competitor in [(28, 1.02, "Market A"), (14, 0.99, "Market B"), (7, 1.01, "Market C"), (1, 0.98, "Market D")]:
                db.add(MarketPriceHistory(
                    product_id=item["id"], competitor=competitor,
                    price=round(market_average * multiplier, 2), observed_at=now - timedelta(days=days),
                ))
    db.commit()


def evaluate_deals(db: Session) -> list[DealDomainEvent]:
    """Evaluate the rolling market average and atomically persist deal state."""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=30)
    averages = dict(db.execute(
        select(MarketPriceHistory.product_id, func.avg(MarketPriceHistory.price))
        .where(MarketPriceHistory.observed_at >= cutoff)
        .group_by(MarketPriceHistory.product_id)
    ).all())
    metrics = {metric.seller_id: metric for metric in db.scalars(select(SellerMetric)).all()}
    existing = {deal.product_id: deal for deal in db.scalars(select(Deal)).all()}
    events: list[DealDomainEvent] = []

    for product in db.scalars(select(Product)).all():
        market_average = float(averages.get(product.id) or 0)
        metric = metrics.get(product.seller_id)
        if market_average <= 0 or metric is None:
            continue
        seller_component = (metric.seller_rating + metric.fulfillment_rate) / 2
        trust_score = round(0.4 * seller_component + 0.4 * metric.authenticity_sentiment + 0.2 * metric.price_stability, 2)
        discount_pct = round((market_average - product.base_price) / market_average * 100, 2)
        eligible = discount_pct >= MINIMUM_DISCOUNT_PERCENT and trust_score >= MINIMUM_TRUST_SCORE and product.stock_count > 0
        deal = existing.get(product.id)

        if deal is not None and _as_utc(deal.deal_expires_at) and _as_utc(deal.deal_expires_at) <= now:
            if deal.is_active:
                deal.is_active = False
                deal.updated_at = now
                db.add(DealAuditLog(
                    deal_id=deal.id, product_id=product.id, event_type="deal_expired", decision="expired",
                    reasoning={"reason": "deal_expires_at reached", "expired_at": deal.deal_expires_at.isoformat()},
                ))
                events.append(DealDomainEvent("deal_expired", deal.id, product.id, product.stock_count))
            continue

        if eligible:
            is_new = deal is None
            changed = is_new or not deal.is_active or any([
                abs((deal.listing_price if deal else 0) - product.base_price) >= 0.01,
                abs((deal.market_avg_price if deal else 0) - market_average) >= 0.01,
                abs((deal.trust_score if deal else 0) - trust_score) >= 0.01,
                (deal.stock_remaining if deal else -1) != product.stock_count,
            ])
            if is_new:
                deal = Deal(product_id=product.id, created_at=now)
                db.add(deal)
            deal.listing_price = product.base_price
            deal.market_avg_price = round(market_average, 2)
            deal.discount_pct = discount_pct
            deal.trust_score = trust_score
            deal.seller_fulfillment_score = round(seller_component, 2)
            deal.authenticity_sentiment_score = round(metric.authenticity_sentiment, 2)
            deal.price_stability_score = round(metric.price_stability, 2)
            deal.badge_type = "Mega Deal" if discount_pct >= 22 else (product.badge if product.badge in {"Bestseller", "New"} else "Mega Deal")
            deal.stock_remaining = product.stock_count
            deal.is_active = True
            if changed:
                deal.updated_at = now
            if deal.badge_type == "Mega Deal" and (_as_utc(deal.deal_expires_at) or now) <= now:
                deal.deal_expires_at = now + timedelta(hours=12)
            db.flush()
            if changed:
                db.add(DealAuditLog(
                    deal_id=deal.id, product_id=product.id, event_type="deal_updated", decision="approved",
                    reasoning={
                        "listing_price": product.base_price, "rolling_30d_market_average": round(market_average, 2),
                        "discount_pct": discount_pct, "minimum_discount_pct": MINIMUM_DISCOUNT_PERCENT,
                        "trust_score": trust_score, "minimum_trust_score": MINIMUM_TRUST_SCORE,
                        "formula": "seller_fulfillment*0.4 + authenticity_sentiment*0.4 + price_stability*0.2",
                        "components": {"seller_fulfillment": round(seller_component, 2), "authenticity_sentiment": round(metric.authenticity_sentiment, 2), "price_stability": round(metric.price_stability, 2)},
                    },
                ))
                events.append(DealDomainEvent("deal_updated", deal.id, product.id, product.stock_count))
        elif deal is not None and deal.is_active:
            deal.is_active = False
            deal.updated_at = now
            db.add(DealAuditLog(
                deal_id=deal.id, product_id=product.id, event_type="deal_expired", decision="rejected",
                reasoning={"discount_pct": discount_pct, "trust_score": trust_score, "stock_count": product.stock_count, "reason": "eligibility threshold no longer satisfied"},
            ))
            events.append(DealDomainEvent("deal_expired", deal.id, product.id, product.stock_count))

    db.commit()
    return events


def _trust(deal: Deal, product: Product) -> TrustScoreBreakdown:
    return TrustScoreBreakdown(
        overall=deal.trust_score,
        seller_fulfillment=deal.seller_fulfillment_score,
        authenticity_sentiment=deal.authenticity_sentiment_score,
        price_stability=deal.price_stability_score,
        seller_verified=product.is_verified_seller,
        summary=f"Seller Rating: {deal.seller_fulfillment_score:.0f}% | Price History: Lowest in 30 Days",
    )


def _category(product: Product) -> str:
    return CATEGORY_MAP.get(product.category, "Accessories")


def _summary(deal: Deal, product: Product) -> DealSummary:
    savings = round(deal.market_avg_price - deal.listing_price, 2)
    return DealSummary(
        id=deal.id, slug=product.id, name=product.title,
        price_display=format_pkr(deal.listing_price), price=deal.listing_price,
        market_price_display=format_pkr(deal.market_avg_price), market_price=deal.market_avg_price,
        savings_display=format_pkr(savings), savings=savings, discount_percent=deal.discount_pct,
        rating=product.rating, total_reviews=product.total_reviews, tag=deal.badge_type,
        trust=_trust(deal, product), seller=product.seller_name, category=_category(product),
        image=product.image_url, stock_remaining=deal.stock_remaining,
        expires_at=_as_utc(deal.deal_expires_at).isoformat() if deal.deal_expires_at else None,
    )


def list_active_deals(db: Session, category: str | None, sort_by: str, page: int, page_size: int) -> DealListResponse:
    now = datetime.now(timezone.utc)
    query = select(Deal, Product).join(Product, Product.id == Deal.product_id).where(
        Deal.is_active.is_(True),
        or_(Deal.deal_expires_at.is_(None), Deal.deal_expires_at > now),
    )
    if category:
        catalog_categories = [key for key, value in CATEGORY_MAP.items() if value == category]
        query = query.where(Product.category.in_(catalog_categories))
    order = Deal.discount_pct.desc() if sort_by == "highest_discount" else Deal.trust_score.desc()
    query = query.order_by(order, Deal.updated_at.desc())
    total = db.scalar(select(func.count()).select_from(query.order_by(None).subquery())) or 0
    rows = db.execute(query.offset((page - 1) * page_size).limit(page_size)).all()
    return DealListResponse(
        items=[_summary(deal, product) for deal, product in rows], total=total,
        page=page, page_size=page_size, total_pages=math.ceil(total / page_size) if total else 0,
    )


def _variant_options(product: Product) -> tuple[list[str], list[str]]:
    if product.category == "Clothing & Fashion": return ["S", "M", "L", "XL"], ["Sage", "Rose", "Midnight"]
    if product.category == "Makeup & Beauty": return ["6-Pack"], ["Nude Edit", "Berry Edit"]
    if product.category == "Jewelry": return ["One Size"], ["Antique Gold", "Champagne Gold"]
    return ["Standard"], ["Graphite", "Silver"]


def get_deal_details(db: Session, deal_id: str) -> DealDetail:
    now = datetime.now(timezone.utc)
    row = db.execute(
        select(Deal, Product).join(Product, Product.id == Deal.product_id)
        .where(
            Deal.id == deal_id,
            Deal.is_active.is_(True),
            or_(Deal.deal_expires_at.is_(None), Deal.deal_expires_at > now),
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Active deal not found")
    deal, product = row
    history = db.scalars(
        select(MarketPriceHistory).where(
            MarketPriceHistory.product_id == product.id,
            MarketPriceHistory.observed_at >= now - timedelta(days=30),
        ).order_by(MarketPriceHistory.observed_at)
    ).all()
    sizes, colors = _variant_options(product)
    image = product.image_url
    gallery = [image, f"{image}&sat=-12", f"{image}&contrast=8"] if "?" in image else [image]
    summary = _summary(deal, product).model_dump()
    audit = db.scalar(
        select(DealAuditLog).where(
            DealAuditLog.deal_id == deal.id,
            DealAuditLog.event_type == "deal_updated",
            DealAuditLog.decision == "approved",
        ).order_by(DealAuditLog.created_at.desc()).limit(1)
    )
    return DealDetail(
        **summary, description=product.description, gallery=gallery, sizes=sizes, colors=colors,
        price_history=[PriceHistoryPoint(
            observed_at=_as_utc(point.observed_at).isoformat(), label=_as_utc(point.observed_at).strftime("%d %b"),
            listing_price=deal.listing_price, market_average=point.price,
        ) for point in history], audit_reasoning=audit.reasoning if audit else {},
    )


def reserve_deal(deal_id: str, payload: ReserveDealRequest, user_id: int) -> tuple[DealReservationResponse, DealDomainEvent]:
    """Reserve inventory under a row lock; no stock can fall below zero."""
    db = SessionLocal()
    try:
        if engine.dialect.name == "sqlite":
            db.execute(text("BEGIN IMMEDIATE"))
        deal = db.scalar(select(Deal).where(Deal.id == deal_id, Deal.is_active.is_(True)).with_for_update())
        if deal is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Active deal not found")
        product = db.scalar(select(Product).where(Product.id == deal.product_id).with_for_update())
        now = datetime.now(timezone.utc)
        if product is None or (_as_utc(deal.deal_expires_at) and _as_utc(deal.deal_expires_at) <= now):
            deal.is_active = False
            db.commit()
            raise HTTPException(status_code=status.HTTP_410_GONE, detail="Deal has expired")
        if product.stock_count < payload.quantity:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Insufficient stock for this reservation")

        product.stock_count -= payload.quantity
        deal.stock_remaining = product.stock_count
        reservation = DealReservation(
            deal_id=deal.id, user_id=user_id, quantity=payload.quantity,
            size=payload.size or "", color=payload.color or "",
            expires_at=now + timedelta(minutes=settings.DEAL_RESERVATION_MINUTES),
        )
        db.add(reservation)
        db.flush()
        order = Order(
            order_ref=f"ORD-{reservation.id[:8].upper()}", user_id=user_id,
            product_id=product.id, reservation_id=reservation.id,
            quantity=payload.quantity, size=payload.size or "", color=payload.color or "",
            price=deal.listing_price * payload.quantity,
            status=OrderStatus.PENDING_APPROVAL,
            approval_deadline=reservation.expires_at,
        )
        db.add(order)
        db.add(DealAuditLog(
            deal_id=deal.id, product_id=product.id, event_type="stock_changed", decision="reserved",
            reasoning={"reservation_id": reservation.id, "quantity": payload.quantity, "stock_remaining": product.stock_count, "lock": "redis_distributed_lock + database_row_lock"},
        ))
        if product.stock_count == 0:
            deal.is_active = False
        db.flush()
        response = DealReservationResponse(
            reservation_id=reservation.id, deal_id=deal.id, status="reserved", quantity=payload.quantity,
            stock_remaining=product.stock_count, expires_at=_as_utc(reservation.expires_at).isoformat(),
            order_ref=order.order_ref,
            message="Stock reserved. Complete approval before the reservation expires.",
        )
        event = DealDomainEvent("deal_expired" if product.stock_count == 0 else "stock_changed", deal.id, product.id, product.stock_count)
        db.commit()
        return response, event
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def release_expired_reservations(db: Session) -> list[DealDomainEvent]:
    """Return abandoned reservation stock under row locks and emit corrections."""
    now = datetime.now(timezone.utc)
    reservations = db.scalars(
        select(DealReservation)
        .where(DealReservation.status == "reserved", DealReservation.expires_at <= now)
        .with_for_update(skip_locked=engine.dialect.name == "postgresql")
    ).all()
    events: list[DealDomainEvent] = []
    for reservation in reservations:
        deal = db.scalar(select(Deal).where(Deal.id == reservation.deal_id).with_for_update())
        if deal is None:
            reservation.status = "expired"
            continue
        product = db.scalar(select(Product).where(Product.id == deal.product_id).with_for_update())
        if product is None:
            reservation.status = "expired"
            continue
        product.stock_count += reservation.quantity
        deal.stock_remaining = product.stock_count
        if not deal.deal_expires_at or _as_utc(deal.deal_expires_at) > now:
            deal.is_active = True
        reservation.status = "expired"
        order = db.scalar(select(Order).where(Order.reservation_id == reservation.id))
        if order and order.status == OrderStatus.PENDING_APPROVAL:
            order.status = OrderStatus.CANCELLED
        db.add(DealAuditLog(
            deal_id=deal.id, product_id=product.id, event_type="stock_changed", decision="reservation_released",
            reasoning={"reservation_id": reservation.id, "quantity_restored": reservation.quantity, "stock_remaining": product.stock_count},
        ))
        events.append(DealDomainEvent("stock_changed", deal.id, product.id, product.stock_count))
    db.commit()
    return events


def finalize_reversal_orders(db: Session) -> None:
    """Confirm approved orders once their reversible checkout window closes."""
    now = datetime.now(timezone.utc)
    orders = db.scalars(select(Order).where(
        Order.status == OrderStatus.REVERSAL_WINDOW_OPEN,
        Order.reversal_deadline <= now,
    )).all()
    for order in orders:
        order.status = OrderStatus.CONFIRMED
    if orders:
        db.commit()
