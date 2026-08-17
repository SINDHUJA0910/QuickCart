"""
QR exit pass.

The QR code does not simply encode the session id in plaintext — anyone who
photographs someone else's QR could then replay it. Instead the payload is
encrypted with Fernet (AES-128-CBC + HMAC, from the `cryptography` package),
keyed by QR_ENCRYPTION_KEY, so:
  - it cannot be read or forged without the server's key,
  - Fernet's built-in HMAC means any tampering (e.g. trying to edit the
    embedded expiry) invalidates the token entirely rather than silently
    corrupting one field,
  - Fernet's TTL support (`decrypt(token, ttl=...)`) gives us expiry
    enforcement for free rather than trusting a timestamp field embedded in
    the plaintext.
"""
import base64
import json
from datetime import datetime, timedelta, timezone
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings
from app.core.exceptions import AuthError

QR_PASS_VALIDITY_SECONDS = 30 * 60  # 30 minutes to walk to the exit and get scanned


@lru_cache
def _fernet() -> Fernet:
    # QR_ENCRYPTION_KEY must be a urlsafe-base64-encoded 32-byte key, as produced
    # by `Fernet.generate_key()`. Generating and storing one is a deployment-time
    # step documented in deployment/README.md (Phase 8).
    return Fernet(settings.qr_encryption_key.encode())


def generate_qr_pass(session_id: str, store_id: str, customer_id: str) -> tuple[str, str]:
    """Returns (encrypted_token, iso_expiry_timestamp)."""
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=QR_PASS_VALIDITY_SECONDS)

    payload = {
        "session_id": session_id,
        "store_id": store_id,
        "customer_id": customer_id,
        "payment_status": "success",
        "issued_at": now.isoformat(),
    }
    token = _fernet().encrypt(json.dumps(payload).encode()).decode()
    return token, expires_at.isoformat()


def decode_qr_pass(token: str) -> dict:
    """Decrypts and validates a QR pass token. Raises AuthError on any
    invalid, tampered, or expired token."""
    try:
        raw = _fernet().decrypt(token.encode(), ttl=QR_PASS_VALIDITY_SECONDS)
    except InvalidToken as exc:
        raise AuthError("This exit pass is invalid or has expired") from exc

    return json.loads(raw.decode())


def qr_image_base64(token: str) -> str:
    """Renders the token as a PNG QR code, base64-encoded for direct embedding
    in a JSON response (`<img src="data:image/png;base64,...">` on the frontend)."""
    import io

    import qrcode

    img = qrcode.make(token)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()
