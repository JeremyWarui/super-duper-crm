"""The migrations build the schema the models describe, on SQLite and as Postgres SQL."""

import functools
import json
import secrets
from urllib.parse import quote

import pytest
import sqlalchemy as sa
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations

from backend.config import alembic_url, get_settings
from backend.models import Base
from tests.conftest import POSTGRES, postgres_url, revision_modules, upgrade_head


@pytest.fixture
def migrated_metadata() -> sa.MetaData:
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        upgrade_head(connection)
        reflected = sa.MetaData()
        reflected.reflect(bind=connection)
    engine.dispose()
    return reflected


def test_revisions_form_a_single_chain() -> None:
    revisions = revision_modules()
    assert len([m for m in revisions if m.down_revision is None]) == 1
    parents = [m.down_revision for m in revisions if m.down_revision is not None]
    assert set(parents) <= {m.revision for m in revisions}
    assert len(parents) == len(set(parents)), "two revisions share a parent"


def test_the_migrated_tables_and_columns_match_the_models(migrated_metadata: sa.MetaData) -> None:
    assert set(migrated_metadata.tables) == set(Base.metadata.tables)
    for name, model_table in Base.metadata.tables.items():
        migrated = {c.name: c.nullable for c in migrated_metadata.tables[name].columns}
        assert migrated == {c.name: c.nullable for c in model_table.columns}, name


def test_the_migrated_indexes_match_the_models(migrated_metadata: sa.MetaData) -> None:
    for name, model_table in Base.metadata.tables.items():
        migrated = {i.name for i in migrated_metadata.tables[name].indexes}
        assert {i.name for i in model_table.indexes} <= migrated, name


def test_the_migrated_foreign_keys_delete_as_the_models_say(
    migrated_metadata: sa.MetaData,
) -> None:
    def rules(table: sa.Table) -> set[tuple[str, str, str | None]]:
        return {
            (fk.parent.name, fk.column.table.name, fk.ondelete and fk.ondelete.upper())
            for fk in table.foreign_keys
        }

    for name, model_table in Base.metadata.tables.items():
        assert rules(migrated_metadata.tables[name]) == rules(model_table), name


def test_downgrade_removes_every_table() -> None:
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        revisions = revision_modules()
        with Operations.context(MigrationContext.configure(connection)):
            for module in revisions:
                module.upgrade()
            for module in reversed(revisions):
                module.downgrade()
        left_over = sa.MetaData()
        left_over.reflect(bind=connection)
    engine.dispose()
    assert set(left_over.tables) == set()


def _down_and_up(connection) -> None:
    with Operations.context(MigrationContext.configure(connection)):
        for module in reversed(revision_modules()):
            module.downgrade()
        for module in revision_modules():
            module.upgrade()


