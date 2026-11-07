# The SPA and the API in one image, so the site is one origin and needs no CORS.
# Built from the repository root: docker build -f Dockerfile .
# Base images are pinned by digest; deploy/README.md says how to move them on.

# ----------------------------------------------------------------- the SPA
FROM node:22-slim@sha256:5ec23b7c622b00547753bc6ffd78085dd868a68aeb41c8e0a1418f033e13d96d AS web

WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
# Same origin as the API.
ENV VITE_API_URL=/api
RUN npm run build

# ------------------------------------------------- the API's environment
FROM python:3.13-slim@sha256:09a17cad02668ae61ece136b4fd36ac3849e14f670ebedb637ea3e15580525bc AS build

COPY --from=ghcr.io/astral-sh/uv:0.12.5@sha256:e85be844203885286c60ffad8a858d48afb6c5a5c237ca0e67f12e74b8f174b1 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0 \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app
# Dependencies first, so a code change does not reinstall them.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=backend/uv.lock,target=uv.lock \
    --mount=type=bind,source=backend/pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-dev
COPY backend/ ./
# Installed from /app/src, so the alembic/ and data/ folders beside it are found.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev

# ------------------------------------------------------------ what runs
FROM python:3.13-slim@sha256:09a17cad02668ae61ece136b4fd36ac3849e14f670ebedb637ea3e15580525bc

# pg_dump and pg_restore for `campaign-crm backup` and `restore`; their major version (17)
# matches the database image in deploy/docker-compose.yml.
RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client-17 \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --no-log-init --home-dir /app app

WORKDIR /app
COPY --from=build --chown=app:app /app /app
COPY --from=web --chown=app:app /web/dist /app/static
RUN mkdir -p /app/uploads /backups && chown app:app /app/uploads /backups

ENV PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    STATIC_DIR=/app/static \
    UPLOAD_DIR=/app/uploads \
    BACKUP_DIR=/backups

USER app
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=4)"]
# Behind Caddy, which sets X-Forwarded-For and -Proto and drops any a client sent.
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers"]
