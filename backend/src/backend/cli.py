"""campaign-crm: load reference data, seed the demo, and run the admin operations."""

import argparse
import asyncio
import getpass
import sys
import uuid
from collections.abc import Awaitable, Callable
from pathlib import Path

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import get_organisation_type
from backend.db.session import get_engine, get_sessionmaker
from backend.models import County, UserRole
from backend.seed.demo import seed_demo
from backend.seed.reference import (
    CAW_CSV,
    CENTRES_CSV,
    COUNTY_RESULTS_CSV,
    COUNTY_VOTERS_CSV,
    import_centres,
    import_geography,
)
from backend.seed.site import seed_branches, seed_home, seed_news, seed_site
from backend.services import admin, imports, ops, setup
from backend.services.accounts import clean_email, new_login, user_with_email
from backend.services.audit import record
from backend.services.clock import today
from backend.services.errors import Refused


async def _seed(args: argparse.Namespace, session: AsyncSession) -> int:
    if await session.scalar(select(County).limit(1)) is not None and not args.force:
        print("Reference data is already loaded. Pass --force to reload it.")
        return 0

    print("Loading geography...")
    geography = await import_geography(
        session,
        caw=Path(args.caw),
        county_voters=Path(args.county_voters),
        county_results=Path(args.county_results),
    )
    print(
        f"  {geography.counties} counties, {geography.constituencies} constituencies, "
        f"{geography.wards} wards. Turnout set for {geography.turnout_set} counties."
    )

    centres_csv = Path(args.centres)
    if not centres_csv.exists():
        print(f"No {centres_csv.name} found; registration centres must load with the wards.")
        return 1
    print("Loading registration centres...")
    centres = await import_centres(session, centres_csv)
    print(f"  {centres.centres:,} centres across {centres.wards_covered:,} wards.")
    if centres.skipped_special:
        print(
            f"  {centres.skipped_special:,} diaspora and prison rows left out: "
            "neither sits in a ward."
        )
    if centres.unmatched:
        print(f"  {len(centres.unmatched)} rows matched no ward, e.g. {centres.unmatched[:3]}")
    return 0


async def _demo(args: argparse.Namespace, session: AsyncSession) -> int:
    summary = await seed_demo(session, password=args.password)
    print(f"{summary.campaign_title} - {summary.office}")
    print(f"  {summary.units} units, win number {summary.win_number:,}")
    print("\nSign in at http://localhost:5173 as (shown once, re-run to reset):")
    width = max(len(email) for email, _, _ in summary.sign_ins)
    for email, password, description in summary.sign_ins:
        print(f"  {email:<{width}}  {password:<20}  {description}")
    return 0


async def _demo_site(args: argparse.Namespace, session: AsyncSession) -> int:
    added = await seed_branches(session, today())
    if added:
        print(f"Published a demo branch for {added} counties.")
    if await seed_home(session):
        print("Published the demo homepage slides and agenda issues.")
    seeded = await seed_site(session, today())
    if await seed_news(session, today()):
        print("Published the demo statements, opinions, event counties, About page and results.")
    if not seeded:
        print("The website already has leaders or posts; nothing else was added.")
        return 0
    print("Published 6 leaders, 4 news posts and 3 events for Pamoja Party.")
    print("Open http://localhost:5173/ to see the site.")
    return 0


async def _createuser(args: argparse.Namespace, session: AsyncSession) -> int:
    password = args.password or getpass.getpass("Password: ")
    if not password:
        print("A password is required.", file=sys.stderr)
        return 1
    user, _ = await new_login(
        session,
        username=args.username,
        role=UserRole(args.role),
        password=password,
        email=args.email,
        first_name=args.first_name,
        last_name=args.last_name,
        phone=args.phone,
        is_superuser=args.superuser,
    )
    record(
        session,
        actor=None,
        action="user.create",
        subject_type="user",
        subject_id=user.id,
        detail={"role": user.role.value if user.role else None, "superuser": args.superuser},
    )
    await session.commit()
    print(f"Created {user}.")
    return 0


