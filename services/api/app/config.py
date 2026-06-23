from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    api_version: str = "1.0.0"
    api_root_path: str = ""
    environment: str = "development"
    log_level: str = "info"

    # PostgreSQL
    database_url: str = "******localhost:5432/betman"

    # Redis (pub/sub for WebSocket live stream)
    redis_url: str = "redis://localhost:6379/0"

    # Media / CDN
    media_base_url: str = "http://localhost:9000/betman-media"
    cdn_base_url: str = "http://localhost:9000/betman-media"

    # Security
    admin_api_key: str = "dev-admin-key-change-in-production"
    platform_master_key: str = ""

    # CORS
    cors_origins: list[str] = ["*"]


settings = Settings()
