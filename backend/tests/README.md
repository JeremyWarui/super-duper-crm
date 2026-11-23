# Tests

```bash
uv run pytest          # everything; test_seed.py loads the real CSVs
uv run pytest tests    # tests only
uv run pytest evals    # the SPA contract and the walks across statuses
```

They build an in-memory SQLite database from the models, so no database server
is needed and nothing touches the network.

`TEST_POSTGRES=1 uv run pytest` runs the same tests on the local Postgres named
by the `DB_*` values in `backend/.env`. It recreates the database
`<DB_NAME>_pytest_<process id>`, builds it with the real migrations, and empties every table
before each test, and drops it when the run ends, so two runs at once never collide. It refuses any `DB_HOST` but this machine. Use it for
migrations, row locks and anything else SQLite cannot prove.

CI (`.github/workflows/backend-tests.yml`) runs everything on SQLite and on
Postgres.

| File | What it covers |
|---|---|
| `test_models.py` | Keys, deletes, constraints, computed values, enums |
| `test_win_model.py` | The seat target and ward targets reproduce the Laikipia and Marsabit worked examples (TD-R7 section 4) |
| `test_migrations.py` | The migration builds the models' schema, renders as Postgres, downgrades |
| `test_console_setup_flow.py` | The superuser sets a campaign up, end to end, on the migrated schema |
| `test_schemas.py` | Read schemas expose their listed fields and nothing else |
| `test_session.py` | Engine caching, rollback, rewriting a pasted Postgres URL for asyncpg, TLS verification |
| `test_app.py` | Startup, the /api prefix, CORS, the SPA mount, docs off in a deploy |
| `test_security.py` | Password hashing, token keys, the default password |
| `test_auth_api.py` | Sign-in and sign-out |
| `test_geography_api.py` | Reference reads, and a mobilizer's one ward |
| `test_campaigns_api.py` | Campaign reads, setup refusals, and that nobody sets one up for themselves |
| `test_users_api.py` | Mobilizer logins added and removed from inside a campaign |
| `test_team_api.py` | The candidate sets the one manager, nobody on the team resets a password, and an MCA mobilizer's centre |
| `test_clock.py` | Every request's today is the date in Nairobi |
| `test_ground_api.py` | Mobilizers, events and the supporter register |
| `test_ward_in_campaign.py` | A ward or centre in a request must lie inside the seat |
| `test_targets_api.py` | Reading targets; only votes committed can be written |
| `test_targets_service.py` | Turning a seat into targets |
| `test_strategy_api.py` | The computed dashboard and its notes |
| `test_invite_api.py` | Texting an event's supporters |
| `test_sms.py` | Phone normalising and both SMS providers |
| `test_admin_api.py` | The admin console and its superuser gate |
| `test_route_guards.py` | Every route needs a login unless public, and only me and logout skip the closed-campaign check |
| `test_permissions.py` | The permissions map is section 0.2, every role reaches exactly its routes, a coordinator stays in their area, a coordinator's payment needs the manager |
| `test_files_api.py` | Uploads: disguised and over-size files refused, metadata stripped, private files hidden, public ones cached |
| `test_workspace_site.py` | The website, edited from the workspace: Comms edits posts and slides, contrast enforced, edits audited, other roles refused |
| `test_cli.py` | campaign-crm |
| `test_seed.py` | The bundled CSVs and the demo |
| `test_history_seed.py` | Past results load, link to today's places, skip an unchanged file, and keep figures that do not add up out of every target |
| `../evals/test_frontend_contract.py` | The API offers what the SPA reads and accepts what it sends |

SQLite cannot prove Postgres-only SQL, so `test_migrations.py` renders the
migration for Postgres and checks the partial `WHERE` clauses and the
`ON DELETE` rules. Driver behaviour against a running server is not covered.

Fixtures live in `conftest.py`, object builders in `factories.py`. Test names
say what must be true.
