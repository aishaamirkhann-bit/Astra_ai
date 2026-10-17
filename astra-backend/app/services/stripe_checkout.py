"""Stripe Checkout settlement and refund reconciliation."""
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.budget import UserBudget
from app.models.checkout import CheckoutSession
from app.models.order import Order, OrderStatus
from app.models.payment import StripeCheckoutPayment, StripeRefund
from app.services import payment_gateway
from app.services.audit import record_audit
from app.services.checkout_fsm import AWAITING_CONSENT, REVERSAL_WINDOW_OPEN, release_checkout_session
from app.services.seller_payouts import record_order_payouts

log = logging.getLogger("astra.payments")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _store_refund(
    db: Session,
    payment: StripeCheckoutPayment,
    refund_id: str,
    amount_paisa: int,
    status: str,
    order_id: int | None = None,
) -> StripeRefund:
    refund = db.get(StripeRefund, refund_id)
    if refund is None:
        refund = StripeRefund(
            refund_id=refund_id,
            stripe_checkout_payment_id=payment.id,
            order_id=order_id,
            amount_paisa=amount_paisa,
            status=status,
        )
        db.add(refund)
    else:
        refund.status = status
        refund.amount_paisa = amount_paisa or refund.amount_paisa
        refund.updated_at = _now()
        if order_id is not None:
            refund.order_id = order_id
    return refund


def settle_paid_checkout(
    db: Session,
    payment: StripeCheckoutPayment,
    stripe_session: dict[str, Any],
    *,
    actor: str,
) -> str:
    """Settle an active checkout, or refund a paid checkout that cannot become an order."""
    checkout = db.query(CheckoutSession).filter(
        CheckoutSession.id == payment.checkout_session_id,
    ).with_for_update().first()
    if not checkout:
        payment.status = "paid_review"
        log.error("Paid Stripe checkout %s has no local checkout", payment.stripe_session_id)
        return payment.status
    if payment.status == "paid":
        return payment.status

    payment_intent_id = stripe_session.get("payment_intent")
    payment.payment_intent_id = payment_intent_id
    payment.paid_at = payment.paid_at or _now()
    orders = db.query(Order).filter(
        Order.checkout_session_id == checkout.id,
    ).with_for_update().all()
    paid_total = stripe_session.get("amount_total")
    expected_total = int(round(checkout.total * 100))
    amount_matches = paid_total is not None and int(paid_total) == expected_total
    active_orders = bool(orders) and all(order.status == OrderStatus.PENDING_APPROVAL for order in orders)

    if checkout.status == AWAITING_CONSENT and active_orders and amount_matches:
        now = payment.paid_at
        payment.status = "paid"
        checkout.status = REVERSAL_WINDOW_OPEN
        checkout.confirmed_at = now
        budget = db.query(UserBudget).filter(UserBudget.user_id == checkout.user_id).with_for_update().first()
        if budget:
            budget.current_spent += checkout.total
        for order in orders:
            order.status = OrderStatus.REVERSAL_WINDOW_OPEN
            order.reversal_deadline = now + timedelta(seconds=settings.APPROVAL_WINDOW_SECONDS)
        record_order_payouts(db, orders)
        record_audit(
            db,
            event_type="payments.checkout_settled",
            endpoint="/webhooks/stripe",
            verdict="paid",
            actor=actor,
        )
        return payment.status

    if checkout.status == AWAITING_CONSENT:
        release_checkout_session(db, checkout, "cancelled")
    payment.status = "paid_review"
    amount_to_refund = int(paid_total) if paid_total is not None else int(round(payment.amount * 100))
    if not payment_intent_id or amount_to_refund <= 0:
        record_audit(
            db,
            event_type="payments.late_checkout_refund_failed",
            endpoint="/webhooks/stripe",
            verdict="missing_refund_reference",
            actor=actor,
        )
        log.error("Paid checkout %s needs manual refund reconciliation", checkout.checkout_ref)
        return payment.status

    try:
        refund_id = payment_gateway.refund_payment_intent(
            payment_intent_id,
            None,
            amount_to_refund,
            idempotency_key=checkout.checkout_ref,
            checkout_ref=checkout.checkout_ref,
        )
        _store_refund(db, payment, refund_id, amount_to_refund, "requested")
        payment.status = "refund_pending"
        record_audit(
            db,
            event_type="payments.late_checkout_refunded",
            endpoint="/webhooks/stripe",
            verdict="refund_requested",
            actor=actor,
        )
    except Exception:
        payment.status = "refund_failed"
        _store_refund(
            db,
            payment,
            f"request-{checkout.checkout_ref}",
            amount_to_refund,
            "failed",
        )
        log.exception("Could not refund paid checkout %s", checkout.checkout_ref)
        record_audit(
            db,
            event_type="payments.late_checkout_refund_failed",
            endpoint="/webhooks/stripe",
            verdict="refund_failed",
            actor=actor,
        )
    return payment.status


