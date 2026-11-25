from pathlib import Path

from backend.config import Settings


def test_live_provider_keys_in_a_developers_env_file_never_reach_the_suite(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text(
        "SMS_PROVIDER=africastalking\nAT_USERNAME=shop\nAT_API_KEY=atsk_live\n"
        "PAYSTACK_SECRET_KEY=sk_live_x\nPAYIN_PROVIDER=paystack\nPAYOUT_PROVIDER=paystack\n"
        "LIVEKIT_URL=wss://x.livekit.cloud\nLIVEKIT_API_KEY=k\nLIVEKIT_API_SECRET=s\n",
        encoding="utf-8",
    )

    settings = Settings(_env_file=env)

    assert settings.sms_provider == "console"
    assert settings.at_api_key == ""
    assert (settings.payin_provider, settings.payout_provider) == ("practice", "practice")
    assert settings.paystack_secret_key == ""
    assert not settings.meetings_configured
