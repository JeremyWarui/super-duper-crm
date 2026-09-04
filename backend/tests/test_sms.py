"""Normalising phone numbers, and the two SMS providers."""

import pytest

from backend.config import Settings
from backend.services.sms import (
    AfricasTalkingSMSProvider,
    ConsoleSMSProvider,
    SendResult,
    get_sms_provider,
    normalise_all,
    normalise_phone,
)

KEY = "test-secret-key-at-least-32-characters-long"


def settings(**overrides) -> Settings:
    return Settings(secret_key=KEY, **overrides)


# ------------------------------------------------------------------- numbers


@pytest.mark.parametrize(
    "raw",
    [
        "+254712345678",
        "254712345678",
        "0712345678",
        "712345678",
        "+254 712 345 678",
        "0712 345 678",
        "254-712-345-678",
        "  +254712345678  ",
        "(0712) 345678",
    ],
)
def test_the_ways_a_register_spells_one_number(raw: str) -> None:
    """All of these are the same person, typed by different hands."""
    assert normalise_phone(raw) == "+254712345678"


@pytest.mark.parametrize(
    "raw",
    [
        None,
        "",
        "   ",
        "not a phone",
        "0712345",  # too short
        "07123456789",  # too long
        "+1234567890123",  # not a Kenyan number
        "+254+712345678",  # a plus that is not at the front
        "++254712345678",
        "0012345678",  # national part cannot start with a zero
    ],
)
def test_what_is_not_a_number_is_refused_rather_than_guessed_at(raw) -> None:
    """A wrong number is a message delivered to a stranger, and billed for."""
    assert normalise_phone(raw) is None


def test_a_safaricom_and_an_airtel_number_both_pass() -> None:
    assert normalise_phone("0722000000") == "+254722000000"
    assert normalise_phone("0733000000") == "+254733000000"
    assert normalise_phone("0110000000") == "+254110000000"


def test_the_same_person_listed_twice_is_messaged_once() -> None:
    """Both spellings are one number, and a gateway bills per number."""
    keep, rejected = normalise_all(["0712345678", "+254712345678", "254 712 345 678"])
    assert keep == ["+254712345678"]
    assert rejected == []


def test_the_unusable_are_reported_rather_than_dropped(caplog) -> None:
    keep, rejected = normalise_all(["0712345678", "", "not a phone", None])
    assert keep == ["+254712345678"]
    assert [r.status for r in rejected] == ["invalid", "invalid", "invalid"]
    assert rejected[1].phone == "not a phone"


def test_an_empty_register_sends_to_nobody() -> None:
    assert normalise_all([]) == ([], [])


# --------------------------------------------------------------- the default


async def test_the_default_provider_sends_nothing(caplog) -> None:
    """There is no subscription; a screen must not be able to claim otherwise."""
    result = await ConsoleSMSProvider().send(["+254712345678"], "Rally on Saturday")

    assert result.provider == "console"
    assert result.delivered is False
    assert result.requested == 1
    assert "nothing was sent" in result.detail.lower()


async def test_the_default_provider_says_how_to_turn_sending_on() -> None:
    result = await ConsoleSMSProvider().send(["+254712345678"], "Hello")
    assert "AT_USERNAME" in result.detail
    assert "SMS_PROVIDER=africastalking" in result.detail


def test_the_console_provider_is_what_a_fresh_install_gets() -> None:
    assert get_sms_provider(settings()).name == "console"


def test_choosing_the_gateway_needs_its_credentials() -> None:
    """Fail at startup, not on the first invitation nobody receives."""
    with pytest.raises(ValueError, match="AT_USERNAME"):
        settings(sms_provider="africastalking")


def test_the_gateway_is_used_once_it_is_configured() -> None:
    provider = get_sms_provider(
        settings(sms_provider="africastalking", at_username="u", at_api_key="k")
    )
    assert provider.name == "africastalking"


# ------------------------------------------------------- africa's talking