def retry_failed_checkout_refunds(db: Session) -> int:
    payments = db.query(StripeCheckoutPayment).filter(
        StripeCheckoutPayment.status == "refund_failed",
        StripeCheckoutPayment.payment_intent_id.is_not(None),
    ).with_for_update().all()
    retried = 0
    for payment in payments:
        checkout = db.get(CheckoutSession, payment.checkout_session_id)
        if not checkout:
            continue
        failed_request = db.get(StripeRefund, f"request-{checkout.checkout_ref}")
        if not failed_request:
            continue
        try:
            refund_id = payment_gateway.refund_payment_intent(
                payment.payment_intent_id,
                None,
                failed_request.amount_paisa,
                idempotency_key=checkout.checkout_ref,
                checkout_ref=checkout.checkout_ref,
            )
            amount_paisa = failed_request.amount_paisa
            db.delete(failed_request)
            _store_refund(db, payment, refund_id, amount_paisa, "requested")
            payment.status = "refund_pending"
            record_audit(
                db,
                event_type="payments.late_checkout_refund_retried",
                endpoint="/webhooks/stripe",
                verdict="refund_requested",
                actor=f"stripe:refund-retry:{checkout.checkout_ref}",
            )
            retried += 1
        except Exception:
            log.exception("Retry failed for paid checkout %s", checkout.checkout_ref)
    if retried:
        db.commit()
    return retried


def mark_checkout_payment_failed(
    db: Session,
    payment: StripeCheckoutPayment,
    status: str,
    *,
    actor: str,
) -> None:
    if payment.status in {"paid", "paid_review", "refund_pending", "refunded", "partially_refunded"}:
        return
    checkout = db.query(CheckoutSession).filter(
        CheckoutSession.id == payment.checkout_session_id,
    ).with_for_update().first()
    payment.status = status
    if checkout and checkout.status == AWAITING_CONSENT:
        target = "expired" if status == "expired" else "cancelled"
        release_checkout_session(db, checkout, target)
    record_audit(
        db,
        event_type="payments.checkout_failed",
        endpoint="/webhooks/stripe",
        verdict=status,
        actor=actor,
    )


def reconcile_refund_object(db: Session, refund_obj: dict[str, Any]) -> None:
    refund_id = refund_obj.get("id")
    if not refund_id:
        return
    payment_intent_id = refund_obj.get("payment_intent")
    existing = db.get(StripeRefund, refund_id)
    payment = db.get(StripeCheckoutPayment, existing.stripe_checkout_payment_id) if existing else None
    if payment is None and payment_intent_id:
        payment = db.query(StripeCheckoutPayment).filter(
            StripeCheckoutPayment.payment_intent_id == payment_intent_id,
        ).first()
    if payment is None:
        return
    status = refund_obj.get("status") or "pending"
    amount = int(refund_obj.get("amount") or 0)
    _store_refund(db, payment, refund_id, amount, status)
    db.flush()
    succeeded = db.query(StripeRefund).filter(
        StripeRefund.stripe_checkout_payment_id == payment.id,
        StripeRefund.status == "succeeded",
    ).all()
    refunded_total = sum(row.amount_paisa for row in succeeded)
    if refunded_total >= int(round(payment.amount * 100)):
        payment.status = "refunded"
    elif refunded_total > 0:
        payment.status = "partially_refunded"
    elif status in {"failed", "canceled"}:
        payment.status = "refund_failed"
    elif payment.status not in {"paid", "paid_review"}:
        payment.status = "refund_pending"


def reconcile_charge_refund(db: Session, charge: dict[str, Any]) -> None:
    refunds = charge.get("refunds") or {}
    payment_intent_id = charge.get("payment_intent")
    if not payment_intent_id:
        return
    payment = db.query(StripeCheckoutPayment).filter(
        StripeCheckoutPayment.payment_intent_id == payment_intent_id,
    ).first()
    if not payment:
        return
    refunded_total = int(charge.get("amount_refunded") or 0)
    refund_objects = refunds.get("data", [])
    for refund_obj in refund_objects:
        if not refund_obj.get("payment_intent"):
            refund_obj = {**refund_obj, "payment_intent": payment_intent_id}
        reconcile_refund_object(db, refund_obj)
    if refunded_total and not refund_objects:
        _store_refund(
            db,
            payment,
            f"charge-refunded-{charge.get('id', payment_intent_id)}",
            refunded_total,
            "succeeded",
        )
    if refunded_total >= int(round(payment.amount * 100)):
        payment.status = "refunded"
    elif refunded_total > 0:
        payment.status = "partially_refunded"