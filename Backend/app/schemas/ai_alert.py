"""Schemas for AI alerts."""
from pydantic import BaseModel


class AIAlertResponse(BaseModel):
    id: str
    session_id: str | None
    camera_id: str | None
    severity: str
    status: str
    reason: str
    confidence_score: float | None
    detected_at: str


class AlertResolveRequest(BaseModel):
    status: str  # "resolved" | "false_positive"
