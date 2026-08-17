"""
Tests for Phase 7: notifications fired at real trigger points (low stock,
payment success, AI alert creation), notification read/unread state, and
admin auth gating.
"""
import pytest
from fastapi.testclient import TestClient

from app.services import (
    ai_alert_service,
    cart_service,
    inventory_service,
    notification_service,
    retailer_store_service,
    session_service,
)
from app.schemas.inventory import ProductCreateRequest
from app.schemas.store import StoreCreateRequest
from tests.fake_supabase import FakeServiceClient

RETAILER_ID = "retailer-1"
CUSTOMER_ID = "cust-1"


@pytest.fixture
def fake_client(monkeypatch):
    client = FakeServiceClient()
    for module in (
        "retailer_store_service", "inventory_service", "session_service",
        "cart_service", "product_service", "notification_service",
        "ai_alert_service", "store_ownership",
    ):
        monkeypatch.setattr(f"app.services.{module}.get_service_client", lambda: client)
    return client


def test_low_stock_notification_fires_when_threshold_crossed(fake_client):
    store = retailer_store_service.create_store(RETAILER_ID, StoreCreateRequest(name="Fresh Mart", store_type="grocery"))
    fake_client.seed("customers", [{"id": CUSTOMER_ID, "full_name": "Asha Kumar"}])
    product = inventory_service.create_product(
        store.id, RETAILER_ID,
        ProductCreateRequest(name="Item", mrp_paise=1000, stock_quantity=6, low_stock_threshold=5),
    )
    session = session_service.create_session(CUSTOMER_ID, store.id)

    # Buying 1 brings stock to 5 (== threshold) -> should trigger low_stock
    cart_service.add_item(session.id, CUSTOMER_ID, product.id, quantity=1)

    notes = notification_service.list_notifications(RETAILER_ID)
    assert any(n.category == "low_stock" for n in notes)


def test_out_of_stock_notification_fires_at_zero(fake_client):
    store = retailer_store_service.create_store(RETAILER_ID, StoreCreateRequest(name="Fresh Mart", store_type="grocery"))
    fake_client.seed("customers", [{"id": CUSTOMER_ID, "full_name": "Asha Kumar"}])
    product = inventory_service.create_product(
        store.id, RETAILER_ID,
        ProductCreateRequest(name="Item", mrp_paise=1000, stock_quantity=1, low_stock_threshold=5),
    )
    session = session_service.create_session(CUSTOMER_ID, store.id)

    cart_service.add_item(session.id, CUSTOMER_ID, product.id, quantity=1)

    notes = notification_service.list_notifications(RETAILER_ID)
    assert any(n.category == "out_of_stock" for n in notes)


def test_removing_item_does_not_fire_stock_notification(fake_client):
    """Restoring stock (removal) should never fire a low/out-of-stock alert —
    only consumption should."""
    store = retailer_store_service.create_store(RETAILER_ID, StoreCreateRequest(name="Fresh Mart", store_type="grocery"))
    fake_client.seed("customers", [{"id": CUSTOMER_ID, "full_name": "Asha Kumar"}])
    product = inventory_service.create_product(
        store.id, RETAILER_ID,
        ProductCreateRequest(name="Item", mrp_paise=1000, stock_quantity=10, low_stock_threshold=5),
    )
    session = session_service.create_session(CUSTOMER_ID, store.id)
    summary = cart_service.add_item(session.id, CUSTOMER_ID, product.id, quantity=1)  # stock -> 9, no alert
    assert notification_service.list_notifications(RETAILER_ID) == []

    cart_service.remove_item(session.id, CUSTOMER_ID, summary.items[0].id)  # stock -> 10 again
    assert notification_service.list_notifications(RETAILER_ID) == []


def test_ai_alert_creation_fires_notification(fake_client):
    store = retailer_store_service.create_store(RETAILER_ID, StoreCreateRequest(name="Fresh Mart", store_type="grocery"))
    ai_alert_service.create_alert(store.id, reason="cart_scan_mismatch", severity="high")

    notes = notification_service.list_notifications(RETAILER_ID)
    assert any(n.category == "ai_alert" for n in notes)


def test_mark_read_updates_state_and_rejects_other_recipient(fake_client):
    store = retailer_store_service.create_store(RETAILER_ID, StoreCreateRequest(name="Fresh Mart", store_type="grocery"))
    ai_alert_service.create_alert(store.id, reason="cart_scan_mismatch", severity="medium")
    note = notification_service.list_notifications(RETAILER_ID)[0]
    assert note.read is False

    updated = notification_service.mark_read(note.id, RETAILER_ID)
    assert updated.read is True

    from app.core.exceptions import ForbiddenError
    with pytest.raises(ForbiddenError):
        notification_service.mark_read(note.id, "someone-else")


def test_unread_only_filter(fake_client):
    store = retailer_store_service.create_store(RETAILER_ID, StoreCreateRequest(name="Fresh Mart", store_type="grocery"))
    ai_alert_service.create_alert(store.id, reason="cart_scan_mismatch", severity="medium")
    ai_alert_service.create_alert(store.id, reason="cart_scan_mismatch", severity="high")

    all_notes = notification_service.list_notifications(RETAILER_ID)
    notification_service.mark_read(all_notes[0].id, RETAILER_ID)

    unread = notification_service.list_notifications(RETAILER_ID, unread_only=True)
    assert len(unread) == 1


# ---------------------------------------------------------------------
# Admin auth gating (via actual HTTP layer, not direct service calls)
# ---------------------------------------------------------------------

def test_admin_endpoint_rejects_missing_key():
    from app.main import create_app
    client = TestClient(create_app())
    response = client.get("/api/v1/admin/stats")
    assert response.status_code in (401, 422)  # 422 if header entirely missing per FastAPI's Header(...)


def test_admin_endpoint_rejects_wrong_key():
    from app.main import create_app
    client = TestClient(create_app())
    response = client.get("/api/v1/admin/stats", headers={"X-Admin-Key": "wrong-key"})
    assert response.status_code == 401


def test_admin_endpoint_accepts_correct_key(monkeypatch):
    client_fake = FakeServiceClient()
    monkeypatch.setattr("app.services.admin_service.get_service_client", lambda: client_fake)

    from app.main import create_app
    client = TestClient(create_app())
    response = client.get("/api/v1/admin/stats", headers={"X-Admin-Key": "test-admin-key"})
    assert response.status_code == 200
    assert response.json()["total_stores"] == 0
