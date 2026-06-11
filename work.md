# ⚽ Football Analytics Dashboard — Completed Work Log

> **Project:** Football Analytics Dashboard (Streamlit + SQLite + Python)
> **Total Work Sessions:** 1 major session across 2 conversations
> **Status:** ✅ Production Ready

---

## 📊 Summary

| Category | Count |
|---|---|
| Python files created | 11 |
| Screens / Pages built | 5 |
| Core modules built | 6 |
| Premium visualizers added | 4 |
| Bugs fixed | 6 |
| UI redesigns completed | 1 |
| Commands run | 12+ |
| Total lines of code written | ~2,500+ |

---

## ✅ WORK #1 — Project Foundation & Dependency Setup

**Status:** Done  
**Description:** Read and interpreted `DEVELOPMENT.md` spec fully. Created the `requirements.txt` and installed all Python dependencies.

**Files Created/Modified:**
- `requirements.txt` — Dependencies: `streamlit>=1.35.0`, `pandas>=2.0.0`, `numpy>=1.24.0`, `plotly>=5.18.0`, `openpyxl>=3.1.0`, `xlsxwriter>=3.1.0`

**Commands Run:**
```bash
pip install -r requirements.txt --quiet
```

---

## ✅ WORK #2 — `utils.py` — Helper Functions

**Status:** Done  
**Description:** Built utility functions used across the entire project.

**File:** `utils.py` (2,391 bytes)

**Functions Implemented:**
- `parse_goal_timings(timing_str)` — Converts `"37,90'4,49,88"` → `[37, 94, 49, 88]` (handles extra-time notation like `90'4` → 94)
- `get_half(minute)` — Returns `"1H"` / `"2H"` based on minute
- `format_pct(value)` — Formats float as percentage string
- `format_roi(value)` — Formats ROI with `+/-` prefix

---

## ✅ WORK #3 — `database.py` — SQLite Database Layer

**Status:** Done  
**File:** `database.py` (10,211 bytes)

**Tables Created:**
| Table | Purpose |
|---|---|
| `matches` | All match data with 60+ columns |
| `saved_filters` | User-saved filter presets (JSON) |
| `exports_log` | History of Excel exports |
| `upload_log` | Track uploaded CSV/Excel files |

**Functions Implemented:**
- `init_db()` — Creates all 4 tables if they don't exist
- `get_connection()` — Returns SQLite connection with `Row` factory
- `get_all_matches(filters)` — Returns filtered match DataFrame
- `get_saved_filters()` / `save_filter()` / `delete_filter()` — CRUD for saved filters
- `log_export()` / `log_upload()` — Audit logging

---

## ✅ WORK #4 — `data_loader.py` — CSV/Excel Ingestion

**Status:** Done  
**File:** `data_loader.py` (12,704 bytes)

**Features:**
- Accepts both `.csv` and `.xlsx` uploads
- 66-column normalization map (Italian and English column names)
- Duplicate detection — skips rows already in DB
- Automatically calls `parse_goal_timings()` to parse timing columns
- Inserts clean rows into `matches` table via `database.py`

**Key Function:** `load_csv(uploaded_file, league, season)` → returns `(inserted_count, skipped_count)`

---

## ✅ WORK #5 — `calculations.py` — Analytics Engine

**Status:** Done  
**File:** `calculations.py` (13,179 bytes)

**Implemented Calculations:**
| Metric Group | Details |
|---|---|
| Goal timing buckets | 1–15, 16–30, 31–45, 46–60, 61–75, 76–90 |
| Over/Under % | Over 0.5, 1.5, 2.5, 3.5 goals |
| BTTS % | Both Teams To Score |
| HT/FT combos | 9 result combinations |
| ROI Simulations | 4 strategies: Over 2.5, BTTS, Home Win, Away Win |
| Live reconstruction | Given score at minute X, reconstruct outcomes |
| H2H analysis | Head-to-head win/draw/loss, goal averages |
| Pattern insights | Streaks, form comparison, database cross-comparison |

---

## ✅ WORK #6 — `filters.py` — Sidebar Filters

