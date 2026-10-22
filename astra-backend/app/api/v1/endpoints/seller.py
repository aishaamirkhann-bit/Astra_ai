import re
import json
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_seller, get_db
from app.core.config import settings
from app.models.order import Order
from app.models.order import OrderStatus
from app.models.negotiation import NegotiationSession
from app.models.product import Product
from app.models.order_return import OrderReturnRequest
from app.models.user import User
from app.models.trust import SellerVerification
from app.models.seller_profile import SellerProfile
from app.models.sales_goal import SalesGoal
from app.models.seller_wallet import SellerWallet, SellerWalletEntry
from app.services.barcode_catalog import lookup_barcode
from app.services.checkout_fsm import dispatch_confirmed_order
from app.services.seller_payouts import (
    connect_account_status,
    retry_seller_transfers,
    SellerPayoutsUnavailable,
    start_connect_onboarding,
)
from app.services.seller_analytics import build_seller_insights
from app.services.cod_risk_engine import score_cod_risk

router = APIRouter(prefix="/seller", tags=["Seller Dashboard"])


class InventoryInput(BaseModel):
    title: str = Field(min_length=2, max_length=160)
    category: str = Field(min_length=2, max_length=80)
    price: float = Field(gt=0)
    seller_price_floor: float | None = Field(default=None, gt=0)
    stock_count: int = Field(ge=0)
    description: str = Field(default="", max_length=2000)
    image_url: str = "/images/products/default-product.png"
    barcode: str | None = Field(default=None, min_length=8, max_length=14, pattern=r"^[0-9]+$")
    brand: str = Field(default="", max_length=120)
    subcategory: str = Field(default="", max_length=120)
    color: str = Field(default="", max_length=80)
    size: str = Field(default="", max_length=80)
    variant: str = Field(default="", max_length=120)
    specifications: dict[str, str] = Field(default_factory=dict)
    quality_tags: list[str] = Field(default_factory=list, max_length=20)
    status: str = Field(default="active", pattern=r"^(active|inactive|low_stock)$")


class InventoryUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=160)
    category: str | None = Field(default=None, min_length=2, max_length=80)
    price: float | None = Field(default=None, gt=0)
    seller_price_floor: float | None = Field(default=None, gt=0)
    stock_count: int | None = Field(default=None, ge=0)
    description: str | None = Field(default=None, max_length=2000)
    image_url: str | None = None
    status: str | None = Field(default=None, pattern=r"^(active|inactive|low_stock)$")


class BarcodeLookupInput(BaseModel):
    barcode: str = Field(min_length=8, max_length=14, pattern=r"^[0-9]+$")


