# Football Analytics Dashboard — Complete Development Plan

---

## Project Overview

A multi-screen Streamlit dashboard for football data analysis. No ML, no predictions — pure historical data analysis. Full interface in Italian. Backend in Python + SQLite.

**Total Milestones:** 3  
**Total Price:** $750  
**Deployment:** Streamlit Cloud

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Streamlit (Python) |
| Backend | Python — pandas, numpy |
| Database | SQLite (via sqlite3) |
| Charts | Plotly |
| Export | openpyxl, xlsxwriter |
| Deployment | Streamlit Cloud |

---

## Folder Structure

```
football_dashboard/
├── app.py                  # Main Streamlit entry point, page routing
├── database.py             # SQLite setup, all DB read/write operations
├── data_loader.py          # CSV/Excel ingestion, column normalization, DB insert
├── filters.py              # Filter UI components + SQL query builder
├── calculations.py         # All stats, percentages, ROI simulations
├── utils.py                # Goal timing parser, helpers, formatters
├── pages/
│   ├── prematch.py         # Prematch Analysis screen
│   ├── live.py             # Live Analysis screen
│   ├── h2h.py              # Head-to-Head screen
│   ├── patterns.py         # Pattern Explorer screen
│   └── saved_filters.py    # Saved Filters manager screen
├── data/
│   └── football.db         # SQLite database (auto-created on first run)
├── exports/                # Temporary folder for Excel exports
├── requirements.txt
└── README.md
```

---

## CSV File Analysis — Client Data

**File:** `england-premier-league-matches-2025-to-2026-stats.csv`  
**Rows:** 380 matches  
**Columns:** 66

### All Available Columns

```
timestamp                         — Unix timestamp of match
date_GMT                          — Human readable date (Aug 15 2025 - 7:00pm)
status                            — complete / incomplete
attendance                        — Stadium attendance
home_team_name                    — Home team name
away_team_name                    — Away team name
referee                           — Referee name
Game Week                         — Matchday number
Pre-Match PPG (Home)              — Pre-match points per game home
Pre-Match PPG (Away)              — Pre-match points per game away
home_ppg                          — Actual PPG home
away_ppg                          — Actual PPG away
home_team_goal_count              — FT goals home
away_team_goal_count              — FT goals away
total_goal_count                  — Total FT goals
total_goals_at_half_time          — Total HT goals
home_team_goal_count_half_time    — HT goals home
away_team_goal_count_half_time    — HT goals away
home_team_goal_timings            — Goal minutes home (e.g. "37,90'4,49,88")
away_team_goal_timings            — Goal minutes away (e.g. "64,76")
home_team_corner_count            — Corners home
away_team_corner_count            — Corners away
home_team_yellow_cards            — Yellow cards home
home_team_red_cards               — Red cards home
away_team_yellow_cards            — Yellow cards away
away_team_red_cards               — Red cards away
home_team_first_half_cards        — Cards home in 1st half
home_team_second_half_cards       — Cards home in 2nd half
away_team_first_half_cards        — Cards away in 1st half
away_team_second_half_cards       — Cards away in 2nd half
home_team_shots                   — Total shots home
away_team_shots                   — Total shots away
home_team_shots_on_target         — Shots on target home
away_team_shots_on_target         — Shots on target away
home_team_shots_off_target        — Shots off target home
away_team_shots_off_target        — Shots off target away
home_team_fouls                   — Fouls home
away_team_fouls                   — Fouls away
home_team_possession              — Possession % home
away_team_possession              — Possession % away
Home Team Pre-Match xG            — Pre-match xG home
Away Team Pre-Match xG            — Pre-match xG away
team_a_xg                         — Actual xG home
team_b_xg                         — Actual xG away
average_goals_per_match_pre_match — Historical avg goals pre-match
btts_percentage_pre_match         — BTTS % pre-match historical
over_15_percentage_pre_match      — Over 1.5 % pre-match historical
over_25_percentage_pre_match      — Over 2.5 % pre-match historical
over_35_percentage_pre_match      — Over 3.5 % pre-match historical
over_45_percentage_pre_match      — Over 4.5 % pre-match historical
over_15_HT_FHG_percentage_pre_match
over_05_HT_FHG_percentage_pre_match
over_15_2HG_percentage_pre_match
over_05_2HG_percentage_pre_match
average_corners_per_match_pre_match
average_cards_per_match_pre_match
odds_ft_home_team_win             — FT home win odds
odds_ft_draw                      — FT draw odds
odds_ft_away_team_win             — FT away win odds
odds_ft_over15                    — Over 1.5 odds
odds_ft_over25                    — Over 2.5 odds
odds_ft_over35                    — Over 3.5 odds
odds_ft_over45                    — Over 4.5 odds
odds_btts_yes                     — BTTS Yes odds
odds_btts_no                      — BTTS No odds
stadium_name                      — Stadium name
```

