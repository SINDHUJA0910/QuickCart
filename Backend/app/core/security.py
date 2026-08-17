"""
Verification of Supabase-issued JWTs.

QuickCart never issues its own auth tokens and never stores or checks passwords —
Supabase Auth owns the credential lifecycle end-to-end (signup, login, password
reset, email verification). This module's only job is to verify the access token
a client sends us on every request and extract the authenticated user's id/email.

Supabase signs access tokens with HS256 using the project's JWT secret
(Project Settings -> API -> JWT Secret), and sets `aud: "authenticated"` for
logged-in users. We verify signature, expiry, and audience on every call.
"""
from dataclasses import dataclass

from jose import JWTError, jwt

from app.core.config import settings
from app.core.exceptions import AuthError

ALGORITHM = "HS256"
EXPECTED_AUDIENCE = "authenticated"


@dataclass(frozen=True)
class AuthenticatedUser:
    """Minimal identity extracted from a verified Supabase JWT."""
    id: str          # matches auth.users.id / customers.id / retailers.id
    email: str | None
    role_claim: str | None  # Supabase's own 'role' claim (usually 'authenticated'); NOT the QuickCart business role


def decode_access_token(token: str) -> AuthenticatedUser:
    """
    Verify a Supabase access token and return the authenticated identity.

    Raises AuthError (-> 401) on any invalid, expired, or malformed token so
    callers never need to inspect jose exceptions directly.
    """
    try:
        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=[ALGORITHM],
            audience=EXPECTED_AUDIENCE,
        )
    except JWTError as exc:
        raise AuthError("Invalid or expired authentication token") from exc

    subject = payload.get("sub")
    if not subject:
        raise AuthError("Token missing subject claim")

    return AuthenticatedUser(
        id=subject,
        email=payload.get("email"),
        role_claim=payload.get("role"),
    )
