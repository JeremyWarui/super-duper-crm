"""The consent wording each sign-up channel shows, kept once and recorded with the supporter."""

from backend.models.enums import ConsentChannel

_PUBLIC_PAGE = "I agree that this campaign may keep my name and phone number to contact me."

WORDING: dict[ConsentChannel, str] = {
    ConsentChannel.EVENT_QR: _PUBLIC_PAGE,
    ConsentChannel.CAMPAIGN_LINK: _PUBLIC_PAGE,
    ConsentChannel.MOBILIZER: "Consent to hold these details under the Data Protection Act, 2019.",
}

# The website's volunteer form.
CAMPAIGN_VOLUNTEER_WORDING = (
    "I agree that this campaign may contact me about volunteering, by the method I chose. "
    "My details go to the campaign only."
)

# The website's news sign-up, shown on the form and recorded with each sign-up.
SUBSCRIBE_WORDING = (
    "I agree that the campaign may send me news and events by SMS or email under its privacy "
    "notice. I can unsubscribe at any time."
)
