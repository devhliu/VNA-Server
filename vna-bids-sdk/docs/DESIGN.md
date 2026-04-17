# BIDS Server SDK Design Document

## Architecture Overview

The BIDS Server SDK is a Python client library for interacting with the BIDSweb API. It provides both synchronous and asynchronous interfaces for all server operations.

### Components

```
bids_sdk/
├── __init__.py          # Package exports
├── client.py            # Synchronous BidsClient
├── client_async.py      # Async AsyncBidsClient
├── cli.py               # Click-based CLI
├── exceptions.py        # Custom exception hierarchy
└── models.py            # Pydantic data models
```

### Design Principles

1. **Dual-mode API**: Every operation is available in both sync (`BidsClient`) and async (`AsyncBidsClient`) flavors.
2. **Type safety**: Full type hints with Pydantic models for request/response validation.
3. **Graceful error handling**: Custom exception hierarchy maps HTTP errors to Python exceptions.
4. **Progress feedback**: Upload and download operations accept optional progress callbacks.
5. **CLI parity**: All API operations accessible via the `bids-cli` command-line tool.

## API Reference

### Client Initialization

```python
from bids_sdk import BidsClient, AsyncBidsClient

# Sync client
client = BidsClient(
    base_url="http://bids-server:8080",
    timeout=30.0,
    api_key="optional-api-key",
    headers={"X-Custom": "value"},
    verify_ssl=True,
)

# Async client
async with AsyncBidsClient(base_url="http://bids-server:8080") as client:
    subjects = await client.list_subjects()
```

### Data Transfer

#### `upload(file_path, subject_id, session_id=None, modality, labels, metadata, progress_callback)`

Upload a single file. `session_id` is optional for subject-level uploads. Supports progress tracking via callback:

```python
def on_progress(bytes_read, total):
    print(f"{bytes_read}/{total} ({bytes_read/total*100:.1f}%)")

resource = client.upload(
    "T1w.nii.gz",
    subject_id="sub-01",
    modality="anat",
    labels=["quality:good"],
    progress_callback=on_progress,
)
```

#### `upload_chunked(file_path, subject_id, session_id=None, modality, chunk_size, ...)`

Chunked upload for large files. Breaks file into chunks and uploads sequentially:

```python
resource = client.upload_chunked(
    "large_scan.nii.gz",
    subject_id="sub-01",
    session_id="ses-01",
    modality="func",
    chunk_size=10 * 1024 * 1024,  # 10MB chunks
)
```

#### `download(resource_id, output_path, progress_callback)`

Download a single file:

```python
path = client.download("res-01", "./downloads/scan.nii.gz")
```

#### `download_stream(resource_id, output_path, range_start, range_end)`

Range-based download:

```python
# Download bytes 0-1023
path = client.download_stream("res-01", "./partial.nii.gz", 0, 1023)
```

#### `batch_download(resource_ids, output_path)`

Download multiple files as a zip:

```python
path = client.batch_download(["res-01", "res-02", "res-03"], "./batch.zip")
```

### Query

#### `query(subject_id, session_id, modality, labels, metadata, search, limit, offset)`

Flexible resource search:

```python
result = client.query(
    subject_id="sub-01",
    modality="anat",
    labels=["quality:good"],
    search="T1w",
    limit=50,
    offset=0,
)
print(f"Found {result.total} resources")
for resource in result.resources:
    print(resource.filename)
```

### Labels

```python
# Get labels
labels = client.get_labels("res-01")

# Replace all labels
client.set_labels("res-01", ["tag1", "tag2"])

# Add/remove labels
client.patch_labels("res-01", add=["new-tag"], remove=["old-tag"])

# List all tags with counts
tags = client.list_all_tags()
```

### Annotations

```python
# Create annotation
ann = client.create_annotation(
    "res-01",
    ann_type="region",
    label="hippocampus",
    data={"coordinates": [10, 20, 30]},
    confidence=0.95,
)

# List annotations
annotations = client.list_annotations("res-01")
```

### Subjects & Sessions

```python
# Create/get/list subjects
client.create_subject("sub-01", patient_ref="P001", hospital_ids=["H1"])
subject = client.get_subject("sub-01")
subjects = client.list_subjects()

# Create/list sessions
client.create_session("ses-01", "sub-01", session_label="baseline")
sessions = client.list_sessions(subject_id="sub-01")
```

### Tasks

