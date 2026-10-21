from datetime import datetime, timezone
import re
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import case, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_active_seller, get_current_user, get_db
from app.models.b2b import B2BBid, DistributionLedger, VendorQuote, VendorSubscription
from app.models.product import Product
from app.models.user import User
from app.services.b2b_matching import score_vendor_quote

b2b_router = APIRouter(prefix="/b2b", tags=["B2B Sourcing"])
distribution_router = APIRouter(prefix="/distribution", tags=["Distribution & Khata"])
subscriptions_router = APIRouter(prefix="/subscriptions", tags=["Vendor Monetization"])

PLAN_DETAILS = {
    "Basic": {"monthly_price": 0, "features": ["Up to 5 quotes/month", "Standard search placement", "Basic distribution ledger"]},
    "Pro": {"monthly_price": 15000, "features": ["Unlimited quotes", "Advanced analytics", "Priority support"]},
    "Enterprise": {"monthly_price": 45000, "features": ["Multi-branch operations", "API access", "Dedicated account support"]},
}


class BidRequestInput(BaseModel):
    title: str = Field(min_length=3, max_length=160)
    description: str = Field(default="", max_length=4000)
    category: str = Field(min_length=2, max_length=80)
    quantity: int = Field(gt=0, le=1_000_000)
    target_budget: float = Field(gt=0, le=1_000_000_000)
    delivery_days: int = Field(gt=0, le=730)
    closes_at: datetime | None = None


class VendorQuoteInput(BaseModel):
    bid_id: int = Field(gt=0)
    offered_price: float = Field(gt=0, le=1_000_000_000)
    delivery_days: int = Field(gt=0, le=730)
    is_featured: bool = False


class DistributionEntryInput(BaseModel):
    retailer_id: int = Field(gt=0)
    product_id: str | None = Field(default=None, max_length=160)
    entry_type: Literal["sale", "repayment"] = "sale"
    transaction_amount: float = Field(gt=0, le=1_000_000_000)
    credit_amount: float = Field(default=0, ge=0, le=1_000_000_000)
    credit_limit: float = Field(default=0, ge=0, le=1_000_000_000)
    reference: str = Field(default="", max_length=120)


def _bid_out(bid: B2BBid, quotes: list[VendorQuote] | None = None) -> dict:
    return {
        "id": bid.id, "buyer_id": bid.buyer_id, "title": bid.title, "description": bid.description,
        "category": bid.category, "quantity": bid.quantity, "target_budget": bid.target_budget,
        "delivery_days": bid.delivery_days, "status": bid.status,
        "created_at": bid.created_at.isoformat(),
        "quotes": [_quote_out(quote) for quote in (quotes or [])],
    }


def _quote_out(quote: VendorQuote) -> dict:
    return {
        "id": quote.id, "bid_id": quote.bid_id, "vendor_id": quote.vendor_id,
        "vendor_name": quote.vendor.name if quote.vendor else f"Vendor {quote.vendor_id}",
        "offered_price": quote.offered_price, "delivery_days": quote.delivery_days,
        "ai_match_score": quote.ai_match_score, "commission_rate": quote.commission_rate,
        "commission_amount": quote.commission_amount, "vendor_net_payout": quote.vendor_net_payout,
        "is_featured": quote.is_featured, "status": quote.status,
        "created_at": quote.created_at.isoformat(),
    }


def _request_expired(closes_at: datetime | None) -> bool:
    if closes_at is None:
        return False
    if closes_at.tzinfo is None:
        closes_at = closes_at.replace(tzinfo=timezone.utc)
    return closes_at <= datetime.now(timezone.utc)


