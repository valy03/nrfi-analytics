"""Application configuration.

Values are read from environment variables (populated via .env in local
dev, or real environment variables in production per M12 deployment).
Nothing in this file should ever contain a real secret — see .env.example
at the repo root for the variables this expects.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    database_url: str = (
        "postgresql://nrfi:nrfi@localhost:5432/nrfi_analytics"
    )

    # External APIs (research.md decisions)
    openweather_api_key: str = ""
    odds_api_key: str = ""

    # CORS — frontend dev server by default
    cors_origins: list[str] = ["http://localhost:5173"]

    # Environment
    environment: str = "development"


@lru_cache
def get_settings() -> Settings:
    """Cached so we don't re-parse env vars on every request."""
    return Settings()
