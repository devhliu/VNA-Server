# VNA (Visual Neuroscience Archive)

A multi-service DICOM/BIDS archive system for medical imaging research data management.

## Architecture

```
┌─────────────┐     ┌──────────────────┐     ┌──────────────────┐
│   Orthanc    │────▶│   VNA Main       │────▶│   VNA BIDS       │
│  (DICOM PACS)│     │   Server         │     │   Server         │
│              │     │  (PostgreSQL)    │     │  (File Storage)  │
└─────────────┘     └──────────────────┘     └──────────────────┘
                           │
                    ┌──────┴──────┐
                    │   Redis     │
                    └─────────────┘
```

### Services

| Service | Port | Description |
|---------|------|-------------|
| **VNA Main Server** | 8000 | Central API, patient mapping, resource index, sync pipeline |
| **VNA BIDS Server** | 8001 | DICOM upload, BIDS conversion, task execution |
| **Orthanc** | 8042 | DICOM PACS server |
| **PostgreSQL** | 5432 | Primary database |
| **Redis** | 6379 | Cache layer |

### SDKs

- **vna-main-sdk** — Python client for the Main Server API
- **vna-dicom-sdk** — Python client for Orthanc REST API
- **vna-bids-sdk** — Python client for the BIDS Server API

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.11+
- Node.js 18+ (for dashboard, Phase 3)

### Development Setup

```bash
# Clone and enter project
cd vna-server

# Copy environment template
cp .env.example .env
# Edit .env with your settings

# Start all services
docker compose up -d

# Verify all services are healthy
make smoke

# Run tests (without Docker)
pip install -r vna-main-server/requirements.txt
pip install -r vna-bids-server/requirements.txt
cd vna-main-server && python -m pytest tests/ -v
cd ../vna-bids-server && python -m pytest tests/ -v
```

### Running Tests

```bash
# Main server tests
cd vna-main-server && python -m pytest tests/ -v

# BIDS server tests
cd vna-bids-server && python -m pytest tests/ -v

# All tests with coverage
cd .. && python -m pytest -v --cov
```

## API Documentation

- **Main Server**: http://localhost:8000/docs (OpenAPI/Swagger)
- **BIDS Server**: http://localhost:8001/docs

## Project Structure

```
vna-server/
├── vna-main-server/          # Central API server
│   ├── vna_main/
│   │   ├── api/routes/       # FastAPI route handlers
│   │   ├── models/           # SQLAlchemy ORM models
│   │   ├── services/         # Business logic layer
│   │   ├── db/migrations/    # Alembic migrations
│   │   └── config/           # Settings & configuration
│   └── tests/
├── vna-bids-server/          # BIDS/DICOM processing server
│   ├── bids_server/
│   │   ├── api/              # Upload, labels, annotations
│   │   ├── services/         # Task worker, replication
│   │   ├── core/             # Webhook manager
│   │   └── models/
│   └── tests/
├── vna-main-sdk/             # Python SDK for Main Server
├── vna-dicom-sdk/            # Python SDK for Orthanc
├── vna-bids-sdk/             # Python SDK for BIDS Server
├── config/
│   └── orthanc/              # Orthanc Lua scripts & config
├── scripts/                  # DevOps utilities
├── docker-compose.yml
└── docs/
```
vna-server/
├── vna-main-server/          # Central API server
│   ├── vna_main/
│   │   ├── api/routes/       # FastAPI route handlers
│   │   ├── models/           # SQLAlchemy ORM models
│   │   ├── services/         # Business logic layer
│   │   ├── db/migrations/    # Alembic migrations
│   │   └── config/           # Settings & configuration
│   └── tests/
├── vna-bids-server/          # BIDS/DICOM processing server
│   ├── bids_server/
│   │   ├── api/              # Upload, labels, annotations
│   │   ├── services/         # Task worker, replication
│   │   ├── core/             # Webhook manager
│   │   └── models/
│   └── tests/
├── vna-main-sdk/             # Python SDK for Main Server
├── vna-dicom-sdk/            # Python SDK for Orthanc
├── vna-bids-sdk/             # Python SDK for BIDS Server
├── config/
│   └── orthanc/              # Orthanc Lua scripts & config
├── scripts/                  # DevOps utilities
├── docker-compose.yml
└── docs/
```

## Key Concepts

- **Resource Index**: Central catalog of all files (DICOM, NIfTI, BIDS, PDF, etc.)
- **Patient Mapping**: Maps hospital patient IDs to de-identified internal references
- **Labels/Tags**: Flexible key-value metadata attached to resources
- **Projects**: Groups of resources and patients for research studies
- **Treatment Timeline**: Chronological record of clinical events per patient
- **Sync Events**: Event pipeline for Orthanc → Main → BIDS data flow
- **Webhooks**: HTTP callbacks for real-time event notifications

## License

Proprietary — Internal research use only.
