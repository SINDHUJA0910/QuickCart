"""
Shelf activity detection via frame differencing.

This is deliberately NOT a trained model. A COCO-pretrained YOLO has no
concept of individual retail SKUs, and training a custom detector needs
labeled shelf imagery this project doesn't have. What's implementable
without any training data is classical background-subtraction: define a
rectangular Region of Interest (ROI) over a shelf in the camera's frame
(operator-configured, stored on cctv_cameras via CameraZoneConfig), and
flag a "shelf event" whenever pixel content inside that ROI changes more
than a threshold amount between frames — which is exactly what happens
when a hand reaches in and an item is lifted off the shelf.

This does not identify *which* product was taken, or attribute the event
to a specific tracked person — it only answers "did something change on
this shelf, and when." theft_logic/mismatch_engine.py is what correlates
the *count* of these events against the *count* of items actually scanned
into a session's cart over the same time window, which is the level of
granularity the rule-based mismatch detection in the spec's Scenarios 1-6
actually needs.
"""
from dataclasses import dataclass

import cv2
import numpy as np

DEFAULT_CHANGE_THRESHOLD = 25       # pixel intensity delta considered "changed"
DEFAULT_MIN_CHANGED_AREA_RATIO = 0.03  # fraction of the ROI that must change to count as an event


@dataclass(frozen=True)
class ShelfZone:
    """A configured region of interest on one camera's frame, in pixel coordinates."""
    zone_id: str
    x1: int
    y1: int
    x2: int
    y2: int


@dataclass(frozen=True)
class ShelfEvent:
    zone_id: str
    changed_area_ratio: float


class ShelfActivityDetector:
    """One instance per camera. Holds the previous frame (per zone) so
    `check` can diff against it — must be called on consecutive frames
    from the same stream, not arbitrary/out-of-order frames."""

    def __init__(self, zones: list[ShelfZone]):
        self._zones = {z.zone_id: z for z in zones}
        self._previous_crops: dict[str, np.ndarray] = {}

    def check(self, frame: np.ndarray) -> list[ShelfEvent]:
        events = []
        for zone_id, zone in self._zones.items():
            crop = cv2.cvtColor(frame[zone.y1:zone.y2, zone.x1:zone.x2], cv2.COLOR_BGR2GRAY)
            crop = cv2.GaussianBlur(crop, (5, 5), 0)

            previous = self._previous_crops.get(zone_id)
            self._previous_crops[zone_id] = crop

            if previous is None or previous.shape != crop.shape:
                continue  # first frame for this zone — nothing to diff against yet

            diff = cv2.absdiff(previous, crop)
            changed_mask = diff > DEFAULT_CHANGE_THRESHOLD
            changed_ratio = float(np.count_nonzero(changed_mask)) / changed_mask.size

            if changed_ratio >= DEFAULT_MIN_CHANGED_AREA_RATIO:
                events.append(ShelfEvent(zone_id=zone_id, changed_area_ratio=round(changed_ratio, 4)))

        return events
