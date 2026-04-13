# VNA Main Server — Design Document

## Architecture Overview

The VNA Main Server is the **central index and routing layer** in a three-component VNA (Vendor Neutral Archive) architecture:

```
┌─────────────────────────────────────────────────────┐
│                  VNA Main Server                     │
│                                                       │
│  ┌───────────┐  ┌───────────┐  ┌──────────────────┐ │
│  │ Resources  │  │ Patients  │  │ Labels           │ │
│  │ Index      │  │ Mapping   │  │ (unified tags)   │ │
│  └─────┬─────┘  └─────┬─────┘  └────────┬─────────┘ │
│        │              │                  │           │
│  ┌─────┴──────────────┴──────────────────┴─────────┐ │
│  │              PostgreSQL Database                 │ │
│  └──────────────────────────────────────────────────┘ │
│                                                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │
│  │ Sync        │  │ Query       │  │ Routing     │  │
│  │ Service     │  │ Engine      │  │ Service     │  │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  │
└─────────┼────────────────┼────────────────┼──────────┘
          │                │                │
    ┌─────┴──────┐   ┌────┴─────┐    ┌─────┴──────┐
    │ DICOM      │   │ BIDS     │    │ Unified    │
    │ Server     │   │ Server   │    │ API        │
    │ (Orthanc)  │   │          │    │ /v1/*      │
    └────────────┘   └──────────┘    └────────────┘
```

### Design Principles

1. **Single source of truth** — All resources across DICOM and BIDS are indexed in one place
2. **Non-destructive indexing** — Main Server indexes metadata, actual data stays on sub-servers
3. **Event-driven sync** — Sub-servers push change events; Main Server processes them asynchronously
4. **Unified labels** — Any resource can be tagged regardless of its storage backend
5. **Routing transparency** — Clients can query the Main Server and get routed to the right backend

---

## Data Model

### Patient Mapping

Maps hospital identifiers to VNA internal patient references. A single patient can appear across multiple systems (PACS, HIS, etc.).

| Column           | Type        | Description                     |
|------------------|-------------|---------------------------------|
| `patient_ref`    | VARCHAR(32) | PK — VNA internal ID (`pt-xxx`) |
| `hospital_id`    | VARCHAR(256)| Hospital's patient identifier   |
| `source`         | VARCHAR(128)| Hospital/clinic identifier      |
| `external_system`| VARCHAR(128)| Origin system (PACS, HIS, etc.) |

### Resource Index

The global index of all resources, whether stored in DICOM, BIDS, or both.

| Column             | Type       | Description                             |
|--------------------|------------|-----------------------------------------|
| `resource_id`      | VARCHAR(32)| PK — `res-xxx`                          |
| `patient_ref`      | VARCHAR(32)| FK → patient_mapping                    |
| `source_type`      | VARCHAR(32)| `dicom_only` / `bids_only` / `dicom_and_bids` |
| `dicom_study_uid`  | VARCHAR(128)| DICOM StudyInstanceUID                 |
| `dicom_series_uid` | VARCHAR(128)| DICOM SeriesInstanceUID                |
| `dicom_sop_uid`    | VARCHAR(128)| DICOM SOPInstanceUID                   |
| `bids_subject_id`  | VARCHAR(128)| BIDS subject (`sub-XX`)               |
| `bids_session_id`  | VARCHAR(128)| BIDS session (`ses-XX`)               |
| `bids_path`        | TEXT       | Path within BIDS dataset               |
| `data_type`        | VARCHAR(64)| `dicom`, `nifti`, `document`, `raw`   |
| `file_name`        | VARCHAR(512)| Original file name                    |
| `file_size`        | INTEGER    | Size in bytes                          |
| `content_hash`     | VARCHAR(128)| SHA256 hash                           |
| `metadata`         | JSONB      | Additional metadata                    |

### Labels

Unified tagging system. Any resource can have any labels.

| Column       | Type         | Description                          |
|--------------|--------------|--------------------------------------|
| `id`         | INTEGER      | PK, auto-increment                   |
| `resource_id`| VARCHAR(32)  | FK → resource_index (CASCADE)        |
| `tag_key`    | VARCHAR(256) | Label key (e.g., `modality`)         |
| `tag_value`  | VARCHAR(1024)| Label value (e.g., `CT`)             |
| `tag_type`   | VARCHAR(32)  | `system` / `custom` / `agent`        |
| `tagged_by`  | VARCHAR(128) | Who applied the tag                  |
| `tagged_at`  | TIMESTAMPTZ  | When                                 |

### Sync Events

