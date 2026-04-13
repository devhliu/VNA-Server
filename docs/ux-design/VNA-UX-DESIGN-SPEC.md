# VNA Server UX Design Specification

> Document Version: 1.0
> Last Updated: 2026-04-05
> Target: VNA Server v1.0 Release

---

## 1. Design Principles

### 1.1 Core Values
- **Clarity first**: Information is presented in order of importance
- **Predictable**: Consistent patterns across all pages
- **Frictionless**: Minimum steps required for common actions
- **Reliable**: User always knows system state
- **Accessible**: All UI elements usable via keyboard and screen readers

### 1.2 Visual Language
| Property | Values |
|---|---|
| **Base Grid** | 8px units |
| **Border Radius** | 4px, 8px, 12px |
| **Elevation Levels** | flat, hover, raised, modal |
| **Spacing Units** | 4px, 8px, 12px, 16px, 20px, 24px, 32px, 48px |
| **Animation Speed** | 150ms (fast), 300ms (normal) |
| **Animation Easing** | `cubic-bezier(0.4, 0, 0.2, 1)` |

---

## 2. Layout System

### 2.1 Consistent Global Navigation

The header and sidebar are **persistent and identical across all pages**, providing consistent orientation.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ ☰  [VNA Server Logo]                                        [● System Online] │ ← Fixed Header (64px height)
├──────────┬──────────────────────────────────────────────────────────────────┤
│          │                                                                  │
│  FIXED   │                                                                  │
│ SIDEBAR  │                        PAGE CONTENT                              │
│  256px   │                                                                  │
│          │                                                                  │
│          │                                                                  │
│          │                                                                  │
│          │                                                                  │
└──────────┴──────────────────────────────────────────────────────────────────┘
```

#### Header Behaviour:
- Always visible, never scrolls out of view
- System title is always shown in top left
- System status indicator always in top right
- No page-specific modifications to header

### 2.2 Sidebar Navigation Structure
Fixed sidebar, always available, consistent order across all pages:

| Icon | Section | Description |
|---|---|---|
| 🏠 | **Dashboard** | System overview, metrics, service status, recent activity |
| 📂 | **Data Management** | Patient search, series browser, document repository |
| 🗂️ | **Archive Browser** | File system view of BIDS archive |
| 🏷️ | **Labels** | Classification labels management |
| 📊 | **System Status** | Performance metrics, health checks |
| 📜 | **Logs** | Audit logs, system events |
| ⚙️ | **Admin** | Configuration, settings, user management |

#### Sidebar Behaviour:
- Active page is always highlighted
- Hover states consistent for all items
- Collapsible to 64px icon-only mode on desktop
- Mobile uses overlay hamburger menu
- No navigation changes when navigating between pages

### 2.3 Responsive Breakpoints
| Breakpoint | Behaviour |
|---|---|
| < 640px | Mobile: Hamburger sidebar, full width cards, 1 column |
| 640px - 1024px | Tablet: Collapsible sidebar, 2 column grid |
| > 1024px | Desktop: Expanded sidebar, 4 column grid |

### 2.3 Content Area Structure
All pages follow this standard layout:
```
Page Content:
┌───────────────────────────────────────────────────────────────────┐
│  [Page Title]                                                      │ ← Title bar (64px)
├───────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Page Content                                                     │
│  (20px padding on all sides)                                      │
│                                                                   │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐    │
│  │     Card 1      │  │     Card 2      │  │     Card 3      │    │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘    │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                       Full Width Card                       │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                   │
└───────────────────────────────────────────────────────────────────┘
```

---

## 3. Page Designs

### 3.1 Dashboard Page

#### Layout:
```
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│  Total Studies   │ │  Total Patients  │ │  Storage Used     │ │  Active Jobs      │
│  [1,247]         │ │  [892]           │ │  [7.2 TB]         │ │  [5 / 5]          │
│  Icon + Metric   │ │  Icon + Metric   │ │  Icon + Metric   │ │  Icon + Metric   │
└──────────────────┘ └──────────────────┘ └──────────────────┘ └──────────────────┘

