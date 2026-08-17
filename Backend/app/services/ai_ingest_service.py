"""
AI frame ingestion — the orchestration point that ties detection, tracking,
shelf-activity detection, and the mismatch engine together for a single
incoming frame from one camera.

State management note: `CameraTracker` and `ShelfActivityDetector` both need
to persist state (tracker identity history, previous-frame pixel data)
across consecutive frames from the same camera. This module keeps that
state in a process-local dict keyed by camera_id, which is correct for a
single backend process but will NOT work correctly if the API is horizontally
scaled across multiple processes/machines without sticky routing per camera —
flagged here explicitly rather than silently shipped as if it were
production-scale-ready. Phase 8's hardening pass should either pin each
camera's frames to one worker (sticky routing) or move this state into
Redis with a per-camera lock, and is noted as a known limitation, not an
oversight.

In a real deployment this endpoint would be called by a lightweight
worker process pulling frames off each camera's RTSP/HLS stream at a fixed
interval (e.g. 2-5 fps is plenty for this use case) — not by the frontend
directly.
"""
from dataclasses import dataclass

import cv2
import numpy as np

from app.ai.detection.detector import detect_people
from app.ai.theft_logic.mismatch_engine import evaluate_session
from app.ai.theft_logic.shelf_activity import ShelfActivityDetector, ShelfZone
from app.ai.tracking.tracker import CameraTracker
from app.core.exceptions import NotFoundError
from app.db.supabase_client import get_service_client
from app.services import ai_alert_service
from app.services.store_ownership import verify_store_ownership
from app.utils.time import utcnow_iso

_camera_state: dict[str, "_CameraState"] = {}


@dataclass
class _CameraState:
    tracker: CameraTracker
    shelf_detector: ShelfActivityDetector


@dataclass(frozen=True)
class IngestResult:
    people_tracked: int
    track_ids: list[str]
    shelf_events_detected: int
    alert_created: dict | None = None


def _get_or_create_state(camera_id: str, zone_config: list[dict]) -> _CameraState:
    if camera_id not in _camera_state:
        zones = [ShelfZone(zone_id=z["zone_id"], x1=z["x1"], y1=z["y1"], x2=z["x2"], y2=z["y2"]) for z in zone_config]
        _camera_state[camera_id] = _CameraState(
            tracker=CameraTracker(), shelf_detector=ShelfActivityDetector(zones)
        )
    return _camera_state[camera_id]


def ingest_frame(camera_id: str, retailer_id: str, frame_bytes: bytes) -> IngestResult:
    service = get_service_client()

    camera = service.table("cctv_cameras").select("*").eq("id", camera_id).execute()
    if not camera.data:
        raise NotFoundError("Camera not found")
    camera_row = camera.data[0]
    store_id = camera_row["store_id"]
    verify_store_ownership(store_id, retailer_id)

    frame = cv2.imdecode(np.frombuffer(frame_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
    if frame is None:
        raise ValueError("Could not decode frame — expected a JPEG/PNG-encoded image")

    state = _get_or_create_state(camera_id, camera_row.get("zone_config") or [])

    people = detect_people(frame)
    tracked = state.tracker.update(frame, people)

    shelf_events = state.shelf_detector.check(frame)
    for event in shelf_events:
        service.table("shelf_events").insert(
            {
                "camera_id": camera_id,
                "store_id": store_id,
                "zone_id": event.zone_id,
                "changed_area_ratio": event.changed_area_ratio,
                "detected_at": utcnow_iso(),
            }
        ).execute()

    service.table("cctv_cameras").update(
        {"status": "online", "last_heartbeat": utcnow_iso()}
    ).eq("id", camera_id).execute()

    alert_created = None
    if shelf_events:
        active_sessions = (
            service.table("shopping_sessions")
            .select("id")
            .eq("store_id", store_id)
            .eq("status", "active")
            .execute()
        )
        for session_row in active_sessions.data or []:
            result = evaluate_session(session_row["id"])
            if result.severity is not None:
                alert = ai_alert_service.create_alert(
                    store_id=store_id,
                    reason="cart_scan_mismatch",
                    severity=result.severity,
                    session_id=result.session_id,
                    camera_id=camera_id,
                    confidence_score=None,
                )
                alert_created = alert.model_dump()

    return IngestResult(
        people_tracked=len(tracked),
        track_ids=[t.track_id for t in tracked],
        shelf_events_detected=len(shelf_events),
        alert_created=alert_created,
    )


def reset_camera_state(camera_id: str) -> None:
    """Called when a camera's monitoring session ends (e.g. store closes,
    or the camera reconnects after a gap) so stale tracker/diff state
    doesn't bleed into the next monitoring window."""
    _camera_state.pop(camera_id, None)
