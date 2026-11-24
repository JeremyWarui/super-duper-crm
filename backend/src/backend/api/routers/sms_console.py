"""A campaign's test text: one number, sent at once, and the delivery status it gets back."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from backend.api.deps import SessionDep, require
from backend.api.scope import require_visible_campaign
from backend.models import User
from backend.schemas.messages import LogRow, TestText, TestTextResult
from backend.services import texting

router = APIRouter(prefix="/console/sms", tags=["messages"])

Sender = Annotated[User, Depends(require("sms.send"))]


@router.post("/test/", response_model=TestTextResult, status_code=status.HTTP_201_CREATED)
async def send_test(payload: TestText, session: SessionDep, user: Sender) -> TestTextResult:
    """Text one number now, past the queue; a live gateway only texts the campaign's own logins
    and consenting supporters."""
    campaign = await require_visible_campaign(session, user, payload.campaign)
    message = await texting.campaign_test(
        session, campaign.id, payload.phone, payload.body, actor=user
    )
    return TestTextResult(message=message)


@router.get("/test/", response_model=list[LogRow])
async def test_log(campaign: uuid.UUID, session: SessionDep, user: Sender) -> list:
    """The campaign's last test texts, newest first."""
    await require_visible_campaign(session, user, campaign)
    return await texting.test_log(session, campaign)