### Derived Columns (calculated on import, stored in DB)

```
ht_result          — e.g. "1-0" (from home_team_goal_count_half_time + away)
ft_result          — e.g. "4-2" (from home_team_goal_count + away)
goals_2h_home      — home_team_goal_count - home_team_goal_count_half_time
goals_2h_away      — away_team_goal_count - away_team_goal_count_half_time
total_goals_2h     — goals_2h_home + goals_2h_away
season             — extracted from date_GMT (e.g. "2025-2026")
league             — extracted from filename or manually set on upload
```

### Goal Timing Parser — Critical Logic

Raw format in CSV: `"37,90'4,49,88"` or `"64,76"` or `nan`

Rules:
- Plain number `"37"` → minute 37
- Format `"90'4"` → minute 94 (90 + 4)
- Format `"45'2"` → minute 47
- `nan` / empty → no goals
- All minutes stored as integers in `goal_events` table

---

## Database Schema

### Table: `matches`

All 66 CSV columns + all derived columns listed above.  
Primary key: `match_id` (auto-increment).  
Unique constraint on `(home_team_name, away_team_name, date_GMT)` to prevent duplicate imports.

### Table: `goal_events`

```sql
CREATE TABLE goal_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id    INTEGER REFERENCES matches(match_id),
    team_name   TEXT,
    is_home     INTEGER,   -- 1 = home, 0 = away
    minute      INTEGER,   -- parsed actual minute (90'4 = 94)
    half        INTEGER    -- 1 = first half, 2 = second half
);
```

### Table: `saved_filters`

```sql
CREATE TABLE saved_filters (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT UNIQUE,
    screen      TEXT,      -- prematch / live / h2h / pattern
    filters_json TEXT,     -- JSON blob of all filter values
    created_at  TEXT
);
```

### Table: `leagues`

```sql
CREATE TABLE leagues (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    name    TEXT UNIQUE,   -- e.g. "Premier League"
    season  TEXT           -- e.g. "2025-2026"
);
```

---

## Module Specifications

### `utils.py`

```python
def parse_goal_timings(timing_str: str) -> list[int]:
    """
    Input:  "37,90'4,49,88"
    Output: [37, 94, 49, 88]
    Handles: plain int, 90'X format, 45'X format, nan, empty string
    """

def get_half(minute: int) -> int:
    """Returns 1 if minute <= 45+stoppage, else 2. Uses 45 as cutoff."""

def format_pct(value: float) -> str:
    """Returns '63.4%' formatted string"""

def format_roi(value: float) -> str:
    """Returns '+12.3%' or '-8.1%' with sign"""
```

---

### `data_loader.py`

```python
def load_csv(filepath: str, league_name: str, season: str) -> dict:
    """
    1. Read CSV with pandas
    2. Normalize column names to standard internal names
    3. Calculate derived columns (ht_result, ft_result, goals_2h_*, season, league)
    4. Parse goal timings → populate goal_events table
    5. Skip duplicates (check unique constraint)
    6. Return summary: {rows_added, rows_skipped, errors}
    """

def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Maps all 66 CSV column names to internal standard names"""
```

