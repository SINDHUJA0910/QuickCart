"""
Invoice generation.

Produces a real PDF (via ReportLab, not a stub) and uploads it to a Supabase
Storage bucket named "invoices". The upload step is isolated in
`_upload_pdf` specifically so tests can patch it without needing a real
Supabase project — everything upstream of it (invoice numbering, totals,
PDF byte generation) is tested against real ReportLab output.
"""
import io
from datetime import datetime, timezone

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

from app.db.supabase_client import get_service_client
from app.schemas.cart import CartSummaryResponse
from app.schemas.checkout import InvoiceResponse
from app.services import email_service


def _generate_invoice_number(session_id: str) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"QC-{timestamp}-{session_id[:8].upper()}"


def _paise_to_rupees_str(paise: int) -> str:
    return f"Rs. {paise / 100:,.2f}"


def _render_pdf(invoice_number: str, store_name: str, cart: CartSummaryResponse) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=20 * mm, bottomMargin=20 * mm)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph(f"<b>{store_name}</b>", styles["Title"]))
    elements.append(Paragraph(f"Invoice: {invoice_number}", styles["Normal"]))
    elements.append(
        Paragraph(f"Date: {datetime.now(timezone.utc).strftime('%d %b %Y, %H:%M UTC')}", styles["Normal"])
    )
    elements.append(Spacer(1, 10 * mm))

    table_data = [["Item", "Qty", "Unit Price", "Line Total"]]
    for item in cart.items:
        table_data.append(
            [
                item.product_name,
                str(item.quantity),
                _paise_to_rupees_str(item.unit_price_paise),
                _paise_to_rupees_str(item.line_total_paise),
            ]
        )

    table = Table(table_data, colWidths=[80 * mm, 20 * mm, 35 * mm, 35 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ]
        )
    )
    elements.append(table)
    elements.append(Spacer(1, 8 * mm))

    summary_data = [
        ["Subtotal", _paise_to_rupees_str(cart.subtotal_paise)],
        ["Discount", f"-{_paise_to_rupees_str(cart.discount_paise)}"],
        ["GST", _paise_to_rupees_str(cart.gst_paise)],
        ["Total", _paise_to_rupees_str(cart.total_paise)],
    ]
    summary_table = Table(summary_data, colWidths=[135 * mm, 35 * mm])
    summary_table.setStyle(
        TableStyle(
            [
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("LINEABOVE", (0, -1), (-1, -1), 1, colors.black),
            ]
        )
    )
    elements.append(summary_table)

    doc.build(elements)
    return buffer.getvalue()


def _upload_pdf(pdf_bytes: bytes, invoice_number: str) -> str | None:
    """Uploads to the 'invoices' Supabase Storage bucket. Returns the storage
    path, or None if upload fails — invoice generation should not hard-fail
    checkout just because storage is briefly unavailable; the PDF can be
    regenerated on demand from the invoice row's stored totals."""
    service = get_service_client()
    path = f"{invoice_number}.pdf"
    try:
        service.storage.from_("invoices").upload(
            path, pdf_bytes, {"content-type": "application/pdf"}
        )
        return path
    except Exception:
        return None


def generate_invoice(
    session_id: str,
    store_name: str,
    cart: CartSummaryResponse,
    customer_email: str | None = None,
    customer_name: str | None = None,
) -> InvoiceResponse:
    service = get_service_client()
    invoice_number = _generate_invoice_number(session_id)

    pdf_bytes = _render_pdf(invoice_number, store_name, cart)
    pdf_path = _upload_pdf(pdf_bytes, invoice_number)

    service.table("invoices").insert(
        {
            "session_id": session_id,
            "invoice_number": invoice_number,
            "subtotal_paise": cart.subtotal_paise,
            "discount_paise": cart.discount_paise,
            "gst_paise": cart.gst_paise,
            "total_paise": cart.total_paise,
            "pdf_storage_path": pdf_path,
        }
    ).execute()

    pdf_url = None
    if pdf_path:
        pdf_url = service.storage.from_("invoices").get_public_url(pdf_path)

    emailed = False
    if customer_email:
        emailed = email_service.send_invoice_email(
            to_email=customer_email,
            customer_name=customer_name or "there",
            store_name=store_name,
            invoice_number=invoice_number,
            total_paise=cart.total_paise,
            pdf_bytes=pdf_bytes,
        )
    if emailed:
        service.table("invoices").update({"emailed": True}).eq("invoice_number", invoice_number).execute()

    return InvoiceResponse(
        invoice_number=invoice_number,
        subtotal_paise=cart.subtotal_paise,
        discount_paise=cart.discount_paise,
        gst_paise=cart.gst_paise,
        total_paise=cart.total_paise,
        pdf_url=pdf_url,
    )
