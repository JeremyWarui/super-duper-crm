"""The consent wording each sign-up channel shows, kept once and recorded with the supporter."""

from backend.models.enums import ConsentChannel

_PUBLIC_PAGE = "I agree that this campaign may keep my name and phone number to contact me."

WORDING: dict[ConsentChannel, str] = {
    ConsentChannel.EVENT_QR: _PUBLIC_PAGE,
    ConsentChannel.CAMPAIGN_LINK: _PUBLIC_PAGE,
    ConsentChannel.MOBILIZER: "Consent to hold these details under the Data Protection Act, 2019.",
}
