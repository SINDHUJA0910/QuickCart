"""
Person detection via YOLOv8 (Ultralytics), pretrained on COCO.

Scope, stated plainly: COCO's 80 classes include 'person' (class 0) and
some generic objects (bottle, cup, handbag, backpack...) but nothing that
maps to actual supermarket SKUs — there is no COCO class for "1kg bag of
basmati rice." This module is therefore deliberately limited to what
pretrained COCO weights can actually do reliably: detecting *people* in the
frame, which is what tracking.py needs. Product-level shelf monitoring is
handled separately in theft_logic/shelf_activity.py via classical CV
(frame differencing) rather than pretending a COCO detector recognizes
retail products it was never trained on.

Model loading is lazy and cached — the ~6MB yolov8n weights download once
on first use and are reused for the life of the process.
"""
from dataclasses import dataclass
from functools import lru_cache

import numpy as np

COCO_PERSON_CLASS_ID = 0
DEFAULT_CONFIDENCE_THRESHOLD = 0.5


@dataclass(frozen=True)
class PersonDetection:
    """A single detected person, in the format DeepSORT's update_tracks expects:
    ([x, y, w, h], confidence, class_name)."""
    x: float
    y: float
    width: float
    height: float
    confidence: float

    def as_deepsort_tuple(self) -> tuple[list[float], float, str]:
        return ([self.x, self.y, self.width, self.height], self.confidence, "person")


@lru_cache
def _load_model():
    # Imported lazily so importing this module doesn't require ultralytics/torch
    # to be installed unless detection is actually used (keeps the rest of the
    # backend importable in lightweight environments/tests).
    from ultralytics import YOLO
    return YOLO("yolov8n.pt")


def detect_people(frame: np.ndarray, confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD) -> list[PersonDetection]:
    """Runs YOLOv8 on a single BGR frame (as read by cv2.VideoCapture / cv2.imread)
    and returns only person detections above the confidence threshold."""
    model = _load_model()
    results = model(frame, verbose=False)[0]

    detections: list[PersonDetection] = []
    for box in results.boxes:
        class_id = int(box.cls[0])
        confidence = float(box.conf[0])
        if class_id != COCO_PERSON_CLASS_ID or confidence < confidence_threshold:
            continue

        x1, y1, x2, y2 = [float(v) for v in box.xyxy[0]]
        detections.append(
            PersonDetection(x=x1, y=y1, width=x2 - x1, height=y2 - y1, confidence=confidence)
        )

    return detections
