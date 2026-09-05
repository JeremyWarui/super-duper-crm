# Deploying to Fly.io

One machine serves both halves: FastAPI answers `/api` and `/health`, and the
built SPA is mounted at `/`. One URL, one origin, no CORS.

Everything below is yours to run. Creating accounts and entering payment
details is not something I do on your behalf.

## Before the first deploy

```bash
# Windows, in PowerShell
iwr https://fly.io/install.ps1 -useb | iex
flyctl auth login
```

## 1. A database

The app talks SQLAlchemy 2.0 async over `asyncpg`. Two options, and they are
not equal.

### Real Postgres (nothing to change)

Neon, Supabase or Fly's own Managed Postgres all work as they are. Put it in
the same region as the app; every request that renders the dashboard makes
several round trips, and a database on another continent shows.

```bash
flyctl postgres create --name mzigo-db --region jnb
```

Take the connection string it prints and turn `postgres://` into
`postgresql+asyncpg://`.

### CockroachDB (one dependency, one scheme)

Tested against your cluster on 2026-09-06, on CockroachDB v26.2.5:

- `postgresql+asyncpg://` **fails**. SQLAlchemy cannot parse Cockroach's
  version string and raises `AssertionError` before the first query.
- `cockroachdb+asyncpg://` with the `sqlalchemy-cockroachdb` dialect connects.
- `alembic upgrade head` applies both migrations, under non-transactional DDL.
- The 27,273-centre seed is **not yet verified** against it.

To go this way, add the dialect to `backend/pyproject.toml` dependencies:

```toml
"sqlalchemy-cockroachdb>=2.0",
```

then `uv lock`, and use a URL shaped like
`cockroachdb+asyncpg://USER:PASSWORD@HOST:26257/defaultdb?ssl=require`.
Note `ssl=`, not libpq's `sslmode=`: asyncpg does not read `sslmode`, and
`verify-full` additionally wants a CA file on disk.

## 2. Create the app and set its secrets

```bash
flyctl launch --no-deploy --copy-config --name mzigo-crm --region jnb
```

Secrets never go in `fly.toml`, and never into a chat window:

```bash
flyctl secrets set DATABASE_URL="postgresql+asyncpg://..."
flyctl secrets set SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
```

Leave `DEFAULT_USER_PASSWORD` unset. Set on a public deploy it hands the same
password to every account anyone creates, including through the open sign-up.

## 3. Deploy

```bash
flyctl deploy --remote-only
```

`--remote-only` builds on Fly's builder, so you do not need Docker locally.
The release command runs `alembic upgrade head` before the new machine takes
traffic; a failing migration fails the deploy instead of half-applying.

## 4. Load the data, once

The reference seed reads 27,273 rows and is far too slow for a release
command, so run it by hand after the first deploy:

```bash
flyctl ssh console -C "campaign-crm seed"
flyctl ssh console -C "campaign-crm demo --password <the-demo-password>"
```

`demo` prints the four logins. `--password` pins them so you can pass one to
whoever you are showing it to; without it each account gets its own generated
password.

## 5. Check it

```bash
flyctl status
curl https://mzigo-crm.fly.dev/health
flyctl logs
```

Then open `https://mzigo-crm.fly.dev` and sign in.

## Known gaps

- The image build has not been run. There is no Docker or `flyctl` on the
  machine this was written on, so `Dockerfile` and `fly.toml` are unverified
  against a real build. Expect to iterate on the first `flyctl deploy`.
- Sign-up at `POST /api/auth/register/` is open and unthrottled. Anyone with
  the link can create a candidate or manager account. They see only their own
  campaigns, but nothing stops them making many. `ALLOW_REGISTRATION=false`
  closes it without a redeploy.
- No backups are configured.
