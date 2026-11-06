"""The consent wording each sign-up channel shows, kept once and recorded with the supporter."""

from backend.models.enums import ConsentChannel, OrganisationType, PartyConsentChannel

_PUBLIC_PAGE = "I agree that this campaign may keep my name and phone number to contact me."

WORDING: dict[ConsentChannel, str] = {
    ConsentChannel.EVENT_QR: _PUBLIC_PAGE,
    ConsentChannel.CAMPAIGN_LINK: _PUBLIC_PAGE,
    ConsentChannel.MOBILIZER: "Consent to hold these details under the Data Protection Act, 2019.",
}

PARTY_WORDING: dict[PartyConsentChannel, str] = {
    PartyConsentChannel.WEB_FORM: (
        "I agree that the party may keep my name, phone number, email, ward and polling station "
        "to manage my membership."
    ),
    PartyConsentChannel.OFFICER_ENTRY: (
        "The member agreed to the party keeping their details under the Data Protection Act, 2019."
    ),
}

# The join form's optional tick-box; only members who ticked it get party texts.
MEMBER_SMS_WORDING = "Send me party updates by SMS. I can reply STOP at any time to stop them."

VOLUNTEER_WORDING = (
    "I agree that the party may contact me about volunteering, by the method I chose."
)

# A candidate's "Support" form: the details go to that campaign, not the party.
CAMPAIGN_VOLUNTEER_WORDING = (
    "I agree that this campaign may contact me about volunteering, by the method I chose. "
    "My details go to the campaign only."
)

SUBSCRIBE_WORDING = (
    "I agree that the party may send me news, events and nomination notices by SMS or email "
    "under its privacy notice. I can unsubscribe at any time."
)
# An aspirant installation's news sign-up.
CAMPAIGN_SUBSCRIBE_WORDING = (
    "I agree that the campaign may send me news and events by SMS or email under its privacy "
    "notice. I can unsubscribe at any time."
)


def subscribe_wording(organisation_type: OrganisationType) -> str:
    """The news sign-up's consent wording, shown on the form and recorded with each sign-up."""
    if organisation_type is OrganisationType.ASPIRANT:
        return CAMPAIGN_SUBSCRIBE_WORDING
    return SUBSCRIBE_WORDING
