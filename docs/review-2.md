# VNA-Server Code Review — 2026-04-12

> Scope: Full codebase review of `devhliu/VNA-server` covering the main server, BIDS server, DICOM server, three SDKs, shared middleware, Docker infrastructure, and test suite.
>
> **Status: Items marked with [FIXED] have been addressed as of 2026-04-13.**

---

## Executive Summary

The VNA-Server project is a well-structured multi-service DICOM/BIDS archive system with clear separation between servers, SDKs, and infrastructure. However, the review identified **6 critical bugs**, **12 security vulnerabilities**, **15 performance bottlenecks**, and **significant code duplication** that should be addressed in priority order.

| Category | Critical | High | Medium | Low |
|----------|----------|------|--------|-----|
| Bugs     | 3        | 3    | 0      | 0   |
| Security | 4        | 4    | 4      | 0   |
| Performance | 2     | 5    | 8      | 0   |
| Code Quality | 0    | 4    | 8      | 5   |
| Architecture | 1    | 2    | 3      | 0   |

---

## 1. Critical Bugs

### 1.1 [FIXED] DICOM SDK: `ServerStatistics` missing fields — `AttributeError` at runtime

**Files:**
- `vna-dicom-sdk/dicom_sdk/models.py:74-82`
- `vna-dicom-sdk/dicom_sdk/client.py:935,1043`

`health_check()` and `get_metrics()` reference `stats.total_patients`, `stats.total_studies`, etc., but the `ServerStatistics` model only defines `count_studies`, `count_series`, `count_instances`. This will raise `AttributeError` at runtime.

**Fix:** Add the missing fields to `ServerStatistics` or fix the references to use the existing field names.

### 1.2 [FIXED] DICOM SDK: `get_patient` 404 check is unreachable dead code

**Files:**
- `vna-dicom-sdk/dicom_sdk/client.py:627-648`
- `vna-dicom-sdk/dicom_sdk/async_client.py:388`

`_request()` calls `_raise_for_status()` which raises `DicomNotFoundError` on 404. The subsequent `if response.status_code == 404: return None` is never reached. Callers expecting `None` on missing patients will get an exception instead.

**Fix:** Either catch `DicomNotFoundError` and return `None`, or add a `raise_for_status=False` parameter to `_request()`.

### 1.3 [FIXED] BIDS Server: UUID collision risk from 12-hex-char truncation

**File:** `vna-bids-server/bids_server/models/database.py:46`

Truncating UUIDs to 12 hex characters (48 bits) dramatically increases collision probability. With ~16M records, the birthday problem gives ~50% collision chance.

**Fix:** Use full UUID strings or at minimum 20+ hex characters.

---

## 2. Security Vulnerabilities

### 2.1 [FIXED] [CRITICAL] Timing attack on API key comparison

**File:** `vna-main-server/vna_main/api/deps/auth.py:31`

Standard string comparison (`!=`) is vulnerable to timing attacks. An attacker can brute-force the API key character by character by measuring response times.

**Fix:** Use `hmac.compare_digest(credentials.credentials, settings.VNA_API_KEY)` for constant-time comparison.

### 2.2 [FIXED] [CRITICAL] Hardcoded default credentials (user = password)

**File:** `docker-compose.yml:8-9,48-49,79-80,83`

Default `POSTGRES_USER` and `POSTGRES_PASSWORD` are both `vna-admin`. Same for DICOM server credentials. If deployed without overriding `.env`, the system runs with trivially guessable credentials.

**Fix:** Remove default values for passwords. Require explicit setting. Fail deployment if `POSTGRES_USER == POSTGRES_PASSWORD`.

### 2.3 [FIXED] [CRITICAL] Redis without authentication

**File:** `docker-compose.yml:21-34`

Redis is started with `redis-server --appendonly yes` but no `--requirepass`. The `REDIS_PASSWORD` env var is passed but never used by the server command.

