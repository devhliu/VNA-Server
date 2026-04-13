# VNA Server Improvement Plan

> Generated: 2026-04-05
> Status: Phases 1-4 Complete, Phase 5 Pending

## Phase 1: Critical Fixes (Security + Core Functionality) ✅ COMPLETE

### 1.1 [CRITICAL] Backend: Auth bypass when no API key set ✅
- **Location**: `vna_main/config/settings.py`, `bids_server/config.py`
- **Fix**: Added `REQUIRE_AUTH` setting (default `true`), startup validation raises `RuntimeError` if no API key configured

### 1.2 [CRITICAL] Backend: CORS wildcard with credentials ✅
- **Location**: `bids_server/config.py:70`
- **Fix**: Changed default from `["*"]` to `[]` (empty list)

### 1.3 [CRITICAL] Backend: Path traversal risk ✅
- **Location**: `bids_server/core/storage.py:18-23`
- **Fix**: Added `resolve()` + `startswith()` validation, raises `ValueError` on traversal attempts

### 1.4 [CRITICAL] Frontend: No routing configured ✅
- **Location**: `vna-ux/src/App.tsx`, `Layout.tsx`
- **Fix**: Added `<BrowserRouter>`, `<Routes>`, `<Outlet>`, replaced `<a>` with `<Link>`

### 1.5 [CRITICAL] Frontend: Broken CSS in ViewerPage ✅
- **Location**: `vna-ux/src/pages/ViewerPage.tsx`
- **Fix**: Closed brackets to `h-[700px]` and `max-h-[600px]`

### 1.6 [CRITICAL] Frontend: File content never fetched ✅
- **Location**: `vna-ux/src/pages/ViewerPage.tsx`
- **Fix**: Added `useEffect` to fetch text/JSON content, added loading state

---

## Phase 2: High Priority - Frontend UX ✅ COMPLETE

### 2.1 Error boundaries ✅
- **Location**: `vna-ux/src/components/ErrorBoundary.tsx`
- **Fix**: Created class component with `getDerivedStateFromError`, wrapped App

### 2.2 Mutation error handling + toast ✅
- **Location**: `vna-ux/src/components/Toast.tsx`, `LabelsPage.tsx`
- **Fix**: Created toast system, added `onError` callbacks to all mutations

### 2.3 Delete confirmation dialog ✅
- **Location**: `vna-ux/src/pages/LabelsPage.tsx`
- **Fix**: Added inline confirmation bar before destructive delete action

### 2.4 Loading skeletons ✅
- **Location**: `DashboardPage.tsx`, `LabelsPage.tsx`, `ArchiveBrowserPage.tsx`
- **Fix**: Replaced `'...'` with `<Skeleton>` components everywhere

### 2.5 UI components used ✅
- **Location**: All pages
- **Fix**: Using `Button`, `Card`, `Skeleton`, `Table`, `Badge` from `components/ui/`

### 2.6 Toast/notification system ✅
- **Location**: `vna-ux/src/components/Toast.tsx`
- **Fix**: Custom toast provider with success/error/warning/info types, auto-dismiss

### 2.7 Mobile responsive sidebar ✅
- **Location**: `vna-ux/src/components/Layout.tsx`
- **Fix**: Separate mobile overlay sidebar + desktop collapsible sidebar, responsive breakpoints

### 2.8 iframe sandbox ✅
- **Location**: `vna-ux/src/pages/ViewerPage.tsx`
- **Fix**: Added `sandbox="allow-same-origin allow-scripts"`

### 2.9 All `any` types typed ✅
- **Location**: `api.ts`, `useSystemStatus.ts`, `DashboardPage.tsx`
- **Fix**: Added `ApiError` class, `ActivityEvent` interface, typed error handler

---

## Phase 3: High Priority - Backend ✅ COMPLETE

### 3.1 N+1 query problems ✅
- **Location**: `bids_server/api/objects.py`
- **Fix**: Moved batch query outside generator loop, uses `WHERE resource_id IN (...)`

### 3.2 Missing database indexes ✅
- **Location**: Both servers' models
- **Fix**: Added indexes on SyncEvent (processed, source_db), AuditLog (action, resource_type, actor, created_at), TreatmentEvent (patient_ref), WebhookDelivery (webhook_id), ConversionJob (task_id), WebhookDeliveryLog (subscription_id), ResourceVersion (resource_id, version_number)

### 3.3 NullPool DB issue ✅
- **Location**: `vna_main/db/session.py`
- **Fix**: Consolidated to re-export from `models/database.py` which uses `AsyncAdaptedQueuePool`

### 3.4 Webhook secrets exposed ✅
- **Location**: `vna_main/api/routes/webhooks.py`
- **Fix**: Removed `secret` field from create response

