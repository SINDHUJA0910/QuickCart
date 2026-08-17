"""AI alert persistence and retailer-facing management."""
from app.core.exceptions import NotFoundError
from app.db.supabase_client import get_service_client
from app.schemas.ai_alert import AIAlertResponse
from app.services import notification_service
from app.services.store_ownership import verify_store_ownership
from app.utils.time import utcnow_iso


def create_alert(
    store_id: str,
    reason: str,
    severity: str,
    session_id: str | None = None,
    camera_id: str | None = None,
    confidence_score: float | None = None,
) -> AIAlertResponse:
    service = get_service_client()
    result = (
        service.table("ai_alerts")
        .insert(
            {
                "store_id": store_id,
                "session_id": session_id,
                "camera_id": camera_id,
                "severity": severity,
                "reason": reason,
                "confidence_score": confidence_score,
            }
        )
        .execute()
    )
    alert = _to_response(result.data[0])

    store = service.table("stores").select("retailer_id").eq("id", store_id).execute()
    if store.data:
        notification_service.create_notification(
            recipient_type="retailer",
            recipient_id=store.data[0]["retailer_id"],
            title=f"{severity.upper()} theft alert: {reason.replace('_', ' ')}",
            category="ai_alert",
            related_id=alert.id,
        )

    return alert


def list_alerts(store_id: str, retailer_id: str, status: str | None = None) -> list[AIAlertResponse]:
    service = get_service_client()
    verify_store_ownership(store_id, retailer_id)

    query = service.table("ai_alerts").select("*").eq("store_id", store_id)
    if status:
        query = query.eq("status", status)
    result = query.execute()
    return [_to_response(row) for row in (result.data or [])]


def resolve_alert(store_id: str, alert_id: str, retailer_id: str, new_status: str) -> AIAlertResponse:
    """new_status must be 'resolved' or 'false_positive'."""
    service = get_service_client()
    verify_store_ownership(store_id, retailer_id)

    existing = service.table("ai_alerts").select("*").eq("id", alert_id).eq("store_id", store_id).execute()
    if not existing.data:
        raise NotFoundError("Alert not found")

    service.table("ai_alerts").update(
        {"status": new_status, "resolved_at": utcnow_iso(), "resolved_by": retailer_id}
    ).eq("id", alert_id).execute()

    result = service.table("ai_alerts").select("*").eq("id", alert_id).execute()
    return _to_response(result.data[0])


def _to_response(row: dict) -> AIAlertResponse:
    return AIAlertResponse(
        id=row["id"],
        session_id=row.get("session_id"),
        camera_id=row.get("camera_id"),
        severity=row["severity"],
        status=row["status"],
        reason=row["reason"],
        confidence_score=row.get("confidence_score"),
        detected_at=row["detected_at"],
    )
