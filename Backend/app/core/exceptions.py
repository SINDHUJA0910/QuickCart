"""
Domain-level exceptions, mapped to HTTP responses in main.py's exception handlers.

Rationale: services and dependencies raise these instead of HTTPException directly,
so business logic stays framework-agnostic and is easier to unit test without
spinning up FastAPI's request/response cycle.
"""


class QuickCartError(Exception):
    """Base class for all QuickCart domain errors."""
    status_code: int = 500
    default_message: str = "Something went wrong"

    def __init__(self, message: str | None = None):
        super().__init__(message or self.default_message)
        self.message = message or self.default_message


class AuthError(QuickCartError):
    """Invalid credentials, invalid/expired token, missing auth header."""
    status_code = 401
    default_message = "Authentication failed"


class ForbiddenError(QuickCartError):
    """Authenticated, but not permitted to perform this action (wrong role, wrong store, etc.)."""
    status_code = 403
    default_message = "You do not have permission to perform this action"


class NotFoundError(QuickCartError):
    status_code = 404
    default_message = "Resource not found"


class ConflictError(QuickCartError):
    """e.g. duplicate email/phone on signup."""
    status_code = 409
    default_message = "Resource already exists"


class ValidationFailedError(QuickCartError):
    status_code = 422
    default_message = "Validation failed"
