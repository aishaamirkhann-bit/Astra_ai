from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.budget import UserBudget
from app.models.cart import CartItem
from app.models.checkout import CheckoutSession
from app.models.deal import Deal, DealAuditLog, DealReservation
from app.models.order import Order, OrderStatus
from app.models.product import Product
from app.models.user import User
from app.models.wallet import FinancialConsentLog, UserWallet, WalletTransaction
from app.services.audit import record_audit
from app.utils.helpers import as_aware_utc


AWAITING_CONSENT = "awaiting_consent"
REVERSAL_WINDOW_OPEN = "reversal_window_open"
CONFIRMED = "confirmed"
CANCELLED = "cancelled"
EXPIRED = "expired"


@dataclass
class CheckoutConfirmation:
    session: CheckoutSession
    order_refs: list[str]
    wallet_balance: float
    created: bool


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _order_ref() -> str:
    return f"ORD-{uuid4().hex[:10].upper()}"


def _checkout_ref() -> str:
    return f"CHK-{uuid4().hex[:16].upper()}"


def _orders_for_session(db: Session, session: CheckoutSession) -> list[Order]:
    return (
        db.query(Order)
        .filter(Order.checkout_session_id == session.id)
        .order_by(Order.id)
        .with_for_update()
        .all()
    )


def _transition(order: Order, target: OrderStatus) -> None:
    allowed = {
        OrderStatus.PENDING_APPROVAL: {OrderStatus.REVERSAL_WINDOW_OPEN, OrderStatus.CANCELLED},
        OrderStatus.REVERSAL_WINDOW_OPEN: {OrderStatus.CONFIRMED, OrderStatus.CANCELLED},
        OrderStatus.CONFIRMED: {OrderStatus.SHIPPED},
        OrderStatus.SHIPPED: {OrderStatus.DELIVERED},
        OrderStatus.DELIVERED: set(),
        OrderStatus.CANCELLED: set(),
    }
    if target not in allowed[order.status]:
        raise HTTPException(status_code=409, detail=f"Illegal order transition: {order.status.value} to {target.value}")
    order.status = target


def get_owned_checkout_session(db: Session, user: User, checkout_ref: str, *, lock: bool = False) -> CheckoutSession:
    query = db.query(CheckoutSession).filter(
        CheckoutSession.checkout_ref == checkout_ref,
        CheckoutSession.user_id == user.id,
    )
    if lock:
        query = query.with_for_update()
    session = query.first()
    if not session:
        raise HTTPException(status_code=404, detail="Checkout session not found")
    return session


def get_active_checkout_session(db: Session, user: User, *, lock: bool = False) -> CheckoutSession | None:
    query = db.query(CheckoutSession).filter(
        CheckoutSession.user_id == user.id,
        CheckoutSession.status == AWAITING_CONSENT,
    ).order_by(CheckoutSession.created_at.desc())
    if lock:
        query = query.with_for_update()
    return query.first()


def _restore_cart_items(db: Session, user_id: int, orders: list[Order]) -> None:
    for order in orders:
        item = (
            db.query(CartItem)
            .filter(
                CartItem.user_id == user_id,
                CartItem.product_id == order.product_id,
                CartItem.size == order.size,
                CartItem.color == order.color,
                CartItem.storage == order.storage,
            )
            .with_for_update()
            .first()
        )
        if item:
            item.quantity += order.quantity
        else:
            db.add(
                CartItem(
                    user_id=user_id,
                    product_id=order.product_id,
                    quantity=order.quantity,
                    size=order.size,
                    color=order.color,
                    storage=order.storage,
                )
            )


def _release_session_reservation(db: Session, session: CheckoutSession, target_status: str) -> bool:
    if session.status != AWAITING_CONSENT:
        return False
    orders = _orders_for_session(db, session)
    for order in orders:
        if order.status != OrderStatus.PENDING_APPROVAL:
            continue
        product = db.query(Product).filter(Product.id == order.product_id).with_for_update().first()
        if product:
            product.stock_count += order.quantity
        _transition(order, OrderStatus.CANCELLED)
    _restore_cart_items(db, session.user_id, orders)
    session.status = target_status
    session.cancelled_at = _now()
    return True


