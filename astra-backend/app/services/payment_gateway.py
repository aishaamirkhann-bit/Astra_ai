"""Payment gateway layer.

The wallet ledger remains the settlement rail for escrow; external card
payments enter the system as wallet top-ups through Stripe PaymentIntents.
When no STRIPE_SECRET_KEY is configured, card rails are unavailable and the
endpoints degrade to 503 instead of failing silently.
"""
import logging
from dataclasses import dataclass

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
    return bool(settings.STRIPE_SECRET_KEY)


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
    log.info("stripe intent created: %s for user %s (Rs. %.2f)", intent.id, user_id, amount_pkr)
    return CardTopUpIntent(
        intent_id=intent.id,
        client_secret=intent.client_secret or "",
        amount=amount_pkr,
        currency="pkr",
    )


def construct_webhook_event(payload: bytes, signature: str) -> stripe.Event:
    return stripe.Webhook.construct_event(payload, signature, settings.STRIPE_WEBHOOK_SECRET)