async def _campaign(args: argparse.Namespace, session: AsyncSession) -> int:
    """Every campaign with its candidate, or one campaign in full with -c."""
    if args.campaign is None:
        found = await admin.campaigns(session)
        for row in found:
            candidate = row.candidate or "-- none --"
            print(f"{row.id}  {row.title}  candidate {candidate}  members {len(row.members)}")
        if not found:
            print("No campaigns.")
        return 0

    row = await admin.campaign(session, args.campaign)
    print(row.title)
    print(f"  id         {row.id}")
    print(f"  seat       {row.office_level}")
    print(f"  candidate  {row.candidate or '-- none --'}")
    print(f"  election   {row.election_date or 'not set'}")
    print("  team")
    for member in row.members:
        print(f"    {member.role.value:10} {member.username}")
    print(f"  targets    {row.targets}")
    print(f"  mobilizers {row.mobilizers}")
    print(f"  events     {row.events}")
    print(f"  supporters {row.supporters}")
    print(f"  votes      {row.votes_needed:,} needed, {row.votes_committed:,} committed")
    return 0


async def _users(args: argparse.Namespace, session: AsyncSession) -> int:
    """Every login, its role, and the campaign it is on."""
    role = UserRole(args.role) if args.role else None
    people = await admin.users(session, role=role, campaign_id=args.campaign)
    for user in people:
        flags = ("" if user.is_active else "  [disabled]") + (
            "  [superuser]" if user.is_superuser else ""
        )
        seen = user.last_login_at[:10] if user.last_login_at else "never"
        role = user.role.value if user.role else "-"
        print(f"{user.username:20} {role:10} last in {seen}{flags}")
        print(f"    {user.campaign or 'on no campaign'}")
    if not people:
        print("No users.")
    return 0


async def _backup(_: argparse.Namespace, session: AsyncSession) -> int:
    run = await ops.backup(session)
    if run.status != "ok":
        print(f"Backup failed: {run.detail}", file=sys.stderr)
        return 1
    print(f"Backed up to {run.path} ({run.size:,} bytes). {run.detail}".strip())
    return 0


async def _restore(args: argparse.Namespace, _: AsyncSession) -> int:
    try:
        print(
            await asyncio.to_thread(
                ops.restore, Path(args.file), confirmed=args.yes_erase_current_data
            )
        )
    except Refused as refused:
        print(refused, file=sys.stderr)
        return 1
    return 0


async def _export(args: argparse.Namespace, session: AsyncSession) -> int:
    kind = await get_organisation_type(session)
    name, data = await ops.export_archive(session, actor=None, organisation_type=kind)
    out = Path(args.out or name)
    out.write_bytes(data)
    print(f"Exported to {out.resolve()} ({len(data):,} bytes).")
    return 0


async def _import(args: argparse.Namespace, session: AsyncSession) -> int:
    path = Path(args.file)
    boundaries = args.command == "import-boundaries"
    run = imports.import_boundaries if boundaries else imports.import_register
    try:
        report = await run(
            session,
            path.read_text(encoding="utf-8-sig"),
            filename=path.name,
            actor=None,
            dry_run=args.dry_run,
        )
    except imports.ImportRefused as refused:
        print("Nothing was imported. Fix these lines and run it again:", file=sys.stderr)
        for line in refused.errors:
            print(f"  {line}", file=sys.stderr)
        return 1
    for change in report.changes:
        print(f"  {change.change:9} {change.level:12} {change.code:14} {change.detail}")
    counts = ", ".join(f"{n} {kind}" for kind, n in sorted(report.counts.items())) or "no changes"
    done = "Would change" if args.dry_run else "Changed"
    print(f"{done}: {counts} ({report.rows} rows read).")
    if report.kind == "register" and report.changes and not args.dry_run:
        print("Targets keep their numbers until a manager presses Refresh targets.")
    return 0


async def _setup_token(_: argparse.Namespace, session: AsyncSession) -> int:
    token = await setup.new_token(session)
    print(f"Setup token, valid 24 hours and spent on use: {token}")
    print("Open /setup on the site and paste it in. Any earlier token no longer works.")
    return 0


async def _reset_password(args: argparse.Namespace, session: AsyncSession) -> int:
    user = await admin.user_by_name(session, args.username)
    password = await admin.set_password(session, user.id, args.password)
    print(f"{args.username} signs in with: {password}")
    print("Shown once, and every other session is signed out.")
    return 0