┌─────────────────────────────┐ ┌───────────────────────────────────────────────────┐
│  Service Status             │ │  Recent Activity                                  │
│  ● Database  Healthy        │ │  [⏱]  Study imported sub-00121  2 mins ago      │
│  ● DICOM     Healthy        │ │  [⏱]  Patient added sub-00120   5 mins ago      │
│  ● BIDS      Degraded       │ │  [⏱]  Annotation created        8 mins ago      │
│  ● Redis     Healthy        │ │  ...                                             │
└─────────────────────────────┘ └───────────────────────────────────────────────────┘
```

#### Card Specifications:
- Card width: 264px (desktop)
- Card height: 96px
- Icon circle: 40px x 40px / 20px icon
- Metric value: 24px / 700 weight
- Label: 12px / 500 weight / gray-600

---

### 3.2 Data Management Page

#### Layout:
```
┌───────────────────────────────────────────────────────────────────┐
│ 🔍 Patient ID / Name / MRN                                        │ ← Global Search bar
├───────────────────────────────────────────────────────────────────┤
│ Results: 127 patients                                             │
├───────────┬─────────────────┬───────────────┬─────────────────────┤
│ Patient   │ Studies         │ Last Visit    │ Actions             │
├───────────┼─────────────────┼───────────────┼─────────────────────┤
│ sub-0001  │ 7               │ 2026-03-15    │ [View] [Export]     │
│ sub-0002  │ 4               │ 2026-03-12    │ [View] [Export]     │
│ sub-0003  │ 12              │ 2026-03-10    │ [View] [Export]     │
│ ...       │ ...             │ ...           │ ...                 │
└───────────┴─────────────────┴───────────────┴─────────────────────┘
```

#### Patient View Flow:
1.  User searches patient ID/Name/MRN
2.  Results shown in patient table
3.  Clicking `[View]` opens patient detail page
4.  Patient detail shows all series and documents for that patient
5.  Clicking series opens corresponding viewer

---

### 3.3 Viewer Integration System

#### Universal Viewer Routing:
All content types open in a consistent viewer layout:

| File Type | Viewer |
|---|---|
| DICOM (.dcm) | OHIF DICOM Viewer (embedded iframe) |
| NIfTI (.nii / .nii.gz) | Three.js Volume Renderer |
| Images (.png / .jpg / .tiff) | Standard image viewer with zoom/pan |
| Documents (.pdf / .txt / .json / .csv) | Native browser renderer |

#### Standard Viewer Layout:
```
┌───────────────────────────────────────────────────────────────────┐
│ /path/to/file.ext                                  [Download] [✕] │ ← Viewer header
├───────────────────────────────────────────────────────────────────┤
│                                                                   │
│                                                                   │
│                                                                   │
│                              VIEWER                               │
│                                                                   │
│                                                                   │
│                                                                   │
└───────────────────────────────────────────────────────────────────┘
```

#### Viewer Behaviour:
- Opens in full screen modal overlay
- Consistent header with filename and close button
- Standard controls: zoom, pan, rotate, window/level
- Metadata panel available for all types
- Can navigate between series without closing viewer

#### Layout:
```
┌───────────────────────────────────────────────────────────────────┐
│ [Search] Filter...                                               │ ← Search bar
├───────────────────────────────────────────────────────────────────┤
│ 📁  sub-0001                                                     │
│ 📁  sub-0002                                                     │
│ 📁  sub-0003                                                     │
│    📁  ses-01                                                    │
│    📁  ses-02                                                    │
│       📁  anat                                                   │
│           📄  T1w.nii.gz                                         │
│           📄  T1w.json                                           │
│ 📁  sub-0004                                                     │
│ ...                                                              │
└───────────────────────────────────────────────────────────────────┘
```

#### Item Specifications:
- Row height: 44px
- Indentation: 24px per level
- Icon: 18px
- Selection: Full row highlight
- Hover: Subtle background change + cursor pointer

---

### 3.4 Archive Browser Page

#### Layout:
```
┌───────────────────────────────────────────────────────────────────┐
│ [Search] Filter...                                               │ ← Search bar
├───────────────────────────────────────────────────────────────────┤
│ 📁  sub-0001                                                     │
│ 📁  sub-0002                                                     │
│ 📁  sub-0003                                                     │
│    📁  ses-01                                                    │
│    📁  ses-02                                                    │
│       📁  anat                                                   │
│           📄  T1w.nii.gz                                         │
│           📄  T1w.json                                           │
│ 📁  sub-0004                                                     │
│ ...                                                              │
└───────────────────────────────────────────────────────────────────┘
```

#### Item Specifications:
- Row height: 44px
- Indentation: 24px per level
- Icon: 18px
- Selection: Full row highlight
- Hover: Subtle background change + cursor pointer

---

### 3.5 Labels Page

#### Layout:
```
[+ New Label]