def expire_checkout_sessions(db: Session) -> int:
    sessions = (
        db.query(CheckoutSession)
        .filter(
            CheckoutSession.status == AWAITING_CONSENT,
            CheckoutSession.expires_at <= _now(),
        )
        .with_for_update()
        .all()
    )
    expired = sum(1 for session in sessions if _release_session_reservation(db, session, EXPIRED))
    if expired:
        db.commit()
    return expired


def create_or_reuse_checkout_session(db: Session, user: User, shipping_address: str) -> CheckoutSession:
    locked_user = db.query(User).filter(User.id == user.id).with_for_update().one()
    active = get_active_checkout_session(db, locked_user, lock=True)
    if active:
        if as_aware_utc(active.expires_at) > _now():
            active.shipping_address = shipping_address
            return active
        _release_session_reservation(db, active, EXPIRED)

    items = (
        db.query(CartItem)
        .filter(CartItem.user_id == locked_user.id)
        .order_by(CartItem.id)
        .with_for_update()
        .all()
    )
    if not items:
        raise HTTPException(status_code=400, detail="Cart is empty")

    product_ids = [item.product_id for item in items]
    products = {
        product.id: product
        for product in (
            db.query(Product)
            .filter(Product.id.in_(product_ids))
            .with_for_update()
            .all()
        )
    }
    if len(products) != len(set(product_ids)):
        raise HTTPException(status_code=409, detail="A cart product is no longer available")

    requested_by_product: dict[str, int] = {}
    for item in items:
        requested_by_product[item.product_id] = requested_by_product.get(item.product_id, 0) + item.quantity
    for product_id, requested_quantity in requested_by_product.items():
        product = products[product_id]
        if product.stock_count < requested_quantity:
            raise HTTPException(status_code=409, detail=f"Insufficient stock for {product.title}")
    total = sum(products[item.product_id].price * item.quantity for item in items)

    session = CheckoutSession(
        checkout_ref=_checkout_ref(),
        user_id=locked_user.id,
        total=round(total, 2),
        shipping_address=shipping_address,
        status=AWAITING_CONSENT,
        expires_at=_now() + timedelta(seconds=settings.CHECKOUT_SESSION_TTL_SECONDS),
    )
    db.add(session)
    db.flush()

    for item in items:
        product = products[item.product_id]
        product.stock_count -= item.quantity
        db.add(
            Order(
                order_ref=_order_ref(),
                user_id=locked_user.id,
                product_id=product.id,
                quantity=item.quantity,
                size=item.size,
                color=item.color,
                storage=item.storage,
                price=round(product.price * item.quantity, 2),
                checkout_session_id=session.id,
                status=OrderStatus.PENDING_APPROVAL,
                approval_deadline=session.expires_at,
            )
        )
        db.delete(item)
    record_audit(
        db,
        event_type="checkout.session_created",
        endpoint="/api/v1/checkout/session",
        verdict="awaiting_consent",
        actor=f"user:{locked_user.email}",
    )
    db.flush()
    return session


def abandon_checkout_session(db: Session, session: CheckoutSession, actor: str) -> bool:
    if session.status in {CANCELLED, EXPIRED}:
        return False
    if session.status != AWAITING_CONSENT:
        raise HTTPException(status_code=409, detail="Confirmed checkouts cannot be abandoned")
    released = _release_session_reservation(db, session, CANCELLED)
    if released:
        record_audit(
            db,
            event_type="checkout.session_abandoned",
            endpoint=f"/api/v1/checkout/session/{session.checkout_ref}/abandon",
            verdict="cancelled",
            actor=actor,
        )
    return released


def _require_consent(
    db: Session,
    user: User,
    amount: float,
    consent_id: str | None,
    *,
    order: Order | None = None,
    checkout: CheckoutSession | None = None,
) -> FinancialConsentLog:
    if bool(order) == bool(checkout):
        raise RuntimeError("Consent must have exactly one subject")
    consent = (
        db.query(FinancialConsentLog)
        .filter(
            FinancialConsentLog.consent_id == consent_id,
            FinancialConsentLog.user_id == user.id,
            FinancialConsentLog.status == "Approved",
            FinancialConsentLog.consumed_at.is_(None),
        )
        .with_for_update()
        .first()
    )
    subject_ref = order.order_ref if order else checkout.checkout_ref
    if not consent or abs(consent.amount - amount) > 0.01:
        raise HTTPException(
            status_code=status.HTTP_428_PRECONDITION_REQUIRED,
            detail=f"FINANCIAL_CONSENT_REQUIRED:{subject_ref}",
        )
    if order and consent.reference_order_id != order.id:
        raise HTTPException(status_code=status.HTTP_428_PRECONDITION_REQUIRED, detail=f"FINANCIAL_CONSENT_REQUIRED:{subject_ref}")
    if checkout and consent.reference_checkout_id != checkout.id:
        raise HTTPException(status_code=status.HTTP_428_PRECONDITION_REQUIRED, detail=f"FINANCIAL_CONSENT_REQUIRED:{subject_ref}")
    return consent