**Fix:** Change command to `redis-server --appendonly yes --requirepass $$REDIS_PASSWORD` (using `$$` for docker-compose variable pass-through).

### 2.4 [FIXED] [CRITICAL] Internal error details leaked to clients

**File:** `vna-main-server/vna_main/main.py:107-113`

The global exception handler returns `str(exc)` in the `details` field, exposing stack traces, SQL queries, and internal state.

**Fix:** Return a generic message in production. Log the full exception server-side with the request ID for correlation.

### 2.5 [FIXED] [HIGH] Backup script copies `.env` unencrypted

**File:** `scripts/backup.sh:35`

`cp .env "${BACKUP_DIR}/.env"` copies all secrets into the backup directory without encryption.

**Fix:** Encrypt the `.env` backup or exclude it. At minimum, `chmod 600 "${BACKUP_DIR}/.env"`.

### 2.6 [FIXED] [HIGH] `X-Forwarded-For` trusted without validation

**File:** `vna-main-server/vna_main/api/middleware/rate_limit.py:53`

An attacker can spoof this header to bypass rate limiting or impersonate other IPs.

**Fix:** Only trust `X-Forwarded-For` from known proxy IPs. Add a `TRUSTED_PROXIES` configuration option.

### 2.7 [FIXED] [HIGH] Arbitrary `setattr` updates (mass assignment)

**Files:**
- `vna-main-server/vna_main/services/patient_service.py:129-131`
- `vna-main-server/vna_main/services/resource_service.py:168-172`
- `vna-main-server/vna_main/services/routing_rules_service.py:222-224`
- `vna-main-server/vna_main/services/project_service.py:57-59`
- `vna-main-server/vna_main/services/treatment_service.py:53-55`

All update methods use `setattr(obj, key, value)` with `hasattr` checks, allowing modification of any model attribute including relationships and internal fields.

**Fix:** Define explicit allowlists of updatable fields for each model:
```python
UPDATABLE_FIELDS = {"name", "status", "metadata_"}
for key, value in updates.items():
    if key in UPDATABLE_FIELDS:
        setattr(obj, key, value)
```

### 2.8 [FIXED] [HIGH] ReDoS via user-stored regex patterns

**File:** `vna-main-server/vna_main/services/routing_rules_service.py:54`

`re.match(target, str(value))` uses regex patterns from user-stored database data. A catastrophic backtracking pattern (e.g., `(a+)+`) can freeze the server.

**Fix:** Validate regex patterns on creation/update. Limit complexity or use `re.match` with a timeout wrapper.

### 2.9 [FIXED] [MEDIUM] Path traversal in DICOM proxy

**File:** `vna-main-server/vna_main/services/routing_service.py:58`

`proxy_to_dicom` constructs URLs via string interpolation. If `path` contains `../`, this could access unintended endpoints.

**Fix:** Validate/sanitize the path or use `urllib.parse.urljoin` for safe URL construction.

### 2.10 [FIXED] [MEDIUM] Client-provided request ID accepted without validation

**File:** `vna-main-server/vna_main/api/middleware/request_id.py:21`

A malicious client could inject very long IDs or format-breaking strings for log injection attacks.

**Fix:** Validate incoming request ID (max length, allowed characters) or always generate server-side.

### 2.11 [FIXED] [MEDIUM] Docker containers run as root

**Files:** `vna-main-server/Dockerfile`, `vna-bids-server/Dockerfile`

Neither Dockerfile includes a `USER` directive. All processes run as root inside the container.

**Fix:** Add non-root user:
```dockerfile
RUN useradd --create-home appuser
USER appuser
```

### 2.12 [MEDIUM] DICOM server credentials visible in process listings

**File:** `docker-compose.yml:83`

`ORTHANC__REGISTERED_USERS` interpolates credentials into an env var, visible via `ps aux` or `docker inspect`.

**Fix:** Use Docker secrets or a mounted config file with restricted permissions.

---

