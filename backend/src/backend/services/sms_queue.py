"""Bulk texts through the compliance queue (CD-R6 5.5, DM-3): approval checks the text, builds a
run of consenting numbers, and a worker sends it a batch at a time inside the sending window.

A number the gateway accepted is never sent again: rows are marked `sending` before the
gateway is called, and only rows still `queued` are picked up.
"""

import csv
import io
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.config import Settings, get_settings
from backend.models import (
    Campaign,
    CampaignMessage,
    Event,
    SmsLog,
    SmsOutbox,
    SmsRun,
    Supporter,
    User,
)
from backend.models.sms_queue import RUN_STAGES
from backend.services import texting
from backend.services.audit import record
from backend.services.errors import Refused
from backend.services.sms import SMSProvider, normalise_phone, parts_of

logger = logging.getLogger(__name__)

NAIROBI = ZoneInfo("Africa/Nairobi")
LANGUAGES = {"en": "English", "sw": "Kiswahili"}
# Words in a consent wording that show it covers being texted.
COVERS_SMS = ("sms", "text", "contact")
FINAL = {"halted", "completed"}

NO_NAME = "The text must carry the candidate's name as registered: {name}."
NO_CANDIDATE = "This campaign has no candidate yet, so its texts cannot carry a name."
BAD_LANGUAGE = "Bulk texts go out in English or Kiswahili only."
PERIOD_OVER = "The campaign period ended on {end}; no more bulk texts can go."
NOBODY = "Nobody in this audience has agreed to be texted."


def clock() -> datetime:
    """The time now; the one place the queue reads the clock."""
    return datetime.now(UTC)


def covers_sms(wording: str | None) -> bool:
    """Whether a consent wording covers being texted."""
    text = (wording or "").lower()
    return any(word in text for word in COVERS_SMS)


def window(settings: Settings | None = None) -> tuple[time, time]:
    start, end = (settings or get_settings()).sms_window.split("-")
    return time.fromisoformat(start.strip()), time.fromisoformat(end.strip())


def sending_allowed(now: datetime, settings: Settings | None = None) -> bool:
    """Inside the daily window, Nairobi time, and inside the campaign period when set."""
    settings = settings or get_settings()
    local = now.astimezone(NAIROBI)
    start, end = window(settings)
    if not (start <= local.time() < end):
        return False
    first, last = settings.campaign_period_start, settings.campaign_period_end
    return (first is None or local.date() >= first) and (last is None or local.date() <= last)


def next_opening(now: datetime, settings: Settings | None = None) -> datetime | None:
    """When sending may next start, in Nairobi time; None once the campaign period is over."""
    settings = settings or get_settings()
    local = now.astimezone(NAIROBI)
    start, end = window(settings)
    day = local.date() + timedelta(days=1) if local.time() >= end else local.date()
    first, last = settings.campaign_period_start, settings.campaign_period_end
    if first is not None and day < first:
        day = first
    if last is not None and day > last:
        return None
    opening = datetime.combine(day, start, NAIROBI)
    return max(opening, local)


def _check_text(body: str, name: str, language: str) -> None:
    if not name:
        raise Refused(NO_CANDIDATE)
    if name.casefold() not in body.casefold():
        raise Refused(NO_NAME.format(name=name))
    if language not in LANGUAGES:
        raise Refused(BAD_LANGUAGE)


def _check_period(now: datetime, settings: Settings) -> None:
    last = settings.campaign_period_end
    if last is not None and now.astimezone(NAIROBI).date() > last:
        raise Refused(PERIOD_OVER.format(end=last.isoformat()))


async def _candidate_name(session: AsyncSession, campaign_id: uuid.UUID) -> str:
    campaign = await session.scalar(
        select(Campaign).where(Campaign.id == campaign_id).options(selectinload(Campaign.candidate))
    )
    return campaign.candidate_label if campaign is not None else ""


@dataclass
class Audience:
    """Who a bulk text goes to: each consenting number with its supporter, and who is left out."""

    queued: dict[str, uuid.UUID]
    no_consent: int
    opted_out: int
    unusable: list[str]


