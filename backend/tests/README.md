# Tests

```bash
uv run pytest          # everything; test_seed.py loads the real CSVs
uv run pytest tests    # tests only
uv run pytest evals    # the SPA contract only
```

They build an in-memory SQLite database from the models, so no database server
is needed and nothing touches the network.

| File | What it covers |
|---|---|
| `test_models.py` | Keys, deletes, constraints, computed values, enums |
| `test_win_number.py` | The vote goal across its edge cases |
| `test_migrations.py` | The migration builds the models' schema, renders as Postgres, downgrades |
| `test_manager_signup_flow.py` | Sign-up to setup, end to end, on the migrated schema |
| `test_schemas.py` | Read schemas expose their listed fields and nothing else |
| `test_session.py` | Engine caching, rollback, the CockroachDB DSN |
| `test_app.py` | Startup, the /api prefix, CORS, the SPA mount, docs off in a deploy |
| `test_security.py` | Password hashing, token keys, the default password |
| `test_auth_api.py` | Sign-up, sign-in and sign-out |
| `test_geography_api.py` | Reference reads, and a mobilizer's one ward |
| `test_campaigns_api.py` | Campaign reads, setup, one campaign per login |
| `test_users_api.py` | Mobilizer logins added and removed from inside a campaign |
| `test_ground_api.py` | Mobilizers, events and the supporter register |
| `test_ward_in_campaign.py` | A ward or centre in a request must lie inside the seat |
| `test_targets_api.py` | Reading and editing the win number |
| `test_targets_service.py` | Turning a seat into targets |
| `test_strategy_api.py` | The computed dashboard and its notes |
| `test_invite_api.py` | Texting an event's supporters |
| `test_sms.py` | Phone normalising and both SMS providers |
| `test_admin_api.py` | The admin console and its superuser gate |
| `test_cli.py` | campaign-crm |
| `test_seed.py` | The bundled CSVs and the demo |
| `../evals/test_frontend_contract.py` | The API offers what the SPA reads and accepts what it sends |

SQLite cannot prove Postgres-only SQL, so `test_migrations.py` renders the
migration for Postgres and checks the partial `WHERE` clauses and the
`ON DELETE` rules. Driver behaviour against a running server is not covered.

Fixtures live in `conftest.py`, object builders in `factories.py`. Test names
say what must be true.
