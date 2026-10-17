"""Seller payout calculation and feature-flagged Stripe Connect transfers."""

from datetime import datetime, timezone
from typing import Protocol

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.order import Order
from app.models.payment import SellerPayoutLedger, StripeConnectAccount
from app.models.product import Product
from app.models.seller_profile import SellerProfile
from app.models.user import User
from app.services import payment_gateway


class SellerPayoutsUnavailable(RuntimeError):
    """Raised until a verified seller settlement provider is configured."""


class SellerPayoutProcessor(Protocol):
    def request_payout(self, seller: User, amount: float) -> dict:
        """Create a payout only from a seller-owned settled balance."""


class UnconfiguredSellerPayoutProcessor:
    """Default provider hook. Replace through dependency wiring after provider review."""

    def request_payout(self, _seller: User, _amount: float) -> dict:
        raise SellerPayoutsUnavailable(
            "Seller payouts are disabled: no verified payout processor or seller settlement ledger is configured."
        )


def get_seller_payout_processor() -> SellerPayoutProcessor:
    """Dependency hook for a future verified processor implementation."""
    return UnconfiguredSellerPayoutProcessor()


def payout_amounts(gross_amount: float, fee_percent: float | None = None) -> tuple[float, float]:
    fee_percent = settings.PLATFORM_FEE_PERCENT if fee_percent is None else fee_percent
    if not 0 <= fee_percent <= 100:
        raise ValueError("PLATFORM_FEE_PERCENT must be between 0 and 100")
    fee = round(gross_amount * fee_percent / 100, 2)
    return fee, round(gross_amount - fee, 2)


def record_order_payouts(db: Session, orders: list[Order]) -> None:
    """Write one net payout ledger row per paid order; transfer only when enabled."""
    for order in orders:
        existing = db.query(SellerPayoutLedger).filter(SellerPayoutLedger.order_id == order.id).first()
        if existing:
            continue
        product: Product = order.product
        seller_profile = db.query(SellerProfile).filter(SellerProfile.seller_key == product.seller_id).first()
        seller = db.get(User, seller_profile.user_id) if seller_profile else None
        fee, seller_amount = payout_amounts(order.price)
        entry = SellerPayoutLedger(
            order_id=order.id,
            seller_user_id=seller.id if seller else None,
            seller_key=product.seller_id,
            gross_amount=order.price,
            platform_fee=fee,
            seller_amount=seller_amount,
            status="pending_seller_match" if seller is None else "queued",
        )
        db.add(entry)
        db.flush()
        if seller is not None and payment_gateway.stripe_connect_configured():
            account = db.get(StripeConnectAccount, seller.id)
            if not account or not account.payouts_enabled:
                entry.status = "pending_onboarding"
        elif seller is not None:
            entry.status = "connect_disabled"


def process_order_payout(db: Session, order: Order) -> None:
    """Transfer a seller's net share only after the reversible escrow window closes."""
    entry = db.query(SellerPayoutLedger).filter(SellerPayoutLedger.order_id == order.id).with_for_update().first()
    if entry is None or entry.status not in {"queued", "pending_onboarding", "connect_disabled", "transfer_failed"}:
        return
    if not payment_gateway.stripe_connect_configured():
        return
    account = db.get(StripeConnectAccount, entry.seller_user_id) if entry.seller_user_id else None
    if not account or not account.payouts_enabled:
        entry.status = "pending_onboarding"
        return
    entry.transfer_attempts += 1
    try:
        entry.stripe_transfer_id = payment_gateway.create_seller_transfer(
            int(round(entry.seller_amount * 100)),
            account.stripe_account_id,
            order.id,
            idempotency_key=f"astra-order-payout-{order.id}-{entry.transfer_attempts}",
        )
        entry.status = "transferred"
    except Exception:
        entry.status = "transfer_failed"


def retry_seller_transfers(db: Session, seller: User) -> int:
    entries = db.query(SellerPayoutLedger).filter(
        SellerPayoutLedger.seller_user_id == seller.id,
        SellerPayoutLedger.status == "transfer_failed",
    ).all()
    for entry in entries:
        order = db.get(Order, entry.order_id)
        if order and order.escrow_status == "RELEASED":
            process_order_payout(db, order)
    db.commit()
    return sum(entry.status == "transferred" for entry in entries)


def start_connect_onboarding(db: Session, seller: User, refresh_url: str, return_url: str) -> str:
    if not payment_gateway.stripe_connect_configured():
        raise SellerPayoutsUnavailable("Stripe Connect is disabled; set STRIPE_CONNECT_ENABLED=true with test-mode keys to enable it.")
    account = db.get(StripeConnectAccount, seller.id)
    if account is None:
        stripe_account_id = payment_gateway.create_connect_account(seller.email, seller.id)
        account = StripeConnectAccount(seller_user_id=seller.id, stripe_account_id=stripe_account_id)
        db.add(account)
        db.commit()
    return payment_gateway.create_connect_account_link(account.stripe_account_id, refresh_url, return_url)


def connect_account_status(db: Session, seller: User) -> dict:
    account = db.get(StripeConnectAccount, seller.id)
    if account is None:
        return {"configured": payment_gateway.stripe_connect_configured(), "onboarded": False, "payouts_enabled": False}
    if not payment_gateway.stripe_connect_configured():
        return {"configured": False, "onboarded": bool(account.details_submitted), "payouts_enabled": bool(account.payouts_enabled)}
    remote = payment_gateway.retrieve_connect_account(account.stripe_account_id)
    account.details_submitted = int(bool(remote.get("details_submitted")))
    account.charges_enabled = int(bool(remote.get("charges_enabled")))
    account.payouts_enabled = int(bool(remote.get("payouts_enabled")))
    account.updated_at = datetime.now(timezone.utc)
    if account.payouts_enabled:
        for entry in db.query(SellerPayoutLedger).filter(
            SellerPayoutLedger.seller_user_id == seller.id,
            SellerPayoutLedger.status.in_( ["pending_onboarding", "connect_disabled", "transfer_failed"]),
        ).all():
            order = db.get(Order, entry.order_id)
            if order and order.escrow_status == "RELEASED":
                process_order_payout(db, order)
    db.commit()
    return {
        "configured": True,
        "onboarded": bool(account.details_submitted),
        "charges_enabled": bool(account.charges_enabled),
        "payouts_enabled": bool(account.payouts_enabled),
    }
