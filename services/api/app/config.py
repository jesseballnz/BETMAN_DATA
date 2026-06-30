from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(ROOT_DIR / ".env", ".env"),
        extra="ignore",
    )

    api_version: str = "1.0.0"
    api_root_path: str = ""
    environment: str = "development"
    log_level: str = "info"

    # PostgreSQL
    database_url: str = "******localhost:5432/betman"
    warehouse_snapshot_path: str = str(ROOT_DIR / "config" / "warehouse_sources.json")

    # Redis (pub/sub for WebSocket live stream)
    redis_url: str = "redis://localhost:6379/0"

    # Media / CDN
    media_base_url: str = "http://localhost:9000/betman-media"
    cdn_base_url: str = "http://localhost:9000/betman-media"

    # Security
    admin_api_key: str = ""
    platform_master_key: str = ""
    metrics_public: bool = False

    # CORS
    cors_origins: str = "http://localhost:5173,http://localhost:8080"
    rate_limit_requests: int = 120
    rate_limit_window_seconds: int = 60
    rate_limit_default_daily_quota: int = 10_000
    websocket_heartbeat_seconds: int = 15

    # Assistant / LLM
    openai_api_key: str = ""
    betman_llm_model: str = "gpt-4o-mini"

    @property
    def cors_origins_list(self) -> list[str]:
        if not self.cors_origins:
            return ["http://localhost:5173", "http://localhost:8080"]
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def cors_allow_credentials(self) -> bool:
        return "*" not in self.cors_origins_list

    @property
    def hsts_enabled(self) -> bool:
        return self.environment.lower() not in {"development", "dev", "local"}


settings = Settings()
