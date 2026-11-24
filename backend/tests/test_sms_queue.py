"""The bulk SMS queue: the compliance gate, batches, STOP mid-run, Halt, retries and the
sending window (DM-3)."""

import asyncio
import secrets
from collections import Counter
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from backend.config import get_settings
from backend.models import CampaignMessage, SmsOptOut, SmsOutbox, SmsRun, Supporter
from backend.services import sms_queue
from backend.services.consent import WORDING, ConsentChannel
from backend.services.errors import Refused
from backend.services.messages import _audience
from backend.services.sms import ConsoleSMSProvider
from tests.conftest import World

TEN_AM = datetime(2026, 11, 24, 7, 0, tzinfo=UTC)
NAMED = "Rally at Kasarani on Saturday. Amina Kariuki"


class Gateway(ConsoleSMSProvider):
    """Practice gateway that remembers every number it was handed; can fail its first calls."""

    def __init__(self, fail_first: int = 0, refuse: bool = False, pause: float = 0) -> None:
        self.calls: list[list[str]] = []
        self.keys: list[str | None] = []
        self.fail_first = fail_first
        self.refuse = refuse
        self.pause = pause

    async def send(self, recipients, message, idempotency_key=None):  # type: ignore[no-untyped-def]
        self.keys.append(idempotency_key)
        if self.refuse:
            raise httpx.HTTPStatusError(
                "refused",
                request=httpx.Request("POST", "https://sozuri.net"),
                response=httpx.Response(422),
            )
        if self.fail_first:
            self.fail_first -= 1
            raise httpx.ReadTimeout("gateway timed out")
        self.calls.append(list(recipients))
        await asyncio.sleep(self.pause)
        return await super().send(recipients, message)


@pytest.fixture
def gateway(monkeypatch: pytest.MonkeyPatch) -> Gateway:
    fake = Gateway()
    monkeypatch.setattr("backend.services.texting.get_sms_provider", lambda *a, **k: fake)
    return fake


async def supporters(session: AsyncSession, world: World, count: int, **fields) -> list[str]:
    phones = [f"+2547{n:08d}" for n in range(1, count + 1)]
    values = {"consent_given": True, "consent_wording": WORDING[ConsentChannel.CAMPAIGN_LINK]}
    session.add_all(
        Supporter(
            campaign_id=world.campaign.id,
            ward_id=world.ward.id,
            full_name=phone,
            phone=phone,
            **(values | fields),
        )
        for phone in phones
    )
    await session.commit()
    return phones


async def approve(session: AsyncSession, world: World, body: str = NAMED, **kw) -> SmsRun:
    message = CampaignMessage(campaign_id=world.campaign.id, body=body, wards=[])
    session.add(message)
    await session.commit()
    audience = _audience(world.campaign.id, None, [], consenting=False)
    return await sms_queue.approve(
        session, message, audience, language=kw.pop("language", "en"), actor=world.manager, **kw
    )


async def test_each_gate_check_refuses_with_its_reason(
    session: AsyncSession, world: World, gateway: Gateway, monkeypatch: pytest.MonkeyPatch
) -> None:
    await supporters(session, world, 3)
    await supporters(session, world, 0)

    with pytest.raises(Refused, match="candidate's name as registered: Amina Kariuki"):
        await approve(session, world, body="Rally on Saturday.")
    with pytest.raises(Refused, match="English or Kiswahili"):
        await approve(session, world, language="fr")
    monkeypatch.setenv("CAMPAIGN_PERIOD_END", "2026-11-01")
    get_settings.cache_clear()
    try:
        with pytest.raises(Refused, match="campaign period ended"):
            await approve(session, world)
    finally:
        monkeypatch.delenv("CAMPAIGN_PERIOD_END")
        get_settings.cache_clear()
    assert gateway.calls == []
    assert await session.scalar(select(SmsRun.id)) is None


async def test_only_consent_that_covers_texts_counts_and_vetting_holds_the_run(
    session: AsyncSession, world: World, gateway: Gateway, monkeypatch: pytest.MonkeyPatch
) -> None:
    await supporters(session, world, 2)
    session.add_all(
        [
            Supporter(
                campaign_id=world.campaign.id,
                ward_id=world.ward.id,
                full_name="Held only",
                phone="+254733000001",
                consent_given=True,
                consent_wording=WORDING[ConsentChannel.MOBILIZER],
            ),
            Supporter(
                campaign_id=world.campaign.id,
                ward_id=world.ward.id,
                full_name="No consent",
                phone="+254733000002",
                consent_given=False,
            ),
        ]
    )
    await session.commit()
    monkeypatch.setenv("SMS_VETTING_REQUIRED", "true")
    get_settings.cache_clear()
    try:
        run = await approve(session, world)
        held = run.status
        await sms_queue.record_vetting(session, run, "SAF-2026-118", actor=world.manager)
    finally:
        monkeypatch.delenv("SMS_VETTING_REQUIRED")
        get_settings.cache_clear()

    assert (held, run.targeted, run.excluded_no_consent) == ("awaiting_vetting", 2, 2)
    assert (run.status, run.sent, run.vetting_ref) == ("completed", 2, "SAF-2026-118")


