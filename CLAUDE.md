# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build, Test, and Lint Commands

### Makefile shortcuts (preferred)

```bash
make setup          # Install all dependencies
make test           # Unit tests (main server contract + SDK suites)
make test-main      # Main server tests only
make test-dicom     # DICOM SDK tests only
make test-bids      # BIDS SDK tests only
make test-integration  # Integration tests (starts Docker)
make test-e2e       # E2E tests (starts Docker on host ports)
make lint           # Ruff linting across all packages
make fmt            # Ruff formatting
```

**Important:** `make test` does NOT run `vna-bids-server/tests/`. Run that package's tests directly when changing the BIDS service.

### Single test execution

Main server:
```bash
cd vna-main-server
TESTING=true REQUIRE_AUTH=false python -m pytest tests/test_health.py::test_health_endpoint -v
```

BIDS server:
```bash
cd vna-bids-server
TESTING=true REQUIRE_AUTH=false python -m pytest tests/test_health.py::test_health_payload_shape -v
```

SDKs:
```bash
cd vna-bids-sdk && python -m pytest tests/test_client.py -v
cd vna-dicom-sdk && python -m pytest tests/ -v
```

### Running services locally

Full stack: `docker compose up -d`

Local dev (services only, no containers):
```bash
docker compose up -d postgres redis

# Main server
cd vna-main-server
pip install -e ../vna-common && pip install -r requirements.txt
export VNA_API_KEY=dev-key REQUIRE_AUTH=false
export DATABASE_URL="postgresql+asyncpg://vna-admin:password@localhost:18432/vna_main"
uvicorn vna_main.main:app --host 0.0.0.0 --port 8000 --reload

# BIDS server
cd vna-bids-server
pip install -e ../vna-common && pip install -r requirements.txt
export BIDS_API_KEY=dev-key REQUIRE_AUTH=false
export DATABASE_URL="postgresql+asyncpg://vna-admin:password@localhost:18432/bidsserver"
uvicorn bids_server.main:app --host 0.0.0.0 --port 8080 --reload
```

Frontend:
```bash
cd vna-ux && npm ci && npm run dev    # Vite dev server on :18300
```

## Architecture

### Service topology

```
Frontend (:13000) ──► Main Server (:18000) ──► PostgreSQL (:18432)
        │                    │
        │                    ├─► BIDS Server (:18080) ──► FileSystem (BIDS_ROOT)
        │                    │
        └─► Orthanc (:18042) ◄─┘
                                    Redis (:18379)
```

- **vna-main-server**: Control plane. Owns resource index, patient mapping, projects, labels, routing rules, sync endpoints, monitoring, and audit. All cross-service coordination flows through here.
- **vna-bids-server**: File management plane. Stores files under `BIDS_ROOT`, manages subjects/sessions/resources/labels/annotations, runs async task workers and webhook delivery loops.
- **vna-dicom-server**: Orthanc DICOM PACS with DICOMweb, OHIF, and VolView plugins.
- **vna-common**: Shared middleware (request ID, API version headers, logging) and response models. Used by both Python services.
- **vna-ux**: React/Vite dashboard. Proxies `/api/v1` → main server, `/bids-api` → BIDS server.

### Cross-service data flow

1. Orthanc or BIDS server emits sync/webhook events
2. Main server receives via `/api/v1/sync/*`, updates central `ResourceIndex`
3. Main server calls downstream systems through `vna_main.services.http_client` (shared async client)
4. Frontend reads from main server for browsing, pulls file content from BIDS for previews/downloads

### Route structure

Main server (`/api/v1`): resources, patients, projects, labels, query, treatments, versions, webhooks, routing, sync, monitoring, audit, health

BIDS server (`/api`): store, objects, query, subjects, sessions, labels, annotations, tasks, webhooks, modalities, verify, rebuild, validation, replication

## Key Conventions

### Auth and settings are enforced at import time

Both FastAPI services construct settings on import and will raise if auth is required but API key is missing. Tests and scripts must set `REQUIRE_AUTH=false` (and often `TESTING=true`) **before** importing app modules.

### Service middleware pattern

Main and BIDS both add:
- Request ID middleware from `vna_common.middleware.request_id`
- API version headers from `vna_common.middleware.api_version`
- Service-specific rate limiting
- Global exception handler returning `vna_common.responses.ErrorResponse`

Follow these patterns instead of inventing per-route response/error envelopes.

### Database differences

- Main server: defaults to SQLite for local/test, PostgreSQL in Docker
- BIDS server: requires PostgreSQL + filesystem, uses Alembic migrations
- Main server rate limiting: Redis-backed; BIDS server: in-memory

### Tests use dependency overrides

- Main server tests override `get_session`, use in-memory SQLite
- BIDS server tests patch session/engine globals, recreate metadata per test

Keep these fixtures working when adding endpoints or startup behavior.

### Frontend API paths

Frontend fetches relative paths, relying on Vite proxying:
- Main server calls under `/api/v1`
- BIDS file/content calls under `/bids-api`

Do not use environment-specific absolute URLs in frontend code.
