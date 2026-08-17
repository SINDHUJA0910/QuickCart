"""
Admin authentication — MVP-level, matching the spec's "Admin Features
(Optional)" status.

A single shared X-Admin-Key header, checked against ADMIN_API_KEY, gates
every admin endpoint. This is intentionally minimal: there is no admin
profile table in the schema, and building full multi-admin accounts with
individual audit trails for a feature the spec marks optional isn't
justified yet. If admin tooling becomes a real operational surface, this
should be replaced with proper Supabase Auth-backed admin accounts — noted
explicitly so it isn't mistaken for a finished, individually-audited
auth system.
"""
from fastapi import Header

from app.core.config import settings
from app.core.exceptions import AuthError


def require_admin(x_admin_key: str = Header(...)) -> None:
    if not settings.admin_api_key or x_admin_key != settings.admin_api_key:
        raise AuthError("Invalid admin key")