## 3. Performance Bottlenecks

### 3.1 [CRITICAL] HTTP client created per request — no connection pooling

**Files:**
- `vna-main-server/vna_main/services/routing_service.py:39,49,59,68`
- `vna-main-server/vna_main/services/webhook_service.py:181`
- `vna-main-server/vna_main/services/patient_sync_service.py:34,53,161`
- `vna-dicom-sdk/dicom_sdk/sync_watcher.py:40-57`

Every HTTP call creates a new `httpx.AsyncClient`, performing a full TLS handshake each time. Under load, this causes connection exhaustion and high latency.

**Fix:** Create a shared `httpx.AsyncClient` singleton (like `sync_service.get_http_client()`) and use it everywhere. Close it in the app lifespan.

### 3.2 [CRITICAL] N+1 query pattern in DICOM SDK `list_studies`

**Files:**
- `vna-dicom-sdk/dicom_sdk/client.py:565-580`
- `vna-dicom-sdk/dicom_sdk/async_client.py:346-357`

`list_studies()` makes 1 + N sequential HTTP requests (one to list IDs, then one per study). For 1000 studies, this is 1001 sequential requests.

**Fix:** Use Orthanc's `POST /tools/find` with `Expand: True` to get all details in one request. For the async version, use `asyncio.gather` with a semaphore for bounded concurrency.

### 3.3 [HIGH] Unbounded concurrent HTTP requests in sync service

**File:** `vna-main-server/vna_main/services/sync_service.py:596-597`

`asyncio.gather(*tasks)` fires all study detail requests simultaneously. Thousands of studies will overwhelm the DICOM server and exhaust connection limits.

**Fix:** Use `asyncio.Semaphore` to limit concurrency (e.g., 20 concurrent requests).

### 3.4 [HIGH] Blocking I/O in async methods

**Files:**
- `vna-bids-sdk/bids_sdk/client_async.py:124-125` — `open(path, "rb")` in async upload
- `vna-dicom-sdk/dicom_sdk/async_client.py:101` — `Path.read_bytes()` in async store
- `vna-bids-sdk/bids_sdk/client_async.py:205-210` — sync `f.write()` in async download
- `vna-bids-server/bids_server/core/storage.py` — sync file I/O in async handlers
- `vna-bids-server/bids_server/core/upload.py` — sync file I/O in async upload

Blocking I/O inside async methods defeats the purpose of async and blocks the event loop for the duration of the I/O operation.

**Fix:** Use `aiofiles` or `asyncio.to_thread()` for all file I/O in async methods.

### 3.5 [FIXED] [HIGH] Rate limit: 4 Redis round-trips per request

**File:** `vna-main-server/vna_main/api/middleware/rate_limit.py:66-71`

Four separate Redis commands (`zadd`, `zremrangebyscore`, `expire`, `zcard`) are executed per request.

**Fix:** Use a Redis pipeline to batch into a single round-trip.

### 3.6 [FIXED] [HIGH] In-memory metrics with unbounded growth

**File:** `vna-main-server/vna_main/services/monitoring_service.py:50-53`

`_metrics` and `_histograms` are `defaultdict(list)` that grow without bound. Over time, this consumes increasing memory.

**Fix:** Add a max size or TTL to metric storage, or use a circular buffer.

### 3.7 [HIGH] `create_snapshot` loads ALL resources into memory

**File:** `vna-main-server/vna_main/services/version_service.py:261-271`

No limit/offset on the query. For large datasets, this will consume significant memory.

**Fix:** Process in batches using `yield_per()` or limit the query.

### 3.8 [MEDIUM] Sequential patient sync

**File:** `vna-main-server/vna_main/services/patient_sync_service.py:78`

Each patient is synced one at a time, including HTTP calls for studies.

**Fix:** Process patients concurrently with `asyncio.Semaphore` for bounded parallelism.

### 3.9 [MEDIUM] `set_labels` deletes ALL and re-creates

