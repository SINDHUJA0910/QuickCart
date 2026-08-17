"""
Tests for customer/retailer auth endpoints.

Covers: successful signup, successful login, and — most importantly — that
role enforcement actually rejects a request when the token's identity does
not own a profile of the required role. That last case is the one most
likely to silently regress into a security hole, so it gets the most
explicit coverage here.
"""
from types import SimpleNamespace


def test_customer_signup_success(client, patched_supabase):
    _, _, table_mock = patched_supabase

    response = client.post(
        "/api/v1/auth/customer/signup",
        json={
            "email": "shopper@example.com",
            "password": "supersecret123",
            "full_name": "Asha Kumar",
            "phone": "9876543210",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["role"] == "customer"
    assert body["profile"]["full_name"] == "Asha Kumar"
    assert body["token"]["access_token"]
    table_mock.insert.assert_called_once()


def test_retailer_signup_success(client, patched_supabase):
    response = client.post(
        "/api/v1/auth/retailer/signup",
        json={
            "email": "owner@store.com",
            "password": "supersecret123",
            "business_name": "Fresh Mart",
            "phone": "9123456780",
            "gstin": "29ABCDE1234F1Z5",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["role"] == "retailer"
    assert body["profile"]["business_name"] == "Fresh Mart"


def test_customer_login_rejects_retailer_account(client, patched_supabase):
    """A valid Supabase login whose identity only has a *retailer* profile
    must be rejected by the customer login route."""
    _, _, table_mock = patched_supabase
    # Simulate: customers table has no matching row, retailers table does.
    table_mock.execute.side_effect = [
        SimpleNamespace(data=None),                 # customers lookup -> not found
        SimpleNamespace(data={"id": "x"}),           # retailers lookup -> found
    ]

    response = client.post(
        "/api/v1/auth/customer/login",
        json={"email": "owner@store.com", "password": "supersecret123"},
    )

    assert response.status_code == 401


def test_me_requires_bearer_token(client, patched_supabase):
    response = client.get("/api/v1/auth/customer/me")
    assert response.status_code in (401, 403)  # FastAPI's HTTPBearer default is 403 when header missing


def test_me_returns_profile_for_valid_customer(client, patched_supabase, auth_headers):
    _, _, table_mock = patched_supabase
    table_mock.execute.side_effect = [
        SimpleNamespace(data={"id": "11111111-1111-1111-1111-111111111111"}),  # resolve_role: customers found
        SimpleNamespace(
            data={"id": "11111111-1111-1111-1111-111111111111", "full_name": "Asha Kumar", "phone": "9876543210"}
        ),  # get_customer_profile
    ]

    response = client.get("/api/v1/auth/customer/me", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["full_name"] == "Asha Kumar"


def test_me_forbidden_for_retailer_token_on_customer_route(client, patched_supabase, auth_headers):
    _, _, table_mock = patched_supabase
    table_mock.execute.side_effect = [
        SimpleNamespace(data=None),                # customers lookup -> not found
        SimpleNamespace(data={"id": "x"}),          # retailers lookup -> found
    ]

    response = client.get("/api/v1/auth/customer/me", headers=auth_headers)

    assert response.status_code == 403
