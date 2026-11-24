"""Settings, read from the environment and from `.env`."""

from datetime import date, time
from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

# Schemes libpq and managed Postgres consoles hand out.
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
    sms_provider: Literal["console", "africastalking", "sozuri"] = "console"
    # The secret part of the delivery-report and inbound-text URLs given to the gateway;
    # blank turns the callbacks off.
    sms_callback_secret: str = ""

    # Sozuri: a project name and its API key. Testing uses a separate project with its own key.
    sozuri_api_key: str = ""
    sozuri_project: str = ""
    sozuri_sender_id: str = ""
    # "promotional" or "transactional", as the sender ID is registered.
    sozuri_message_type: Literal["promotional", "transactional"] = "promotional"
    # The webhook signing secret (szs_...); callbacks are refused without it.
    sozuri_signing_secret: str = ""
    # The project's webhook auth key (szk_...); when set, a callback's authKey must match it.
    sozuri_auth_key: str = ""

    # Bulk texts go out only inside this daily window, Nairobi time, and never wider than
    # 08:00 to 18:00; and inside the campaign period when one is set.
    sms_window: str = "08:00-18:00"
    # At most 500: one batch is one request to the gateway, under one idempotency key.
    sms_batch_size: int = Field(default=500, ge=1, le=500)
    sms_max_attempts: int = 3
    # What one SMS part costs, in KES cents, for the run's cost estimate.
    sms_part_price_cents: int = 80
    campaign_period_start: date | None = None
    campaign_period_end: date | None = None
    # A run waits for a vetting reference before it sends.
    sms_vetting_required: bool = False
    # Sent as a bearer token by the scheduler that drains the SMS queue; blank turns the route off.
    cron_secret: str = ""

    # Online meetings; blank turns meetings off.
    livekit_url: str = ""
    livekit_api_key: str = ""
    livekit_api_secret: str = ""

    # Web push for call alerts; `campaign-crm make-vapid-keys` prints a pair.
    vapid_public_key: str = ""
    vapid_private_key: str = ""
    vapid_subject: str = ""

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
    # "practice" moves no money; "paystack" sends M-Pesa transfers for campaign payments.
    payout_provider: Literal["practice", "paystack"] = "practice"
    # "practice" marks an M-Pesa prompt paid at once and takes no money; "paystack" sends a real
    # prompt to the payer's phone. Paying by Paybill or Till code works in both.
    payin_provider: Literal["practice", "paystack"] = "practice"

    # Google sign-in; blank hides the button. The OAuth client's redirect URI is
    # PUBLIC_URL followed by /api/auth/google/callback/.
    google_client_id: str = ""
    google_client_secret: str = ""

    @field_validator("payout_provider", "payin_provider", mode="after")
    @classmethod
    def _paystack_needs_a_key(cls, value: str, info: ValidationInfo) -> str:
        if value == "paystack" and not info.data.get("paystack_secret_key"):
            raise ValueError(f"{info.field_name.upper()}=paystack needs PAYSTACK_SECRET_KEY.")
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
        if value == "sozuri" and not (
            info.data.get("sozuri_api_key")
            and info.data.get("sozuri_project")
            and info.data.get("sozuri_sender_id")
        ):
            raise ValueError(
                "SMS_PROVIDER=sozuri needs SOZURI_API_KEY, SOZURI_PROJECT and SOZURI_SENDER_ID."
            )
        return value

    @field_validator("sms_window", mode="after")
    @classmethod
    def _window_inside_the_day(cls, value: str) -> str:
        """HH:MM-HH:MM, inside 08:00 to 18:00."""
        try:
            start, end = (time.fromisoformat(part.strip()) for part in value.split("-"))
        except ValueError:
            raise ValueError("SMS_WINDOW must look like 08:00-18:00.") from None
        if not (time(8) <= start < end <= time(18)):
            raise ValueError("SMS_WINDOW must sit inside 08:00-18:00.")
        return value

    @property
    def meetings_configured(self) -> bool:
        return bool(self.livekit_url and self.livekit_api_key and self.livekit_api_secret)

    @property
    def push_configured(self) -> bool:
        return bool(self.vapid_public_key and self.vapid_private_key and self.vapid_subject)

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

    def url(self, path: str) -> str:
        """`path` on the public site, as a full address."""
        return f"{self.public_url.rstrip('/')}{path}"


@lru_cache
def get_settings() -> Settings:
    """Read once per process."""
    return Settings()  # type: ignore[call-arg]


def alembic_url() -> str:
    """The DSN with `%` doubled, since Alembic reads it through configparser."""
    return get_settings().database_url.replace("%", "%%")
