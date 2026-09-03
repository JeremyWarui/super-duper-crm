"""Runtime settings, read from the environment (and `.env` in development).

Replaces `config/settings.py`. Everything Django needed a settings module for
(installed apps, middleware, template engines, password validators) is either
gone with Django or lives in `main.py` now, so this file holds only what the
process genuinely reads at boot.
"""

from functools import lru_cache

from pydantic import Field, PostgresDsn, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    debug: bool = False

    # Secret used to sign tokens/sessions. No default: a hardcoded fallback is
    # how the Django scaffold shipped a live-looking key in source control.
    secret_key: str = Field(min_length=32)

    # Individual parts, kept because .env already carries them.
    db_name: str = "campaign_crm"
    db_user: str = "root"
    db_password: str = ""
    db_host: str = "localhost"
    db_port: int = 26257

    # Set DATABASE_URL to override the parts above wholesale. Use
    # `cockroachdb+asyncpg://` with the `cockroachdb` extra installed to get
    # CockroachDB's retry/savepoint handling; `postgresql+asyncpg://` works for
    # plain Postgres and for basic CockroachDB use.
    database_url: str = ""

    # Origins allowed to call this API from a browser (the Vite dev server).
    cors_allow_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    echo_sql: bool = False

    @field_validator("database_url", mode="after")
    @classmethod
    def _assemble_database_url(cls, value: str, info: ValidationInfo) -> str:
        if value:
            return value
        d = info.data
        dsn = PostgresDsn.build(
            scheme="postgresql+asyncpg",
            username=d.get("db_user"),
            password=d.get("db_password") or None,
            host=d.get("db_host"),
            port=d.get("db_port"),
            path=d.get("db_name"),
        )
        return str(dsn)


@lru_cache
def get_settings() -> Settings:
    """Cached so the environment is read once per process."""
    return Settings()  # type: ignore[call-arg]
