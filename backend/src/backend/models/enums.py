"""Choice sets, ported from Django's `TextChoices`.

`StrEnum` keeps the stored value a plain string, so the columns stay VARCHAR
exactly as Django wrote them and JSON serialization is the value itself. The
human label that `get_FOO_display()` used to return lives on `.label`.
"""

from enum import StrEnum


class LabelledStrEnum(StrEnum):
    """A StrEnum carrying Django-style display labels."""

    label: str

    def __new__(cls, value: str, label: str) -> "LabelledStrEnum":
        member = str.__new__(cls, value)
        member._value_ = value
        member.label = label
        return member

    @classmethod
    def choices(cls) -> list[tuple[str, str]]:
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
    """Whichever unit a campaign organizes on, derived from its office level."""

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
