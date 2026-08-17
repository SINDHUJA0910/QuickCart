"""
Tests for the shopping session + cart flow, run directly against the service
layer using FakeServiceClient (see fake_supabase.py). This exercises the
actual business rules — one active session per customer, price snapshotting,
live stock sync — rather than just checking that routes return 200.
"""
import pytest

from app.core.exceptions import ConflictError, ForbiddenError
from app.services import cart_service, session_service, store_service, product_service
from tests.fake_supabase import FakeServiceClient

CUSTOMER_ID = "cust-1"
STORE_ID = "store-1"
PRODUCT_ID = "prod-1"


@pytest.fixture
def fake_client(monkeypatch):
    client = FakeServiceClient()
    client.seed(
        "stores",
        [{"id": STORE_ID, "name": "Fresh Mart", "is_active": True, "store_type": "grocery",
          "latitude": 12.97, "longitude": 77.59, "rating": 4.5, "image_url": None,
          "address_line": "MG Road", "city": "Bengaluru", "opening_time": "09:00", "closing_time": "22:00"}],
    )
    client.seed(
        "products",
        [{"id": PRODUCT_ID, "store_id": STORE_ID, "barcode": "8901030123", "name": "Basmati Rice 1kg",
          "brand": "India Gate", "mrp_paise": 15000, "discount_percent": 10.0, "price_paise": 13500,
          "gst_percent": 5.0, "stock_quantity": 20, "is_active": True, "image_url": None,
          "description": None, "weight_value": 1.0, "weight_unit": "kg",
          "manufacture_date": None, "expiry_date": None}],
    )

    monkeypatch.setattr("app.services.store_service.get_service_client", lambda: client)
    monkeypatch.setattr("app.services.session_service.get_service_client", lambda: client)
    monkeypatch.setattr("app.services.product_service.get_service_client", lambda: client)
    monkeypatch.setattr("app.services.cart_service.get_service_client", lambda: client)
    monkeypatch.setattr("app.services.notification_service.get_service_client", lambda: client)
    return client


def test_store_search_computes_distance(fake_client):
    results = store_service.search_stores(lat=12.97, lng=77.60)
    assert len(results) == 1
    assert results[0].distance_km is not None
    assert results[0].name == "Fresh Mart"


def test_create_session_then_second_session_conflicts(fake_client):
    session = session_service.create_session(CUSTOMER_ID, STORE_ID)
    assert session.status == "active"
    assert session.store_name == "Fresh Mart"

    with pytest.raises(ConflictError):
        session_service.create_session(CUSTOMER_ID, STORE_ID)


def test_barcode_lookup_returns_product_detail(fake_client):
    product = product_service.get_product_by_barcode(STORE_ID, "8901030123")
    assert product.name == "Basmati Rice 1kg"
    assert product.price_paise == 13500
    assert product.in_stock is True


def test_add_to_cart_snapshots_price_and_decrements_stock(fake_client):
    session = session_service.create_session(CUSTOMER_ID, STORE_ID)

    summary = cart_service.add_item(session.id, CUSTOMER_ID, PRODUCT_ID, quantity=2)

    assert summary.item_count == 2
    assert summary.subtotal_paise == 15000 * 2
    assert summary.discount_paise == (15000 - 13500) * 2
    assert summary.total_paise == summary.subtotal_paise - summary.discount_paise + summary.gst_paise

    remaining_stock = product_service.get_product_by_id(PRODUCT_ID)["stock_quantity"]
    assert remaining_stock == 18  # 20 - 2


def test_scanning_same_product_twice_merges_into_one_line(fake_client):
    session = session_service.create_session(CUSTOMER_ID, STORE_ID)
    cart_service.add_item(session.id, CUSTOMER_ID, PRODUCT_ID, quantity=1)
    summary = cart_service.add_item(session.id, CUSTOMER_ID, PRODUCT_ID, quantity=1)

    assert len(summary.items) == 1
    assert summary.items[0].quantity == 2


def test_remove_item_restores_stock(fake_client):
    session = session_service.create_session(CUSTOMER_ID, STORE_ID)
    summary = cart_service.add_item(session.id, CUSTOMER_ID, PRODUCT_ID, quantity=3)
    item_id = summary.items[0].id

    cart_service.remove_item(session.id, CUSTOMER_ID, item_id)

    remaining_stock = product_service.get_product_by_id(PRODUCT_ID)["stock_quantity"]
    assert remaining_stock == 20  # fully restored


def test_cannot_add_more_than_available_stock(fake_client):
    session = session_service.create_session(CUSTOMER_ID, STORE_ID)
    with pytest.raises(ConflictError):
        cart_service.add_item(session.id, CUSTOMER_ID, PRODUCT_ID, quantity=999)


def test_other_customer_cannot_access_session(fake_client):
    session = session_service.create_session(CUSTOMER_ID, STORE_ID)
    with pytest.raises(ForbiddenError):
        cart_service.get_cart_summary(session.id, customer_id="someone-else")
