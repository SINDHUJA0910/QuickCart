"""
Multi-person tracking via DeepSORT (deep_sort_realtime).

One tracker instance must be maintained per camera stream (not shared
across cameras, and not recreated per frame) — DeepSORT's identity
continuity depends on its internal Kalman filter state and track history
persisting across calls. `CameraTracker` wraps this lifecycle: one instance
lives for the duration of a camera's active monitoring session, created by
the ingestion service (Phase 6's api/v1/endpoints/ai_ingest.py) when a
shopping session starts and discarded when it ends.

Uses the 'mobilenet' embedder (a small pretrained ReID CNN bundled with
deep_sort_realtime) for appearance matching between frames, which is what
lets the tracker keep the same identity for a person even through brief
occlusion — mentioned in the original spec's "Occlusion Handling" requirement.
"""
from dataclasses import dataclass

import numpy as np

from app.ai.detection.detector import PersonDetection


@dataclass(frozen=True)
class TrackedPerson:
    track_id: str
    x1: float
    y1: float
    x2: float
    y2: float


class CameraTracker:
    """One instance per camera stream. Not thread-safe — one tracker per
    camera's dedicated processing task/thread."""

    def __init__(self, max_age: int = 30):
        from deep_sort_realtime.deepsort_tracker import DeepSort
        self._tracker = DeepSort(max_age=max_age, embedder="mobilenet", half=False)

    def update(self, frame: np.ndarray, detections: list[PersonDetection]) -> list[TrackedPerson]:
        raw_detections = [d.as_deepsort_tuple() for d in detections]
        tracks = self._tracker.update_tracks(raw_detections, frame=frame)

        result = []
        for track in tracks:
            if not track.is_confirmed():
                continue
            x1, y1, x2, y2 = track.to_ltrb()
            result.append(TrackedPerson(track_id=str(track.track_id), x1=x1, y1=y1, x2=x2, y2=y2))
        return result