async def plan_audience(session: AsyncSession, campaign_id: uuid.UUID, audience: list) -> Audience:
    """Sort everyone the conditions match into the numbers to text and the ones left out; only
    supporters whose consent wording covers texts are texted, and opted-out numbers never."""
    people = (
        await session.execute(
            select(
                Supporter.id, Supporter.phone, Supporter.consent_given, Supporter.consent_wording
            ).where(*audience)
        )
    ).all()
    consenting: dict[str, uuid.UUID] = {}
    no_consent = 0
    unusable: list[str] = []
    for supporter_id, phone, given, wording in people:
        number = normalise_phone(phone)
        if number is None:
            unusable.append(phone or "")
            continue
        if not (given and covers_sms(wording)):
            no_consent += 1
            continue
        consenting.setdefault(number, supporter_id)
    blocked = await texting.opted_out(session, campaign_id, list(consenting))
    queued = {n: s for n, s in consenting.items() if n not in blocked}
    return Audience(queued, no_consent, len(blocked), unusable)


async def check_text(session: AsyncSession, campaign_id: uuid.UUID, body: str, language: str):
    """Refused unless the text names the candidate and is in English or Kiswahili."""
    _check_text(body, await _candidate_name(session, campaign_id), language)


async def approve(
    session: AsyncSession,
    message: CampaignMessage,
    audience: list,
    *,
    language: str,
    actor: User,
    now: datetime | None = None,
    provider: SMSProvider | None = None,
    event_id: uuid.UUID | None = None,
) -> SmsRun:
    """Check the draft, build its run and, inside the window, send the first batch; commits.

    `audience` is the conditions on `supporters` for everyone the message is addressed to,
    consenting or not. A failed check refuses and leaves the draft as it was.
    """
    settings = get_settings()
    now = now or clock()
    name = await _candidate_name(session, message.campaign_id)
    _check_text(message.body, name, language)
    _check_period(now, settings)

    plan = await plan_audience(session, message.campaign_id, audience)
    queued = plan.queued
    if not queued:
        raise Refused(NOBODY)

    await texting.decide(session, CampaignMessage, message, "sent", actor)
    message.language = language
    text = texting.text_of(message.body)
    segments = parts_of(text)
    if settings.sms_vetting_required:
        stage = "awaiting_vetting"
    else:
        stage = "sending" if sending_allowed(now, settings) else "scheduled"
    run = SmsRun(
        campaign_id=message.campaign_id,
        message_id=message.id,
        status=stage,
        language=language,
        sender_name=name,
        text=text,
        targeted=len(queued),
        excluded_no_consent=plan.no_consent,
        excluded_opted_out=plan.opted_out,
        event_id=event_id,
        segments=segments,
        estimated_cost_cents=len(queued) * segments * settings.sms_part_price_cents,
        approved_by_id=actor.id,
    )
    session.add(run)
    await session.flush()
    session.add_all(
        SmsOutbox(run_id=run.id, supporter_id=supporter_id, phone=number)
        for number, supporter_id in queued.items()
    )
    message.recipients = len(queued)
    _audit(session, actor, run, "sms.run.approve", targeted=len(queued), stage=stage)
    await session.commit()
    if stage == "sending":
        await process_next_batch(session, run.id, now=now, provider=provider)
        await session.refresh(run)
    return run


# A row claimed this long ago and still sending belongs to a worker that died; it is sent again
# under the same key, which the gateway answers as a repeat.
STALE_CLAIM = timedelta(minutes=15)


async def _set_status(
    session: AsyncSession, run_id: uuid.UUID, from_: tuple[str, ...], to: str, **values
) -> bool:
    """Move the run on only from these stages; False when someone else moved it first."""
    changed = await session.execute(
        update(SmsRun)
        .where(SmsRun.id == run_id, SmsRun.status.in_(from_))
        .values(status=to, **values)
        .execution_options(synchronize_session=False)
    )
    return changed.rowcount > 0


def _due(run_id: uuid.UUID, now: datetime) -> tuple:
    return (
        SmsOutbox.run_id == run_id,
        SmsOutbox.status == "queued",
        (SmsOutbox.next_attempt_at.is_(None)) | (SmsOutbox.next_attempt_at <= now),
    )


