from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

WORKSPACE_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Server-side configuration loaded without exposing secret values."""

    model_config = SettingsConfigDict(
        env_file=WORKSPACE_ROOT / ".env.local",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    caresignal_env: str = "development"
    caresignal_cors_origins: str = "http://localhost:3000"
    caresignal_database_url: str = "sqlite:///./caresignal.db"
    caresignal_auto_bootstrap: bool = True
    caresignal_demo_reset_enabled: bool = True
    caresignal_demo_reset_token: str = "local-demo-reset"
    caresignal_bp_systolic_min: int = 40
    caresignal_bp_systolic_max: int = 300
    caresignal_bp_diastolic_min: int = 20
    caresignal_bp_diastolic_max: int = 200
    openai_api_key: str | None = None
    openai_model: str = "gpt-5.6"
    openai_timeout_seconds: float = 15.0
    whatsapp_cloud_api_enabled: bool = False
    whatsapp_cloud_api_version: str = "v23.0"
    whatsapp_phone_number_id: str | None = None
    whatsapp_access_token: str | None = None
    whatsapp_verify_token: str | None = None
    whatsapp_app_secret: str | None = None
    whatsapp_demo_phone_map: str = "{}"

    @property
    def cors_origins(self) -> list[str]:
        return [
            origin.strip() for origin in self.caresignal_cors_origins.split(",") if origin.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()
