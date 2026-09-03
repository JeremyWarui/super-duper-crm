# Tests

```bash
uv run pytest          # everything, ~6s
uv run pytest tests    # tests only
uv run pytest evals    # the schema guard only
```

They build an in-memory database from the real schema, so no Postgres server is
needed and nothing touches the network.

| File | What it covers |
|---|---|
| `test_models.py` | Keys, deletes, unique and check constraints, calculated values, enums |
| `test_win_number.py` | The vote goal, across the edge cases |
| `test_migrations.py` | The migrations build the schema the models describe, and reverse cleanly |
| `test_schemas.py` | Response schemas expose their listed fields and nothing else |
| `test_session.py` | Engine caching, and the rollback when a request fails |
| `test_app.py` | The app starts and serves |
| `../evals/test_schema_baseline.py` | No field leaves the schema without a recorded reason |

## What the in-memory database does not cover

Driver behaviour and Postgres-specific SQL. To check the migration produces
valid Postgres without running a server:

```bash
DATABASE_URL=postgresql+asyncpg://u:p@h:5432/d uv run alembic upgrade head --sql
```

## Conventions

- Test names say what must be true, not which function is called.
- A test of a database rule inserts a row to prove the rule is in the schema and
  not only in Python.
- Fixtures in `conftest.py`, object builders in `factories.py`.
