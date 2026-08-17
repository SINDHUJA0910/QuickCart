"""
Auth service — orchestrates Supabase Auth (credentials) with QuickCart's own
profile tables (customers / retailers).

Every signup is a two-step operation:
  1. Supabase Auth creates the auth.users row (handles password hashing,
     sends the verification email, etc). This is the only place a password
     is ever handled, and it never touches our database directly.
  2. We create the matching profile row (customers or retailers) using the
     service-role client, since RLS on those tables only allows a row's own
     owner to read/update it — but at signup time no session exists yet to
     satisfy that policy, so the backend does this step as a trusted actor.

If step 2 fails after step 1 succeeds, we surface a clear error rather than
silently leaving an orphaned auth.users row with no profile — the signup
endpoints below catch this and return a 500 with guidance to retry, since
Supabase Auth signup is idempotent per-email (a retry with the same email
will not create a duplicate auth user; it will error, which we resolve by
allowing an admin/ops path to backfill the missing profile in Phase 8's
ops tooling).
"""
# NOTE: `gotrue` is the auth-error module bundled with supabase-py==2.9.0 (pinned
# in requirements.txt). A future supabase-py upgrade renames this to
# `supabase_auth.errors` — update this import when bumping that dependency.
from gotrue.errors import AuthApiError
from postgrest.exceptions import APIError

from app.core.exceptions import AuthError, ConflictError, ValidationFailedError
from app.db.supabase_client import get_anon_client, get_service_client
from app.schemas.auth import (
    CustomerSignupRequest,
    RetailerSignupRequest,
    LoginRequest,
    TokenResponse,
    CustomerProfileResponse,
    RetailerProfileResponse,
)


def _token_from_session(session) -> TokenResponse:
    return TokenResponse(
        access_token=session.access_token,
        refresh_token=session.refresh_token,
        expires_in=session.expires_in,
    )


def signup_customer(payload: CustomerSignupRequest) -> tuple[TokenResponse, CustomerProfileResponse]:
    anon = get_anon_client()
    service = get_service_client()

    try:
        auth_response = anon.auth.sign_up(
            {"email": payload.email, "password": payload.password}
        )
    except AuthApiError as exc:
        if "already registered" in str(exc).lower() or "already exists" in str(exc).lower():
            raise ConflictError("An account with this email already exists") from exc
        raise ValidationFailedError(str(exc)) from exc

    user = auth_response.user
    session = auth_response.session
    if user is None:
        raise ValidationFailedError("Signup failed — no user returned by Supabase Auth")

    try:
        service.table("customers").insert(
            {
                "id": user.id,
                "full_name": payload.full_name,
                "phone": payload.phone,
            }
        ).execute()
    except APIError as exc:
        raise ConflictError(f"Could not create customer profile: {exc.message}") from exc

    profile = CustomerProfileResponse(
        id=user.id, email=user.email, full_name=payload.full_name, phone=payload.phone
    )

    # If email confirmation is required, Supabase returns no session yet.
    if session is None:
        return None, profile
    return _token_from_session(session), profile


def signup_retailer(payload: RetailerSignupRequest) -> tuple[TokenResponse | None, RetailerProfileResponse]:
    anon = get_anon_client()
    service = get_service_client()

    try:
        auth_response = anon.auth.sign_up(
            {"email": payload.email, "password": payload.password}
        )
    except AuthApiError as exc:
        if "already registered" in str(exc).lower() or "already exists" in str(exc).lower():
            raise ConflictError("An account with this email already exists") from exc
        raise ValidationFailedError(str(exc)) from exc

    user = auth_response.user
    session = auth_response.session
    if user is None:
        raise ValidationFailedError("Signup failed — no user returned by Supabase Auth")

    try:
        service.table("retailers").insert(
            {
                "id": user.id,
                "business_name": payload.business_name,
                "phone": payload.phone,
                "gstin": payload.gstin,
            }
        ).execute()
    except APIError as exc:
        raise ConflictError(f"Could not create retailer profile: {exc.message}") from exc

    profile = RetailerProfileResponse(
        id=user.id,
        email=user.email,
        business_name=payload.business_name,
        phone=payload.phone,
        verified=False,
    )

    if session is None:
        return None, profile
    return _token_from_session(session), profile


def login(payload: LoginRequest) -> TokenResponse:
    """
    Role-agnostic login. QuickCart deliberately does not ask "customer or
    retailer" at login time — the caller resolves which role owns this
    identity afterward via `resolve_role(user_id)`, since the same email
    could theoretically only ever belong to one role's profile table
    (enforced at the application level during signup, not at the DB level,
    since auth.users itself has no notion of QuickCart's roles).
    """
    anon = get_anon_client()
    try:
        auth_response = anon.auth.sign_in_with_password(
            {"email": payload.email, "password": payload.password}
        )
    except AuthApiError as exc:
        raise AuthError("Invalid email or password") from exc

    if auth_response.session is None:
        raise AuthError("Login failed — no session returned")

    return _token_from_session(auth_response.session)


def resolve_role(user_id: str) -> str:
    """Determine whether a logged-in user is a customer or retailer by profile existence."""
    service = get_service_client()

    customer = service.table("customers").select("id").eq("id", user_id).execute()
    if customer.data:
        return "customer"

    retailer = service.table("retailers").select("id").eq("id", user_id).execute()
    if retailer.data:
        return "retailer"

    raise AuthError("No QuickCart profile found for this account")


def get_customer_profile(user_id: str) -> CustomerProfileResponse:
    service = get_service_client()
    result = service.table("customers").select("*").eq("id", user_id).single().execute()
    row = result.data
    return CustomerProfileResponse(
        id=row["id"], email=None, full_name=row["full_name"], phone=row.get("phone")
    )


def get_retailer_profile(user_id: str) -> RetailerProfileResponse:
    service = get_service_client()
    result = service.table("retailers").select("*").eq("id", user_id).single().execute()
    row = result.data
    return RetailerProfileResponse(
        id=row["id"],
        email=None,
        business_name=row["business_name"],
        phone=row.get("phone"),
        verified=row.get("verified", False),
    )


def send_password_reset(email: str) -> None:
    anon = get_anon_client()
    anon.auth.reset_password_for_email(email)