┌───────────┬─────────────────┬───────────────┬─────────────────────┐
│ Label     │ Description     │ Usage Count   │ Actions             │
├───────────┼─────────────────┼───────────────┼─────────────────────┤
│ ● QC Pass │ Quality passed  │ 127           │ [Delete]            │
│ ● Raw     │ Unprocessed     │ 542           │ [Delete]            │
│ ● Process │ Processed       │ 89            │ [Delete]            │
│ ● Exclude │ Excluded        │ 12            │ [Delete]            │
└───────────┴─────────────────┴───────────────┴─────────────────────┘
```

#### Table Specifications:
- Row height: 52px
- Cell padding: 16px horizontal
- Color indicator: 16px circle
- Delete button: Ghost variant

---

### 3.5.1 Labeling System Extensions

#### Label Types & Hierarchy
```
┌───────────────────────────────────────────────────────────────────┐
│ 🏷️  Label Management                                              │
├───────────────────────────────────────────────────────────────────┤
│  [ System Labels ] 🔒  |  [ User Labels ] ✏️                      │
├───────────────────────────────────────────────────────────────────┤
│  ● Reviewed        (locked)    │  ● High Priority  (custom)      │
│  ● QC Failed       (locked)    │  ● Follow Up      (custom)      │
│  ● Imported        (locked)    │  ● Research Set   (custom)      │
│  ● Archived        (locked)    │  ● Needs Review   (custom)      │
├───────────────────────────────────────────────────────────────────┤
│  Scope:  [✓] Patient  [✓] Study  [ ] Series  [ ] File             │
└───────────────────────────────────────────────────────────────────┘
```

| Label Attribute | Specification |
|---|---|
| System Labels | Created by system, non-editable, non-deletable, padlock indicator |
| User Labels | User defined, editable colors/names, full permissions |
| Scope Levels | Patient / Study / Series / File granularity |
| Color Coding | 12 predefined accessible colors + custom hex input |

#### Bulk Label Operations
```
┌───────────────────────────────────────────────────────────────────┐
│ ✅  17 items selected                          [+ Add Label]  [- Remove Label] │
├───────────────────────────────────────────────────────────────────┤
│  [✓] sub-0001  [● QC Pass] [● Research]         [ View ] [ Export ] │
│  [✓] sub-0002  [● QC Pass]                       [ View ] [ Export ] │
│  [✓] sub-0003  [● Raw] [● Follow Up]             [ View ] [ Export ] │
│  ...                                                               │
├───────────────────────────────────────────────────────────────────┤
│  Label propagation:  □ Apply to child studies / series / files     │
└───────────────────────────────────────────────────────────────────┘
```

- Multi-select via checkboxes or shift-click range selection
- Bulk operations apply in background with progress indicator
- Filter panel includes "Has label" / "Does not have label" operators
- Propagation rules: parent labels cascade down unless explicitly overridden

#### Label Metadata
Every label entry stores:
- Creation timestamp & author user
- Last modification audit trail
- Usage count per entity type
- Full change history log
- Tagging origin (system / user / import)

---

### 3.5.2 Search System Extensions

#### Advanced Search Syntax
```
┌───────────────────────────────────────────────────────────────────┐
│ 🔍 patient:sub-00* modality:MR date:>2026-01-01 NOT label:Exclude │
├───────────────────────────────────────────────────────────────────┤
│  ✅ Field specific search                                         │
│  ✅ Boolean operators AND / OR / NOT                              │
│  ✅ Wildcards * ?                                                 │
│  ✅ Range operators > < >= <=                                     │
│  ✅ Exact match "quoted terms"                                    │
└───────────────────────────────────────────────────────────────────┘
```

Search input supports syntax highlighting with inline validation feedback.

#### Search Filters Panel
```
┌───────────────────┬───────────────────────────────────────────────┐
│                   │                                               │
│  Date Range       │  [ 2026-01-01 ]  to  [ 2026-04-05 ]          │
│  Modality         │  ▢ MR  ▢ CT  ▢ PET  ▢ X-Ray  ▢ Ultrasound    │
│  Labels           │  ● QC Pass  ● Raw  ☐ Process  ☐ Exclude       │
│  Status           │  ▢ Archived  ▢ Active  ▢ Processing           │
│  Study Type       │  ▢ Anatomical  ▢ Functional  ▢ Diffusion      │
│                   │                                               │
└───────────────────┴───────────────────────────────────────────────┘
```

All filters update results in real-time without page reload.

#### Search Results Behaviour
```
┌───────────────────────────────────────────────────────────────────┐
│  Results: 142 items    [ Relevance ▼ ]  [ Group by: Patient ]     │
├───────────────────────────────────────────────────────────────────┤
│  📁 sub-00121  [6 studies]  87% match                             │
│    📄 ses-01 T1w.nii.gz  **matching term highlighted**            │
│    📄 ses-02 FLAIR.nii.gz                                         │
│  📁 sub-00078  [3 studies]  72% match                             │
│  ...                                                              │
├───────────────────────────────────────────────────────────────────┤
│  [ Save Search ]  [ Clear Filters ]  ⬅️  Search history: [MR Brain] [QC Failed] │
└───────────────────────────────────────────────────────────────────┘
```

- Relevance ranking with confidence percentage
- Optional grouping by patient, study date, or modality
- Sort options: relevance, date, patient id, file size
- Saved searches stored per user profile
- 10 entry search history with clickable quick access

#### Real Time Search
- 200ms debounced search as you type
- Instant result preview in dropdown
- Matching terms highlighted in results
- Auto-complete suggestions for fields and values
- Keyboard navigation for search suggestions

---

### 3.6 Viewer Page

#### Layout:
```
┌───────────────────────────────────────────────────────────────────┐
│ /sub-0001/ses-01/anat/T1w.nii.gz                        [Download]│
├───────────────────────────────────────────────────────────────────┤
│                                                                   │
│                                                                   │
│                                                                   │
│                              [Viewer]                             │
│                                                                   │
│                                                                   │
│                                                                   │
└───────────────────────────────────────────────────────────────────┘
```

---

## 4. Interaction Patterns

### 4.1 Loading States
- Skeleton loaders match exact content shape
- Loading spinners only used for full page loads
- Skeletons have soft pulse animation
- No layout shift when content loads

### 4.2 Feedback States
| Action | Feedback |
|---|---|
| Success | Green toast, 2.5s duration |
| Error | Red toast, persistent until dismissed |
| Warning | Amber toast, 5s duration |
| Info | Blue toast, 3s duration |

### 4.3 Destructive Actions
- All delete operations require explicit confirmation
- Confirmation bar appears inline
- No modal dialogs for routine deletions

---

## 5. Accessibility

### 5.1 Required Standards
- All interactive elements have proper `aria-label`
- All images have descriptive alt text
- Minimum 4.5:1 text contrast ratio
- All buttons minimum 44px x 44px touch target
- Full keyboard navigation support
- Focus states visible on all interactive elements

### 5.2 Keyboard Shortcuts
| Shortcut | Action |
|---|---|
| `Alt + 1` | Dashboard |
| `Alt + 2` | Archive |
| `Alt + 3` | Labels |
| `Alt + /` | Search |
| `Escape` | Close dialog / cancel |

---

## 6. Implementation Status

✅ Specification complete and ready for implementation

Next steps:
1. Review and approval of this design
2. Implementation of design system components
3. Page layout updates
4. Responsive testing
5. Accessibility audit