@pytest.mark.skipif(not POSTGRES, reason="needs TEST_POSTGRES=1")
async def test_every_revision_downgrades_and_upgrades_again_on_postgres() -> None:
    from sqlalchemy.engine import make_url
    from sqlalchemy.ext.asyncio import create_async_engine

    name = f"{make_url(postgres_url()).database}_downgrade"
    admin = create_async_engine(postgres_url("postgres"), isolation_level="AUTOCOMMIT")
    async with admin.connect() as connection:
        await connection.execute(sa.text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        await connection.execute(sa.text(f'CREATE DATABASE "{name}"'))
    scratch = create_async_engine(postgres_url(name))
    try:
        async with scratch.begin() as connection:
            await connection.run_sync(upgrade_head)
        async with scratch.begin() as connection:
            await connection.run_sync(_down_and_up)
    finally:
        await scratch.dispose()
        async with admin.connect() as connection:
            await connection.execute(sa.text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        await admin.dispose()


@functools.cache
def _postgres_sql() -> str:
    """The migrations rendered as Postgres SQL, without a database."""
    import io
    import os
    from contextlib import redirect_stdout
    from pathlib import Path

    from alembic import command

    root = Path(__file__).resolve().parent.parent
    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = "postgresql+asyncpg://USER:PASSWORD@localhost:5432/campaign_crm"
    get_settings.cache_clear()
    try:
        config = Config(str(root / "alembic.ini"))
        config.set_main_option("script_location", str(root / "alembic"))
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            command.upgrade(config, "head", sql=True)
        return buffer.getvalue()
    finally:
        if previous is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous
        get_settings.cache_clear()


def test_the_migrations_render_as_postgres_with_every_table() -> None:
    sql = _postgres_sql()
    assert sql.strip().startswith("BEGIN;")
    assert sql.strip().endswith("COMMIT;")
    for table in Base.metadata.tables:
        assert f"CREATE TABLE {table}" in sql, table
    assert "ON DELETE CASCADE" in sql
    assert "ON DELETE SET NULL" in sql


def test_the_unique_indexes_keep_their_where_clause_in_postgres() -> None:
    sql = _postgres_sql()
    assert (
        "CREATE UNIQUE INDEX uq_targets_campaign_ward ON targets "
        "(campaign_id, ward_id) WHERE registration_centre_id IS NULL" in sql
    )
    assert (
        "CREATE UNIQUE INDEX uq_targets_campaign_registration_centre ON targets "
        "(campaign_id, registration_centre_id) WHERE registration_centre_id IS NOT NULL" in sql
    )
    assert (
        "CREATE UNIQUE INDEX uq_campaign_members_one_candidate ON campaign_members "
        "(campaign_id) WHERE role = 'candidate'" in sql
    )
    assert (
        "CREATE UNIQUE INDEX uq_campaign_members_one_manager ON campaign_members "
        "(campaign_id) WHERE role = 'manager'" in sql
    )
    assert (
        "CREATE UNIQUE INDEX uq_campaign_members_one_campaign_per_user ON campaign_members "
        "(user_id)" in sql
    )


def test_a_password_with_a_percent_survives_the_alembic_config(
    monkeypatch: pytest.MonkeyPatch, fresh_settings: None
) -> None:
    """A percent-encoded `@` in the password must not trip configparser interpolation."""
    with_an_at = f"{secrets.token_hex(4)}@{secrets.token_hex(4)}"
    dsn = f"postgresql+asyncpg://postgres:{quote(with_an_at, safe='')}@localhost:5432/campaign_crm"
    monkeypatch.setenv("DATABASE_URL", dsn)
    get_settings.cache_clear()
    config = Config()
    config.set_main_option("sqlalchemy.url", alembic_url())
    assert config.get_main_option("sqlalchemy.url") == dsn


def test_the_member_role_migration_refuses_a_member_whose_role_differs_from_its_user() -> None:
    by_id = {m.revision: m for m in revision_modules()}
    first, second = by_id["schema_20261024"], by_id["member_role_fk"]
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            first.upgrade()
        connection.execute(
            sa.text(
                "INSERT INTO users (id, username, email, first_name, last_name, phone, role, "
                "password_hash, is_active, is_superuser) VALUES "
                "('u1', 'amina', '', '', '', '', 'mobilizer', '', 1, 0)"
            )
        )
        connection.execute(
            sa.text(
                "INSERT INTO campaigns (id, title, office_level, seat, signup_code, signups_open) "
                "VALUES ('c1', 'C', 'ward', 'mca', 'code', 1)"
            )
        )
        connection.execute(
            sa.text(
                "INSERT INTO campaign_members (id, campaign_id, user_id, role) "
                "VALUES ('m1', 'c1', 'u1', 'manager')"
            )
        )
        with (
            Operations.context(MigrationContext.configure(connection)),
            pytest.raises(RuntimeError, match="m1"),
        ):
            second.upgrade()
    engine.dispose()


def test_the_subscriptions_migration_gives_each_existing_campaign_an_unpaid_subscription() -> None:
    revisions = revision_modules()
    last = next(i for i, m in enumerate(revisions) if m.revision == "subscriptions")
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            for module in revisions[:last]:
                module.upgrade()
        connection.execute(
            sa.text(
                "INSERT INTO campaigns (id, title, office_level, seat, signup_code, signups_open) "
                "VALUES ('c1', 'C', 'ward', 'mca', 'code', 1)"
            )
        )
        with Operations.context(MigrationContext.configure(connection)):
            revisions[last].upgrade()
        rows = connection.execute(
            sa.text("SELECT campaign_id, paid_until, hold FROM campaign_subscriptions")
        ).all()
    engine.dispose()
    assert [tuple(row) for row in rows] == [("c1", None, "none")]


def test_the_volunteer_register_migration_gives_each_profile_its_members_details() -> None:
    revisions = revision_modules()
    last = next(i for i, m in enumerate(revisions) if m.revision == "volunteer_register")
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            for module in revisions[:last]:
                module.upgrade()
        for statement in (
            "INSERT INTO counties (id, name, code) VALUES ('k1', 'Nairobi', '047')",
            "INSERT INTO constituencies (id, county_id, name, code) "
            "VALUES ('c1', 'k1', 'W', '274')",
            "INSERT INTO wards (id, constituency_id, name, code) VALUES ('w1', 'c1', 'P', '1370')",
            "INSERT INTO party_members (id, full_name, phone, email, ward_id, status, "
            "consent_wording, consent_channel, consent_at) VALUES ('m1', 'Wanjiru Njeri Kamau', "
            "'+254712345678', 'w@example.com', 'w1', 'approved', 'I agree.', 'web_form', "
            "'2026-11-01')",
            "INSERT INTO volunteer_profiles (id, member_id, status, interests, preferred_contact, "
            "consent_wording, consent_at) VALUES ('v1', 'm1', 'active', '[]', 'call', 'I agree.', "
            "'2026-11-01')",
        ):
            connection.execute(sa.text(statement))
        with Operations.context(MigrationContext.configure(connection)):
            revisions[last].upgrade()
        row = connection.execute(
            sa.text(
                "SELECT first_name, last_name, phone, email, ward_id, campaign_id "
                "FROM volunteer_profiles"
            )
        ).one()
    engine.dispose()
    assert tuple(row) == (
        "Wanjiru",
        "Njeri Kamau",
        "+254712345678",
        "w@example.com",
        "w1",
        None,
    )


def test_the_volunteer_areas_migration_maps_old_interests_to_the_new_areas() -> None:
    revisions = revision_modules()
    last = next(i for i, m in enumerate(revisions) if m.revision == "volunteer_areas")
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            for module in revisions[:last]:
                module.upgrade()
        for statement in (
            "INSERT INTO counties (id, name, code) VALUES ('k1', 'Nairobi', '047')",
            "INSERT INTO constituencies (id, county_id, name, code) "
            "VALUES ('c1', 'k1', 'W', '274')",
            "INSERT INTO wards (id, constituency_id, name, code) VALUES ('w1', 'c1', 'P', '1370')",
            "INSERT INTO party_members (id, full_name, phone, ward_id, status, "
            "consent_wording, consent_channel, consent_at) VALUES ('m1', 'Wanjiru Kamau', "
            "'+254712345678', 'w1', 'approved', 'I agree.', 'web_form', '2026-11-01')",
            "INSERT INTO volunteer_profiles (id, member_id, first_name, last_name, phone, ward_id, "
            "status, interests, interest_other, profession_other, preferred_contact, "
            "consent_wording, consent_at) VALUES ('v1', 'm1', 'Wanjiru', 'Kamau', "
            "'+254712345678', 'w1', 'active', "
            "'[\"mobilisation\", \"events\", \"fundraising\", \"polling_day\"]', '', '', 'call', "
            "'I agree.', '2026-11-01')",
        ):
            connection.execute(sa.text(statement))
        with Operations.context(MigrationContext.configure(connection)):
            revisions[last].upgrade()
        row = connection.execute(
            sa.text("SELECT interests, interest_other FROM volunteer_profiles")
        ).one()
    engine.dispose()
    assert (json.loads(row[0]), row[1]) == (
        ["mobilising_voters", "fundraising", "other"],
        "Events, Polling day",
    )


def test_the_site_settings_migration_copies_every_field_and_sets_party() -> None:
    revisions = revision_modules()
    last = next(i for i, m in enumerate(revisions) if m.revision == "site_settings")
    moved = {
        "name": "Pamoja Party",
        "short_name": "PP",
        "slogan": "Pamoja tunaweza",
        "about_headline": "Built in every ward",
        "logo_url": "https://example.com/logo.png",
        "primary_colour": "#0b5d3b",
        "secondary_colour": "#f2b705",
        "contact_email": "info@example.com",
        "contact_phone": "0700 000000",
        "address": "Moi Avenue",
        "social_links": '{"X": "https://x.com/example"}',
        "description": "A party.",
        "manifesto_text": "1. Jobs.",
        "manifesto_url": "https://example.com/manifesto.pdf",
        "privacy_notice": "We keep your data safe.",
        "privacy_notice_version": "2026-11",
    }
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            for module in revisions[:last]:
                module.upgrade()
        connection.execute(
            sa.text(
                "UPDATE party_settings SET "
                + ", ".join(f"{name} = :{name}" for name in moved)
                + ", registration_number = 'DEMO-001', grace_days = 3"
            ),
            moved,
        )
        with Operations.context(MigrationContext.configure(connection)):
            revisions[last].upgrade()
        site = connection.execute(sa.text("SELECT * FROM site_settings")).mappings().one()
        party = connection.execute(sa.text("SELECT * FROM party_settings")).mappings().one()
    engine.dispose()
    assert site["organisation_type"] == "party"
    assert {name: site[name] for name in moved} == moved
    assert set(party) == {
        "id",
        "registration_number",
        "founded_year",
        "aspirant_steps",
        "grace_days",
        "read_only_days",
        "payment_instructions",
        "hosting_enabled",
        "updated_at",
    }
    assert (party["registration_number"], party["grace_days"], party["hosting_enabled"]) == (
        "DEMO-001",
        3,
        1,
    )


def test_the_hosting_and_finance_removal_drops_the_finance_office_and_keeps_the_others() -> None:
    revisions = revision_modules()
    last = next(i for i, m in enumerate(revisions) if m.revision == "remove_hosting_finance")
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            for module in revisions[:last]:
                module.upgrade()
        connection.execute(
            sa.text(
                "INSERT INTO party_roles (user_id, kind, role) VALUES "
                "('u1', 'staff', 'finance_officer'), ('u1', 'staff', 'nominations_officer')"
            )
        )
        connection.execute(sa.text("UPDATE party_settings SET payment_instructions = 'Paybill 1'"))
        with Operations.context(MigrationContext.configure(connection)):
            revisions[last].upgrade()
        roles = connection.execute(sa.text("SELECT role FROM party_roles")).scalars().all()
        party = connection.execute(sa.text("SELECT * FROM party_settings")).mappings().one()
        tables = set(sa.inspect(connection).get_table_names())
        ddl = connection.execute(
            sa.text("SELECT sql FROM sqlite_master WHERE name = 'party_roles'")
        ).scalar()
        with pytest.raises(sa.exc.IntegrityError):
            connection.execute(
                sa.text(
                    "INSERT INTO party_roles (user_id, kind, role) "
                    "VALUES ('u2', 'staff', 'finance_officer')"
                )
            )
    engine.dispose()
    assert roles == ["nominations_officer"]
    assert "finance_officer" not in ddl
    assert not tables & {
        "crm_plans",
        "campaign_subscriptions",
        "subscription_entries",
        "party_payments",
    }
    assert set(party) == {
        "id",
        "registration_number",
        "founded_year",
        "aspirant_steps",
        "payment_instructions",
        "updated_at",
    }
    assert party["payment_instructions"] == "Paybill 1"


def _alembic(database: str, *steps: tuple[str, str]) -> None:
    """Run `alembic upgrade|downgrade <target>` steps through env.py against one database."""
    import os
    from pathlib import Path

    from alembic import command

    root = Path(__file__).resolve().parent.parent
    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = postgres_url(database)
    get_settings.cache_clear()
    try:
        config = Config(str(root / "alembic.ini"))
        config.set_main_option("script_location", str(root / "alembic"))
        for action, target in steps:
            getattr(command, action)(config, target)
    finally:
        if previous is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous
        get_settings.cache_clear()


@pytest.mark.skipif(not POSTGRES, reason="needs TEST_POSTGRES=1")
def test_alembic_itself_replaces_the_looked_up_checks_both_ways_on_postgres() -> None:
    import asyncio

    from sqlalchemy.engine import make_url
    from sqlalchemy.ext.asyncio import create_async_engine

    name = f"{make_url(postgres_url()).database}_alembic"

    async def run(database: str, sql: str) -> list:
        engine = create_async_engine(postgres_url(database), isolation_level="AUTOCOMMIT")
        async with engine.connect() as connection:
            result = await connection.execute(sa.text(sql))
            rows = result.all() if result.returns_rows else []
        await engine.dispose()
        return rows

    def checks(table: str, column: str) -> str:
        return (
            "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
            f"WHERE conrelid = '{table}'::regclass AND contype = 'c' "
            f"AND pg_get_constraintdef(oid) LIKE '%({column})::text%' "
            "AND pg_get_constraintdef(oid) NOT LIKE '%seat%' "
            "AND pg_get_constraintdef(oid) NOT LIKE '%kind%'"
        )

    def both() -> list:
        return [
            asyncio.run(run(name, checks("party_roles", "role"))),
            asyncio.run(run(name, checks("campaigns", "office_level"))),
        ]

    asyncio.run(run("postgres", f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
    asyncio.run(run("postgres", f'CREATE DATABASE "{name}"'))
    try:
        _alembic(name, ("upgrade", "head"))
        head = both()
        _alembic(name, ("downgrade", "site_settings"))
        before = both()
        _alembic(name, ("upgrade", "head"))
        again = both()
    finally:
        asyncio.run(run("postgres", f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))

    assert [len(rows) for rows in head + before] == [1, 1, 1, 1]
    (roles,), (levels,) = (rows[0] for rows in head)
    (old_roles,), (old_levels,) = (rows[0] for rows in before)
    assert "finance_officer" not in roles and "finance_officer" in old_roles
    assert "national" in levels and "national" not in old_levels
    assert again == head


def test_the_workspace_kinds_migration_makes_every_campaign_hosted_and_guards_the_scope() -> None:
    revisions = revision_modules()
    last = next(i for i, m in enumerate(revisions) if m.revision == "workspace_kinds")
    engine = sa.create_engine("sqlite://")
    insert = (
        "INSERT INTO campaigns (id, title, office_level, seat, signup_code, signups_open, kind) "
        "VALUES (:id, 't', :level, :seat, :id, 0, :kind)"
    )
    with engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            for module in revisions[:last]:
                module.upgrade()
        connection.execute(
            sa.text(
                "INSERT INTO campaigns (id, title, office_level, seat, signup_code, signups_open) "
                "VALUES ('c1', 'MP race', 'constituency', 'mp', 'c1', 0)"
            )
        )
        with Operations.context(MigrationContext.configure(connection)):
            revisions[last].upgrade()
        kinds = connection.execute(sa.text("SELECT kind FROM campaigns")).scalars().all()
        connection.execute(
            sa.text(insert), {"id": "p1", "level": "national", "seat": None, "kind": "party"}
        )
        refused = []
        for row in (
            {"id": "p2", "level": "national", "seat": None, "kind": "party"},
            {"id": "h1", "level": "national", "seat": None, "kind": "hosted"},
            {"id": "h2", "level": "constituency", "seat": None, "kind": "hosted"},
            {"id": "p3", "level": "constituency", "seat": "mp", "kind": "standalone2"},
        ):
            try:
                with connection.begin_nested():
                    connection.execute(sa.text(insert), row)
            except sa.exc.IntegrityError:
                refused.append(row["id"])
        with (
            Operations.context(MigrationContext.configure(connection)),
            pytest.raises(RuntimeError, match="party or standalone"),
        ):
            revisions[last].downgrade()
    engine.dispose()

    assert kinds == ["hosted"]
    assert refused == ["p2", "h1", "h2", "p3"]


def test_the_candidate_profiles_migration_takes_each_aspirants_campaign() -> None:
    revisions = revision_modules()
    last = next(
        i for i, m in enumerate(revisions) if m.revision == "candidate_profiles_by_campaign"
    )
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            for module in revisions[:last]:
                module.upgrade()
        for row in (
            "INSERT INTO party_members (id, full_name, first_name, phone, ward_id, status, "
            "consent_wording, consent_channel, consent_at) VALUES ('m1', 'A', 'A', '1', 'w1', "
            "'approved', 'x', 'web_form', '2026-01-01'), ('m2', 'B', 'B', '2', 'w1', "
            "'approved', 'x', 'web_form', '2026-01-01')",
            "INSERT INTO campaigns (id, title, office_level, seat, ward_id, signup_code, "
            "signups_open, kind) VALUES ('c1', 't', 'ward', 'mca', 'w1', 'c1', 0, 'hosted')",
            "INSERT INTO aspirants (id, member_id, seat, ward_id, status, campaign_id) VALUES "
            "('a1', 'm1', 'mca', 'w1', 'approved', 'c1'), "
            "('a2', 'm2', 'mca', 'w1', 'approved', NULL)",
            "INSERT INTO candidate_profiles (aspirant_id, priorities) VALUES ('a1', '[]'), "
            "('a2', '[]')",
        ):
            connection.execute(sa.text(row))
        with Operations.context(MigrationContext.configure(connection)):
            revisions[last].upgrade()
        rows = connection.execute(
            sa.text("SELECT aspirant_id, campaign_id, length(id) FROM candidate_profiles")
        ).all()
        connection.execute(
            sa.text(
                "INSERT INTO campaigns (id, title, office_level, seat, ward_id, signup_code, "
                "signups_open, kind) VALUES ('c2', 't', 'ward', 'mca', 'w1', 'c2', 0, 'standalone')"
            )
        )
        connection.execute(
            sa.text(
                "INSERT INTO candidate_profiles (id, campaign_id, priorities) "
                "VALUES ('p2', 'c2', '[]')"
            )
        )
        with (
            Operations.context(MigrationContext.configure(connection)),
            pytest.raises(RuntimeError, match="no aspirant"),
        ):
            revisions[last].downgrade()
    engine.dispose()

    assert rows == [("a1", "c1", 32)]
