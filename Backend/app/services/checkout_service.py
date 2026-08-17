"""
Checkout orchestration.

Two entry points matching the two-step Razorpay flow:

  init_checkout()    -> validates the cart, creates a Razorpay order,
                         records a 'pending' payment row.
  confirm_checkout()  -> re-verifies the payment signature (never trusts the
                         client's claim of success), marks the payment and
                         session paid, generates the invoice, and issues the
                         encrypted QR exit pass.

Session status transitions: 'active' (shopping) -> stays 'active' through
payment (the customer is still physically in the store) -> 'checked_out'
only once the QR exit pass has actually been scanned by the retailer
(see exit_service.py). Payment success alone does not close the session —
that's an important distinction for Phase 6's AI pipeline, which needs to
keep monitoring a customer between "paid" and "actually walked out."
"""
from app.core.exceptions import ConflictError, ValidationFailedError
from app.db.supabase_client import get_service_client
from app.schemas.checkout import CheckoutConfirmResponse, CheckoutInitResponse, PaymentConfirmRequest
from app.core.config import settings
from app.services import cart_service, invoice_service, notification_service, payment_service, qr_service, session_service
from app.utils.time import utcnow_iso


def init_checkout(session_id: str, customer_id: str) -> CheckoutInitResponse:
    service = get_service_client()
    session = session_service.get_session_or_raise(session_id, customer_id)

    if session["status"] != "active":
        raise ConflictError("This session is not open for checkout")
    if session["payment_status"] == "success":
        raise ConflictError("This session has already been paid for")

    cart = cart_service.get_cart_summary(session_id, customer_id)
    if not cart.items:
        raise ValidationFailedError("Cannot checkout an empty cart")

    order = payment_service.create_order(amount_paise=cart.total_paise, receipt=session_id)

    service.table("payments").insert(
        {
            "session_id": session_id,
            "provider": "razorpay",
            "provider_order_id": order["id"],
            "amount_paise": cart.total_paise,
            "status": "pending",
        }
    ).execute()

    return CheckoutInitResponse(
        session_id=session_id,
        razorpay_order_id=order["id"],
        razorpay_key_id=settings.razorpay_key_id,
        amount_paise=cart.total_paise,
    )


def confirm_checkout(
    session_id: str, customer_id: str, payload: PaymentConfirmRequest, customer_email: str | None = None
) -> CheckoutConfirmResponse:
    service = get_service_client()
    session = session_service.get_session_or_raise(session_id, customer_id)

    payment_rows = (
        service.table("payments")
        .select("*")
        .eq("session_id", session_id)
        .eq("provider_order_id", payload.razorpay_order_id)
        .execute()
    )
    if not payment_rows.data:
        raise ValidationFailedError("No matching payment order for this session")
    payment_row = payment_rows.data[0]

    is_valid = payment_service.verify_signature(
        order_id=payload.razorpay_order_id,
        payment_id=payload.razorpay_payment_id,
        signature=payload.razorpay_signature,
    )
    if not is_valid:
        service.table("payments").update(
            {"status": "failed", "provider_payment_id": payload.razorpay_payment_id,
             "failure_reason": "Signature verification failed"}
        ).eq("id", payment_row["id"]).execute()
        raise ValidationFailedError("Payment verification failed")

    service.table("payments").update(
        {"status": "success", "provider_payment_id": payload.razorpay_payment_id}
    ).eq("id", payment_row["id"]).execute()
    service.table("shopping_sessions").update(
        {"payment_status": "success", "checkout_time": utcnow_iso()}
    ).eq("id", session_id).execute()

    cart = cart_service.get_cart_summary(session_id, customer_id)
    store = service.table("stores").select("name, retailer_id").eq("id", session["store_id"]).execute()
    store_name = store.data[0]["name"] if store.data else ""
    retailer_id = store.data[0].get("retailer_id") if store.data else None

    customer_row = service.table("customers").select("full_name").eq("id", customer_id).execute()
    customer_name = customer_row.data[0]["full_name"] if customer_row.data else None

    invoice = invoice_service.generate_invoice(
        session_id, store_name, cart, customer_email=customer_email, customer_name=customer_name
    )

    if retailer_id:
        notification_service.create_notification(
            recipient_type="retailer",
            recipient_id=retailer_id,
            title=f"Payment received: {invoice.invoice_number}",
            body=f"Rs. {cart.total_paise / 100:.2f}",
            category="payment",
            related_id=session_id,
        )
    notification_service.create_notification(
        recipient_type="customer",
        recipient_id=customer_id,
        title="Payment successful",
        body=f"Your order at {store_name} is confirmed. Show your QR pass to exit.",
        category="payment",
        related_id=session_id,
    )

    qr_token, qr_expiry = qr_service.generate_qr_pass(
        session_id=session_id, store_id=session["store_id"], customer_id=customer_id
    )
    service.table("shopping_sessions").update(
        {"qr_pass_token": qr_token, "qr_pass_expires_at": qr_expiry}
    ).eq("id", session_id).execute()

    return CheckoutConfirmResponse(
        session_id=session_id,
        payment_status="success",
        invoice=invoice,
        qr_pass_token=qr_token,
        qr_pass_expires_at=qr_expiry,
        qr_code_image_base64=qr_service.qr_image_base64(qr_token),
    )
