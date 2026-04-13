# VNA Server Architecture Review

**Review Date:** 2026-04-07  
**Reviewer:** Fullstack Developer (Medical Imaging & Data Storage Specialist)  
**Scope:** Module consistency and inter-module interactions

> **Status: Items marked with [FIXED] have been addressed as of 2026-04-13.**
---

## Executive Summary

The VNA (Vendor Neutral Archive) server is a comprehensive medical imaging data management system built with a microservices architecture. The system integrates DICOM image storage (Orthanc), BIDS (Brain Imaging Data Structure) data management, and a main coordination server with a React-based frontend.

**Overall Assessment:** The architecture is well-structured with clear separation of concerns. However, there are several consistency issues and potential improvements that should be addressed for production readiness.

---

## 1. Architecture Overview

### 1.1 Core Components

```
┌─────────────────────────────────────────────────────────────┐
│                      VNA Stack                               │
├─────────────────────────────────────────────────────────────┤
│  UX Layer        │ vna-ux (React + TypeScript + Vite)       │
├──────────────────┼──────────────────────────────────────────┤
│  API Gateway     │ vna-main-server (FastAPI)                │
│                  │  - Resource indexing                      │
│                  │  - Patient mapping                        │
│                  │  - Sync coordination                      │
│                  │  - Webhook management                     │
├──────────────────┼──────────────────────────────────────────┤
│  DICOM Server    │ vna-dicom-server (Orthanc 26.1.0)        │
│                  │  - DICOMweb support                       │
│                  │  - OHIF/VolView viewers                   │
│                  │  - Lua scripting for sync                 │
├──────────────────┼──────────────────────────────────────────┤
│  BIDS Server     │ vna-bids-server (FastAPI)                │
│                  │  - BIDS data management                   │
│                  │  - Multi-datacenter support               │
│                  │  - Background worker tasks                │
├──────────────────┼──────────────────────────────────────────┤
│  Data Layer      │ PostgreSQL 16 (3 databases)              │
│                  │ Redis 7 (caching & queue)                │
└──────────────────┴──────────────────────────────────────────┘
```

### 1.2 Module Dependencies

```
vna-ux
  └── vna-main-server (API calls)

vna-main-server
  ├── vna-dicom-server (HTTP REST API)
  ├── vna-bids-server (HTTP REST API)
  ├── PostgreSQL (vna_main database)
  └── Redis (caching)

vna-dicom-server (Orthanc)
  ├── PostgreSQL (orthanc database)
  └── vna-main-server (webhook notifications via Lua)

vna-bids-server
  ├── PostgreSQL (bidsserver database)
  └── vna-main-server (sync notifications)
```

---

## 2. Configuration Consistency Issues

### 2.1 Environment Variable Inconsistencies

#### **[FIXED] CRITICAL: Database Configuration Mismatch**

**Issue:** The `.env` file and `docker-compose.yml` have inconsistent database configurations.

**Details:**
- **Root docker-compose.yml (line 43):** Uses `vna_main` database for main-server
  ```yaml
  DATABASE_URL: "postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/vna_main"
  ```

- **Root docker-compose.yml (line 106):** Uses `bidsserver` database for bids-server
  ```yaml
  DATABASE_URL: "postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/bidsserver"
  ```

- **vna-dicom-server/docker-compose.yml (line 7):** Uses `orthanc` database
  ```yaml
  POSTGRES_DB: ${POSTGRES_DB:-orthanc}
  ```

- **vna-bids-server/docker-compose.yml (line 9):** Uses `bidsserver` database with different credentials
  ```yaml
  POSTGRES_USER: bids
  POSTGRES_PASSWORD: bids
  POSTGRES_DB: bidsserver
  ```

**Impact:** 
- The standalone docker-compose files for individual services use different credentials than the main stack
- This creates confusion and potential deployment errors
- Developers testing individual services will have different auth than production

**Recommendation:**
1. Standardize all docker-compose files to use the same credential pattern
2. Use environment variable substitution consistently across all compose files
3. Document the credential strategy clearly

---

