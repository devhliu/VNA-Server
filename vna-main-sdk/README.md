# VNA Main Server Python SDK

Python client library and CLI for the VNA Main Server — the central database and routing layer for unified DICOM + BIDS data management.

## Installation

```bash
pip install -e ".[dev]"
```

## Quick Start

### Python API

```python
from vna_main_sdk import VnaClient

# Connect to the VNA server
client = VnaClient(base_url="http://localhost:8000", api_key="your-key")

# Health check
status = client.health()
print(f"Server status: {status.status}")

# List resources
result = client.list_resources(patient_ref="patient-001", source_type="dicom")
for resource in result.resources:
    print(f"{resource.resource_id}: {resource.data_type}")

# Register a new DICOM resource
resource = client.register_resource(
    patient_ref="patient-001",
    source_type="dicom",
    dicom_study_uid="1.2.840.113619.2.55.3.604177001.1",
    dicom_series_uid="1.2.840.113619.2.55.3.604177001.1.1",
)

# Manage labels
client.set_labels(resource.resource_id, {"modality": "MRI", "site": "hospital_a"})
labels = client.get_labels(resource.resource_id)

# Query across sources
results = client.query(
    patient_ref="patient-001",
    data_type="imaging",
    labels={"modality": "MRI"},
    search="brain",
)

# Create patient mapping
patient = client.create_patient(
    patient_ref="vna-patient-001",
    hospital_id="HOS-12345",
    source="hospital_a",
)

client.close()
```

### Async API

```python
import asyncio
from vna_main_sdk import AsyncVnaClient

async def main():
    async with AsyncVnaClient(base_url="http://localhost:8000") as client:
        status = await client.health()
        print(f"Server status: {status.status}")

        resources = await client.list_resources(patient_ref="patient-001")
        for r in resources.resources:
            print(r.resource_id)

asyncio.run(main())
```

### CLI

```bash
# Health check
vna-cli --base-url http://localhost:8000 health

# List resources
vna-cli resources list --patient patient-001 --type imaging

# Get a specific resource
vna-cli resources get res-abc123

# Register a resource
vna-cli resources register --patient patient-001 --source dicom --dicom-study-uid 1.2.3.4

# Delete a resource
vna-cli resources delete res-abc123

# List patients
vna-cli patients list

# Create a patient
vna-cli patients create vna-patient-001 --hospital-id HOS-12345 --source hospital_a

# Get labels
vna-cli labels get res-abc123

# Set labels
vna-cli labels set res-abc123 --labels '{"modality": "MRI"}'

# Patch labels
vna-cli labels patch res-abc123 --add '{"site": "A"}' --remove 'old_tag'

# List all tags
vna-cli labels tags

# Unified query
vna-cli query --patient patient-001 --search "brain MRI"

# Sync management
vna-cli sync status
vna-cli sync trigger --source dicom

# JSON output
vna-cli --json resources list --patient patient-001
```

Set environment variables to avoid repeating flags:

```bash
export VNA_BASE_URL=http://localhost:8000
export VNA_API_KEY=your-api-key
```

## Features

- **Unified Resource Index** — Single view of DICOM and BIDS data
- **Patient ID Mapping** — Hospital IDs ↔ VNA internal IDs
- **Label Management** — Consistent labels across DICOM and BIDS sources
- **Cross-source Query** — Search and filter across all data
- **Sync Management** — Monitor and trigger database synchronization
- **Async Support** — Both sync and async clients available
- **Full Type Hints** — Pydantic v2 models throughout

## Development

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

## License

MIT