def test_the_gateway_refuses_to_be_built_without_credentials() -> None:
    with pytest.raises(ValueError, match="AT_USERNAME"):
        AfricasTalkingSMSProvider(username="", api_key="")
    with pytest.raises(ValueError, match="AT_API_KEY"):
        AfricasTalkingSMSProvider(username="campaign", api_key="")


def test_the_request_carries_what_the_gateway_expects() -> None:
    provider = AfricasTalkingSMSProvider(username="campaign", api_key="secret")

    data, headers = provider.build_request(["+254712345678", "+254722000000"], "Rally Saturday")

    assert data["username"] == "campaign"
    assert data["to"] == "+254712345678,+254722000000"
    assert data["message"] == "Rally Saturday"
    assert headers["apiKey"] == "secret"
    assert headers["Content-Type"] == "application/x-www-form-urlencoded"


def test_a_registered_sender_is_sent_and_a_blank_one_is_not() -> None:
    """Blank falls back to the shared short code; an empty `from` is refused."""
    with_id, _ = AfricasTalkingSMSProvider("u", "k", sender_id="MZIGO").build_request(
        ["+254712345678"], "x"
    )
    without, _ = AfricasTalkingSMSProvider("u", "k").build_request(["+254712345678"], "x")

    assert with_id["from"] == "MZIGO"
    assert "from" not in without


def test_the_sandbox_username_never_hits_the_live_gateway() -> None:
    """Their sandbox only answers to the literal username "sandbox"."""
    assert AfricasTalkingSMSProvider("sandbox", "k").url.startswith(
        AfricasTalkingSMSProvider.SANDBOX_URL
    )
    assert AfricasTalkingSMSProvider("campaign", "k").url == AfricasTalkingSMSProvider.LIVE_URL
    assert AfricasTalkingSMSProvider("campaign", "k", sandbox=True).url == (
        AfricasTalkingSMSProvider.SANDBOX_URL
    )


# A reply in the shape Africa's Talking documents.
GATEWAY_REPLY = {
    "SMSMessageData": {
        "Message": "Sent to 1/2 Total Cost: KES 0.8000",
        "Recipients": [
            {
                "statusCode": 101,
                "number": "+254712345678",
                "status": "Success",
                "cost": "KES 0.8000",
                "messageId": "ATXid_abc",
            },
            {
                "statusCode": 403,
                "number": "+254722000000",
                "status": "UserInBlacklist",
                "cost": "0",
            },
        ],
    }
}


def test_the_reply_is_split_into_what_was_taken_and_what_was_not() -> None:
    result = AfricasTalkingSMSProvider.parse_response(GATEWAY_REPLY, "Rally Saturday", 2)

    assert result.delivered is True
    assert [r.phone for r in result.accepted] == ["+254712345678"]
    assert [r.phone for r in result.rejected] == ["+254722000000"]
    assert result.rejected[0].status == "UserInBlacklist"
    assert "Total Cost" in result.detail


def test_a_reply_taking_nobody_is_not_a_delivery() -> None:
    payload = {"SMSMessageData": {"Message": "Sent to 0/1", "Recipients": []}}
    result = AfricasTalkingSMSProvider.parse_response(payload, "x", 1)

    assert result.delivered is False
    assert result.accepted == []


def test_a_reply_with_nothing_in_it_does_not_raise() -> None:
    """Their errors do not always match the documented shape."""
    result = AfricasTalkingSMSProvider.parse_response({}, "x", 1)
    assert result.delivered is False
    assert result.requested == 1


# ------------------------------------------------------------------- billing


@pytest.mark.parametrize(
    ("length", "parts"),
    [(0, 0), (1, 1), (160, 1), (161, 2), (320, 2), (321, 3)],
)
def test_a_message_is_billed_in_one_hundred_and_sixty_character_parts(
    length: int, parts: int
) -> None:
    """The cost of a send is per part per recipient, so the count is shown."""
    result = SendResult(provider="console", delivered=False, message="x" * length, requested=1)
    assert result.parts == parts