#### **[FIXED] CRITICAL: Orthanc PostgreSQL Configuration Hardcoded**

**Issue:** The Orthanc configuration file has hardcoded database credentials.

**File:** `vna-dicom-server/config/orthanc/orthanc.json` (lines 30-40)
```json
"PostgreSQL": {
  "Host": "postgres",
  "Port": 5432,
  "Database": "orthanc",
  "Username": "vna-admin",
  "Password": "vna-admin",
  ...
}
```

**Impact:**
- Credentials don't match environment variables
- Cannot be changed without rebuilding the Docker image
- Security risk in production

**Recommendation:**
1. Use environment variable substitution in Orthanc config
2. Generate orthanc.json at container startup from template
3. Never hardcode credentials in config files

---

### 2.2 Port Configuration Issues

#### **WARNING: Port Mapping Inconsistencies**

**Issue:** Different default ports between `.env` and `.env.example`

| Service | .env | .env.example | Difference |
|---------|------|--------------|------------|
| PostgreSQL | 18432 | 5432 | +13000 offset |
| Redis | 18379 | 6379 | +12000 offset |
| Main Server | 18000 | 8000 | +10000 offset |
| BIDS Server | 18080 | 8080 | +10000 offset |
| Orthanc HTTP | 18042 | 8042 | +10000 offset |
| Orthanc DICOM | 18242 | 4242 | +14000 offset |

**Impact:**
- Developers using `.env.example` will have conflicts with production ports
- Documentation must clarify port strategy
- Potential for accidental connection to wrong environment

**Recommendation:**
1. Document the port offset strategy clearly (appears to be for avoiding conflicts on shared hosts)
2. Consider using a single port prefix variable: `PORT_PREFIX=18` for production
3. Ensure all documentation references the correct ports

---

### 2.3 API Key Security Issues

#### **[FIXED] CRITICAL: Weak Default API Keys**

**Issue:** The `.env` file uses weak, predictable API keys.

```bash
VNA_API_KEY=vna-admin
BIDS_SERVER_API_KEY=vna-admin
BIDS_API_KEY=vna-admin
```

**Impact:**
- Major security vulnerability in production
- All services share the same weak key
- No rotation strategy documented

**Recommendation:**
1. Generate strong random keys for production (minimum 32 characters)
2. Use different keys for each service
3. Implement key rotation mechanism
4. Add validation to reject weak keys on startup
5. Document key management procedures

---

## 3. Database Architecture Review

### 3.1 Database Schema Consistency

#### **GOOD: Proper Database Separation**

The system correctly uses separate databases for different concerns:
- `vna_main`: Central index and coordination data
- `bidsserver`: BIDS-specific metadata and resources
- `orthanc`: DICOM image index and storage metadata

This separation provides:
- Clear data ownership boundaries
- Independent scaling possibilities
- Reduced cross-service coupling

---

#### **ISSUE: Missing Foreign Key Constraints**

**File:** `vna-main-server/vna_main/db/migrations/versions/0001_initial_schema.py`

The `resource_index` table has a foreign key to `patient_mapping`, but the relationship is nullable:

```python
sa.Column("patient_ref", sa.String(32), 
          sa.ForeignKey("patient_mapping.patient_ref", ondelete="SET NULL"), 
          nullable=True),
```

**Impact:**
- Orphaned resources can exist without patient references
- Data integrity depends on application logic
- Difficult to enforce patient-level access control

**Recommendation:**
1. Document the business logic for when patient_ref can be NULL
2. Consider adding a check constraint or application validation
3. Add database-level audit triggers for patient_ref changes

---

#### **ISSUE: Inconsistent Column Naming**

**Problem:** Different naming conventions across databases.

**vna_main database:**
- Uses `metadata` (with underscore in Python: `metadata_`)

**bidsserver database:**
- Uses `metadata` consistently
- Uses `search_vector` for full-text search

**Impact:**
- Developers must remember different conventions
- ORM mapping complexity
- Potential for bugs in cross-database queries

**Recommendation:**
1. Standardize on `metadata_` or `metadata` across all databases
2. Create a shared naming convention document
3. Use linter rules to enforce naming