async def _claim(
    session: AsyncSession, run_id: uuid.UUID, now: datetime, size: int
) -> tuple[str, list[uuid.UUID]]:
    """Take the next batch for this worker alone: a batch that failed before goes again whole,
    under its old key; otherwise up to `size` fresh numbers under a new one. A row another
    worker took first is not taken."""
    key = await session.scalar(
        select(SmsOutbox.batch_key).where(*_due(run_id, now), SmsOutbox.batch_key != "").limit(1)
    )
    taking = update(SmsOutbox).values(status="sending", claimed_at=now)
    if key:
        taking = taking.where(*_due(run_id, now), SmsOutbox.batch_key == key)
    else:
        key = uuid.uuid4().hex
        ids = list(
            await session.scalars(
                select(SmsOutbox.id).where(*_due(run_id, now)).order_by(SmsOutbox.phone).limit(size)
            )
        )
        taking = taking.values(batch_key=key).where(
            SmsOutbox.id.in_(ids), SmsOutbox.status == "queued"
        )
    claimed = await session.execute(
        taking.returning(SmsOutbox.id).execution_options(synchronize_session=False)
    )
    return key, list(claimed.scalars())


async def _reclaim_stale(session: AsyncSession, run_id: uuid.UUID, now: datetime) -> None:
    await session.execute(
        update(SmsOutbox)
        .where(
            SmsOutbox.run_id == run_id,
            SmsOutbox.status == "sending",
            SmsOutbox.claimed_at < now - STALE_CLAIM,
        )
        .values(status="queued", next_attempt_at=now)
        .execution_options(synchronize_session=False)
    )


async def _still_consenting(session: AsyncSession, rows: list[SmsOutbox]) -> set[uuid.UUID]:
    """The rows whose supporter still exists, keeps that number and still consents to texts."""
    people = {
        supporter_id: (phone, given, wording)
        for supporter_id, phone, given, wording in await session.execute(
            select(
                Supporter.id, Supporter.phone, Supporter.consent_given, Supporter.consent_wording
            ).where(Supporter.id.in_([r.supporter_id for r in rows if r.supporter_id]))
        )
    }
    ok = set()
    for row in rows:
        phone, given, wording = people.get(row.supporter_id, ("", False, None))
        if given and covers_sms(wording) and normalise_phone(phone) == row.phone:
            ok.add(row.id)
    return ok


def _refused(exc: Exception) -> int | None:
    """The status of a refusal that a retry would only repeat; None for a failure worth retrying."""
    status = getattr(getattr(exc, "response", None), "status_code", None)
    if status is not None and 400 <= status < 500 and status not in (408, 409, 429):
        return status
    return None