**File:** `vna-main-server/vna_main/services/label_service.py:79-92`

Even for a single label change, all existing labels are deleted and re-created. This is O(n) delete + O(m) insert and creates 2x history entries.

**Fix:** Diff existing and new labels to only add/remove changed labels.

### 3.10 [MEDIUM] `clear_pattern` loads all keys into memory

**File:** `vna-main-server/vna_main/services/cache_service.py:90-97`

`scan_iter` then `delete(*)` loads all matching keys into memory before deleting.

**Fix:** Delete in batches using `SCAN` + `DELETE` chunks, or use `UNLINK` for non-blocking deletion.

### 3.11 [MEDIUM] BIDS client reads entire file into memory for upload

**File:** `vna-bids-sdk/bids_sdk/client.py:206-212`

Neuroimaging files can be multiple GB. Reading the entire file into memory is problematic.

**Fix:** Use streaming upload with httpx's `stream` parameter or the chunked upload path for large files.

### 3.12 [FIXED] [MEDIUM] Inline imports on every request

**Files:**
- `vna-main-server/vna_main/api/middleware/rate_limit.py:38,58`
- `vna-bids-server/bids_server/core/upload.py` (multiple)

Imports inside request handlers are executed on every request.

**Fix:** Move to module-level imports.

---

## 4. Error Handling Gaps

### 4.1 [FIXED] Cache falsy value bug

**Files:**
- `vna-main-server/vna_main/services/patient_service.py:36`
- `vna-main-server/vna_main/services/resource_service.py:53`

Using `if cached:` instead of `if cached is not None:` treats cached `0`, `False`, `""`, `[]` as cache misses.

**Fix:** Change all cache hit checks to `if cached is not None:`.

### 4.2 [FIXED] `assert` in production code

**File:** `vna-main-server/vna_main/services/sync_service.py:398`

`assert event.processed is False` can be disabled with `-O` flag. This is a data integrity check that should use a proper exception.

**Fix:** Replace with `if event.processed is not False: raise RuntimeError(...)`.

### 4.3 [FIXED] Inconsistent transaction management

**Files:**
- `vna-main-server/vna_main/services/sync_service.py:477`
- `vna-main-server/vna_main/services/patient_sync_service.py:144`

Some services call `commit()` while others use `flush()`. This can cause partial commits or double commits.

**Fix:** Standardize on `flush()` in services. Let the FastAPI dependency/caller manage `commit()`.

### 4.4 [FIXED] Lifespan does not handle `init_db()` failure

**File:** `vna-main-server/vna_main/main.py:44-60`

If `init_db()` raises, the exception propagates unhandled and the server may start in a broken state.

**Fix:** Wrap in try/except and re-raise with a clear startup failure message.

### 4.5 [FIXED] No error handling for Redis operations in rate limiter

**File:** `vna-main-server/vna_main/api/middleware/rate_limit.py:66-71`

If Redis is down, all requests get 500 errors.

**Fix:** Wrap Redis operations in try/except and fail-open (allow the request) or fail-closed based on configuration.

### 4.6 `json.loads` in CLI without error handling

**Files:**
- `vna-main-sdk/vna_main_sdk/cli.py:104,170-171,313,336,385`
- `vna-bids-sdk/bids_sdk/cli.py:93-94,230,233,361`

Invalid JSON from user input raises `json.JSONDecodeError` with no friendly message.

**Fix:** Wrap in try/except and provide user-friendly error messages.

### 4.7 [FIXED] `int()` conversions without error handling

**Files:**
- `vna-main-server/vna_main/config/settings.py:33`
- `vna-dicom-sdk/dicom_sdk/client.py:86,103-109`

Non-numeric env vars or DICOM tags cause `ValueError` with no context.

**Fix:** Wrap in try/except with clear error messages.

---

## 5. Code Duplication & Architecture

### 5.1 [CRITICAL] Sync/async client duplication across all 3 SDKs

