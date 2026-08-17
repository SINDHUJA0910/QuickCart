"""
Cart service.

Two invariants matter more than the CRUD itself:

1. Price snapshotting: `cart_items.unit_price_paise` is copied from the
   product's current price at the moment of adding, not looked up live at
   checkout. If a retailer changes a price mid-shop, everyone already
   shopping keeps the price they scanned at — which is both the fair
   customer experience and the only sane way to make the eventual invoice
   reproducible.

2. Live inventory sync: adding an item decrements `products.stock_quantity`
   immediately (not at checkout), and removing/reducing an item restores it.
   This models the physical reality that the product has already left the
   shelf — and it's the signal Phase 6's AI theft logic compares physical
   shelf activity against ("was everything picked up also scanned?").

Stock adjustments call the `adjust_product_stock` Postgres RPC (migration
0005) rather than a read-then-write from application code — the increment
and the "don't go below zero" floor check happen in one atomic UPDATE
statement, so concurrent scans of the same product are serialized correctly
by Postgres's own row locking instead of racing in Python.
"""
from postgrest.exceptions import APIError

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.db.supabase_client import get_service_client
from app.schemas.cart import CartItemResponse, CartSummaryResponse
from app.services import notification_service, product_service, session_service
from app.utils.time import utcnow_iso


def _notify_if_stock_threshold_crossed(product: dict, new_quantity: int) -> None:
    """Fires a low_stock/out_of_stock notification exactly at the moment
    stock crosses the threshold — not on a periodic scan — so retailers see
    it as it happens rather than discovering it later on a dashboard refresh."""
    service = get_service_client()
    store = service.table("stores").select("retailer_id").eq("id", product["store_id"]).execute()
    if not store.data or not store.data[0].get("retailer_id"):
        return
    retailer_id = store.data[0]["retailer_id"]

    if new_quantity == 0:
        notification_service.create_notification(
            recipient_type="retailer",
            recipient_id=retailer_id,
            title=f"Out of stock: {product['name']}",
            category="out_of_stock",
            related_id=product["id"],
        )
    elif new_quantity <= product.get("low_stock_threshold", 5):
        notification_service.create_notification(
            recipient_type="retailer",
            recipient_id=retailer_id,
            title=f"Low stock: {product['name']} ({new_quantity} left)",
            category="low_stock",
            related_id=product["id"],
        )


def _adjust_stock(product_id: str, delta: int) -> None:
    """delta > 0 restores stock (item removed/reduced); delta < 0 consumes stock (item added/increased).
    Calls the atomic adjust_product_stock RPC (migration 0005) instead of a
    read-then-write, so concurrent scans of the same product can't race."""
    service = get_service_client()
    try:
        result = service.rpc(
            "adjust_product_stock", {"p_product_id": product_id, "p_delta": delta}
        ).execute()
    except APIError as exc:
        if "insufficient_stock" in str(exc):
            raise ConflictError("Not enough stock available for the requested quantity") from exc
        raise

    product = result.data
    if delta < 0:  # only notify when stock is being consumed, not restored
        _notify_if_stock_threshold_crossed(product, product["stock_quantity"])


def _active_session_or_raise(session_id: str, customer_id: str) -> dict:
    session = session_service.get_session_or_raise(session_id, customer_id)
    if session["status"] != "active":
        raise ConflictError("This shopping session is no longer active")
    return session


def add_item(session_id: str, customer_id: str, product_id: str, quantity: int) -> CartSummaryResponse:
    service = get_service_client()
    session = _active_session_or_raise(session_id, customer_id)

    product = product_service.get_product_by_id(product_id)
    if product["store_id"] != session["store_id"]:
        raise ForbiddenError("This product does not belong to the store for this session")

    existing = (
        service.table("cart_items")
        .select("*")
        .eq("session_id", session_id)
        .eq("product_id", product_id)
        .is_("removed_at", "null")
        .execute()
    )

    _adjust_stock(product_id, -quantity)

    if existing.data:
        item = existing.data[0]
        new_qty = item["quantity"] + quantity
        service.table("cart_items").update({"quantity": new_qty}).eq("id", item["id"]).execute()
    else:
        service.table("cart_items").insert(
            {
                "session_id": session_id,
                "product_id": product_id,
                "quantity": quantity,
                "unit_price_paise": product["price_paise"],
            }
        ).execute()

    return get_cart_summary(session_id, customer_id)


def update_item_quantity(session_id: str, customer_id: str, item_id: str, new_quantity: int) -> CartSummaryResponse:
    service = get_service_client()
    _active_session_or_raise(session_id, customer_id)

    result = service.table("cart_items").select("*").eq("id", item_id).eq("session_id", session_id).execute()
    if not result.data:
        raise NotFoundError("Cart item not found")
    item = result.data[0]

    delta = item["quantity"] - new_quantity  # positive delta = reducing quantity = restore stock
    _adjust_stock(item["product_id"], delta)

    service.table("cart_items").update({"quantity": new_quantity}).eq("id", item_id).execute()
    return get_cart_summary(session_id, customer_id)


def remove_item(session_id: str, customer_id: str, item_id: str) -> CartSummaryResponse:
    service = get_service_client()
    _active_session_or_raise(session_id, customer_id)

    result = service.table("cart_items").select("*").eq("id", item_id).eq("session_id", session_id).execute()
    if not result.data:
        raise NotFoundError("Cart item not found")
    item = result.data[0]

    _adjust_stock(item["product_id"], item["quantity"])  # restore stock
    service.table("cart_items").update({"removed_at": utcnow_iso()}).eq("id", item_id).execute()

    return get_cart_summary(session_id, customer_id)


def get_cart_summary(session_id: str, customer_id: str) -> CartSummaryResponse:
    service = get_service_client()
    session_service.get_session_or_raise(session_id, customer_id)  # ownership check, any status

    result = (
        service.table("cart_items")
        .select("*, products(name, image_url, mrp_paise, gst_percent)")
        .eq("session_id", session_id)
        .is_("removed_at", "null")
        .execute()
    )

    items: list[CartItemResponse] = []
    subtotal = discount = gst = 0

    for row in result.data or []:
        product = row.get("products") or {}
        qty = row["quantity"]
        unit_price = row["unit_price_paise"]
        mrp = product.get("mrp_paise", unit_price)
        gst_percent = float(product.get("gst_percent", 0))

        line_total = unit_price * qty
        subtotal += mrp * qty
        discount += (mrp - unit_price) * qty
        gst += round(line_total * gst_percent / 100)

        items.append(
            CartItemResponse(
                id=row["id"],
                product_id=row["product_id"],
                product_name=product.get("name", ""),
                product_image_url=product.get("image_url"),
                quantity=qty,
                unit_price_paise=unit_price,
                line_total_paise=line_total,
            )
        )

    total = subtotal - discount + gst

    return CartSummaryResponse(
        session_id=session_id,
        items=items,
        item_count=sum(i.quantity for i in items),
        subtotal_paise=subtotal,
        discount_paise=discount,
        gst_paise=gst,
        total_paise=total,
    )
