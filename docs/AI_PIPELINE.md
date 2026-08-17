# QuickCart AI Theft-Detection Pipeline

## What's real vs. what needs your own data

| Component | Status | Notes |
|---|---|---|
| Person detection (YOLOv8) | ✅ Working, pretrained | COCO weights, verified against real photos |
| Multi-person tracking (DeepSORT) | ✅ Working, pretrained | Verified stable track IDs across frames |
| Shelf activity detection | ✅ Working, no training needed | Classical CV frame-differencing per configured ROI |
| Cart-vs-shelf mismatch engine | ✅ Working, rule-based | Correlates shelf events against scanned cart items |
| Product-level identification | ❌ Not implemented | No pretrained model recognizes arbitrary retail SKUs |
| Concealment gesture recognition | ❌ Needs training | Harness provided in `scripts/train_concealment_classifier.py`; needs your own labeled footage |

## Pipeline flow (as implemented)

```
Camera frame (JPEG, POSTed to /retailer/cameras/{id}/ingest-frame)
        │
        ▼
YOLOv8 person detection (app/ai/detection/detector.py)
        │
        ▼
DeepSORT tracking — maintains stable identity per person (app/ai/tracking/tracker.py)
        │
        ▼
Shelf-activity detection — per-zone frame differencing (app/ai/theft_logic/shelf_activity.py)
        │                                    │
        │                                    ▼
        │                          shelf_events table (persisted)
        │                                    │
        ▼                                    ▼
                 Mismatch engine (app/ai/theft_logic/mismatch_engine.py)
                 compares: shelf_events count (since session start)
                       vs. cart_items scanned quantity (same session)
                                    │
                                    ▼
                     ai_alerts row created if gap ≥ threshold
                     (medium/high/critical by magnitude)
```

## Why product identity and gestures aren't faked here

A YOLOv8 model pretrained on COCO knows 80 general object classes (person,
bottle, cup, backpack...). It has never seen "India Gate Basmati Rice 1kg"
and cannot be made to recognize it without training on labeled images of
that exact product — the same is true for every other SKU in a real store.
Building a fake "it works" detector for this would be actively misleading:
it would either always miss, always guess wrong, or require weights that
don't exist. Instead, shelf-activity detection sidesteps the problem
entirely by asking a coarser, honestly-answerable question — "did the
pixels in this shelf region change?" — which needs zero training data and
is genuinely reliable for what it claims to do.

Concealment gesture recognition (spec Scenario 3) is a genuine action-
recognition problem — it needs a model trained on labeled video clips of
what concealment actually looks like on your cameras, which by definition
doesn't exist until you collect it. `scripts/train_concealment_classifier.py`
is a real, runnable fine-tuning script (torchvision's r3d_18, pretrained on
Kinetics-400 general actions) — but it requires you to supply labeled clips
first; there's no way around that step.

## Known limitations (Phase 8 hardening candidates)

- **Per-process tracker/detector state**: `ai_ingest_service.py` keeps one
  `CameraTracker` + `ShelfActivityDetector` per camera in a process-local
  dict. Correct for a single backend process; needs sticky routing or a
  shared store (Redis) before horizontal scaling.
- **Attribution refuses ambiguity by design**: `mismatch_engine.evaluate_session`
  returns `ambiguous=True` (no alert) whenever more than one customer is
  shopping the same store concurrently, since shelf events can't currently
  be attributed to a specific tracked person. Solving this needs person-to-
  session fusion (e.g. recognizing a customer at store entry and maintaining
  that identity across cameras), which is a larger camera-placement and
  re-identification project, not a small addition.
- **Ingestion is pull-based in this design**: a real deployment needs a
  worker process pulling frames off each camera's RTSP/HLS stream at a
  fixed interval and POSTing them to `/ingest-frame` — that worker isn't
  included here (out of scope for a backend-API phase) but the endpoint
  contract is ready for it.
