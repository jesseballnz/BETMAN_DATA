from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    version: str = "1.0.0"

    # PostgreSQL
    database_url: str = "******localhost:5432/betman"

    # Redis — live state store and task queue
    redis_url: str = "redis://localhost:6379/0"
    queue_url: str = "redis://localhost:6379/1"

    # Object storage (S3-compatible)
    storage_base_path: str = "s3://betman-media"
    storage_region: str = "ap-southeast-2"

    # HLS feed polling
    hls_poll_interval_s: float = 2.0
    hls_segment_timeout_s: float = 10.0
    hls_max_retries: int = 3

    # Race data polling
    race_data_poll_interval_s: float = 30.0

    # Odds polling
    odds_poll_interval_s: float = 10.0
    odds_steam_threshold_pct: float = 20.0   # % firming to flag as steam
    odds_blowout_threshold_pct: float = 20.0  # % drifting to flag as blowout
    odds_late_firm_window_s: int = 600        # 10 mins before jump = "late"

    # WeatherLink polling
    weatherlink_poll_interval_s: float = 60.0
    weatherlink_base_url: str = "https://api.weatherlink.com/v2"
    # Master key for decrypting api_key_configs.encrypted_key (set via env)
    platform_master_key: str = ""

    # Processing queue names
    ocr_queue_name: str = "betman.ocr"
    audio_queue_name: str = "betman.audio"
    ingest_queue_name: str = "betman.ingest"

    # Barrier analysis
    barrier_stats_rebuild_on_result: bool = True


settings = Settings()
