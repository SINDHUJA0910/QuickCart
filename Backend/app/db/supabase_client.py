"""
Supabase client factory.

Two distinct clients are exposed, and mixing them up is the single easiest way
to introduce a security bug in this codebase, so the naming is deliberately loud:

- `get_anon_client()`   -> respects RLS. Use for any operation that should be
                            scoped by the requesting user's own permissions.
- `get_service_client()` -> BYPASSES RLS entirely. Use only for backend-trusted
                            operations that legitimately span across users/roles,
                            e.g. creating a customer's profile row right after
                            Supabase Auth confirms signup, writing AI alerts,
                            generating invoices. Never expose this client's
                            results directly without your own authorization
                            check first.
"""
from functools import lru_cache

from supabase import Client, create_client

from app.core.config import settings


@lru_cache
def get_anon_client() -> Client:
    return create_client(settings.supabase_url, settings.supabase_anon_key)


@lru_cache
def get_service_client() -> Client:
    return create_client(settings.supabase_url, settings.supabase_service_role_key)
