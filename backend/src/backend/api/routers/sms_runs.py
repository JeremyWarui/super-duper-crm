"""Bulk text runs: their progress, Pause, Resume and Halt, the vetting reference, and the consent
evidence behind each (`services/sms_queue.py`)."""

import hmac
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Response

from backend.api.deps import SessionDep, require
from backend.api.scope import require_visible_campaign
from backend.config import get_settings
from backend.models import SmsRun, User
from backend.schemas.messages import RunHalt, RunVetting, SmsRunRead
from backend.services import sms_queue
from backend.services.errors import NotFound

router = APIRouter(tags=["messages"])

Sender = Annotated[User, Depends(require("sms.send"))]
RUN = "/campaigns/{campaign_id}/sms-runs/{run_id}"


async def _run(session, user: User, campaign_id: uuid.UUID, run_id: uuid.UUID) -> SmsRun:
    await require_visible_campaign(session, user, campaign_id)
    run = await session.get(SmsRun, run_id)
    if run is None or run.campaign_id != campaign_id:
        raise NotFound("No such run.")
    return run


def _read(entry: dict) -> SmsRunRead:
    run = SmsRunRead.model_validate(entry["run"])
    return run.model_copy(
        update={"delivered": entry["delivered"], "waiting_until": entry["waiting_until"]}
    )


async def _one(session, run: SmsRun) -> SmsRunRead:
    entries = await sms_queue.runs(session, run.campaign_id)
    return _read(next(e for e in entries if e["run"].id == run.id))


@router.get("/campaigns/{campaign_id}/sms-runs/", response_model=list[SmsRunRead])
async def list_runs(campaign_id: uuid.UUID, session: SessionDep, user: Sender) -> list:
    await require_visible_campaign(session, user, campaign_id)
    return [_read(e) for e in await sms_queue.runs(session, campaign_id)]


@router.post(f"{RUN}/pause/", response_model=SmsRunRead)
async def pause(
    campaign_id: uuid.UUID, run_id: uuid.UUID, session: SessionDep, user: Sender
) -> SmsRunRead:
    run = await _run(session, user, campaign_id, run_id)
    return await _one(session, await sms_queue.pause(session, run, actor=user))


@router.post(f"{RUN}/resume/", response_model=SmsRunRead)
async def resume(
    campaign_id: uuid.UUID, run_id: uuid.UUID, session: SessionDep, user: Sender
) -> SmsRunRead:
    run = await _run(session, user, campaign_id, run_id)
    return await _one(session, await sms_queue.resume(session, run, actor=user))


@router.post(f"{RUN}/halt/", response_model=SmsRunRead)
async def halt(
    campaign_id: uuid.UUID, run_id: uuid.UUID, payload: RunHalt, session: SessionDep, user: Sender
) -> SmsRunRead:
    run = await _run(session, user, campaign_id, run_id)
    return await _one(session, await sms_queue.halt(session, run, payload.reason, actor=user))


@router.post(f"{RUN}/vetting/", response_model=SmsRunRead)
async def vetting(
    campaign_id: uuid.UUID,
    run_id: uuid.UUID,
    payload: RunVetting,
    session: SessionDep,
    user: Sender,
) -> SmsRunRead:
    run = await _run(session, user, campaign_id, run_id)
    run = await sms_queue.record_vetting(session, run, payload.reference, actor=user)
    return await _one(session, run)


@router.get(f"{RUN}/consent.csv")
async def consent(
    campaign_id: uuid.UUID, run_id: uuid.UUID, session: SessionDep, user: Sender
) -> Response:
    """Each number in the run with the consent it was texted on."""
    run = await _run(session, user, campaign_id, run_id)
    return Response(
        await sms_queue.consent_csv(session, run),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="sms-run-{run.id}-consent.csv"'},
    )


async def drain(session: SessionDep, authorization: Annotated[str, Header()] = "") -> dict:
    """One batch from every due run; the scheduler calls it with `Bearer CRON_SECRET`."""
    secret = get_settings().cron_secret
    expected = f"Bearer {secret}".encode()
    if not secret or not hmac.compare_digest(authorization.encode(), expected):
        raise NotFound("Not Found")
    return {"runs": await sms_queue.drain(session)}


# Vercel cron calls with GET; a person draining by hand uses POST.
router.add_api_route("/internal/sms/drain/", drain, methods=["GET"], name="drain_on_schedule")
router.add_api_route("/internal/sms/drain/", drain, methods=["POST"], name="drain_by_hand")