### 3.5 Inconsistent session management ✅
- **Location**: `bids_server/api/store.py`, `labels.py`, `annotations.py`
- **Fix**: Replaced manual `db_session_factory()` with shared `async_session()`

### 3.6 Duplicate DB session code ✅
- **Location**: `vna_main/db/session.py`
- **Fix**: Thin re-export module, canonical code in `models/database.py`

### 3.7 Missing unique constraints ✅
- **Location**: `vna_main/models/database.py`
- **Fix**: Added `unique=True` to `PatientMapping.hospital_id`, `RoutingRule.name`, `Project.name`

### 3.8 Label.resource_id NOT NULL ✅
- **Location**: `bids_server/models/database.py`
- **Fix**: Changed `nullable=True` to `nullable=False`

---

## Phase 4: Medium Priority - Frontend UX ✅ COMPLETE

### 4.1 Search/filter in archive browser ✅
- **Location**: `ArchiveBrowserPage.tsx`
- **Fix**: Added search input with real-time filtering via `useMemo`

### 4.2 Header title dynamic ✅
- **Location**: `Layout.tsx`
- **Fix**: Uses `useLocation()` + `pageTitleMap` to show current page name

### 4.3 Form validation + feedback ✅
- **Location**: `LabelsPage.tsx`
- **Fix**: Added placeholder text, loading state on submit button, toast feedback

### 4.4 Success feedback on create ✅
- **Location**: `LabelsPage.tsx`
- **Fix**: Toast notification on successful label creation

### 4.5 Activity list uses proper key ✅
- **Location**: `DashboardPage.tsx`
- **Fix**: Uses `event.id ?? event.timestamp` instead of array index

### 4.6 Auto-scale storage units ✅
- **Location**: `DashboardPage.tsx`
- **Fix**: `formatBytes()` function with B/KB/MB/GB/TB auto-scaling

### 4.7 Byte formatting in archive browser ✅
- **Location**: `ArchiveBrowserPage.tsx`
- **Fix**: Same `formatBytes()` utility

### 4.8 Error retry buttons ✅
- **Location**: All pages
- **Fix**: Added retry buttons on error states for all data fetching

### 4.9 Descriptive alt text on images ✅
- **Location**: `ViewerPage.tsx`
- **Fix**: Changed `alt=""` to `alt={resource.name}`

### 4.10 aria-label on delete button ✅
- **Location**: `LabelsPage.tsx`
- **Fix**: Added `aria-label={`Delete label ${label.name}`}`

---

## Phase 5: Medium Priority - Backend ⏳ PENDING

### 5.1 Inconsistent response formats
- **Location**: Multiple route files across both servers
- **Fix**: Define standard `ErrorResponse` model and use consistently

### 5.2 Missing pagination on list endpoints
- **Location**: `webhooks`, `alerts`, `subjects`, `sessions`, `tasks`
- **Fix**: Add `offset`/`limit`/`total` to all list responses

### 5.3 Blocking file I/O in async context
- **Location**: `bids_server/api/rebuild.py`, `modalities.py`, `core/storage.py`
- **Fix**: Use `aiofiles` and `asyncio.to_thread()` for `shutil`/`pathlib` operations

### 5.4 In-memory rate limiting
- **Location**: Both servers' `rate_limit.py`
- **Fix**: Use Redis-backed rate limiting

### 5.5 No global exception handler
- **Location**: Both servers' `main.py`
- **Fix**: Add `@app.exception_handler(Exception)` for consistent error format

### 5.6 Duplicated middleware code
- **Location**: Both servers share identical `rate_limit.py`, `api_version.py`, `request_id.py`, `logging.py`
- **Fix**: Extract to shared package

### 5.7 Missing DB cascades
- **Location**: `bids_server/models/database.py`
- **Fix**: Add `ondelete` to FK constraints

### 5.8 No Redis connection cleanup
- **Location**: `vna_main/main.py`
- **Fix**: Add `close_cache()` to lifespan shutdown

### 5.9 Fragile JSON-as-text search
- **Location**: `bids_server/api/query.py`
- **Fix**: Use PostgreSQL JSONB operators (`@>`, `->>`)

### 5.10 Upload size enforcement
- **Location**: `bids_server/api/store.py`
- **Fix**: Add middleware-level validation

---

## Summary

| Phase | Status | Items |
|-------|--------|-------|
| Phase 1: Critical | ✅ Complete | 6/6 |
| Phase 2: Frontend High | ✅ Complete | 9/9 |
| Phase 3: Backend High | ✅ Complete | 8/8 |
| Phase 4: Frontend Medium | ✅ Complete | 10/10 |
| Phase 5: Backend Medium | ⏳ Pending | 0/10 |

**Total: 33/43 items completed (77%)**
