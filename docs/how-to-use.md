# How to Use VNA Server

This guide provides comprehensive instructions for building, deploying, and using the VNA (Visual Neuroscience Archive) server system.

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Development Setup](#development-setup)
3. [Building the Services](#building-the-services)
4. [Running the Services](#running-the-services)
5. [Using the APIs](#using-the-apis)
6. [Examples](#examples)
7. [Troubleshooting](#troubleshooting)
8. [Production Deployment](#production-deployment)

## Prerequisites

Before you begin, ensure you have the following installed:

- Docker & Docker Compose (v2.0+)
- Python 3.11+
- Git
- Make (optional but recommended)

## Development Setup

Follow these steps to set up the development environment:

### 1. Clone the Repository

```bash
git clone <repository-url>
cd vna-server
```

### 2. Configure Environment

Copy the example environment file and edit it with your settings:

```bash
cp .env.example .env
# Edit .env with your preferred text editor
nano .env
```

Key configuration options in `.env`:
- Database credentials
- Redis connection settings
- Orthanc configuration
- API keys and secrets

### 3. Install Python Dependencies

```bash
# Install dependencies for both servers
pip install -r vna-main-server/requirements.txt
pip install -r vna-bids-server/requirements.txt
```

### 4. Initialize Databases

```bash
# Run database migrations for main server
cd vna-main-server
alembic upgrade head
cd ..

# Run database migrations for bids server (if applicable)
cd vna-bids-server
alembic upgrade head
cd ..
```

## Building the Services

VNA Server uses Docker Compose to build and run all services. You can build the images manually or let Docker Compose handle it.

### Manual Build

```bash
# Build all services
docker compose build

# Or build specific services
docker compose build vna-main-server
docker compose build vna-bids-server
docker compose build orthanc
```

### Using Makefile (Recommended)

The project includes a Makefile with convenient commands:

```bash
# Show available make commands
make help

# Common build commands
make build          # Build all services
make rebuild        # Rebuild all services (no cache)
make pull           # Pull latest base images
```

## Running the Services

### Development Mode

```bash
# Start all services in detached mode
docker compose up -d

# View logs for all services
docker compose logs -f

# View logs for a specific service
docker compose logs -f vna-main-server
```

### Development Mode with Hot Reload

For development, you might want to run services with hot reload:

```bash
# Start main server with reload
cd vna-main-server
uvicorn vna_main.main:app --host 0.0.0.0 --port 8000 --reload

# In another terminal, start bids server with reload
cd vna-bids-server
uvicorn bids_server.main:app --host 0.0.0.0 --port 8001 --reload
```

Note: You'll still need to run Orthanc, PostgreSQL, and Redis via Docker Compose:
```bash
docker compose up -d orthanc postgres redis
```

### Stopping Services

```bash
# Stop all services
docker compose down

# Stop all services and remove volumes
docker compose down -v
```

## Using the APIs

Once the services are running, you can access the APIs:

### Main Server API
- URL: http://localhost:8000
- Interactive Docs: http://localhost:8000/docs
- Alternative Docs: http://localhost:8000/redoc

### BIDS Server API
- URL: http://localhost:8001
- Interactive Docs: http://localhost:8001/docs
- Alternative Docs: http://localhost:8001/redoc

### Orthanc DICOM Server
- URL: http://localhost:8042
- Default Login: `orthanc` / `orthanc`

## SDK Usage

VNA provides Python SDKs for interacting with each service:

### VNA Main SDK

```python
from vna_main_sdk import VNAMainClient

# Initialize client
client = VNAMainClient(base_url="http://localhost:8000")

# Get server info
info = client.get_info()
print(info)

# Create a new patient
patient_data = {
    "external_id": "HOSP12345",
    "name": "John Doe",
    "birth_date": "1980-01-01",
    "sex": "M"
}
patient = client.create_patient(patient_data)
print(f"Created patient: {patient.id}")
```

### VNA BIDS SDK

```python
from vna_bids_sdk import VNABIDSClient

# Initialize client
client = VNABIDSClient(base_url="http://localhost:8001")

# Upload a DICOM file
with open("path/to/dicom/file.dcm", "rb") as f:
    upload_result = client.upload_dicom(f, filename="file.dcm")
print(f"Uploaded: {upload_result.id}")

# Get BIDS conversion status
status = client.get_conversion_status(upload_result.id)
print(f"Conversion status: {status.status}")
```

### VNA DICOM SDK (for Orthanc)

```python
from vna_dicom_sdk import OrthancClient

# Initialize client
client = OrthancClient(base_url="http://localhost:8042", auth=("orthanc", "orthanc"))

# Get list of studies
studies = client.get_studies()
print(f"Found {len(studies)} studies")

# Get a specific study
study = client.get_study(studies[0])
print(f"Study: {study.MainDicomTags.PatientName}")
```

## Examples

Here are practical examples of common operations:

### Example 1: Complete DICOM to BIDS Workflow

This example shows the full flow from DICOM upload to BIDS conversion:

```bash
# 1. Upload a DICOM file to Orthanc (via Main Server)
curl -X POST "http://localhost:8000/dicom/upload" \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "/path/to/dicom/file.dcm",
    "patient_id": "HOSP12345"
  }'

# 2. Wait for sync to Main Server (check status)
curl "http://localhost:8000/resources?external_id=HOSP12345"

# 3. Trigger BIDS conversion via Main Server
curl -X POST "http://localhost:8000/sync/trigger" \
  -H "Content-Type: application/json" \
  -d '{
    "resource_id": "RESOURCE_ID_FROM_PREVIOUS_STEP"
  }'

# 4. Check conversion status on BIDS Server
curl "http://localhost:8001/conversion/status?resource_id=RESOURCE_ID"
```

### Example 2: Creating a Research Project

```bash
# 1. Create a new project
curl -X POST "http://localhost:8000/projects" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Alzheimer's Study 2024",
    "description": "Longitudinal study of Alzheimer's progression",
    "principal_investigator": "Dr. Smith"
  }'

# 2. Add patients to project
curl -X POST "http://localhost:8000/projects/PROJECT_ID/patients" \
  -H "Content-Type: application/json" \
  -d '{
    "patient_ids": ["PATIENT_ID_1", "PATIENT_ID_2"]
  }'

# 3. Add labels/tags to resources
curl -X POST "http://localhost:8000/resources/RESOURCE_ID/labels" \
  -H "Content-Type: application/json" \
  -d '{
    "labels": [
      {"key": "study_phase", "value": "baseline"},
      {"key": "scan_type", "value": "T1-weighted"}
    ]
  }'
```

### Example 3: Retrieving BIDS Data

```bash
# 1. Find BIDS-converted resources
curl "http://localhost:8001/bids/resources?subject=001&session=baseline"

# 2. Download BIDS file
curl -o sub-001_ses-baseline_T1w.nii.gz \
  "http://localhost:8001/bids/download?filepath=sub-001/ses-baseline/anat/sub-001_ses-baseline_T1w.nii.gz"

# 3. Get BIDS dataset description
curl "http://localhost:8001/bids/dataset-description"
```

## Troubleshooting

### Common Issues

#### Services Not Starting
```bash
# Check service logs
docker compose logs [service-name]

# Check if ports are already in use
sudo lsof -i :8000
sudo lsof -i :8001
sudo lsof -i :8042

# Restart services
docker compose restart [service-name]
```

#### Database Connection Issues
```bash
# Check PostgreSQL connection
docker compose exec postgres pg_isready -U ${POSTGRES_USER}

# Check Redis connection
docker compose exec redis redis-cli ping
```

#### Migration Failures
```bash
# Check migration history
cd vna-main-server
alembic current
alembic history

# Try to stamp to a known good revision
alembic stamp base
alembic upgrade head
```

#### DICOM Upload Problems
```bash
# Check Orthanc logs
docker compose logs orthanc

# Verify DICOM file is valid
dicom_info /path/to/dicom/file.dcm

# Check file permissions
ls -l /path/to/dicom/file.dcm
```

### Getting Help

If you encounter issues not covered here:

1. Check the [GitHub Issues](https://github.com/your-org/vna-server/issues)
2. Review the [CHANGELOG.md](../CHANGELOG.md) for recent changes
3. Consult the API documentation at http://localhost:8000/docs and http://localhost:8001/docs
4. Contact the development team

## Production Deployment

For production deployments, consider these additional steps:

### Security Considerations

1. Change default passwords in `.env`:
   - Database credentials
   - Redis password
   - Orthanc credentials
   - API keys

2. Enable HTTPS:
   - Configure SSL/TLS termination at the reverse proxy level
   - Update `BASE_URL` in `.env` to use HTTPS

3. Configure firewall rules:
   - Only expose necessary ports (typically 80/443 for HTTP/HTTPS)
   - Restrict database and Redis access to internal networks

### Performance Optimization

1. Adjust resource limits in `docker-compose.yml`:
   - Increase memory for Orthanc if handling large DICOM studies
   - Adjust Redis memory based on caching needs
   - Tune PostgreSQL shared buffers and connections

2. Enable caching:
   - Configure Redis for API response caching
   - Enable HTTP caching proxies (Varnish, Cloudflare)

3. Use a reverse proxy:
   - Deploy NGINX or Traefik for SSL termination and load balancing
   - Configure rate limiting and request throttling

### Backup and Recovery

1. Database backups:
   ```bash
   # Backup PostgreSQL
   docker compose exec postgres pg_dumpall -U ${POSTGRES_USER} > backup.sql

   # Restore PostgreSQL
   cat backup.sql | docker compose exec -i postgres psql -U ${POSTGRES_USER}
   ```

2. File storage backups:
   - Orthanc storage: `/var/lib/orthanc` in the orthanc container
   - BIDS server storage: Configured via `BIDS_STORAGE_PATH` in `.env`

3. Regular backup schedule:
   ```bash
   # Add to crontab for daily backups at 2 AM
   0 2 * * * /path/to/backup/script.sh
   ```

### Monitoring and Logging

1. Health checks:
   - All services expose `/health` endpoints
   - Configure monitoring system to check these endpoints

2. Log aggregation:
   - Use Docker logging drivers to send logs to ELK stack or similar
   - Configure application-level logging in Python services

3. Metrics collection:
   - Services expose Prometheus metrics at `/metrics` (if enabled)
   - Configure Prometheus to scrape these endpoints

## Conclusion

You now have a comprehensive understanding of how to build, deploy, and use the VNA Server system. From development setup to production deployment, this guide covers the essential aspects of working with VNA.

Remember to:
- Regularly update dependencies and base images
- Monitor service health and performance
- Backup critical data regularly
- Consult the API documentation for advanced features

For the most up-to-date information, always refer to the README.md and check the project repository.