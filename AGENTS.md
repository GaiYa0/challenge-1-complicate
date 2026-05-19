# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) and other AI coding agents when working with this repository.

## Project Overview

检察侦查画像模型 (Investigation Profiling Model) — a full-stack system for person profiling, data processing, analysis, and clue discovery in digital prosecution. FastAPI monolith backend + Vue 3 SPA frontend, with Celery workers and optional Kafka consumers for async processing.

The codebase has been refactored to an **industrial-grade frontend/backend split**: the backend lives under `backend/app/{routers,services,repositories,schemas}`; the frontend under `frontend/src/{views,components,api,store}`. Views never touch HTTP clients directly; routers never embed business logic.

## Quick Start

```bash
# Full stack via Docker Compose (recommended)
docker compose --env-file .env.dev up -d --build

# Backend only (no frontend Nginx)
docker compose -f docker-compose.backend.yml --env-file .env.dev up -d --build

# Stop
docker compose down
# Stop and remove volumes
docker compose down -v
```

Dev credentials (DEBUG=true only): `admin` / `admin`

## Development Commands

### Backend (local, outside Docker)

```bash
pip install -r requirements.txt

# API server (from project root; main.py re-exports backend.app.main:app)
PYTHONPATH=. uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Celery worker
PYTHONPATH=. celery -A backend.tasks.celery_app worker --loglevel=info

# Celery beat
PYTHONPATH=. celery -A backend.tasks.celery_app beat --loglevel=info

# Kafka consumer (only if KAFKA_ENABLED=true)
PYTHONPATH=. python -m backend.events.kafka_consumer
```

### Frontend

```bash
cd frontend
npm install
npm run dev       # Vite on :5173, proxies /api and /ws to :8000
npm run build     # vue-tsc + vite build (must stay green)
npm run preview   # Preview production build
```

### Helper Scripts

```bash
chmod +x run/*.sh
./run/run.sh help           # List all subcommands
./run/docker-up.sh          # Build + start compose
./run/docker-down.sh        # Stop compose
./run/docker-logs.sh        # Tail backend logs (pass service name to override)
./run/frontend-dev.sh       # npm install + npm run dev
./run/frontend-build.sh     # Production build
./run/db-list-users.sh      # List users in postgres (needs running container)
```

## Runtime Topology (Docker Compose)

```
Browser → web (Nginx+Vue :8080) → backend (FastAPI :8000, internal only)
                                      ├── PostgreSQL (business data)
                                      ├── Redis (cache + Celery broker + rate limit)
                                      ├── MinIO (object storage / raw/clean/reports)
                                      ├── Neo4j (graph database)
                                      └── Kafka (optional) → kafka-consumer
                                                               celery-worker (multi-queue)
```

Port 8000 is **not** exposed to the host in production compose; all traffic must enter via Nginx at 8080.

## Backend Structure (`backend/`)

Layered split with Protocol-aligned contracts:

- `app/` — the HTTP application
  - `main.py` — FastAPI app, lifespan (engine, MinIO bootstrap, schema patching, Celery wiring), middleware chain, router registration.
  - `routers/` — FastAPI route handlers. **Only** parse inputs, call services, and wrap results via `success_for_request`.
    - `auth.py` `case.py` `clue_routes.py` `graph_case_routes.py` `file.py` `analyze.py` `graph.py` `model.py` `feature.py` `feedback.py` `task.py` `reports.py` `health.py` `realtime_ws.py` `rbac.py` (dependency factory)
  - `services/` — Business logic. Stateless modules; one per domain.
  - `repositories/` — SQLAlchemy ORM access only. No HTTP, no business rules.
  - `schemas/` — Pydantic request/response models. Shared `common.ApiResponse[T]` + `success_for_request(...)` envelope.
- `core/` — Config (pydantic-settings), DB/engine, JWT, exceptions, response envelope, tenant access helpers, security audit, transaction context.
- `middleware/` — JWT gate, rate limiting, trusted-proxy / request-id sanitization.
- `model/` — SQLAlchemy ORM models + enums.
- `tasks/` — Celery tasks (`analyze`, `clean`, `feature`, `report_export`, `cost`, `lifecycle`, `compensation`) across queues `high_priority` / `default` / `low_priority` / `compensation`.
- `events/` — Kafka producer/consumer and DLQ handling. Topics: `data-uploaded`, `data-processed`, `model-trained`, `prediction-done`, `events-dlq`.
- `infra/` — Redis client, MinIO client (bucket helpers + layered naming), tiered cache, data lake helpers.
- `data_platform/` — Multi-source collision / trajectory / fund-flow / risk scoring / call record / person profile engines.
- `contracts/` — `service_protocols.py` — Port definitions for future boundary enforcement.