---

### `calculations.py`

```python
def analyze_matches(df: pd.DataFrame) -> dict:
    """
    Takes filtered DataFrame, returns complete results dict:
    
    GENERAL:
    - match_count
    - home_win_pct, draw_pct, away_win_pct
    
    GOALS FT:
    - over_05_ft_pct, over_15_ft_pct, over_25_ft_pct, over_35_ft_pct
    - btts_pct
    - avg_goals_ft
    
    HALF TIME:
    - over_05_ht_pct, over_15_ht_pct
    - avg_goals_ht
    
    2ND HALF:
    - over_05_2h_pct
    - at_least_1_goal_2h_pct
    - zero_goals_2h_pct
    - avg_goals_2h
    
    TIMING:
    - goals_01_15_pct, goals_16_30_pct, goals_31_45_pct
    - goals_46_60_pct, goals_61_75_pct, goals_76_90_pct
    - avg_first_goal_minute
    
    ROI SIMULATIONS (fixed stake = 1 unit):
    - roi_home_win     — bet home win at odds_ft_home_team_win
    - roi_lay_home     — lay home win (back draw or away)
    - roi_over_05_2h   — bet over 0.5 2H at odds_ft_over15 (proxy)
    - roi_lay_00       — lay 0-0 result
    
    Each ROI = ((wins * (odds-1)) - losses) / total_bets * 100
    """

def analyze_live_state(
    df: pd.DataFrame,
    from_minute: int,
    home_score: int,
    away_score: int
) -> dict:
    """
    Finds all matches in df where at given minute score was home_score-away_score.
    Returns what happened from that point onward:
    - final_result_distribution (home_win/draw/away_win %)
    - goals_added_distribution (0 more, 1 more, 2 more, 3+ more)
    - next_goal_by (home % / away % / no more goals %)
    - next_goal_window (46-60, 61-75, 76-90 %)
    - most_likely_exact_ft
    """

def analyze_h2h(df: pd.DataFrame, home: str, away: str) -> dict:
    """
    Filters all matches between these two teams (both home and away).
    Returns complete H2H stats including last 10 meetings.
    """
```

---

### `filters.py`

```python
def render_filter_sidebar(screen: str) -> dict:
    """
    Renders Streamlit sidebar filters for given screen.
    Returns dict of active filter values.
    
    PREMATCH filters:
    - odds_home_min / odds_home_max       (slider 1.0–20.0)
    - odds_away_min / odds_away_max       (slider 1.0–20.0)
    - odds_draw_min / odds_draw_max       (slider 1.0–20.0)
    - ht_result                           (multiselect)
    - ft_result                           (multiselect, optional)
    - shots_total_min / shots_total_max   (slider)
    - shots_on_target_min/max             (slider)
    - possession_min / possession_max     (slider 0–100)
    - corners_min / corners_max           (slider)
    - league                              (dropdown)
    - season                              (dropdown)
    - game_week_min / game_week_max       (slider)
    
    LIVE filters (subset):
    - league, season, current_minute (slider), home_score, away_score
    
    H2H filters:
    - home_team (selectbox), away_team (selectbox), season (multiselect)
    """

def apply_filters(df: pd.DataFrame, filters: dict) -> pd.DataFrame:
    """Applies filter dict to DataFrame, returns filtered subset"""
```

---

## Screen Specifications

### Screen 1 — Prematch Analysis (`pages/prematch.py`)

**Purpose:** User sets filters, clicks Analizza, sees complete stats output.