**Status:** Done  
**File:** `filters.py` (10,629 bytes)

**Filter Controls Implemented:**
- League selector (multiselect)
- Season selector (multiselect)
- Home Team / Away Team selectors
- Date range picker
- Home Goals / Away Goals range sliders
- HT Result filter
- Result filter (Home Win / Draw / Away Win)
- Over/Under threshold slider
- "Salva filtri" (Save filter) button integration

**Output:** Returns a structured `dict` of filter values applied to DataFrame via `apply_filters(df, filters)`

---

## ✅ WORK #7 — `app.py` — Main Entry Point & Navigation

**Status:** Done  
**File:** `app.py` (7,665 bytes)

**Features:**
- `st.set_page_config()` with dark theme and ⚽ icon
- Global dark CSS injected via `st.html()` (safe, no React conflicts)
- Custom sidebar navigation using `st.sidebar.radio()` with 6 pages:
  1. 📊 Prematch Analysis
  2. 🔴 Live Analysis
  3. ⚔️ Testa a Testa (H2H)
  4. 🔍 Pattern Explorer
  5. 💾 Filtri Salvati
  6. 📤 Upload Dati
- Upload Dati page built inline in `app.py`:
  - `st.file_uploader` for CSV/Excel
  - League and Season `st.text_input` fields (with unique `key=` values)
  - Calls `data_loader.load_csv()` with success/error feedback

---

## ✅ WORK #8 — `screens/prematch.py` — Prematch Analysis Screen (v1)

