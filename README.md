# 🗞️ News Search — Fast, Reliable, Production-Ready

A small but mighty news meta-search service that aggregates from multiple providers (The Guardian + NYT), normalizes results, dedupes, caches intelligently, and serves a bundled React UI — all with solid engineering foundations: **SOLID design, 12-Factor config, circuit breakers, retries, Redis caching, rate limiting, TDD & BDD**, and containerized delivery.

---

## ✨ Features

- **Multi-provider aggregation**: Guardian + NYT via a clean provider interface.
- **Normalized output**: consistent fields (`title`, `url`, `published_at`, `source`, `excerpt`).
- **Smart merge**: canonical-URL dedupe + published-date sort.
- **Fast**  
  - Redis caching on merged results.  
  - Threaded HTTP server for concurrency.  
  - “Interactive” mode for type-ahead with a time budget + lighter retry profile (`interactive=1`).  
  - Preloaded offline caches to avoid disk I/O on hot paths.
- **Resilient**  
  - Circuit breakers and retries per provider.  
  - Egress rate limiting (protect upstream APIs).  
  - Ingress rate limiting (protect your API; optional in dev).  
  - Offline fallback datasets.
- **Secure**  
  - Bearer token required for `/search` and `/openapi.json`.  
  - Strict query validation to prevent abuse.  
  - CORS allowlist.
- **12-Factor friendly**  
  - All config via environment variables.  
  - Stateless, logs to stdout/stderr by default.
- **Observability**  
  - Structured logging with configurable level and rotation.  
  - Health endpoint `/health`.
- **DevX**  
  - **TDD/BDD** test suites (pytest + pytest-bdd).  
  - Multi-stage Dockerfile + Docker Compose.  
  - Swagger UI served at `/docs`.

---

## 🧱 Architecture (at a glance)

```
UI (React build) ──> app.py (ThreadingHTTPServer)
          │            ├── /search → Aggregator
          │            │      ├── Providers: GuardianProvider / NYTProvider
          │            │      ├── Redis cache (merged result)
          │            │      ├── Dedupe (CanonUrlDedupe)
          │            │      └── Sort (PublishedAtSort)
          │            ├── /health
          │            └── /docs + /openapi.json
          └── static assets served from ui_build/
```

- **Providers** implement `fetch(query, page, page_size, offline, fast=False)`, encapsulating URL build, retries, circuit breaker, **egress limiter**, and offline fallback.
- **Aggregator** runs providers in threads, merges, dedupes, sorts, slices, and caches.
- **Cache**: Redis (configurable TTL).
- **Rate limiting**:  
  - **Egress** per provider (token bucket via Redis).  
  - **Ingress** (optional) to protect your API.

---

## 🧰 SOLID in practice

- **S**ingle Responsibility — providers fetch/normalize; aggregator merges; strategies dedupe/sort; cache & rate-limit utilities are isolated.
- **O**pen/Closed — add a provider by implementing the base interface; no aggregator changes needed.
- **L**iskov Substitution — any `NewsProvider` works where a provider is expected.
- **I**nterface Segregation — focused interfaces (provider, cache, strategies) instead of god objects.
- **D**ependency Inversion — aggregator depends on abstractions (provider list, cache, strategies), not concretions.

---

## 🧭 12-Factor (production-ready)

- **Config via env**: API keys, Redis, logging, ports in `.env` / secret store.
- **Backing services**: Redis as an attached resource via env vars.
- **Build, release, run**: multi-stage Docker builds; Compose orchestrates services.
- **Logs**: to stdout; optional rotation to files.
- **Disposability**: fast start/stop; `/health` for readiness.

---

## ⚙️ Configuration

Create `.env` (or use secrets in CI/CD):

```env
# Secrets
API_SECRET_KEY=newssearch_secret_2025
GUARDIAN_API_KEY=...
NYT_API_KEY=...

# Server
HOST=0.0.0.0
PORT=8080
OFFLINE_DEFAULT=0

# Redis
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0
REDIS_CACHE_TTL=300

# Logging
LOG_LEVEL=ERROR      # DEBUG/INFO/WARNING/ERROR/CRITICAL
LOG_TO_FILE=false
LOG_ROTATE=size      # size | time
LOG_MAX_BYTES=1048576
LOG_BACKUP_COUNT=3
LOG_WHEN=midnight
LOG_INTERVAL=1
```

---

## 🔌 API