**Layout:**
```
[Sidebar: all filters + Saved Filters loader + Analizza button]

[Main area]
Row 1 (4 cols): Partite Totali | % Vittoria Casa | % Pareggio | % Vittoria Trasferta
Row 2 (4 cols): Over 0.5 FT   | Over 1.5 FT     | Over 2.5 FT | BTTS %
Row 3 (4 cols): Gol 1° Tempo % | Gol 2° Tempo % | Media Primo Gol | Media Gol Totali
Row 4 (4 cols): Over 0.5 2T   | Almeno 1 Gol 2T | Nessun Gol 2T  | Over 1.5 2T

[ROI Table]
Scommessa          | Vincite | Perdite | ROI
Vittoria Casa      |   XX    |   XX    | +/-XX%
Lay Casa           |   XX    |   XX    | +/-XX%
Over 0.5 2° Tempo  |   XX    |   XX    | +/-XX%
Lay 0-0            |   XX    |   XX    | +/-XX%

[Charts — 2 columns]
Left:  Bar chart — Distribuzione Gol per Fascia Oraria (6 bars: 1-15, 16-30, 31-45, 46-60, 61-75, 76-90)
Right: Pie chart — Vittoria Casa / Pareggio / Vittoria Trasferta

[Export button: Esporta in Excel]
```

---

### Screen 2 — Live Analysis (`pages/live.py`)

**Purpose:** User enters current match state (minute + score), system finds all historical matches that had this exact state at this minute, shows what happened next.

**Layout:**
```
[Sidebar]
- League selector
- Season selector
- Minuto attuale (slider 1–90)
- Gol Casa (number input 0–10)
- Gol Trasferta (number input 0–10)
- [Analizza button]

[Main area — after analysis]
Header: "XX partite trovate con questo scenario"

Row 1 (3 cols):
  % Vittoria Casa  |  % Pareggio  |  % Vittoria Trasferta
  (from current state to end)

Row 2 (3 cols):
  % Nessun altro gol  |  % +1 Gol  |  % +2 o più Gol

Row 3 (3 cols):
  % Prossimo Gol Casa  |  % Prossimo Gol Trasferta  |  % Nessun Altro Gol

[Chart: Distribuzione Risultati Finali Esatti]
Bar chart of top 8 most common final scorelines from this state

[Chart: Fascia Oraria Prossimo Gol]
Bar chart — when was the next goal scored (46-60, 61-75, 76-90, no goal)

[Auto text insight box — Italian]
Example: "Nel 63% delle partite simili è stato segnato almeno un altro gol.
          Il risultato finale più comune è stato 1-1 (18% dei casi)."
```

**Core Logic — Match State Reconstruction:**

For each match in DB:
1. Load all goal_events for that match ordered by minute
2. At `from_minute`, reconstruct score by counting goals before that minute
3. If reconstructed score matches input (home_score, away_score) → include this match
4. From this match, record: goals after `from_minute`, final result, next goal minute + team

---

### Screen 3 — H2H Analysis (`pages/h2h.py`)

**Purpose:** Select two teams, see complete head-to-head history from uploaded files.

**Layout:**
```
[Sidebar]
- Squadra Casa (selectbox — all unique teams in DB)
- Squadra Trasferta (selectbox)
- Stagione (multiselect — all / specific)
- [Cerca button]

[Main area]
Header: "Milan vs Inter — 12 partite"

Row 1 (3 cols): Vittorie Milan | Pareggi | Vittorie Inter

[Table: Ultimi incontri]
Data | Casa | Risultato HT | Risultato FT | Gol Totali | Over 2.5

Row 2 stats (4 cols):
Media Gol / Partita | Over 2.5 % | BTTS % | % Gol 2° Tempo

[Chart: Distribuzione Risultati H2H]
[Chart: Gol per Partita trend — last 10 meetings]
```

---

### Screen 4 — Pattern Explorer (`pages/patterns.py`)

**Purpose:** Advanced filter combinations with pattern identification. Shows which filter combinations are producing statistically strong results.

**Layout:**
```
[Sidebar: all prematch filters]
[Load Saved Filter dropdown]
[Analizza button]

[Main area]
[Same output as Prematch Analysis]

[Pattern Insights section]
- Trend ultime 10 partite (mini sparkline chart)
- Confronto con media generale del database
- Highlight: "Questo filtro ha un ROI di +18.3% su 47 partite"

[Compare Filters button — opens second filter column for side-by-side comparison]
```

---

