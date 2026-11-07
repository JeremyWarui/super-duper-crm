# Self-host package

Everything one server needs to run the platform with Docker. The step-by-step guide for the IT
person is `docs/handover/IT_Operations.md`; this page lists what is here.

| File | What it is |
|---|---|
| `docker-compose.yml` | The database (`postgres:17`), a one-off `migrate` step, the `app`, the nightly `backup`, and `caddy` serving HTTPS |
| `.env.example` | Every setting, with the required ones at the top; copy it to `.env` |
| `caddy/Caddyfile` | HTTPS for `DOMAIN`, proxying to the app |
| `nightly-backup.sh` | Runs `campaign-crm backup` once a day at `BACKUP_HOUR_UTC` |
| `../Dockerfile` | The app image: the built website and the API, run as a non-root user |

## Run it

```bash
cd deploy
cp .env.example .env        # then fill in the required lines
docker compose up -d --build
docker compose exec app campaign-crm seed         # the map data; takes a few minutes
docker compose exec app campaign-crm setup-token
```

Open `https://DOMAIN/setup` and paste the token. Data lives in named volumes: `db-data`
(database), `uploads` (uploaded files), `backups` (nightly archives), `caddy-data` and
`caddy-config` (certificates). `docker compose down` keeps them; `down -v` deletes them.

## Pinned images

Every image is pinned to a digest, so a rebuild gets exactly the same base. To move one on,
look up the new digest and replace it in `docker-compose.yml` or `../Dockerfile`:

```bash
docker buildx imagetools inspect postgres:17 --format '{{json .Manifest.Digest}}'
```

The database image and the app image's `postgresql-client-17` must stay on the same major
version, or backups taken by one may not restore into the other.
