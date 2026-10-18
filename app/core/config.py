"""Environment-backed application settings."""

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_DATABASE_URL = "postgresql+psycopg://localhost/kanban"


def normalize_database_url(url: str) -> str:
    """Make a Postgres URL use the psycopg 3 driver.

    Supabase hands out ``postgresql://`` (or ``postgres://``) URIs. SQLAlchemy
    needs the driver name, so the prefix is rewritten.

    Args:
        url: A database URL as given by the user.

    Returns:
        The URL with a ``postgresql+psycopg://`` scheme when it was plain Postgres.

    """
    for prefix in ("postgresql://", "postgres://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url.removeprefix(prefix)
    return url


class Settings(BaseSettings):
    """Settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = Field(default=DEFAULT_DATABASE_URL)
    database_pool_size: int = Field(default=5, ge=1)
    database_max_overflow: int = Field(default=10, ge=0)
    database_pool_timeout: float = Field(default=30, gt=0)

    @field_validator("database_url")
    @classmethod
    def _normalize_url(cls, value: str) -> str:
        return normalize_database_url(value)


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings.

    Returns:
        The cached environment-backed settings.

    """
    return Settings()
