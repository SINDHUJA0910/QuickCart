"""Retailer AI theft-alert management."""
from fastapi import APIRouter, Depends, Query

from app.api.v1.deps import get_current_retailer
from app.core.security import AuthenticatedUser
from app.schemas.ai_alert import AIAlertResponse, AlertResolveRequest
from app.services import ai_alert_service

router = APIRouter(prefix="/retailer/stores/{store_id}/ai-alerts", tags=["Retailer — AI Alerts"])


@router.get("", response_model=list[AIAlertResponse])
def list_alerts(
    store_id: str,
    status: str | None = Query(default=None, description="open | acknowledged | resolved | false_positive"),
    user: AuthenticatedUser = Depends(get_current_retailer),
) -> list[AIAlertResponse]:
    return ai_alert_service.list_alerts(store_id=store_id, retailer_id=user.id, status=status)


@router.post("/{alert_id}/resolve", response_model=AIAlertResponse)
def resolve_alert(
    store_id: str,
    alert_id: str,
    payload: AlertResolveRequest,
    user: AuthenticatedUser = Depends(get_current_retailer),
) -> AIAlertResponse:
    return ai_alert_service.resolve_alert(
        store_id=store_id, alert_id=alert_id, retailer_id=user.id, new_status=payload.status
    )
