"""
Request/response models for authentication endpoints.

Kept separate for customer vs retailer signup (rather than one shared model with
optional fields) because the two roles genuinely have different required fields
(business_name/gstin vs full_name) and separate models make invalid combinations
unrepresentable rather than merely disallowed by extra validation logic.
"""
from pydantic import BaseModel, EmailStr, Field


class CustomerSignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=120)
    phone: str | None = Field(default=None, max_length=20)


class RetailerSignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    business_name: str = Field(min_length=1, max_length=160)
    phone: str | None = Field(default=None, max_length=20)
    gstin: str | None = Field(default=None, max_length=20)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class CustomerProfileResponse(BaseModel):
    id: str
    email: str | None
    full_name: str
    phone: str | None


class RetailerProfileResponse(BaseModel):
    id: str
    email: str | None
    business_name: str
    phone: str | None
    verified: bool


class AuthSuccessResponse(BaseModel):
    """
    Returned by signup/login — bundles the session token with the role-specific profile.

    `token` is null on signup only when the Supabase project has email
    confirmation enabled: Supabase Auth then returns no session until the
    user clicks the verification link, so the client should show a
    "check your email" screen rather than treating this as an error.
    """
    token: TokenResponse | None
    role: str  # "customer" | "retailer"
    profile: CustomerProfileResponse | RetailerProfileResponse