def _validate_session_snapshot(db: Session, session: CheckoutSession, orders: list[Order]) -> None:
    changed = False
    for order in orders:
        product = db.query(Product).filter(Product.id == order.product_id).with_for_update().first()
        if not product or abs(product.price * order.quantity - order.price) > 0.01:
            changed = True
            break
    if changed:
        _release_session_reservation(db, session, CANCELLED)
        db.commit()
        raise HTTPException(status_code=409, detail="CHECKOUT_PRICE_CHANGED: Cart was restored; review the updated price and authorize again")


def confirm_checkout_session(
    db: Session,
    user: User,
    session: CheckoutSession,
    consent_id: str | None,
) -> CheckoutConfirmation:
    locked_user = db.query(User).filter(User.id == user.id).with_for_update().one()
    session = (
        db.query(CheckoutSession)
        .filter(CheckoutSession.id == session.id, CheckoutSession.user_id == locked_user.id)
        .with_for_update()
        .one()
    )
    if session.status in {REVERSAL_WINDOW_OPEN, CONFIRMED}:
        wallet = db.query(UserWallet).filter(UserWallet.user_id == locked_user.id).with_for_update().one()
        return CheckoutConfirmation(session, [order.order_ref for order in _orders_for_session(db, session)], wallet.available_balance, False)
    if session.status in {CANCELLED, EXPIRED}:
        raise HTTPException(status_code=409, detail="Checkout session is no longer active")
    if session.status != AWAITING_CONSENT:
        raise HTTPException(status_code=409, detail="Checkout session cannot be confirmed")
    if as_aware_utc(session.expires_at) <= _now():
        _release_session_reservation(db, session, EXPIRED)
        db.commit()
        raise HTTPException(status_code=410, detail="Checkout session expired; cart items were restored")

    orders = _orders_for_session(db, session)
    if not orders or any(order.status != OrderStatus.PENDING_APPROVAL for order in orders):
        raise HTTPException(status_code=409, detail="Checkout session orders are not awaiting approval")
    _validate_session_snapshot(db, session, orders)
    consent = _require_consent(db, locked_user, session.total, consent_id, checkout=session)
    wallet = db.query(UserWallet).filter(UserWallet.user_id == locked_user.id).with_for_update().one()
    if wallet.available_balance < session.total:
        raise HTTPException(status_code=409, detail="Insufficient wallet balance")
    budget = db.query(UserBudget).filter(UserBudget.user_id == locked_user.id).with_for_update().first()

    now = _now()
    for order in orders:
        existing_debit = (
            db.query(WalletTransaction)
            .filter(
                WalletTransaction.reference_order_id == order.id,
                WalletTransaction.txn_type == "Debit",
            )
            .first()
        )
        if existing_debit:
            raise HTTPException(status_code=409, detail="Checkout session has an inconsistent debit state")
        wallet.available_balance -= order.price
        db.add(
            WalletTransaction(
                wallet_id=wallet.id,
                amount=order.price,
                txn_type="Debit",
                description=f"Purchase - {order.product.title}",
                reference_order_id=order.id,
            )
        )
        _transition(order, OrderStatus.REVERSAL_WINDOW_OPEN)
        order.reversal_deadline = now + timedelta(seconds=settings.APPROVAL_WINDOW_SECONDS)

    if budget:
        budget.current_spent += session.total
    consent.consumed_at = now
    session.status = REVERSAL_WINDOW_OPEN
    session.confirmed_at = now
    record_audit(
        db,
        event_type="checkout.confirmed",
        endpoint=f"/api/v1/checkout/session/{session.checkout_ref}/confirm",
        verdict="reversal_window_open",
        actor=f"user:{user.email}",
    )
    return CheckoutConfirmation(session, [order.order_ref for order in orders], wallet.available_balance, True)


