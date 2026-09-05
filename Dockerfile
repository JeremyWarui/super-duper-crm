# The SPA and the API in one image, so the deploy is one URL and no CORS.
# Built from the repository root: docker build -f Dockerfile .

# ----------------------------------------------------------------- the SPA
FROM node:22-slim AS web

WORKDIR /web
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci || npm install

COPY frontend/ ./
# Same origin as the API, so the browser never makes a cross-site request.
ENV VITE_API_URL=/api
RUN npm run build

# ----------------------------------------------------------------- the API
FROM python:3.13-slim AS api

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH=/app/.venv/bin:$PATH

COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /usr/local/bin/uv

WORKDIR /app

# Dependencies first, so a code change does not re-resolve them.
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

COPY backend/ ./
RUN uv sync --frozen --no-dev

COPY --from=web /web/dist ./static
ENV STATIC_DIR=/app/static

EXPOSE 8080
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8080"]
