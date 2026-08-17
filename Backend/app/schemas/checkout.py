"""Schemas for checkout, payment confirmation, invoice, and QR exit pass."""
from pydantic import BaseModel


class CheckoutInitResponse(BaseModel):
    """Returned when a customer starts checkout — everything the frontend needs
    to open the Razorpay Checkout widget."""
    session_id: str
    razorpay_order_id: str
    razorpay_key_id: str
    amount_paise: int
    currency: str = "INR"


class PaymentConfirmRequest(BaseModel):
    """The three fields Razorpay's client-side checkout returns on success —
    all three are required to verify the payment signature server-side."""
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


class InvoiceResponse(BaseModel):
    invoice_number: str
    subtotal_paise: int
    discount_paise: int
    gst_paise: int
    total_paise: int
    pdf_url: str | None


class CheckoutConfirmResponse(BaseModel):
    session_id: str
    payment_status: str
    invoice: InvoiceResponse
    qr_pass_token: str
    qr_pass_expires_at: str
    qr_code_image_base64: str  # PNG, base64-encoded, ready for an <img src="data:image/png;base64,...">


class ExitScanRequest(BaseModel):
    qr_token: str


class ExitScanResponse(BaseModel):
    session_id: str
    customer_name: str
    store_name: str
    total_paise: int
    exit_time: str