### Screen 5 — Filtri Salvati (`pages/saved_filters.py`)

**Purpose:** Manage saved filter combinations — create, edit, delete, apply to any screen.

**Layout:**
```
[List of saved filters — card layout]
Each card shows:
  Filter Name
  Screen: Prematch / Live / Pattern
  Preview of active filter values
  [Applica] [Modifica] [Elimina] buttons

[Create new filter]
  Nome filtro (text input)
  Schermata di destinazione (dropdown)
  [All filter inputs]
  [Salva Filtro button]
```

---

### Screen 6 — Upload Dati (`app.py` sidebar or dedicated tab)

**Purpose:** Upload new CSV/Excel files to update the database.

**Layout:**
```
[File uploader — accepts .csv, .xlsx, .xls]
[League name input]
[Season input]
[Importa button]

[Result message]
"Importati 380 risultati. 0 duplicati saltati."
or
"Errore: colonna 'home_team_name' non trovata."
```

---

## ROI Calculation Logic

```
For each simulation (e.g. Bet Home Win):

wins  = number of matches where home team won
losses = total_matches - wins
profit = wins * (odds - 1) - losses * 1
roi    = (profit / total_matches) * 100

Display: "+12.3%" in green / "-8.1%" in red
```

**Four ROI simulations:**

| Simulation | Bet condition | Odds used |
|---|---|---|
| Vittoria Casa | home_goal_count > away_goal_count | odds_ft_home_team_win |
| Lay Casa | home team did NOT win | 1 / (1 - 1/odds_ft_home_team_win) |
| Over 0.5 2° Tempo | total_goals_2h >= 1 | odds_ft_over15 (proxy) |
| Lay 0-0 | ft_result != "0-0" | odds_btts_no (proxy) |

---

## Goal Timing Distribution Logic

```python
# For each filtered match, parse all goal_events
# Bucket each goal minute:

BUCKETS = {
    '1-15':   (1,  15),
    '16-30':  (16, 30),
    '31-45':  (31, 45),
    '46-60':  (46, 60),
    '61-75':  (61, 75),
    '76-90':  (76, 120),  # includes extra time
}

# Count goals per bucket, divide by total goals = %
# Display as bar chart (Plotly)
```

---

## Strategy Simulation Logic

**Simulation: Over 0.5 at Minute X**

User inputs: minute X

Logic:
1. For each match, check: were there 0 goals before minute X?
2. If yes → this match is a valid simulation entry
3. Check: was there at least 1 goal after minute X?
4. wins / total_entries = success %
5. ROI = standard formula

**Simulation: Lay 0-0 at Minute X**

Same but: check score = 0-0 at minute X, then track if it stayed 0-0.

---

## Export Functionality

On every screen with results, an "Esporta in Excel" button:

```python
def export_to_excel(results_dict: dict, filtered_df: pd.DataFrame, filename: str):
    """
    Sheet 1: Riepilogo — all calculated metrics
    Sheet 2: Partite — raw filtered match list
    Sheet 3: ROI — ROI simulation detail
    """
```

---

## Column Normalization Map

When client uploads a file from a different source with different column names, `data_loader.py` maps to internal standard names:

```python
COLUMN_MAP = {
    # Standard names (this CSV) → internal name
    'home_team_name':                  'home_team',
    'away_team_name':                  'away_team',
    'home_team_goal_count':            'home_goals_ft',
    'away_team_goal_count':            'away_goals_ft',
    'home_team_goal_count_half_time':  'home_goals_ht',
    'away_team_goal_count_half_time':  'away_goals_ht',
    'total_goal_count':                'total_goals_ft',
    'total_goals_at_half_time':        'total_goals_ht',
    'home_team_goal_timings':          'home_goal_timings',
    'away_team_goal_timings':          'away_goal_timings',
    'home_team_shots':                 'home_shots',
    'away_team_shots':                 'away_shots',
    'home_team_shots_on_target':       'home_shots_on_target',
    'away_team_shots_on_target':       'away_shots_on_target',
    'home_team_possession':            'home_possession',
    'away_team_possession':            'away_possession',
    'home_team_corner_count':          'home_corners',
    'away_team_corner_count':          'away_corners',
    'odds_ft_home_team_win':           'odds_home',
    'odds_ft_draw':                    'odds_draw',
    'odds_ft_away_team_win':           'odds_away',
    'odds_ft_over15':                  'odds_over15',
    'odds_ft_over25':                  'odds_over25',
    'odds_ft_over35':                  'odds_over35',
    'odds_ft_over45':                  'odds_over45',
    'odds_btts_yes':                   'odds_btts_yes',
    'odds_btts_no':                    'odds_btts_no',
    'Game Week':                       'game_week',
    'date_GMT':                        'match_date',
    # ... all 66 columns mapped
}
```

