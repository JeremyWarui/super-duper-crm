"""The choice sets used by the models."""

from enum import StrEnum


class LabelledStrEnum(StrEnum):
    """A string enum where each member also carries a display label."""

    label: str

    def __new__(cls, value: str, label: str) -> "LabelledStrEnum":
        member = str.__new__(cls, value)
        member._value_ = value
        member.label = label
        return member


class UserRole(LabelledStrEnum):
    CANDIDATE = ("candidate", "Candidate")
    MANAGER = ("manager", "Campaign Manager")
    COORDINATOR = ("coordinator", "Coordinator")
    COMMS = ("comms", "Comms")
    MOBILIZER = ("mobilizer", "Mobilizer")
    AGENT = ("agent", "Agent")


class UserKind(LabelledStrEnum):
    """A login works on a campaign, holds party offices, or is a party member's own account."""

    CAMPAIGN = ("campaign", "Campaign login")
    STAFF = ("staff", "Party staff login")
    MEMBER = ("member", "Member login")


class PartyRoleName(LabelledStrEnum):
    """A party office held by a login that has no campaign role."""

    MEMBERSHIP_OFFICER = ("membership_officer", "Membership Officer")
    NOMINATIONS_OFFICER = ("nominations_officer", "Nominations Officer")


class OfficeLevel(LabelledStrEnum):
    WARD = ("ward", "Ward (MCA)")
    CONSTITUENCY = ("constituency", "Constituency (MP)")
    COUNTY = ("county", "County (Governor / Senator / Women Rep)")
    NATIONAL = ("national", "National (party workspace)")


class WorkspaceKind(LabelledStrEnum):
    """Who a campaign workspace belongs to, which decides who may create it and when it opens."""

    PARTY = ("party", "Party workspace")
    HOSTED = ("hosted", "Hosted workspace")
    STANDALONE = ("standalone", "Standalone workspace")


class Seat(LabelledStrEnum):
    """The office contested; several seats share an area scope."""

    MCA = ("mca", "MCA")
    MP = ("mp", "MP")
    GOVERNOR = ("governor", "Governor")
    SENATOR = ("senator", "Senator")
    WOMEN_REP = ("women_rep", "Women Rep")

    @property
    def office_level(self) -> OfficeLevel:
        """The area the seat is contested over."""
        if self is Seat.MCA:
            return OfficeLevel.WARD
        if self is Seat.MP:
            return OfficeLevel.CONSTITUENCY
        return OfficeLevel.COUNTY


class AspirantStatus(LabelledStrEnum):
    DRAFT = ("draft", "Draft")
    SUBMITTED = ("submitted", "Submitted")
    APPROVED = ("approved", "Approved")
    REJECTED = ("rejected", "Rejected")
    WITHDRAWN = ("withdrawn", "Withdrawn")
    SUSPENDED = ("suspended", "Suspended")


class OperationalGrain(StrEnum):
    """The unit a campaign organizes on."""

    CENTRE = "centre"
    WARD = "ward"


class FieldRole(LabelledStrEnum):
    """The roles a person may sign themselves up for on a workspace's team link."""

    MOBILIZER = ("mobilizer", "Mobilizer")
    AGENT = ("agent", "Agent")


class RegistrationStatus(LabelledStrEnum):
    PENDING = ("pending", "Waiting for a decision")
    APPROVED = ("approved", "Approved")
    REJECTED = ("rejected", "Not approved")


class AgentStatus(LabelledStrEnum):
    """How far a polling agent has come before polling day."""

    APPLIED = ("applied", "Applied")
    VETTED = ("vetted", "Vetted")
    TRAINED = ("trained", "Trained")
    READY = ("ready", "Ready")


class AssignmentKind(LabelledStrEnum):
    EVENT = ("event", "Event")
    WARD_WORK = ("ward_work", "Ward work")
    ACTIVITY = ("activity", "Activity")


class AssignmentStatus(LabelledStrEnum):
    ASSIGNED = ("assigned", "Assigned")
    DONE = ("done", "Done")
    CANCELLED = ("cancelled", "Cancelled")


class LinkPurpose(StrEnum):
    """What a one-time sign-in link does."""

    INVITE = "invite"
    RESET = "reset"


class ConsentChannel(StrEnum):
    """Where a supporter gave consent."""

    EVENT_QR = "event_qr"
    CAMPAIGN_LINK = "campaign_link"
    MOBILIZER = "mobilizer"


class PartyMemberStatus(LabelledStrEnum):
    PENDING = ("pending", "Pending")
    APPROVED = ("approved", "Approved")
    REJECTED = ("rejected", "Rejected")
    SUSPENDED = ("suspended", "Suspended")
    WITHDRAWN = ("withdrawn", "Withdrawn")


