# VNA (Vendor Neutral Archive)

A multi-service DICOM/BIDS archive system for medical imaging research data management.

## Architecture

```
                     ┌──────────────┐
                     │   Frontend   │ :13000
                     │  (React/Vite)│
                     └──────┬───────┘
                            │
          ┌─────────────────┼─────────────────┐
          ▼                 ▼                  ▼
┌─────────────────┐ ┌──────────────┐  ┌───────────────┐
│  VNA Main       │ │  VNA BIDS    │  │   Orthanc     │
│  Server         │ │  Server      │  │ (DICOM PACS)  │
│  :18000         │ │  :18080      │  │ :18042/:18242 │
└────────┬────────┘ └──────┬───────┘  └───────────────┘
         │                 │
    ┌────┴────┐       ┌────┴────┐
    │PostgreSQL│       │  Redis  │
    │  :18432  │       │  :18379 │
    └─────────┘       └─────────┘
```

### Services

| Service | Port | Description |
|---------|------|-------------|
| **VNA Main Server** | 18000 | Central API — patient mapping, resource index, sync, routing, projects |
| **VNA BIDS Server** | 18080 | BIDS data management — file storage, labels, annotations, queries, tasks |
| **Orthanc** | 18042 (HTTP) / 18242 (DICOM) | DICOM PACS server with DICOMweb, OHIF, and VolView plugins |
| **Frontend** | 13000 | React dashboard for browsing and managing data |
| **PostgreSQL** | 18432 | Primary database (separate DBs per service) |
| **Redis** | 18379 | Cache and rate limiting backend |

### SDKs & Shared Packages

| Package | Description |
|---------|-------------|
| **vna-common** | Shared middleware (API versioning, logging, request ID, rate limiting) and response models |
| **vna-main-sdk** | Python client for the Main Server API |
| **vna-dicom-sdk** | Python client for the Orthanc REST API |
| **vna-bids-sdk** | Python client for the BIDS Server API |

## Quick Start

### Prerequisites

- Docker & Docker Compose v2.0+
- Python 3.11+

### Deploy

```bash
# Clone and enter project
git clone <repository-url>
cd VNA-Server

# Configure environment
cp .env.example .env
# Edit .env — set POSTGRES_PASSWORD, VNA_API_KEY, BIDS_API_KEY,
# DICOM_SERVER_PASSWORD, REDIS_PASSWORD at minimum

# Start all services
docker compose up -d

# Verify health
curl http://localhost:18000/api/v1/health
curl http://localhost:18080/health
```

### Access Points

| UI | URL |
|----|-----|
| **VNA Dashboard** | http://localhost:13000 |
| **Main Server Docs** | http://localhost:18000/docs |
| **BIDS Server Docs** | http://localhost:18080/docs |
| **Orthanc Explorer** | http://localhost:18042 |

### Authentication

Both API servers require Bearer token authentication:

```bash
# Main Server
curl -H "Authorization: Bearer $VNA_API_KEY" http://localhost:18000/api/v1/resources

# BIDS Server
curl -H "Authorization: Bearer $BIDS_API_KEY" http://localhost:18080/api/subjects
```

### Running Tests

```bash
# Setup dev dependencies
make setup

# Unit tests (all packages)
make test

# Integration tests (starts Docker services)
make test-integration

# End-to-end tests
make test-e2e

# Individual packages
make test-main    # Main server only
make test-dicom   # DICOM SDK only
make test-bids    # BIDS SDK only

# Lint & format
make lint
make fmt
```

## API Overview

### Main Server (`/api/v1`)

| Route | Description |
|-------|-------------|
| `/api/v1/resources` | Central resource catalog — CRUD for all file references |
| `/api/v1/patients` | Patient mapping — hospital ID ↔ de-identified reference |
| `/api/v1/projects` | Research project management with members and resources |
| `/api/v1/labels` | Flexible key-value tags on resources |
| `/api/v1/query` | Unified cross-server search |
| `/api/v1/treatments` | Patient treatment timeline events |
| `/api/v1/versions` | Data versioning and snapshots |
| `/api/v1/webhooks` | Event subscription management |
| `/api/v1/routing` | Automatic data routing rules |
| `/api/v1/sync` | Cross-service synchronization |
| `/api/v1/monitoring` | Metrics, alerts, component health |
| `/api/v1/audit` | Audit log queries |
| `/api/v1/health` | Service health with dependency status |

