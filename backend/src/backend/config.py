"""Settings, read from the environment and from `.env`."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    debug: bool = False

    # No default, so it cannot be forgotten.
    secret_key: str = Field(min_length=32)

    db_name: str = "campaign_crm"
    db_user: str = "postgres"
    db_password: str = ""
    db_host: str = "localhost"
    db_port: int = 5432

    # A full DSN, which overrides the DB_* parts above.
    database_url: str = ""

    # Browser origins allowed to call this API.
    cors_allow_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # Log every SQL statement.
    echo_sql: bool = False

    # Whether POST /api/auth/register/ answers. Off closes self-serve sign-up
    # without a deploy, leaving the invite routes working.
    allow_registration: bool = True

    # Given to every account the app creates, instead of a generated password.
    # Blank generates one per account, which is the only safe setting outside a demo.
    default_user_password: str = ""

    # "console" records and sends nothing.
    at_username: str = ""
    at_api_key: str = ""
    # Blank uses the shared short code.
    at_sender_id: str = ""
    at_sandbox: bool = False
    sms_provider: Literal["console", "africastalking"] = "console"

    @field_validator("sms_provider", mode="after")
    @classmethod
    def _gateway_needs_credentials(cls, value: str, info: ValidationInfo) -> str:
        """Fail at startup rather than on the first invitation."""
        if value == "africastalking" and not (
            info.data.get("at_username") and info.data.get("at_api_key")
        ):
            raise ValueError("SMS_PROVIDER=africastalking needs AT_USERNAME and AT_API_KEY.")
        return value

    @field_validator("database_url", mode="after")
    @classmethod
    def _assemble_database_url(cls, value: str, info: ValidationInfo) -> str:
        """Build the DSN from the DB_* parts when DATABASE_URL is not set."""
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
    """Read once per process."""
    return Settings()  # type: ignore[call-arg]


def alembic_url() -> str:
    """The DSN with every `%` doubled.

    Alembic holds it in a configparser, which reads `%` as interpolation, and a
    password containing `@`, `%`, `:` or `/` arrives percent-encoded.
    """
    return get_settings().database_url.replace("%", "%%")
