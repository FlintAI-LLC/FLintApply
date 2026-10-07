"""Stripe Checkout wallet payment options (Apple Pay, Google Pay)."""

from __future__ import annotations

from typing import Any

from app.config import settings


def checkout_wallet_kwargs() -> dict[str, Any]:
    """Extra kwargs for ``stripe.checkout.Session.create``.

    Apple Pay and Google Pay on Stripe *hosted* Checkout are controlled from the
    Dashboard payment-method settings. Do **not** pass ``automatic_payment_methods``
    here — that parameter is for PaymentIntents, and Stripe rejects it on Checkout
    Sessions with ``invalid_request_error`` (surfaced to users as HTTP 500).

    ``STRIPE_CHECKOUT_WALLETS_ENABLED`` is retained for future ``wallet_options``
    tuning; today both paths omit invalid Session parameters.
    """
    if not settings.STRIPE_CHECKOUT_WALLETS_ENABLED:
        return {}
    return {}


__all__ = ["checkout_wallet_kwargs"]
