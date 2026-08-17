"""
FastAPI application entrypoint.

Run locally with:
    uvicorn app.main:app --reload

Uses an application-factory pattern (`create_app`) rather than a bare module-level
`app = FastAPI()` so tests can construct isolated app instances with overridden
dependencies (see tests/test_auth.py) without import-order side effects.
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exceptions import QuickCartError
from app.core.rate_limit import limiter

import logging

logger = logging.getLogger("quickcart")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        description=(
            "QuickCart API — barcode self-checkout and AI-powered theft "
            "detection for offline supermarkets."
        ),
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(QuickCartError)
    def handle_quickcart_error(_: Request, exc: QuickCartError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})

    @app.exception_handler(Exception)
    def handle_unexpected_error(_: Request, exc: Exception) -> JSONResponse:
        """
        Catches anything not already a QuickCartError.

        This matters for two reasons, discovered together while building a
        real end-to-end integration test against this app (frontend +
        backend + fake Supabase, driven by a real browser): (1) an
        unhandled exception previously fell through to Starlette's default
        handler, which returns a bare 500 with no CORS headers — and a
        cross-origin response missing CORS headers is exactly what a
        browser reports as a confusing "CORS error", masking the real
        500 entirely; and (2) the default handler's response could leak
        internal details (in debug configurations) that production
        shouldn't expose. This handler fixes both: it always returns
        through the normal FastAPI/Starlette response path (so
        CORSMiddleware still adds its headers), and it never includes the
        exception's own message in the response body — only a generic
        message, with the real exception logged server-side for debugging.
        """
        logger.exception("Unhandled exception processing request: %s %s", _.method, _.url.path)
        return JSONResponse(status_code=500, content={"detail": "An unexpected error occurred"})

    app.include_router(api_router, prefix=settings.api_v1_prefix)

    @app.get("/health", tags=["System"], summary="Liveness check")
    def health() -> dict:
        return {"status": "ok", "service": settings.app_name, "env": settings.app_env}

    return app


app = create_app()
