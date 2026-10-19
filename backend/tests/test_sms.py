"""Normalising phone numbers, and the two SMS providers."""

import secrets

import pytest

from backend.config import Settings
from backend.services.sms import (
    AfricasTalkingSMSProvider,
    ConsoleSMSProvider,
    normalise_phone,
)

KEY = secrets.token_urlsafe(48)


def settings(**overrides) -> Settings:
    return Settings(secret_key=KEY, **overrides)


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
    assert normalise_phone(raw) == "+254712345678"


async def test_the_default_provider_sends_nothing(caplog) -> None:
    result = await ConsoleSMSProvider().send(["+254712345678"], "Rally on Saturday")

    assert result.provider == "console"
    assert result.delivered is False
    assert result.requested == 1
    assert "nothing was sent" in result.detail.lower()


def test_the_request_carries_what_the_gateway_expects() -> None:
    key = secrets.token_urlsafe(16)
    provider = AfricasTalkingSMSProvider(username="campaign", api_key=key)

    data, headers = provider.build_request(["+254712345678", "+254722000000"], "Rally Saturday")

    assert data["username"] == "campaign"
    assert data["to"] == "+254712345678,+254722000000"
    assert data["message"] == "Rally Saturday"
    assert headers["apiKey"] == key
    assert headers["Content-Type"] == "application/x-www-form-urlencoded"


# A reply in the shape Africa's Talking documents.
