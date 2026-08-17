"""
Retailer authentication routes. Mirrors auth_customer.py's structure exactly —
see that file's module docstring for the rationale on keeping these separate.
"""
from fastapi import APIRouter, Depends, Request, status

from app.api.v1.deps import get_current_retailer
from app.core.exceptions import AuthError
from app.core.rate_limit import limiter
from app.core.security import AuthenticatedUser, decode_access_token
from app.schemas.auth import (
    AuthSuccessResponse,
    ForgotPasswordRequest,
    LoginRequest,
    RetailerProfileResponse,
    RetailerSignupRequest,
)
from app.services import auth_service

router = APIRouter(prefix="/auth/retailer", tags=["Retailer Auth"])


@router.post(
    "/signup",
    response_model=AuthSuccessResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new retailer account",
)
@limiter.limit("5/minute")
def retailer_signup(request: Request, payload: RetailerSignupRequest) -> AuthSuccessResponse:
    token, profile = auth_service.signup_retailer(payload)
    return AuthSuccessResponse(token=token, role="retailer", profile=profile)


@router.post(
    "/login",
    response_model=AuthSuccessResponse,
    summary="Log in as a retailer",
)
@limiter.limit("10/minute")
def retailer_login(request: Request, payload: LoginRequest) -> AuthSuccessResponse:
    token = auth_service.login(payload)

    user = decode_access_token(token.access_token)
    if auth_service.resolve_role(user.id) != "retailer":
        raise AuthError("This account is not registered as a retailer")

    profile = auth_service.get_retailer_profile(user.id)
    return AuthSuccessResponse(token=token, role="retailer", profile=profile)


@router.get(
    "/me",
    response_model=RetailerProfileResponse,
    summary="Get the logged-in retailer's profile",
)
def retailer_me(user: AuthenticatedUser = Depends(get_current_retailer)) -> RetailerProfileResponse:
    return auth_service.get_retailer_profile(user.id)


@router.post(
    "/forgot-password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Send a password reset email",
)
@limiter.limit("3/minute")
def retailer_forgot_password(request: Request, payload: ForgotPasswordRequest) -> None:
    auth_service.send_password_reset(payload.email)
