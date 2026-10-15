import re
import json

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_seller, get_db
from app.core.config import settings
from app.models.order import Order
from app.models.product import Product
from app.models.user import User
from app.models.trust import SellerVerification
from app.models.seller_profile import SellerProfile
from app.models.sales_goal import SalesGoal
from app.models.seller_wallet import SellerWallet, SellerWalletEntry
from app.services.barcode_catalog import lookup_barcode
from app.services.checkout_fsm import dispatch_confirmed_order
from app.services.seller_payouts import (
    SellerPayoutProcessor,
    SellerPayoutsUnavailable,
    connect_account_status,
    get_seller_payout_processor,
    start_connect_onboarding,
)

router = APIRouter(prefix="/seller", tags=["Seller Dashboard"])


class InventoryInput(BaseModel):
    title: str = Field(min_length=2, max_length=160)
    category: str = Field(min_length=2, max_length=80)
    price: float = Field(gt=0)
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


def _seller_slug(user: User) -> str:
    return re.sub(r"[^a-z0-9]+", "-", user.name.lower()).strip("-")


def _product_out(product: Product) -> dict:
    return {
        "id": product.id, "title": product.title, "category": product.category,
        "price": product.base_price, "stock_count": product.stock_count,
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
    products = db.query(Product).filter(Product.seller_name == seller.name).all()
    orders = db.query(Order).join(Product).filter(Product.seller_name == seller.name).all()
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
    if profile and (
        profile.total_revenue != revenue
        or (verification and profile.trust_score != verification.trust_index)
    ):
        profile.total_revenue = revenue
        if verification:
            profile.trust_score = verification.trust_index
            profile.authenticity_score = verification.review_sentiment_score
            profile.compliance_status = verification.verification_status
        db.commit()
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


@router.get("/inventory")
def inventory(db: Session = Depends(get_db), seller: User = Depends(get_current_active_seller)):
    products = db.query(Product).filter(Product.seller_name == seller.name).order_by(Product.title).all()
    return [_product_out(product) for product in products]


@router.post("/inventory", status_code=201)
def create_inventory(payload: InventoryInput, db: Session = Depends(get_db), seller: User = Depends(get_current_active_seller)):
    base = re.sub(r"[^a-z0-9]+", "-", payload.title.lower()).strip("-")
    product_id, suffix = base, 2
    while db.get(Product, product_id):
        product_id, suffix = f"{base}-{suffix}", suffix + 1
    product = Product(
        id=product_id, title=payload.title, category=payload.category, base_price=payload.price,
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
    product = db.query(Product).filter(Product.id == product_id, Product.seller_name == seller.name).first()
    if not product: raise HTTPException(status_code=404, detail="Inventory item not found")
    values = payload.model_dump(exclude_unset=True)
    if "price" in values: product.base_price = values.pop("price")
    if "status" in values: product.listing_status = values.pop("status")
    for key, value in values.items(): setattr(product, key, value)
    db.commit(); db.refresh(product)
    return _product_out(product)


@router.delete("/inventory/{product_id}", status_code=204)
def delete_inventory(product_id: str, db: Session = Depends(get_db), seller: User = Depends(get_current_active_seller)):
    product = db.query(Product).filter(Product.id == product_id, Product.seller_name == seller.name).first()
    if not product: raise HTTPException(status_code=404, detail="Inventory item not found")
    if db.query(Order).filter(Order.product_id == product.id).first():
        raise HTTPException(status_code=409, detail="Products with order history cannot be deleted; set stock to zero")
    db.delete(product); db.commit()
    return Response(status_code=204)


@router.get("/orders")
def seller_orders(db: Session = Depends(get_db), seller: User = Depends(get_current_active_seller)):
    orders = db.query(Order).join(Product).filter(Product.seller_name == seller.name).order_by(Order.created_at.desc()).all()
    return [{"order_ref": o.order_ref, "product_name": o.product.title, "quantity": o.quantity, "total": o.price, "order_status": o.status.value, "escrow_status": "LOCKED" if o.escrow_status == "HELD" else o.escrow_status, "placed_at": o.created_at} for o in orders]


@router.post("/orders/{order_ref}/dispatch")
def dispatch(order_ref: str, db: Session = Depends(get_db), seller: User = Depends(get_current_active_seller)):
    order = db.query(Order).join(Product).filter(Order.order_ref == order_ref, Product.seller_name == seller.name).with_for_update().first()
    if not order:
        raise HTTPException(status_code=404, detail="Seller order not found")
    dispatch_confirmed_order(db, order, f"seller:{seller.email}")
    db.commit()
    return {"order_ref": order_ref, "order_status": order.status.value, "escrow_status": order.escrow_status}


@router.get("/wallet")
def seller_wallet(db: Session = Depends(get_db), seller: User = Depends(get_current_active_seller)):
    revenue = db.query(func.coalesce(func.sum(Order.price), 0.0)).join(Product).filter(
        Product.seller_name == seller.name, Order.status.in_(["CONFIRMED", "SHIPPED", "DELIVERED"])
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
    processor: SellerPayoutProcessor = Depends(get_seller_payout_processor),
):
    try:
        return processor.request_payout(seller, payload.amount)
    except SellerPayoutsUnavailable as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error


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
