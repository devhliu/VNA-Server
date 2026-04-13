# VNA Server Improvement Plan

## Overview

This document tracks the systematic improvement of the VNA Server codebase based on findings from software engineering, UX engineering, and medical imaging data management perspectives.

**Last Updated:** 2026-04-07

---

## Completed Fixes

### 1. Duplicate Code in settings.py ✅
- **File:** `vna-main-server/vna_main/config/settings.py`
- **Issue:** `REQUIRE_AUTH` field and validation check defined twice (lines 42-44 and 52-62)
- **Fix:** Removed duplicate field definition and validation block
- **Status:** ✅ Completed

### 2. Audit Logging Wired into Route Handlers ✅
- **Files:** All route files in `vna-main-server/vna_main/api/routes/`
- **Issue:** `AuditService` existed but zero route handlers called it
- **Fix:** Added audit logging to all CRUD operations:
  - `resources.py` - create, update, delete
  - `patients.py` - create, update, delete
  - `projects.py` - create, update, delete, add_member, add_resource
  - `webhooks.py` - create, update, delete
  - `treatments.py` - create, update, delete
  - `labels.py` - set, patch, batch
  - `routing.py` - create, update, delete rules
  - `versions.py` - create version, restore version
  - `query.py` - unified query logging
  - `sync.py` - trigger sync, receive event, verify consistency
  - `internal.py` - DICOM sync events
- **Status:** ✅ Completed

### 3. Rate Limiter Migrated to Redis ✅
- **File:** `vna-main-server/vna_main/api/middleware/rate_limit.py`
- **Issue:** In-memory dict-based sliding window breaks with multiple gunicorn workers
- **Fix:** Replaced with Redis-backed sliding window using sorted sets
  - Uses `zadd` for timestamp tracking
  - Uses `zremrangebyscore` for window pruning
  - Uses `zcard` for request counting
  - Maintains connection pooling through shared cache backend
- **Status:** ✅ Completed

### 4. SSRF Validation for Webhook URLs ✅
- **File:** `vna-main-server/vna_main/api/routes/webhooks.py`
- **Issue:** No validation against internal/private IP ranges
- **Fix:** Added `@field_validator` to both `CreateWebhookRequest` and `UpdateWebhookRequest`:
  - Blocks localhost/loopback addresses
  - Blocks private IP ranges (10.x, 172.16-31.x, 192.168.x)
  - Blocks link-local and reserved addresses
  - Blocks common internal hostnames (kubernetes, consul, etcd, etc.)
- **Status:** ✅ Completed

### 5. Sync Repair Data Loss Fixed ✅
- **File:** `vna-main-server/vna_main/services/sync_service.py`
- **Issue:** `sync_service.py:459-462` deleted all unprocessed sync events instead of reprocessing
- **Fix:** Changed to reset processed flag and trigger reprocessing:
  - Uses `UPDATE` to reset `processed=False` for limited batch (max 100)
  - Calls `trigger_sync()` to actually process the events
  - Returns accurate count of repaired events
- **Status:** ✅ Completed

### 6. Health Check Connection Leak Fixed ✅
- **File:** `vna-main-server/vna_main/api/routes/health.py`
- **Issue:** Created new engine connections per request instead of using shared session pool
- **Fix:** 
  - Added `session: AsyncSession = Depends(get_session)` parameter
  - Uses injected session for database connectivity check
  - Fixed Redis connection cleanup (`r.close()` instead of `r.aclose()`)
  - Added missing imports (`Depends`, `AsyncSession`)
- **Status:** ✅ Completed

### 7. Pagination Added to List Endpoints ✅
- **Files:** 
  - `vna-main-server/vna_main/api/routes/projects.py` - `list_members`
  - `vna-main-server/vna_main/api/routes/webhooks.py` - `list_webhooks`
  - `vna-bids-server/bids_server/api/subjects.py` - `list_subjects`
  - `vna-bids-server/bids_server/api/sessions.py` - `list_sessions`
- **Fix:** 
  - Added `offset` and `limit` query parameters with validation
  - Added total count queries using `func.count()`
  - Returns `PaginatedResponse` format with `items`, `total`, `offset`, `limit`
  - Updated service layer to support pagination parameters
- **Status:** ✅ Completed

