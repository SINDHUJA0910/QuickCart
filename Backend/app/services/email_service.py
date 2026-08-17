"""
Invoice email delivery via SMTP.

Provider-agnostic on purpose: any transactional email provider (SendGrid,
Resend, Postmark, Amazon SES) exposes an SMTP endpoint, so this needs no
provider-specific SDK — just host/port/credentials in settings. If
SMTP_HOST isn't configured, sending is a silent no-op (logged, not
raised) so checkout never fails because email delivery isn't set up yet in
a given environment — matches invoice PDF upload's own fail-open pattern
in invoice_service.py.
"""
import logging
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings

logger = logging.getLogger("quickcart")


def send_invoice_email(
    to_email: str,
    customer_name: str,
    store_name: str,
    invoice_number: str,
    total_paise: int,
    pdf_bytes: bytes | None = None,
) -> bool:
    """Returns True if the email was sent, False if skipped or failed —
    callers should log/notify on False but never treat it as fatal to checkout."""
    if not settings.smtp_host:
        logger.info("SMTP not configured — skipping invoice email for %s", invoice_number)
        return False

    total_rupees = total_paise / 100

    message = MIMEMultipart()
    message["Subject"] = f"Your QuickCart receipt — {invoice_number}"
    message["From"] = f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
    message["To"] = to_email

    body = (
        f"Hi {customer_name},\n\n"
        f"Thanks for shopping at {store_name}.\n\n"
        f"Invoice: {invoice_number}\n"
        f"Total paid: Rs. {total_rupees:,.2f}\n\n"
        f"Your invoice PDF is attached.\n\n"
        f"— QuickCart"
    )
    message.attach(MIMEText(body, "plain"))

    if pdf_bytes:
        attachment = MIMEApplication(pdf_bytes, _subtype="pdf")
        attachment.add_header("Content-Disposition", "attachment", filename=f"{invoice_number}.pdf")
        message.attach(attachment)

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
            server.starttls()
            if settings.smtp_username:
                server.login(settings.smtp_username, settings.smtp_password)
            server.sendmail(settings.smtp_from_email, [to_email], message.as_string())
        return True
    except Exception:
        logger.exception("Failed to send invoice email for %s to %s", invoice_number, to_email)
        return False
