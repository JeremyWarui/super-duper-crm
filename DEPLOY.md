# Deploying to Fly.io, on CockroachDB

One machine serves both halves: FastAPI answers `/api` and `/health`, and the
built SPA is mounted at `/`. One URL, one origin, no CORS. The database is a
CockroachDB Cloud cluster reached over `DATABASE_URL`.

Everything below is yours to run. Creating accounts and entering payment
details is not something I do on your behalf, and no connection string should
be pasted into a chat window: `flyctl secrets set` reads it straight from your
shell into Fly.

## Before the first deploy

```bash
# Windows, in PowerShell
iwr https://fly.io/install.ps1 -useb | iex
flyctl auth login
```

## 1. The connection string

Take the string from the CockroachDB console and reshape it. Two changes, both
required:

| From | To | Why |
|---|---|---|
| `postgresql://` | `cockroachdb+asyncpg://` | SQLAlchemy's own Postgres dialect raises `AssertionError` reading Cockroach's version string. `sqlalchemy-cockroachdb` is a dependency for this reason. |
| `?sslmode=verify-full` | `?ssl=require` | asyncpg does not read libpq's `sslmode`. `verify-full` additionally wants a CA file on disk, which the container has no reason to carry. |

So the shape is:

```
cockroachdb+asyncpg://USER:PASSWORD@HOST:26257/defaultdb?ssl=require
```

Verified against your cluster on 2026-09-06 (CockroachDB v26.2.5): the dialect
connects, and `alembic upgrade head` applies both migrations under
non-transactional DDL.

## 2. Create the app and set its secrets

```bash
flyctl launch --no-deploy --copy-config --name mzigo-crm --region jnb
flyctl secrets set DATABASE_URL="cockroachdb+asyncpg://...?ssl=require"
flyctl secrets set SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
```

Leave `DEFAULT_USER_PASSWORD` unset. Set on a public deploy, it hands the same
password to every account anyone creates, including through the open sign-up.

Pick a region near the cluster. Yours is in `aws-ap-south-1` (Mumbai), so
`bom` keeps the round trips short; the dashboard makes several per render, and
a database on another continent shows. `fly.toml` currently says `jnb`, which
is closer to your users but roughly 60ms further from the data. Change
`primary_region` to whichever you would rather pay for.

## 3. Deploy

```bash
flyctl deploy --remote-only
```

`--remote-only` builds on Fly's builder, so Docker is not needed locally. The
release command runs `alembic upgrade head` before the new machine takes
traffic, so a failing migration fails the deploy instead of half-applying.

## 4. Load the data, once

The reference seed writes 27,273 registration centres and is far too slow for
a release command, so run it by hand after the first deploy:

```bash
flyctl ssh console -C "campaign-crm seed"
flyctl ssh console -C "campaign-crm demo --password <the-demo-password>"
```

`demo` prints the four logins. `--password` pins them so you can pass one to
whoever you are showing it to; without it each account gets its own generated
password.

**The seed has not been run against CockroachDB.** Migrations have. Watch this
step: 27k inserts under Cockroach's serializable isolation is the part most
likely to be slow or to raise a retryable error. If it does, that is the thing
to fix before showing anyone.

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
- The 27,273-row seed is unverified on CockroachDB, as above.
- Cockroach runs serializable by default and returns retryable errors under
  write contention. Nothing here retries. One person clicking around will not
  hit it; concurrent writers might.
- Sign-up at `POST /api/auth/register/` is open and unthrottled. Anyone with
  the link can create a candidate or manager account. They see only their own
  campaigns, but nothing stops them making many. `ALLOW_REGISTRATION=false`
  closes it without a redeploy.
- No backups are configured beyond whatever the Cockroach plan gives you.