class SellerGoalInput(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    target_amount: float = Field(gt=0)
    deadline: str | None = Field(default=None, max_length=20)


class SellerOrderStatusInput(BaseModel):
    order_status: str = Field(pattern=r"^shipped$")


class SellerOrderCollectionUpdate(SellerOrderStatusInput):
    order_ref: str = Field(min_length=4, max_length=30)


class PayoutRequestInput(BaseModel):
    amount: float = Field(gt=0)


class SellerAssistantQuery(BaseModel):
    query: str = Field(min_length=1, max_length=500)


def _seller_assistant_reply(query: str, seller: User, db: Session) -> str:
    """Build a seller-scoped, read-only summary from current workspace records."""
    seller_id = _seller_slug(seller)
    products = db.query(Product).filter(Product.seller_id == seller_id).all()
    orders = db.query(Order).join(Product).filter(Product.seller_id == seller_id).order_by(Order.created_at.desc()).limit(100).all()
    text = query.casefold()
    if any(word in text for word in ("cod", "risk", "confirmation", "confirm")):
        high_risk = 0
        for order in orders:
            if order.status in {OrderStatus.CANCELLED, OrderStatus.DELIVERED}:
                continue
            history = db.query(Order).filter(Order.user_id == order.user_id, Order.id != order.id, Order.status == OrderStatus.DELIVERED).all()
            average = sum(item.price for item in history) / len(history) if history else None
            returns = db.query(OrderReturnRequest).filter(
                OrderReturnRequest.user_id == order.user_id,
                OrderReturnRequest.status.in_(("approved", "completed", "returned")),
            ).count()
            assessment = score_cod_risk(delivered_orders=len(history), return_count=returns, order_total=order.price,
                                        historical_average=average, route_risk=None, phone_verified=None)
            high_risk += assessment.level == "HIGH"
        pending = sum(order.status in {OrderStatus.PENDING_APPROVAL, OrderStatus.REVERSAL_WINDOW_OPEN} for order in orders)
        return (f"I reviewed {len(orders)} recent seller orders. {high_risk} currently score as high COD risk and {pending} await order review. "
                "These scores are advisory only; review the COD Risk panel for order-level factors. No order was changed.")
    if any(word in text for word in ("bundle", "floor", "price", "discount", "pricing")):
        configured = [item for item in products if item.seller_price_floor is not None and item.seller_price_floor > 0]
        below_floor = sum(item.base_price < item.seller_price_floor for item in configured)
        return (f"You have {len(configured)} listings with seller price floors configured. "
                f"{below_floor} listed prices are below their saved floor and may need review. Bundle offers should be calculated from each item's floor; this assistant does not set or approve discounts.")
    if any(word in text for word in ("order", "shipment", "pending", "fulfillment", "return")):
        counts = {status.value: sum(order.status == status for order in orders) for status in OrderStatus}
        summary = ", ".join(f"{count} {status.replace('_', ' ')}" for status, count in counts.items() if count)
        return f"Across your {len(orders)} most recent orders: {summary or 'no order records yet'}. Use the Orders or Fulfillment page to review an order and take an allowed action. I have not changed any order."
    active = sum(item.listing_status == "active" for item in products)
    low_stock = sum(item.listing_status == "active" and item.stock_count < 5 for item in products)
    out_of_stock = sum(item.stock_count == 0 for item in products)
    return (f"Your seller catalog has {len(products)} listings: {active} active, {low_stock} active listings below 5 units, and {out_of_stock} out of stock. "
            "Open Merchant Insights for detailed trends or Inventory to update stock. I only read your seller-scoped catalog data.")


def _seller_slug(user: User) -> str:
    return re.sub(r"[^a-z0-9]+", "-", user.name.lower()).strip("-")


def _product_out(product: Product) -> dict:
    return {
        "id": product.id, "title": product.title, "category": product.category,
        "price": product.base_price, "stock_count": product.stock_count,
        "seller_price_floor": product.seller_price_floor,
        "status": product.listing_status if product.stock_count >= 5 else "low_stock" if product.listing_status == "active" else product.listing_status,
        "image_url": product.image_url, "barcode": product.barcode,
        "brand": product.brand, "subcategory": product.subcategory,
        "color": product.color, "size": product.size, "variant": product.variant,
        "barcode_verified": product.barcode_verified,
        "specifications": json.loads(product.specifications or "{}"),
        "quality_tags": json.loads(product.quality_tags or "[]"),
    }


def _barcode_lookup(barcode: str, db: Session) -> dict:
    if not re.fullmatch(r"[0-9]{8,14}", barcode):
        raise HTTPException(status_code=422, detail="Barcode must contain 8 to 14 digits")
    match = lookup_barcode(barcode)
    if match:
        return {"barcode": barcode, "found": True, "verified": True, **match}

    product = db.query(Product).filter(Product.barcode == barcode, Product.barcode_verified.is_(True)).first()
    if not product:
        raise HTTPException(status_code=404, detail="New barcode detected; enter product details manually.")
    return {
        "barcode": barcode, "found": True, "verified": True,
        "title": product.title, "brand": product.brand, "category": product.category,
        "subcategory": product.subcategory, "color": product.color, "size": product.size,
        "variant": product.variant, "description": product.description,
        "image_url": product.image_url, "market_price": product.base_price,
        "specifications": json.loads(product.specifications or "{}"),
        "quality_tags": json.loads(product.quality_tags or "[]"),
    }


@router.get("/catalog/barcode/{barcode}", dependencies=[Depends(get_current_active_seller)])
def barcode_lookup_get(barcode: str, db: Session = Depends(get_db)):
    return _barcode_lookup(barcode, db)


@router.post("/products/barcode-lookup", dependencies=[Depends(get_current_active_seller)])
def barcode_lookup_post(payload: BarcodeLookupInput, db: Session = Depends(get_db)):
    return _barcode_lookup(payload.barcode, db)


@router.get("/dashboard-stats")
def dashboard_stats(db: Session = Depends(get_db), seller: User = Depends(get_current_active_seller)):
    products = db.query(Product).filter(Product.seller_id == _seller_slug(seller)).all()
    orders = db.query(Order).join(Product).filter(Product.seller_id == _seller_slug(seller)).all()
    paid_statuses = {"confirmed", "shipped", "delivered"}
    revenue = sum(order.price for order in orders if order.status.value in paid_statuses)
    inventory_value = sum(product.base_price * product.stock_count for product in products)
    pending_orders = sum(order.status.value in {"pending_approval", "reversal_window_open"} for order in orders)
    ratings = [product.rating for product in products if product.total_reviews > 0]
    verification = db.query(SellerVerification).filter(
        SellerVerification.seller_id == _seller_slug(seller)
    ).first()
    profile = db.query(SellerProfile).filter(SellerProfile.user_id == seller.id).first()
    trust = verification.trust_index if verification else profile.trust_score if profile else None
    units_by_product: dict[str, int] = {}
    for order in orders:
        if order.status.value in paid_statuses:
            units_by_product[order.product_id] = units_by_product.get(order.product_id, 0) + order.quantity
    top_products = sorted(products, key=lambda product: units_by_product.get(product.id, 0), reverse=True)[:5]
    month_labels = ("May", "Jun", "Jul", "Aug", "Sep", "Oct")
    revenue_by_month = {month: 0.0 for month in month_labels}
    for order in orders:
        if order.status.value in paid_statuses and order.created_at:
            label = order.created_at.strftime("%b")
            if label in revenue_by_month:
                revenue_by_month[label] += order.price
    return {
        "total_revenue": round(revenue, 2),
        "pending_orders": pending_orders,
        "inventory_value": round(inventory_value, 2),
        "average_rating": round(sum(ratings) / len(ratings), 1) if ratings else 0,
        "trust_score": round(trust, 1) if trust is not None else None,
        "compliance_score": round(verification.trust_index, 1) if verification else None,
        "authenticity_score": round(verification.review_sentiment_score, 1) if verification else None,
        "price_fairness_score": round(verification.price_stability_score, 1) if verification else None,
        "total_products": len(products),
        "orders": len(orders),
        "revenue_series": [
            {"label": month, "amount": round(revenue_by_month[month], 2)}
            for month in month_labels
        ],
        "top_products": [
            {"id": item.id, "title": item.title, "price": item.base_price, "stock_count": item.stock_count, "sales_velocity": units_by_product.get(item.id, 0)}
            for item in top_products
        ],
    }


@router.post("/assistant")
def seller_assistant(payload: SellerAssistantQuery, db: Session = Depends(get_db), seller: User = Depends(get_current_active_seller)):
    """Seller workspace copilot; answers from seller-owned data without mutations."""
    return {"message": _seller_assistant_reply(payload.query.strip(), seller, db), "read_only": True}


@router.get("/analytics/insights")
def seller_analytics_insights(
    db: Session = Depends(get_db),
    seller: User = Depends(get_current_active_seller),
):
    """Return seller-scoped aggregates without persisting analytics or buyer data."""
    seller_id = _seller_slug(seller)
    products = db.query(
        Product.id, Product.title, Product.base_price, Product.stock_count,
        Product.listing_status,
    ).filter(Product.seller_id == seller_id).all()
    product_rows = [
        {"id": row.id, "title": row.title, "price": row.base_price,
         "stock_count": row.stock_count, "listing_status": row.listing_status}
        for row in products
    ]
    window_start = datetime.now(timezone.utc) - timedelta(days=30)
    session_rows = db.query(
        NegotiationSession.product_id, NegotiationSession.status,
        NegotiationSession.final_price, NegotiationSession.created_at,
        NegotiationSession.size, NegotiationSession.color,
    ).join(Product, Product.id == NegotiationSession.product_id).filter(
        NegotiationSession.seller_id == seller_id,
        Product.seller_id == seller_id,
        NegotiationSession.created_at >= window_start,
    ).all()
    negotiation_rows = [
        {"product_id": row.product_id, "status": row.status,
         "final_price": row.final_price, "created_at": row.created_at,
         "size": row.size, "color": row.color}
        for row in session_rows
    ]
    paid_order_counts = dict(db.query(
        Order.product_id, func.count(Order.id),
    ).join(Product, Product.id == Order.product_id).join(
        NegotiationSession, NegotiationSession.id == Order.negotiation_session_id,
    ).filter(
        Product.seller_id == seller_id,
        NegotiationSession.seller_id == seller_id,
        NegotiationSession.product_id == Order.product_id,
        NegotiationSession.created_at >= window_start,
        Order.created_at >= window_start,
        Order.status.in_((OrderStatus.CONFIRMED, OrderStatus.SHIPPED, OrderStatus.DELIVERED)),
    ).group_by(Order.product_id).all())
    return build_seller_insights(product_rows, negotiation_rows, paid_order_counts)


@router.get("/inventory")
def inventory(db: Session = Depends(get_db), seller: User = Depends(get_current_active_seller)):
    products = db.query(Product).filter(Product.seller_id == _seller_slug(seller)).order_by(Product.title).all()
    return [_product_out(product) for product in products]


@router.post("/inventory", status_code=201)
def create_inventory(payload: InventoryInput, db: Session = Depends(get_db), seller: User = Depends(get_current_active_seller)):
    if payload.seller_price_floor is not None and payload.seller_price_floor > payload.price:
        raise HTTPException(status_code=422, detail="Seller price floor cannot exceed the listing price")
    base = re.sub(r"[^a-z0-9]+", "-", payload.title.lower()).strip("-")
    product_id, suffix = base, 2
    while db.get(Product, product_id):
        product_id, suffix = f"{base}-{suffix}", suffix + 1
    product = Product(
        id=product_id, title=payload.title, category=payload.category, base_price=payload.price,
        seller_price_floor=payload.seller_price_floor or payload.price,
        stock_count=payload.stock_count, description=payload.description or payload.title,
        image_url=payload.image_url, seller_name=seller.name, seller_id=_seller_slug(seller),
        rating=0, total_reviews=0, is_verified_seller=True, semantic_tags="seller listing,verified seller",
        fit="Seller managed", trust=85, search_terms=f"{payload.title},{payload.category}",
        barcode=payload.barcode, barcode_verified=False, listing_status=payload.status, brand=payload.brand,
        subcategory=payload.subcategory, color=payload.color, size=payload.size,
        variant=payload.variant, specifications=json.dumps(payload.specifications),
        quality_tags=json.dumps(payload.quality_tags),
    )
    db.add(product); db.commit(); db.refresh(product)
    return _product_out(product)


@router.patch("/inventory/{product_id}")
@router.put("/inventory/{product_id}")
def update_inventory(product_id: str, payload: InventoryUpdate, db: Session = Depends(get_db), seller: User = Depends(get_current_active_seller)):
    product = db.query(Product).filter(Product.id == product_id, Product.seller_id == _seller_slug(seller)).first()
    if not product: raise HTTPException(status_code=404, detail="Inventory item not found")
    values = payload.model_dump(exclude_unset=True)
    next_price = values.pop("price", product.base_price)
    next_floor = values.pop("seller_price_floor", product.seller_price_floor)
    if "price" in payload.model_fields_set and "seller_price_floor" not in payload.model_fields_set and next_floor > next_price:
        next_floor = next_price
    if next_floor > next_price:
        raise HTTPException(status_code=422, detail="Seller price floor cannot exceed the listing price")
    product.base_price = next_price
    product.seller_price_floor = next_floor
    if "status" in values: product.listing_status = values.pop("status")
    for key, value in values.items(): setattr(product, key, value)
    db.commit(); db.refresh(product)
    return _product_out(product)


@router.delete("/inventory/{product_id}", status_code=204)
def delete_inventory(product_id: str, db: Session = Depends(get_db), seller: User = Depends(get_current_active_seller)):
    product = db.query(Product).filter(Product.id == product_id, Product.seller_id == _seller_slug(seller)).first()
    if not product: raise HTTPException(status_code=404, detail="Inventory item not found")
    if db.query(Order).filter(Order.product_id == product.id).first():
        raise HTTPException(status_code=409, detail="Products with order history cannot be deleted; set stock to zero")
    db.delete(product); db.commit()
    return Response(status_code=204)


@router.get("/orders")
def seller_orders(db: Session = Depends(get_db), seller: User = Depends(get_current_active_seller)):
    orders = db.query(Order).join(Product).filter(Product.seller_id == _seller_slug(seller)).order_by(Order.created_at.desc()).all()
    return [{"order_ref": o.order_ref, "product_name": o.product.title, "quantity": o.quantity, "total": o.price, "order_status": o.status.value, "escrow_status": "LOCKED" if o.escrow_status == "HELD" else o.escrow_status, "placed_at": o.created_at} for o in orders]


@router.post("/orders/{order_ref}/dispatch")
def dispatch(order_ref: str, db: Session = Depends(get_db), seller: User = Depends(get_current_active_seller)):
    order = db.query(Order).join(Product).filter(Order.order_ref == order_ref, Product.seller_id == _seller_slug(seller)).with_for_update().first()
    if not order:
        raise HTTPException(status_code=404, detail="Seller order not found")
    dispatch_confirmed_order(db, order, f"seller:{seller.email}")
    db.commit()
    return {"order_ref": order_ref, "order_status": order.status.value, "escrow_status": order.escrow_status}


@router.get("/wallet")
def seller_wallet(db: Session = Depends(get_db), seller: User = Depends(get_current_active_seller)):
    revenue = db.query(func.coalesce(func.sum(Order.price), 0.0)).join(Product).filter(
        Product.seller_id == _seller_slug(seller), Order.status.in_(["CONFIRMED", "SHIPPED", "DELIVERED"])
    ).scalar()
    wallet = db.query(SellerWallet).filter(SellerWallet.seller_id == seller.id).first()
    ledger = db.query(SellerWalletEntry).filter(
        SellerWalletEntry.seller_wallet_id == wallet.id
    ).order_by(SellerWalletEntry.created_at.desc()).limit(50).all() if wallet else []
    return {
        "available_balance": wallet.available_balance if wallet else 0,
        "pending_payouts": wallet.pending_payouts if wallet else 0,
        "earned_revenue": float(revenue or 0),
        "ledger": [
            {"id": entry.id, "amount": entry.amount, "type": entry.entry_type,
             "description": entry.description, "created_at": entry.created_at}
            for entry in ledger
        ],
        "payouts_enabled": False,
    }


@router.post("/wallet", dependencies=[Depends(get_current_active_seller)])
@router.post("/wallet/payout")
def request_payout(
    payload: PayoutRequestInput,
    seller: User = Depends(get_current_active_seller),
):
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Manual payouts are disabled; released order balances transfer through Stripe Connect.",
    )


