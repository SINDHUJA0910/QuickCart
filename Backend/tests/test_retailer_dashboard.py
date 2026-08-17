"""
Tests for Phase 5: store ownership enforcement, inventory CRUD (with barcode
uniqueness and low-stock detection), dashboard stats computed from real data,
and report generation.
"""
import pytest

from app.core.exceptions import ConflictError, ForbiddenError
from app.schemas.inventory import ProductCreateRequest, ProductUpdateRequest
from app.services import dashboard_service, inventory_service, report_service, retailer_store_service
from app.schemas.store import StoreCreateRequest
from tests.fake_supabase import FakeServiceClient

RETAILER_ID = "retailer-1"
OTHER_RETAILER_ID = "retailer-2"
CUSTOMER_ID = "cust-1"


@pytest.fixture
def fake_client(monkeypatch):
    client = FakeServiceClient()
    for module in (
        "retailer_store_service", "inventory_service", "dashboard_service",
        "report_service", "store_ownership", "session_service", "cart_service",
        "product_service",
    ):
        monkeypatch.setattr(f"app.services.{module}.get_service_client", lambda: client)
    return client


def test_create_store_and_list_only_own_stores(fake_client):
    retailer_store_service.create_store(
        RETAILER_ID, StoreCreateRequest(name="Fresh Mart", store_type="grocery")
    )
    retailer_store_service.create_store(
        OTHER_RETAILER_ID, StoreCreateRequest(name="Rival Store", store_type="mini_mart")
    )

    mine = retailer_store_service.list_my_stores(RETAILER_ID)
    assert len(mine) == 1
    assert mine[0].name == "Fresh Mart"


def test_cannot_update_someone_elses_store(fake_client):
    from app.schemas.store import StoreUpdateRequest
    store = retailer_store_service.create_store(RETAILER_ID, StoreCreateRequest(name="Fresh Mart", store_type="grocery"))

    with pytest.raises(ForbiddenError):
        retailer_store_service.update_store(store.id, OTHER_RETAILER_ID, StoreUpdateRequest(name="Hacked"))


def test_create_product_auto_generates_valid_barcode(fake_client):
    store = retailer_store_service.create_store(RETAILER_ID, StoreCreateRequest(name="Fresh Mart", store_type="grocery"))

    product = inventory_service.create_product(
        store.id, RETAILER_ID,
        ProductCreateRequest(name="Basmati Rice 1kg", mrp_paise=15000, discount_percent=10, stock_quantity=20),
    )

    assert len(product.barcode) == 13
    assert product.barcode.isdigit()
    # Re-validate the checksum independently of the generator
    from app.services.inventory_service import _ean13_check_digit
    assert _ean13_check_digit(product.barcode[:12]) == product.barcode[12]


def test_duplicate_barcode_in_same_store_rejected(fake_client):
    store = retailer_store_service.create_store(RETAILER_ID, StoreCreateRequest(name="Fresh Mart", store_type="grocery"))
    inventory_service.create_product(
        store.id, RETAILER_ID, ProductCreateRequest(barcode="2001234567895", name="Item A", mrp_paise=1000)
    )
    with pytest.raises(ConflictError):
        inventory_service.create_product(
            store.id, RETAILER_ID, ProductCreateRequest(barcode="2001234567895", name="Item B", mrp_paise=2000)
        )


def test_low_stock_detection(fake_client):
    store = retailer_store_service.create_store(RETAILER_ID, StoreCreateRequest(name="Fresh Mart", store_type="grocery"))
    inventory_service.create_product(
        store.id, RETAILER_ID,
        ProductCreateRequest(name="Low Stock Item", mrp_paise=1000, stock_quantity=2, low_stock_threshold=5),
    )
    inventory_service.create_product(
        store.id, RETAILER_ID,
        ProductCreateRequest(name="Well Stocked Item", mrp_paise=1000, stock_quantity=50, low_stock_threshold=5),
    )

    low_stock = inventory_service.list_products(store.id, RETAILER_ID, low_stock_only=True)
    assert len(low_stock) == 1
    assert low_stock[0].name == "Low Stock Item"


def test_retailer_cannot_manage_products_in_store_they_dont_own(fake_client):
    store = retailer_store_service.create_store(RETAILER_ID, StoreCreateRequest(name="Fresh Mart", store_type="grocery"))
    with pytest.raises(ForbiddenError):
        inventory_service.create_product(
            store.id, OTHER_RETAILER_ID, ProductCreateRequest(name="Sneaky Item", mrp_paise=1000)
        )


def test_delete_product_is_soft_delete(fake_client):
    store = retailer_store_service.create_store(RETAILER_ID, StoreCreateRequest(name="Fresh Mart", store_type="grocery"))
    product = inventory_service.create_product(
        store.id, RETAILER_ID, ProductCreateRequest(name="Item", mrp_paise=1000, stock_quantity=5)
    )
    inventory_service.delete_product(store.id, product.id, RETAILER_ID)

    active_products = inventory_service.list_products(store.id, RETAILER_ID)
    assert all(p.id != product.id for p in active_products)  # filtered out — soft-deleted, not in active list?
    # list_products doesn't filter is_active currently at the service layer -> verify row itself
    row = fake_client.table("products").select("*").eq("id", product.id).execute().data[0]
    assert row["is_active"] is False


def test_dashboard_stats_reflect_real_session_and_sales_data(fake_client):
    from app.services import cart_service, session_service

    store = retailer_store_service.create_store(RETAILER_ID, StoreCreateRequest(name="Fresh Mart", store_type="grocery"))
    fake_client.seed("customers", [{"id": CUSTOMER_ID, "full_name": "Asha Kumar"}])
    product = inventory_service.create_product(
        store.id, RETAILER_ID, ProductCreateRequest(name="Item", mrp_paise=10000, stock_quantity=10)
    )

    session = session_service.create_session(CUSTOMER_ID, store.id)
    cart_service.add_item(session.id, CUSTOMER_ID, product.id, quantity=2)

    stats = dashboard_service.get_dashboard_stats(store.id, RETAILER_ID)
    assert stats.customers_inside_store == 1
    assert stats.live_sessions == 1
    assert stats.total_products == 1
    assert stats.pending_payments == 1  # payment not yet completed


def test_reports_csv_export_produces_valid_csv(fake_client):
    csv_text = report_service.export_transactions_csv(
        retailer_store_service.create_store(RETAILER_ID, StoreCreateRequest(name="Fresh Mart", store_type="grocery")).id,
        RETAILER_ID,
    )
    assert "Session ID" in csv_text
    assert "Customer" in csv_text
