# VNA Main Server SDK — Design Document

## Overview

The VNA Main Server SDK provides a Python client for interacting with the VNA Main Server, which acts as the central database and routing layer in a medical imaging VNA (Vendor Neutral Archive) system. It manages a unified resource index that provides a single view of data stored across DICOM servers and BIDS-compliant filesystems.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   VNA Main Server                    │
│  ┌──────────────┐  ┌────────────┐  ┌─────────────┐  │
│  │  Resource     │  │  Patient   │  │   Label     │  │
│  │  Index        │  │  Registry  │  │   Store     │  │
│  └──────┬───────┘  └─────┬──────┘  └──────┬──────┘  │
│         └────────────────┼─────────────────┘         │
│                    Query Engine                      │
│                         │                            │
│  ┌──────────┐  ┌────────┴────────┐  ┌────────────┐  │
│  │  DICOM   │  │  Sync Manager   │  │   BIDS     │  │
│  │  Bridge  │  │                 │  │  Bridge    │  │
│  └────┬─────┘  └─────────────────┘  └─────┬──────┘  │
└───────┼────────────────────────────────────┼────────┘
        │                                    │
   DICOM Server                        BIDS Filesystem
```

## Module Structure

```
vna_main_sdk/
├── __init__.py          # Package exports
├── models.py            # Pydantic v2 data models
├── client.py            # Synchronous VnaClient
├── client_async.py      # Async AsyncVnaClient
└── cli.py               # Click-based CLI (vna-cli)
```

## Data Models

### Core Models

- **`Resource`** — Unified view of a DICOM study/series or BIDS entity. Contains both DICOM UIDs and BIDS path metadata plus shared labels.
- **`Patient`** — Patient record with hospital ID mapping and associated resources.
- **`Label`** — Key-value tag attached to resources. Shared across DICOM and BIDS.
- **`QueryResult`** — Paginated query response with total count and resource list.

### Supporting Models

- **`SyncStatus`** / **`SyncEvent`** — Sync state and event history.
- **`HealthStatus`** — Server health and version info.
- **`ServerRegistration`** — DICOM/BIDS server registration.
- **`BatchLabelOperation`** — Batch label mutation request.
- **`TagInfo`** — Tag key with usage count.

### Enums

- **`SourceType`** — `dicom` or `bids`
- **`DataType`** — `imaging`, `derivative`, `bids_raw`, `bids_deriv`

## Client Design

### Synchronous Client (`VnaClient`)

- Uses `httpx.Client` for HTTP requests.
- Supports context manager (`with` statement).
- All methods are blocking.
- Raises `VnaClientError` with status code and detail on failures.

### Async Client (`AsyncVnaClient`)

- Uses `httpx.AsyncClient` for async HTTP requests.
- Supports async context manager (`async with`).
- All methods are coroutines (`async def`).
- Reuses `VnaClientError` from the sync client.

### Error Handling

Both clients share `VnaClientError`:
- `message` — Human-readable error string.
- `status_code` — HTTP status code (if applicable).
- `detail` — Parsed response body (JSON or text).

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/health` | Health check |
| `GET` | `/api/v1/resources` | List resources (with filters) |
| `GET` | `/api/v1/resources/{id}` | Get resource |
| `POST` | `/api/v1/resources` | Register resource |
| `PATCH` | `/api/v1/resources/{id}` | Update resource |
| `DELETE` | `/api/v1/resources/{id}` | Delete resource |
| `GET` | `/api/v1/patients` | List patients |
| `GET` | `/api/v1/patients/{ref}` | Get patient |
| `POST` | `/api/v1/patients` | Create patient |
| `PATCH` | `/api/v1/patients/{ref}` | Update patient |
| `GET` | `/api/v1/resources/{id}/labels` | Get labels |
| `PUT` | `/api/v1/resources/{id}/labels` | Set labels |
| `PATCH` | `/api/v1/resources/{id}/labels` | Patch labels |
| `GET` | `/api/v1/labels/tags` | List all tags |
| `POST` | `/api/v1/labels/batch` | Batch label operations |
| `GET` | `/api/v1/query` | Unified query |
| `POST` | `/api/v1/servers` | Register server |
| `GET` | `/api/v1/sync/status` | Sync status |
| `POST` | `/api/v1/sync/trigger` | Trigger sync |

## CLI Design

The CLI uses Click with the following structure:

```
vna-cli [global options] <command group> <command> [options]

Global options:
  --base-url TEXT   Server URL (or VNA_BASE_URL env var)
  --api-key TEXT    API key (or VNA_API_KEY env var)
  --json            Output as JSON
  --verbose         Verbose output

Command groups:
  resources         Resource management
  patients          Patient management
  labels            Label management
  sync              Sync management

Standalone commands:
  query             Unified query
  health            Health check
```

## Testing Strategy

- **`test_client.py`** — Unit tests using `respx` to mock HTTP responses. Tests each API method including error paths and edge cases.
- **`test_cli.py`** — CLI tests using Click's `CliRunner` with mocked `VnaClient`. Tests all commands, JSON output, and error handling.

## Design Decisions

1. **Pydantic v2** — Uses `model_config = ConfigDict(...)` instead of `class Config` (Pydantic v1).
2. **`datetime.now(timezone.utc)`** — Avoids deprecated `datetime.utcnow()`.
3. **Shared error class** — `VnaClientError` used by both sync and async clients.
4. **Enum support** — Methods accept both strings and enum values for `SourceType`/`DataType`.
5. **Flexible label responses** — Handles both list and dict-wrapped list responses from the server.
6. **Click groups** — Nested command groups mirror the API structure.