**Files (total ~5000 lines duplicated):**
- `vna-main-sdk/vna_main_sdk/client.py` (962 lines) ↔ `client_async.py` (711 lines)
- `vna-bids-sdk/bids_sdk/client.py` (956 lines) ↔ `client_async.py` (587 lines)
- `vna-dicom-sdk/dicom_sdk/client.py` (1081 lines) ↔ `async_client.py` (683 lines)

The async client is almost a line-for-line copy of the sync client with only `await` differences. Any bug fix or feature must be applied twice.

**Fix:** Use a base mixin pattern or code generation. Define method signatures once and use a decorator/factory to create both sync and async variants. Libraries like `httpx` itself do this with shared `_client.py` logic.

### 5.2 Middleware duplicated between servers

**Files:**
- `vna-common/vna_common/middleware/` (canonical source, NOT installable)
- `vna-main-server/vna_main/api/middleware/` (copy)
- `vna-bids-server/bids_server/api/middleware/` (copy)

The `vna-common` directory exists but has no `__init__.py`, `pyproject.toml`, or `requirements.txt`. Both servers maintain their own copies.

**Fix:** Make `vna-common` a proper installable package with `pyproject.toml`. Both servers should depend on it via `vna-common = {path = "../vna-common"}`.

### 5.3 Duplicated CLI helpers

**Files:**
- `vna-main-sdk/vna_main_sdk/cli.py:23-31`
- `vna-bids-sdk/bids_sdk/cli.py:21-52`
- `vna-dicom-sdk/dicom_sdk/cli.py:24-48`

All three CLIs implement their own output formatting with nearly identical logic.

**Fix:** Extract into `vna-common` shared CLI utilities.

### 5.4 ORM models mixed with engine/session management

**File:** `vna-main-server/vna_main/models/database.py`

Lines 26-300 (ORM models) are mixed with lines 302-378 (engine/session management). This violates separation of concerns.

**Fix:** Split into `models/tables.py` (or `models/orm.py`) and `db/engine.py`.

### 5.5 Thread safety: engine creation race condition

**File:** `vna-main-server/vna_main/models/database.py:306-309`

Module-level globals `_engine`, `_session_factory` with `asyncio.Lock()`, but `get_engine()` and `get_session_factory()` are NOT protected by the lock. Concurrent calls can create multiple engines.

**Fix:** Protect `get_engine()` and `get_session_factory()` with the lock, or use a singleton pattern with proper async initialization.

---

## 6. Configuration & Dependency Issues

### 6.1 Settings: dataclass instead of pydantic BaseSettings

**File:** `vna-main-server/vna_main/config/settings.py:15-48`

Using a plain dataclass means no validation, no `.env` file support, no type coercion, and no schema generation.

**Fix:** Migrate to `pydantic-settings` `BaseSettings` for proper validation, `.env` support, and schema generation.

### 6.2 [FIXED] Inconsistent `requires-python` across SDKs

- `vna-main-sdk`: `>=3.10`
- `vna-bids-sdk`: `>=3.9`
- `vna-dicom-sdk`: `>=3.10`

**Fix:** Standardize on `>=3.10` for all SDKs.

### 6.3 [FIXED] Inconsistent `httpx` minimum version

- `vna-main-sdk`: `httpx>=0.27.0`
- `vna-bids-sdk`: `httpx>=0.25.0`
- `vna-dicom-sdk`: `httpx>=0.25.0`

**Fix:** Standardize on `httpx>=0.27.0`.

### 6.4 [FIXED] Test dependencies in production requirements

**Files:**
- `vna-main-server/requirements.txt:10-12`
- `vna-bids-server/requirements.txt:15-17`

`pytest`, `pytest-asyncio`, `pytest-cov` are in production requirements.

**Fix:** Move to `requirements-dev.txt` or `pyproject.toml [project.optional-dependencies]`.

### 6.5 [FIXED] Docker Python version mismatch