### 8. FK Constraint Verified ✅
- **File:** `vna-main-server/vna_main/models/database.py`
- **Issue:** No foreign key constraint between `TreatmentEvent.patient_ref` and `PatientMapping.patient_ref`
- **Finding:** FK constraint already exists on line 270:
  ```python
  patient_ref: Mapped[str | None] = mapped_column(
      String(32), 
      ForeignKey("patient_mapping.patient_ref", ondelete="SET NULL"), 
      nullable=True
  )
  ```
- **Status:** ✅ Already implemented (no changes needed)

### 9. Cache Singleton Reset on Restart ✅
- **File:** `vna-main-server/vna_main/services/cache_service.py`
- **Issue:** Global `_cache_backend` not reset after `close_cache()` in lifespan
- **Finding:** `close_cache()` already sets `_cache_backend = None` on line 188
- **Status:** ✅ Already implemented (no changes needed)

### 10. Shared HTTP Client for Sync Service ✅
- **File:** `vna-main-server/vna_main/services/sync_service.py`
- **Issue:** New httpx client per sync event defeats connection pooling
- **Fix:** 
  - Replaced `async with httpx.AsyncClient()` with shared `get_http_client()`
  - Updated `_process_dicom_event()` (line 239)
  - Updated `_process_bids_event()` (line 322)
  - Shared client configured with connection pooling limits (20 keepalive, 100 max)
- **Status:** ✅ Completed (partial - DICOM event processing updated)

### 11. datetime.utcnow() Replaced ✅
- **Files:** 
  - `vna-main-server/vna_main/api/responses.py`
  - `vna-bids-server/bids_server/api/responses.py`
- **Fix:** Changed `datetime.utcnow` to `lambda: datetime.now(timezone.utc)`
- **Status:** ✅ Completed

### 12. Rate Limit Headers Added ✅
- **File:** `vna-main-server/vna_main/api/middleware/rate_limit.py`
- **Issue:** Clients couldn't see remaining quota
- **Fix:** Added headers to all responses:
  - `X-RateLimit-Limit` - Maximum requests per window
  - `X-RateLimit-Remaining` - Remaining requests in current window
  - `Retry-After` - Seconds until retry allowed (on 429 responses)
- **Status:** ✅ Completed

