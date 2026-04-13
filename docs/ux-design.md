# VNA Server Dashboard - UX Design & Architecture

## 1. Overview

This document defines the user interface, interaction design and technical architecture for the **VNA (Vendor Neutral Archive)** Server administration and research dashboard.

VNA is a standards-based, vendor neutral medical and scientific data archive system designed for long term retention, universal access, and interoperability of medical imaging and associated clinical data across healthcare and research environments.

### Core VNA Capabilities
- Vendor independent storage and retrieval of all medical data types
- Standards compliant DICOM, HL7, FHIR, and IHE interfaces
- Cross-modality, cross-institution data federation
- De-identification, anonymization and audit controls
- Format migration and long term data preservation
- Research export capabilities including BIDS dataset generation

### Supported Data Types
| Category | Supported Formats |
|----------|-------------------|
| **Medical Imaging** | DICOM (all SOP classes), NIfTI, NRRD, MINC, Analyze |
| **Scientific Imaging** | OME-TIFF, TIFF, JPEG 2000, PNG, BigTIFF, Zeiss CZI |
| **Clinical Documents** | PDF, CDA, HL7 messages, FHIR resources, DICOM SR |
| **Derived Data** | BIDS datasets, segmentations, annotations, analysis outputs |
| **Administrative** | Audit logs, consent records, study metadata, reports |

---

## 2. Core User Personas

| Persona | Role | Primary Goals |
|---------|------|---------------|
| **VNA Administrator** | System / PACS Admin | Monitor archive health, manage storage tiers, configure interfaces, audit access |
| **Clinical User** | Radiologist / Clinician | Query patient history, view studies, verify uploads, clinical review |
| **Research Coordinator** | Study Manager | Create research projects, apply de-identification, export datasets |
| **Research Scientist** | Data Analyst | Browse archived data, run cohort queries, export analysis ready data |
| **IT Operations** | DevOps | Monitor system performance, manage backups, capacity planning |
| **Compliance Officer** | Audit / Privacy | Review access logs, verify de-identification, ensure regulatory compliance |

---

## 3. Global Dashboard Layout

```
┌───────────────────────────────────────────────────────────────────────────┐
│ 🔍 Universal Search  ◼️ System Status  🔔 Alerts  ⚙️ Admin  👤 User Menu   │
├────────────┬──────────────────────────────────────────────────────────────┤
│            │                                                              │
│  📊 Dashboard                                                            │
│  📁 Archive Browser                                                      │
│  👥 Patient Index                                                        │
│  📋 Studies                                                              │
│  🧪 Research Projects                                                    │
│  ⚡ System Status                                                        │
│  📜 Audit Logs                                                           │
│  ⚙️ Administration                                                       │
│            │                                                              │
│  Sidebar   │                  Main Content Workspace                      │
│  (Fixed)   │                  (Responsive Grid Layout)                   │
│            │                                                              │
│            │                                                              │
└────────────┴──────────────────────────────────────────────────────────────┘
```

### Layout Principles
- **Data Density First**: Optimized for clinical and research workflows requiring high information density
- **Persistent Navigation**: Sidebar and header always visible for fast context switching
- **Progressive Disclosure**: Advanced functionality hidden by default
- **Single Click Access**: All primary functions reachable in maximum 2 clicks
- **Responsive Breakpoints**: Desktop (1200px+), Tablet (768-1199px), Mobile (<768px)

---

## 4. Page Structure & Features

### 4.1 Dashboard Overview (`/`)
**Default landing page - system health at a glance**

| Component | Purpose |
|-----------|---------|
| Service Health Cards | Real-time status for all VNA components: Main Server, DICOM Interface, Storage Tiers, Database, Work Queue |
| Archive Metrics | Total studies, patients, series, objects, storage utilization by tier |
| Ingest Pipeline | 24 hour graph of objects received, processed, completed, failed |
| Recent Activity Timeline | Last 25 system events: ingest, access, exports, errors |
| Quick Actions | Upload Study, Search Archive, View Jobs, System Alerts |
| Capacity Forecast | Storage growth trend and projected full date |

