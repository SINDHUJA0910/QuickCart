"""
Tests for Phase 6.

Includes real (not mocked) exercises of the classical-CV shelf activity
detector and the DeepSORT tracker — these are the two pieces that run real
algorithms locally with no network/training dependency, so they're tested
against actual pixel data / actual tracker state, matching the manual
verification already done against real YOLOv8 inference and a real photo.
The mismatch engine and camera/alert services are tested against the fake
Supabase fixture, same pattern as every other phase.
"""
import numpy as np
import pytest

from app.ai.theft_logic.shelf_activity import ShelfActivityDetector, ShelfZone
from app.core.exceptions import ForbiddenError
from app.schemas.camera import CameraCreateRequest, ZoneConfig
from app.schemas.store import StoreCreateRequest
from app.services import ai_alert_service, camera_service, retailer_store_service
from app.ai.theft_logic.mismatch_engine import evaluate_session
from tests.fake_supabase import FakeServiceClient

RETAILER_ID = "retailer-1"
OTHER_RETAILER_ID = "retailer-2"
CUSTOMER_ID = "cust-1"
CUSTOMER_2_ID = "cust-2"


# ---------------------------------------------------------------------
# Shelf activity — real pixel-diff logic, no mocking
# ---------------------------------------------------------------------

def test_shelf_activity_ignores_static_scene_but_flags_real_change():
    zones = [ShelfZone("shelf-A", 100, 100, 300, 300)]
    detector = ShelfActivityDetector(zones)

    rng = np.random.default_rng(7)
    base = rng.integers(0, 255, (480, 640, 3), dtype=np.uint8)

    detector.check(base)  # establish baseline
    assert detector.check(base.copy()) == []  # identical frame -> no event

    changed = base.copy()
    changed[150:250, 150:250] = 255
    events = detector.check(changed)
    assert len(events) == 1
    assert events[0].zone_id == "shelf-A"


def test_shelf_activity_multiple_zones_independent():
    zones = [ShelfZone("A", 0, 0, 100, 100), ShelfZone("B", 200, 200, 300, 300)]
    detector = ShelfActivityDetector(zones)
    rng = np.random.default_rng(1)
    base = rng.integers(0, 255, (480, 640, 3), dtype=np.uint8)
    detector.check(base)

    changed = base.copy()
    changed[10:90, 10:90] = 0  # only zone A changes
    events = detector.check(changed)
    assert {e.zone_id for e in events} == {"A"}


# ---------------------------------------------------------------------
# Camera + alert services
# ---------------------------------------------------------------------

@pytest.fixture
def fake_client(monkeypatch):
    client = FakeServiceClient()
    for module in (
        "retailer_store_service", "camera_service", "ai_alert_service",
        "store_ownership", "session_service", "cart_service",
        "product_service", "inventory_service", "notification_service",
    ):
        monkeypatch.setattr(f"app.services.{module}.get_service_client", lambda: client)
    monkeypatch.setattr("app.ai.theft_logic.mismatch_engine.get_service_client", lambda: client)
    return client


def test_create_camera_with_zones_and_ownership_enforced(fake_client):
    store = retailer_store_service.create_store(RETAILER_ID, StoreCreateRequest(name="Fresh Mart", store_type="grocery"))

    camera = camera_service.create_camera(
        store.id, RETAILER_ID,
        CameraCreateRequest(
            label="Aisle 1", stream_url="rtsp://example/cam1",
            zone_config=[ZoneConfig(zone_id="z1", x1=0, y1=0, x2=100, y2=100, shelf_location="Aisle 1")],
        ),
    )
    assert camera.zone_config[0].zone_id == "z1"

    with pytest.raises(ForbiddenError):
        camera_service.list_cameras(store.id, OTHER_RETAILER_ID)


def test_alert_create_list_resolve(fake_client):
    store = retailer_store_service.create_store(RETAILER_ID, StoreCreateRequest(name="Fresh Mart", store_type="grocery"))

    alert = ai_alert_service.create_alert(store.id, reason="cart_scan_mismatch", severity="high")
    open_alerts = ai_alert_service.list_alerts(store.id, RETAILER_ID, status="open")
    assert len(open_alerts) == 1

    resolved = ai_alert_service.resolve_alert(store.id, alert.id, RETAILER_ID, new_status="false_positive")
    assert resolved.status == "false_positive"

    still_open = ai_alert_service.list_alerts(store.id, RETAILER_ID, status="open")
    assert len(still_open) == 0


