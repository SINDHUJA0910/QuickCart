"""
Tests for Phase 4: payment signature verification, QR pass encryption, and
the end-to-end checkout flow (init -> confirm -> invoice -> QR -> exit scan).

Razorpay's order-creation API call is patched out (no network access), but
signature verification uses the REAL HMAC algorithm against the test secret —
this is the one function in the whole app where a bug would mean free
groceries, so it gets tested against the real implementation, not a mock
that just returns True.
"""
import hashlib
import hmac

import pytest

from app.core.exceptions import ForbiddenError, ValidationFailedError
from app.services import checkout_service, exit_service, payment_service, qr_service, session_service
from app.schemas.checkout import PaymentConfirmRequest
from tests.fake_supabase import FakeServiceClient

CUSTOMER_ID = "cust-1"
RETAILER_ID = "retailer-1"
STORE_ID = "store-1"
PRODUCT_ID = "prod-1"


def _sign(order_id: str, payment_id: str, secret: str) -> str:
    payload = f"{order_id}|{payment_id}".encode()
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


# ---------------------------------------------------------------------
# payment_service — pure signature verification
# ---------------------------------------------------------------------

def test_verify_signature_accepts_correctly_signed_payment():
    from app.core.config import settings
    sig = _sign("order_abc", "pay_xyz", settings.razorpay_key_secret)
    assert payment_service.verify_signature("order_abc", "pay_xyz", sig) is True


def test_verify_signature_rejects_forged_payment():
    """A client claiming success with a made-up signature must be rejected."""
    assert payment_service.verify_signature("order_abc", "pay_xyz", "not-a-real-signature") is False


def test_verify_signature_rejects_signature_for_different_payment_id():
    """Signature was valid for a DIFFERENT payment id — must not be reused."""
    from app.core.config import settings
    sig = _sign("order_abc", "pay_ORIGINAL", settings.razorpay_key_secret)
    assert payment_service.verify_signature("order_abc", "pay_TAMPERED", sig) is False


# ---------------------------------------------------------------------
# qr_service — encrypted pass round-trip
# ---------------------------------------------------------------------

def test_qr_pass_round_trips():
    token, expiry = qr_service.generate_qr_pass("sess-1", STORE_ID, CUSTOMER_ID)
    payload = qr_service.decode_qr_pass(token)
    assert payload["session_id"] == "sess-1"
    assert payload["store_id"] == STORE_ID
    assert payload["payment_status"] == "success"


def test_qr_pass_rejects_tampered_token():
    token, _ = qr_service.generate_qr_pass("sess-1", STORE_ID, CUSTOMER_ID)
    tampered = token[:-4] + "abcd"
    from app.core.exceptions import AuthError
    with pytest.raises(AuthError):
        qr_service.decode_qr_pass(tampered)


# ---------------------------------------------------------------------
# End-to-end checkout flow
# ---------------------------------------------------------------------

@pytest.fixture
def fake_client(monkeypatch):
    client = FakeServiceClient()
    client.seed(
        "stores",
        [{"id": STORE_ID, "name": "Fresh Mart", "is_active": True, "store_type": "grocery",
          "retailer_id": RETAILER_ID, "latitude": 12.97, "longitude": 77.59, "rating": 4.5,
          "image_url": None, "address_line": "MG Road", "city": "Bengaluru",
          "opening_time": "09:00", "closing_time": "22:00"}],
    )
    client.seed(
        "products",
        [{"id": PRODUCT_ID, "store_id": STORE_ID, "barcode": "8901030123", "name": "Basmati Rice 1kg",
          "brand": "India Gate", "mrp_paise": 15000, "discount_percent": 10.0, "price_paise": 13500,
          "gst_percent": 5.0, "stock_quantity": 20, "is_active": True, "image_url": None,
          "description": None, "weight_value": 1.0, "weight_unit": "kg",
          "manufacture_date": None, "expiry_date": None}],
    )
    client.seed("customers", [{"id": CUSTOMER_ID, "full_name": "Asha Kumar"}])

    for module in ("session_service", "cart_service", "product_service", "checkout_service",
                   "invoice_service", "exit_service", "notification_service"):
        monkeypatch.setattr(f"app.services.{module}.get_service_client", lambda: client)

    monkeypatch.setattr(
        "app.services.payment_service.create_order",
        lambda amount_paise, receipt: {"id": "order_test123"},
    )
    return client


