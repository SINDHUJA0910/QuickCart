"""
Centralized application configuration.

All environment-dependent values are read exactly once here via pydantic-settings,
so the rest of the codebase imports `settings` instead of calling os.environ
directly. This keeps config typed, validated at startup, and easy to mock in tests.
"""
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- App ---
    app_name: str = "QuickCart API"
    app_env: str = "development"
    api_v1_prefix: str = "/api/v1"
    cors_origins: str = "http://localhost:5173"

    # --- Supabase ---
    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str
    supabase_jwt_secret: str

    # --- Payments (Phase 4) ---
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""

    # --- QR / crypto (Phase 4) ---
    qr_encryption_key: str = ""

    # --- Admin (Phase 7) ---
    # MVP-level protection for the "Optional" admin feature set: a single
    # shared secret checked against the X-Admin-Key header. Documented
    # explicitly as a placeholder — if admin features graduate from optional
    # to a real operational tool, this should become proper admin accounts
    # (a dedicated table + Supabase Auth role) with individual audit trails,
    # not a shared static key.
    admin_api_key: str = ""

    # --- Email (invoice delivery) ---
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = "receipts@quickcart.app"
    smtp_from_name: str = "QuickCart"

    @property
    def cors_origin_list(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance — env is read once per process."""
    return Settings()


settings = get_settings()
