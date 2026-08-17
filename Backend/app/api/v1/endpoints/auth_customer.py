"""
Customer authentication routes.

Kept in a separate router from retailer auth (rather than one shared
`/auth/signup?role=customer` endpoint) so each route's request/response schema
is unambiguous in the OpenAPI docs, and so a customer-only rate limit or
abuse rule can be attached to this router independently in Phase 8.
"""
from fastapi import APIRouter, Depends, Request, status

from app.api.v1.deps import get_current_customer
from app.core.exceptions import AuthError
from app.core.rate_limit import limiter
from app.core.security import AuthenticatedUser, decode_access_token
from app.schemas.auth import (
    AuthSuccessResponse,
    CustomerProfileResponse,
    CustomerSignupRequest,
    ForgotPasswordRequest,
    LoginRequest,
)
from app.services import auth_service

router = APIRouter(prefix="/auth/customer", tags=["Customer Auth"])


@router.post(
    "/signup",
    response_model=AuthSuccessResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new customer account",
    description=(
        "Creates a Supabase Auth user and a matching customer profile. "
        "If email confirmation is enabled on the Supabase project, `token` "
        "will be null and the client should prompt the user to verify their "
        "email before logging in."
    ),
)
@limiter.limit("5/minute")
def customer_signup(request: Request, payload: CustomerSignupRequest) -> AuthSuccessResponse:
    token, profile = auth_service.signup_customer(payload)
    return AuthSuccessResponse(token=token, role="customer", profile=profile)


@router.post(
    "/login",
    response_model=AuthSuccessResponse,
    summary="Log in as a customer",
)
@limiter.limit("10/minute")
def customer_login(request: Request, payload: LoginRequest) -> AuthSuccessResponse:
    token = auth_service.login(payload)

    # decode the fresh token to get the user id, then confirm this identity
    # actually owns a customer profile — a retailer's credentials should
    # never succeed against the customer login route.
    user = decode_access_token(token.access_token)
    if auth_service.resolve_role(user.id) != "customer":
        raise AuthError("This account is not registered as a customer")

    profile = auth_service.get_customer_profile(user.id)
    return AuthSuccessResponse(token=token, role="customer", profile=profile)


@router.get(
    "/me",
    response_model=CustomerProfileResponse,
    summary="Get the logged-in customer's profile",
)
def customer_me(user: AuthenticatedUser = Depends(get_current_customer)) -> CustomerProfileResponse:
    return auth_service.get_customer_profile(user.id)


@router.post(
    "/forgot-password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Send a password reset email",
)
@limiter.limit("3/minute")
def customer_forgot_password(request: Request, payload: ForgotPasswordRequest) -> None:
    auth_service.send_password_reset(payload.email)