---

### 3.2 Index Strategy Review

#### **GOOD: Comprehensive Indexing in BIDS Server**

**File:** `vna-bids-server/bids_server/db/migrations/versions/0001_initial_schema.py`

The BIDS server has excellent index coverage:
- Single-column indexes on foreign keys
- Composite indexes for common query patterns
- Indexes on search columns (content_hash, search_vector)

```python
op.create_index("idx_resources_composite", "resources", 
                ["subject_id", "session_id", "modality"])
```

---

#### **[FIXED] ISSUE: Missing Indexes in Main Server**

**File:** `vna-main-server/vna_main/db/migrations/versions/0001_initial_schema.py`

The main server schema lacks indexes on frequently queried columns:
- `resource_index.dicom_study_uid` - used for DICOM lookups
- `resource_index.bids_path` - used for BIDS lookups
- `sync_events.processed` - used for event processing
- `sync_events.source_db` - used for filtering

**Impact:**
- Slow queries as data volume grows
- Full table scans on critical operations
- Poor performance on sync event processing

**Recommendation:**
1. Add indexes on all foreign keys
2. Add composite index on `(source_db, processed, created_at)` for sync events
3. Add unique constraint on `resource_index.dicom_study_uid` where not null
4. Consider partial indexes for common query patterns

---

## 4. Inter-Module Communication Review

### 4.1 Sync Event Flow

#### **GOOD: Event-Driven Architecture**

The system uses an event-driven approach for synchronization:

```
Orthanc (Lua) ──webhook──> Main Server ──> Sync Event Queue
                                                    │
BIDS Server ──webhook──> Main Server ───────────────┘
                                                    │
                                         Background Processing
                                                    │
                                         Resource Index Update
```

**File:** `vna-main-server/vna_main/services/sync_service.py`

This design provides:
- Loose coupling between services
- Resilience to temporary failures
- Audit trail of all changes
- Ability to replay events

---

#### **[FIXED] ISSUE: Lua Script Incomplete**

**File:** `vna-dicom-server/config/orthanc/lua/sync_to_vna.lua`

The Lua script has a critical issue:

```lua
function OnStableInstance(modality, instanceId, tags, metadata)
    -- ...
    local success, result = pcall(function()
        return RestApiPost("/tools/json", jsonPayload)  -- WRONG ENDPOINT
    end)
```

**Problems:**
1. Posts to `/tools/json` instead of the main server sync endpoint
2. No authentication headers for the main server
3. No error handling or retry logic
4. Doesn't match the expected sync event format

**Expected endpoint:** Should post to `ORTHANC_TO_MAIN_URL` (from .env)

**Impact:**
- DICOM sync notifications don't reach main server
- Resource index won't be updated automatically
- Manual sync required

**Recommendation:**
1. Fix the endpoint URL to use environment variable
2. Add authentication header with DICOM_SERVER_USER/PASSWORD
3. Implement retry logic with exponential backoff
4. Add proper error logging
5. Test the complete flow end-to-end

---

### 4.2 HTTP Client Configuration

#### **GOOD: Connection Pooling**

**File:** `vna-main-server/vna_main/services/sync_service.py` (lines 24-32)

```python
async def get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(
            timeout=30.0,
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=100),
        )
    return _http_client
```

This is excellent practice for performance and resource management.

---

#### **[FIXED] ISSUE: Missing Authentication in HTTP Calls**

**File:** `vna-main-server/vna_main/services/sync_service.py`

When fetching data from DICOM server (line 240):
```python
resp = await client.get(f"{dicom_url}/studies/{orthanc_study_id}")
```

No authentication headers are sent, but Orthanc requires auth.

**Impact:**
- Requests will fail with 401 Unauthorized
- Sync processing will fail
- Fallback to payload data only

**Recommendation:**
1. Add authentication headers to all DICOM server requests
2. Use the configured DICOM_SERVER_USER and DICOM_SERVER_PASSWORD
3. Create a shared HTTP client factory that includes auth

---

### 4.3 Redis Integration

#### **GOOD: Optional Caching with Graceful Degradation**