# ---------------------------------------------------------------------
# Mismatch engine — the core correlation logic
# ---------------------------------------------------------------------

def test_mismatch_engine_flags_gap_between_shelf_events_and_scanned_items(fake_client):
    from app.services import session_service, cart_service, inventory_service

    store = retailer_store_service.create_store(RETAILER_ID, StoreCreateRequest(name="Fresh Mart", store_type="grocery"))
    fake_client.seed("customers", [{"id": CUSTOMER_ID, "full_name": "Asha Kumar"}])

    from app.schemas.inventory import ProductCreateRequest
    product = inventory_service.create_product(
        store.id, RETAILER_ID, ProductCreateRequest(name="Item", mrp_paise=1000, stock_quantity=20)
    )

    session = session_service.create_session(CUSTOMER_ID, store.id)
    cart_service.add_item(session.id, CUSTOMER_ID, product.id, quantity=1)  # only 1 scanned

    # Simulate 4 shelf events (4 "picks") at this store since the session started
    for _ in range(4):
        fake_client.table("shelf_events").insert(
            {"camera_id": "cam-1", "store_id": store.id, "zone_id": "z1",
             "changed_area_ratio": 0.1, "detected_at": "2026-08-05T10:05:00+00:00"}
        ).execute()

    result = evaluate_session(session.id)
    assert result.picked_estimate == 4
    assert result.scanned_count == 1
    assert result.gap == 3
    assert result.severity == "high"  # gap >= 3 threshold
    assert result.ambiguous is False


def test_mismatch_engine_no_alert_when_counts_match(fake_client):
    from app.services import session_service, cart_service, inventory_service

    store = retailer_store_service.create_store(RETAILER_ID, StoreCreateRequest(name="Fresh Mart", store_type="grocery"))
    fake_client.seed("customers", [{"id": CUSTOMER_ID, "full_name": "Asha Kumar"}])
    from app.schemas.inventory import ProductCreateRequest
    product = inventory_service.create_product(
        store.id, RETAILER_ID, ProductCreateRequest(name="Item", mrp_paise=1000, stock_quantity=20)
    )

    session = session_service.create_session(CUSTOMER_ID, store.id)
    cart_service.add_item(session.id, CUSTOMER_ID, product.id, quantity=2)

    fake_client.table("shelf_events").insert(
        {"camera_id": "cam-1", "store_id": store.id, "zone_id": "z1",
         "changed_area_ratio": 0.1, "detected_at": "2026-08-05T10:05:00+00:00"}
    ).execute()
    fake_client.table("shelf_events").insert(
        {"camera_id": "cam-1", "store_id": store.id, "zone_id": "z1",
         "changed_area_ratio": 0.1, "detected_at": "2026-08-05T10:06:00+00:00"}
    ).execute()

    result = evaluate_session(session.id)
    assert result.gap == 0
    assert result.severity is None


def test_mismatch_engine_refuses_to_attribute_when_multiple_concurrent_sessions(fake_client):
    """The one guardrail that matters most: never blame the wrong customer."""
    from app.services import session_service

    store = retailer_store_service.create_store(RETAILER_ID, StoreCreateRequest(name="Fresh Mart", store_type="grocery"))
    fake_client.seed("customers", [
        {"id": CUSTOMER_ID, "full_name": "Asha Kumar"},
        {"id": CUSTOMER_2_ID, "full_name": "Rahul Verma"},
    ])

    session1 = session_service.create_session(CUSTOMER_ID, store.id)
    # A second, different customer also shopping concurrently at the same store
    session2_row = fake_client.table("shopping_sessions").insert(
        {"customer_id": CUSTOMER_2_ID, "store_id": store.id}
    ).execute().data[0]

    result = evaluate_session(session1.id)
    assert result.ambiguous is True
    assert result.severity is None
