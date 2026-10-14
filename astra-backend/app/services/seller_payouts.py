"""Seller payout boundary, intentionally isolated from buyer wallet funds."""

from typing import Protocol

from app.models.user import User


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