**File:** `vna-main-server/vna_main/config/settings.py` (lines 31-35)

```python
REDIS_URL: str = field(default_factory=lambda: os.getenv("REDIS_URL", "redis://localhost:6379/0"))
REDIS_ENABLED: bool = field(default_factory=lambda: os.getenv("REDIS_ENABLED", "true").lower() == "true")
```

The system can operate without Redis, which is good for development and resilience.

---

#### **[FIXED] ISSUE: No Redis Password in Production Config**

**File:** `.env` (line 17)
```bash
REDIS_PASSWORD=
```

**Impact:**
- Redis is completely unprotected
- Anyone with network access can read/write cache
- Can poison cache to affect application behavior

**Recommendation:**
1. Set a strong Redis password in production
2. Use Redis ACLs if available (Redis 6+)
3. Consider TLS for Redis connections in production

---

## 5. DICOM & Medical Imaging Specific Review

### 5.1 DICOMweb Implementation

#### **GOOD: Standards-Compliant DICOMweb**

**File:** `vna-dicom-server/config/orthanc/orthanc.json`

```json
"DicomWeb": {
  "Enable": true,
  "Root": "/dicom-web/"
}
```

Orthanc provides a full DICOMweb implementation, which is the modern standard for medical image access.

---

#### **GOOD: Multiple Viewer Support**

The configuration enables multiple modern viewers:
- OHIF (DICOMweb-based, widely used)
- VolView (volume rendering)
- Orthanc Explorer 2 (built-in admin UI)

This provides flexibility for different use cases.

---

### 5.2 DICOM Tag Handling

#### **[FIXED] ISSUE: Limited Tag Extraction in Lua Script**

**File:** `vna-dicom-server/config/orthanc/lua/sync_to_vna.lua`

The script only extracts minimal tags:
```lua
patient_id = tags["PatientID"] or "",
study_uid = tags["StudyInstanceUID"] or "",
series_uid = tags["SeriesInstanceUID"] or "",
```

**Missing critical tags for medical imaging workflows:**
- `StudyDescription` - needed for clinical context
- `Modality` - needed for routing and processing
- `StudyDate` - needed for temporal queries
- `AccessionNumber` - needed for RIS/PACS integration
- `PatientName` - needed for display (with privacy considerations)

**Impact:**
- Limited search and filtering capabilities
- Cannot route studies based on modality
- Poor user experience without descriptive metadata

**Recommendation:**
1. Extract all relevant DICOM tags
2. Consider extracting private tags if institution-specific
3. Validate tag extraction with real clinical data
4. Handle character encoding properly (already set to Latin1)

---

### 5.3 Patient Privacy & HIPAA Considerations

#### **CRITICAL: No PHI Anonymization**

The system stores PatientID and PatientName without anonymization:
- `patient_mapping.hospital_id` stores raw PatientID
- Resource metadata includes patient name

**Impact:**
- Must be treated as PHI (Protected Health Information)
- Requires full HIPAA compliance measures
- Cannot be used for research without IRB approval
- Backup and logging must be secured

**Recommendation:**
1. Document PHI handling procedures
2. Implement audit logging for all PHI access
3. Consider adding anonymization/de-identification features
4. Ensure encryption at rest for all databases
5. Implement proper access controls and authentication
6. Add data retention policies

---

### 5.4 Storage Architecture

#### **GOOD: Separation of Index and Blob Storage**

Orthanc uses PostgreSQL for metadata and filesystem for DICOM files:
```json
"PostgreSQL": {
  "EnableIndex": true,
  "EnableStorage": true,  // Stores DICOM files in DB
}
```

Wait - this stores DICOM files in the database, which is not ideal for large datasets.

**Impact:**
- Database size grows rapidly with image data
- Backup times increase
- May hit PostgreSQL row size limits for large series

**Recommendation:**
1. Consider using filesystem storage for DICOM files: `"EnableStorage": false`
2. Use dedicated storage volumes for DICOM data
3. Implement tiered storage (hot/warm/cold) for older studies
4. Add storage quota management

---

## 6. Frontend Architecture Review