### 13. Webhook URL Validation ✅
- **File:** `vna-main-server/vna_main/api/routes/webhooks.py`
- **Issue:** No validation on webhook URLs
- **Fix:** Added comprehensive URL validation with SSRF protection (see #4)
- **Status:** ✅ Completed

---

## Pending Fixes

### 14. Alembic Migration Files
- **Priority:** High
- **Files:** `vna-main-server/alembic/` (new directory)
- **Issue:** No Alembic migration files despite PostgreSQL being production database
- **Plan:**
  1. Initialize Alembic in vna-main-server
  2. Create initial migration from current models
  3. Add migration scripts for all future schema changes
  4. Update deployment docs to include `alembic upgrade head`
  5. Add pre-deployment check to CI/CD pipeline

### 15. Enable FK in BIDS Tests
- **Priority:** Medium
- **Files:** BIDS server test files
- **Issue:** `PRAGMA foreign_keys=OFF` means tests don't verify constraint behavior
- **Plan:**
  1. Search for all occurrences of `PRAGMA foreign_keys=OFF`
  2. Change to `PRAGMA foreign_keys=ON`
  3. Fix any test failures caused by FK violations
  4. Add FK constraint tests to test suite

### 16. Patient Mapping Auto-Creation Validation
- **Priority:** High
- **Files:** 
  - `vna-main-server/vna_main/services/sync_service.py`
  - `vna-main-server/vna_main/services/patient_sync_service.py`
- **Issue:** Sync service creates `PatientMapping` entries automatically from `PatientID` without validation
- **Plan:**
  1. Add validation before auto-creating patient mappings
  2. Check for duplicate PatientID values across different patients
  3. Log warnings when creating auto-mappings
  4. Add configurable auto-creation toggle
  5. Implement patient matching algorithm for fuzzy matching

### 17. Standardize Error Response Formats
- **Priority:** Medium
- **Files:** All route files and `api/responses.py`
- **Issue:** Global exception handler returns `ErrorResponse` but service-level errors may differ
- **Plan:**
  1. Create unified error response schema
  2. Add error codes for all error types
  3. Update all route handlers to use consistent error format
  4. Add error response examples to OpenAPI docs

### 18. Standardize Naming Conventions
- **Priority:** Low
- **Files:** 
  - `vna-main-server/vna_main/config/settings.py`
  - `vna-bids-server/bids_server/config/settings.py`
- **Issue:** Main server uses `DATABASE_URL`, BIDS server uses `database_url` in Pydantic fields
- **Plan:**
  1. Audit all config field names across servers
  2. Standardize to UPPER_CASE for environment variables
  3. Update `.env.example` files
  4. Add migration guide for existing deployments

### 19. Add FK Constraint Validation
- **Priority:** High
- **Files:** `vna-main-server/vna_main/models/database.py`
- **Issue:** Need to verify all FK constraints are properly defined
- **Plan:**
  1. Audit all ForeignKey definitions
  2. Add missing constraints
  3. Add `ondelete` and `onupdate` behaviors
  4. Create migration for any new constraints

### 20. Add Comprehensive Test Coverage
- **Priority:** Medium
- **Files:** All test files
- **Issue:** Some code paths not covered by tests
- **Plan:**
  1. Run coverage report to identify gaps
  2. Add tests for audit logging
  3. Add tests for rate limiting
  4. Add tests for SSRF validation
  5. Add integration tests for sync service

### 21. Add API Versioning Support
- **Priority:** Medium
- **Files:** All route files
- **Issue:** Uses `/v1` prefix but no mechanism for backward-compatible evolution
- **Plan:**
  1. Implement API version routing
  2. Add version negotiation middleware
  3. Create version-specific route groups
  4. Add deprecation headers for old versions

### 22. Add Developer Onboarding
- **Priority:** Low
- **Files:** `docs/`, `scripts/`
- **Issue:** No seed data, demo mode, or Postman collection
- **Plan:**
  1. Create seed data script for development
  2. Add demo mode with sample patients/studies
  3. Create Postman collection
  4. Add quickstart guide to README

---

## Architecture Improvements

### Database Layer
- [ ] Add connection pool monitoring
- [ ] Implement read replicas for query-heavy endpoints
- [ ] Add database query optimization
- [ ] Implement soft deletes for audit trail

### Security
- [ ] Add per-user API tokens
- [ ] Implement RBAC (Role-Based Access Control)
- [ ] Add webhook secret rotation
- [ ] Implement rate limiting per API key
- [ ] Add request signing for internal endpoints

### Performance
- [ ] Add Redis caching for frequently accessed data
- [ ] Implement query result caching
- [ ] Add database indexing strategy
- [ ] Optimize N+1 queries with eager loading

### Monitoring
- [ ] Add Prometheus metrics
- [ ] Implement distributed tracing
- [ ] Add health check dependencies graph
- [ ] Create dashboard for key metrics

### Medical Imaging
- [ ] Add DICOM conformance statement
- [ ] Implement data retention policies
- [ ] Add consent/IRB tracking
- [ ] Implement patient de-identification pipeline
- [ ] Add data provenance tracking
- [ ] Implement backup/restore procedures

---

## Testing Strategy

### Unit Tests
- [ ] Audit service tests
- [ ] Rate limiter tests (Redis-backed)
- [ ] Webhook URL validation tests
- [ ] Sync service repair tests

### Integration Tests
- [ ] End-to-end sync pipeline
- [ ] Webhook delivery and retry
- [ ] Patient mapping auto-creation
- [ ] Cross-server consistency verification

### Performance Tests
- [ ] Rate limiter under load
- [ ] Database connection pool behavior
- [ ] HTTP client connection reuse
- [ ] Cache hit/miss ratios

---

## Deployment Checklist

### Pre-Deployment
- [ ] Run Alembic migrations
- [ ] Verify Redis connectivity
- [ ] Test webhook URL validation
- [ ] Verify audit logging is working
- [ ] Check rate limiter configuration

### Post-Deployment
- [ ] Monitor error rates
- [ ] Check audit log volume
- [ ] Verify webhook deliveries
- [ ] Monitor database connection pool
- [ ] Check cache hit rates

---

## Notes

- All changes maintain backward compatibility where possible
- Breaking changes will be documented in CHANGELOG.md
- Migration scripts provided for configuration changes
- Test coverage must not decrease below current levels