- `vna-main-server/Dockerfile`: `python:3.12-slim`
- `vna-bids-server/Dockerfile`: `python:3.11-slim`

**Fix:** Standardize on Python 3.12 across all Docker images.

### 6.6 [FIXED] Zero coverage threshold

**File:** `pytest.ini:7,21`

`cov-fail-under=0` means the test suite passes even with no coverage.

**Fix:** Set a meaningful threshold (e.g., `fail_under = 60` initially, increasing over time).

### 6.7 No resource limits in docker-compose.yml

None of the services define `mem_limit`, `cpus`, or `deploy.resources`.

**Fix:** Add resource limits to each service.

### 6.8 [FIXED] `test-e2e` uses fragile `sleep 15`

**File:** `Makefile:37`

Hard-coded sleep is unreliable. The `test-integration` target properly uses `wait-for-http.sh`.

**Fix:** Use the same `wait-for-http.sh` approach.

---

## 7. Type Safety & API Design

### 7.1 Inconsistent return types across SDKs

Many SDK methods return `dict[str, Any]` instead of typed Pydantic models:
- VNA Main: `list_patients`, `delete_resource`, `batch_label`, all version/monitoring/routing methods
- BIDS: `get_labels` returns `List[Dict[str, Any]]` instead of `List[Label]`
- DICOM: `health_check` returns `dict[str, Any]`

**Fix:** Define Pydantic models for all API responses.

### 7.2 Inconsistent error hierarchies

- VNA Main SDK: Single `VnaClientError`
- BIDS SDK: Full hierarchy (`BidsError`, `BidsAuthenticationError`, `BidsNotFoundError`, etc.)
- DICOM SDK: Full hierarchy (`DicomError`, `DicomAuthenticationError`, `DicomNotFoundError`, etc.)

**Fix:** Expand `VnaClientError` into a hierarchy matching the other SDKs, or create a shared base in `vna-common`.

### 7.3 Inconsistent client constructor signatures

- VNA Main: `base_url, api_key, timeout, verify_ssl`
- BIDS: `base_url, timeout, api_key, headers, verify_ssl` (different order)
- DICOM: `base_url, username, password, timeout, verify_ssl` (BasicAuth instead of Bearer)

**Fix:** Standardize parameter order and naming across all SDKs.

### 7.4 BIDS SDK uses legacy type hints

**File:** `vna-bids-sdk/bids_sdk/client.py:6-7`

Uses `Dict`, `List`, `Union` from `typing` instead of modern `dict`, `list`, `X | Y` syntax.

**Fix:** Standardize on Python 3.10+ type hints across all SDKs.

### 7.5 `Subject.hospital_ids` typed as `Any`

**File:** `vna-bids-sdk/bids_sdk/models.py:60`

Using `Any` defeats type checking. The default factory is `dict` but the field name suggests a list.

**Fix:** Type as `Optional[List[str]]` or `Dict[str, Any]` with appropriate default.

---

## 8. Dead Code & Minor Issues

### 8.1 Dead code: webhook queue system

**File:** `vna-main-server/vna_main/services/webhook_service.py:148`

`_queue` and `_worker_task` are initialized but never used.

**Fix:** Remove or implement the queue-based delivery system.

### 8.2 [FIXED] Anti-pattern: `__import__("json")`

**File:** `vna-main-server/vna_main/services/webhook_service.py:168`

Bypasses normal import mechanisms and confuses linters/security scanners.

**Fix:** Use `import json` at the top of the file.

### 8.3 Unused imports

- `vna-main-sdk/vna_main_sdk/client.py:7` — `datetime`, `timezone`
- `vna-main-sdk/vna_main_sdk/client_async.py:17-18` — `LabelHistoryEntry`
- `vna-dicom-sdk/dicom_sdk/client.py:9` — `urlencode`

**Fix:** Remove unused imports.

### 8.4 f-strings in logger calls

