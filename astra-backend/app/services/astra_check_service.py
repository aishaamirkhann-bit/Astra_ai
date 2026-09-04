from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.deal import Deal, MarketPriceHistory, SellerMetric
from app.models.product import Product
from app.models.trust import PlatformTrustMetric, SellerVerification, TrustAuditLog
from app.schemas.astra_check import (
    DashboardStatsOut, PricePointOut, SellerProfileOut, SellerVerificationOut, TrustActionRequest,
    TrustActionResponse, TrustInspectionOut,
)
from app.services.deals_pipeline import DealDomainEvent


def ensure_seller_verifications(db: Session) -> None:
    existing = {row.seller_id: row for row in db.scalars(select(SellerVerification)).all()}
    for metric in db.scalars(select(SellerMetric)).all():
        verification = existing.get(metric.seller_id)
        if verification is None:
            verification = SellerVerification(
            seller_id=metric.seller_id, seller_name=metric.seller_name,
            business_identity_verified=metric.seller_rating >= 75,
            fulfillment_rate=metric.fulfillment_rate,
            review_sentiment_score=metric.authenticity_sentiment,
            price_stability_score=metric.price_stability,
            )
            db.add(verification)
        verification.business_name = metric.seller_name
        verification.verification_status = "verified" if metric.seller_rating >= 75 else "pending"
        verification.dispute_rate = max(0, round((100 - metric.seller_rating) * 0.25, 2))
        verification.return_rate = max(0, round((100 - metric.fulfillment_rate) * 0.35, 2))
        verification.trust_index = round((metric.fulfillment_rate + metric.authenticity_sentiment + metric.price_stability) / 3, 2)
    db.commit()


def dashboard_stats(db: Session) -> DashboardStatsOut:
    ensure_seller_verifications(db)
    verified = db.scalar(select(func.count()).select_from(SellerVerification).where(
        SellerVerification.business_identity_verified.is_(True), SellerVerification.is_flagged.is_(False)
    )) or 0
    flagged = db.scalar(select(func.count()).select_from(Product).where(Product.trust < 60)) or 0
    average = db.scalar(select(func.avg(Product.trust))) or 0
    active = db.scalar(select(func.count()).select_from(Product).where(Product.stock_count > 0)) or 0
    metrics = db.get(PlatformTrustMetric, 1) or PlatformTrustMetric(id=1)
    metrics.verified_sellers_count = verified; metrics.flagged_listings_count = flagged
    metrics.avg_trust_score = round(float(average), 1); metrics.active_ai_scans = active
    metrics.updated_at = datetime.now(timezone.utc); db.add(metrics); db.commit()
    return DashboardStatsOut(
        total_verified_sellers=verified, flagged_listings=flagged,
        average_platform_trust_index=round(float(average), 1), real_time_scans_active=active,
    )


def _find_product(db: Session, query: str) -> Product:
    normalized = query.strip()
    product = db.scalar(select(Product).where(or_(
        func.lower(Product.id) == normalized.casefold(),
        func.lower(Product.seller_name) == normalized.casefold(),
    )).order_by(Product.trust.desc()))
    if product is None:
        product = db.scalar(select(Product).where(or_(
            func.lower(Product.id).contains(normalized.casefold()),
            func.lower(Product.seller_name).contains(normalized.casefold()),
            func.lower(Product.title).contains(normalized.casefold()),
        )).order_by(Product.trust.desc()))
    if product is None:
        raise HTTPException(status_code=404, detail="No product or seller matched this inspection query")
    return product


def inspect_product(db: Session, query: str, actor_user_id: int | None = None) -> tuple[TrustInspectionOut, DealDomainEvent | None]:
    ensure_seller_verifications(db)
    product = _find_product(db, query)
    verification = db.get(SellerVerification, product.seller_id)
    if verification is None:
        raise HTTPException(status_code=409, detail="Seller verification metrics are unavailable")
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    history = db.scalars(select(MarketPriceHistory).where(
        MarketPriceHistory.product_id == product.id, MarketPriceHistory.observed_at >= cutoff,
    ).order_by(MarketPriceHistory.observed_at)).all()
    market_average = float(sum(point.price for point in history) / len(history)) if history else product.base_price
    identity_score = 100 if verification.business_identity_verified else 35
    seller_score = round(0.65 * verification.fulfillment_rate + 0.25 * identity_score + 0.10 * (100 - verification.dispute_rate), 2)
    computed = round(0.4 * seller_score + 0.4 * verification.review_sentiment_score + 0.2 * verification.price_stability_score, 2)
    price_anomaly = market_average > 0 and product.base_price < market_average * 0.5
    if price_anomaly:
        computed = max(0, round(computed - 15, 2))
    authenticity_flag = verification.review_sentiment_score < 60 or verification.is_flagged
    if verification.is_flagged:
        computed = min(computed, 59)
    previous = float(product.trust)
    product.trust = round(computed)
    deal = db.scalar(select(Deal).where(Deal.product_id == product.id))
    event = None
    if deal:
        deal.trust_score = computed
        deal.seller_fulfillment_score = seller_score
        deal.authenticity_sentiment_score = verification.review_sentiment_score
        deal.price_stability_score = verification.price_stability_score
        if computed < 75 and deal.is_active:
            deal.is_active = False
            event = DealDomainEvent("deal_expired", deal.id, product.id, deal.stock_remaining)
    audit = TrustAuditLog(
        audit_id=str(uuid4()),
        product_id=product.id, seller_id=product.seller_id, action="automated_inspection",
        previous_score=previous, computed_score=computed, final_score=computed,
        calculated_trust_score=computed, authenticity_flag=authenticity_flag,
        price_anomaly_detected=price_anomaly,
        reasoning_summary=("Price_Anomaly_Warning: listing is below 50% of the 30-day market average; 15-point penalty applied. " if price_anomaly else "Price is within the expected 30-day market range. ") + ("Suspicious review authenticity signals detected." if authenticity_flag else "Buyer review patterns passed authenticity checks."),
        components={"seller": seller_score, "review_sentiment": verification.review_sentiment_score, "price_stability": verification.price_stability_score, "weights": {"seller": 0.4, "review_sentiment": 0.4, "price_stability": 0.2}},
        actor_user_id=actor_user_id,
    )
    db.add(audit); db.flush(); db.commit()
    inspected_at = datetime.now(timezone.utc)
    result = TrustInspectionOut(
        product_id=product.id, product_name=product.title, current_price=product.base_price,
        market_average=round(market_average, 2), trust_score=computed,
        risk_level="safe" if computed >= 80 else "caution" if computed >= 60 else "flagged",
        seller_score=seller_score, review_sentiment_score=verification.review_sentiment_score,
        price_stability_score=verification.price_stability_score,
        seller=SellerVerificationOut(
            seller_id=verification.seller_id, seller_name=verification.seller_name,
            business_name=verification.business_name, verification_status=verification.verification_status,
            business_identity_verified=verification.business_identity_verified,
            fulfillment_rate=verification.fulfillment_rate, return_rate=verification.return_rate,
            dispute_rate=verification.dispute_rate, trust_index=verification.trust_index,
            is_flagged=verification.is_flagged, last_verified_at=verification.last_verified_at.isoformat(),
        ),
        price_history=[PricePointOut(
            observed_at=point.observed_at.replace(tzinfo=point.observed_at.tzinfo or timezone.utc).isoformat(),
            label=point.observed_at.strftime("%d %b"), market_average=point.price,
            current_price=product.base_price,
        ) for point in history],
        deal_eligible=computed >= 75 and bool(deal and deal.is_active),
        inspected_at=inspected_at.isoformat(), audit_id=audit.id, external_audit_id=audit.audit_id,
        authenticity_flag=authenticity_flag, price_anomaly_detected=price_anomaly,
        reasoning_summary=audit.reasoning_summary,
    )
    return result, event


