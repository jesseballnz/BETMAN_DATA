from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    database_url: str = ""  # Set DATABASE_URL env var
    redis_url: str = "redis://localhost:6379/0"

    # Cron-style schedule: run discovery at 02:00 UTC daily
    run_hour_utc: int = 2

    # Minimum ROI threshold to persist a discovered pattern (%)
    min_roi_to_persist: float = 0.05

    # Minimum statistical confidence to persist a pattern (0–1)
    min_confidence: float = 0.70

    # Lookback window for pattern detection (days)
    lookback_days: int = 90

    # Minimum sample size for a pattern to be considered
    min_sample_size: int = 30


settings = Settings()