**File:** `vna-main-server/vna_main/services/sync_service.py:298,305`

Using f-strings defeats lazy evaluation — the string is computed even if the log level is disabled.

**Fix:** Use `%s` style formatting: `logger.warning("...: %s", repr(patient_id))`.

### 8.5 [FIXED] Duplicate `EXPOSE 8080` in BIDS Server Dockerfile

**File:** `vna-bids-server/Dockerfile:41,45`

**Fix:** Remove the duplicate.

### 8.6 [FIXED] Smoke test uses wrong port numbers

**File:** `scripts/smoke-compose.sh:58,76,84,92`

Hardcoded ports (5432, 8000, 8042, 8080) don't match docker-compose.yml mappings (18432, 18000, 18042, 18080).

**Fix:** Read port mappings from environment variables or docker-compose.yml.

---

## 9. Recommended Improvement Priority

### Phase 1 — Fix Critical Bugs & Security (Do First)

| # | Item | Impact |
|---|------|--------|
| 1 | Fix `ServerStatistics` missing fields | Runtime crash |
| 2 | Fix `get_patient` unreachable 404 | Wrong API behavior |
| 3 | Fix UUID truncation collision risk | Data corruption |
| 4 | Use `hmac.compare_digest` for API key | Credential theft |
| 5 | Remove default credentials | System compromise |
| 6 | Enable Redis authentication | Unauthorized access |
| 7 | Hide internal error details | Information disclosure |
| 8 | Fix arbitrary `setattr` mass assignment | Data tampering |

### Phase 2 — Performance (Do Next)

| # | Item | Impact |
|---|------|--------|
| 1 | Shared `httpx.AsyncClient` singleton | Latency, connection exhaustion |
| 2 | Fix N+1 in `list_studies` | Scalability |
| 3 | Add `asyncio.Semaphore` for bounded concurrency | Server overload |
| 4 | Fix blocking I/O in async methods | Event loop blocking |
| 5 | Batch Redis commands via pipeline | Per-request latency |
| 6 | Bound in-memory metrics growth | Memory leak |

### Phase 3 — Code Quality & Architecture

| # | Item | Impact |
|---|------|--------|
| 1 | Make `vna-common` installable package | Dedup middleware |
| 2 | Refactor sync/async client duplication | Maintenance burden |
| 3 | Migrate settings to pydantic BaseSettings | Validation, .env support |
| 4 | Standardize transaction management | Data consistency |
| 5 | Add type-safe return models to SDKs | Developer experience |
| 6 | Fix cache falsy value bug | Correctness |

### Phase 4 — Infrastructure & DevOps

| # | Item | Impact |
|---|------|--------|
| 1 | Add non-root user to Dockerfiles | Container security |
| 2 | Add resource limits to docker-compose | Reliability |
| 3 | Separate test/production dependencies | Image size, security |
| 4 | Standardize Python version in Docker | Consistency |
| 5 | Set meaningful coverage threshold | Quality gate |
| 6 | Fix smoke test port numbers | CI reliability |
| 7 | Encrypt `.env` in backups | Secret protection |

---

## 10. Positive Observations

- **Clear service separation:** Each server has its own database, Dockerfile, and API boundary.
- **Consistent SDK structure:** All three SDKs follow the same pattern (sync client, async client, models, exceptions, CLI).
- **Proper async database layer:** SQLAlchemy async sessions with `asyncpg` for PostgreSQL.
- **Alembic migrations:** Both servers use versioned database migrations.
- **Structured logging:** JSON logging with request ID tracing for observability.
- **API versioning middleware:** `X-API-Version` header for version management.
- **Rate limiting:** Per-IP rate limiting with Redis backend.
- **Health checks:** All services have health check endpoints and Docker healthchecks.
- **Backup script:** Automated backup for PostgreSQL, BIDS data, and configuration.
- **Orthanc Lua integration:** Clean integration pattern with `sync_to_vna.lua` for DICOM event propagation.
