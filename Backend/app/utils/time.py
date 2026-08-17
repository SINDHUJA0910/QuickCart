"""
Timestamp helper.

Fixes a real bug caught during Phase 5 development: earlier code wrote the
literal string "now()" into timestamp columns via the Supabase REST API,
intending it as an SQL function call. PostgREST does not evaluate function
calls from JSON payload values — it would have attempted to cast the literal
text "now()" into a timestamptz and failed. The correct fix is to compute
the timestamp in application code and send a real ISO-8601 value, which is
what every write in this codebase now does via this helper.
"""
from datetime import datetime, timezone


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
