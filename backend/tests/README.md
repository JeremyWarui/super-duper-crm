# Tests

```bash
uv run pytest                      # everything, ~6s
uv run pytest tests                # gate tests only
uv run pytest evals                # the Django parity check only
```

Deterministic, local, free, no network and no database server. Safe to run on
every commit.

| File | What it holds the line on |
|---|---|
| `test_models.py` | DDL, UUID keys, cascade and SET NULL behavior, unique and check constraints, derived properties, enum values |
| `test_win_number.py` | The one piece of real arithmetic, table-driven, including the float bug it replaced |
| `test_migrations.py` | The migration builds the schema the models describe, and downgrade reverses it |
| `test_schemas.py` | Read schemas validate off mapped instances and never carry `password_hash` |
| `test_app.py` | The ASGI app boots, serves `/health`, exposes no data routes yet |
| `../evals/test_django_parity.py` | Every field of the pre-port Django schema is mapped, renamed, or dropped with a written reason |

## SQLite, not a Postgres container

The suite runs on in-memory SQLite so it stays free and finishes in seconds.
`sqlalchemy.Uuid`, `Numeric`, `DateTime(timezone=True)` and the partial unique
indexes all work there, and `conftest.py` turns on `PRAGMA foreign_keys` - SQLite
ignores foreign keys by default, and without it every cascade and SET NULL test
here would pass while proving nothing.

What that does not cover, and what covers it instead:

- **Dialect-specific DDL** (native `UUID`, `DEFAULT now()`, quoting of `role`,
  which is reserved in CockroachDB). Checked by compiling the migration offline
  against both dialects, which needs no server:
  ```bash
  DATABASE_URL=postgresql+asyncpg://u:p@h:5432/d  uv run alembic upgrade head --sql
  DATABASE_URL=cockroachdb+asyncpg://u:p@h:26257/d uv run alembic upgrade head --sql
  ```
- **Real asyncpg driver behavior and CockroachDB transaction retries.** Not
  covered by anything yet. It needs a running node, so it belongs in a
  integration lane once one exists.

## Conventions

- Test names are sentences: what must be true, not which function is called.
- Anything asserting a database rule inserts to prove the rule is in the DDL, not
  just in Python. `test_the_database_rejects_an_unknown_role` uses raw SQL for
  exactly this reason - the ORM-level check above it would pass with no
  constraint in the schema at all.
- Fixtures live in `conftest.py`, object builders in `factories.py`.