def test_full_checkout_flow_confirms_and_generates_pass(fake_client):
    from app.services import cart_service
    session = session_service.create_session(CUSTOMER_ID, STORE_ID)
    cart_service.add_item(session.id, CUSTOMER_ID, PRODUCT_ID, quantity=2)

    init = checkout_service.init_checkout(session.id, CUSTOMER_ID)
    assert init.razorpay_order_id == "order_test123"
    assert init.amount_paise > 0

    from app.core.config import settings
    signature = _sign(init.razorpay_order_id, "pay_success_1", settings.razorpay_key_secret)
    confirm = checkout_service.confirm_checkout(
        session.id,
        CUSTOMER_ID,
        PaymentConfirmRequest(
            razorpay_order_id=init.razorpay_order_id,
            razorpay_payment_id="pay_success_1",
            razorpay_signature=signature,
        ),
    )

    assert confirm.payment_status == "success"
    assert confirm.invoice.total_paise == init.amount_paise
    assert confirm.qr_pass_token
    assert confirm.qr_code_image_base64  # non-empty base64 PNG


def test_confirm_checkout_rejects_forged_signature(fake_client):
    from app.services import cart_service
    session = session_service.create_session(CUSTOMER_ID, STORE_ID)
    cart_service.add_item(session.id, CUSTOMER_ID, PRODUCT_ID, quantity=1)
    init = checkout_service.init_checkout(session.id, CUSTOMER_ID)

    with pytest.raises(ValidationFailedError):
        checkout_service.confirm_checkout(
            session.id,
            CUSTOMER_ID,
            PaymentConfirmRequest(
                razorpay_order_id=init.razorpay_order_id,
                razorpay_payment_id="pay_fake",
                razorpay_signature="totally-forged",
            ),
        )


def test_exit_scan_closes_session_and_rejects_wrong_retailer(fake_client):
    from app.services import cart_service
    session = session_service.create_session(CUSTOMER_ID, STORE_ID)
    cart_service.add_item(session.id, CUSTOMER_ID, PRODUCT_ID, quantity=1)
    init = checkout_service.init_checkout(session.id, CUSTOMER_ID)

    from app.core.config import settings
    signature = _sign(init.razorpay_order_id, "pay_ok", settings.razorpay_key_secret)
    confirm = checkout_service.confirm_checkout(
        session.id, CUSTOMER_ID,
        PaymentConfirmRequest(
            razorpay_order_id=init.razorpay_order_id, razorpay_payment_id="pay_ok", razorpay_signature=signature
        ),
    )

    # Wrong retailer must be rejected
    with pytest.raises(ForbiddenError):
        exit_service.scan_exit(confirm.qr_pass_token, retailer_id="someone-elses-store")

    # Correct retailer succeeds and closes the session
    result = exit_service.scan_exit(confirm.qr_pass_token, retailer_id=RETAILER_ID)
    assert result.session_id == session.id
    assert result.customer_name == "Asha Kumar"

    # Replay must be rejected
    with pytest.raises(ValidationFailedError):
        exit_service.scan_exit(confirm.qr_pass_token, retailer_id=RETAILER_ID)


def test_checkout_rejects_empty_cart(fake_client):
    session = session_service.create_session(CUSTOMER_ID, STORE_ID)
    with pytest.raises(ValidationFailedError):
        checkout_service.init_checkout(session.id, CUSTOMER_ID)
