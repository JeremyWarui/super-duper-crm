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

    @classmethod
    def choices(cls) -> list[tuple[str, str]]:
        """Every member as a (value, label) pair."""
        return [(member.value, member.label) for member in cls]


class UserRole(LabelledStrEnum):
    CANDIDATE = ("candidate", "Candidate")
    MANAGER = ("manager", "Campaign Manager")
    MOBILIZER = ("mobilizer", "Mobilizer")


class OfficeLevel(LabelledStrEnum):
    WARD = ("ward", "Ward (MCA)")
    CONSTITUENCY = ("constituency", "Constituency (MP)")
    COUNTY = ("county", "County (Governor / Senator / Women Rep)")


class OperationalGrain(StrEnum):
    """The unit a campaign organizes on."""

    CENTRE = "centre"
    WARD = "ward"


class EventStatus(LabelledStrEnum):
    PLANNED = ("planned", "Planned")
    DONE = ("done", "Done")
    CANCELLED = ("cancelled", "Cancelled")


class SupportLevel(LabelledStrEnum):
    SUPPORTER = ("supporter", "Supporter")
    UNDECIDED = ("undecided", "Undecided")
    OPPOSED = ("opposed", "Opposed")