async def test_twelve_hundred_numbers_go_in_three_batches(
    session: AsyncSession, world: World, gateway: Gateway
) -> None:
    await supporters(session, world, 1200)

    run = await approve(session, world)
    await sms_queue.drain(session, now=TEN_AM)
    await sms_queue.drain(session, now=TEN_AM)
    await session.refresh(run)

    assert [len(batch) for batch in gateway.calls] == [500, 500, 200]
    assert (run.status, run.sent, run.targeted) == ("completed", 1200, 1200)


async def test_a_stop_mid_run_is_skipped_and_halt_stops_the_next_batch(
    session: AsyncSession, world: World, gateway: Gateway, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SMS_BATCH_SIZE", "2")
    get_settings.cache_clear()
    try:
        phones = await supporters(session, world, 6)
        run = await approve(session, world)
        session.add(SmsOptOut(phone=phones[2], campaign_id=world.campaign.id, source="stop"))
        await session.commit()
        await sms_queue.process_next_batch(session, run.id, now=TEN_AM)
        await sms_queue.halt(session, run, "Wrong venue in the text.", actor=world.manager)
        await sms_queue.process_next_batch(session, run.id, now=TEN_AM)
    finally:
        get_settings.cache_clear()

    rows = dict((await session.execute(select(SmsOutbox.phone, SmsOutbox.skip_reason))).all())
    assert gateway.calls == [phones[0:2], phones[3:4]]
    assert rows[phones[2]] == "opted_out"
    assert [rows[p] for p in phones[4:]] == ["halted", "halted"]
    assert (run.status, run.halt_reason) == ("halted", "Wrong venue in the text.")


async def test_a_retried_batch_never_texts_an_accepted_number_twice(
    session: AsyncSession, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    flaky = Gateway(fail_first=1)
    monkeypatch.setattr("backend.services.texting.get_sms_provider", lambda *a, **k: flaky)
    await supporters(session, world, 3)

    run = await approve(session, world)
    early = await sms_queue.process_next_batch(session, run.id, now=TEN_AM)
    retried = await sms_queue.process_next_batch(session, run.id, now=TEN_AM + timedelta(minutes=3))
    again = await sms_queue.process_next_batch(session, run.id, now=TEN_AM + timedelta(hours=1))
    await session.refresh(run)

    assert (early, retried, again) == (0, 3, 0)
    assert Counter(p for batch in flaky.calls for p in batch).most_common(1)[0][1] == 1
    assert run.status == "completed"


@pytest.mark.parametrize(
    ("hour", "minute", "open_"), [(7, 59, False), (8, 0, True), (17, 59, True), (18, 0, False)]
)
def test_the_window_opens_at_eight_and_closes_at_six_nairobi_time(
    hour: int, minute: int, open_: bool
) -> None:
    nairobi = datetime(2026, 11, 24, hour, minute, tzinfo=sms_queue.NAIROBI)

    assert sms_queue.sending_allowed(nairobi) is open_


async def test_a_run_approved_at_six_waits_until_eight_next_morning(
    session: AsyncSession, world: World, gateway: Gateway, monkeypatch: pytest.MonkeyPatch
) -> None:
    await supporters(session, world, 2)
    six_pm = datetime(2026, 11, 24, 18, 0, tzinfo=sms_queue.NAIROBI)
    monkeypatch.setattr("backend.services.sms_queue.clock", lambda: six_pm)

    run = await approve(session, world, now=six_pm)
    (entry,) = await sms_queue.runs(session, world.campaign.id)

    assert (run.status, gateway.calls) == ("scheduled", [])
    assert entry["waiting_until"] == datetime(2026, 11, 25, 8, 0, tzinfo=sms_queue.NAIROBI)


async def test_the_scheduler_drains_due_runs_only_with_the_cron_secret(
    client, session: AsyncSession, world: World, gateway: Gateway, monkeypatch, fresh_settings
) -> None:
    cron = secrets.token_urlsafe(24)
    monkeypatch.setenv("CRON_SECRET", cron)
    await supporters(session, world, 2)
    run = await approve(session, world, now=datetime(2026, 11, 24, 19, 0, tzinfo=sms_queue.NAIROBI))

    refused = await client.get("/api/internal/sms/drain/", headers={"Authorization": "Bearer no"})
    drained = await client.get(
        "/api/internal/sms/drain/", headers={"Authorization": f"Bearer {cron}"}
    )
    await session.refresh(run)

    assert (refused.status_code, drained.json()) == (404, {"runs": 1})
    assert (run.status, run.sent) == ("completed", 2)


async def test_the_demo_drafts_show_the_gate_refusing_and_then_sending_to_the_demo_phones(
    client, session: AsyncSession, world: World, gateway: Gateway
) -> None:
    from backend.seed.demo_comms import seed_demo_texting

    await supporters(session, world, 3, consent_wording=WORDING[ConsentChannel.MOBILIZER])
    demo = await seed_demo_texting(session, ["0799123456", "0711222333"])
    drafts = {
        m.body: m.id
        for m in await session.scalars(
            select(CampaignMessage).where(CampaignMessage.status == "draft")
        )
    }
    manager = world.headers("manager")

    refused = await client.post(
        f"/api/messages/{drafts[min(drafts, key=len)]}/send/",
        json={"language": "en"},
        headers=manager,
    )
    sent = await client.post(
        f"/api/messages/{drafts[max(drafts, key=len)]}/send/",
        json={"language": "en"},
        headers=manager,
    )

    assert demo.ward != world.ward.name
    assert refused.status_code == 400 and "Amina Kariuki" in refused.json()["detail"]
    assert sent.status_code == 200, sent.text
    assert gateway.calls == [["+254711222333", "+254799123456"]]


async def test_two_workers_at_once_never_text_a_number_twice(
    engine: AsyncEngine, session: AsyncSession, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    slow = Gateway(pause=0.2)
    monkeypatch.setattr("backend.services.texting.get_sms_provider", lambda *a, **k: slow)
    await supporters(session, world, 4)
    run = await approve(session, world, now=datetime(2026, 11, 24, 20, 0, tzinfo=sms_queue.NAIROBI))

    async with (
        AsyncSession(engine, expire_on_commit=False) as a,
        AsyncSession(engine, expire_on_commit=False) as b,
    ):
        await asyncio.gather(
            sms_queue.process_next_batch(a, run.id, now=TEN_AM),
            sms_queue.process_next_batch(b, run.id, now=TEN_AM),
        )

    assert Counter(p for batch in slow.calls for p in batch) == Counter(
        {f"+2547{n:08d}": 1 for n in range(1, 5)}
    )


async def test_a_halt_during_a_batch_leaves_the_run_halted(
    engine: AsyncEngine, session: AsyncSession, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    slow = Gateway(pause=0.2)
    monkeypatch.setattr("backend.services.texting.get_sms_provider", lambda *a, **k: slow)
    await supporters(session, world, 4)
    run = await approve(session, world, now=datetime(2026, 11, 24, 20, 0, tzinfo=sms_queue.NAIROBI))

    async with (
        AsyncSession(engine, expire_on_commit=False) as a,
        AsyncSession(engine, expire_on_commit=False) as b,
    ):

        async def halt_it() -> None:
            await asyncio.sleep(0.05)
            await sms_queue.halt(b, await b.get(SmsRun, run.id), "stop", actor=world.manager)

        await asyncio.gather(sms_queue.process_next_batch(a, run.id, now=TEN_AM), halt_it())
    await session.refresh(run)

    assert (run.status, run.halt_reason) == ("halted", "stop")


async def test_a_lost_answer_is_retried_under_the_same_key_and_a_refusal_is_final(
    session: AsyncSession, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    flaky = Gateway(fail_first=1)
    monkeypatch.setattr("backend.services.texting.get_sms_provider", lambda *a, **k: flaky)
    await supporters(session, world, 2)
    run = await approve(session, world)
    await sms_queue.process_next_batch(session, run.id, now=TEN_AM + timedelta(minutes=3))

    refusing = Gateway(refuse=True)
    monkeypatch.setattr("backend.services.texting.get_sms_provider", lambda *a, **k: refusing)
    message = CampaignMessage(campaign_id=world.campaign.id, body=NAMED, wards=[])
    session.add(message)
    await session.commit()
    refused = await sms_queue.approve(
        session,
        message,
        _audience(world.campaign.id, None, [], consenting=False),
        language="en",
        actor=world.manager,
    )
    later = await sms_queue.process_next_batch(session, refused.id, now=TEN_AM + timedelta(hours=1))
    await session.refresh(refused)

    assert len(flaky.keys) == 2 and flaky.keys[0] == flaky.keys[1]
    assert (refused.status, refused.failed, later, len(refusing.keys)) == ("completed", 2, 0, 1)


async def test_a_number_erased_mid_run_is_not_texted(
    session: AsyncSession, world: World, gateway: Gateway, monkeypatch: pytest.MonkeyPatch
) -> None:
    from backend.services.privacy import erase_supporter

    phones = await supporters(session, world, 2)
    run = await approve(session, world, now=datetime(2026, 11, 24, 20, 0, tzinfo=sms_queue.NAIROBI))
    gone = await session.scalar(select(Supporter).where(Supporter.phone == phones[0]))
    await erase_supporter(session, gone, actor=world.manager)
    await session.commit()

    await sms_queue.process_next_batch(session, run.id, now=TEN_AM)

    assert gateway.calls == [[phones[1]]]
