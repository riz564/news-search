#syntax=docker/dockerfile:1.7


# Stage 1 — Build CRA UI

ARG NODE_VERSION=18-alpine
FROM node:${NODE_VERSION} AS ui-build
WORKDIR /app/ui

COPY ui/package*.json ./
RUN npm ci --no-audit --no-fund

COPY ui/ .
RUN npm run build


# Stage 2 — Python API + Static UI

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /srv/app

# Minimal system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates tzdata curl \
    && rm -rf /var/lib/apt/lists/*

# Python deps (cached layer)
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# App code and assets
COPY newssearch/ /srv/app/newssearch/
COPY openapi.json /srv/app/
COPY data/ /srv/app/data/
COPY swagger_ui/ /srv/app/swagger_ui/
COPY --from=ui-build /app/ui/build /srv/app/ui_build

# Non-root user
RUN useradd -r -u 10001 -g users app && chown -R app:users /srv/app
USER app

# Runtime env
ENV HOST=0.0.0.0 \
    PORT=8080 \
    OFFLINE_DEFAULT=0 \
    PYTHONPATH=/srv/app

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8080/health || exit 1

CMD ["python", "-m", "newssearch.app"]