def release_deal_reservation(db: Session, order: Order, reason: str) -> None:
    if not order.reservation_id:
        return
    reservation = (
        db.query(DealReservation)
        .filter(DealReservation.id == order.reservation_id)
        .with_for_update()
        .first()
    )
    if not reservation or reservation.status not in {"reserved", "committed"}:
        return
    deal = db.query(Deal).filter(Deal.id == reservation.deal_id).with_for_update().first()
    product = db.query(Product).filter(Product.id == order.product_id).with_for_update().first()
    reservation.status = "cancelled"
    if not deal or not product:
        return
    product.stock_count += reservation.quantity
    deal.stock_remaining = product.stock_count
    if not deal.deal_expires_at or as_aware_utc(deal.deal_expires_at) > _now():
        deal.is_active = True
    db.add(
        DealAuditLog(
            deal_id=deal.id,
            product_id=product.id,
            event_type="stock_changed",
            decision="reservation_released",
            reasoning={"reservation_id": reservation.id, "reason": reason, "quantity_restored": reservation.quantity},
        )
    )


def approve_pending_order(db: Session, user: User, order: Order, consent_id: str | None) -> float:
    if order.checkout_session_id:
        raise HTTPException(status_code=409, detail="Checkout-session orders must be confirmed through their checkout session")
    if order.status != OrderStatus.PENDING_APPROVAL:
        raise HTTPException(status_code=409, detail="Order is no longer pending approval")
    if order.approval_deadline and as_aware_utc(order.approval_deadline) <= _now():
        release_deal_reservation(db, order, "approval_expired")
        _transition(order, OrderStatus.CANCELLED)
        db.commit()
        raise HTTPException(status_code=410, detail="Approval window expired; reserved stock was released")

    consent = _require_consent(db, user, order.price, consent_id, order=order)
    wallet = db.query(UserWallet).filter(UserWallet.user_id == user.id).with_for_update().one()
    if wallet.available_balance < order.price:
        raise HTTPException(status_code=409, detail="Insufficient wallet balance")
    budget = db.query(UserBudget).filter(UserBudget.user_id == user.id).with_for_update().first()
    existing_debit = (
        db.query(WalletTransaction)
        .filter(
            WalletTransaction.reference_order_id == order.id,
            WalletTransaction.txn_type == "Debit",
        )
        .first()
    )
    if existing_debit:
        raise HTTPException(status_code=409, detail="Order already has a debit")
    wallet.available_balance -= order.price
    db.add(
        WalletTransaction(
            wallet_id=wallet.id,
            amount=order.price,
            txn_type="Debit",
            description=f"Purchase - {order.product.title}",
            reference_order_id=order.id,
        )
    )
    if budget:
        budget.current_spent += order.price
    consent.consumed_at = _now()
    _transition(order, OrderStatus.REVERSAL_WINDOW_OPEN)
    order.reversal_deadline = _now() + timedelta(seconds=settings.APPROVAL_WINDOW_SECONDS)
    if order.reservation_id:
        reservation = db.query(DealReservation).filter(DealReservation.id == order.reservation_id).first()
        if reservation and reservation.status == "reserved":
            reservation.status = "committed"
    record_audit(
        db,
        event_type="human.approval",
        endpoint=f"/api/v1/approval/approve?order_ref={order.order_ref}",
        verdict="approved",
        actor=f"user:{user.email}",
    )
    return wallet.available_balance


def cancel_pending_order(db: Session, order: Order, reason: str) -> None:
    if order.status != OrderStatus.PENDING_APPROVAL:
        raise HTTPException(status_code=409, detail="Order is no longer pending approval")
    if order.checkout_session_id:
        raise HTTPException(status_code=409, detail="Checkout-session orders must be abandoned through their checkout session")
    release_deal_reservation(db, order, reason)
    _transition(order, OrderStatus.CANCELLED)


def _release_checkout_order_stock(db: Session, order: Order) -> None:
    product = db.query(Product).filter(Product.id == order.product_id).with_for_update().first()
    if product:
        product.stock_count += order.quantity