async def process_next_batch(
    session: AsyncSession,
    run_id: uuid.UUID,
    *,
    now: datetime | None = None,
    provider: SMSProvider | None = None,
) -> int:
    """Send up to `SMS_BATCH_SIZE` due numbers of one run; returns how many the gateway took.

    Outside the window the run waits as `scheduled`. Numbers that opted out, withdrew consent
    or were erased since approval are skipped. Each batch carries one idempotency key, kept
    when the batch is retried, so a gateway that took it and lost its answer sees a repeat.
    A refusal is final; any other failure is retried with a growing delay, up to
    `SMS_MAX_ATTEMPTS`. Commits.
    """
    settings = get_settings()
    now = now or clock()
    run = await session.get(SmsRun, run_id, populate_existing=True)
    if run is None or run.status not in ("sending", "scheduled"):
        return 0
    if not sending_allowed(now, settings):
        await _set_status(session, run.id, ("sending",), "scheduled")
        await session.commit()
        return 0
    if not await _set_status(session, run.id, ("sending", "scheduled"), "sending"):
        await session.commit()
        return 0
    message = await session.get(CampaignMessage, run.message_id)
    try:
        _check_text(message.body if message else "", run.sender_name, run.language)
        _check_period(now, settings)
    except Refused as failed:
        await _set_status(session, run.id, ("sending",), "halted", halt_reason=str(failed))
        await session.commit()
        return 0

    await _reclaim_stale(session, run.id, now)
    key, claimed = await _claim(session, run.id, now, settings.sms_batch_size)
    await session.commit()
    rows = list(
        await session.scalars(
            select(SmsOutbox)
            .where(SmsOutbox.id.in_(claimed))
            .order_by(SmsOutbox.phone)
            .execution_options(populate_existing=True)
        )
    )
    blocked = await texting.opted_out(session, run.campaign_id, [row.phone for row in rows])
    consenting = await _still_consenting(session, rows)
    batch = []
    for row in rows:
        if row.phone in blocked:
            row.status, row.skip_reason = "skipped", "opted_out"
        elif row.id not in consenting:
            row.status, row.skip_reason = "skipped", "no_consent"
        else:
            batch.append(row)
    await session.commit()

    # A Pause or Halt that landed after the claim keeps this batch back.
    stage = await session.scalar(
        select(SmsRun.status).where(SmsRun.id == run.id).execution_options(populate_existing=True)
    )
    if stage != "sending":
        for row in batch:
            row.status = "queued" if stage == "paused" else "skipped"
            row.skip_reason = "" if stage == "paused" else "halted"
        await session.commit()
        return 0
    await session.commit()

    taken = 0
    if batch:
        try:
            result, logged = await texting.deliver(
                session,
                [row.phone for row in batch],
                run.text,
                purpose="invite" if run.event_id else "message",
                sender=None,
                campaign_id=run.campaign_id,
                message_id=run.message_id,
                event_id=run.event_id,
                provider=provider,
                idempotency_key=key,
            )
        except Exception as exc:
            await session.rollback()
            for row in batch:
                await session.refresh(row)
            refused = _refused(exc)
            logger.warning("sms run %s: batch %s not sent: %s", run.id, key, exc)
            for row in batch:
                row.attempts += 1
                if refused is not None:
                    row.status, row.skip_reason = "failed", f"refused_{refused}"
                elif row.attempts >= settings.sms_max_attempts:
                    row.status, row.skip_reason = "failed", "gateway_unreachable"
                else:
                    row.status = "queued"
                    row.next_attempt_at = now + timedelta(minutes=2**row.attempts)
        else:
            accepted = {r.phone for r in result.accepted}
            for row in batch:
                log = logged.get(row.phone)
                row.attempts += 1
                row.sms_log_id = log.id if log is not None else None
                if row.phone in accepted:
                    row.status, row.sent_at = "sent", now
                    taken += 1
                else:
                    row.status = "failed"
                    row.skip_reason = (log.detail if log is not None else "")[:40]
            await session.flush()
    await _settle(session, run.id, now)
    await session.commit()
    return taken


async def _settle(session: AsyncSession, run_id: uuid.UUID, now: datetime) -> None:
    """Update the run's totals; complete it once nothing is left to send, unless someone paused
    or halted it meanwhile."""
    counts = dict(
        (
            await session.execute(
                select(SmsOutbox.status, func.count())
                .where(SmsOutbox.run_id == run_id)
                .group_by(SmsOutbox.status)
            )
        ).all()
    )
    sent = counts.get("sent", 0)
    segments, event_id = (
        await session.execute(select(SmsRun.segments, SmsRun.event_id).where(SmsRun.id == run_id))
    ).one()
    if event_id is not None:
        # An invitation reaches as many people as its texts went to.
        await session.execute(
            update(Event)
            .where(Event.id == event_id)
            .values(number_reached=sent)
            .execution_options(synchronize_session=False)
        )
    await session.execute(
        update(SmsRun)
        .where(SmsRun.id == run_id)
        .values(
            sent=sent,
            failed=counts.get("failed", 0),
            actual_cost_cents=sent * (segments or 1) * get_settings().sms_part_price_cents,
        )
        .execution_options(synchronize_session=False)
    )
    if not (counts.get("queued", 0) or counts.get("sending", 0)):
        await _set_status(session, run_id, ("sending",), "completed", completed_at=now)


async def drain(session: AsyncSession, *, now: datetime | None = None) -> int:
    """One batch from every run that is due; returns how many runs were looked at."""
    runs = list(
        await session.scalars(select(SmsRun.id).where(SmsRun.status.in_(("sending", "scheduled"))))
    )
    for run_id in runs:
        await process_next_batch(session, run_id, now=now)
    return len(runs)


async def pause(session: AsyncSession, run: SmsRun, *, actor: User) -> SmsRun:
    """Hold the run; a batch already with the gateway still lands."""
    if not await _set_status(session, run.id, ("sending", "scheduled"), "paused"):
        raise Refused("Only a run that is sending or waiting can be paused.")
    _audit(session, actor, run, "sms.run.pause")
    await session.commit()
    await session.refresh(run)
    return run