def apply_trust_action(db: Session, action: str, payload: TrustActionRequest, actor_user_id: int) -> tuple[TrustActionResponse, DealDomainEvent | None]:
    product = db.get(Product, payload.product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    ensure_seller_verifications(db)
    verification = db.get(SellerVerification, product.seller_id)
    deal = db.scalar(select(Deal).where(Deal.product_id == product.id))
    previous = float(product.trust)
    event = None
    if action == "manual_override":
        if payload.score is None:
            raise HTTPException(status_code=422, detail="score is required for manual override")
        final = payload.score
    elif action == "flagged":
        verification.is_flagged = True
        final = min(previous, 59)
    elif action == "approved_for_deals":
        verification.is_flagged = False
        final = max(previous, 75)
    else:
        raise HTTPException(status_code=400, detail="Unsupported trust action")
    product.trust = round(final)
    if deal:
        deal.trust_score = final
        if action == "approved_for_deals":
            deal.is_active = deal.discount_pct >= 15 and deal.stock_remaining > 0
            if deal.is_active:
                event = DealDomainEvent("deal_updated", deal.id, product.id, deal.stock_remaining)
        elif final < 75 or action == "flagged":
            deal.is_active = False
            event = DealDomainEvent("deal_expired", deal.id, product.id, deal.stock_remaining)
    db.add(TrustAuditLog(
        audit_id=str(uuid4()),
        product_id=product.id, seller_id=product.seller_id, action=action,
        previous_score=previous, computed_score=previous, final_score=final,
        calculated_trust_score=final, authenticity_flag=bool(verification.is_flagged),
        price_anomaly_detected=False, reasoning_summary=payload.reason,
        components={"manual": True}, reason=payload.reason, actor_user_id=actor_user_id,
    ))
    db.commit()
    return TrustActionResponse(
        product_id=product.id, action=action, trust_score=final,
        deal_active=bool(deal and deal.is_active), message=f"Trust action {action.replace('_', ' ')} applied",
    ), event


def seller_profile(db: Session, seller_id: str) -> SellerProfileOut:
    ensure_seller_verifications(db)
    verification = db.get(SellerVerification, seller_id)
    if not verification:
        raise HTTPException(status_code=404, detail="Seller verification profile not found")
    audits = db.scalars(select(TrustAuditLog).where(TrustAuditLog.seller_id == seller_id).order_by(TrustAuditLog.inspected_at.desc()).limit(25)).all()
    products_count = db.scalar(select(func.count()).select_from(Product).where(Product.seller_id == seller_id)) or 0
    seller_out = SellerVerificationOut(
        id=verification.seller_id, seller_id=verification.seller_id, seller_name=verification.seller_name,
        business_name=verification.business_name, verification_status=verification.verification_status,
        business_identity_verified=verification.business_identity_verified,
        fulfillment_rate=verification.fulfillment_rate, return_rate=verification.return_rate,
        dispute_rate=verification.dispute_rate, trust_index=verification.trust_index,
        is_flagged=verification.is_flagged, last_verified_at=verification.last_verified_at.isoformat(),
    )
    return SellerProfileOut(
        seller=seller_out, verification=seller_out, products_count=products_count,
        audit_history=[{"audit_id": audit.audit_id, "product_id": audit.product_id, "calculated_trust_score": audit.calculated_trust_score, "authenticity_flag": audit.authenticity_flag, "price_anomaly_detected": audit.price_anomaly_detected, "reasoning_summary": audit.reasoning_summary, "inspected_at": audit.inspected_at.isoformat()} for audit in audits],
    )