@b2b_router.post("/requests", status_code=status.HTTP_201_CREATED)
def create_bid_request(payload: BidRequestInput, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if _request_expired(payload.closes_at):
        raise HTTPException(status_code=422, detail="The response deadline must be in the future.")
    bid = B2BBid(buyer_id=current_user.id, **payload.model_dump())
    db.add(bid)
    db.commit()
    db.refresh(bid)
    return _bid_out(bid)


@b2b_router.get("/requests")
def list_bid_requests(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    query = db.query(B2BBid)
    if current_user.role != "seller":
        query = query.filter(B2BBid.buyer_id == current_user.id)
    now = datetime.now(timezone.utc)
    bids = query.filter(
        B2BBid.status == "open",
        (B2BBid.closes_at.is_(None) | (B2BBid.closes_at > now)),
    ).order_by(B2BBid.created_at.desc()).limit(100).all()
    if not bids:
        return []
    grouped: dict[int, list[VendorQuote]] = {bid.id: [] for bid in bids}
    # Suppliers can inspect open buyer requests, but not competitor quotes.
    # Their own quote history is available through /vendor/quotes.
    if current_user.role != "seller":
        quotes = db.query(VendorQuote).options(selectinload(VendorQuote.vendor)).filter(
            VendorQuote.bid_id.in_(grouped), VendorQuote.status.in_(("submitted", "awarded")),
        ).order_by(VendorQuote.ai_match_score.desc()).all()
        for quote in quotes:
            grouped[quote.bid_id].append(quote)
    return [_bid_out(bid, grouped[bid.id]) for bid in bids]


@b2b_router.get("/requests/{bid_id}/quotes")
def get_bid_quotes(bid_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    bid = db.query(B2BBid).filter(B2BBid.id == bid_id).first()
    if bid is None:
        raise HTTPException(status_code=404, detail="Bid request not found.")
    if current_user.id != bid.buyer_id:
        raise HTTPException(status_code=403, detail="Only the buyer who created this request can compare supplier quotes.")
    quotes = db.query(VendorQuote).options(selectinload(VendorQuote.vendor)).filter(VendorQuote.bid_id == bid_id, VendorQuote.status.in_(("submitted", "awarded"))).all()
    quotes.sort(key=lambda item: (item.ai_match_score, item.is_featured), reverse=True)
    return [_quote_out(quote) for quote in quotes]


@b2b_router.post("/requests/{bid_id}/award/{quote_id}")
def award_vendor_quote(bid_id: int, quote_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Record supplier selection without creating an order or moving funds."""
    bid = db.query(B2BBid).filter(B2BBid.id == bid_id).with_for_update().first()
    if bid is None:
        raise HTTPException(status_code=404, detail="Buyer request not found.")
    if bid.buyer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the buyer who created this request can select a supplier.")
    if bid.status != "open" or _request_expired(bid.closes_at):
        raise HTTPException(status_code=409, detail="This buyer request is no longer open for supplier selection.")
    quote = db.query(VendorQuote).filter(
        VendorQuote.id == quote_id, VendorQuote.bid_id == bid.id,
    ).with_for_update().first()
    if quote is None:
        raise HTTPException(status_code=404, detail="Supplier quote not found for this request.")
    if quote.status != "submitted":
        raise HTTPException(status_code=409, detail="This supplier quote is no longer available for selection.")

    bid.status = "awarded"
    quote.status = "awarded"
    db.query(VendorQuote).filter(
        VendorQuote.bid_id == bid.id, VendorQuote.id != quote.id, VendorQuote.status == "submitted",
    ).update({VendorQuote.status: "declined"}, synchronize_session="fetch")
    db.commit()
    db.refresh(quote)
    return {
        **_quote_out(quote), "bid_status": bid.status,
        "selection_status": "supplier_selected", "order_created": False, "payment_processed": False,
    }


@b2b_router.post("/place-bid", status_code=status.HTTP_201_CREATED)
def place_vendor_bid(payload: VendorQuoteInput, db: Session = Depends(get_db), vendor: User = Depends(get_current_active_seller)):
    bid = db.query(B2BBid).filter(B2BBid.id == payload.bid_id).with_for_update().first()
    if bid is None:
        raise HTTPException(status_code=404, detail="Bid request not found.")
    if bid.status != "open" or _request_expired(bid.closes_at):
        raise HTTPException(status_code=409, detail="This buyer request is closed to quotes.")
    if bid.buyer_id == vendor.id:
        raise HTTPException(status_code=400, detail="You cannot quote your own request.")
    if db.query(VendorQuote.id).filter(VendorQuote.bid_id == bid.id, VendorQuote.vendor_id == vendor.id).first():
        raise HTTPException(status_code=409, detail="You already submitted a quote for this request.")
    active_subscription = db.query(VendorSubscription).filter(
        VendorSubscription.vendor_id == vendor.id, VendorSubscription.status == "active",
    ).order_by(VendorSubscription.started_at.desc()).first()
    tier = active_subscription.tier if active_subscription else "Basic"
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if tier == "Basic":
        monthly_quotes = db.query(func.count(VendorQuote.id)).filter(
            VendorQuote.vendor_id == vendor.id, VendorQuote.created_at >= month_start,
        ).scalar() or 0
        if monthly_quotes >= 5:
            raise HTTPException(status_code=403, detail="Basic includes five supplier quotes per month. Select Pro or Enterprise to submit more.")
    commission_rate = 0.02 if payload.is_featured else 0.01
    commission = round(payload.offered_price * commission_rate, 2)
    quote = VendorQuote(
        bid_id=bid.id, vendor_id=vendor.id, offered_price=payload.offered_price,
        delivery_days=payload.delivery_days,
        ai_match_score=score_vendor_quote(bid, payload.offered_price, payload.delivery_days),
        commission_rate=commission_rate, commission_amount=commission,
        vendor_net_payout=round(payload.offered_price - commission, 2), is_featured=payload.is_featured,
    )
    db.add(quote)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="A quote from your account already exists for this request.")
    db.refresh(quote)
    return _quote_out(quote)


@b2b_router.get("/vendor/quotes")
def vendor_quotes(db: Session = Depends(get_db), vendor: User = Depends(get_current_active_seller)):
    quotes = db.query(VendorQuote).options(selectinload(VendorQuote.vendor), selectinload(VendorQuote.bid)).filter(VendorQuote.vendor_id == vendor.id).order_by(VendorQuote.created_at.desc()).limit(100).all()
    return [{**_quote_out(quote), "request": _bid_out(quote.bid)} for quote in quotes]


@distribution_router.post("/ledger", status_code=status.HTTP_201_CREATED)
def create_distribution_entry(payload: DistributionEntryInput, db: Session = Depends(get_db), distributor: User = Depends(get_current_active_seller)):
    retailer = db.query(User).filter(User.id == payload.retailer_id).first()
    if retailer is None:
        raise HTTPException(status_code=404, detail="Retailer account not found.")
    if retailer.id == distributor.id:
        raise HTTPException(status_code=422, detail="A distributor cannot create a retailer ledger against their own account.")
    if payload.product_id:
        product = db.query(Product).filter(Product.id == payload.product_id).first()
        if product is None:
            raise HTTPException(status_code=404, detail="Product not found.")
        distributor_slug = re.sub(r"[^a-z0-9]+", "-", distributor.name.lower()).strip("-")
        if distributor.role != "admin" and product.seller_id != distributor_slug:
            raise HTTPException(status_code=403, detail="You can only record distribution for your own catalog listings.")
    outstanding = db.query(func.coalesce(func.sum(case(
        (DistributionLedger.entry_type == "repayment", -DistributionLedger.khata_amount),
        else_=DistributionLedger.khata_amount,
    )), 0)).filter(DistributionLedger.retailer_id == retailer.id).scalar() or 0
    if payload.entry_type == "repayment":
        if payload.transaction_amount > outstanding:
            raise HTTPException(status_code=422, detail="Repayment cannot exceed the outstanding khata balance.")
        if payload.credit_amount > 0:
            raise HTTPException(status_code=422, detail="Repayments cannot create additional credit.")
        commission_rate, commission, credit_amount, khata_amount = 0.015, 0.0, 0.0, payload.transaction_amount
    else:
        if payload.credit_amount > payload.transaction_amount:
            raise HTTPException(status_code=422, detail="Credit portion cannot exceed the distribution amount.")
        if payload.credit_amount and payload.credit_limit <= 0:
            raise HTTPException(status_code=422, detail="Set a positive credit limit before extending khata credit.")
        if payload.credit_limit and outstanding > payload.credit_limit:
            raise HTTPException(status_code=409, detail="The new credit limit is below the retailer's existing khata balance.")
        if payload.credit_amount and outstanding + payload.credit_amount > payload.credit_limit:
            raise HTTPException(status_code=409, detail="This distribution would exceed the retailer's credit limit.")
        commission_rate = 0.015
        commission = round(payload.transaction_amount * commission_rate, 2)
        credit_amount, khata_amount = payload.credit_amount, payload.credit_amount
    entry = DistributionLedger(
        distributor_id=distributor.id, retailer_id=retailer.id, product_id=payload.product_id,
        entry_type=payload.entry_type, platform_commission_rate=commission_rate,
        commission_amount=commission, credit_amount=credit_amount, khata_amount=khata_amount,
        credit_limit=payload.credit_limit, reference=payload.reference,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return {"id": entry.id, "entry_type": entry.entry_type, "commission_amount": entry.commission_amount,
            "credit_amount": entry.credit_amount, "khata_amount": entry.khata_amount, "credit_limit": entry.credit_limit}


@distribution_router.get("/khata-alert/{retailer_id}")
def khata_alert(retailer_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    retailer = db.query(User).filter(User.id == retailer_id).first()
    if retailer is None:
        raise HTTPException(status_code=404, detail="Retailer account not found.")
    relationship = db.query(DistributionLedger.id).filter(
        DistributionLedger.retailer_id == retailer_id, DistributionLedger.distributor_id == current_user.id,
    ).first()
    if current_user.id != retailer_id and current_user.role != "admin" and relationship is None:
        raise HTTPException(status_code=403, detail="You can only inspect your own retailer account or an account you distribute to.")
    ledger_entries = db.query(DistributionLedger).filter(DistributionLedger.retailer_id == retailer_id).order_by(DistributionLedger.created_at.desc()).all()
    khata_outstanding = round(sum(-row.khata_amount if row.entry_type == "repayment" else row.khata_amount for row in ledger_entries), 2)
    credit_limit = next((row.credit_limit for row in ledger_entries if row.credit_limit > 0), 0.0)
    utilization = round(khata_outstanding / credit_limit * 100, 1) if credit_limit else (100.0 if khata_outstanding else 0.0)
    stock_owner = re.sub(r"[^a-z0-9]+", "-", retailer.name.lower()).strip("-")
    stock_rows = db.query(Product).filter(Product.seller_id == stock_owner, Product.listing_status == "active").order_by(Product.stock_count.asc()).all()
    low_stock = [{"product_id": p.id, "title": p.title, "stock_count": p.stock_count, "replenish_suggested": max(10 - p.stock_count, 0)} for p in stock_rows if p.stock_count <= 5]
    risk = "over_limit" if credit_limit and khata_outstanding > credit_limit else "high" if utilization >= 90 else "watch" if utilization >= 70 else "low"
    return {
        "retailer_id": retailer_id, "low_stock_alerts": low_stock,
        "replenishment_is_advisory": True, "khata_outstanding": khata_outstanding,
        "credit_limit": credit_limit, "credit_utilization_percent": utilization,
        "khata_risk_status": risk, "commission_tracked": round(sum(row.commission_amount for row in ledger_entries), 2),
    }


@subscriptions_router.get("/plans")
def list_vendor_plans():
    return [{"tier": tier, **details, "currency": "PKR", "billing_period": "monthly"} for tier, details in PLAN_DETAILS.items()]


@subscriptions_router.get("/me")
def current_vendor_subscription(db: Session = Depends(get_db), vendor: User = Depends(get_current_active_seller)):
    subscription = db.query(VendorSubscription).filter(VendorSubscription.vendor_id == vendor.id).order_by(VendorSubscription.started_at.desc()).first()
    if not subscription:
        return {"tier": "Basic", "monthly_price": 0, "status": "active", "billing_period": "monthly"}
    return {"id": subscription.id, "tier": subscription.tier, "monthly_price": subscription.monthly_price,
            "status": subscription.status, "billing_period": "monthly", "started_at": subscription.started_at.isoformat()}


@subscriptions_router.post("/select", status_code=status.HTTP_201_CREATED)
def select_vendor_plan(tier: Literal["Basic", "Pro", "Enterprise"], db: Session = Depends(get_db), vendor: User = Depends(get_current_active_seller)):
    plan = PLAN_DETAILS[tier]
    # This records plan intent only. Paid tiers cannot activate until a billing
    # provider confirms collection through the server-authoritative consent flow.
    now = datetime.now(timezone.utc)
    previous_pending = db.query(VendorSubscription).filter(
        VendorSubscription.vendor_id == vendor.id, VendorSubscription.status == "pending_payment",
    ).all()
    for previous in previous_pending:
        previous.status = "cancelled"
        previous.ended_at = now
    if tier == "Basic":
        previous_active = db.query(VendorSubscription).filter(
            VendorSubscription.vendor_id == vendor.id, VendorSubscription.status == "active",
        ).all()
        for previous in previous_active:
            previous.status = "cancelled"
            previous.ended_at = now
    subscription = VendorSubscription(vendor_id=vendor.id, tier=tier, monthly_price=plan["monthly_price"],
                                      status="active" if tier == "Basic" else "pending_payment")
    db.add(subscription)
    db.commit()
    db.refresh(subscription)
    return {"id": subscription.id, "tier": subscription.tier, "monthly_price": subscription.monthly_price,
            "status": subscription.status, "billing_period": "monthly",
            "message": "Basic is active." if tier == "Basic" else "Plan selected. Complete billing to activate this paid subscription."}
