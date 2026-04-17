# VNA-Server Copilot Instructions

## Build, test, and lint commands

### Repo-level commands

Use the root `Makefile` when it matches the package you are changing:

```bash
make setup
make test-main
make test-dicom
make test-bids
make lint
make fmt
```

`Makefile` also defines `make test`, `make test-integration`, and `make test-e2e`, but those targets still reference top-level `tests/` files that are not present in the current tree. Prefer the package-specific commands below for reliable runs.

Important naming detail: `make test-bids` runs the **BIDS SDK** suite in `vna-bids-sdk/`, not `vna-bids-server/tests/`.

### Package-specific commands

Main server:

```bash
pip install -e vna-common/
pip install -r vna-main-server/requirements.txt -r vna-main-server/requirements-dev.txt
cd vna-main-server
TESTING=true REQUIRE_AUTH=false python -m pytest tests/ -v --tb=short --cov=vna_main --cov-report=term-missing --cov-fail-under=40
```

Single main-server test:

```bash
cd vna-main-server
TESTING=true REQUIRE_AUTH=false python -m pytest tests/test_health.py::test_health_endpoint -v
```

BIDS server:

```bash
pip install -e vna-common/
pip install -r vna-bids-server/requirements.txt -r vna-bids-server/requirements-dev.txt
cd vna-bids-server
TESTING=true REQUIRE_AUTH=false python -m pytest tests/ -v --tb=short --cov=bids_server --cov-report=term-missing --cov-fail-under=40
```

Single BIDS-server test:

```bash
cd vna-bids-server
TESTING=true REQUIRE_AUTH=false python -m pytest tests/test_health.py::test_health_payload_shape -v
```

SDKs:

```bash
cd vna-main-sdk && python -m pytest tests/ -v --tb=short
cd vna-dicom-sdk && python -m pytest tests/ -v --tb=short
cd vna-bids-sdk && python -m pytest tests/ -v --tb=short
```

Single SDK test:

```bash
cd vna-main-sdk && python -m pytest tests/test_client.py -v
cd vna-dicom-sdk && python -m pytest tests/test_client.py -v
cd vna-bids-sdk && python -m pytest tests/test_client.py -v
```

Frontend:

```bash
cd vna-ux
npm ci
npm run lint
npx tsc --noEmit
npm run build
npm run dev
```

There is no frontend test script in `vna-ux/package.json` right now.

If you need to regenerate frontend API types, the existing script expects the main server to be running directly on port `8000`:

```bash
cd vna-ux
npm run generate-api
```

## High-level architecture

This repository is a multi-service VNA stack for medical imaging research:

- `vna-main-server` is the control plane. It owns the central resource index, patient mapping, projects, labels, monitoring, routing, audit, treatments, versions, and sync endpoints.
- `vna-bids-server` is the BIDS/file-management plane. It stores files under `BIDS_ROOT`, manages subjects/sessions/resources/labels/annotations, loads default modalities on startup, and can run background task + webhook delivery loops.
- `vna-dicom-server` packages Orthanc plus plugins and acts as the DICOM/PACS node.
- `vna-ux` is a React/Vite dashboard. In local dev it proxies `/api/v1` to the main server, `/bids-api` to the BIDS server (rewritten to `/api`), and `/dicom-web` and `/ohif` to Orthanc.
- `vna-common` is shared infrastructure used by both Python services: request ID middleware, API version headers, logging helpers, and common response models.

The important cross-service flow is:

1. Orthanc or the BIDS server emits sync/webhook events.
2. `vna-main-server` receives them through `/api/v1/sync/*`, then updates the central `ResourceIndex` and related patient/project metadata.
3. Main-server code is expected to call downstream services through `vna_main.services.http_client` instead of creating ad hoc HTTP clients.
4. The frontend mostly reads browsing and monitoring state from the main server, and pulls file content/previews from the BIDS service.

Keep the port split straight:

- Docker/containerized stack: main `18000`, BIDS `18080`, Orthanc HTTP `18042`, frontend `13000`, Postgres `18432`, Redis `18379`
- Service-only local dev: main `8000`, BIDS `8080`
- Vite dev server: `18300`

## Key conventions

### Auth and settings are enforced at import time

Both FastAPI services instantiate settings during import and raise immediately if auth is required but the corresponding API key is missing. Tests and ad hoc scripts need to set `REQUIRE_AUTH=false` (and usually `TESTING=true`) **before** importing app modules.

### The top-level test entrypoints are inconsistent

The root `pytest.ini` only targets `vna-main-server/tests` and `vna-bids-server/tests`, while the root `Makefile` still points some targets at top-level `tests/` files that are not in the repository. Do not assume `pytest` from repo root or `make test` covers the package you changed; run the package suite directly.

### The two Python services have different runtime assumptions

- `vna-main-server` defaults to SQLite for local/test usage and only calls `init_db()` automatically for SQLite. In PostgreSQL environments it expects schema management outside app startup.
- `vna-bids-server` assumes PostgreSQL + filesystem storage, creates writable storage/upload directories, and expects its schema to be managed before startup.
- Main-server rate limiting is Redis-backed; BIDS-server rate limiting is in-memory.

### Startup behavior matters when changing app lifecycle code

- `vna-main-server` closes its shared HTTP client and cache layer during shutdown.
- `vna-bids-server` always runs startup reclaim logic and default-modality loading, and only starts the long-running worker/webhook loops when `ENABLE_BACKGROUND_WORKER=true`.

### Service middleware and error shape are shared on purpose

Main and BIDS both add:

- request ID middleware from `vna_common.middleware.request_id`
- API version headers from `vna_common.middleware.api_version`
- service-specific rate limiting middleware
- a global exception handler returning `vna_common.responses.ErrorResponse`

Follow those patterns instead of inventing per-route response or error envelopes.

### Tests rely heavily on dependency overrides and module-level patching

- Main-server tests override `get_session`, disable Redis, and run against SQLite.
- BIDS-server tests patch the module-level `engine` and `async_session` references used by the app, task service, and webhook manager, then recreate metadata per test.

If you add endpoints, startup behavior, or new long-lived services, keep those fixtures working.

### Route prefixes are intentionally uneven

- Main-server routes live under `/api/v1/...`.
- BIDS resource routes live mostly under `/api/...`.
- BIDS also exposes `/api/v1/internal/status` for cross-service health checks.
- The replication router is mounted at `/replication`, not `/api/replication`.

Do not normalize these prefixes unless the change is deliberate and coordinated across callers.

### Frontend data access assumes Vite proxying

Frontend code uses `@/` imports and relative fetch paths, not environment-specific absolute URLs. Keep main-server calls under `/api/v1` and BIDS file/content calls under `/bids-api` so local Vite proxying and containerized deployment stay aligned.

## Relevant MCP server

Playwright MCP is a good fit for this repo when working in `vna-ux`. Use it for browser-level validation of archive browsing, label workflows, and viewer flows after the backend services are up. Prefer the Vite dev server at `http://localhost:18300` for active frontend work; use `http://localhost:13000` when validating the containerized UI.
