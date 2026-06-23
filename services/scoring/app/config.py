from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    database_url: str = ""  # Set DATABASE_URL env var
    redis_url: str = "redis://localhost:6379/0"

    # How often to recompute scores for upcoming races (seconds)
    score_refresh_interval_s: int = 60

    # Minimum sample size before a component score is included
    min_gas_sample: int = 30
    min_bloodline_starters: int = 20
    min_trainer_runs: int = 10


settings = Settings()
