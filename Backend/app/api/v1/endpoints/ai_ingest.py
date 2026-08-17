"""
AI frame ingestion endpoint.

In production this is called by a worker process pulling frames off each
camera's stream at a fixed interval — not by a browser. It's exposed as a
regular authenticated REST endpoint here (rather than only an internal
function) so that worker can be a separate deployable service that simply
POSTs frames, keeping the CV/ML runtime out of the main API process if
that separation is wanted later (heavier dependencies, different scaling
needs).
"""
from fastapi import APIRouter, Depends, UploadFile

from app.api.v1.deps import get_current_retailer
from app.core.security import AuthenticatedUser
from app.services import ai_ingest_service

router = APIRouter(prefix="/retailer/cameras/{camera_id}/ingest-frame", tags=["Retailer — AI Ingestion"])


@router.post("", summary="Submit one camera frame for AI processing")
async def ingest_frame(
    camera_id: str,
    file: UploadFile,
    user: AuthenticatedUser = Depends(get_current_retailer),
) -> dict:
    frame_bytes = await file.read()
    result = ai_ingest_service.ingest_frame(camera_id=camera_id, retailer_id=user.id, frame_bytes=frame_bytes)
    return {
        "people_tracked": result.people_tracked,
        "track_ids": result.track_ids,
        "shelf_events_detected": result.shelf_events_detected,
        "alert_created": result.alert_created,
    }
