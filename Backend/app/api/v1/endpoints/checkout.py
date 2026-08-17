"""Checkout — spec Steps 6-8 (final bill, payment, invoice + QR pass)."""
from fastapi import APIRouter, Depends, Request

from app.api.v1.deps import get_current_customer
from app.core.rate_limit import limiter
from app.core.security import AuthenticatedUser
from app.schemas.checkout import CheckoutConfirmResponse, CheckoutInitResponse, PaymentConfirmRequest
from app.services import checkout_service

router = APIRouter(prefix="/sessions/{session_id}/checkout", tags=["Checkout"])


@router.post(
    "",
    response_model=CheckoutInitResponse,
    summary="Start checkout: generate the final bill and a Razorpay order",
)
@limiter.limit("10/minute")
def start_checkout(
    request: Request, session_id: str, user: AuthenticatedUser = Depends(get_current_customer)
) -> CheckoutInitResponse:
    return checkout_service.init_checkout(session_id=session_id, customer_id=user.id)


@router.post(
    "/confirm",
    response_model=CheckoutConfirmResponse,
    summary="Confirm payment after the Razorpay Checkout widget succeeds",
    description=(
        "The payment signature is re-verified server-side — a client claiming "
        "success is never trusted on its own. On success, generates the invoice "
        "and the encrypted QR exit pass."
    ),
)
@limiter.limit("10/minute")
def confirm_checkout(
    request: Request,
    session_id: str,
    payload: PaymentConfirmRequest,
    user: AuthenticatedUser = Depends(get_current_customer),
) -> CheckoutConfirmResponse:
    return checkout_service.confirm_checkout(
        session_id=session_id, customer_id=user.id, payload=payload, customer_email=user.email
    )