### 6.1 Technology Stack

**File:** `vna-ux/package.json`

**GOOD: Modern, well-chosen stack:**
- React 18 with TypeScript
- Vite for fast development
- TanStack Query for data fetching
- Zustand for state management
- Tailwind CSS for styling

This is a solid, production-ready frontend stack.

---

### 6.2 API Integration

#### **ISSUE: No API Client Configuration**

The frontend likely needs to know the main server URL, but there's no configuration file visible.

**Recommendation:**
1. Add environment configuration for API base URL
2. Use Vite's env variables: `VITE_API_URL`
3. Configure for different environments (dev/staging/prod)
4. Add API client with proper error handling

---

## 7. Deployment & Operations Review

### 7.1 Docker Configuration

#### **GOOD: Health Checks**

All services have proper health checks defined:
```yaml
healthcheck:
  test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
  interval: 5s
  timeout: 3s
  retries: 10
```

This enables proper orchestration and dependency management.

---

#### **ISSUE: No Resource Limits**

The docker-compose.yml has no resource limits (CPU, memory).

**Impact:**
- Services can consume unlimited resources
- No protection against runaway processes
- Difficult to plan capacity

**Recommendation:**
1. Add resource limits for all services
2. Set memory limits based on expected workload
3. Add CPU quotas for fair sharing
4. Document resource requirements

---

### 7.2 Logging & Monitoring

#### **ISSUE: No Centralized Logging**

No logging configuration visible for:
- Log aggregation
- Log rotation
- Structured logging format
- Log levels per service

**Recommendation:**
1. Add structured logging (JSON format) for production
2. Configure log rotation
3. Add log aggregation (ELK stack, Loki, etc.)
4. Set appropriate log levels per environment
5. Add request ID tracing across services

---

### 7.3 Backup Strategy

**File:** `scripts/backup.sh` exists but not reviewed in detail.

**Recommendations:**
1. Ensure backup includes all 3 databases
2. Backup Orthanc storage separately
3. Implement point-in-time recovery
4. Test backup restoration regularly
5. Document RPO (Recovery Point Objective) and RTO (Recovery Time Objective)

---

## 8. Code Quality & Best Practices

### 8.1 Dependency Management

#### **GOOD: Pinned Dependencies**

All requirements.txt files use exact version pinning:
```
fastapi==0.115.0
sqlalchemy[asyncio]==2.0.35
```

This ensures reproducible builds.

---

#### **ISSUE: Version Inconsistencies**

Different services use different versions of the same packages:

| Package | vna-main-server | vna-bids-server | vna-dicom-sdk |
|---------|-----------------|-----------------|---------------|
| httpx | 0.27.2 | 0.27.2 | >=0.25.0 |
| pydantic | 2.10.0 | 2.10.0 | >=2.0.0 |
| pytest | 8.3.0 | 8.3.0 | >=7.0.0 |

**Impact:**
- Potential for subtle bugs from version differences
- Security updates must be applied separately
- Larger Docker images

**Recommendation:**
1. Create a shared requirements-base.txt
2. Use constraints file for version management
3. Automate dependency updates with Dependabot

---

### 8.2 Error Handling

#### **GOOD: Custom Exception Hierarchy**

**File:** `vna-dicom-sdk/dicom_sdk/exceptions.py`

The DICOM SDK has a well-designed exception hierarchy for different error types.

---

#### **ISSUE: Silent Failures in Sync Service**

**File:** `vna-main-server/vna_main/services/sync_service.py` (lines 134-144)

```python
except Exception as exc:
    logger.warning("Failed to process sync event...", exc_info=True)
    errors.append({...})
    # Event is NOT marked as processed, will retry indefinitely
```

**Impact:**
- Failed events will retry forever
- No circuit breaker pattern
- Can block processing of other events

**Recommendation:**
1. Add max retry count to sync events
2. Implement dead letter queue for permanently failed events
3. Add circuit breaker for external service calls
4. Alert on high error rates

---

## 9. Security Review

### 9.1 Authentication & Authorization

#### **ISSUE: Inconsistent Auth Implementation**