def refund_reversible_order(db: Session, user: User, order: Order, reason: str, endpoint: str) -> tuple[float, bool]:
    if order.status != OrderStatus.REVERSAL_WINDOW_OPEN:
        raise HTTPException(status_code=409, detail="Order is no longer reversible")
    if not order.reversal_deadline or as_aware_utc(order.reversal_deadline) <= _now():
        raise HTTPException(status_code=409, detail="Order is no longer reversible")

    wallet = db.query(UserWallet).filter(UserWallet.user_id == user.id).with_for_update().one()
    debit = (
        db.query(WalletTransaction)
        .filter(WalletTransaction.reference_order_id == order.id, WalletTransaction.txn_type == "Debit")
        .first()
    )
    refund = (
        db.query(WalletTransaction)
        .filter(WalletTransaction.reference_order_id == order.id, WalletTransaction.txn_type == "Refund")
        .first()
    )
    refunded = False
    if debit and not refund:
        wallet.available_balance += order.price
        db.add(
            WalletTransaction(
                wallet_id=wallet.id,
                amount=order.price,
                txn_type="Refund",
                description=f"Refund - {order.product.title}",
                reference_order_id=order.id,
            )
        )
        budget = db.query(UserBudget).filter(UserBudget.user_id == user.id).with_for_update().first()
        if budget:
            budget.current_spent = max(0, budget.current_spent - order.price)
        refunded = True
    if order.checkout_session_id:
        _release_checkout_order_stock(db, order)
    else:
        release_deal_reservation(db, order, reason)
    _transition(order, OrderStatus.CANCELLED)
    order.escrow_status = "REFUNDED"
    if order.checkout_session_id:
        checkout = db.query(CheckoutSession).filter(CheckoutSession.id == order.checkout_session_id).with_for_update().one()
        active_order = db.query(Order.id).filter(
            Order.checkout_session_id == checkout.id,
            Order.status != OrderStatus.CANCELLED,
        ).first()
        if not active_order:
            checkout.status = CANCELLED
            checkout.cancelled_at = _now()
    record_audit(db, event_type="order.reversal", endpoint=endpoint, verdict="cancelled", actor=f"user:{user.email}")
    return wallet.available_balance, refunded


def finalize_reversal_orders(db: Session) -> list[Order]:
    orders = (
        db.query(Order)
        .filter(
            Order.status == OrderStatus.REVERSAL_WINDOW_OPEN,
            Order.reversal_deadline <= _now(),
        )
        .with_for_update()
        .all()
    )
    finalized_order_ids = [order.id for order in orders]
    for order in orders:
        _transition(order, OrderStatus.CONFIRMED)
        order.escrow_status = "RELEASED"
    db.flush()

    if finalized_order_ids:
        checkouts = (
            db.query(CheckoutSession)
            .join(Order, Order.checkout_session_id == CheckoutSession.id)
            .filter(Order.id.in_(finalized_order_ids))
            .with_for_update()
            .all()
        )
        for checkout in checkouts:
            remaining = db.query(Order.id).filter(
                Order.checkout_session_id == checkout.id,
                Order.status == OrderStatus.REVERSAL_WINDOW_OPEN,
            ).first()
            if not remaining:
                terminal_orders = db.query(Order.status).filter(Order.checkout_session_id == checkout.id).all()
                if terminal_orders and all(order_status == OrderStatus.CANCELLED for (order_status,) in terminal_orders):
                    checkout.status = CANCELLED
                    checkout.cancelled_at = _now()
                else:
                    checkout.status = CONFIRMED
    if orders:
        db.commit()
    return orders


def dispatch_confirmed_order(db: Session, order: Order, actor: str) -> None:
    if order.status != OrderStatus.CONFIRMED or order.escrow_status != "RELEASED":
        raise HTTPException(status_code=409, detail="Order cannot be dispatched")
    _transition(order, OrderStatus.SHIPPED)
    order.shipped_at = _now()
    record_audit(
        db,
        event_type="seller.dispatch",
        endpoint=f"/api/v1/seller/orders/{order.order_ref}/dispatch",
        verdict="shipped",
        actor=actor,
    )


def confirm_delivery(db: Session, user: User, order: Order) -> None:
    if order.status != OrderStatus.SHIPPED:
        raise HTTPException(status_code=409, detail="Order has not been dispatched")
    _transition(order, OrderStatus.DELIVERED)
    order.delivered_at = _now()
    record_audit(
        db,
        event_type="order.delivery_confirmed",
        endpoint=f"/api/v1/orders/{order.order_ref}/confirm-delivery",
        verdict="delivered",
        actor=f"user:{user.email}",
    )