Legacy import compatibility shims are deliberately kept thin: all new code must import from `backend.app.*`.

## Frontend Structure (`frontend/src/`)

Vue 3 + TypeScript + Pinia + Element Plus + ECharts + AntV G6:

- `views/` — Page components. **No** direct `axios` / `api/*` imports; they subscribe to stores with `storeToRefs` and dispatch actions.
- `components/` — Reusable UI (charts, graphs, investigation widgets, portrait panels, virtual table).
- `api/` — Axios client + per-domain API modules. `client.ts` is the sole axios instance; response interceptor handles `{code,msg,data,request_id}` envelopes, 401 redirect, and **429 exponential backoff with `Retry-After` awareness**.
- `store/` — Pinia stores, all complex orchestration lives here.
  - `modules/` — Per-domain stores: `analysis`, `case`, `clue`, `file`, `graph`, `portrait`, `relationshipAnalysis`, `risk`, `task`, `userAdmin`.
- `composables/` — `useTaskPoller` (batch polling with backoff), `usePermission`, `useGlobalLoading`.
- `router/` — Route definitions + meta-based role guards (`router/guard.ts`).
- `state/httpContext.ts` — Request ID tracking for UI breadcrumbs.

### Frontend boundary rules (enforced on review)

1. Views may only import from `store/`, `components/`, `composables/`, and types. They must **not** import from `api/*`.
2. All HTTP goes through `api/` → Pinia actions. Business transformations (prediction → risk score, anomaly aggregation, etc.) live inside stores, never in views.
3. `useTaskPoller` issues exactly one `POST /task/batch` per tick; never per-id. Derivatives (`clean_*`, `feature_*`) are filtered before enqueueing new pipelines.

## Microservices Preview (`services/`)

Parallel evolution, not the primary runtime:

- `gateway/` — API gateway with JWT, circuit breaker, service registry
- `user_service/`, `file_service/`, `data_service/`, `model_service/`, `task_service/`
- `common/` — Shared kafka_bus, tracing, circuit breaker, resilient HTTP

## Key Patterns

- **Entry point**: root `main.py` re-exports `backend.app.main:app`. Uvicorn/Gunicorn launches `main:app`.
- **Config**: `backend/core/config.py` defines a pydantic-settings `Settings` class. `get_settings()` is an `@lru_cache` singleton. Tests call `get_settings.cache_clear()` after env mutations. Module-level constants (`UPLOAD_DIR`, `RATE_LIMIT_REQUESTS_PER_MINUTE`, etc.) are preserved for backwards compatibility but the runtime value for rate limits is always read from `Settings`.
- **Middleware chain** (registered bottom-up in `backend/app/main.py`, executes top-down):
  `request_id → degraded_mode → jwt_gate → rate_limit → access_log`.
- **Rate limiting** (`backend/middleware/rate_limit.py`): dual-layer Redis counters — minute window (`RATE_LIMIT_REQUESTS_PER_MINUTE`, default 600) and burst window (`RATE_LIMIT_BURST_*`, default 120/10s). Exempt prefixes configured via `RATE_LIMIT_EXEMPT_PREFIXES` (defaults cover `/task/`, `/auth/me`, `/live`, `/ready`, `/metrics`). On trip, responds `429` with `Retry-After` and `X-RateLimit-Bucket` headers. Redis failures fail-open.
- **Response envelope**: `{code, msg, data, request_id}` via `backend.app.schemas.common.ApiResponse[T]` and `success_for_request`.
- **Request-level Unit of Work**: `backend/core/deps.py:get_db` yields a `Session` that commits on successful route return and rolls back on exception; `SessionLocal` uses `expire_on_commit=False` to survive middleware post-processing.
- **Additive schema patches**: `_apply_additive_schema_patches` in `backend/app/main.py` runs `ALTER TABLE IF EXISTS ... ADD COLUMN IF NOT EXISTS` idempotently on startup to handle schema drift without Alembic.
- **Async work**: heavy computation → Celery; event-driven pipelines → Kafka. When `KAFKA_ENABLED=false`, uploads fall back to direct Celery dispatch (`KAFKA_UPLOAD_FALLBACK_CELERY`).
- **Tenant isolation**: every repo query and MinIO path is keyed by `user_id`. Fail-closed IDOR check is enforced in services (`_verify_task_ownership`, `resolve_file_for_read`, etc.).
- **ML bootstrap**: `predict` auto-activates the latest `ModelRegistry` row for a `model_name`; if none exist, it auto-trains using the tenant's latest `feature_version`, then activates. Prevents "no deployable model" dead-ends on fresh tenants.
- **Task polling**: frontend hits `POST /task/batch` (≤64 ids) instead of per-id status/result. Unknown or unauthorized ids return `UNAUTHORIZED` which the poller treats as terminal.
- **Derivative filename guard**: `clean_data_task` refuses to re-clean filenames starting with `clean_` and returns an idempotent success, preventing `clean_<h2>_clean_<h1>_<orig>` explosion. Frontend additionally filters derivatives before enqueueing pipelines.