- Main server: API key auth (VNA_API_KEY)
- BIDS server: API key auth (BIDS_API_KEY)
- Orthanc: Basic auth (DICOM_SERVER_USER/PASSWORD)
- No JWT or OAuth2 implementation
- No role-based access control (RBAC)

**Impact:**
- Limited access control granularity
- Cannot implement user-level permissions
- No audit trail at user level

**Recommendation:**
1. Implement proper OAuth2/OIDC for user authentication
2. Add RBAC for fine-grained permissions
3. Consider integrating with hospital LDAP/AD
4. Add API key rotation mechanism
5. Implement rate limiting per user/key

---

### 9.2 Network Security

#### **ISSUE: No TLS Configuration**

No TLS/SSL configuration visible for:
- Inter-service communication (HTTP)
- Database connections
- Redis connections
- DICOM DIMSE protocol

**Impact:**
- Data in transit is not encrypted
- Vulnerable to man-in-the-middle attacks
- Does not meet HIPAA requirements

**Recommendation:**
1. Enable TLS for all HTTP connections
2. Use TLS for PostgreSQL connections
3. Configure DICOM TLS (DICOM Part 15)
4. Use proper certificate management
5. Document security architecture

---

## 10. Performance Considerations

### 10.1 Database Connection Pooling

#### **GOOD: Configurable Pool Settings**

```bash
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20
DB_POOL_TIMEOUT=30
DB_POOL_RECYCLE=3600
```

These are reasonable defaults for moderate workloads.

---

### 10.2 Caching Strategy

#### **ISSUE: Limited Cache Utilization**

Redis is enabled but:
- No cache invalidation strategy documented
- No cache hit/miss metrics
- TTL is fixed (300 seconds)
- No cache warming strategy

**Recommendation:**
1. Document what is cached and why
2. Add cache metrics and monitoring
3. Implement smart cache invalidation
4. Consider different TTLs for different data types
5. Add cache warming on startup for hot data

---

## 11. Recommendations Summary

### Critical (Must Fix Before Production)

1. **Fix hardcoded credentials** in Orthanc config
2. **Generate strong API keys** for all services
3. **Fix Lua script** to properly notify main server
4. **Add authentication headers** to HTTP client calls
5. **Implement TLS** for all network connections
6. **Add database indexes** to main server schema
7. **Document PHI handling** and implement audit logging
8. **Set Redis password** in production

### High Priority

9. **Standardize database credentials** across all docker-compose files
10. **Implement proper error handling** with retry limits
11. **Add resource limits** to Docker containers
12. **Implement centralized logging**
13. **Add missing DICOM tags** to Lua script
14. **Create shared dependency management**

### Medium Priority

15. **Document port strategy** and environment setup
16. **Implement cache monitoring** and metrics
17. **Add API client configuration** to frontend
18. **Implement health check endpoints** for all services
19. **Add database migration validation** in CI/CD

### Low Priority (Nice to Have)

20. **Consider filesystem storage** for DICOM files
21. **Implement OAuth2/OIDC** for user authentication
22. **Add RBAC** for fine-grained permissions
23. **Implement tiered storage** for old studies
24. **Add OpenAPI documentation** for all APIs

---

## 12. Conclusion

The VNA server architecture demonstrates solid fundamentals with a clear microservices design, proper separation of concerns, and modern technology choices. The event-driven synchronization approach is well-suited for medical imaging workflows.

However, several critical issues must be addressed before production deployment, particularly around security (hardcoded credentials, missing TLS, weak API keys), configuration consistency, and the broken DICOM sync notification flow.

The system shows good understanding of medical imaging requirements (DICOMweb support, BIDS integration, patient mapping) but needs more attention to HIPAA compliance, PHI handling, and audit requirements.

With the recommended fixes, this would be a solid foundation for a production VNA system. The modular architecture allows for incremental improvements without major refactoring.

---

**Next Steps:**
1. Prioritize and schedule critical fixes
2. Create detailed implementation tickets for each recommendation
3. Set up security review with compliance team
4. Plan staged rollout with monitoring
5. Document deployment and operational procedures
