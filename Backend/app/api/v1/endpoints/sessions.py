"""Shopping session lifecycle — customer Step 2 (select store -> create session)."""
from fastapi import APIRouter, Depends, status

from app.api.v1.deps import get_current_customer
from app.core.exceptions import NotFoundError
from app.core.security import AuthenticatedUser
from app.schemas.session import SessionCreateRequest, SessionResponse
from app.services import session_service

router = APIRouter(prefix="/sessions", tags=["Shopping Sessions"])


@router.post(
    "",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start a new shopping session at a store",
    description="Fails with 409 if the customer already has an active session anywhere.",
)
def create_session(
    payload: SessionCreateRequest,
    user: AuthenticatedUser = Depends(get_current_customer),
) -> SessionResponse:
    return session_service.create_session(customer_id=user.id, store_id=payload.store_id)


@router.get(
    "/active",
    response_model=SessionResponse,
    summary="Get the customer's current active session, if any",
)
def get_active_session(user: AuthenticatedUser = Depends(get_current_customer)) -> SessionResponse:
    session = session_service.get_active_session(customer_id=user.id)
    if session is None:
        raise NotFoundError("No active shopping session")
    return session