### BIDS Server (`/api`)

| Route | Description |
|-------|-------------|
| `/api/store` | File upload — single and chunked (resumable) |
| `/api/objects` | File download, streaming, preview, batch export |
| `/api/query` | Multi-criteria search with JSONB, labels, and time-range filters |
| `/api/subjects` | Subject (patient) CRUD |
| `/api/sessions` | Scan session CRUD |
| `/api/labels` | Per-resource labels with JSON sidecar sync |
| `/api/annotations` | Structured annotations (bbox, segmentation, classification, etc.) |
| `/api/tasks` | Async task queue (convert, validate, export, reindex) |
| `/api/webhooks` | Event subscriptions |
| `/api/modalities` | Data type registration (17 built-in types) |
| `/api/verify` | Data integrity verification |
| `/api/rebuild` | Database reconstruction from filesystem |
| `/api/validation` | BIDS structure validation |
| `/replication` | Multi-datacenter replication |

## Project Structure

```
VNA-Server/
├── vna-main-server/          # Central API server (FastAPI, port 18000)
│   ├── vna_main/
│   │   ├── api/routes/       # 15 route modules
│   │   ├── models/           # SQLAlchemy ORM models
│   │   ├── services/         # Business logic (sync, routing, http_client)
│   │   ├── db/               # Database engine & migrations
│   │   ├── config/           # Pydantic Settings
│   │   └── static/           # Routing UI
│   └── tests/
├── vna-bids-server/          # BIDS data server (FastAPI, port 18080)
│   ├── bids_server/
│   │   ├── api/              # 14 route modules (store, query, labels, …)
│   │   ├── services/         # Task worker, replication, sync
│   │   ├── core/             # Webhook manager
│   │   ├── models/           # SQLAlchemy models & schemas
│   │   └── db/               # Database engine
│   └── tests/
├── vna-common/               # Shared package (pip install -e)
│   └── vna_common/           # Middleware + response models
├── vna-dicom-server/         # Orthanc configuration & Dockerfile
│   └── config/               # Lua scripts & orthanc.json
├── vna-ux/                   # React + Vite frontend
│   └── src/
├── vna-main-sdk/             # Python SDK for Main Server
├── vna-dicom-sdk/            # Python SDK for Orthanc
├── vna-bids-sdk/             # Python SDK for BIDS Server
├── scripts/                  # DevOps utilities (init-db, wait-for-http, …)
├── tests/                    # Integration & E2E tests
├── docs/                     # User guides, plans, UX design specs
├── docker-compose.yml
├── Makefile
└── .env
```

## Key Concepts

- **Resource Index** — Central catalog of all files (DICOM, NIfTI, BIDS, PDF, etc.)
- **Patient Mapping** — Maps hospital patient IDs to de-identified internal references
- **Labels / Tags** — Flexible key-value metadata attached to any resource
- **Annotations** — Structured data (bounding boxes, segmentation masks, classifications) linked to resources
- **Projects** — Groups of resources and patients for research studies
- **Treatment Timeline** — Chronological record of clinical events per patient
- **Sync Pipeline** — Event-driven flow: Orthanc → Main Server → BIDS Server
- **Routing Rules** — Automatic data forwarding based on modality, type, or custom conditions
- **Webhooks** — HTTP callbacks for real-time event notifications
- **Async Tasks** — Background job queue for compute-intensive operations (convert, validate, export)
- **Data Versioning** — Snapshot and restore support for reproducible research

## Documentation

- [**How to Use**](docs/how-to-use.md) — Comprehensive deployment, configuration, and API usage guide
- [**UX Design**](docs/ux-design.md) — Frontend design specifications
- [**Plans**](docs/plans.md) — Development roadmap and improvement tracking

## License

Proprietary — Internal research use only.
