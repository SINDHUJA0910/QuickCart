"""
Exit validation — spec Step 9 (retailer scans QR, session closes, customer exits).

Deliberately checks that the scanning retailer actually owns the store the
QR pass was issued for. Without this check, a QR pass valid at Store A could
be replayed at Store B if the two happened to share a customer/session id
namespace — an easy mistake to miss since both are legitimate retailers,
just not the *right* one for this pass.
"""
from app.core.exceptions import ForbiddenError, ValidationFailedError
from app.db.supabase_client import get_service_client
from app.schemas.checkout import ExitScanResponse
from app.services import qr_service
from app.utils.time import utcnow_iso


def scan_exit(qr_token: str, retailer_id: str) -> ExitScanResponse:
    service = get_service_client()
    payload = qr_service.decode_qr_pass(qr_token)

    store = service.table("stores").select("id, name, retailer_id").eq("id", payload["store_id"]).execute()
    if not store.data:
        raise ValidationFailedError("Store on this pass no longer exists")
    if store.data[0]["retailer_id"] != retailer_id:
        raise ForbiddenError("This exit pass was not issued for your store")

    session = (
        service.table("shopping_sessions").select("*").eq("id", payload["session_id"]).execute()
    )
    if not session.data:
        raise ValidationFailedError("Session not found")
    session_row = session.data[0]

    if session_row["payment_status"] != "success":
        service.table("shopping_sessions").update({"exit_status": "blocked"}).eq(
            "id", session_row["id"]
        ).execute()
        raise ValidationFailedError("Payment not completed — exit blocked")

    if session_row["exit_status"] == "exited":
        raise ValidationFailedError("This exit pass has already been used")

    service.table("shopping_sessions").update(
        {"status": "checked_out", "exit_status": "exited", "exit_time": utcnow_iso()}
    ).eq("id", session_row["id"]).execute()

    customer = service.table("customers").select("full_name").eq("id", payload["customer_id"]).execute()
    customer_name = customer.data[0]["full_name"] if customer.data else ""

    invoice = service.table("invoices").select("total_paise").eq("session_id", session_row["id"]).execute()
    total_paise = invoice.data[0]["total_paise"] if invoice.data else 0

    return ExitScanResponse(
        session_id=session_row["id"],
        customer_name=customer_name,
        store_name=store.data[0]["name"],
        total_paise=total_paise,
        exit_time=utcnow_iso(),
    )