- **Health**: `GET /health` → `{"status":"ok"}`
- **Swagger UI**: `GET /docs`
- **OpenAPI JSON**: `GET /openapi.json` *(requires Authorization)*
- **Search**:  
  `GET /search?query=<q>&page=<n>&page_size=<m>&offline=<0|1>[&interactive=1]`  
  **Headers**: `Authorization: Bearer <API_SECRET_KEY>`  
  **Query rules**: alphanumeric/space/hyphen, 1–100 chars.  
  **Interactive**: `interactive=1` enables time-budgeted, low-retry path (type-ahead).

Example:

```bash
curl -H "Authorization: Bearer ${API_SECRET_KEY}"   "http://127.0.0.1:8080/search?query=apple&page=1&page_size=10&offline=0&interactive=1"
```

---

## 🧪 Tests (TDD & BDD)

### Unit & Integration

- Providers: success/offline/retry/circuit-breaker; normalization shape.
- Strategies: `CanonUrlDedupe`, `PublishedAtSort`.
- Cache wrapper + rate limiter.
- Aggregator merge/dedupe/pagination/caching.
- HTTP layer: auth gates, health, static serving, 429 on ingress limit.

Run:

```bash
pytest -q --maxfail=1 --disable-warnings --cov=newssearch
```

Key fixtures:
- `fakeredis` replaces Redis.
- `freezegun` controls time windows.
- `run_server` spins up the threaded HTTP server with a **temporary `.env`** so values like `API_SECRET_KEY`/`OFFLINE_DEFAULT` are deterministic in tests, then restores the original.

### BDD (pytest-bdd)

`features/search_success.feature`
```gherkin
Feature: Search news
  Scenario: Successful search with valid token (offline mode)
    Given the API server is running on port 8090 with offline mode
    And I use the bearer token "test-secret"
    When I GET "/search?query=apple&page=1&page_size=10&offline=0"
    Then the response code is 200
    And the JSON has keys "items", "total_estimated_pages", "time_taken_ms"
```

`features/steps/steps.py` (snippet)
```python
from pytest_bdd import scenarios, given, when, then, parsers
import requests

scenarios("../search_success.feature")

@given(parsers.parse("the API server is running on port {port:d} with offline mode"))
def api_server(run_server, port):
    with run_server(port=port, env={"API_SECRET_KEY":"test-secret","OFFLINE_DEFAULT":"1"}) as ctx:
        yield ctx

@given(parsers.parse('I use the bearer token "{token}"'))
def auth(token):
    return {"Authorization": f"Bearer {token}"}

@when(parsers.parse('I GET "{path}"'))
def do_get(api_server, auth, path):
    _, base = api_server
    return {"resp": requests.get(f"{base}{path}", headers=auth)}

@then(parsers.parse("the response code is {code:d}"))
def assert_status(do_get, code):
    assert do_get["resp"].status_code == code
```

Run BDD only:

```bash
pytest -q features
```

---

## 🐋 Docker

### Dockerfile (multi-stage) — healthcheck fix

We use a Node build stage for the UI and a Python slim runtime. Healthcheck uses curl (no heredoc).

```dockerfile
# syntax=docker/dockerfile:1.7

# Stage 1 — Build CRA UI
FROM node:18-alpine AS ui-build
WORKDIR /app/ui
COPY ui/package*.json ./
RUN npm ci --no-audit --no-fund
COPY ui/ .
RUN npm run build

# Stage 2 — Python API + Static UI
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv/app

RUN apt-get update && apt-get install -y --no-install-recommends       ca-certificates tzdata curl &&     rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY newssearch/ /srv/app/newssearch/
COPY openapi.json /srv/app/
COPY data/ /srv/app/data/
COPY swagger_ui/ /srv/app/swagger_ui/
COPY --from=ui-build /app/ui/build /srv/app/ui_build

RUN useradd -r -u 10001 -g users app && chown -R app:users /srv/app
USER app

ENV HOST=0.0.0.0 PORT=8080 OFFLINE_DEFAULT=0 PYTHONPATH=/srv/app
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3   CMD curl -fsS http://127.0.0.1:8080/health || exit 1

CMD ["python", "-m", "newssearch.app"]
```

### requirements.txt

```text
python-dotenv==1.0.1
tenacity==8.5.0
pybreaker==1.0.2
redis==5.0.6
requests==2.32.3
```

### .dockerignore

```gitignore
.git
**/__pycache__/
**/*.py[cod]
**/.pytest_cache/
**/.mypy_cache/
**/.ruff_cache/
.venv
.env
ui/node_modules
ui/build
tests
dist
logs
```