@router.post("/connect/retry-transfers")
def retry_payout_transfers(
    db: Session = Depends(get_db),
    seller: User = Depends(get_current_active_seller),
):
    return {"retried": retry_seller_transfers(db, seller)}


@router.post("/connect/onboarding")
def connect_onboarding(
    db: Session = Depends(get_db),
    seller: User = Depends(get_current_active_seller),
):
    origin = settings.primary_frontend_url
    try:
        url = start_connect_onboarding(
            db,
            seller,
            f"{origin}/seller/wallet?connect=refresh",
            f"{origin}/seller/wallet?connect=complete",
        )
    except SellerPayoutsUnavailable as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    return {"onboarding_url": url}


@router.get("/connect/status")
def seller_connect_status(
    db: Session = Depends(get_db),
    seller: User = Depends(get_current_active_seller),
):
    try:
        return connect_account_status(db, seller)
    except Exception as error:
        raise HTTPException(status_code=502, detail="Could not retrieve Stripe Connect status") from error


@router.put("/orders/{order_ref}")
def update_seller_order(order_ref: str, payload: SellerOrderStatusInput, db: Session = Depends(get_db), seller: User = Depends(get_current_active_seller)):
    if payload.order_status != "shipped":
        raise HTTPException(status_code=409, detail="Only the shipped transition is available through seller fulfillment. Delivery is confirmed by the buyer.")
    return dispatch(order_ref, db, seller)


