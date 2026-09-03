# Campaign CRM - backend

FastAPI, SQLAlchemy 2.0 (async) and Pydantic v2, on Postgres. Managed with `uv`.

Models only so far. The one route is `/health`; endpoints come next.

## Quick start

Needs a local Postgres running.

```bash
cd backend
uv sync --group dev
createdb campaign_crm                     # or: psql -c "CREATE DATABASE campaign_crm"
cp .env.example .env                      # fill in SECRET_KEY and your Postgres password
uv run alembic upgrade head               # create the tables
uv run uvicorn backend.main:app --reload  # http://127.0.0.1:8000/docs
```

Checks:

```bash
uv run pytest        # 119 tests, ~6s, no database server needed
uv run ruff check .
uv run ruff format .
```

## Layout

```
backend/
├── alembic/               migrations
│   ├── env.py             reads the database URL and schema from the app
│   └── versions/          one migration so far: the initial schema
├── src/backend/
│   ├── main.py            the app and its middleware
│   ├── config.py          settings, read from the environment
│   ├── db/
│   │   ├── base.py        declarative base, id and timestamp mixins
│   │   └── session.py     engine, session factory, the request dependency
│   ├── models/            the tables
│   └── schemas/           what each model looks like in a response
├── tests/
└── evals/                 guards the schema against fields going missing
```

## The models

```
County -> Constituency -> Ward -> RegistrationCentre
                               -> PollingStation

User (candidate | campaign manager | mobilizer)
  └── Campaign  -> Target      vote goal per ward or centre
                -> Mobilizer   organizer on the ground
                -> Event       meeting or rally, with attendance
                -> Supporter   someone who signed up
```

A campaign contests one office. `office_level` decides which of `county`,
`constituency` or `ward` applies, and whether the campaign organizes by ward or
by registration centre.

`Target` holds the win number: half the projected votes cast, plus one. Call
`recompute_win_number()` after changing the projected turnout.

## How the models are set up

- **UUID primary keys**, generated in Python, so an object has its id before it
  is saved and ids are safe to show in URLs.
- **Enums are stored as text** with a CHECK constraint listing the valid values,
  so the database rejects a bad one.
- **Deletes are handled in the database.** Deleting a county removes its
  constituencies and wards; deleting a mobilizer's login keeps the mobilizer.
- **Money-shaped maths uses `Decimal`**, not float. Float rounding at the halfway
  point moves a win number by a whole vote.
- **Relationships are not loaded lazily.** Reading one that was not fetched
  raises an error naming the `selectinload` you need, rather than firing a
  hidden query.

## Known gaps

1. `PollingStation.centre_code` and `centre_name` are free text that repeat
   `RegistrationCentre`. They should be a foreign key.
2. `Campaign` has three geography columns and only one applies. Nothing stops a
   ward campaign from also setting `county_id`.
3. `Mobilizer` has no uniqueness rule, so a ward can hold any number of them.

## Migrations

```bash
uv run alembic revision --autogenerate -m "what changed"
uv run alembic upgrade head
uv run alembic downgrade -1
uv run alembic upgrade head --sql        # print the SQL instead of running it
```

The connection string lives in `.env`, not in `alembic.ini`.

`tests/test_migrations.py` fails if you add a column and forget to generate a
migration for it.

## Configuration

Read from the environment and from `.env`; see `.env.example`. `SECRET_KEY` has
no default and must be at least 32 characters.

## Not built yet

Endpoints, request schemas, authentication, password hashing, and queries.
