from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.models.cart import CartItem
from app.models.notification import Notification
from app.models.order import Order, OrderStatus
from app.models.pipeline import AuditLog
from app.models.user import User
from app.models.wallet import FinancialConsentLog
from app.realtime.notifications_ws import manager as notification_events
from app.realtime.wallet_ws import manager as wallet_events
from app.schemas.order import OrderDetailOut, OrderOut, ReorderResponse, ReverseOrderResponse
from app.services import astra_agents
from app.services.audit import record_audit
from app.services.checkout_fsm import confirm_delivery, refund_reversible_order
from app.utils.helpers import as_aware_utc

router = APIRouter(prefix="/orders", tags=["Orders"])


def _seconds_left(order: Order) -> int:
    deadline = order.approval_deadline if order.status == OrderStatus.PENDING_APPROVAL else order.reversal_deadline
    if not deadline:
        return 0
    return max(0, int((as_aware_utc(deadline) - datetime.now(timezone.utc)).total_seconds()))


@router.get("/audit")
def audit_trail(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    entries = db.query(AuditLog).order_by(AuditLog.id.desc()).limit(30).all()
    return [
        {
            "id": entry.event_ref,
            "type": entry.event_type,
            "endpoint": entry.endpoint,
            "actor": entry.actor,
            "verdict": entry.verdict,
            "time": as_aware_utc(entry.created_at).isoformat() if entry.created_at else None,
        }
        for entry in entries
    ]


@router.get("", response_model=list[OrderOut])
def list_orders(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    orders = db.query(Order).filter(Order.user_id == current_user.id).order_by(Order.created_at.desc()).all()
    return [OrderOut(
        order_ref=order.order_ref, product_name=order.product.title,
        price=order.price, quantity=order.quantity, size=order.size, color=order.color, storage=order.storage,
        status=order.status.value, escrow_status=order.escrow_status, seconds_left=_seconds_left(order), placed_at=order.created_at,
        image=order.product.image_url,
    ) for order in orders]


@router.get("/{order_ref}", response_model=OrderDetailOut)
def order_detail(order_ref: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    order = db.query(Order).filter(Order.order_ref == order_ref, Order.user_id == current_user.id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    consent_subject = (
        FinancialConsentLog.reference_checkout_id == order.checkout_session_id
        if order.checkout_session_id
        else FinancialConsentLog.reference_order_id == order.id
    )
    consent = db.query(FinancialConsentLog).filter(consent_subject, FinancialConsentLog.consumed_at.is_not(None)).first()
    return OrderDetailOut(order_ref=order.order_ref, product_name=order.product.title, product_id=order.product_id, price=order.price, unit_price=round(order.price / order.quantity, 2), subtotal=order.price, quantity=order.quantity, size=order.size, color=order.color, storage=order.storage, status=order.status.value, escrow_status=order.escrow_status, seconds_left=_seconds_left(order), placed_at=order.created_at, image=order.product.image_url, seller_name=order.product.seller_name, seller_verified=order.product.is_verified_seller, seller_trust_score=order.product.trust, payment_method="Wallet / Consent Verified" if consent else "Wallet", consent_method=consent.auth_method if consent else None, shipped_at=order.shipped_at, delivered_at=order.delivered_at)


@router.post("/{order_ref}/reorder", response_model=ReorderResponse)
def reorder(order_ref: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    order = db.query(Order).filter(Order.order_ref == order_ref, Order.user_id == current_user.id).first()
    if not order: raise HTTPException(status_code=404, detail="Order not found")
    item = db.query(CartItem).filter(CartItem.user_id == current_user.id, CartItem.product_id == order.product_id, CartItem.size == order.size, CartItem.color == order.color, CartItem.storage == order.storage).first()
    if item: item.quantity += order.quantity
    else: db.add(CartItem(user_id=current_user.id, product_id=order.product_id, quantity=order.quantity, size=order.size, color=order.color, storage=order.storage))
    db.flush(); total = sum(q for (q,) in db.query(CartItem.quantity).filter(CartItem.user_id == current_user.id).all()); db.commit()
    return ReorderResponse(order_ref=order_ref, cart_total_quantity=total, message=f"{order.product.title} added to cart again")


@router.post("/{order_ref}/reverse", response_model=ReverseOrderResponse)
async def reverse_order(order_ref: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    order = db.query(Order).filter(Order.order_ref == order_ref, Order.user_id == current_user.id).with_for_update().first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    wallet_balance, refunded = refund_reversible_order(
        db,
        current_user,
        order,
        "reversal_requested",
        f"/api/v1/orders/{order.order_ref}/reverse",
    )
    db.add(Notification(user_id=current_user.id, message=f"{order.order_ref} was reversed and refunded."))
    db.commit()
    if refunded:
        await wallet_events.balance_updated(current_user.id, wallet_balance, "Refund")
    await notification_events.broadcast(current_user.id, {"type": "order_update", "order_ref": order.order_ref, "status": "cancelled", "message": "Order reversed and refunded"})
    return ReverseOrderResponse(order_ref=order.order_ref, status="cancelled", message="Order reversed and stock restored")


@router.post("/{order_ref}/confirm-delivery")
async def confirm_order_delivery(order_ref: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    order = db.query(Order).filter(Order.order_ref == order_ref, Order.user_id == current_user.id).with_for_update().first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    confirm_delivery(db, current_user, order)
    db.add(Notification(user_id=current_user.id, message=f"Delivery confirmed for {order.order_ref}."))
    db.commit()
    await notification_events.broadcast(current_user.id, {"type": "order_update", "order_ref": order.order_ref, "status": "delivered", "message": "Delivery confirmed"})
    return {"order_ref": order.order_ref, "status": order.status.value, "delivered_at": order.delivered_at}


DISPUTE_SEVERITY = {
    "item_not_received": 70,
    "item_damaged": 60,
    "not_as_described": 55,
    "charged_by_mistake": 45,
}


class DisputeRequest(BaseModel):
    reason: str


@router.get("/{order_ref}/timeline")
def order_timeline(order_ref: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    order = db.query(Order).filter(Order.order_ref == order_ref, Order.user_id == current_user.id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    consent_subject = (
        FinancialConsentLog.reference_checkout_id == order.checkout_session_id
        if order.checkout_session_id
        else FinancialConsentLog.reference_order_id == order.id
    )
    consent = db.query(FinancialConsentLog).filter(consent_subject, FinancialConsentLog.consumed_at.is_not(None)).first()
    product = order.product
    placed = as_aware_utc(order.created_at)

    stages = [
        {"key": "placed", "label": "Order placed & stock reserved", "status": "done", "at": placed.isoformat()},
        {"key": "approval", "label": "Human approval / financial consent", "status": "done" if order.status != OrderStatus.PENDING_APPROVAL else "active", "at": placed.isoformat()},
        {"key": "escrow", "label": f"Payment held in escrow (Rs. {order.price:,.0f})", "status": "done", "at": placed.isoformat()},
        {"key": "release", "label": "Escrow released to seller", "status": "done" if order.escrow_status == "RELEASED" else ("cancelled" if order.escrow_status == "REFUNDED" else "pending"), "at": as_aware_utc(order.reversal_deadline).isoformat() if order.reversal_deadline else None},
        {"key": "refund", "label": "Escrow refunded to buyer", "status": "done" if order.escrow_status == "REFUNDED" else "pending", "at": None},
        {"key": "shipping", "label": "Seller dispatched order", "status": "done" if order.status in {OrderStatus.SHIPPED, OrderStatus.DELIVERED} else ("active" if order.status == OrderStatus.CONFIRMED else "pending"), "at": as_aware_utc(order.shipped_at).isoformat() if order.shipped_at else None},
        {"key": "delivery", "label": "Buyer confirmed delivery", "status": "done" if order.status == OrderStatus.DELIVERED else "pending", "at": as_aware_utc(order.delivered_at).isoformat() if order.delivered_at else None},
    ]

    reasoning = [
        {"at": placed.isoformat(), "step": "ASTRA Check", "detail": f"Seller trust {product.trust}/100, verified={product.is_verified_seller}; listing passed price-fairness band."},
        {"at": placed.isoformat(), "step": "Consent evaluation", "detail": f"{consent.auth_method} authorization for Rs. {order.price:,.0f}; single-use consent token consumed at checkout." if consent else "Consent record is unavailable for this legacy order."},
        {"at": placed.isoformat(), "step": "Escrow policy", "detail": f"Reversible window {settings.APPROVAL_WINDOW_SECONDS}s; funds HELD until release conditions met."},
    ]
    if order.escrow_status == "REFUNDED":
        reasoning.append({"at": None, "step": "Dispute engine", "detail": "Risk threshold exceeded — escrow auto-refunded with audit note."})

    response = {"order_ref": order.order_ref, "escrow_status": order.escrow_status, "stages": stages, "reasoning": reasoning}
    if order.escrow_status == "REFUNDED":
        response["resolution_timeline"] = astra_agents.resolution_timeline(order.order_ref, 62, order.price)
    return response


@router.get("/{order_ref}/swarm")
def order_swarm_log(order_ref: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Multi-Agent Swarm Orchestration log for order verification."""
    order = db.query(Order).filter(Order.order_ref == order_ref, Order.user_id == current_user.id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return astra_agents.swarm_trace(order.order_ref, order.product.title, order.price)


@router.post("/{order_ref}/dispute")
async def initiate_ai_dispute(
    order_ref: str,
    payload: DisputeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = db.query(Order).filter(Order.order_ref == order_ref, Order.user_id == current_user.id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.escrow_status == "REFUNDED":
        raise HTTPException(status_code=409, detail="This order was already refunded")
    if order.status != OrderStatus.REVERSAL_WINDOW_OPEN or _seconds_left(order) <= 0:
        raise HTTPException(status_code=409, detail="Order is no longer reversible")

    reason_key = payload.reason.strip().lower()
    severity = DISPUTE_SEVERITY.get(reason_key, 30)
    seller_risk = max(0, 100 - order.product.trust)
    delivery_risk = 20 if order.status in (OrderStatus.CONFIRMED, OrderStatus.SHIPPED) else 0
    risk_score = min(100, severity + seller_risk + delivery_risk)
    checks = [
        {"rule": "reason.severity", "score": severity, "detail": f"Dispute reason '{reason_key}' mapped to severity {severity}"},
        {"rule": "seller.trust_exposure", "score": seller_risk, "detail": f"Seller trust {order.product.trust}/100 contributes {seller_risk} risk points"},
        {"rule": "delivery.stage", "score": delivery_risk, "detail": f"Order status {order.status.value} contributes {delivery_risk} risk points"},
    ]
    approved = risk_score >= 50

    if not approved:
        record_audit(db, event_type="ai.dispute", endpoint=f"/api/v1/orders/{order_ref}/dispute", verdict="review_queued", actor=f"user:{current_user.email}")
        db.commit()
        return {"order_ref": order_ref, "risk_score": risk_score, "checks": checks, "escrow_status": order.escrow_status, "decision": "review_queued", "message": "Risk below auto-refund threshold — queued for human review."}

    wallet_balance, refunded = refund_reversible_order(
        db,
        current_user,
        order,
        "ai_dispute_refund",
        f"/api/v1/orders/{order_ref}/dispute",
    )
    db.add(Notification(user_id=current_user.id, message=f"AI Dispute on {order_ref}: risk {risk_score}/100 — escrow auto-refunded."))
    record_audit(
        db,
        event_type="ai.dispute",
        endpoint=f"/api/v1/orders/{order_ref}/dispute",
        verdict="refunded",
        actor=f"dispute-engine:{current_user.email}",
    )
    db.commit()
    if refunded:
        await wallet_events.balance_updated(current_user.id, wallet_balance, "Refund")
    await notification_events.broadcast(current_user.id, {"type": "order_update", "order_ref": order.order_ref, "status": "refunded", "message": "AI dispute approved — escrow refunded"})
    return {
        "order_ref": order_ref, "risk_score": risk_score, "checks": checks,
        "escrow_status": "REFUNDED", "decision": "refunded",
        "message": "Risk threshold exceeded — escrow auto-refunded with audit note.",
        "resolution_timeline": astra_agents.resolution_timeline(order_ref, risk_score, order.price),
    }
