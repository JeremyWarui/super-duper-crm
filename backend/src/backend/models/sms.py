"""Texts: every one the app sends, numbers that said STOP, replies from the gateway, and the
workspace's drafted messages."""

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class CampaignMessage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A text to a campaign's supporters: drafted, then sent or declined by the Candidate or
    Manager. `wards` empty means every ward the drafter reaches."""

    __tablename__ = "campaign_messages"

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("campaigns.id", ondelete="CASCADE"), index=True
    )
    body: Mapped[str] = mapped_column(Text)
    wards: Mapped[list] = mapped_column(JSON, default=list)
    # draft, sent or declined.
    status: Mapped[str] = mapped_column(String(20), default="draft")
    drafted_by_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    decided_by_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    note: Mapped[str] = mapped_column(Text, default="")
    recipients: Mapped[int] = mapped_column(Integer, default=0)


class PartyMessage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A party text to consenting members or volunteers, in a county, constituency or ward or
    everywhere: drafted by the Comms Officer, then sent or declined by the Party Super Admin."""

    __tablename__ = "party_messages"

    body: Mapped[str] = mapped_column(Text)
    # members or volunteers.
    audience: Mapped[str] = mapped_column(String(20))
    county_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("counties.id", ondelete="SET NULL"), default=None
    )
    constituency_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("constituencies.id", ondelete="SET NULL"), default=None
    )
    ward_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("wards.id", ondelete="SET NULL"), default=None
    )
    # draft, sent or declined.
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    drafted_by_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    decided_by_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    note: Mapped[str] = mapped_column(Text, default="")
    targeted: Mapped[int] = mapped_column(Integer, default=0)
    recipients: Mapped[int] = mapped_column(Integer, default=0)


class SmsLog(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One text to one number, or what would have gone in practice mode.

    `status` is `practice` (nothing sent), `sent` (the gateway took it), `delivered` or `failed`,
    with the gateway's reason in `detail`. `campaign_id` is None for the party office and tests.
    """

    __tablename__ = "sms_log"

    campaign_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("campaigns.id", ondelete="CASCADE"), index=True, default=None
    )
    message_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("campaign_messages.id", ondelete="SET NULL"), index=True, default=None
    )
    event_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("events.id", ondelete="SET NULL"), index=True, default=None
    )
    party_message_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("party_messages.id", ondelete="SET NULL"), index=True, default=None
    )
    sender_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    # message, invite, party or test.
    purpose: Mapped[str] = mapped_column(String(20))
    phone: Mapped[str] = mapped_column(String(20), index=True)
    body: Mapped[str] = mapped_column(Text)
    provider: Mapped[str] = mapped_column(String(20))
    provider_id: Mapped[str | None] = mapped_column(String(100), unique=True, default=None)
    status: Mapped[str] = mapped_column(String(20))
    detail: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class SmsOptOut(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A number that asked for no more texts: from one campaign, or from the whole installation
    when `campaign_id` is None."""

    __tablename__ = "sms_opt_outs"
    __table_args__ = (
        Index(
            "uq_sms_opt_outs_campaign",
            "phone",
            "campaign_id",
            unique=True,
            postgresql_where=text("campaign_id IS NOT NULL"),
            sqlite_where=text("campaign_id IS NOT NULL"),
        ),
        Index(
            "uq_sms_opt_outs_everywhere",
            "phone",
            unique=True,
            postgresql_where=text("campaign_id IS NULL"),
            sqlite_where=text("campaign_id IS NULL"),
        ),
    )

    phone: Mapped[str] = mapped_column(String(20), index=True)
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("campaigns.id", ondelete="CASCADE"), default=None
    )
    # stop (a reply), gateway (the provider's opt-out list).
    source: Mapped[str] = mapped_column(String(20))


class SmsInbound(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A text the gateway passed on, kept once per gateway id; `action` is what the app did."""

    __tablename__ = "sms_inbound"

    provider_id: Mapped[str] = mapped_column(String(100), unique=True)
    phone: Mapped[str] = mapped_column(String(20))
    to: Mapped[str] = mapped_column(String(20), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    # opted_out or none.
    action: Mapped[str] = mapped_column(String(20))
