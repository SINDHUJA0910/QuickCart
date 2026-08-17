"""
Razorpay payment integration.

Wrapped behind this module's two functions (`create_order`, `verify_signature`)
rather than calling the Razorpay SDK directly from checkout_service, for two
reasons: (1) it's the seam tests patch to avoid hitting Razorpay's real API,
and (2) if Stripe support is added later (per the spec's "Stripe (configurable)"
option), a `stripe_payment_service.py` implementing the same two functions
can be swapped in behind a `PAYMENT_PROVIDER` setting without touching
checkout_service at all.

Signature verification is the security-critical piece: Razorpay signs
`order_id + "|" + payment_id` with HMAC-SHA256 using the account's key secret.
A client claiming "payment succeeded" is never trusted on its own — we
recompute this HMAC ourselves and compare, so a malicious client can't
fabricate a fake success callback.
"""
import hashlib
import hmac
from functools import lru_cache

import razorpay

from app.core.config import settings
from app.core.exceptions import ValidationFailedError


@lru_cache
def _client() -> razorpay.Client:
    return razorpay.Client(auth=(settings.razorpay_key_id, settings.razorpay_key_secret))


def create_order(amount_paise: int, receipt: str) -> dict:
    """Creates a Razorpay order. Returns the raw order dict (contains `id`, used
    by the frontend to open Razorpay Checkout)."""
    if amount_paise <= 0:
        raise ValidationFailedError("Cannot checkout an empty cart")

    return _client().order.create(
        {
            "amount": amount_paise,  # Razorpay also expects the smallest currency unit (paise)
            "currency": "INR",
            "receipt": receipt,
            "payment_capture": 1,
        }
    )


def verify_signature(order_id: str, payment_id: str, signature: str) -> bool:
    """Recomputes the HMAC-SHA256 signature Razorpay expects and compares it
    against what the client sent, using a constant-time comparison to avoid
    timing side-channels. Returns True only on an exact match."""
    payload = f"{order_id}|{payment_id}".encode()
    expected = hmac.new(
        settings.razorpay_key_secret.encode(), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
