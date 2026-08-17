"""
FastAPI dependencies enforcing authentication and role-based access.

Design: `get_current_user` only proves "this is a validly-signed Supabase token."
`get_current_customer` / `get_current_retailer` additionally prove "and this
identity owns a profile of the required role" — a retailer's token can never
satisfy a customer-only route, and vice versa, regardless of what the frontend
sends. This is enforced server-side on every request, independent of RLS
(which protects direct Supabase access) and independent of the frontend
(which could be bypassed entirely).
"""
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.exceptions import ForbiddenError
from app.core.security import AuthenticatedUser, decode_access_token
from app.services import auth_service

_bearer_scheme = HTTPBearer(auto_error=True)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> AuthenticatedUser:
    """Verifies the bearer token and returns the authenticated identity. No role check."""
    return decode_access_token(credentials.credentials)


def get_current_customer(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
    role = auth_service.resolve_role(user.id)
    if role != "customer":
        raise ForbiddenError("This action is restricted to customer accounts")
    return user


def get_current_retailer(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
    role = auth_service.resolve_role(user.id)
    if role != "retailer":
        raise ForbiddenError("This action is restricted to retailer accounts")
    return user
