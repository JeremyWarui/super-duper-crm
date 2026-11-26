"""Online calls on LiveKit and the call alerts that ring the team (DM-4, DM-5)."""

import base64
import hashlib
import json
import secrets
import time

import httpx
import jwt
import pytest
from livekit import api
from pywebpush import WebPushException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import MeetingAttendance, PushSubscription
from backend.services import meetings, push
from tests.conftest import World
from tests.factories import make_user, sign_in

KEY, SECRET = secrets.token_hex(8), secrets.token_urlsafe(32)


class Rooms:
    def __init__(self) -> None:
        self.created: list[str] = []
        self.closed: list[str] = []

    async def create(self, name: str) -> None:
        self.created.append(name)

    async def close(self, name: str) -> None:
        self.closed.append(name)


@pytest.fixture
def livekit(monkeypatch: pytest.MonkeyPatch, fresh_settings: None) -> Rooms:
    monkeypatch.setenv("LIVEKIT_URL", "wss://demo.livekit.cloud")
    monkeypatch.setenv("LIVEKIT_API_KEY", KEY)
    monkeypatch.setenv("LIVEKIT_API_SECRET", SECRET)
    fake = Rooms()
    monkeypatch.setattr(meetings, "rooms", fake)
    return fake


async def start(client: httpx.AsyncClient, world: World, mode: str = "video", **extra) -> dict:
    answer = await client.post(
        f"/api/campaigns/{world.campaign.id}/meetings/",
        json={"title": "Ward check-in", "mode": mode, **extra},
        headers=world.headers("manager"),
    )
    assert answer.status_code == 201, answer.text
    return answer.json()


def grants(token: str) -> dict:
    return jwt.decode(token, SECRET, algorithms=["HS256"], options={"verify_aud": False})


async def test_a_token_lets_one_login_into_one_room_for_fifteen_minutes(
    client: httpx.AsyncClient, session: AsyncSession, world: World, livekit: Rooms
) -> None:
    video = await start(client, world)
    audio = await start(client, world, mode="audio")
    outsider = await make_user(session, username="outsider")
    path = f"/api/meetings/{video['meeting']['id']}/token/"

    mine = await client.get(path, headers=world.headers("mobilizer"))
    theirs = await client.get(
        path, headers={"Authorization": f"Token {await sign_in(client, 'outsider')}"}
    )
    audio_token = await client.get(
        f"/api/meetings/{audio['meeting']['id']}/token/", headers=world.headers("mobilizer")
    )

    claims = grants(mine.json()["token"])
    assert claims["sub"] == str(world.mobilizer_user.id)
    assert claims["video"]["room"] == livekit.created[0]
    assert claims["exp"] - claims["nbf"] == 15 * 60
    assert theirs.status_code in (403, 404)
    assert outsider.id
    assert grants(audio_token.json()["token"])["video"]["canPublishSources"] == ["microphone"]


def signed(event: dict) -> tuple[str, dict]:
    body = json.dumps(event)
    digest = base64.b64encode(hashlib.sha256(body.encode()).digest()).decode()
    token = api.AccessToken(KEY, SECRET).with_sha256(digest).to_jwt()
    return body, {"Authorization": token, "Content-Type": "application/webhook+json"}


async def test_attendance_comes_from_signed_joins_and_leaves_and_a_forgery_is_refused(
    client: httpx.AsyncClient, session: AsyncSession, world: World, livekit: Rooms
) -> None:
    started = await start(client, world)
    room = {"name": livekit.created[0]}
    who = {"identity": str(world.mobilizer_user.id)}
    now = int(time.time())
    joined = {"event": "participant_joined", "room": room, "participant": who, "createdAt": now}
    left = {**joined, "event": "participant_left", "createdAt": now + 300}
    finished = {"event": "room_finished", "room": room, "createdAt": now + 400}

    async def post(event: dict, forge: bool = False) -> httpx.Response:
        body, headers = signed(event)
        if forge:
            body = body.replace("participant_left", "participant_joined")
        return await client.post("/api/livekit/webhook/", content=body, headers=headers)

    forged = await post(left, forge=True)
    results = [(await post(e)).json()["applied"] for e in (joined, joined, left, finished)]
    calls = await client.get(
        f"/api/campaigns/{world.campaign.id}/meetings/", headers=world.headers("manager")
    )

    assert forged.status_code == 401
    assert results == [True, False, True, True]
    (call,) = calls.json()
    assert call["meeting"]["id"] == started["meeting"]["id"]
    assert (call["meeting"]["status"], call["minutes"]) == ("ended", 6)
    assert [s["name"] for s in call["attendance"]] == [world.mobilizer_user.display_name]
    stay = await session.scalar(select(MeetingAttendance))
    assert (stay.left_at - stay.joined_at).seconds == 300