async def _set_email(args: argparse.Namespace, session: AsyncSession) -> int:
    user = await admin.user_by_name(session, args.username)
    email = clean_email(args.email)
    holder = await user_with_email(session, email)
    if holder is not None and holder.id != user.id:
        raise Refused(f"The email {email} already belongs to {holder.username}.")
    user.email = email
    record(session, actor=None, action="user.email", subject_type="user", subject_id=user.id)
    await session.commit()
    print(f"{args.username} signs in with the email {email}.")
    return 0


async def _add_member(args: argparse.Namespace, session: AsyncSession) -> int:
    user = await admin.user_by_name(session, args.username)
    member = await admin.add_member(session, args.campaign, user.id, actor=None)
    print(f"{args.username} is on that campaign as its {member.role.label.lower()}.")
    return 0


async def _remove_member(args: argparse.Namespace, session: AsyncSession) -> int:
    user = await admin.user_by_name(session, args.username)
    await admin.remove_member(session, args.campaign, user.id, actor=None)
    print(f"{args.username} is off that campaign.")
    return 0


async def _reset_database(args: argparse.Namespace, session: AsyncSession) -> int:
    """Empty the database's public schema, ready for `alembic upgrade head`; Postgres only.

    Runs only when --yes names the database it is connected to.
    """
    if session.bind.dialect.name != "postgresql":
        print(
            "reset-database works on Postgres only; delete a SQLite file instead.", file=sys.stderr
        )
        return 1
    name = await session.scalar(text("SELECT current_database()"))
    if args.yes != name:
        print(
            f"This would delete every table and row in the database {name}. "
            f"Run it again with --yes {name}.",
            file=sys.stderr,
        )
        return 1
    await session.execute(text("DROP SCHEMA public CASCADE"))
    # Owned and granted as a new database's public schema is.
    await session.execute(text("CREATE SCHEMA public AUTHORIZATION pg_database_owner"))
    await session.execute(text("GRANT USAGE ON SCHEMA public TO PUBLIC"))
    await session.commit()
    print(f"Emptied {name}. Next: alembic upgrade head, then campaign-crm seed.")
    return 0


async def _rename_campaign(args: argparse.Namespace, session: AsyncSession) -> int:
    campaign = await admin.rename_campaign(session, args.campaign, args.title, actor=None)
    print(f"The campaign is now called {campaign.title}.")
    return 0


async def _delete_campaign(args: argparse.Namespace, session: AsyncSession) -> int:
    """Without --yes, only say what and who would be deleted."""
    row = await admin.campaign(session, args.campaign)
    people = await admin.logins_on(session, args.campaign)
    logins = ", ".join(person.username for person in people) or "none"
    what = (
        f"{row.title} with {row.targets} targets, {row.mobilizers} mobilizers, "
        f"{row.events} events, {row.supporters} supporters, and {len(people)} logins "
        f"({logins})"
    )
    if not args.yes:
        print(f"This would delete {what}. Run it again with --yes.", file=sys.stderr)
        return 1
    gone = await admin.delete_campaign(session, args.campaign, actor=None)
    print(f"Deleted {row.title} and {len(gone)} logins: {', '.join(gone) or 'none'}.")
    return 0


async def _set_active(args: argparse.Namespace, session: AsyncSession) -> int:
    user = await admin.user_by_name(session, args.username)
    await admin.set_active(session, user.id, args.active, actor=None)
    print(f"{args.username} is {'enabled' if args.active else 'disabled'}.")
    return 0


