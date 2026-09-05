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
flyctl launch --no-deploy --copy-config --name mzigo-crm --region sin
flyctl secrets set DATABASE_URL="cockroachdb+asyncpg://...?ssl=require"
flyctl secrets set SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
```

Leave `DEFAULT_USER_PASSWORD` unset. Set on a public deploy, it hands the same
password to every account anyone creates, including through the open sign-up.

`fly.toml` runs in `sin`. Fly has deprecated `bom` and will not provision new
resources there, so Singapore is the closest it still offers to the cluster in
`aws-ap-south-1`. A dashboard render makes several database round trips, so the
app sits near the data: Kenyan users pay one slower trip to Singapore rather
than one slow trip per query. `jnb` is the alternative if that trade ever
inverts.

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

Both ran against CockroachDB on 2026-09-06: 47 counties, 290 constituencies,
1,450 wards and 27,273 centres in 68 seconds, no retryable errors. On Windows
`flyctl ssh console -C` prints `Error: The handle is invalid` as it tears the
session down, after the command has already finished. Read the output above it.

## 5. Check it

```bash
flyctl status
curl https://mzigo-crm.fly.dev/health
flyctl logs
```

Then open `https://mzigo-crm.fly.dev` and sign in.

## Known gaps

- Fly's Depot builder failed with `authentication handshake failed: EOF` on
  the first attempt. `--depot=false` builds on a Fly builder machine instead
  and works. Reach for it when a build hangs on "Waiting for depot builder".
- The app runs one `shared-cpu-1x` 512MB machine. It is not free. With
  `min_machines_running = 1` it bills around the clock; set it to 0 and the
  machine suspends when idle, billing only its rootfs, and resumes on the next
  request.
- Cockroach runs serializable by default and returns retryable errors under
  write contention. Nothing here retries. One person clicking around will not
  hit it; concurrent writers might.
- Sign-up at `POST /api/auth/register/` is open and unthrottled. Anyone with
  the link can create a candidate or manager account. They see only their own
  campaigns, but nothing stops them making many. `ALLOW_REGISTRATION=false`
  closes it without a redeploy.
- No backups are configured beyond whatever the Cockroach plan gives you.
