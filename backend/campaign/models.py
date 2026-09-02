"""
Campaign CRM - models

Maps to 9 tables: County -> Constituency -> Ward
                User (candidate, manager, mobilizer, follower )
                Campaing -> Target (win number per ward)
                        -> Mobilizer, Event, Supporter

"""

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models

# Create your models here.

# ===============================
# USERS
# ================================


class User(AbstractUser):
    "Single login model for everyone who signs in"

    class Role(models.TextChoices):
        CANDIDATE = "candidate", "Candidate"
        MANAGER = "manager", "Campaign Manager"
        MOBILIZER = "mobilizer", "Mobilizer"

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.Manager)
    phone = models.CharField(max_length=20, blank=True)

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_role_display()})"


# ========================
# GEOGRAPHY
# ========================


class County(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10, blank=True)
    # total_population = models.PositiveIntegerField(null=True, blank=True)
    registered_voters = models.PositiveIntegerField(null=True, blank=True)
    turnout_2022_pct = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )

    class Meta:
        verbrose_name_pLural = "counties"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Constituency(models.Model):
    county = models.ForeignKey(
        County, on_delete=models.CASCADE, related_name="constituencies"
    )
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10, blank=True)

    class Meta:
        verbose_name_plural = "constituencies"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Ward(models.Model):
    constituency = models.ForeignKey(
        Constituency, on_delete=models.CASCADE, related_name="wards"
    )
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10, blank=True)
    registered_voters = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        verbose_name_plural = "wards"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} — {self.constituency.name}"


class PollingStation(models.Model):
    """A polling station under a ward — the operating unit for a ward (MCA) race"""

    ward = models.ForeignKey(
        Ward, on_delete=models.CASCADE, related_name="polling_stations"
    )
    centre_code = models.CharField(max_length=30, blank=True)  # registration centre
    centre_name = models.CharField(max_length=200, blank=True)
    code = models.CharField(max_length=30, blank=True)  # polling station code
    name = models.CharField(max_length=200)
    registered_voters = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        verbose_name_plural = "polling_stations"
        ordering = ["centre_name", "name"]

    def __str__(self):
        return f"{self.name} — {self.ward.name}"


class RegistrationCentre(models.Model):
    """A registration centre — the physical venue (a school, a church hall) that
    holds several polling stations. This is the OPERATING UNIT for a ward (MCA).
    """

    ward = models.ForeignKey(Ward, on_delete=models.CASCADE, related_name="centres")
    code = models.CharField(max_length=30, blank=True)
    name = models.CharField(max_length=200)
    registered_voters = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} — {self.ward.name}"


# ==============================
# CAMPAIGN (constest)
# ==============================


class Campaign(models.Model):
    class OfficeLevel(models.Model):
        WARD = "ward", "Ward (MCA)"
        CONSTITUENCY = "constituency", "Constituency (MP)"
        COUNTY = "county", "County (Governor / Senator / Women Rep)"

    candidate = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="campaigns"
    )

    title = models.CharField(max_length=150)

    office_level = models.CharField(max_length=20, choices=OfficeLevel.choices)

    county = models.ForeignKey(County, on_delete=models.SET_NULL, null=True, blank=True)

    constituency = models.ForeignKey(
        Constituency, on_delete=models.SET_NULL, null=True, blank=True
    )

    ward = models.ForeignKey(Ward, on_delete=models.SET_NULL, null=True, blank=True)

    election_date = models.DateField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

    @property
    def area(self):
        """Geographic unit this campaign is contesting"""
        return {
            self.OfficeLevel.WARD: self.ward,
            self.OfficeLevel.CONSTITUENCY: self.constituency,
            self.OfficeLevel.COUNTY: self.county,
        }.get(self.office_level)

    @property
    def operational_grain(self):
        """MCA (ward office) campaigns operate at registration-centre level;
        Higher offices (MP, governor, senator, woman rep) operate at ward level.
        """
        return "center" if self.office_level == self.OfficeLevel.Ward else "ward"


# =================================================================
# TARGET (WIN-NUMBER One per ward)
# ================================================================