**Status:** Done (later fully redesigned — see Work #14)  
**Description:** Initial Prematch Analysis screen with 16 KPI cards, ROI table, 2 Plotly charts, and Excel export.

---

## ✅ WORK #9 — `screens/live.py` — Live Analysis Screen

**Status:** Done  
**File:** `screens/live.py` (7,362 bytes)

**Features:**
- Input: Current score at current minute
- Output: Historical matches in the same state, projected outcomes
- 2 Plotly charts: outcome distribution, goal timing post-state
- Excel export via `st.download_button` (eager generation, no double-button bug)

---

## ✅ WORK #10 — `screens/h2h.py` — Head-to-Head Screen

**Status:** Done  
**File:** `screens/h2h.py` (5,828 bytes)

**Features:**
- Team A vs Team B selector
- Win / Draw / Loss metric cards
- Last 10 meetings table
- 4 aggregate stats (goals, BTTS, Over 2.5, HT result)
- 2 Plotly charts: result distribution pie + goal trend line

---

## ✅ WORK #11 — `screens/patterns.py` — Pattern Explorer Screen

**Status:** Done  
**File:** `screens/patterns.py` (11,827 bytes)

**Features:**
- Prematch pattern stats per team
- DB comparison (team vs all DB averages)
- Compare Mode: Team A vs Team B side-by-side
- Sparkline-style mini charts
- ROI table with color-coded cells
- Excel export via `st.download_button`

---

## ✅ WORK #12 — `screens/saved_filters.py` — Saved Filters Manager

**Status:** Done  
**File:** `screens/saved_filters.py` (6,935 bytes)

**Features:**
- Card layout showing all saved filters
- Apply filter → jumps to Prematch with pre-filled filters
- Edit → opens edit form inline
- Delete → removes from DB with confirmation
- Create new filter form at bottom

---

## ✅ WORK #13 — Folder Architecture Fix (pages → screens)

**Status:** Done  
**Problem:** Streamlit auto-detects a `pages/` folder and injects its own navigation, causing duplicate sidebar menus.  
**Fix:** Renamed `pages/` → `screens/`, updated all imports in `app.py` and all screen files to `from screens.X import render`.

---

## ✅ WORK #14 — Bug Fix: React `removeChild` DOM Error

**Status:** Done  
**Error:** `NotFoundError: Failed to execute 'removeChild' on 'Node'`  
**Root Cause:** Using `st.markdown("<style>...</style>", unsafe_allow_html=True)` caused React's virtual DOM to lose track of injected nodes during rerenders.  
**Fix:**
1. Replaced `st.markdown("<style>...</style>", unsafe_allow_html=True)` → `st.html("<style>...</style>")` (Streamlit 1.34+ safe API)
2. Removed raw `<div>` HTML from the sidebar title

---

## ✅ WORK #15 — Bug Fix: Export Button Not Working

**Status:** Done  
**Problem:** Clicking "Esporta in Excel" triggered a page rerender, causing the inner `st.download_button` to never render.  
**Fix (in `prematch.py` and `live.py`):** Removed outer `st.button("Esporta")` wrapper. Excel buffer is now generated eagerly after analysis completes, and `st.download_button` is rendered directly — always visible when results are shown.

---

## ✅ WORK #16 — Bug Fix: `applymap` → `map` (Pandas 2.1+ Compatibility)

**Status:** Done  
**Problem:** `roi_df.style.applymap(...)` is deprecated in Pandas 2.1+.  
**Fix:** Replaced `.applymap()` with `.map()` in both `screens/prematch.py` and `screens/patterns.py`.

---

## ✅ WORK #17 — Bug Fix: Missing Widget Keys

**Status:** Done  
**Problem:** Streamlit throws `DuplicateWidgetID` warnings when widgets lack explicit `key=` parameters, especially across rerenders.  
**Fix:** Added unique `key=` to all widgets in `app.py` Upload Dati section:
- `st.file_uploader(..., key="app_file")`
- `st.text_input("Lega", ..., key="app_league")`
- `st.text_input("Stagione", ..., key="app_season")`

---

## ✅ WORK #18 — Full UI Redesign: `screens/prematch.py` (Dark Sports Analytics)

**Status:** Done  
**File:** `screens/prematch.py` (28,724 bytes — ~800 lines)  
**Description:** Complete visual overhaul to match a professional dark sports analytics dashboard.

**CSS Design System Injected:**
| Token | Value |
|---|---|
| Background | `#0a0e1a` |
| Card Background | `#111827` |
| Border | `#1f2937` |
| Primary Text | `#f1f5f9` |
| Secondary Text | `#94a3b8` |
| Green Accent | `#22c55e` |
| Red Accent | `#ef4444` |
| Yellow Accent | `#f59e0b` |
| Blue Accent | `#3b82f6` |

**9 Sections Implemented:**

| # | Section | Details |
|---|---|---|
| 1 | **Header** | "⚽ PREMATCH ANALYSIS" title + subtitle with date |
| 2 | **Top KPI Bar** | 6 metric cards: Matches, % Casa, % Pareggi, % Trasferta, Media Gol, BTTS% |
| 3 | **Middle Row (4 panels)** | Over 2.5%, Under 2.5%, ROI%, Confidence Score |
| 4 | **Performance Breakdown** | Over/Under, BTTS/No BTTS bar charts side by side |
| 5 | **Goal Interval Distribution** | Horizontal bar chart (6 time buckets: 0-15, 16-30, etc.) |
| 6 | **ROI Simulation Table** | 4 strategies with colored Win Rate and ROI columns |
| 7 | **Exact Score Distribution** | Top-10 most common scorelines as bar chart |
| 8 | **First Goal Scorer Breakdown** | Pie chart: Home / Away / No Goal first goal analysis |
| 9 | **Match Data Table + Export** | Full filtered DataFrame + Excel download button |

**Plotly Charts:** All charts use `#1f2937` paper/plot bgcolor, white/gray text, green/red color scales.

---

## ✅ WORK #19 — `data/football.db` — SQLite Database File

**Status:** Done (auto-created on first run)  
**File:** `data/football.db` (248 KB)  
**Description:** Live SQLite database auto-initialized by `database.init_db()` on app startup.

---

## ✅ WORK #20 — App Verified Running at `localhost:8501`

**Status:** Done  
**Command:**
```bash
python -m streamlit run app.py --server.port 8501 --server.headless true
```
**Verified:**
- All 5 screens load without errors
- Sidebar navigation works (no duplicate Streamlit built-in nav)
- Upload Dati page accepts CSV/Excel files
- All module imports pass (`database`, `utils`, `data_loader`, `calculations`, `filters`)

---

## 📁 Final Project File Structure

```
Football-dashboard/
├── app.py                    ← Main entry point + navigation + Upload Dati
├── database.py               ← SQLite: 4 tables, all CRUD helpers
├── data_loader.py            ← CSV/Excel ingestion, 66-col map, duplicate skip
├── calculations.py           ← Stats, 4 ROI simulations, live reconstruction, H2H
├── filters.py                ← Sidebar filter UI + DataFrame filtering
├── utils.py                  ← Goal timing parser, formatters
├── requirements.txt          ← Python dependencies
├── README.md                 ← Quick start guide
├── DEVELOPMENT.md            ← Original spec (untouched)
├── work.md                   ← THIS FILE — all completed work
├── screens/
│   ├── __init__.py           ← Package init
│   ├── prematch.py           ← Prematch Analysis (dark redesign, 28KB)
│   ├── live.py               ← Live Analysis screen
│   ├── h2h.py                ← Head-to-Head Analysis
│   ├── patterns.py           ← Pattern Explorer
│   └── saved_filters.py      ← Saved Filters manager
└── data/
    └── football.db           ← SQLite database (248 KB, auto-created)
```

---

## 🐛 All Bugs Fixed

| # | Bug | File | Fix |
|---|---|---|---|
| 1 | React `removeChild` DOM crash | `app.py` | `st.markdown(unsafe_allow_html)` → `st.html()` |
| 2 | Export button not downloading | `prematch.py`, `live.py` | Removed wrapper `st.button`, use eager `st.download_button` |
| 3 | `applymap` deprecated (Pandas 2.1+) | `prematch.py`, `patterns.py` | `.applymap()` → `.map()` |
| 4 | Duplicate sidebar navigation | `app.py` | Renamed `pages/` → `screens/` to avoid Streamlit auto-detection |
| 5 | Missing widget `key=` parameters | `app.py` | Added `key="app_file"`, `key="app_league"`, `key="app_season"` |
| 6 | Function called before defined | `app.py` | Reordered code so `_render_upload()` is defined before it's called |

---

## ✅ WORK #10 — Advanced Visualizers & Redesign Additions

**Status:** Done  
**Description:** Expanded the Prematch Analysis UI to include four highly requested sports-analytics additions:
1. **Dynamic Top KPI Cards:** Extended columns to 8. Added Card 6 (Doppia Chance 1X) with dynamic conditional coloring (vibrant green `#22c55e` if >60%), Card 7 (Doppia Chance 12), and Card 8 (Doppia Chance X2). Added explicit subtext counts with custom styling (`#64748b`, `11px`, `margin-top: 4px`).
2. **Performance Squadre (Last 20 Matches):** Built a gorgeous comparison component displaying Wins, Draws, Losses, Goals Scored/Conceded, Points, and a custom mini bar chart for goal timing buckets across a team's last 20 matches.
3. **Indice di Pericolosità (Danger Index):** Implemented a custom 0-10 gauge indicator and text banner displaying a compound danger score computed from Shot on Target averages, goals, and Over 2.5 probabilities. Fixed indicator double value scale and removed duplicate title metrics.
4. **Trend Over/Under Charts:** Integrated interactive Plotly multi-line charts showing seasonal historical trends for Over 0.5, 1.5, and 2.5 percentages across 1T and 2T.
5. **Team Selectbox Filters:** Integrated Home Team and Away Team dropdown selectboxes dynamically derived from unique database values with complete preloaded values (`saved_filter_values`) and index state restoration.
6. **Over/Under UI Counts:** Enhanced the 1T and 2T Over/Under UI boxes to dynamically calculate and display precise `count/total` ratios underneath the percentage values styled with premium `#64748b` gray.

**Files Created/Modified:**
- `screens/prematch.py` — Fully implemented visualizers, filters integration, and refined UI fixes.
- `filters.py` — Integrated dropdown team filter selectboxes and backend `apply_filters` conditions.

---

*Generated: 2026-05-28 | Conversation: 9eb1b8ed-5a6b-40bb-a8f8-979593f3fd26*
