"""
Aggregates all v1 endpoint routers into a single router mounted by main.py.

Adding a new resource in a later phase (products, sessions, payments...) means
creating app/api/v1/endpoints/<resource>.py and adding one line here — routes
never get registered directly on the FastAPI app instance in main.py, keeping
main.py stable as the API surface grows.
"""
from fastapi import APIRouter

from app.api.v1.endpoints import (
    admin,
    ai_alerts,
    ai_ingest,
    auth_customer,
    auth_retailer,
    cameras,
    cart,
    checkout,
    dashboard,
    exit as exit_endpoint,
    inventory,
    notifications,
    products,
    reports,
    retailer_stores,
    sessions,
    stores,
)

api_router = APIRouter()

api_router.include_router(auth_customer.router)
api_router.include_router(auth_retailer.router)
api_router.include_router(stores.router)
api_router.include_router(sessions.router)
api_router.include_router(products.router)
api_router.include_router(cart.router)
api_router.include_router(checkout.router)
api_router.include_router(exit_endpoint.router)
api_router.include_router(retailer_stores.router)
api_router.include_router(inventory.router)
api_router.include_router(dashboard.router)
api_router.include_router(reports.router)
api_router.include_router(cameras.router)
api_router.include_router(ai_alerts.router)
api_router.include_router(ai_ingest.router)
api_router.include_router(notifications.router)
api_router.include_router(admin.router)

# Phase 8: deployment, additional hardening — no new routers expected.
