"""Web push to installed field apps and browsers (DM-5): who gets call alerts, and sending them.

With no VAPID keys set, nothing is sent and `notify` reports 0.
"""

import asyncio
import json
import logging
import uuid
from datetime import UTC, datetime

from pywebpush import WebPushException, webpush
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.models import PushSubscription, User

logger = logging.getLogger(__name__)

# The push service says the subscription is gone.
GONE = {404, 410}
TTL_SECONDS = 60


def _send(subscription: PushSubscription, payload: str) -> None:
    s = get_settings()
    webpush(
        subscription_info={
            "endpoint": subscription.endpoint,
            "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth},
        },
        data=payload,
        vapid_private_key=s.vapid_private_key,
        vapid_claims={"sub": s.vapid_subject},
        ttl=TTL_SECONDS,
        timeout=10,
    )


async def subscribe(
    session: AsyncSession, user: User, endpoint: str, p256dh: str, auth: str
) -> PushSubscription:
    """Keep this device for the login; a device that changed hands moves to the new login."""
    found = await session.scalar(
        select(PushSubscription).where(PushSubscription.endpoint == endpoint)
    )
    if found is None:
        found = PushSubscription(endpoint=endpoint, user_id=user.id, p256dh=p256dh, auth=auth)
        session.add(found)
    else:
        found.user_id, found.p256dh, found.auth = user.id, p256dh, auth
    await session.commit()
    return found


async def unsubscribe(session: AsyncSession, user: User, endpoint: str) -> None:
    await session.execute(
        delete(PushSubscription).where(
            PushSubscription.endpoint == endpoint, PushSubscription.user_id == user.id
        )
    )
    await session.commit()


async def notify(
    session: AsyncSession, user_ids: list[uuid.UUID], title: str, body: str, url: str
) -> int:
    """Alert every device of these logins; returns how many took it. Devices the push service
    no longer knows are deleted. Commits."""
    if not get_settings().push_configured or not user_ids:
        return 0
    devices = list(
        await session.scalars(
            select(PushSubscription).where(PushSubscription.user_id.in_(user_ids))
        )
    )
    payload = json.dumps({"title": title, "body": body, "url": url})
    sent = 0
    for device in devices:
        try:
            await asyncio.to_thread(_send, device, payload)
        except WebPushException as failed:
            status = getattr(failed.response, "status_code", None)
            if status in GONE:
                await session.delete(device)
            else:
                logger.warning("push to a device failed: %s", failed.message)
            continue
        device.last_used_at = datetime.now(UTC)
        sent += 1
    await session.commit()
    return sent
