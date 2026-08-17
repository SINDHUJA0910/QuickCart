"""
Notification feed — shared by both customer and retailer, since both roles
receive notifications (payment confirmations, low stock, AI alerts). Uses
the role-agnostic `get_current_user` dependency rather than
`get_current_customer`/`get_current_retailer`, since a notification's
ownership is determined by `recipient_id = auth.uid()` regardless of which
role that identity has — the same pattern RLS uses on this table.
"""
from fastapi import APIRouter, Depends, Query

from app.api.v1.deps import get_current_user
from app.core.security import AuthenticatedUser
from app.schemas.notification import NotificationResponse
from app.services import notification_service

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("", response_model=list[NotificationResponse])
def list_notifications(
    unread_only: bool = Query(default=False),
    user: AuthenticatedUser = Depends(get_current_user),
) -> list[NotificationResponse]:
    return notification_service.list_notifications(recipient_id=user.id, unread_only=unread_only)


@router.post("/{notification_id}/read", response_model=NotificationResponse)
def mark_read(
    notification_id: str, user: AuthenticatedUser = Depends(get_current_user)
) -> NotificationResponse:
    return notification_service.mark_read(notification_id=notification_id, recipient_id=user.id)
