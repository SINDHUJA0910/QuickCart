"""
Tests for Phase 8 hardening: rate limiting actually triggers a 429 under
excess requests (not just "doesn't break normal traffic", which the rest
of the suite already covers implicitly), and the atomic stock RPC path
rejects a real race — two concurrent-style adjustments that would
oversell stock if they weren't serialized.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient


def test_forgot_password_rate_limit_triggers_429(monkeypatch):
    """3/minute limit on forgot-password — the 4th request in the same
    minute from the same client should be rejected."""
    anon_mock = MagicMock()
    service_mock = MagicMock()
    monkeypatch.setattr("app.services.auth_service.get_anon_client", lambda: anon_mock)
    monkeypatch.setattr("app.services.auth_service.get_service_client", lambda: service_mock)

    from app.main import create_app
    client = TestClient(create_app())

    statuses = []
    for _ in range(4):
        resp = client.post("/api/v1/auth/customer/forgot-password", json={"email": "a@b.com"})
        statuses.append(resp.status_code)

    assert statuses[:3] == [204, 204, 204]
    assert statuses[3] == 429


def test_atomic_stock_rpc_rejects_overselling():
    """Two sequential calls that together would oversell stock: the first
    succeeds, the second must be rejected by the floor check in one atomic
    statement — this is what migration 0005's RPC replaces the old
    read-then-write race with."""
    from tests.fake_supabase import FakeServiceClient

    client = FakeServiceClient()
    client.seed("products", [{"id": "p1", "store_id": "s1", "stock_quantity": 5, "low_stock_threshold": 2}])

    # First call takes the last 5 units -> succeeds, stock now 0
    result = client.rpc("adjust_product_stock", {"p_product_id": "p1", "p_delta": -5}).execute()
    assert result.data["stock_quantity"] == 0

    # A second call trying to take 1 more must be rejected, not driven negative
    from postgrest.exceptions import APIError
    with pytest.raises(APIError):
        client.rpc("adjust_product_stock", {"p_product_id": "p1", "p_delta": -1}).execute()

    final = client.table("products").select("*").eq("id", "p1").execute().data[0]
    assert final["stock_quantity"] == 0  # never went negative
