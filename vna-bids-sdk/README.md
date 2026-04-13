# BIDS Server SDK

Python SDK and CLI for the BIDS Server (BIDSweb) API. Provides both synchronous and asynchronous clients for managing neuroimaging data.

## Features

- **Full API coverage** — Upload, download, query, labels, annotations, subjects, sessions, tasks, webhooks, and system operations
- **Sync & Async** — `BidsClient` for synchronous code, `AsyncBidsClient` for async/await
- **Type-safe** — Full type hints with Pydantic models
- **CLI included** — `bids-cli` for command-line operations
- **Progress tracking** — Optional callbacks for upload/download progress
- **Error handling** — Custom exception hierarchy maps HTTP errors to Python exceptions

## Installation

```bash
pip install bids-sdk
```

Or from source:

```bash
git clone https://github.com/bids-server/bids-sdk.git
cd bids-sdk
pip install -e ".[dev]"
```

## Quick Start

### Python API

```python
from bids_sdk import BidsClient

# Initialize client
client = BidsClient(base_url="http://localhost:8080", api_key="optional-key")

# Upload a file
resource = client.upload(
    "T1w.nii.gz",
    subject_id="sub-01",
    session_id="ses-01",
    modality="anat",
    labels=["quality:good"],
)

# Query resources
results = client.query(subject_id="sub-01", modality="anat", limit=10)
for r in results.resources:
    print(f"{r.id}: {r.filename}")

# Download a file
client.download("res-01", "./downloaded.nii.gz")

# Create annotation
ann = client.create_annotation("res-01", "region", "hippocampus", confidence=0.95)

# Submit async task
task = client.submit_task("convert", ["res-01"], params={"format": "nifti"})

# Close client
client.close()
```

Or use as a context manager:

```python
with BidsClient(base_url="http://localhost:8080") as client:
    subjects = client.list_subjects()
```

### Async API

```python
import asyncio
from bids_sdk import AsyncBidsClient

async def main():
    async with AsyncBidsClient(base_url="http://localhost:8080") as client:
        subjects = await client.list_subjects()
        for subject in subjects:
            sessions = await client.list_sessions(subject.subject_id)
            print(f"{subject.subject_id}: {len(sessions)} sessions")

asyncio.run(main())
```

### CLI

```bash
# Upload a file
bids-cli upload scan.nii.gz \
  --subject sub-01 \
  --session ses-01 \
  --modality anat \
  --server http://localhost:8080 \
  --labels "quality:good" \
  --json

# Download a file
bids-cli download res-01 \
  --output ./scan.nii.gz \
  --server http://localhost:8080

# Query resources
bids-cli query \
  --server http://localhost:8080 \
  --subject sub-01 \
  --modality anat \
  --json

# Manage labels
bids-cli label res-01 \
  --server http://localhost:8080 \
  --add '["new-tag"]' \
  --remove "old-tag"

# List/create subjects
bids-cli subjects --server http://localhost:8080 --list --json
bids-cli subjects --server http://localhost:8080 --create sub-03 --json

# Submit a task
bids-cli tasks \
  --server http://localhost:8080 \
  --submit convert \
  --resource-ids res-01,res-02 \
  --json

# Verify integrity
bids-cli verify --server http://localhost:8080 --json

# Rebuild database
bids-cli rebuild --server http://localhost:8080 --clear-existing --json
```

## API Reference

### Data Transfer

| Method | Description |
|--------|-------------|
| `upload(file_path, subject_id, session_id, modality, ...)` | Upload single file |
| `upload_chunked(file_path, subject_id, session_id, modality, ...)` | Chunked upload for large files |
| `download(resource_id, output_path)` | Download file |
| `download_stream(resource_id, output_path, range_start, range_end)` | Range download |
| `batch_download(resource_ids, output_path)` | Download multiple files as zip |

### Query

| Method | Description |
|--------|-------------|
| `query(subject_id, session_id, modality, labels, ...)` | Flexible resource search |

### Labels

| Method | Description |
|--------|-------------|
| `get_labels(resource_id)` | Get labels for a resource |
| `set_labels(resource_id, labels)` | Replace all labels |
| `patch_labels(resource_id, add, remove)` | Add/remove labels |
| `list_all_tags()` | List all tags with counts |

### Annotations

| Method | Description |
|--------|-------------|
| `create_annotation(resource_id, type, label, ...)` | Create annotation |
| `list_annotations(resource_id)` | List annotations for resource |

### Subjects & Sessions

| Method | Description |
|--------|-------------|
| `create_subject(subject_id, patient_ref, hospital_ids)` | Create subject |
| `get_subject(subject_id)` | Get subject by ID |
| `list_subjects()` | List all subjects |
| `create_session(session_id, subject_id, label)` | Create session |
| `list_sessions(subject_id)` | List sessions |

### Tasks

| Method | Description |
|--------|-------------|
| `submit_task(action, resource_ids, params)` | Submit async task |
| `get_task(task_id)` | Get task status |
| `cancel_task(task_id)` | Cancel task |

### Webhooks

| Method | Description |
|--------|-------------|
| `create_webhook(url, events, name, secret)` | Register webhook |
| `list_webhooks()` | List webhooks |
| `delete_webhook(webhook_id)` | Delete webhook |

### System

| Method | Description |
|--------|-------------|
| `verify(target, check_hash)` | Verify data integrity |
| `rebuild(target, clear_existing)` | Rebuild database |
| `list_modalities()` | List modalities |
| `register_modality(id, directory, extensions)` | Register modality |

## Error Handling

```python
from bids_sdk.exceptions import (
    BidsNotFoundError,      # 404
    BidsAuthenticationError, # 401
    BidsValidationError,     # 400
    BidsServerError,        # 5xx
    BidsTimeoutError,       # Request timeout
    BidsConnectionError,    # Connection failed
)

try:
    client.get_subject("nonexistent")
except BidsNotFoundError:
    print("Subject not found")
```

## Progress Callbacks

```python
def on_progress(bytes_done, total):
    print(f"{bytes_done}/{total} ({bytes_done/total*100:.1f}%)")

client.upload("large_file.nii.gz", ..., progress_callback=on_progress)
client.download("res-01", "./output.nii.gz", progress_callback=on_progress)
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Run specific test file
pytest tests/test_client.py -v
pytest tests/test_cli.py -v
```

## License

MIT
