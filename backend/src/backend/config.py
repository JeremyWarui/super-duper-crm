"""Settings, read from the environment and from `.env`."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

# Schemes libpq and hosted Postgres consoles hand out.
LIBPQ_SCHEMES = ("postgres", "postgresql")


def asyncpg_dsn(value: str) -> str:
    """A Postgres URL as asyncpg reads it: driver named, `sslmode` as `ssl`, `channel_binding` gone.

    An explicit `ssl` wins over `sslmode`. Other databases pass through untouched.
    """
    url = make_url(value)
    if url.drivername in LIBPQ_SCHEMES:
        url = url.set(drivername="postgresql+asyncpg")
    if url.drivername != "postgresql+asyncpg":
        return value
    query = dict(url.query)
    sslmode = query.pop("sslmode", None)
    query.pop("channel_binding", None)
    if sslmode is not None:
        query.setdefault("ssl", sslmode)
    return url.set(query=query).render_as_string(hide_password=False)


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

    # A built SPA served at "/"; blank serves the API alone.
    static_dir: str = ""

    # Where uploaded files are kept; created on first upload.
    upload_dir: str = "uploads"

    # Where `campaign-crm backup` writes its archives; 14 daily and 8 weekly are kept.
    backup_dir: str = "backups"
    # The folder holding pg_dump and pg_restore; blank finds them on PATH.
    pg_bin_dir: str = ""

    # Seconds between runs applying public party requests to the register; 0 switches it off.
    party_inbox_seconds: int = 60
    # How often the payments ledger is compared with the payout provider; 0 turns it off.
    reconcile_hours: int = 24

    # One password for every account the app creates; blank generates one each.
    default_user_password: str = ""

    # "console" records and sends nothing.
    at_username: str = ""
    at_api_key: str = ""
    # Blank uses the shared short code.
    at_sender_id: str = ""
    at_sandbox: bool = False
    sms_provider: Literal["console", "africastalking"] = "console"
    # The secret part of the delivery-report and inbound-text URLs given to Africa's Talking,
    # which does not sign its callbacks; blank turns the callbacks off.
    sms_callback_secret: str = ""

    # Where people open the app; sign-in links in emails and texts start with it.
    public_url: str = "http://localhost:5173"

    # "practice" records each email in email_log and sends nothing.
    email_provider: Literal["practice", "smtp"] = "practice"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""

    # Webhook signing secret (whsec_...) from the Paystack dashboard; blank checks the
    # older x-paystack-signature header against the secret key instead.
    paystack_webhook_secret: str = ""
    paystack_secret_key: str = ""
    # "practice" moves no money; "paystack" sends M-Pesa transfers for party and campaign payments.
    payout_provider: Literal["practice", "paystack"] = "practice"

    @field_validator("payout_provider", mode="after")
    @classmethod
    def _paystack_needs_a_key(cls, value: str, info: ValidationInfo) -> str:
        if value == "paystack" and not info.data.get("paystack_secret_key"):
            raise ValueError("PAYOUT_PROVIDER=paystack needs PAYSTACK_SECRET_KEY.")
        return value

    @field_validator("email_provider", mode="after")
    @classmethod
    def _smtp_needs_a_server(cls, value: str, info: ValidationInfo) -> str:
        if value == "smtp" and not (info.data.get("smtp_host") and info.data.get("smtp_from")):
            raise ValueError("EMAIL_PROVIDER=smtp needs SMTP_HOST and SMTP_FROM.")
        return value

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
            return asyncpg_dsn(value)
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
    """The DSN with `%` doubled, since Alembic reads it through configparser."""
    return get_settings().database_url.replace("%", "%%")
