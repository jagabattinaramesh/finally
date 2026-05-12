# syntax=docker/dockerfile:1.7

# Stage 1: build the Next.js static export
FROM node:20-slim AS frontend-build
WORKDIR /frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build


# Stage 2: Python runtime with FastAPI + static frontend
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:/root/.local/bin:${PATH}" \
    DB_PATH=/app/db/finally.db \
    FRONTEND_DIST=/app/static

WORKDIR /app

# uv binary (Astral official image)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# Install Python deps first so the layer is cacheable
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# Copy backend source and finish install
COPY backend/ ./
RUN uv sync --frozen --no-dev

# Copy the built frontend from stage 1
COPY --from=frontend-build /frontend/out /app/static

# DB volume mount point
RUN mkdir -p /app/db
VOLUME ["/app/db"]

EXPOSE 8000

CMD ["uv", "run", "--no-dev", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
