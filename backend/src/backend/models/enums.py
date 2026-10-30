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
    MOBILIZER = ("mobilizer", "Mobilizer")


class OfficeLevel(LabelledStrEnum):
    WARD = ("ward", "Ward (MCA)")
    CONSTITUENCY = ("constituency", "Constituency (MP)")
    COUNTY = ("county", "County (Governor / Senator / Women Rep)")


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


class OperationalGrain(StrEnum):
    """The unit a campaign organizes on."""

    CENTRE = "centre"
    WARD = "ward"


class ConsentChannel(StrEnum):
    """Where a supporter gave consent."""

    EVENT_QR = "event_qr"
    CAMPAIGN_LINK = "campaign_link"
    MOBILIZER = "mobilizer"


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
