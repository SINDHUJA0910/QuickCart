"""
Notification service.

Creating a row here is the entire "send" operation — Supabase Realtime
(enabled on this table via migration 0004) handles delivery to any
subscribed client automatically via Postgres logical replication. There is
no separate push/websocket code in this backend; that's the point of using
Supabase Realtime instead of hand-rolling one.
"""
from app.core.exceptions import ForbiddenError, NotFoundError
from app.db.supabase_client import get_service_client
from app.schemas.notification import NotificationResponse
from app.utils.time import utcnow_iso


def create_notification(
    recipient_type: str,  # "customer" | "retailer"
    recipient_id: str,
    title: str,
    category: str,
    body: str | None = None,
    related_id: str | None = None,
) -> None:
    service = get_service_client()
    service.table("notifications").insert(
        {
            "recipient_type": recipient_type,
            "recipient_id": recipient_id,
            "title": title,
            "body": body,
            "category": category,
            "related_id": related_id,
        }
    ).execute()


def list_notifications(recipient_id: str, unread_only: bool = False) -> list[NotificationResponse]:
    service = get_service_client()
    query = service.table("notifications").select("*").eq("recipient_id", recipient_id)
    if unread_only:
        query = query.is_("read_at", "null")
    result = query.execute()

    rows = sorted(result.data or [], key=lambda r: r["created_at"], reverse=True)
    return [_to_response(row) for row in rows]


def mark_read(notification_id: str, recipient_id: str) -> NotificationResponse:
    service = get_service_client()
    existing = service.table("notifications").select("*").eq("id", notification_id).execute()
    if not existing.data:
        raise NotFoundError("Notification not found")
    if existing.data[0]["recipient_id"] != recipient_id:
        raise ForbiddenError("This notification does not belong to you")

    service.table("notifications").update({"read_at": utcnow_iso()}).eq("id", notification_id).execute()
    result = service.table("notifications").select("*").eq("id", notification_id).execute()
    return _to_response(result.data[0])


def _to_response(row: dict) -> NotificationResponse:
    return NotificationResponse(
        id=row["id"],
        title=row["title"],
        body=row.get("body"),
        category=row["category"],
        related_id=row.get("related_id"),
        read=row.get("read_at") is not None,
        created_at=row["created_at"],
    )
