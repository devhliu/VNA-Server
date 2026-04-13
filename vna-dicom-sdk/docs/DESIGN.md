# DICOM Server SDK — Design Document

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────┐
│                  dicom_sdk/                      │
│                                                  │
│  ┌──────────────┐    ┌───────────────────┐      │
│  │ DicomClient  │    │ AsyncDicomClient   │      │
│  │  (sync)      │    │  (async)           │      │
│  └──────┬───────┘    └────────┬──────────┘      │
│         │                     │                  │
│  ┌──────▼─────────────────────▼──────────┐      │
│  │          httpx (HTTP/2)               │      │
│  └──────────────────┬────────────────────┘      │
│                     │                            │
│  ┌──────────────────▼────────────────────┐      │
│  │  Orthanc REST API / DICOMweb           │      │
│  │  • /instances (STOW-RS)               │      │
│  │  • /tools/find (QIDO-RS)              │      │
│  │  • /studies/{uid} (WADO-RS)           │      │
│  │  • /{resource} (CRUD)                 │      │
│  │  • /statistics, /modalities           │      │
│  └───────────────────────────────────────┘      │
│                                                  │
│  ┌──────────────┐  ┌──────────────┐             │
│  │   models.py  │  │ exceptions.py│             │
│  │  Pydantic    │  │  Custom      │             │
│  │  data models │  │  exceptions  │             │
│  └──────────────┘  └──────────────┘             │
│                                                  │
│  ┌──────────────────────────────┐               │
│  │         cli.py               │               │
│  │  Click-based CLI             │               │
│  │  dicom-cli store/query/...   │               │
│  └──────────────────────────────┘               │
└─────────────────────────────────────────────────┘
```

### Design Principles

1. **Single Codebase, Dual Interface** — `DicomClient` and `AsyncDicomClient` share parsing logic but have independent HTTP paths (sync vs async).
2. **Orthanc-Native** — Uses Orthanc's REST API directly rather than a generic DICOMweb abstraction, giving access to Orthanc-specific features (statistics, modalities).
3. **Pydantic Models** — All data returned is parsed into strongly-typed Pydantic models with validation.
4. **Custom Exceptions** — HTTP errors are mapped to semantic DICOM exceptions for clean error handling.
5. **Zero Config** — Works with just a URL; auth, timeout, and SSL are optional.

## 2. Component Design

### 2.1 DicomClient (client.py)

The synchronous client wraps `httpx.Client`. Each method:
1. Validates inputs (raises `DicomValidationError` for bad arguments)
2. Sends an HTTP request via `_request()` helper
3. `_request()` wraps errors: `ConnectError` → `DicomConnectionError`, etc.
4. Parses JSON responses into Pydantic models

Key methods and their Orthanc endpoints:

| Method | HTTP | Endpoint | Notes |
|--------|------|----------|-------|
| `store()` | POST | `/instances` | Content-Type: application/dicom |
| `query()` | POST | `/tools/find` | JSON body with Level/Query/Expand |
| `retrieve()` | GET | `/studies/{uid}[/series/{uid}][/instances/{uid}]` | Accept: application/dicom |
| `delete()` | DELETE | `/{orthanc_id}` | Resolves DICOM UID → Orthanc ID first |
| `get_study()` | GET | `/{orthanc_id}` | Resolves via /tools/find |
| `render()` | GET | `/{orthanc_id}/render` | Accept: image/png or image/jpeg |
| `get_statistics()` | GET | `/statistics` | Direct REST call |
| `list_modalities()` | GET | `/modalities` | Direct REST call |

### 2.2 AsyncDicomClient (async_client.py)

Mirror of `DicomClient` using `httpx.AsyncClient`. Reuses parsing functions from `client.py`:
- `_parse_orthanc_study()`
- `_parse_orthanc_series()`
- `_parse_orthanc_instance()`
- `_raise_for_status()`

### 2.3 Models (models.py)

Pydantic v2 models with:
- `model_config = {"populate_by_name": True}` for DICOM tag alias support
- Optional fields throughout (DICOM data is inherently sparse)
- Nested models for hierarchical data (Study → Series → Instance)

### 2.4 Exceptions (exceptions.py)

```
DicomError (base)
├── DicomConnectionError   — network/timeout
├── DicomAuthenticationError — 401
├── DicomNotFoundError     — 404
├── DicomValidationError   — 400 / bad input
└── DicomServerError       — 5xx
```

### 2.5 CLI (cli.py)

Click-based CLI with consistent patterns:
- All commands accept `--server`, `-u`/`-p` for auth
- `--json` flag for machine-readable output
- `--verbose` for detailed output
- `delete` requires `--yes` or interactive confirmation

## 3. Data Flow

### Store Operation

```
User → store("file.dcm")
  → Path.read_bytes() → POST /instances (application/dicom)
  → Orthanc returns {ID, ParentStudy, ParentSeries}
  → StoreResult(sop_instance_uid, study_instance_uid, success=True)
```

### Query Operation

```
User → query(patient_id="P001")
  → POST /tools/find {Level: "Study", Query: {PatientID: "P001"}, Expand: True}
  → Orthanc returns list of study objects
  → [QueryResult(study_instance_uid, patient_id, patient_name, ...)]
```

### Retrieve Operation

```
User → retrieve("1.2.3.4", output_dir="/tmp")
  → GET /studies/1.2.3.4 (Accept: application/dicom)
  → Parse multipart response or single DICOM
  → Write files to output_dir/dicom_NNNN.dcm
  → Return list of bytes
```

## 4. CLI Usage Examples

```bash
# Upload a study
$ dicom-cli store scan001.dcm --server http://orthanc:8042
  success: True
  sop_instance_uid: abc123
  status_code: 200

# Find all CT studies from January
$ dicom-cli query --modality CT --study-date 20240101 --json --server http://orthanc:8042
[
  {
    "study_instance_uid": "1.2.3.4.5",
    "patient_id": "P001",
    "patient_name": "DOE^JOHN",
    ...
  }
]

# Download a study
$ dicom-cli retrieve 1.2.3.4.5 --server http://orthanc:8042 -o ./downloads
Retrieved 42 file(s) to ./downloads

# Check server health
$ dicom-cli stats --json --server http://orthanc:8042
{
  "count_studies": 150,
  "count_series": 450,
  "count_instances": 12000
}
```

## 5. Integration Guide

### With FastAPI / Starlette

```python
from fastapi import FastAPI
from dicom_sdk import DicomClient

app = FastAPI()
client = DicomClient("http://orthanc:8042")

@app.get("/studies")
def list_studies(patient_id: str = None):
    return client.query(patient_id=patient_id)
```

### With Django

```python
# views.py
from dicom_sdk import DicomClient

def study_list(request):
    client = DicomClient(settings.ORTHANC_URL)
    studies = client.query(patient_id=request.GET.get("patient_id"))
    return JsonResponse([s.model_dump() for s in studies], safe=False)
```

### Async with httpx/aiohttp

```python
from dicom_sdk import AsyncDicomClient

async def process_studies():
    async with AsyncDicomClient("http://orthanc:8042") as client:
        stats = await client.get_statistics()
        studies = await client.list_studies()
        return {"stats": stats, "studies": studies}
```

## 6. Testing Strategy

- **test_client.py**: Unit tests with mocked `httpx.Client.request()`. Covers all API methods, error paths, and edge cases.
- **test_cli.py**: Integration tests using Click's `CliRunner` with mocked `DicomClient`. Validates CLI argument parsing, output formatting, and error handling.

All tests run offline with no real server required.
