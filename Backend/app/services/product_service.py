"""Product lookup, used by the barcode-scan product detail card (spec Step 4)."""
from app.core.exceptions import NotFoundError
from app.db.supabase_client import get_service_client
from app.schemas.product import ProductDetailResponse


def get_product_by_barcode(store_id: str, barcode: str) -> ProductDetailResponse:
    service = get_service_client()
    result = (
        service.table("products")
        .select("*")
        .eq("store_id", store_id)
        .eq("barcode", barcode)
        .eq("is_active", True)
        .execute()
    )
    if not result.data:
        raise NotFoundError("Product not found for this store")

    return _to_response(result.data[0])


def get_product_by_id(product_id: str) -> dict:
    """Returns the raw row — used internally by cart_service, which needs
    fields (store_id, stock_quantity) outside ProductDetailResponse's shape."""
    service = get_service_client()
    result = service.table("products").select("*").eq("id", product_id).execute()
    if not result.data:
        raise NotFoundError("Product not found")
    return result.data[0]


def _to_response(row: dict) -> ProductDetailResponse:
    return ProductDetailResponse(
        id=row["id"],
        barcode=row["barcode"],
        name=row["name"],
        brand=row.get("brand"),
        image_url=row.get("image_url"),
        description=row.get("description"),
        mrp_paise=row["mrp_paise"],
        discount_percent=float(row["discount_percent"]),
        price_paise=row["price_paise"],
        gst_percent=float(row["gst_percent"]),
        weight_value=row.get("weight_value"),
        weight_unit=row.get("weight_unit"),
        manufacture_date=row.get("manufacture_date"),
        expiry_date=row.get("expiry_date"),
        in_stock=row["stock_quantity"] > 0,
        stock_quantity=row["stock_quantity"],
    )