---

## 🧩 Docker Compose

`docker-compose.yml` (no host port for Redis to avoid conflicts; API talks to `redis` on the Compose network):

```yaml
services:
  redis:
    image: redis:7-alpine
    command: ["redis-server", "--save", "", "--appendonly", "no"]
    healthcheck:
      test: ["CMD", "redis-cli", "PING"]
      interval: 10s
      timeout: 3s
      retries: 5

  api:
    build: .
    image: newssearch:latest
    depends_on:
      redis:
        condition: service_healthy
    ports:
      - "8080:8080"
    environment:
      HOST: 0.0.0.0
      PORT: 8080
      OFFLINE_DEFAULT: "0"
      API_SECRET_KEY: ${API_SECRET_KEY}
      GUARDIAN_API_KEY: ${GUARDIAN_API_KEY}
      NYT_API_KEY: ${NYT_API_KEY}
      REDIS_HOST: redis
      REDIS_PORT: 6379
      REDIS_DB: 0
      REDIS_CACHE_TTL: 300
      LOG_LEVEL: ERROR
      LOG_TO_FILE: "false"
```

> **Note:** If you had `version:` at the top, remove it — Compose v2 ignores it and warns it’s obsolete.

### Compose commands

```bash
# build
docker compose build

# run (reads .env)
docker compose --env-file .env up -d

# logs
docker compose logs -f
docker compose logs -f api

# health check
curl -fsS http://127.0.0.1:8080/health

# request
curl -H "Authorization: Bearer ${API_SECRET_KEY}"   "http://127.0.0.1:8080/search?query=apple&page=1&page_size=10&offline=0"

# stop + remove
docker compose down
```

**Port 6379 already in use?** Don’t publish Redis, or map to another host port:
```yaml
# if you really need host access:
redis:
  ports:
    - "6380:6379"
```

---

## 🐳 Plain Docker (without Compose)

```bash
docker build -t newssearch:latest .
docker network create newsnet || true

docker run -d --name redis --network newsnet redis:7-alpine
docker run -d --name api --network newsnet -p 8080:8080   -e HOST=0.0.0.0 -e PORT=8080 -e OFFLINE_DEFAULT=0   -e API_SECRET_KEY="newssearch_secret_2025"   -e GUARDIAN_API_KEY="..." -e NYT_API_KEY="..."   -e REDIS_HOST=redis -e REDIS_PORT=6379 -e REDIS_DB=0 -e REDIS_CACHE_TTL=300   newssearch:latest
```

**Tag & push (optional)**

```bash
REG=ghcr.io/<you>/newssearch:latest
docker tag newssearch:latest $REG
docker push $REG

# multi-arch
docker buildx create --use --name nsbuilder || true
docker buildx build --platform linux/amd64,linux/arm64 -t $REG --push .
```

---

## 🤖 CI/CD — Jenkins with Docker Compose

Place this `Jenkinsfile` at repo root. It builds, tests, builds images with Compose, optionally pushes to a registry, and deploys locally via Compose with a smoke check.

