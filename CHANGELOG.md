# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [0.3.0] - 2026-04-01

### Added
- Phase 3: API versioning header middleware (`X-API-Version` on all responses)
- Phase 3: Rate limiting middleware (100 req/min per IP, disabled during tests)
- Phase 3: Request ID tracing middleware on both servers
- Phase 4: Structured JSON logging middleware (BIDS server, configurable via `LOG_FORMAT=json`)
- Phase 4: Docker multi-stage builds (main-server, bids-server)
- Phase 4: `pyproject.toml` for BIDS server package discovery
- BIDS server config: `log_level` and `log_format` settings

### Changed
- Main server: Registered `RequestIDMiddleware`, `APIVersionMiddleware`, `RateLimitMiddleware`
- BIDS server: Registered `RequestIDMiddleware`, `APIVersionMiddleware`, `RateLimitMiddleware`
- BIDS server: JSON logging enabled via `settings.log_format == "json"`
- Makefile: Added `vna-bids-server` to `lint` and `fmt` targets
- Dockerfiles: Multi-stage builds separate builder (gcc/libpq-dev) from runtime

## [0.2.0] - 2026-04-01

### Added
- Phase 2: Project management (CRUD, members, resources)
- Phase 2: Treatment timeline (CRUD, patient timeline view)
- Phase 2: Audit log API with filtering
- Phase 2: BIDS dataset, session, and conversion job models
- Phase 2: Alembic migration for new tables (0002)
- Phase 2: Test coverage infrastructure (pytest-cov)
- Phase 2: Root README, CONTRIBUTING, CHANGELOG documentation
- 54 unit tests for main server (health, patients, resources, labels, sync, versions, monitoring, query, auth)

## [0.1.0] - 2026-03-31

### Added
- Phase 0: Error handling hardening (specific exceptions, structured logging)
- Phase 0: Security hardening (CORS config, credential parameterization)
- Phase 1: Orthanc integration (Lua callbacks, DICOM sync endpoint)
- Phase 1: Sync pipeline (event-driven Orthanc → Main → BIDS)
- Phase 1: BIDS task execution (convert/analyze/export with progress)
- Phase 1: Webhook delivery with retry
- Phase 1: Alembic migrations (initial schema, 10 tables)
- Phase 1: Docker Compose stack with healthchecks
- Phase 1: Smoke test script and Makefile targets

### Fixed
- DICOM SDK: `except Exception` blocks narrowed to specific types
- BIDS SDK: Label serialization unified to JSON array format
- Main SDK: Error handling improved
- All servers: Bare `pass` statements replaced with logger.debug
- All routes: DB session unified to `get_session` from models.database
