"""A demo install's sign-ins and the sheet that hands them over."""

from dataclasses import dataclass


@dataclass
class SignIn:
    email: str
    role: str
    sees: str


def credentials_sheet(title: str, sign_ins: list[SignIn], password: str, url: str) -> str:
    """The sign-ins as a Markdown sheet."""
    lines = [
        f"# {title} demo",
        "",
        f"Open {url} and sign in at {url.rstrip('/')}/signin.",
        f"Every login uses the password: `{password}`",
        "",
        "| Email | Role | What to try |",
        "| --- | --- | --- |",
    ]
    lines += [f"| {s.email} | {s.role} | {s.sees} |" for s in sign_ins]
    return "\n".join(lines) + "\n"
