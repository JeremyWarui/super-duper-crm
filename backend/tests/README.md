# Tests

```bash
uv run pytest          # everything, ~1 min; test_seed.py loads the real CSVs
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
| `test_app.py` | The app starts, and every data route sits under /api |
| `test_security.py` | Password hashing and token keys |
| `test_auth_api.py` | Signing in and out, and what a stale token gets |
| `test_geography_api.py` | The reference reads, and what each role may see |
| `test_campaigns_api.py` | Campaign reads, and the one-call setup |
| `test_targets_api.py` | Reading and editing the win number |
| `test_ground_api.py` | Mobilizers, events and the supporter register |
| `test_strategy_api.py` | The computed dashboard and its three flags |
| `test_targets_service.py` | Turning a seat into targets |
| `test_seed.py` | The bundled CSVs, against the real files |
| `../evals/test_schema_baseline.py` | No field leaves the schema without a recorded reason |
| `../evals/test_frontend_contract.py` | The API still offers what the SPA reads and accepts what it sends |

## What the in-memory database does not cover

Driver behaviour. Postgres-specific SQL is covered: `test_migrations.py` renders
the migrations offline for the Postgres dialect and checks the pieces SQLite
cannot prove - the partial `WHERE` clauses on the target indexes, and the
`ON DELETE` rules SQLite ignores unless a pragma is on. To read that SQL
yourself:

```bash
DATABASE_URL=postgresql+asyncpg://u:p@h:5432/d uv run alembic upgrade head --sql
```

What is left is the driver: asyncpg's type handling, and anything that only
shows up against a running server.

## Conventions

- Test names say what must be true, not which function is called.
- A test of a database rule inserts a row to prove the rule is in the schema and
  not only in Python.
- Fixtures in `conftest.py`, object builders in `factories.py`.
