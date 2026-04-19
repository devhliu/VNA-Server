# DICOM Server SDK

Production-grade Python SDK for Orthanc-compatible DICOMweb servers. Provides both synchronous and asynchronous clients, a CLI, and type-safe Pydantic models.

## Installation

```bash
pip install -e .
```

Or from source:

```bash
pip install httpx click pydantic
```

## Quick Start

### Python API

```python
from dicom_sdk import DicomClient

# Connect to an Orthanc server
with DicomClient("http://localhost:8042", username=os.environ["DICOM_SERVER_USER"], password=os.environ["DICOM_SERVER_PASSWORD"]) as client:
    # Store a DICOM file
    result = client.store("chest_ct.dcm")
    print(f"Stored: {result.sop_instance_uid}")

    # Query studies
    studies = client.query(patient_id="P001", modality="CT")
    for study in studies:
        print(f"Study: {study.study_instance_uid}, Patient: {study.patient_name}")

    # Query series
    series = client.query_series(study_uid="1.2.3.4.5", modality="CT")
    for s in series:
        print(f"Series: {s.series_instance_uid}, Description: {s.series_description}")

    # Query instances
    instances = client.query_instances(
        study_uid="1.2.3.4.5",
        series_uid="1.2.3.4.5.1",
    )
    print(f"Found {len(instances)} instances")

    # Batch store multiple files
    results = client.store_directory("./dicom_folder")

    # Get patient info
    patient = client.get_patient("P001")
    print(f"Patient: {patient.patient_name}")

    # Get study details
    metadata = client.get_study("1.2.3.4.5")
    print(f"Description: {metadata.study_description}")

    # Retrieve DICOM files
    files = client.retrieve("1.2.3.4.5", output_dir="./downloaded")

    # Archive study to ZIP
    zip_data = client.archive_study("1.2.3.4.5")
    Path("study.zip").write_bytes(zip_data)

    # Anonymize a study
    result = client.anonymize("1.2.3.4.5", patient_name="ANONYMIZED")

    # Get server statistics
    stats = client.get_statistics()
    print(f"Server has {stats.count_studies} studies, {stats.count_instances} instances")

    # Get system info
    system = client.get_system()
    print(f"Orthanc version: {system.get('Version')}")

    # Get change log (for sync)
    changes = client.get_changes(limit=50, since=0)
    print(f"Change log: {len(changes.get('content', []))} changes")

    # Delete a study
    client.delete("1.2.3.4.5")
```

### Async API

```python
import asyncio
from dicom_sdk import AsyncDicomClient

async def main():
    async with AsyncDicomClient("http://localhost:8042") as client:
        studies = await client.query(patient_id="P001")
        for study in studies:
            print(study.study_instance_uid)

        stats = await client.get_statistics()
        print(f"Instances: {stats.count_instances}")

        # Batch store
        results = await client.store_directory("./dicom_folder")
        print(f"Stored {len(results)} files")

asyncio.run(main())
```

### Change Watcher (Orthanc → VNA Sync)

```python
import asyncio
from dicom_sdk import AsyncDicomClient, ChangeWatcher

async def main():
    client = AsyncDicomClient("http://localhost:8042")
    watcher = ChangeWatcher(
        dicom_client=client,
        vna_server_url="http://localhost:8000",
        api_key=os.environ["VNA_API_KEY"],
        poll_interval=5.0,
    )
    await watcher.start()  # Runs forever

asyncio.run(main())
```

### Synchronous Change Watcher

```python
from dicom_sdk import DicomClient, SyncWatcher

client = DicomClient("http://localhost:8042")
watcher = SyncWatcher(
    dicom_client=client,
    vna_server_url="http://localhost:8000",
    api_key=os.environ["VNA_API_KEY"],
    poll_interval=5.0,
)
watcher.start()  # Runs forever (blocking)
```

## CLI Usage

The CLI provides a command-line interface for common DICOM operations.

```bash
# Store a DICOM file
dicom-cli store chest_ct.dcm --server http://localhost:8042

# Query studies
dicom-cli query --patient-id P001 --server http://localhost:8042
dicom-cli query --modality CT --study-date 20240101 --server http://localhost:8042

# Retrieve DICOM files
dicom-cli retrieve 1.2.3.4.5 --server http://localhost:8042 --output ./downloaded

# Get study info
dicom-cli info 1.2.3.4.5 --server http://localhost:8042 --json

# Server statistics
dicom-cli stats --server http://localhost:8042

# Render DICOM as image
dicom-cli render 1.2.3.4.5 1.2.3.4.5.1 1.2.3.4.5.1.1 --server http://localhost:8042 --output image.png

# Delete a study
dicom-cli delete 1.2.3.4.5 --server http://localhost:8042 --yes

# List modalities
dicom-cli modalities --server http://localhost:8042

# JSON output (supported by store, query, info, stats, and modalities)
dicom-cli stats --server http://localhost:8042 --json

# Authentication
dicom-cli query --server http://localhost:8042 -u orthanc -p orthanc
```

## API Reference

### DicomClient / AsyncDicomClient

| Method | Description |
|--------|-------------|
| `store(file_path)` | Store a DICOM file (STOW-RS) |
| `upload_dicom(data)` | Upload raw DICOM bytes |
| `store_batch(file_paths)` | Store multiple DICOM files |
| `store_directory(path)` | Store all DICOM files in a directory |
| `query(...)` | Query studies (QIDO-RS) |
| `query_series(...)` | Query series (QIDO-RS at series level) |
| `query_instances(...)` | Query instances (QIDO-RS at instance level) |
| `retrieve(...)` | Retrieve DICOM files (WADO-RS) |
| `delete(...)` | Delete study/series/instance |
| `get_study(uid)` | Get study metadata |
| `get_series(study_uid, series_uid)` | Get series metadata |
| `get_instance(study_uid, series_uid, sop_uid)` | Get instance metadata |
| `get_patient(patient_id)` | Get patient metadata |
| `list_patients()` | List all patients |
| `render(...)` | Render DICOM as PNG/JPEG image |
| `list_modalities()` | List configured modalities |
| `get_statistics()` | Get server statistics |
| `list_studies()` | List all studies |
| `archive_study(uid)` | Archive study to ZIP |
| `archive_series(study_uid, series_uid)` | Archive series to ZIP |
| `anonymize(...)` | Anonymize a study |
| `list_peers()` | List configured peer DICOM nodes |
| `ping_peer(name)` | Ping a peer node (C-ECHO) |
| `get_system()` | Get Orthanc system information |
| `get_changes(limit, since)` | Get change log for sync |

### ChangeWatcher / SyncWatcher

| Method | Description |
|--------|-------------|
| `start()` | Start polling Orthanc /changes and forwarding events to VNA |
| `stop()` | Stop the watcher |

### Exceptions

| Exception | Description |
|-----------|-------------|
| `DicomError` | Base exception |
| `DicomConnectionError` | Connection failure |
| `DicomAuthenticationError` | Auth failure (401) |
| `DicomNotFoundError` | Resource not found (404) |
| `DicomValidationError` | Input validation error |
| `DicomServerError` | Server error (5xx) |

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v
```

## License

MIT