class PartyConsentChannel(StrEnum):
    """Where a party member gave consent."""

    WEB_FORM = "web_form"
    OFFICER_ENTRY = "officer_entry"


class EventStatus(LabelledStrEnum):
    PLANNED = ("planned", "Planned")
    DONE = ("done", "Done")
    CANCELLED = ("cancelled", "Cancelled")


class PaymentStatus(LabelledStrEnum):
    SCHEDULED = ("scheduled", "Scheduled")
    SENDING = ("sending", "Sending")
    PAID = ("paid", "Paid")
    FAILED = ("failed", "Failed")
    CANCELLED = ("cancelled", "Cancelled")


class SupportLevel(LabelledStrEnum):
    SUPPORTER = ("supporter", "Supporter")
    UNDECIDED = ("undecided", "Undecided")
    OPPOSED = ("opposed", "Opposed")


class PartyRequestKind(StrEnum):
    """What a public request to the party register asks for."""

    JOIN = "join"
    WITHDRAW = "withdraw"
    VOLUNTEER_WITHDRAW = "volunteer_withdraw"


class VolunteerStatus(LabelledStrEnum):
    INTERESTED = ("interested", "Interested")
    ACTIVE = ("active", "Active")
    INACTIVE = ("inactive", "Inactive")
    WITHDRAWN = ("withdrawn", "Withdrawn")


class VolunteerArea(LabelledStrEnum):
    FUNDRAISING = ("fundraising", "Fundraising Support")
    DOOR_TO_DOOR = ("door_to_door", "Door-to-door Campaign")
    MOBILISING_VOTERS = ("mobilising_voters", "Mobilising Voters")
    SOCIAL_MEDIA = ("social_media", "Social Media Support")
    RECRUITING = ("recruiting", "Recruiting Volunteers")
    MATERIALS = ("materials", "Distributing Campaign Materials")
    DATA_COLLECTION = ("data_collection", "Data Collection")
    COMMUNITY_LISTENING = ("community_listening", "Community Listening")
    BARAZAS = ("barazas", "Holding Barazas & Household Meetings")
    OTHER = ("other", "Other")


class Profession(LabelledStrEnum):
    FARMER = ("farmer", "Farmer")
    TEACHER = ("teacher", "Teacher")
    BUSINESS = ("business", "Business")
    STUDENT = ("student", "Student")
    OTHER = ("other", "Other")


class ContactMethod(LabelledStrEnum):
    CALL = ("call", "Call")
    SMS = ("sms", "SMS")
    WHATSAPP = ("whatsapp", "WhatsApp")
    EMAIL = ("email", "Email")


class PostKind(LabelledStrEnum):
    """What a public post is: a news item or a party event."""

    NEWS = ("news", "News")
    EVENT = ("event", "Event")


class PostLabel(LabelledStrEnum):
    """How a news post presents itself: an official statement, news, or a writer's opinion."""

    STATEMENT = ("statement", "Statement")
    NEWS = ("news", "News")
    OPINION = ("opinion", "Opinion")


class OrganisationType(LabelledStrEnum):
    """Who runs this copy: a party or a single aspirant. Set once, at setup."""

    PARTY = ("party", "Party")
    ASPIRANT = ("aspirant", "Aspirant")


class FileArea(LabelledStrEnum):
    """Where an uploaded file is used."""

    SITE = ("site", "Site settings")
    SLIDES = ("slides", "Hero slides")
    LEADERS = ("leaders", "Party leaders")
    DOCUMENTS = ("documents", "Documents")
    CANDIDATES = ("candidates", "Candidate pages")
    MINUTES = ("minutes", "Branch meeting minutes")
    NOMINATIONS = ("nominations", "Nomination documents")


class BranchOffice(LabelledStrEnum):
    """An office on a county branch, in the order the branch lists them."""

    CHAIR = ("chair", "Chairperson")
    SECRETARY = ("secretary", "Secretary")
    TREASURER = ("treasurer", "Treasurer")
    ORGANISING_SECRETARY = ("organising_secretary", "Organising secretary")
    YOUTH_LEADER = ("youth_leader", "Youth leader")
    WOMEN_LEADER = ("women_leader", "Women leader")
    OTHER = ("other", "Other office")


class TermStart(LabelledStrEnum):
    ELECTED = ("elected", "Elected at a branch meeting")
    INTERIM = ("interim", "Interim appointment")
    RECORDED = ("recorded", "Recorded before terms were kept")


class TermEnd(LabelledStrEnum):
    REPLACED = ("replaced", "Replaced")
    RESIGNED = ("resigned", "Resigned")
    REMOVED = ("removed", "Removed")
    COMPLETED = ("completed", "Term completed")