async def resume(session: AsyncSession, run: SmsRun, *, actor: User) -> SmsRun:
    if not await _set_status(session, run.id, ("paused",), "scheduled"):
        raise Refused("Only a paused run can be resumed.")
    _audit(session, actor, run, "sms.run.resume")
    await session.commit()
    await process_next_batch(session, run.id)
    await session.refresh(run)
    return run


async def halt(session: AsyncSession, run: SmsRun, reason: str, *, actor: User) -> SmsRun:
    """Stop the run for good: no further batch goes, and what was queued is skipped. A batch
    already with the gateway still lands."""
    reason = reason.strip()
    if not reason:
        raise Refused("Say why the run is halted.")
    unfinished = tuple(stage for stage in RUN_STAGES if stage not in FINAL)
    if not await _set_status(
        session, run.id, unfinished, "halted", halt_reason=reason, halted_by_id=actor.id
    ):
        raise Refused("This run has already finished.")
    await session.execute(
        update(SmsOutbox)
        .where(SmsOutbox.run_id == run.id, SmsOutbox.status == "queued")
        .values(status="skipped", skip_reason="halted")
        .execution_options(synchronize_session=False)
    )
    _audit(session, actor, run, "sms.run.halt", reason=reason)
    await session.commit()
    await session.refresh(run)
    return run


async def record_vetting(
    session: AsyncSession, run: SmsRun, reference: str, *, actor: User
) -> SmsRun:
    """The provider's vetting reference; the run then waits for the window."""
    if not reference.strip():
        raise Refused("Enter the provider's vetting reference.")
    if not await _set_status(
        session,
        run.id,
        ("awaiting_vetting",),
        "scheduled",
        vetting_ref=reference.strip()[:100],
        vetted_at=datetime.now(UTC),
    ):
        raise Refused("This run is not waiting for vetting.")
    await session.refresh(run)
    _audit(session, actor, run, "sms.run.vetted", reference=run.vetting_ref)
    await session.commit()
    await process_next_batch(session, run.id)
    await session.refresh(run)
    return run


async def runs(session: AsyncSession, campaign_id: uuid.UUID) -> list[dict]:
    """The campaign's runs, newest first, with delivered counts from the delivery reports."""
    found = list(
        await session.scalars(
            select(SmsRun)
            .where(SmsRun.campaign_id == campaign_id)
            .order_by(SmsRun.created_at.desc())
            .execution_options(populate_existing=True)
        )
    )
    delivered = (
        dict(
            (
                await session.execute(
                    select(SmsOutbox.run_id, func.count())
                    .join(SmsLog, SmsLog.id == SmsOutbox.sms_log_id)
                    .where(
                        SmsOutbox.run_id.in_([r.id for r in found]),
                        SmsLog.status == "delivered",
                    )
                    .group_by(SmsOutbox.run_id)
                )
            ).all()
        )
        if found
        else {}
    )
    now = clock()
    out = []
    for run in found:
        opening = next_opening(now) if run.status == "scheduled" else None
        out.append(
            {
                "run": run,
                "delivered": delivered.get(run.id, 0),
                "waiting_until": opening,
            }
        )
    return out


async def consent_csv(session: AsyncSession, run: SmsRun) -> str:
    """Each number in the run with the consent it was texted on."""
    rows = (
        await session.execute(
            select(
                SmsOutbox.phone,
                SmsOutbox.status,
                Supporter.full_name,
                Supporter.created_at,
                Supporter.consent_channel,
                Supporter.consent_wording,
            )
            .outerjoin(Supporter, Supporter.id == SmsOutbox.supporter_id)
            .where(SmsOutbox.run_id == run.id)
            .order_by(SmsOutbox.phone)
        )
    ).all()
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["phone", "name", "status", "consent_recorded", "consent_channel", "wording"])
    for phone, status, name, recorded, channel, wording in rows:
        writer.writerow(
            [
                phone,
                name or "",
                status,
                recorded.date().isoformat() if recorded else "",
                getattr(channel, "value", channel) or "",
                wording or "",
            ]
        )
    return out.getvalue()


def _audit(session: AsyncSession, actor: User, run: SmsRun, action: str, **detail) -> None:
    record(
        session,
        actor=actor,
        action=action,
        subject_type="sms_run",
        subject_id=run.id,
        campaign_id=run.campaign_id,
        detail=detail or None,
    )
