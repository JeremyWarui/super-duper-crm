"""Refusals the services raise; the API answers them as 400, or 404 for NotFound."""


class Refused(Exception):
    """A request that cannot be done, with the reason to show."""


class NotFound(Refused):
    """The named row does not exist."""