@router.put("/orders", dependencies=[Depends(get_current_active_seller)])
def update_seller_order_from_collection(payload: SellerOrderCollectionUpdate, db: Session = Depends(get_db), seller: User = Depends(get_current_active_seller)):
    return update_seller_order(payload.order_ref, payload, db, seller)


@router.get("/goals")
def seller_goals(db: Session = Depends(get_db), seller: User = Depends(get_current_active_seller)):
    goals = db.query(SalesGoal).filter(SalesGoal.seller_id == seller.id).order_by(SalesGoal.id.desc()).all()
    return [
        {"id": goal.id, "title": goal.target_title, "target_amount": goal.target_amount,
         "current_amount": goal.current_amount, "deadline": goal.deadline,
         "progress_percent": round(min(100, goal.current_amount / goal.target_amount * 100), 1)}
        for goal in goals
    ]


@router.post("/goals", status_code=201)
def create_seller_goal(payload: SellerGoalInput, db: Session = Depends(get_db), seller: User = Depends(get_current_active_seller)):
    goal = SalesGoal(seller_id=seller.id, target_title=payload.name, target_amount=payload.target_amount, current_amount=0, deadline=payload.deadline)
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return {"id": goal.id, "title": goal.target_title, "target_amount": goal.target_amount,
            "current_amount": goal.current_amount, "deadline": goal.deadline,
            "progress_percent": round(min(100, goal.current_amount / goal.target_amount * 100), 1)}
