"""
A minimal in-memory fake of the subset of PostgREST's query-builder chain
QuickCart's services use (select/eq/is_/ilike/limit/insert/update/execute),
backed by a plain Python list of dicts per table. This is deliberately more
capable than the MagicMock-based fixtures in conftest.py's `patched_supabase`
(which is fine for auth's simpler single-lookup calls) because
store/session/cart services chain multiple `.eq()`/`.is_()` filters and
expect insert/update to actually mutate state that a subsequent call reads
back — a MagicMock returning a fixed value can't model that.
"""
from __future__ import annotations

import uuid
from copy import deepcopy

from postgrest.exceptions import APIError


class FakeTable:
    def __init__(self, store: dict, name: str):
        self._store = store
        self._name = name
        self._filters: list[tuple[str, str, object]] = []  # (field, op, value)
        self._select_relations: list[str] = []
        self._limit_n: int | None = None
        self._pending_insert: dict | None = None
        self._pending_update: dict | None = None
        self._single = False

    # --- query builder chain ---
    def select(self, columns: str = "*"):
        for part in columns.split(","):
            part = part.strip()
            if "(" in part:
                self._select_relations.append(part.split("(")[0].strip())
        return self

    def eq(self, field: str, value):
        self._filters.append((field, "eq", value))
        return self

    def is_(self, field: str, value):
        self._filters.append((field, "is", value))
        return self

    def ilike(self, field: str, pattern: str):
        self._filters.append((field, "ilike", pattern.strip("%").lower()))
        return self

    def limit(self, n: int):
        self._limit_n = n
        return self

    def single(self):
        self._single = True
        return self

    def insert(self, payload: dict):
        self._pending_insert = payload
        return self

    def update(self, payload: dict):
        self._pending_update = payload
        return self

    # --- execution ---
    def execute(self):
        rows = self._store.setdefault(self._name, [])

        if self._pending_insert is not None:
            row = deepcopy(self._pending_insert)
            row.setdefault("id", str(uuid.uuid4()))
            row.setdefault("created_at", "2026-08-05T10:00:00+00:00")
            if self._name == "shopping_sessions":
                row.setdefault("status", "active")
                row.setdefault("payment_status", "pending")
                row.setdefault("exit_status", "not_exited")
                row.setdefault("entry_time", "2026-08-05T10:00:00+00:00")
            if self._name == "cart_items":
                row.setdefault("removed_at", None)
            if self._name in ("stores", "products"):
                row.setdefault("is_active", True)  # matches Postgres schema DEFAULT true
            self._apply_generated_columns(row)
            rows.append(row)
            return _Result([deepcopy(row)])

        matched = [r for r in rows if self._matches(r)]

        if self._pending_update is not None:
            for r in matched:
                r.update(self._pending_update)
                self._apply_generated_columns(r)
            return _Result([deepcopy(r) for r in matched])

        matched = [self._attach_relations(r) for r in matched]
        if self._limit_n is not None:
            matched = matched[: self._limit_n]

        if self._single:
            return _Result(matched[0] if matched else None)
        return _Result(matched)

    def _matches(self, row: dict) -> bool:
        for field, op, value in self._filters:
            row_value = row.get(field)
            if op == "eq" and row_value != value:
                return False
            if op == "is" and value == "null" and row_value is not None:
                return False
            if op == "ilike" and (row_value is None or value not in str(row_value).lower()):
                return False
        return True

    def _apply_generated_columns(self, row: dict) -> None:
        """Mirrors Postgres GENERATED ALWAYS AS columns that real inserts/updates
        compute automatically — currently just products.price_paise."""
        if self._name == "products" and "mrp_paise" in row:
            discount = row.get("discount_percent", 0) or 0
            row["price_paise"] = round(row["mrp_paise"] * (1 - discount / 100.0))
        if self._name == "cctv_cameras":
            row.setdefault("status", "offline")
            row.setdefault("zone_config", [])
        if self._name == "ai_alerts":
            row.setdefault("status", "open")
            row.setdefault("detected_at", "2026-08-05T10:00:00+00:00")

    def _attach_relations(self, row: dict) -> dict:
        row = deepcopy(row)
        relation_fk = {
            "stores": ("store_id", "stores"),
            "products": ("product_id", "products"),
            "customers": ("customer_id", "customers"),
            "shopping_sessions": ("session_id", "shopping_sessions"),
        }
        for relation in self._select_relations:
            if relation not in relation_fk:
                continue
            fk_field, table_name = relation_fk[relation]
            related = next(
                (r for r in self._store.get(table_name, []) if r["id"] == row.get(fk_field)), None
            )
            row[relation] = deepcopy(related) if related else None
        return row


class _Result:
    def __init__(self, data):
        self.data = data


class FakeStorageBucket:
    def __init__(self, files: dict):
        self._files = files

    def upload(self, path: str, data: bytes, options: dict | None = None):
        self._files[path] = data
        return {"path": path}

    def get_public_url(self, path: str) -> str:
        return f"https://fake-storage.local/invoices/{path}"


class FakeStorage:
    def __init__(self):
        self._buckets: dict[str, dict] = {}

    def from_(self, bucket: str) -> FakeStorageBucket:
        files = self._buckets.setdefault(bucket, {})
        return FakeStorageBucket(files)


class FakeRPC:
    """Simulates the subset of RPC behavior QuickCart relies on: currently
    just adjust_product_stock, mirroring migration 0005's atomic UPDATE +
    floor-check semantics (raises the same 'insufficient_stock' error text
    the real Postgres function raises, so callers' except-clauses are
    exercised identically to production)."""

    def __init__(self, store: dict, function_name: str, params: dict):
        self._store = store
        self._function_name = function_name
        self._params = params

    def execute(self):
        if self._function_name == "adjust_product_stock":
            product_id = self._params["p_product_id"]
            delta = self._params["p_delta"]
            products = self._store.setdefault("products", [])
            product = next((p for p in products if p["id"] == product_id), None)
            if product is None:
                raise APIError({"message": "product not found"})

            new_quantity = product["stock_quantity"] + delta
            if new_quantity < 0:
                raise APIError({"message": "insufficient_stock"})

            product["stock_quantity"] = new_quantity
            return _Result(deepcopy(product))

        raise NotImplementedError(f"FakeRPC does not simulate '{self._function_name}'")


class FakeServiceClient:
    """Drop-in replacement for the Supabase service client used by store/session/cart services."""
    def __init__(self):
        self._store: dict[str, list[dict]] = {}
        self.storage = FakeStorage()

    def table(self, name: str) -> FakeTable:
        return FakeTable(self._store, name)

    def rpc(self, function_name: str, params: dict) -> FakeRPC:
        return FakeRPC(self._store, function_name, params)

    def seed(self, table: str, rows: list[dict]) -> None:
        """Adds rows directly, bypassing the insert/update path — so any
        Postgres-computed generated column (currently just
        products.price_paise) must be applied here too, or seeded rows
        would silently lack a field every real row always has. This bit a
        manual integration-testing harness in development (see git history
        around Phase 6/frontend integration) with a real KeyError at
        runtime — worth keeping this explicit rather than assuming seed()
        and insert() can drift."""
        rows = [deepcopy(r) for r in rows]
        if table == "products":
            for row in rows:
                if "mrp_paise" in row and "price_paise" not in row:
                    discount = row.get("discount_percent", 0) or 0
                    row["price_paise"] = round(row["mrp_paise"] * (1 - discount / 100.0))
        self._store.setdefault(table, []).extend(rows)
