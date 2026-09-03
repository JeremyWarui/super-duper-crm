# Campaign CRM - backend

FastAPI + SQLAlchemy 2.0 (async) + Pydantic v2, on CockroachDB. Managed with `uv`.

This is the models layer only. There are no API routes yet beyond `/health`, and
that is deliberate: the Django app it replaces had nothing but `models.py` either
(`views.py`, `admin.py`, `tests.py` and `urls.py` were all empty scaffolding).

## Quick start

```bash
cd backend
uv sync --group dev --extra cockroachdb   # drop --extra for plain Postgres
cp .env.example .env                      # then fill in SECRET_KEY and the DB parts
uv run alembic upgrade head               # create the schema
uv run uvicorn backend.main:app --reload  # http://127.0.0.1:8000/docs
```

Checks:

```bash
uv run pytest        # 115 tests, ~6s, no network, no database server
uv run ruff check .
uv run ruff format .
```

## Layout

```
backend/
├── alembic/               migrations (replaces campaign/migrations/)
│   ├── env.py             async engine; DSN and metadata come from the app
│   └── versions/          one revision so far: the initial schema
├── src/backend/
│   ├── main.py            the ASGI app (replaces config/{asgi,wsgi,urls}.py)
│   ├── config.py          settings from the environment (replaces config/settings.py)
│   ├── db/
│   │   ├── base.py        DeclarativeBase, UUID + timestamp mixins, naming convention
│   │   └── session.py     async engine, sessionmaker, the get_session dependency
│   ├── models/            the mapped classes (replaces campaign/models.py)
│   └── schemas/           Pydantic v2 read schemas
├── tests/                 gate tests - deterministic, local, free
└── evals/                 parity check against the pre-port Django schema
```

## The stack, and why

**SQLAlchemy 2.0 + Pydantic v2 as two layers, not SQLModel as one.** They are the
vanilla, best-supported choice, Alembic autogenerate works properly against them,
and the DB shape and the wire shape are free to differ. That last point is not
theoretical: `users.password_hash` is a column and must never appear in a
response. With one class doing both jobs, keeping it out means remembering to
exclude it at every call site; with two, it is absent by construction. The cost
is writing each field roughly twice.

**Async (asyncpg).** A CRM is I/O-bound on the database, which is the reason to
be on FastAPI at all. Choosing sync now would mean rewriting every session call
later. The cost: lazy relationship access raises instead of quietly querying, so
derived properties that read a related row (`Campaign.area`,
`Target.registered_voters`) call `require_loaded()` and tell you which
`selectinload` is missing.

**UUID primary keys.** CockroachDB distributes by key range, so sequential
integer keys funnel every insert into a single range and cap write throughput.
UUIDs spread the writes, and are safe to expose to the React frontend without
leaking row counts. `sqlalchemy.Uuid` maps to native `UUID` on
Postgres/CockroachDB and to `CHAR(32)` on SQLite, which is how the test suite
runs the same models without a database server. Ids are generated in `__init__`,
not at flush, so a new object can be referenced before it is saved.

**Enums are VARCHAR + CHECK, not native database enums.** Django stored choices
as `varchar(20)` validated in Python only. Keeping VARCHAR means no data
migration, and avoids CockroachDB's awkward `ALTER TYPE` path; the CHECK
constraint moves validation Django never enforced into the database.

## Bugs found and fixed during the port

The Django models could not have started. Each of these is covered by a test.

| Where | Problem | Fix |
|---|---|---|
| `User.role` | `default=Role.Manager` - the member is `MANAGER`. `AttributeError` at import. | `default=UserRole.MANAGER` |
| `Campaign.OfficeLevel` | Subclassed `models.Model`, not `TextChoices`, so `OfficeLevel.choices` did not exist. | `OfficeLevel(LabelledStrEnum)` |
| `Campaign.operational_grain` | Read `self.OfficeLevel.Ward`; the member is `WARD`. | `OfficeLevel.WARD` |
| `County.Meta` | `verbrose_name_pLural` - typo, silently ignored by Django. | Dropped; Django `Meta` has no SQLAlchemy equivalent |
| `Target.registration_center` | FK to `"RegistrationCenter"`, a model that does not exist (it is spelled `Centre`). | `registration_centre_id` -> `registration_centres.id` |
| `Target.compute_win_number` | Read `self.registered_voters`, not a field on `Target`. Always `None`, so it could never compute anything. | `Target.registered_voters` resolves the centre's roll for a centre-level target, the ward's otherwise |
| `Target.compute_win_number` | `rv * float(pct) / 100` - binary float lands on the wrong side of the floor. 375 voters at 36.8% gives 137.99999999999997, so the win number came out 69 instead of 70. | Decimal throughout |
| naming | `registration_center` on `Target`, `registration_centre` on `Mobilizer` and `Event`. | `registration_centre` everywhere |

## What changed in the schema

Renames and drops are recorded in `evals/django_parity.json` and enforced by
`evals/test_django_parity.py`, which fails if a Django field goes missing without
an entry there.

- `User.password` -> `password_hash`. Hashing is not wired up; no auth code exists yet.
- `User.date_joined` -> `created_at`, `User.last_login` -> `last_login_at`,
  `Supporter.registered_at` -> `created_at`. Every table names its creation time the same way.
- Dropped with Django: `User.is_staff`, `User.groups`, `User.user_permissions`.
  All three existed to drive `django.contrib.admin` and the `contrib.auth`
  permission tables. `User.role` is the authorization signal this app uses.
- `Meta.ordering` has no model-level equivalent in SQLAlchemy. Each old default
  is recorded in its class docstring; ordering moves onto the queries when the
  query layer is written.
- Django's `PositiveIntegerField` check constraints are kept, and turnout
  percentages gained a `0 <= pct <= 100` check.

## Known data-model issues (not fixed - they are schema changes, not a port)

1. **`PollingStation` and `RegistrationCentre` overlap.** `PollingStation` carries
   `centre_code` and `centre_name` as loose strings while `RegistrationCentre` is
   a real table. That should be a foreign key. Nothing populates either yet, so
   this is cheap to fix now and expensive later.
2. **`Campaign` has three nullable geography FKs and only one is meaningful**, chosen
   by `office_level`. Nothing stops a ward-level campaign from also setting
   `county_id`. A CHECK constraint could enforce it.
3. **`Mobilizer` has no uniqueness rule.** The Django comment said "one per ward to
   start" but left it open. Still open.

## Migrations

```bash
uv run alembic revision --autogenerate -m "what changed"
uv run alembic upgrade head
uv run alembic downgrade -1
uv run alembic upgrade head --sql        # print the DDL instead of running it
```

`alembic.ini` has no `sqlalchemy.url`: `env.py` reads `DATABASE_URL` through
`backend.config`, so there is one source of truth for the DSN and no credentials
in a tracked file.

`tests/test_migrations.py` executes every revision against in-memory SQLite and
compares the result to `Base.metadata`. It fails if you add a column and forget
to autogenerate - the tests themselves use `create_all`, so nothing else would
notice the drift.

## Configuration

Everything is read from the environment (and `.env` in development); see
`.env.example`. `SECRET_KEY` has no default and must be at least 32 characters -
the Django scaffold shipped a real-looking key hardcoded in `settings.py`, which
is how those end up in source control.

For CockroachDB use `cockroachdb+asyncpg://` with the `cockroachdb` extra
installed; it adds Cockroach's retry and savepoint handling. Plain
`postgresql+asyncpg://` works for Postgres and for basic CockroachDB use.

## Not here yet

Routers, request (create/update) schemas, authentication, password hashing, and
repository/query code. They arrive with the endpoints.