---

## Italian UI Labels Reference

```python
LABELS = {
    'match_count':        'Partite Totali',
    'home_win_pct':       '% Vittoria Casa',
    'draw_pct':           '% Pareggio',
    'away_win_pct':       '% Vittoria Trasferta',
    'over_05_ft':         'Over 0.5 FT',
    'over_15_ft':         'Over 1.5 FT',
    'over_25_ft':         'Over 2.5 FT',
    'btts_pct':           'Goal Goal %',
    'goals_1h_pct':       'Gol 1° Tempo %',
    'goals_2h_pct':       'Gol 2° Tempo %',
    'avg_first_goal':     'Media Minuto Primo Gol',
    'over_05_2h':         'Over 0.5 2° Tempo',
    'at_least_1_2h':      'Almeno 1 Gol 2° Tempo',
    'zero_goals_2h':      'Nessun Gol 2° Tempo',
    'roi_home_win':       'Vittoria Casa',
    'roi_lay_home':       'Lay Casa',
    'roi_over_05_2h':     'Over 0.5 2° Tempo',
    'roi_lay_00':         'Lay 0-0',
    'analyze_btn':        'Analizza',
    'export_btn':         'Esporta in Excel',
    'save_filter_btn':    'Salva Filtro',
    'load_filter':        'Carica Filtro',
    'no_data':            'Nessun dato trovato con i filtri selezionati.',
    'db_updated':         'Database aggiornato: {n} partite importate.',
}
```

---

## requirements.txt

```
streamlit>=1.35.0
pandas>=2.0.0
numpy>=1.24.0
plotly>=5.18.0
openpyxl>=3.1.0
xlsxwriter>=3.1.0
```

---

## README — Deploy Instructions (for client)

```
1. Install Python 3.10+
2. pip install -r requirements.txt
3. streamlit run app.py
4. Open browser: http://localhost:8501

For Streamlit Cloud:
1. Push repo to GitHub
2. Go to share.streamlit.io
3. Connect repo → set app.py as entry point
4. Deploy
```

---

## Edge Cases to Handle

| Case | Handling |
|---|---|
| Goal timing is `nan` | Treat as no goals, skip parsing |
| Format `"90'4"` | Parse as minute 94 |
| Format `"45'2"` | Parse as minute 47 |
| Duplicate file upload | Check unique constraint, skip duplicates, report count |
| Filter returns 0 matches | Show "Nessun dato trovato" message, no crash |
| Live analysis: no historical match found | Show "Scenario non trovato nel database" |
| Missing odds column | Set odds to NaN, skip ROI for that simulation |
| Possession > 100 or < 0 | Data cleaning step — clamp to 0–100 |
| H2H: teams never played | Show "Nessun precedente trovato" |

---

## Milestone Summary

| Milestone | Deliverables | Price |
|---|---|---|
| M1 | DB setup + data loader + Prematch Analysis screen complete | $250 |
| M2 | Live Analysis screen + H2H Analysis screen | $250 |
| M3 | Pattern Explorer + Saved Filters + Streamlit Cloud deployment + export | $250 |

**Each milestone reviewed and approved by client before next begins.**

---

*Last updated: May 2026*
