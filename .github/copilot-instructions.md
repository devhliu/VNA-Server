# VNA-Server Copilot Instructions

## Build, test, and lint commands

### Repo-level shortcuts

Use the root `Makefile` first when it covers what you need:

```bash
make setup
make test
make test-main
make test-dicom
make test-bids
make test-integration
make test-e2e
make lint
make fmt
```

Important coverage detail: `make test` runs the top-level contract-style main-server test plus the DICOM and BIDS SDK suites. It does **not** run `vna-bids-server/tests/`; run that package directly when changing the BIDS service.

### Package-specific commands

Assume the package-specific install steps below have already been run before using the single-test examples.

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
cd vna-bids-sdk
python -m pytest tests/test_client.py -v
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

### Running services locally

Docker is the default integration path:

```bash
docker compose up -d
```

For service-only local development without full Dockerized app startup:

```bash
docker compose up -d postgres redis

cd vna-main-server
pip install -e ../vna-common
pip install -r requirements.txt
export VNA_API_KEY=dev-key REQUIRE_AUTH=false
export DATABASE_URL="postgresql+asyncpg://vna-admin:password@localhost:18432/vna_main"
uvicorn vna_main.main:app --host 0.0.0.0 --port 8000 --reload

cd ../vna-bids-server
pip install -r requirements.txt
pip install -e ../vna-common
export BIDS_API_KEY=dev-key REQUIRE_AUTH=false
export DATABASE_URL="postgresql+asyncpg://vna-admin:password@localhost:18432/bidsserver"
uvicorn bids_server.main:app --host 0.0.0.0 --port 8080 --reload
```

## High-level architecture

This repository is a multi-service VNA stack for medical imaging research:

- `vna-main-server` is the control plane. It owns the central resource index, patient mapping, projects, labels, monitoring, routing, audit, versioning, and sync endpoints.
- `vna-bids-server` is the BIDS/file-management plane. It stores files under `BIDS_ROOT`, manages subjects/sessions/resources/labels/annotations, and runs async task + webhook delivery loops on startup when background workers are enabled.
- `vna-dicom-server` packages Orthanc plus plugins and acts as the DICOM/PACS node.
- `vna-ux` is a React/Vite dashboard. In local dev it proxies `/api/v1` to the main server, `/bids-api` to the BIDS server (`/api` after rewrite), and DICOM viewer paths to Orthanc.
- `vna-common` is shared infrastructure used by both Python services: request ID middleware, API version headers, logging helpers, and common response models.

The important cross-service flow is:

1. Orthanc or the BIDS server emits sync/webhook events.
2. `vna-main-server` receives them through `/api/v1/sync/*`, then updates the central `ResourceIndex` and related patient/project metadata.
3. Main-server services call downstream systems through the shared async HTTP client in `vna_main.services.http_client` instead of creating ad hoc clients.
4. The frontend mostly reads from the main server for browsing/monitoring and pulls file content from the BIDS service for previews/downloads.

Deployment ports are easiest to reason about from `docker-compose.yml`:

- Main server: container `8000`, host `18000`
- BIDS server: container `8080`, host `18080`
- Orthanc HTTP: container `8042`, host `18042`
- Frontend container: host `13000`
- Frontend Vite dev server: `18300`

## Key conventions

### Auth and settings are enforced at import time

Both FastAPI services construct settings on import and will raise if auth is required but the corresponding API key is missing. Tests and ad hoc scripts usually set `REQUIRE_AUTH=false` (and often `TESTING=true`) **before** importing app modules.

### Top-level pytest config is not the whole test story

The root `pytest.ini` only points at `vna-main-server/tests` and `vna-bids-server/tests`, while the root `Makefile` also runs top-level contract/E2E tests and SDK suites separately. When changing a package, run that package's tests directly instead of assuming `pytest` from repo root or `make test` covers everything.

### Service middleware and error shape are shared on purpose

Main and BIDS both add:

- request ID middleware from `vna_common.middleware.request_id`
- API version headers from `vna_common.middleware.api_version`
- service-specific rate limiting middleware
- a global exception handler returning `vna_common.responses.ErrorResponse`

Follow those patterns instead of inventing per-route response/error envelopes.

### The two services use different runtime assumptions

- `vna-main-server` defaults to SQLite for local/test usage and switches to PostgreSQL in Docker/production.
- `vna-bids-server` assumes PostgreSQL + filesystem storage and runs Alembic-managed schema plus optional background worker loops.
- Main-server rate limiting is Redis-backed; BIDS-server rate limiting is in-memory.

### Tests rely heavily on dependency overrides

- Main-server tests override `get_session` and use in-memory SQLite.
- BIDS-server tests patch the session/engine globals and recreate metadata per test.

If you add endpoints or startup behavior, keep those fixtures working instead of bypassing them.

### Frontend data access assumes Vite proxying

Frontend hooks use `@/` imports and fetch relative paths, not environment-specific absolute URLs. Keep main-server calls under `/api/v1` and BIDS file/content calls under `/bids-api` so local Vite proxying and the containerized deployment stay aligned.

## Relevant MCP server

Playwright MCP is a good fit for this repo when working in `vna-ux`. Use it for browser-level validation of archive browsing, label workflows, and viewer flows after the backend services are up. Prefer the Vite dev server at `http://localhost:18300` for active frontend work; use `http://localhost:13000` when validating the containerized UI.
