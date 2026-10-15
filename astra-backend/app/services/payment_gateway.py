"""Payment gateway layer.

The wallet ledger remains the settlement rail for escrow; external card
payments enter the system as wallet top-ups through Stripe PaymentIntents.
When no STRIPE_SECRET_KEY is configured, card rails are unavailable and the
endpoints degrade to 503 instead of failing silently.
"""
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import stripe

from app.core.config import settings

log = logging.getLogger("astra.payments")


@dataclass
class CardTopUpIntent:
    intent_id: str
    client_secret: str
    amount: float
    currency: str


def stripe_configured() -> bool:
    return bool(
        settings.STRIPE_SECRET_KEY
        and settings.STRIPE_PUBLISHABLE_KEY
        and settings.STRIPE_WEBHOOK_SECRET
        and _mode_matches_key()
    )


def _mode_matches_key() -> bool:
    if settings.STRIPE_MODE == "test":
        return (
            settings.STRIPE_SECRET_KEY.startswith("sk_test_")
            and settings.STRIPE_PUBLISHABLE_KEY.startswith("pk_test_")
        )
    if settings.STRIPE_MODE == "live":
        return (
            settings.STRIPE_SECRET_KEY.startswith("sk_live_")
            and settings.STRIPE_PUBLISHABLE_KEY.startswith("pk_live_")
        )
    return False


def stripe_checkout_configured() -> bool:
    return stripe_configured()


def stripe_connect_configured() -> bool:
    return settings.STRIPE_CONNECT_ENABLED and settings.STRIPE_MODE == "test" and stripe_checkout_configured()


def _client() -> stripe.StripeClient:
    return stripe.StripeClient(settings.STRIPE_SECRET_KEY)


def create_topup_intent(amount_pkr: float, user_id: int, reference: str) -> CardTopUpIntent:
    """Create a Stripe PaymentIntent that credits the user's wallet on success."""
    intent = _client().payment_intents.create(
        amount=int(round(amount_pkr * 100)),
        currency="pkr",
        automatic_payment_methods={"enabled": True},
        metadata={"kind": "wallet_topup", "user_id": str(user_id), "reference": reference},
    )


def create_checkout_session(
    *,
    line_items: list[dict[str, Any]],
    metadata: dict[str, str],
    success_url: str,
    cancel_url: str,
    expires_at: int,
    idempotency_key: str,
) -> tuple[str, str]:
    session = _client().checkout.sessions.create(
        mode="payment",
        line_items=line_items,
        metadata=metadata,
        success_url=success_url,
        cancel_url=cancel_url,
        expires_at=expires_at,
        payment_intent_data={"metadata": metadata},
        options={"idempotency_key": idempotency_key},
    )
    return session.id, session.url


def create_connect_account(email: str, seller_user_id: int) -> str:
    account = _client().accounts.create(
        type="express",
        email=email,
        metadata={"astra_seller_user_id": str(seller_user_id)},
    )
    return account.id


def create_connect_account_link(account_id: str, refresh_url: str, return_url: str) -> str:
    link = _client().account_links.create(
        account=account_id,
        refresh_url=refresh_url,
        return_url=return_url,
        type="account_onboarding",
    )
    return link.url


def retrieve_connect_account(account_id: str) -> Any:
    return _client().accounts.retrieve(account_id)


def create_seller_transfer(amount_paisa: int, account_id: str, order_id: int) -> str:
    transfer = _client().transfers.create(
        amount=amount_paisa,
        currency="pkr",
        destination=account_id,
        metadata={"astra_order_id": str(order_id)},
        options={"idempotency_key": f"astra-order-payout-{order_id}"},
    )
    return transfer.id


def refund_payment_intent(payment_intent_id: str, order_id: int, amount_paisa: int) -> str:
    refund = _client().refunds.create(
        payment_intent=payment_intent_id,
        amount=amount_paisa,
        metadata={"astra_order_id": str(order_id)},
        options={"idempotency_key": f"astra-order-refund-{order_id}"},
    )
    return refund.id


def expire_checkout_session(session_id: str) -> None:
    _client().checkout.sessions.expire(session_id)


def retrieve_checkout_session(session_id: str) -> Any:
    return _client().checkout.sessions.retrieve(session_id)
    log.info("stripe intent created: %s for user %s (Rs. %.2f)", intent.id, user_id, amount_pkr)
    return CardTopUpIntent(
        intent_id=intent.id,
        client_secret=intent.client_secret or "",
        amount=amount_pkr,
        currency="pkr",
    )


def construct_webhook_event(payload: bytes, signature: str) -> stripe.Event:
    return stripe.Webhook.construct_event(payload, signature, settings.STRIPE_WEBHOOK_SECRET)
