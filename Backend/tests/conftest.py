"""
Shared pytest fixtures.

Tests never hit a real Supabase project. `get_anon_client`/`get_service_client`
are patched with lightweight fakes that mimic the subset of the supabase-py
interface QuickCart actually uses (`.auth.sign_up`, `.table(...).insert(...)`,
etc.), so tests stay fast and deterministic and don't require network access
or real credentials.
"""
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock  # noqa: F401 (re-exported for readability in fixtures below)

import pytest
from fastapi.testclient import TestClient
from jose import jwt

# Ensure required env vars exist before app.core.config.Settings() is constructed.
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_ANON_KEY", "test-anon-key")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-key")
os.environ.setdefault("SUPABASE_JWT_SECRET", "test-jwt-secret")
os.environ.setdefault("RAZORPAY_KEY_ID", "rzp_test_fake")
os.environ.setdefault("RAZORPAY_KEY_SECRET", "fake_razorpay_secret")
os.environ.setdefault("QR_ENCRYPTION_KEY", "n9ARrZuU2bzI5fBJxK2tbYicDgribrjVKvgm3A-9_aY=")
os.environ.setdefault("ADMIN_API_KEY", "test-admin-key")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

TEST_USER_ID = "11111111-1111-1111-1111-111111111111"


def _make_test_jwt(subject: str = TEST_USER_ID, email: str = "test@example.com") -> str:
    """Builds a JWT signed the same way Supabase signs real access tokens, so
    app.core.security.decode_access_token verifies it successfully in tests."""
    return jwt.encode(
        {"sub": subject, "email": email, "role": "authenticated", "aud": "authenticated"},
        os.environ["SUPABASE_JWT_SECRET"],
        algorithm="HS256",
    )


@pytest.fixture
def fake_auth_user():
    return SimpleNamespace(id=TEST_USER_ID, email="test@example.com")


@pytest.fixture
def fake_session():
    return SimpleNamespace(
        access_token=_make_test_jwt(),
        refresh_token="fake-refresh-token",
        expires_in=3600,
    )


@pytest.fixture
def patched_supabase(monkeypatch, fake_auth_user, fake_session):
    """
    Patches app.db.supabase_client.get_anon_client / get_service_client with
    MagicMocks whose .auth and .table(...) chains return controllable fakes.
    Returns the (anon_mock, service_mock) pair so individual tests can further
    configure return values (e.g. simulating an existing profile row).
    """
    anon_mock = MagicMock()
    service_mock = MagicMock()

    anon_mock.auth.sign_up.return_value = SimpleNamespace(user=fake_auth_user, session=fake_session)
    anon_mock.auth.sign_in_with_password.return_value = SimpleNamespace(session=fake_session)

    # service.table("customers").select("id").eq("id", uid).execute() -> .data
    table_mock = MagicMock()
    table_mock.select.return_value = table_mock
    table_mock.eq.return_value = table_mock
    table_mock.insert.return_value = table_mock
    table_mock.single.return_value = table_mock
    table_mock.execute.return_value = SimpleNamespace(data=None)
    service_mock.table.return_value = table_mock

    monkeypatch.setattr("app.services.auth_service.get_anon_client", lambda: anon_mock)
    monkeypatch.setattr("app.services.auth_service.get_service_client", lambda: service_mock)

    return anon_mock, service_mock, table_mock


@pytest.fixture
def client(patched_supabase):
    from app.main import create_app
    return TestClient(create_app())


@pytest.fixture
def auth_headers():
    return {"Authorization": f"Bearer {_make_test_jwt()}"}