```python
# Submit task
task = client.submit_task("convert", ["res-01"], params={"format": "nifti"})

# Check status
task = client.get_task(task.task_id)
print(f"Status: {task.status}, Progress: {task.progress}")

# Cancel
client.cancel_task(task.task_id)
```

### Webhooks

```python
# Register webhook
wh = client.create_webhook(
    "https://example.com/hooks/bids",
    events=["upload", "delete"],
    name="My Hook",
    secret="my-secret",
)

# List webhooks
webhooks = client.list_webhooks()

# Delete
client.delete_webhook(wh.webhook_id)
```

### System

```python
# Verify integrity
result = client.verify(target="sub-01", check_hash=True)

# Rebuild database
result = client.rebuild(clear_existing=False)

# Manage modalities
modalities = client.list_modalities()
client.register_modality("pet", "pet", [".nii.gz"])
```

## CLI Usage Examples

### Upload

```bash
# Basic upload
bids-cli upload scan.nii.gz --subject sub-01 --modality anat --server http://localhost:8080

# With labels and JSON output
bids-cli upload scan.nii.gz --subject sub-01 --session ses-01 --modality anat --server http://localhost:8080 --labels "quality:good,scanner:Siemens" --json

# Chunked upload
bids-cli upload large_scan.nii.gz --subject sub-01 --session ses-01 --modality func --server http://localhost:8080 --chunked --chunk-size 10485760
```

### Download

```bash
# Basic download
bids-cli download res-01 --output ./scan.nii.gz --server http://localhost:8080

# Range download
bids-cli download res-01 --output ./partial.nii.gz --server http://localhost:8080 --range-start 0 --range-end 1048575
```

### Query

```bash
# Query by subject and modality
bids-cli query --server http://localhost:8080 --subject sub-01 --modality anat --json

# Full-text search
bids-cli query --server http://localhost:8080 --search "hippocampus" --limit 10
```

### Labels

```bash
# Get labels
bids-cli label res-01 --server http://localhost:8080 --json

# Set labels
bids-cli label res-01 --server http://localhost:8080 --set '["tag1", "tag2"]'

# Add/remove labels
bids-cli label res-01 --server http://localhost:8080 --add '["new-tag"]' --remove "old-tag"
```

### Subjects & Sessions

```bash
# List subjects
bids-cli subjects --server http://localhost:8080 --list --json

# Create subject
bids-cli subjects --server http://localhost:8080 --create sub-03 --patient-ref P003 --json

# List sessions for subject
bids-cli sessions --server http://localhost:8080 --subject sub-01 --list --json

# Create session
bids-cli sessions --server http://localhost:8080 --subject sub-01 --create ses-02 --json
```

### Tasks

```bash
# Submit task
bids-cli tasks --server http://localhost:8080 --submit convert --resource-ids res-01,res-02 --json

# Check status
bids-cli tasks --server http://localhost:8080 --status task-01 --json

# Cancel task
bids-cli tasks --server http://localhost:8080 --cancel task-01 --json
```

### System

```bash
# Verify data integrity
bids-cli verify --server http://localhost:8080 --json

# Rebuild database
bids-cli rebuild --server http://localhost:8080 --clear-existing --json
```

## Integration Guide

### Installation

```bash
pip install bids-sdk
```

### Error Handling

```python
from bids_sdk import BidsClient
from bids_sdk.exceptions import (
    BidsNotFoundError,
    BidsAuthenticationError,
    BidsValidationError,
    BidsServerError,
)

client = BidsClient(base_url="http://localhost:8080")
try:
    subject = client.get_subject("sub-01")
except BidsNotFoundError:
    print("Subject not found")
except BidsAuthenticationError:
    print("Invalid API key")
except BidsValidationError as e:
    print(f"Invalid request: {e.details}")
except BidsServerError as e:
    print(f"Server error: {e.message}")
```

### Async Usage

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

### Custom Headers & Auth

```python
client = BidsClient(
    base_url="http://localhost:8080",
    api_key="your-api-key",
    headers={"X-Request-ID": "abc123"},
    verify_ssl=True,
)
```

### Progress Tracking

```python
def upload_with_progress(filepath, client):
    total_size = os.path.getsize(filepath)

    def on_progress(bytes_done, total):
        pct = bytes_done / total * 100
        bar = "█" * int(pct // 2) + "░" * (50 - int(pct // 2))
        print(f"\r[{bar}] {pct:.1f}%", end="", flush=True)

    resource = client.upload(
        filepath,
        subject_id="sub-01",
        modality="anat",
        progress_callback=on_progress,
    )
    print()  # newline after progress bar
    return resource
```
