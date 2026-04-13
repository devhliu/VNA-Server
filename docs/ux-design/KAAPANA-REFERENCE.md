# KAAPANA Reference Implementation Notes

This document outlines the Kaapana UX patterns that will be adopted into the VNA Server design.

---

## 1. Gallery View (Adopted from Kaapana)

### Layout
```
┌─────────────────────────────────────────────────────────────────────────────┐
│ [Dataset: Default]  [Create Dataset]  [Add to Dataset]  [Run Workflow]       │ ← Dataset Bar
├─────────────────────────────────────────────────────────────────────────────┤
│ 🔍 [Search...]   [Filter: Modality] [Filter: Date] [Filter: Tags]            │ ← Search Bar
├─────────────────────────────────────────────────────────────────────────────┤
│ ▢ T1 Brain  ▢ T2 FLAIR  ▢ CT Chest  ▢ + Add Tag      [ Tag Mode: Single ]    │ ← Tag Bar
├─────────────────┬───────────────────────────────────────────────────────────┤
│                 │                                                           │
│ Metadata        │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│ Dashboard       │  │          │ │          │ │          │ │          │       │
│ (Sidebar)       │  │   Card   │ │   Card   │ │   Card   │ │   Card   │       │
│ 150px           │  │          │ │          │ │          │ │          │       │
│                 │  └──────────┘ └──────────┘ └──────────┘ └──────────┘       │
│                 │                                                           │
│                 │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│                 │  │          │ │          │ │          │ │          │       │
│                 │  │   Card   │ │   Card   │ │   Card   │ │   Card   │       │
│                 │  │          │ │          │ │          │ │          │       │
│                 │  └──────────┘ └──────────┘ └──────────┘ └──────────┘       │
│                 │                                                           │
└─────────────────┴───────────────────────────────────────────────────────────┘
```

### Kaapana Gallery Patterns:
1.  **Card based layout**: Thumbnail + metadata cards in grid
2.  **Multi selection**: CTRL/CMD click, shift click, drag select
3.  **Bulk operations**: All actions apply to selection
4.  **No active selection = select all**: Critical UX pattern
5.  **Selection count indicator**: Always visible
6.  **Lazy loading**: Virtual scrolling for large datasets
7.  **Thumbnail generator**: 128x128 thumbnails for all DICOM series

---

## 2. Tagging System (Exact Kaapana Behaviour)

### Tag Bar Pattern
```
┌─────────────────────────────────────────────────────────────────────────────┐
│ ▢ T1 Brain  ▢ T2 FLAIR  ▢ CT Chest  ▢ + Add Tag      [ Tag Mode: Single ]    │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Kaapana Tagging Rules:
✅  **Toggle active tags**: Click tag to activate
✅  **One click apply**: Click any item to apply active tag
✅  **Toggle off**: Click already tagged item to remove tag
✅  **Multi tag mode**: Toggle button to apply multiple tags at once
✅  **Keyboard shortcuts**: 1/2/3/4/5 toggle first 5 tags
✅  **Autocomplete**: Free text tag entry with existing tag suggestions
✅  **No save button**: Tags applied instantly
✅  **Visual indication**: Tagged items have tag badge overlay

---

## 3. Search & Filtering

### Kaapana Search Syntax (Lucene Compatible):
| Operator | Usage |
|---|---|
| `*` | Wildcard: `LUNG*` |
| `-` | Exclude: `-CHEST` |
| `:` | Field search: `modality:MR` |
| `AND` / `OR` | Boolean operators |
| `"` | Exact match: `"T1 Weighted"` |

### Filter Bar Pattern
```
┌─────────────────────────────────────────────────────────────────────────────┐
│ 🔍 patient:sub-00* modality:MR -label:Exclude                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Selection Model

### Critical Kaapana UX Principle:
> If no items are explicitly selected, ALL filtered items are implicitly selected for all operations.

This is the single most important UX pattern adopted from Kaapana. There is no "select all" button. Users learn intuitively that empty selection = select all.

---

## 5. Side Panel Viewer

### Kaapana Detail View Pattern
```
┌───────────────────────────────────────────────────────────────────┐
│ /path/to/series                                  [Download] [✕] │
├──────────────────────┬────────────────────────────────────────────┤
│                      │                                            │
│ OHIF DICOM Viewer    │  Metadata Table                            │
│ 60% width            │  40% width                                │
│                      │                                            │
│                      │  Patient ID:    sub-001                    │
│                      │  Study Date:    2026-03-15                │
│                      │  Modality:      MR                         │
│                      │  Series Desc:   T1 MPRAGE                  │
│                      │                                            │
└──────────────────────┴────────────────────────────────────────────┘
```

---

## 6. Implementation Roadmap

| Priority | Feature | Timeline |
|---|---|---|
| 🔴 High | Gallery card view | Next |
| 🔴 High | Kaapana selection model | Next |
| 🔴 High | One click tagging system | Next |
| 🟡 Medium | Metadata dashboard sidebar | After |
| 🟡 Medium | Lucene search syntax | After |
| 🟡 Medium | Side panel viewer | After |
| 🟢 Low | Virtual scrolling | Later |

---

## 7. Differences from Original VNA Design:

| Original VNA Design | Kaapana Pattern |
|---|---|
| Table view only | Card gallery view primary, table view optional |
| Checkbox selection only | No checkboxes, click to select |
| Explicit select all button | Implicit select all when none selected |
| Multi step tagging | One click tagging |
| Server side pagination | Lazy loaded virtual scrolling |

This reference document will guide the UI implementation.
