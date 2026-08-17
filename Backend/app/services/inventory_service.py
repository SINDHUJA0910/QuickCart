"""
Inventory management.

Barcode generation produces a real, valid EAN-13 code (12 digits + a
correctly computed checksum digit), not a random number — an invalid check
digit would make the code unreadable/rejected by real barcode scanners
(ZXing included), defeating the point of the "Barcode Generation" feature.
"""
import random

from app.core.exceptions import ConflictError, NotFoundError
from app.db.supabase_client import get_service_client
from app.schemas.inventory import (
    CategoryCreateRequest,
    CategoryResponse,
    ProductCreateRequest,
    ProductUpdateRequest,
    RetailerProductResponse,
)
from app.services.store_ownership import verify_store_ownership

# A private-label prefix range (200-299) is reserved by GS1 for in-store use —
# exactly the use case here (retailer-generated codes for unbarcoded products).
EAN13_PRIVATE_PREFIX = "20"


def _ean13_check_digit(digits12: str) -> str:
    total = 0
    for i, ch in enumerate(digits12):
        n = int(ch)
        total += n * (3 if i % 2 == 1 else 1)
    return str((10 - (total % 10)) % 10)


def generate_ean13_barcode() -> str:
    body = EAN13_PRIVATE_PREFIX + "".join(str(random.randint(0, 9)) for _ in range(10))
    return body + _ean13_check_digit(body)


def _to_response(row: dict) -> RetailerProductResponse:
    return RetailerProductResponse(
        id=row["id"],
        barcode=row["barcode"],
        name=row["name"],
        brand=row.get("brand"),
        category_id=row.get("category_id"),
        image_url=row.get("image_url"),
        mrp_paise=row["mrp_paise"],
        discount_percent=float(row["discount_percent"]),
        price_paise=row["price_paise"],
        gst_percent=float(row["gst_percent"]),
        stock_quantity=row["stock_quantity"],
        low_stock_threshold=row["low_stock_threshold"],
        is_low_stock=row["stock_quantity"] <= row["low_stock_threshold"],
        supplier_name=row.get("supplier_name"),
        expiry_date=row.get("expiry_date"),
        is_active=row["is_active"],
    )


def create_product(store_id: str, retailer_id: str, payload: ProductCreateRequest) -> RetailerProductResponse:
    service = get_service_client()
    verify_store_ownership(store_id, retailer_id)

    data = payload.model_dump()
    data["store_id"] = store_id
    if not data.get("barcode"):
        data["barcode"] = generate_ean13_barcode()

    existing = (
        service.table("products").select("id").eq("store_id", store_id).eq("barcode", data["barcode"]).execute()
    )
    if existing.data:
        raise ConflictError("A product with this barcode already exists in this store")

    result = service.table("products").insert(data).execute()
    return _to_response(result.data[0])


def update_product(
    store_id: str, product_id: str, retailer_id: str, payload: ProductUpdateRequest
) -> RetailerProductResponse:
    service = get_service_client()
    verify_store_ownership(store_id, retailer_id)

    existing = service.table("products").select("id").eq("id", product_id).eq("store_id", store_id).execute()
    if not existing.data:
        raise NotFoundError("Product not found in this store")

    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    if updates:
        service.table("products").update(updates).eq("id", product_id).execute()

    result = service.table("products").select("*").eq("id", product_id).execute()
    return _to_response(result.data[0])


def delete_product(store_id: str, product_id: str, retailer_id: str) -> None:
    """Soft delete (is_active=False) rather than a hard DELETE — preserves
    referential integrity with historical cart_items/order records that
    reference this product."""
    service = get_service_client()
    verify_store_ownership(store_id, retailer_id)

    existing = service.table("products").select("id").eq("id", product_id).eq("store_id", store_id).execute()
    if not existing.data:
        raise NotFoundError("Product not found in this store")

    service.table("products").update({"is_active": False}).eq("id", product_id).execute()


def list_products(
    store_id: str, retailer_id: str, low_stock_only: bool = False, include_inactive: bool = False
) -> list[RetailerProductResponse]:
    service = get_service_client()
    verify_store_ownership(store_id, retailer_id)

    query = service.table("products").select("*").eq("store_id", store_id)
    if not include_inactive:
        query = query.eq("is_active", True)
    result = query.execute()
    rows = result.data or []
    products = [_to_response(row) for row in rows]
    if low_stock_only:
        products = [p for p in products if p.is_low_stock]
    return products


def create_category(store_id: str, retailer_id: str, payload: CategoryCreateRequest) -> CategoryResponse:
    service = get_service_client()
    verify_store_ownership(store_id, retailer_id)

    data = payload.model_dump()
    data["store_id"] = store_id
    result = service.table("categories").insert(data).execute()
    row = result.data[0]
    return CategoryResponse(id=row["id"], name=row["name"], parent_id=row.get("parent_id"))


def list_categories(store_id: str, retailer_id: str) -> list[CategoryResponse]:
    service = get_service_client()
    verify_store_ownership(store_id, retailer_id)

    result = service.table("categories").select("*").eq("store_id", store_id).execute()
    return [CategoryResponse(id=r["id"], name=r["name"], parent_id=r.get("parent_id")) for r in (result.data or [])]