## Environment Variables

All settings live in `backend/core/config.py` (`Settings`). Defaults cover local dev; override via `.env.dev` / `.env.prod` / env vars. Key groups:

- `APP_NAME`, `DEBUG`, `CORS_ORIGINS`
- `DB_*` (PostgreSQL), `REDIS_*`, `MINIO_*`, `NEO4J_*`, `KAFKA_*`, `CELERY_*`
- `JWT_SECRET`, `JWT_EXPIRE_MINUTES`
- `RATE_LIMIT_REQUESTS_PER_MINUTE`, `RATE_LIMIT_BURST_BUCKET_SEC`, `RATE_LIMIT_BURST_PER_BUCKET`, `RATE_LIMIT_EXEMPT_PREFIXES`
- `TRUSTED_PROXY_IPS`, `REQUEST_ID_MAX_LEN`
- `DEGRADED`, `DEGRADE_GRAPH`, `DEMO_MODE`, `GRAPH_VIZ_CACHE_TTL_SEC`, `GRAPH_NODE_CAP`
- `LIFECYCLE_DELETE_WARM_AFTER_COLD`, `LIFECYCLE_COLD_ARCHIVE_BATCH`, `REPORT_RETENTION_DAYS`
- `COST_METRICS_ENABLED`, `COMPLIANCE_EXPORT_APPROVAL_REQUIRED`
- `CELERY_MAX_CONCURRENT_PER_USER`, `CELERY_TASK_MAX_RETRIES`

## Deployment

- **Docker Compose**: `docker-compose.yml` includes both backend and frontend (`docker-compose.backend.yml`, `docker-compose.frontend.yml`).
- **Kubernetes**: `deploy/k8s/` — Kustomize manifests (namespace: `challenge-demo`), HPA, PDB, Ingress, monitoring (Prometheus/Grafana).
- **CI/CD**: `.github/workflows/k8s-ci-cd.yml` — builds + pushes to GHCR, Trivy scan, optional K8s rolling update.

## Endpoints

- Site: http://127.0.0.1:8080 (Nginx + Vue; proxies `/api` and `/ws`)
- OpenAPI docs (internal only): http://127.0.0.1:8080/api/docs once reverse-proxied; direct `127.0.0.1:8000` is disabled in prod compose.
- Health: `GET /live`, `GET /ready`
- Metrics: `GET /metrics` (Prometheus)
- MinIO console: http://127.0.0.1:9001

## Working Conventions for Agents

- **Do not** reintroduce direct API calls inside Vue views. Route new state/behavior through the appropriate Pinia store.
- **Do not** embed business logic in routers. Call a service; services own validation, tenant checks, side effects.
- **Commit / rollback** is handled by `get_db`; repos should `db.flush()`, not `db.commit()`.
- When adding columns, update the ORM model **and** add an entry to `_ADDITIVE_COLUMN_PATCHES` in `backend/app/main.py` so existing dev DBs upgrade automatically.
- When adding HTTP endpoints, keep the path registered **before** any generic `/{param}` route in the same router to avoid wildcard capture (see `backend/app/routers/task.py` — `/batch` routes precede `/{task_id}`).
- Frontend 429 retry is automatic up to 3 attempts; do not add your own ad-hoc retry loops.
- When enqueueing Celery analysis/feature jobs from the UI, always operate on `useFileStore().sourceFilenames()` to exclude derivatives.
- Run `npx vue-tsc --noEmit -p tsconfig.app.json` after frontend edits; it is part of the build gate.