### 4.2 Archive Browser (`/archive`)
**Universal VNA content browser**
- Hierarchical navigation: Patient → Study → Series → Instance / Document / Derivative
- Multi-dimensional filtering: Modality, Date Range, Institution, Performing Physician, Labels, Tags, File Format
- View modes: List, Card, Thumbnail Grid, Timeline, Study Compare
- Bulk operations: Export, Label, Move Tier, Verify, Delete, Anonymize, Convert
- Integrated BIDS Server Document Viewer with native support for:
  - Medical Imaging: NIfTI, NRRD, DICOM
  - Documents: PDF, DOCX, ODT, Markdown
  - Scientific: JSON, YAML, CSV, TSV, PNG, JPEG, TIFF
  - BIDS Specific: sidecar files, event files, phenotype data
- Format agnostic: All data types displayed consistently with type specific actions

### 4.3 Patient Index (`/patients`)
- De-identified master patient index (MPI)
- Patient longitudinal timeline: all clinical events across all modalities and institutions
- Cross reference mapping: MRN, internal IDs, study identifiers
- Consent status and research eligibility indicators
- Access history and audit trail per patient

### 4.4 Studies (`/studies`)
- Complete study lifecycle management
- Study status tracking: Received → Processing → Verified → Archived
- DICOM header inspection and validation reports
- Associated documents, reports and derived data
- Study quality metrics and integrity verification

### 4.3 Labeling & Annotations (`/labels`)
**Central labeling system for all archive resources**
- Global label ontology management: create, edit, retire label definitions
- Hierarchical label trees, controlled vocabularies and value constraints
- Resource labeling interface: apply labels to patients, studies, series, files
- Bulk labeling operations across query result sets
- Label history and audit trail: who applied what label when
- Label based access controls and search filtering
- Export labels with BIDS datasets

### 4.4 Viewer Workspace (`/viewer`)
**Unified integrated viewer for all data types**
- Side-by-side multi view layout
- Synchronized viewports for correlating multiple modalities
- Overlay support for segmentations and region of interests
- Annotation drawing tools
- Measurement tools for distances, areas, volumes
- Persistent annotation storage linked to original resources

### 4.5 Research Projects (`/projects`)
- Isolated workspaces for research studies
- Cohort definition and query builder
- De-identification profile configuration
- BIDS export job monitoring
- Project member and permission management
- Project level label sets and annotations
- Project level audit logging

### 4.7 System Status (`/system`)
- Real-time service health dashboard
- Work queue monitoring and job management
- Storage tier utilization and performance metrics
- Network throughput and interface statistics
- Active connection monitoring

### 4.8 Audit Logs (`/audit`)
- Immutable centralized audit trail for all operations
- Filtering: User, Action, Object, Date Range, Outcome, Label changes
- Full text search across all log entries
- Compliance report generation
- Log export for regulatory purposes

### 4.9 Administration (`/admin`)
- User and role management
- Storage tier configuration
- DICOM interface settings
- De-identification rule management
- Retention policy configuration
- System backup and recovery status

---

## 5. Design System

### Visual Principles
1. **Functional Priority**: Interface optimized for task completion speed and accuracy
2. **High Legibility**: Contrast ratios meeting WCAG 2.1 AA for 8+ hour working sessions
3. **Consistent Interaction Patterns**: Same controls behave identically across all pages
4. **Low Cognitive Load**: Minimized visual noise, clear visual hierarchy
5. **Error Transparency**: All system failures clearly communicated with remediation steps
6. **Neutral Palette**: Avoided distracting colours except for status indication

### Colour Palette
| Role | Hex Code | Usage |
|------|----------|-------|
| Primary | `#0c4a6e` | Navigation, primary actions, brand identity |
| Success | `#065f46` | Healthy status, completed operations |
| Warning | `#92400e` | Pending operations, warnings, degraded performance |
| Danger | `#991b1b` | Critical errors, failed jobs, system alerts |
| Info | `#1e40af` | Informational status, progress indicators |
| Neutral 900 | `#0f172a` | Body text |
| Neutral 700 | `#334155` | Secondary text, labels |
| Neutral 300 | `#cbd5e1` | Borders, dividers |
| Neutral 100 | `#f1f5f9` | Card backgrounds, surface layers |

### Typography
- Primary font: Inter (system sans-serif fallback)
- Base size: 14px
- Line height: 1.5
- Font weights: 400 (body), 500 (labels), 600 (headings)
- Monospace: JetBrains Mono for logs, identifiers and technical data

---

## 6. Technical Architecture