Tracks change events from sub-servers for eventual consistency.

| Column        | Type         | Description                      |
|---------------|--------------|----------------------------------|
| `id`          | INTEGER      | PK, auto-increment               |
| `source_db`   | VARCHAR(32)  | `dicom` or `bids`               |
| `event_type`  | VARCHAR(32)  | `created` / `updated` / `deleted`|
| `resource_id` | VARCHAR(32)  | Affected resource                |
| `payload`     | JSONB        | Event data                       |
| `processed`   | BOOLEAN      | Whether event was consumed       |

---

## API Reference

All endpoints are under `/v1`.

### Resources (`/v1/resources`)

| Method | Path          | Description                    |
|--------|---------------|--------------------------------|
| GET    | `/`           | List resources with filters    |
| GET    | `/{id}`       | Get resource (merged view)     |
| POST   | `/`           | Register new resource          |
| PUT    | `/{id}`       | Update resource mapping        |
| DELETE | `/{id}`       | Delete from index              |

### Patients (`/v1/patients`)

| Method | Path              | Description                    |
|--------|-------------------|--------------------------------|
| GET    | `/`               | List patients                  |
| GET    | `/{patient_ref}`  | Get patient with resources     |
| POST   | `/`               | Create patient mapping         |
| PUT    | `/{patient_ref}`  | Update mapping                 |
| DELETE | `/{patient_ref}`  | Delete mapping                 |

### Labels (`/v1/labels`)

| Method | Path                | Description                    |
|--------|---------------------|--------------------------------|
| GET    | `/`                 | List all tags with counts      |
| GET    | `/resource/{id}`    | Get labels for resource        |
| PUT    | `/resource/{id}`    | Replace all labels             |
| PATCH  | `/resource/{id}`    | Add/update labels              |
| POST   | `/batch`            | Batch label operations         |

### Query (`/v1/query`)

| Method | Path  | Description                         |
|--------|-------|-------------------------------------|
| POST   | `/`   | Unified query across DICOM + BIDS   |

### Sync (`/v1/sync`)

| Method | Path        | Description                       |
|--------|-------------|-----------------------------------|
| POST   | `/register` | Register a sub-server             |
| GET    | `/status`   | Sync status                       |
| POST   | `/trigger`  | Trigger manual sync               |
| POST   | `/event`    | Receive event from sub-server     |
| GET    | `/events`   | List sync events                  |

### Health (`/v1/health`)

| Method | Path | Description                          |
|--------|------|--------------------------------------|
| GET    | `/`  | Health status of all components      |

---

## Sync Mechanism

The sync system follows an **event-driven push model**:

1. **Sub-servers push events** — When DICOM or BIDS servers create/update/delete data, they POST to `/v1/sync/event`
2. **Events are queued** — Events are stored in `sync_events` with `processed = false`
3. **Processing** — The Main Server processes events to update the resource index:
   - `created` → Add to resource_index
   - `updated` → Update metadata
   - `deleted` → Remove from index (or mark as deleted)
4. **Manual sync** — `POST /v1/sync/trigger` initiates a pull-based sync for reconciliation
5. **Server registration** — Sub-servers register via `/v1/sync/register` for tracking

### Event Flow

```
DICOM Server                    Main Server                    BIDS Server
     │                               │                              │
     │── POST /v1/sync/event ───────>│                              │
     │   {source_db: "dicom",        │                              │
     │    event_type: "created",     │── Store as pending ──>       │
     │    resource_id: "res-xxx"}    │                              │
     │                               │                              │
     │                               │<── POST /v1/sync/event ─────│
     │                               │    {source_db: "bids",...}   │
     │                               │                              │
     │                               │── Process pending ──>        │
     │                               │   Update resource_index      │
```

### Conflict Resolution

When a resource exists in both DICOM and BIDS (e.g., a converted NIfTI from DICOM):
- `source_type` is set to `dicom_and_bids`
- Both `dicom_*_uid` and `bids_*` fields are populated
- The resource appears in queries from both systems

---

## Running

### Development

```bash
pip install -r requirements.txt
uvicorn vna_main.main:app --reload
```

### Docker

```bash
# From project root (proj_vna/)
docker-compose up --build
```

### Testing

```bash
pytest tests/ -v
```

---

## Tech Stack

- **FastAPI** — Async web framework
- **SQLAlchemy 2.0** — Async ORM with PostgreSQL
- **Pydantic v2** — Request/response validation
- **httpx** — Async HTTP client for sub-server communication
- **PostgreSQL** — Primary database
- **pytest + pytest-asyncio** — Testing with async support