```groovy
pipeline {
  agent any
  options { timestamps(); ansiColor('xterm') }

  environment {
    IMAGE           = "newssearch:latest"
    REGISTRY_IMAGE  = ""   // set to non-empty to push (e.g., ghcr.io/you/newssearch:latest)
    COMPOSE_FILE    = "docker-compose.yml"
    DOCKER_BUILDKIT = "1"

    API_SECRET_KEY   = credentials('api-secret-key')
    GUARDIAN_API_KEY = credentials('guardian-api-key')
    NYT_API_KEY      = credentials('nyt-api-key')
  }

  stages {
    stage('Checkout') { steps { checkout scm } }

    stage('Prepare .env for Compose') {
      steps {
        sh '''
          cat > .env.ci <<EOF
API_SECRET_KEY=${API_SECRET_KEY}
GUARDIAN_API_KEY=${GUARDIAN_API_KEY}
NYT_API_KEY=${NYT_API_KEY}
HOST=0.0.0.0
PORT=8080
OFFLINE_DEFAULT=0
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0
REDIS_CACHE_TTL=300
LOG_LEVEL=ERROR
LOG_TO_FILE=false
EOF
        '''
      }
    }

    stage('Unit Tests') {
      steps {
        sh '''
          python -m pip install -U pip
          [ -f requirements.txt ] && pip install -r requirements.txt || true
          if python -c "import pytest" 2>/dev/null; then
            pytest -q --maxfail=1 --disable-warnings --cov=newssearch
          else
            python -m unittest -v
          fi
        '''
      }
      post { always { junit allowEmptyResults: true, testResults: '**/junit*.xml' } }
    }

    stage('Build (docker compose)') {
      steps { sh 'docker compose --env-file .env.ci build' }
    }

    stage('Push Image (optional)') {
      when { expression { return env.REGISTRY_IMAGE?.trim() } }
      steps {
        sh '''
          docker tag ${IMAGE} ${REGISTRY_IMAGE}
          docker push ${REGISTRY_IMAGE}
        '''
      }
    }

    stage('Deploy (docker compose up)') {
      steps {
        sh '''
          docker compose --env-file .env.ci down || true
          docker compose --env-file .env.ci up -d --build
          echo "Waiting for API to become healthy..."
          for i in $(seq 1 30); do
            if curl -fsS http://127.0.0.1:8080/health >/dev/null 2>&1; then
              echo "API healthy"; exit 0
            fi
            sleep 2
          done
          echo "API failed healthcheck"; docker compose logs --no-color; exit 1
        '''
      }
    }
  }

  post {
    always {
      archiveArtifacts artifacts: 'openapi.json', onlyIfSuccessful: false
      sh 'docker compose ps || true'
      sh 'docker compose logs --no-color || true'
    }
  }
}
```

---

## 🧪 Dev UX & Performance Tips

- Use `ThreadingHTTPServer` (already configured).
- Keep `LOG_LEVEL=ERROR` in production; DEBUG in hot paths impacts latency.
- Debounce search input on the client (≈250ms), minimum query length (2–3 chars), cancel in-flight requests.
- For type-ahead, pass `interactive=1` → aggregator time budget + lighter retries.
- Keep ingress rate limiting relaxed/disabled in local dev to avoid throttling while typing.

---

## 📁 .gitignore

```gitignore
# OS
.DS_Store
Thumbs.db

# Python
__pycache__/
*.py[cod]
*.so
.eggs/
*.egg-info/
dist/
build/
pip-wheel-metadata/
.pytest_cache/
.tox/
.mypy_cache/
.pyre/
.ruff_cache/
.coverage*
htmlcov/
*.log

# Virtualenvs
.venv/
venv/
ENV/
env/

# Node / React (UI)
ui/node_modules/
ui/build/
npm-debug.log*
yarn-*.log
pnpm-debug.log*

# Docker / Compose
docker-compose.override.yml

# IDE
.vscode/
.idea/
*.iml
*.swp
*.swo

# Env & secrets
.env
.env.*
!.env.example
.env.local
.env.development.local
.env.test.local
.env.production.local

# Logs
logs/

# Redis dumps
*.rdb
*.aof

# Data: keep offline samples, ignore everything else
data/*
!data/guardian_offline.json
!data/nyt_offline.json
!data/README.md
```

---

## ⛳ GitHub push quickstart

### Using GitHub CLI (recommended)

```bash
brew install gh
gh auth login

# if repo doesn’t exist:
USER=$(gh api user -q .login)
gh repo create "$USER/news-search" --public --source=. --remote=origin --push

# if repo exists:
git remote set-url origin https://github.com/$USER/news-search.git
gh auth setup-git
git push -u origin main
```

### Using SSH

```bash
ssh-keygen -t ed25519 -C "you@example.com"
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/id_ed25519
gh ssh-key add ~/.ssh/id_ed25519.pub -t "Dev Laptop"

git remote set-url origin git@github.com:<you>/news-search.git
ssh -T git@github.com
git push -u origin main
```

> If you see `Permission denied (publickey)`, ensure the key is added and `ssh -vT git@github.com` shows it being used.

---

## 🛠️ Troubleshooting

- **Redis port in use**: don’t publish Redis on host; let API talk to `redis` over the Compose network, or map to `6380:6379`.
- **Compose warning “version is obsolete”**: remove the `version:` key from `docker-compose.yml`.
- **Healthcheck heredoc error**: Docker HEALTHCHECK doesn’t support heredocs; use `curl` or a Python one-liner.
- **401 Unauthorized**: ensure `Authorization: Bearer <API_SECRET_KEY>` header is present; confirm server env loads the expected key.

---

## 📝 License & Contributions

PRs welcome! Please include tests (unit and/or BDD) for behavioral changes and keep logging minimal in hot paths. For larger features, open an issue to discuss approach.
