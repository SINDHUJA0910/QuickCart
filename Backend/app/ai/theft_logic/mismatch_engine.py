"""
Cart-vs-shelf mismatch engine — implements the spec's Scenarios 1-6 at the
level classical CV (shelf_activity.py) can actually support.

Honest statement of what this can and cannot do, stated once here rather
than re-litigated in every function's docstring:

CAN do: count how many "something was taken off a shelf" events happened
at a store since a session started, and compare that count against how
many items were actually scanned into that session's cart. A sustained,
significant gap between the two is exactly Scenario 2 ("picks 2, scans 1")
and a proxy for Scenario 5 ("removed from shelf, never scanned, never
returned").

CANNOT do (without a labeled training run this project doesn't have):
attribute a specific shelf event to a specific tracked person (Scenario 3's
"customer hides product" needs action/gesture recognition on a person, not
shelf pixels), or resolve which of several simultaneous shoppers at the
same store caused a given shelf event. The latter is why `evaluate_session`
below explicitly refuses to generate an alert when more than one session is
active at the same store concurrently — attributing a shelf change to the
wrong customer would be worse than not flagging it, and this is flagged as
an open problem for Phase 8 (solvable with person-to-cart fusion: matching
a tracked person's continuous on-camera presence to their session via
entry-gate recognition, which needs its own camera placement and isn't
assumed by the current single-store-camera-array design).
"""
from dataclasses import dataclass
from datetime import datetime, timezone

from app.db.supabase_client import get_service_client
from app.services.dashboard_service import _parse_dt

MISMATCH_THRESHOLDS = [
    (5, "critical"),  # picked - scanned >= 5
    (3, "high"),
    (1, "medium"),
]


@dataclass(frozen=True)
class MismatchResult:
    session_id: str
    picked_estimate: int
    scanned_count: int
    gap: int
    severity: str | None  # None means no alert warranted
    ambiguous: bool = False  # True when multiple concurrent sessions prevented attribution


def _severity_for_gap(gap: int) -> str | None:
    for threshold, severity in MISMATCH_THRESHOLDS:
        if gap >= threshold:
            return severity
    return None


def evaluate_session(session_id: str) -> MismatchResult:
    service = get_service_client()

    session_result = service.table("shopping_sessions").select("*").eq("id", session_id).execute()
    if not session_result.data:
        raise ValueError(f"Session {session_id} not found")
    session = session_result.data[0]
    store_id = session["store_id"]

    concurrent = (
        service.table("shopping_sessions")
        .select("id")
        .eq("store_id", store_id)
        .eq("status", "active")
        .execute()
    )
    other_active = [s for s in (concurrent.data or []) if s["id"] != session_id]
    if other_active:
        return MismatchResult(
            session_id=session_id, picked_estimate=0, scanned_count=0, gap=0, severity=None, ambiguous=True
        )

    entry_time = _parse_dt(session["entry_time"])
    shelf_events = service.table("shelf_events").select("*").eq("store_id", store_id).execute()
    picked_estimate = sum(
        1 for e in (shelf_events.data or []) if _parse_dt(e["detected_at"]) >= entry_time
    )

    cart_items = (
        service.table("cart_items")
        .select("quantity")
        .eq("session_id", session_id)
        .is_("removed_at", "null")
        .execute()
    )
    scanned_count = sum(item["quantity"] for item in (cart_items.data or []))

    gap = max(0, picked_estimate - scanned_count)
    severity = _severity_for_gap(gap)

    return MismatchResult(
        session_id=session_id,
        picked_estimate=picked_estimate,
        scanned_count=scanned_count,
        gap=gap,
        severity=severity,
    )