async def test_with_no_livekit_keys_a_call_cannot_start(
    client: httpx.AsyncClient, world: World
) -> None:
    answer = await client.post(
        f"/api/campaigns/{world.campaign.id}/meetings/",
        json={"title": "Ward check-in"},
        headers=world.headers("manager"),
    )

    assert answer.status_code == 400
    assert "Meetings are not configured" in answer.json()["detail"]


async def test_a_ward_call_alerts_only_its_invitees_and_a_gone_device_is_dropped(
    client: httpx.AsyncClient,
    session: AsyncSession,
    world: World,
    livekit: Rooms,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VAPID_PUBLIC_KEY", "public")
    monkeypatch.setenv("VAPID_PRIVATE_KEY", secrets.token_urlsafe(32))
    monkeypatch.setenv("VAPID_SUBJECT", "mailto:ops@example.org")
    sent: list[str] = []

    def deliver(device: PushSubscription, payload: str) -> None:
        if device.endpoint.endswith("gone"):
            raise WebPushException("Gone", response=httpx.Response(410))
        sent.append(device.endpoint)
        assert json.loads(payload)["url"].startswith("/meet/")

    monkeypatch.setattr(push, "_send", deliver)
    keys = {"p256dh": "k", "auth": "a"}
    for role, endpoint in (
        ("mobilizer", "https://fcm.googleapis.com/fcm/send/mobilizer"),
        ("candidate", "https://fcm.googleapis.com/fcm/send/candidate-gone"),
        ("manager", "https://fcm.googleapis.com/fcm/send/manager"),
    ):
        answer = await client.post(
            "/api/push/subscribe/",
            json={"endpoint": endpoint, "keys": keys},
            headers=world.headers(role),
        )
        assert answer.status_code == 204
    internal = await client.post(
        "/api/push/subscribe/",
        json={"endpoint": "http://10.0.0.5/admin", "keys": keys},
        headers=world.headers("manager"),
    )
    sneaky = await client.post(
        "/api/push/subscribe/",
        json={"endpoint": "https://evil.example\\@fcm.googleapis.com/fcm/send/x", "keys": keys},
        headers=world.headers("manager"),
    )
    assert (internal.status_code, sneaky.status_code) == (400, 400)
    other_ward = await start(client, world, ward=str(world.other_ward.id))
    whole = await start(client, world)
    removed = await client.request(
        "DELETE",
        "/api/push/subscribe/",
        json={"endpoint": "https://fcm.googleapis.com/fcm/send/mobilizer"},
        headers=world.headers("mobilizer"),
    )
    left = list(await session.scalars(select(PushSubscription.endpoint)))

    assert other_ward["alerted"] == 0
    assert whole["alerted"] == 1
    assert sent == ["https://fcm.googleapis.com/fcm/send/mobilizer"]
    assert removed.status_code == 204
    assert left == ["https://fcm.googleapis.com/fcm/send/manager"]


async def test_a_started_call_reaches_its_invitees_in_the_app_without_push(
    client: httpx.AsyncClient, world: World, livekit: Rooms
) -> None:
    await start(client, world, ward=str(world.other_ward.id))
    whole = await start(client, world)
    live_path = f"/api/campaigns/{world.campaign.id}/meetings/live/"

    bell = (await client.get("/api/notices/", headers=world.headers("mobilizer"))).json()
    live = (await client.get(live_path, headers=world.headers("mobilizer"))).json()
    host_bell = (await client.get("/api/notices/", headers=world.headers("manager"))).json()
    await client.post(
        f"/api/meetings/{whole['meeting']['id']}/end/", headers=world.headers("manager")
    )
    after = (await client.get(live_path, headers=world.headers("mobilizer"))).json()

    assert [(n["text"], n["url"]) for n in bell] == [
        ("Call started: Ward check-in", whole["join_path"])
    ]
    assert [m["id"] for m in live] == [whole["meeting"]["id"]]
    assert host_bell == []
    assert after == []