Handler = Callable[[argparse.Namespace, AsyncSession], Awaitable[int]]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="campaign-crm", description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    def command(name: str, handler: Handler, help_text: str, **defaults) -> argparse.ArgumentParser:
        sub = subparsers.add_parser(name, help=help_text)
        sub.set_defaults(handler=handler, **defaults)
        return sub

    def needs_user(sub: argparse.ArgumentParser) -> None:
        sub.add_argument("-u", "--username", required=True)

    def needs_campaign(sub: argparse.ArgumentParser, required: bool = True) -> None:
        sub.add_argument("-c", "--campaign", required=required, type=uuid.UUID, help="campaign id")

    seed = command("seed", _seed, "load the bundled 2022 reference data")
    seed.add_argument("--caw", default=str(CAW_CSV), help="wards and their registered voters")
    seed.add_argument("--county-voters", default=str(COUNTY_VOTERS_CSV))
    seed.add_argument("--county-results", default=str(COUNTY_RESULTS_CSV))
    seed.add_argument("--centres", default=str(CENTRES_CSV))
    seed.add_argument("--force", action="store_true", help="reload even if data is present")

    demo = command("demo", _demo, "build the demo campaign and its sign-ins")
    demo.add_argument("-p", "--password", help="one password for every demo account")

    command(
        "demo-site", _demo_site, "brand the party; publish demo leaders, news, events and branches"
    )

    createuser = command("createuser", _createuser, "add a login")
    needs_user(createuser)
    createuser.add_argument(
        "-r",
        "--role",
        default=UserRole.MANAGER.value,
        choices=[r.value for r in (UserRole.CANDIDATE, UserRole.MANAGER, UserRole.MOBILIZER)],
    )
    createuser.add_argument("-p", "--password", help="prompted for when left out")
    createuser.add_argument("--email", default="")
    createuser.add_argument("--first-name", default="")
    createuser.add_argument("--last-name", default="")
    createuser.add_argument("--phone", default="")
    createuser.add_argument("--superuser", action="store_true")

    needs_campaign(
        command("campaign", _campaign, "every campaign, or one in full with -c"), required=False
    )

    users = command("users", _users, "every login and the campaign it is on")
    users.add_argument("-r", "--role", choices=[r.value for r in UserRole])
    needs_campaign(users, required=False)

    set_email = command("set-email", _set_email, "give a login the email it signs in with")
    needs_user(set_email)
    set_email.add_argument("--email", required=True)

    command("setup-token", _setup_token, "print a one-time token that opens the first-run setup")
    command(
        "backup", _backup, "dump the database and uploads into BACKUP_DIR; keeps 14 daily, 8 weekly"
    )
    restore = command("restore", _restore, "replace the database and uploads with a backup")
    restore.add_argument("file", help="a backup-*.tar.gz archive")
    restore.add_argument(
        "--yes-erase-current-data", action="store_true", help="required: it erases today's data"
    )
    export = command("export", _export, "write every table as JSON and CSV in one zip")
    export.add_argument("--out", help="where to write it; default export-<time>.zip here")
    for name, help_text in (
        ("import-boundaries", "upsert counties, constituencies, wards and centres from a CSV"),
        ("import-register", "update registered voters and county turnout from a CSV"),
    ):
        sub = command(name, _import, help_text)
        sub.add_argument("file", help="the CSV file; see docs/handover/samples")
        sub.add_argument("--dry-run", action="store_true", help="report the changes, write nothing")
    reset = command("reset-password", _reset_password, "give a login a new password")
    needs_user(reset)
    reset.add_argument("-p", "--password", help="generated when left out")

    for name, handler, help_text in (
        ("add-member", _add_member, "put somebody on a campaign"),
        ("remove-member", _remove_member, "take somebody off a campaign"),
    ):
        sub = command(name, handler, help_text)
        needs_user(sub)
        needs_campaign(sub)

    rename = command("rename-campaign", _rename_campaign, "change what a campaign is called")
    needs_campaign(rename)
    rename.add_argument("-t", "--title", required=True)

    drop = command(
        "delete-campaign", _delete_campaign, "delete a campaign, everything on it, and its logins"
    )
    needs_campaign(drop)
    drop.add_argument("--yes", action="store_true", help="delete it, rather than only saying what")

    wipe = command(
        "reset-database",
        _reset_database,
        "empty the whole database, ready to rebuild from the migrations (Postgres)",
    )
    wipe.add_argument("--yes", metavar="DATABASE", help="the database's name, to confirm")

    needs_user(command("deactivate", _set_active, "stop a login working", active=False))
    needs_user(command("activate", _set_active, "let a disabled login work again", active=True))
    return parser


async def run(args: argparse.Namespace, session: AsyncSession) -> int:
    """Run the parsed command; a refusal prints to stderr and exits 1."""
    try:
        return await args.handler(args, session)
    except Refused as error:
        print(error, file=sys.stderr)
        return 1


async def _run(args: argparse.Namespace) -> int:
    try:
        async with get_sessionmaker()() as session:
            return await run(args, session)
    finally:
        await get_engine().dispose()


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return asyncio.run(_run(args))
    except (ValueError, FileNotFoundError) as error:
        print(error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