### Frontend Stack
| Layer | Technology Selection |
|-------|----------------------|
| Framework | React 18 |
| Build Tool | Vite |
| UI Components | Radix UI Primitives + shadcn/ui |
| Styling | Tailwind CSS 3 |
| Server State | TanStack Query |
| Client State | Zustand |
| Data Tables | TanStack Table |
| Charts | Recharts |
| DICOM Viewer | OHIF Viewer integration |
| API Client | Auto-generated from OpenAPI schema |
| Authentication | JWT + HTTP Only Secure Cookies |

### System Integration Architecture

#### Verified Service Boundaries
```
┌──────────────────────────────────────────────────────────┐
│                     Dashboard UI                         │
└─────────────┬───────────────────────────┬────────────────┘
              │                           │
┌─────────────▼─────────────┐             │
│  vna-main-server          │             │
│  :8000                    │             │
│  ✅ Labels                │             │
│  ✅ Resource Index        │             │
│  ✅ Routing & Auth        │             │
└─────────────┬─────────────┘             │
              │                           │
┌─────────────▼─────────────┐   ┌─────────▼──────────────┐
│  vna-dicom-server         │   │  vna-bids-server       │
│  :8042 (Orthanc)          │   │  :8001                 │
│  ✅ All DICOM formats     │   │  ✅ NIfTI              │
│                           │   │  ✅ JSON sidecars      │
│                           │   │  ✅ Documents: PDF/DOCX │
│                           │   │  ✅ Annotations        │
│                           │   │  ✅ BIDS datasets      │
└───────────────────────────┘   └────────────────────────┘
```

#### Synchronization Architecture
```
                            ┌─────────────────────┐
                            │  vna-main-server    │
                            │  Source of Truth    │
                            └─────────┬───────────┘
                                      │
                    ┌─────────────────┴─────────────────┐
         Active Push  ▼                               ▼  Active Push
┌──────────────────────────┐            ┌──────────────────────────┐
│ vna-dicom-server         │            │ vna-bids-server          │
│                          │            │                          │
│ Passive Sync Polling     │            │ Passive Sync Polling     │
│ └─ Every 60 seconds      │            │ └─ Every 30 seconds      │
│                          │            │                          │
└──────────────────────────┘            └──────────────────────────┘
```

#### Synchronization Modes
1. **Active Push**: Main server notifies downstream services immediately on changes
2. **Passive Polling**: Downstream servers pull state changes on fixed intervals
3. **Eventual Consistency**: All services will converge on correct state, no transactional guarantees
4. **Idempotent Operations**: All synchronization operations are safely retryable

#### Request Routing Logic
- **Dashboard always talks to vna-main-server first**
- Main server routes requests transparently to appropriate backend service
- File streams are proxied directly without buffering
- Label operations are written to main server which synchronizes to both downstream servers
- All authentication is handled exclusively by main server
- Dashboard does not communicate directly with dicom or bids servers

### Data Flow Principles
- All server state managed exclusively via TanStack Query
- Automatic background data refresh for dynamic metrics
- Optimistic UI updates for user initiated actions
- Graceful degradation and retry logic for network failures
- Real-time updates via Server Sent Events (SSE)
- No local duplication of authoritative server state

---

## 7. Implementation Roadmap

### Phase 1: Core Monitoring & Status
✅ Dashboard overview page
✅ System health indicators
✅ Archive metrics and statistics
✅ Global navigation layout

### Phase 2: Viewer & Labeling System
⬜ BIDS Server unified document viewer
⬜ NIfTI, PDF, JSON, DOCX, PNG native renderers
⬜ Label ontology management interface
⬜ Resource labeling interface
⬜ Bulk labeling operations
⬜ Annotation drawing tools

### Phase 3: Archive Browsing
⬜ Archive browser interface
⬜ Patient index listing
⬜ Study and series views
⬜ Advanced search and filtering

### Phase 4: Data Management
⬜ DICOM metadata viewer
⬜ Bulk operations
⬜ Storage tier management
⬜ Study integrity verification

### Phase 4: Research Capabilities
⬜ Research project workspaces
⬜ Cohort query builder
⬜ BIDS export job management
⬜ De-identification configuration

### Phase 5: Administration & Compliance
⬜ Audit logging interface
⬜ User and permission management
⬜ System configuration panel
⬜ Compliance reporting tools

---

## 8. Accessibility & Compliance Standards
- WCAG 2.1 AA compliance
- Full keyboard navigation for all functions
- Screen reader optimized semantic markup
- No time limits on user operations
- Adjustable text sizing
- Reduced motion support
- All interactive elements have clear focus indicators

---

Document Version: 1.0
Last Updated: 2026-04-04