class Target(models.Model):
    campaign = models.ForeignKey(
        Campaign, on_delete=models.CASCADE, related_name="targets"
    )
    ward = models.ForeignKey(Ward, on_delete=models.CASCADE, related_name="targets")

    registration_center = models.ForeignKey(
        "RegistrationCenter",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="targets",
    )
    projected_turnout_pct = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    votes_needed = models.PositiveIntegerField(null=True, blank=True)
    votes_committed = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            # one target per ward when targeting at ward level
            models.UniqueConstraint(
                fields=["campaign", "ward"],
                condition=models.Q(registration_center__isnull=True),
                name="uniq_ward_target",
            ),
            # one per registration center at center level
            models.UniqueConstraint(
                fields=["campaign", "registration_center"],
                condition=models.Q(registration_center__isnull=False),
                name="uniq_center_target",
            ),
        ]

    def __str__(self):
        return f"{self.ward.name}: need {self.votes_needed or '-'}"

    def compute_win_number(self, save=True):
        """
        50% + 1 of the projected votes cast.
        votes_needed = floor(registered_voters * turnout% / 100 / 2) + 1
        """
        if self.registered_voters and self.projected_turnout_pct:
            projected_cast = (
                self.registered_voters * float(self.projected_turnout_pct) / 100
            )
            self.votes_needed = int(projected_cast // 2) + 1
            if save:
                self.save(update_fields=["votes_needed"])
        return self.votes_needed

    @property
    def votes_remaining(self):
        if self.votes_needed is None:
            return None
        return max(self.votes_needed - self.votes_committed, 0)

    @property
    def progress_pct(self):
        if not self.votes_needed:
            return 0
        return round(self.votes_committed / self.votes_needed * 100, 1)

# ============================================================================
# MOBILIZER  (ground organizer, assigned to a ward)
#==============================================================================
class Mobilizer(models.Model):
    campaign = models.ForeignKey(
        Campaign, on_delete=models.CASCADE, related_name="mobilizers"
    )
    ward = models.ForeignKey(
        Ward, on_delete=models.CASCADE, related_name="mobilizers"
    )
    registration_centre = models.ForeignKey(
        "RegistrationCentre", on_delete=models.SET_NULL, null=True, blank=True, related_name="mobilizers"
    )
    # Optional login — a mobilizer may report through the app, or not.
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="mobilizer_profile",
    )
    full_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # One per ward to start. Add a unique_together on (campaign, ward) later if
    # you want to enforce that; left open so you can grow to several per ward.

    def __str__(self):
        return f"{self.full_name} — {self.ward.name}"


# ===========================================================================
# EVENT  (meeting / rally, with mobilization counts)
# ============================================================================
class Event(models.Model):
    class Status(models.TextChoices):
        PLANNED = "planned", "Planned"
        DONE = "done", "Done"
        CANCELLED = "cancelled", "Cancelled"

    campaign = models.ForeignKey(
        Campaign, on_delete=models.CASCADE, related_name="events"
    )
    ward = models.ForeignKey(
        Ward, on_delete=models.CASCADE, related_name="events"
    )
    registration_centre = models.ForeignKey(
        "RegistrationCentre", on_delete=models.SET_NULL, null=True, blank=True, related_name="events"
    )
    mobilizer = models.ForeignKey(
        Mobilizer,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="events",
    )
    title = models.CharField(max_length=150, blank=True)
    venue = models.CharField(max_length=150, blank=True)
    scheduled_date = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PLANNED
    )
    number_reached = models.PositiveIntegerField(default=0)
    number_attended = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-scheduled_date"]

    def __str__(self):
        return self.title or f"Event in {self.ward.name}"

    @property
    def turnout_pct(self):
        """Attendance vs. how many were reached to invite them."""
        if not self.number_reached:
            return 0
        return round(self.number_attended / self.number_reached * 100, 1)


# ===========================================================================
# SUPPORTER  (from public self-registration)
# ===========================================================================
class Supporter(models.Model):
    class SupportLevel(models.TextChoices):
        SUPPORTER = "supporter", "Supporter"
        UNDECIDED = "undecided", "Undecided"
        OPPOSED = "opposed", "Opposed"

    campaign = models.ForeignKey(
        Campaign, on_delete=models.CASCADE, related_name="supporters"
    )
    ward = models.ForeignKey(
        Ward,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="supporters",
    )
    mobilizer = models.ForeignKey(
        Mobilizer,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="supporters",
    )
    full_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=20, blank=True)
    support_level = models.CharField(
        max_length=20, choices=SupportLevel.choices, default=SupportLevel.UNDECIDED
    )
    consent_given = models.BooleanField(
        default=False
    )  # Data Protection Act 2019 — capture consent at sign-up
    registered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-registered_at"]

    def __str__(self):
        return self.full_name
