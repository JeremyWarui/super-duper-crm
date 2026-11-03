"""A party member's own account, as their signed-in page reads it."""

from datetime import datetime

from backend.models import ContactMethod, PartyMemberStatus, Profession, VolunteerStatus
from backend.schemas.common import ORMModel
from backend.schemas.party import MemberPlace


class AccountVolunteer(ORMModel):
    status: VolunteerStatus
    profession: Profession | None
    profession_other: str
    areas: list[str]
    area_other: str
    preferred_contact: ContactMethod
    consent_wording: str
    consent_at: datetime


class AccountRead(ORMModel):
    first_name: str
    full_name: str
    # Only the first two and last three digits show, like 07•• ••• 678.
    phone: str
    email: str | None
    status: PartyMemberStatus
    ward: MemberPlace
    constituency: MemberPlace
    county: MemberPlace
    registration_centre: MemberPlace | None
    member_since: datetime
    consent_wording: str
    consent_at: datetime
    volunteer: AccountVolunteer | None
