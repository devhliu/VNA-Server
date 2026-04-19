# How to Use VNA Server

This guide covers deploying, configuring, and using the VNA (Vendor Neutral Archive) server system — a multi-service platform for medical imaging research data management.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Prerequisites](#prerequisites)
3. [Quick Start (Docker)](#quick-start-docker)
4. [Configuration](#configuration)
5. [Authentication](#authentication)
6. [Main Server API](#main-server-api)
7. [BIDS Server API](#bids-server-api)
8. [SDK Usage](#sdk-usage)
9. [End-to-End Workflows](#end-to-end-workflows)
10. [Monitoring & Operations](#monitoring--operations)
11. [Local Development](#local-development)
12. [Troubleshooting](#troubleshooting)
13. [Production Deployment](#production-deployment)

---

## Architecture Overview

```
                    ┌──────────────┐
                    │   Frontend   │ :13000
                    │   (React)    │
                    └──────┬───────┘
                           │
         ┌─────────────────┼─────────────────┐
         ▼                 ▼                  ▼
┌────────────────┐ ┌──────────────┐  ┌───────────────┐
│  VNA Main      │ │  VNA BIDS    │  │   Orthanc     │
│  Server        │ │  Server      │  │ (DICOM PACS)  │
│  :18000        │ │  :18080      │  │  :18042       │
└───────┬────────┘ └──────┬───────┘  └───────────────┘
        │                 │
   ┌────┴────┐       ┌────┴────┐
   │PostgreSQL│       │PostgreSQL│
   │  :18432  │       │  :18432 │
   └─────────┘       └─────────┘
        │
   ┌────┴────┐
   │  Redis  │
   │  :18379 │
   └─────────┘
```

| Service | Default Port | Description |
|---------|-------------|-------------|
| **VNA Main Server** | 18000 | Central coordination: patient mapping, resource index, routing, sync |
| **VNA BIDS Server** | 18080 | BIDS data management: file storage, labels, annotations, queries |
| **Orthanc** | 18042 (HTTP) / 18242 (DICOM) | DICOM PACS server with web viewer |
| **Frontend** | 13000 | React dashboard for browsing and managing data |
| **PostgreSQL** | 18432 | Shared database (separate DBs per service) |
| **Redis** | 18379 | Cache and rate limiting backend |

---

## Prerequisites

- **Docker & Docker Compose** v2.0+
- **Python 3.11+** (for local development / SDK usage)
- **Git**

---

## Quick Start (Docker)

### 1. Clone and Configure

```bash
git clone <repository-url>
cd VNA-Server

# Create environment file from template
cp .env.example .env
```

### 2. Edit `.env` — Required Variables

```bash
# Database
POSTGRES_USER=vna-admin
POSTGRES_PASSWORD=<strong-password>
POSTGRES_DB=postgres

# API Keys (REQUIRED — servers refuse to start without them)
VNA_API_KEY=<main-server-api-key>
BIDS_API_KEY=<bids-server-api-key>
BIDS_SERVER_API_KEY=<same-as-BIDS_API_KEY>

# Orthanc
DICOM_SERVER_USER=vna-orthanc-user
DICOM_SERVER_PASSWORD=<orthanc-password>

# Redis
REDIS_PASSWORD=<redis-password>
REDIS_ENABLED=true

# BIDS Storage
BIDS_ROOT=/data01/vna_data
UPLOAD_TEMP_DIR=/tmp/bids_uploads
ENABLE_BACKGROUND_WORKER=true
WORKER_POLL_INTERVAL=2
```

### 3. Start All Services

```bash
docker compose up -d

# Check status
docker compose ps

# Wait for all health checks to pass
docker compose logs -f main-server bids-server
```

### 4. Verify

```bash
# Main Server
curl http://localhost:18000/

# BIDS Server
curl http://localhost:18080/

# Health checks
curl http://localhost:18000/api/v1/health
curl http://localhost:18080/health
```

### 5. Access UIs

| UI | URL |
|---|---|
| **VNA Dashboard** | http://localhost:13000 |
| **Main Server Swagger** | http://localhost:18000/docs |
| **BIDS Server Swagger** | http://localhost:18080/docs |
| **Orthanc Explorer** | http://localhost:18042 |

---

## Configuration

### Main Server Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite+aiosqlite:///./vna_main.db` | Database connection string |
| `DICOM_SERVER_URL` | `http://localhost:8042` | Orthanc server URL |
| `BIDS_SERVER_URL` | `http://localhost:8080` | BIDS server URL |
| `VNA_API_KEY` | *(required)* | API key for main server authentication |
| `BIDS_SERVER_API_KEY` | — | API key for main→BIDS server calls |
| `DICOM_SERVER_USER` / `DICOM_SERVER_PASSWORD` | — | Orthanc credentials |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection string |
| `REDIS_ENABLED` | `true` | Enable Redis caching |
| `CACHE_TTL` | `300` | Cache time-to-live (seconds) |
| `DB_POOL_SIZE` | `10` | Database connection pool size |
| `REQUIRE_AUTH` | `true` | Enforce API key authentication |
| `LOG_LEVEL` | `INFO` | Logging level |
| `LOG_FORMAT` | `text` | `text` or `json` |

### BIDS Server Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://...` | Database connection string |
| `BIDS_ROOT` | `/bids_data` | Root directory for BIDS file storage |
| `UPLOAD_TEMP_DIR` | `/tmp/bids_uploads` | Temporary directory for chunked uploads |
| `MAX_UPLOAD_SIZE` | `10737418240` (10 GB) | Maximum single-file upload size |
| `CHUNK_SIZE` | `10485760` (10 MB) | Chunk size for resumable uploads |
| `BIDS_API_KEY` | *(required)* | API key for BIDS server authentication |
| `ENABLE_BACKGROUND_WORKER` | `true` | Enable async task processing |
| `WORKER_POLL_INTERVAL` | `2` | Task worker poll interval (seconds) |
| `REQUIRE_AUTH` | `true` | Enforce API key authentication |

---

## Authentication

Both servers use Bearer token authentication. Include the API key in every request:

```bash
# Main Server
curl -H "Authorization: Bearer $VNA_API_KEY" \
  http://localhost:18000/api/v1/resources

# BIDS Server
curl -H "Authorization: Bearer $BIDS_API_KEY" \
  http://localhost:18080/api/subjects
```

**Unauthenticated endpoints** (no token needed):
- `GET /` — Root health check
- `GET /health` — Detailed health status
- `GET /docs`, `/redoc` — API documentation

For convenience, set shell variables:

```bash
export VNA_KEY="your-main-server-api-key"
export BIDS_KEY="your-bids-server-api-key"
alias vna='curl -s -H "Authorization: Bearer $VNA_KEY" -H "Content-Type: application/json"'
alias bids='curl -s -H "Authorization: Bearer $BIDS_KEY" -H "Content-Type: application/json"'
```

---

## Main Server API

Base URL: `http://localhost:18000/api/v1`

All examples below assume the `vna` alias above or an explicit `Authorization` header.

### Resources (Central Catalog)

```bash
# List resources (paginated)
vna http://localhost:18000/api/v1/resources

# Create a resource entry
vna -X POST http://localhost:18000/api/v1/resources \
  -d '{
    "source_type": "dicom_only",
    "dicom_study_uid": "1.2.840.113654.2.70.1.123",
    "data_type": "dicom",
    "patient_ref": "PAT001"
  }'

# Get a specific resource
vna http://localhost:18000/api/v1/resources/{resource_id}

# Update a resource
vna -X PUT http://localhost:18000/api/v1/resources/{resource_id} \
  -d '{"data_type": "nifti", "bids_path": "sub-001/ses-01/anat/T1w.nii.gz"}'

# Delete a resource
vna -X DELETE http://localhost:18000/api/v1/resources/{resource_id}
```

### Patients

```bash
# List patients (paginated)
vna http://localhost:18000/api/v1/patients

# Create patient mapping
vna -X POST http://localhost:18000/api/v1/patients \
  -d '{
    "hospital_id": "HOSP-12345",
    "source": "radiology",
    "external_system": "HIS"
  }'

# Sync patients from Orthanc
vna -X POST "http://localhost:18000/api/v1/patients/sync-from-dicom?hospital_id=default"
```

### Projects

```bash
# Create a research project
vna -X POST http://localhost:18000/api/v1/projects \
  -d '{
    "name": "Glioma Longitudinal Study",
    "description": "Multi-center brain tumor progression tracking",
    "principal_investigator": "Dr. Wang"
  }'

# List projects
vna http://localhost:18000/api/v1/projects

# Add a member to a project
vna -X POST http://localhost:18000/api/v1/projects/{project_id}/members \
  -d '{"patient_ref": "PAT001"}'

# Add a resource to a project
vna -X POST http://localhost:18000/api/v1/projects/{project_id}/resources \
  -d '{"resource_id": "res-abc123"}'
```

### Labels (Main Server)

```bash
# Set labels on a resource
vna -X PUT http://localhost:18000/api/v1/labels/{resource_id} \
  -d '{
    "labels": [
      {"tag_key": "diagnosis", "tag_value": "glioma", "tag_type": "clinical"},
      {"tag_key": "qc_status", "tag_value": "passed", "tag_type": "custom"}
    ],
    "tagged_by": "dr.smith"
  }'

# Get labels for a resource
vna http://localhost:18000/api/v1/labels/{resource_id}

# Batch set labels on multiple resources
vna -X POST http://localhost:18000/api/v1/labels/batch \
  -d '{
    "resource_ids": ["res-001", "res-002", "res-003"],
    "labels": [{"tag_key": "cohort", "tag_value": "training"}]
  }'
```

### Unified Query

```bash
# Query across all data sources
vna -X POST http://localhost:18000/api/v1/query \
  -d '{
    "patient_ref": "PAT001",
    "data_type": "nifti",
    "label_key": "diagnosis",
    "label_value": "glioma",
    "limit": 50,
    "offset": 0
  }'
```

### Treatment Timeline

```bash
# Record a treatment event
vna -X POST http://localhost:18000/api/v1/treatments \
  -d '{
    "patient_ref": "PAT001",
    "event_type": "surgery",
    "event_date": "2026-03-15",
    "description": "Tumor resection - left temporal lobe",
    "outcome": "complete resection",
    "facility": "University Hospital"
  }'

# Get patient treatment timeline
vna http://localhost:18000/api/v1/treatments/timeline/{patient_ref}
```

### Webhooks (Main Server)

```bash
# Register a webhook for resource events
vna -X POST http://localhost:18000/api/v1/webhooks \
  -d '{
    "url": "https://my-app.example.com/hooks/vna",
    "events": ["resource.created", "resource.updated"],
    "description": "Pipeline trigger"
  }'

# List webhooks
vna http://localhost:18000/api/v1/webhooks
```

### Routing Rules

```bash
# Create a routing rule (auto-forward data by type)
vna -X POST http://localhost:18000/api/v1/routing/rules \
  -d '{
    "name": "MRI to BIDS",
    "target": "bids-server",
    "rule_type": "data_type",
    "conditions": {"modality": "MR"},
    "priority": 100,
    "enabled": true
  }'

# List routing rules
vna http://localhost:18000/api/v1/routing/rules
```

### Data Versioning

```bash
# Create a version snapshot
vna -X POST http://localhost:18000/api/v1/versions/{resource_id} \
  -d '{
    "change_type": "update",
    "change_description": "Added segmentation mask",
    "changed_by": "pipeline:nnunet"
  }'

# List versions for a resource
vna http://localhost:18000/api/v1/versions/{resource_id}
```

### Audit Logs

```bash
# Query audit trail
vna "http://localhost:18000/api/v1/audit/logs?action=create&resource_type=resource&limit=20"
```

### Sync Pipeline

```bash
# Trigger database sync
vna -X POST http://localhost:18000/api/v1/sync/trigger

# Send a sync event
vna -X POST http://localhost:18000/api/v1/sync/event \
  -d '{
    "source_db": "dicom",
    "event_type": "study_stable",
    "resource_id": "orthanc-study-uuid",
    "payload": {"PatientID": "12345", "Modality": "MR"}
  }'

# Verify cross-service consistency
vna -X POST http://localhost:18000/api/v1/sync/verify
```

### Monitoring

```bash
# Full health check (all sub-services)
vna http://localhost:18000/api/v1/health

# Prometheus-style metrics
vna http://localhost:18000/api/v1/monitoring/metrics

# Detailed component health
vna http://localhost:18000/api/v1/monitoring/health
```

---

## BIDS Server API

Base URL: `http://localhost:18080/api`

All examples below assume the `bids` alias or an explicit `Authorization: Bearer $BIDS_KEY` header.

### Upload Files

#### Single File Upload

```bash
# Upload a NIfTI file with labels
bids -X POST http://localhost:18080/api/store \
  -H "Content-Type: multipart/form-data" \
  -F "file=@sub-001_ses-01_T1w.nii.gz" \
  -F "subject_id=sub-001" \
  -F "session_id=sub-001_ses-01" \
  -F "modality=anat" \
  -F "source=scanner_import" \
  -F 'labels={"diagnosis": "tumor", "qc": "pass", "scanner": "Siemens_Prisma"}'
```

#### Chunked Upload (Large Files)

```bash
# Step 1: Initialize upload session
bids -X POST http://localhost:18080/api/store/init \
  -d '{
    "file_name": "sub-001_ses-01_bold.nii.gz",
    "file_size": 524288000,
    "modality": "func",
    "subject_id": "sub-001",
    "session_id": "sub-001_ses-01",
    "labels": {"task": "rest", "run": "01"}
  }'
# Response: {"upload_id": "upl-abc123", "chunk_size": 10485760, "total_chunks": 50}

# Step 2: Upload chunks (repeat for each chunk)
curl -X PATCH http://localhost:18080/api/store/upl-abc123 \
  -H "Authorization: Bearer $BIDS_KEY" \
  -F "chunk_index=0" \
  -F "file=@chunk_000"

# Step 3: Finalize
bids -X POST http://localhost:18080/api/store/upl-abc123/complete
```

### Download & Stream Files

```bash
# Download a file
curl -H "Authorization: Bearer $BIDS_KEY" \
  http://localhost:18080/api/objects/{resource_id} \
  -o output.nii.gz

# Stream with Range support (resume-friendly)
curl -H "Authorization: Bearer $BIDS_KEY" \
  -H "Range: bytes=0-10485759" \
  http://localhost:18080/api/objects/{resource_id}/stream \
  -o partial.bin

# Get JSON sidecar metadata
bids http://localhost:18080/api/objects/{resource_id}/metadata

# Render a preview (NIfTI → PNG slice)
curl -H "Authorization: Bearer $BIDS_KEY" \
  "http://localhost:18080/api/objects/{resource_id}/render?format=png&slice_index=80" \
  -o preview.png

# Batch download as ZIP
bids -X POST http://localhost:18080/api/objects/batch-download \
  -d '["res-001", "res-002", "res-003"]' \
  -o batch.zip
```

### Query Resources

```bash
# Multi-criteria query
bids -X POST http://localhost:18080/api/query \
  -d '{
    "subject_id": "sub-001",
    "modality": ["anat", "func"],
    "labels": {
      "match": ["tumor"],
      "exclude": ["rejected"]
    },
    "metadata": {"scanner": "Siemens_Prisma"},
    "time_range": {
      "field": "created_at",
      "from": "2026-01-01T00:00:00Z",
      "to": "2026-12-31T23:59:59Z"
    },
    "sort": [{"field": "created_at", "order": "desc"}],
    "limit": 50,
    "offset": 0
  }'
```

### Subjects (Patients)

```bash
# List subjects (paginated)
bids http://localhost:18080/api/subjects?limit=50&offset=0

# Create a subject
bids -X POST http://localhost:18080/api/subjects \
  -d '{
    "subject_id": "sub-002",
    "patient_ref": "PAT002",
    "hospital_ids": {"site_a": "H-5678", "site_b": "P-9012"},
    "metadata": {"age": 65, "sex": "M", "group": "patient"}
  }'

# Get subject details
bids http://localhost:18080/api/subjects/sub-002

# Update subject
bids -X PUT http://localhost:18080/api/subjects/sub-002 \
  -d '{"metadata": {"age": 65, "sex": "M", "group": "patient", "status": "active"}}'

# Delete subject (cascades to sessions and resources)
bids -X DELETE http://localhost:18080/api/subjects/sub-002
```

### Sessions (Scan Sessions)

```bash
# List sessions (optionally filter by subject)
bids "http://localhost:18080/api/sessions?subject_id=sub-001&limit=50"

# Create a session
bids -X POST http://localhost:18080/api/sessions \
  -d '{
    "session_id": "sub-001_ses-baseline",
    "subject_id": "sub-001",
    "session_label": "ses-baseline",
    "scan_date": "2026-03-15T10:30:00Z",
    "metadata": {"scanner": "Siemens_Prisma", "coil": "64ch_head"}
  }'
```

### Labels (BIDS Server)

```bash
# List all unique tags with counts
bids http://localhost:18080/api/labels

# Get labels for a specific resource
bids http://localhost:18080/api/labels/{resource_id}

# Set (replace) labels for a resource
bids -X PUT http://localhost:18080/api/labels/{resource_id} \
  -d '{
    "labels": {
      "diagnosis": "glioblastoma",
      "grade": "IV",
      "reviewed_by": "dr.chen",
      "qc": "pass"
    }
  }'

# Patch (merge) labels — adds/updates without removing existing
bids -X PATCH http://localhost:18080/api/labels/{resource_id} \
  -d '{"labels": {"treatment_phase": "pre-op"}}'
```

### Annotations (Structured)

```bash
# Create a bounding box annotation
bids -X POST http://localhost:18080/api/annotations \
  -d '{
    "resource_id": "res-xxxxx",
    "ann_type": "bbox",
    "label": "tumor",
    "data": {"x": 120, "y": 85, "z": 42, "w": 45, "h": 38, "d": 22},
    "confidence": 0.95,
    "created_by": "model:nnunet_v2"
  }'

# Create a classification annotation
bids -X POST http://localhost:18080/api/annotations \
  -d '{
    "resource_id": "res-xxxxx",
    "ann_type": "classification",
    "label": "glioma_grade",
    "data": {"class": "HGG", "probabilities": {"LGG": 0.12, "HGG": 0.88}},
    "confidence": 0.88,
    "created_by": "model:classifier_v3"
  }'

# List annotations (filter by resource or type)
bids "http://localhost:18080/api/annotations?resource_id=res-xxxxx&ann_type=bbox"
```

Supported annotation types: `bbox`, `point`, `polygon`, `segmentation`, `text`, `classification`.

### Async Tasks

```bash
# Submit a task
bids -X POST http://localhost:18080/api/tasks \
  -d '{
    "action": "validate",
    "resource_ids": ["res-001", "res-002"],
    "params": {"strict": true},
    "callback_url": "https://my-app.example.com/hooks/task-done"
  }'
# Response: {"task_id": "tsk-abc123", "status": "queued", ...}

# Poll task status
bids http://localhost:18080/api/tasks/tsk-abc123

# List tasks (filter by status)
bids "http://localhost:18080/api/tasks?status=running&limit=20"

# Cancel a task
bids -X DELETE http://localhost:18080/api/tasks/tsk-abc123
```

Supported task actions: `convert`, `analyze`, `export`, `validate`, `reindex`.

### Data Integrity

```bash
# Verify file integrity (DB ↔ filesystem)
bids -X POST http://localhost:18080/api/verify \
  -d '{"check_hashes": true, "auto_repair": false}'

# Rebuild database from filesystem (disaster recovery)
bids -X POST http://localhost:18080/api/rebuild \
  -d '{"target": "all", "clear_existing": false}'

# Validate BIDS structure
bids -X POST http://localhost:18080/api/validation/dataset \
  -d '{"strict": false}'
```

### Modalities

```bash
# List registered modalities
bids http://localhost:18080/api/modalities

# Register a custom modality
bids -X POST http://localhost:18080/api/modalities \
  -d '{
    "modality_id": "spect",
    "directory": "spect",
    "description": "SPECT imaging",
    "extensions": [".nii", ".nii.gz", ".dcm"],
    "required_files": ["json"],
    "category": "nuclear"
  }'
```

Built-in modalities: `anat`, `func`, `dwi`, `fmap`, `ct`, `pet`, `microscopy`, `eeg`, `meg`, `docs`, `tables`, `code`, `models`, `raw`, `other`.

### Webhooks (BIDS Server)

```bash
# Register a webhook
bids -X POST http://localhost:18080/api/webhooks \
  -d '{
    "name": "Pipeline Trigger",
    "url": "https://my-app.example.com/hooks/bids",
    "events": ["resource.created", "resource.deleted", "task.completed"],
    "secret": "webhook-signing-secret",
    "filters": {"modality": "anat"}
  }'

# List webhooks
bids http://localhost:18080/api/webhooks

# Delete a webhook
bids -X DELETE http://localhost:18080/api/webhooks/{webhook_id}
```

Available events: `resource.created`, `resource.updated`, `resource.deleted`, `label.updated`, `annotation.created`, `task.completed`, `task.failed`, `*` (all).

### Data Relationships

```bash
# Link resources (parent/child, DICOM reference, same-subject)
bids -X PUT http://localhost:18080/api/objects/{resource_id}/relationships \
  -d '{
    "parent_refs": ["res-original-t1w"],
    "dicom_ref": "1.2.840.113654.2.70.1.123",
    "same_subject": ["res-flair", "res-dwi"]
  }'

# Get relationships
bids http://localhost:18080/api/objects/{resource_id}/relationships
```

---

## SDK Usage

### VNA BIDS SDK (Python)

```python
from bids_sdk.client import BidsClient

client = BidsClient(
    base_url="http://localhost:18080",
    api_key=os.environ["BIDS_API_KEY"],
)

# Upload a file
resource = client.upload(
    file_path="sub-001_ses-01_T1w.nii.gz",
    subject_id="sub-001",
    session_id="sub-001_ses-01",
    modality="anat",
    labels={"diagnosis": "tumor"},
)
print(f"Uploaded: {resource['resource_id']}")

# Query resources
results = client.query(subject_id="sub-001", modality=["anat"])
for r in results:
    print(r["bids_path"])

# Download a file
client.download(resource_id="res-xxxxx", output_path="./output.nii.gz")
```

### Async SDK

```python
from bids_sdk.client_async import AsyncBidsClient

async with AsyncBidsClient(
    base_url="http://localhost:18080",
    api_key=os.environ["BIDS_API_KEY"],
) as client:
    resources = await client.query(modality=["pet"])
    for r in resources:
        print(r["resource_id"], r["bids_path"])
```

---

## End-to-End Workflows

### Workflow 1: Import DICOM Data into BIDS

```bash
# 1. Upload DICOM to Orthanc
curl -X POST http://localhost:18042/instances \
  -u "$DICOM_SERVER_USER:$DICOM_SERVER_PASSWORD" \
  --data-binary @scan.dcm

# 2. Orthanc triggers sync event → Main Server picks it up automatically
#    (via Lua script + /api/v1/internal/events/dicom endpoint)

# 3. Check the resource appeared in Main Server
vna http://localhost:18000/api/v1/resources

# 4. The routing rules forward it to BIDS Server for conversion
#    Upload the converted NIfTI to BIDS Server
bids -X POST http://localhost:18080/api/store \
  -F "file=@sub-001_ses-01_T1w.nii.gz" \
  -F "subject_id=sub-001" \
  -F "session_id=sub-001_ses-01" \
  -F "modality=anat" \
  -F "dicom_ref=1.2.840.113654.2.70.1.123"

# 5. Tag the resource
bids -X PUT http://localhost:18080/api/labels/res-xxxxx \
  -d '{"labels": {"diagnosis": "glioma", "grade": "IV"}}'
```

### Workflow 2: Build a Research Dataset

```bash
# 1. Create a project
vna -X POST http://localhost:18000/api/v1/projects \
  -d '{"name": "Brain Tumor Dataset v2", "principal_investigator": "Dr. Li"}'

# 2. Query all tumor cases
bids -X POST http://localhost:18080/api/query \
  -d '{"labels": {"match": ["tumor"]}, "modality": ["anat", "func"]}'

# 3. Batch tag for the dataset
bids -X PATCH http://localhost:18080/api/labels/{resource_id} \
  -d '{"labels": {"dataset": "brain_tumor_v2", "split": "train"}}'

# 4. Batch download
bids -X POST http://localhost:18080/api/objects/batch-download \
  -d '["res-001", "res-002", "res-003"]' \
  -o dataset.zip
```

### Workflow 3: AI Pipeline Integration

```bash
# 1. Register a webhook for new uploads
bids -X POST http://localhost:18080/api/webhooks \
  -d '{
    "name": "Auto-segment",
    "url": "https://pipeline.internal/hooks/segment",
    "events": ["resource.created"],
    "filters": {"modality": "anat"}
  }'

# 2. When a file is uploaded, the webhook fires automatically
# 3. Your pipeline downloads, processes, and uploads results:

# Download the input
curl -H "Authorization: Bearer $BIDS_KEY" \
  http://localhost:18080/api/objects/{resource_id}/stream -o input.nii.gz

# Run segmentation (your pipeline)
# ...

# Upload result with relationship link
bids -X POST http://localhost:18080/api/store \
  -F "file=@sub-001_ses-01_T1w_dseg.nii.gz" \
  -F "subject_id=sub-001" \
  -F "session_id=sub-001_ses-01" \
  -F "modality=anat" \
  -F 'labels={"pipeline": "nnunet_v2", "type": "segmentation"}'

# Link parent → child
bids -X PUT http://localhost:18080/api/objects/{result_id}/relationships \
  -d '{"parent_refs": ["{input_resource_id}"]}'

# Add annotation
bids -X POST http://localhost:18080/api/annotations \
  -d '{
    "resource_id": "{result_id}",
    "ann_type": "segmentation",
    "label": "brain_structures",
    "data": {"classes": ["GM", "WM", "CSF"], "num_voxels": [450000, 380000, 120000]},
    "confidence": 0.92,
    "created_by": "pipeline:nnunet_v2"
  }'
```

---

## Monitoring & Operations

### Health Checks

```bash
# Main Server — comprehensive health with sub-service status
curl http://localhost:18000/api/v1/health
# Returns: live/ready/degraded status, DB, Redis, Orthanc, BIDS checks

# BIDS Server — operational health
curl http://localhost:18080/health
# Returns: database, storage, webhook delivery status

# Internal cross-service probe
curl -X POST http://localhost:18080/api/v1/internal/status
```

### Database Backup & Restore

```bash
# Backup PostgreSQL (all databases)
docker compose exec postgres pg_dumpall -U vna-admin > backup_$(date +%Y%m%d).sql

# Restore
cat backup_20260413.sql | docker compose exec -T postgres psql -U vna-admin

# BIDS file backup — the filesystem is the source of truth
rsync -av /data01/vna_data/ /backup/bids_data/

# Disaster recovery — rebuild DB index from filesystem
bids -X POST http://localhost:18080/api/rebuild \
  -d '{"target": "all", "clear_existing": true}'
```

### Audit Trail

```bash
# Who did what?
vna "http://localhost:18000/api/v1/audit/logs?limit=100"

# Filter by action
vna "http://localhost:18000/api/v1/audit/logs?action=delete&resource_type=resource"
```

---

## Local Development

### Run Servers Without Docker

```bash
# Start infrastructure only
docker compose up -d postgres redis

# Main Server
cd vna-main-server
pip install -r requirements.txt
export VNA_API_KEY=$VNA_API_KEY REQUIRE_AUTH=false
export DATABASE_URL="postgresql+asyncpg://$POSTGRES_USER:$POSTGRES_PASSWORD@localhost:$POSTGRES_PORT/vna_main"
uvicorn vna_main.main:app --host 0.0.0.0 --port 8000 --reload

# BIDS Server (separate terminal)
cd vna-bids-server
pip install -r requirements.txt
pip install -e ../vna-common
export BIDS_API_KEY=$BIDS_API_KEY REQUIRE_AUTH=false
export DATABASE_URL="postgresql+asyncpg://$POSTGRES_USER:$POSTGRES_PASSWORD@localhost:$POSTGRES_PORT/bidsserver"
uvicorn bids_server.main:app --host 0.0.0.0 --port 8080 --reload
```

### Run Tests

```bash
# Main Server tests
cd vna-main-server
TESTING=true VNA_API_KEY=test REQUIRE_AUTH=false \
  python -m pytest tests/ -v

# BIDS Server tests
cd vna-bids-server
TESTING=true BIDS_API_KEY=test REQUIRE_AUTH=false \
  python -m pytest tests/ -v
```

### Database Migrations

```bash
# Create a new migration
cd vna-main-server
alembic revision --autogenerate -m "add new column"

# Apply migrations
alembic upgrade head

# Check current version
alembic current
```

---

## Troubleshooting

### Services Won't Start

```bash
# Check logs
docker compose logs main-server
docker compose logs bids-server

# Common cause: missing API key
# Fix: set VNA_API_KEY and BIDS_API_KEY in .env
```

### "401 Unauthorized"

```bash
# Verify your API key
curl -v -H "Authorization: Bearer $VNA_API_KEY" http://localhost:18000/api/v1/resources
# Check the VNA_API_KEY matches what's in .env
```

### Database Connection Errors

```bash
# Verify PostgreSQL is running
docker compose exec postgres pg_isready -U vna-admin

# Check connection string
docker compose exec main-server env | grep DATABASE_URL
```

### Upload Fails with 413

The file exceeds `MAX_UPLOAD_SIZE` (default 10 GB). Use chunked upload for large files, or increase the limit in BIDS server configuration.

### Rate Limited (429)

The server enforces per-IP rate limits. Check response headers:
- `X-RateLimit-Limit` — max requests per window
- `X-RateLimit-Remaining` — remaining quota
- `Retry-After` — seconds until retry allowed

---

## Production Deployment

### Security Checklist

- [ ] Set strong, unique values for `POSTGRES_PASSWORD`, `REDIS_PASSWORD`, `VNA_API_KEY`, `BIDS_API_KEY`
- [ ] Set `REQUIRE_AUTH=true` on both servers
- [ ] Set `CORS_ORIGINS` to specific allowed domains (not `*`)
- [ ] Place a reverse proxy (NGINX/Traefik) in front for TLS termination
- [ ] Restrict database/Redis ports to internal networks only
- [ ] Rotate API keys periodically

### Resource Tuning

Docker Compose applies default resource limits (configurable in `docker-compose.yml`):

| Service | Memory | CPU |
|---------|--------|-----|
| PostgreSQL | 1 GB | 1.0 |
| Redis | 512 MB | 0.5 |
| Main Server | 1 GB | 1.0 |
| BIDS Server | 1 GB | 1.0 |
| Orthanc | 2 GB | 2.0 |
| Frontend | 256 MB | 0.5 |

Adjust `deploy.resources.limits` per service based on workload.

### Log Aggregation

Enable JSON logging for structured log collection:

```bash
# In .env
LOG_FORMAT=json
LOG_LEVEL=INFO
```

Logs include `request_id`, `timestamp`, `level`, `module` — suitable for ELK, Loki, or CloudWatch.
