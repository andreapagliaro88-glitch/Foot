"""
database.py — SQLite setup and all DB read/write operations
"""

from __future__ import annotations

import sqlite3
import os
import json
import shutil
from datetime import datetime
from typing import Optional

import pandas as pd
import streamlit as st

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "football.db")
SEED_DB_PATH = os.path.join(os.path.dirname(__file__), "data", "football_seed.db")


def _db_mtime() -> float:
    try:
        return os.path.getmtime(DB_PATH)
    except OSError:
        return 0.0


def _match_count(db_path: str) -> int:
    if not os.path.isfile(db_path) or os.path.getsize(db_path) == 0:
        return 0
    conn = sqlite3.connect(db_path)
    try:
        return int(conn.execute("SELECT COUNT(*) FROM matches").fetchone()[0])
    except sqlite3.Error:
        return 0
    finally:
        conn.close()


def _ensure_seeded_database() -> None:
    """Copia il database seed nel runtime se mancante o vuoto (deploy Streamlit Cloud)."""
    if not os.path.isfile(SEED_DB_PATH):
        return

    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    if _match_count(DB_PATH) == 0:
        shutil.copy2(SEED_DB_PATH, DB_PATH)


def get_connection():
    """Returns a SQLite connection with row_factory set to Row."""
    _ensure_seeded_database()
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA temp_store=MEMORY")
    except sqlite3.OperationalError:
        pass
    return conn


@st.cache_resource(show_spinner=False)
def init_db():
    """Creates all tables if they don't exist (once per server session)."""
    _ensure_seeded_database()
    conn = get_connection()
    cur = conn.cursor()

    # ── matches ────────────────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS matches (
            match_id                        INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp                       INTEGER,
            match_date                      TEXT,
            status                          TEXT,
            attendance                      REAL,
            home_team                       TEXT,
            away_team                       TEXT,
            referee                         TEXT,
            game_week                       REAL,
            pre_match_ppg_home              REAL,
            pre_match_ppg_away              REAL,
            home_ppg                        REAL,
            away_ppg                        REAL,
            home_goals_ft                   REAL,
            away_goals_ft                   REAL,
            total_goals_ft                  REAL,
            total_goals_ht                  REAL,
            home_goals_ht                   REAL,
            away_goals_ht                   REAL,
            home_goal_timings               TEXT,
            away_goal_timings               TEXT,
            home_corners                    REAL,
            away_corners                    REAL,
            home_yellow_cards               REAL,
            home_red_cards                  REAL,
            away_yellow_cards               REAL,
            away_red_cards                  REAL,
            home_first_half_cards           REAL,
            home_second_half_cards          REAL,
            away_first_half_cards           REAL,
            away_second_half_cards          REAL,
            home_shots                      REAL,
            away_shots                      REAL,
            home_shots_on_target            REAL,
            away_shots_on_target            REAL,
            home_shots_off_target           REAL,
            away_shots_off_target           REAL,
            home_fouls                      REAL,
            away_fouls                      REAL,
            home_possession                 REAL,
            away_possession                 REAL,
            home_xg_pre                     REAL,
            away_xg_pre                     REAL,
            home_xg                         REAL,
            away_xg                         REAL,
            avg_goals_pre_match             REAL,
            btts_pct_pre_match              REAL,
            over_15_pct_pre_match           REAL,
            over_25_pct_pre_match           REAL,
            over_35_pct_pre_match           REAL,
            over_45_pct_pre_match           REAL,
            over_15_ht_pct_pre_match        REAL,
            over_05_ht_pct_pre_match        REAL,
            over_15_2h_pct_pre_match        REAL,
            over_05_2h_pct_pre_match        REAL,
            avg_corners_pre_match           REAL,
            avg_cards_pre_match             REAL,
            odds_home                       REAL,
            odds_draw                       REAL,
            odds_away                       REAL,
            odds_over15                     REAL,
            odds_over25                     REAL,
            odds_over35                     REAL,
            odds_over45                     REAL,
            odds_btts_yes                   REAL,
            odds_btts_no                    REAL,
            stadium_name                    TEXT,
            -- derived columns
            ht_result                       TEXT,
            ft_result                       TEXT,
            goals_2h_home                   REAL,
            goals_2h_away                   REAL,
            total_goals_2h                  REAL,
            season                          TEXT,
            league                          TEXT,
            UNIQUE (home_team, away_team, match_date)
        )
    """)

    # ── goal_events ────────────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS goal_events (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id    INTEGER REFERENCES matches(match_id) ON DELETE CASCADE,
            team_name   TEXT,
            is_home     INTEGER,   -- 1 = home, 0 = away
            minute      INTEGER,   -- parsed actual minute (90'4 → 94)
            half        INTEGER    -- 1 = first half, 2 = second half
        )
    """)

    # ── saved_filters ──────────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS saved_filters (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            name         TEXT UNIQUE,
            screen       TEXT,         -- prematch / live / h2h / pattern
            filters_json TEXT,         -- JSON blob of all filter values
            created_at   TEXT
        )
    """)

    # ── leagues ────────────────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS leagues (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            name    TEXT UNIQUE,
            season  TEXT
        )
    """)

    conn.commit()
    conn.close()


# ── Read helpers (cached) ───────────────────────────────────────────────────

def _fetch_all_matches() -> list:
    conn = get_connection()
    cur = conn.execute("SELECT * FROM matches")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


@st.cache_data(show_spinner=False)
def _cached_all_matches(_db_version: float) -> list:
    return _fetch_all_matches()


def get_matches_dataframe() -> pd.DataFrame:
    """Tutte le partite come DataFrame (cached)."""
    return pd.DataFrame(_cached_all_matches(_db_mtime()))


def get_all_matches():
    """Returns all matches as a list of dicts."""
    return _cached_all_matches(_db_mtime())


def get_all_matches_unfiltered() -> list:
    """Alias di get_all_matches — mantiene compatibilità."""
    return get_all_matches()


def _fetch_teams() -> list:
    conn = get_connection()
    cur = conn.execute(
        "SELECT DISTINCT home_team FROM matches "
        "UNION SELECT DISTINCT away_team FROM matches ORDER BY 1"
    )
    teams = [r[0] for r in cur.fetchall() if r[0]]
    conn.close()
    return teams


@st.cache_data(show_spinner=False)
def _cached_teams(_db_version: float) -> list:
    return _fetch_teams()


def get_teams():
    """Returns sorted list of all unique team names."""
    return _cached_teams(_db_mtime())


def _fetch_leagues() -> list:
    conn = get_connection()
    cur = conn.execute(
        "SELECT DISTINCT league FROM matches WHERE league IS NOT NULL ORDER BY league"
    )
    leagues = [r[0] for r in cur.fetchall()]
    conn.close()
    return leagues


@st.cache_data(show_spinner=False)
def _cached_leagues(_db_version: float) -> list:
    return _fetch_leagues()


def get_leagues():
    """Returns list of unique league names."""
    return _cached_leagues(_db_mtime())


def _fetch_seasons() -> list:
    conn = get_connection()
    cur = conn.execute(
        "SELECT DISTINCT season FROM matches WHERE season IS NOT NULL ORDER BY season"
    )
    seasons = [r[0] for r in cur.fetchall()]
    conn.close()
    return seasons


@st.cache_data(show_spinner=False)
def _cached_seasons(_db_version: float) -> list:
    return _fetch_seasons()


def get_seasons():
    """Returns list of unique seasons."""
    return _cached_seasons(_db_mtime())


def _fetch_teams_by_league(league: str) -> list:
    conn = get_connection()
    cur = conn.execute(
        """
        SELECT DISTINCT home_team FROM matches WHERE league = ?
        UNION
        SELECT DISTINCT away_team FROM matches WHERE league = ?
        ORDER BY 1
        """,
        (league, league),
    )
    teams = [r[0] for r in cur.fetchall() if r[0]]
    conn.close()
    return teams


@st.cache_data(show_spinner=False)
def _cached_teams_by_league(_db_version: float, league: str) -> list:
    return _fetch_teams_by_league(league)


def get_teams_by_league(league: str) -> list:
    """Squadre distinte per un campionato."""
    if not league:
        return []
    return _cached_teams_by_league(_db_mtime(), league)


def _fetch_league_season_stats() -> list[dict]:
    conn = get_connection()
    cur = conn.execute("""
        SELECT league, season, COUNT(*) AS match_count
        FROM matches
        WHERE league IS NOT NULL AND TRIM(league) != ''
        GROUP BY league, season
        ORDER BY league, season
    """)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


@st.cache_data(show_spinner=False)
def _cached_league_season_stats(_db_version: float) -> list[dict]:
    return _fetch_league_season_stats()


def get_league_season_stats() -> list[dict]:
    """Raggruppa partite per campionato + stagione con conteggio."""
    return _cached_league_season_stats(_db_mtime())


def delete_league_data(league: str, season: Optional[str] = None) -> dict:
    """
    Elimina partite (e goal_events in cascade) per campionato.
    Se season è valorizzata, elimina solo quella combinazione league+season.
    """
    league = str(league or "").strip()
    season = str(season or "").strip() if season else ""
    if not league:
        return {"matches_deleted": 0, "league": league, "season": season or None}

    conn = get_connection()
    try:
        if season:
            cur = conn.execute(
                "DELETE FROM matches WHERE league = ? AND season = ?",
                (league, season),
            )
            conn.execute(
                "DELETE FROM leagues WHERE name = ? AND season = ?",
                (league, season),
            )
        else:
            cur = conn.execute("DELETE FROM matches WHERE league = ?", (league,))
            conn.execute("DELETE FROM leagues WHERE name = ?", (league,))
        matches_deleted = cur.rowcount
        conn.commit()
        invalidate_db_cache()
        return {
            "matches_deleted": matches_deleted,
            "league": league,
            "season": season or None,
        }
    finally:
        conn.close()


def _fetch_goal_events_for_matches(match_ids: list) -> dict:
    conn = get_connection()
    placeholders = ",".join("?" * len(match_ids))
    cur = conn.execute(
        f"SELECT * FROM goal_events WHERE match_id IN ({placeholders}) ORDER BY match_id, minute",
        match_ids,
    )
    events = {}
    for row in cur.fetchall():
        mid = row["match_id"]
        events.setdefault(mid, []).append(dict(row))
    conn.close()
    return events


@st.cache_data(show_spinner=False)
def _cached_goal_events(_db_version: float, match_ids: tuple[int, ...]) -> dict:
    return _fetch_goal_events_for_matches(list(match_ids))


def get_goal_events_for_matches(match_ids: list) -> dict:
    """
    Returns goal_events grouped by match_id.
    {match_id: [{'team_name': ..., 'is_home': ..., 'minute': ..., 'half': ...}, ...]}
    """
    if not match_ids:
        return {}
    ids = tuple(int(i) for i in match_ids)
    return _cached_goal_events(_db_mtime(), ids)


def invalidate_db_cache() -> None:
    """Svuota la cache query dopo import o eliminazione dati."""
    _cached_all_matches.clear()
    _cached_teams.clear()
    _cached_leagues.clear()
    _cached_seasons.clear()
    _cached_teams_by_league.clear()
    _cached_league_season_stats.clear()
    _cached_goal_events.clear()


# ── Saved filters ──────────────────────────────────────────────────────────

def save_filter(name: str, screen: str, filters: dict) -> bool:
    """Saves a filter. Returns True on success, False if name already exists."""
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO saved_filters (name, screen, filters_json, created_at) VALUES (?,?,?,?)",
            (name, screen, json.dumps(filters), datetime.now().isoformat())
        )
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()


def get_saved_filters(screen: str = None) -> list:
    """Returns list of saved filter dicts. Optionally filtered by screen."""
    conn = get_connection()
    if screen:
        cur = conn.execute(
            "SELECT * FROM saved_filters WHERE screen=? ORDER BY created_at DESC", (screen,)
        )
    else:
        cur = conn.execute("SELECT * FROM saved_filters ORDER BY created_at DESC")
    rows = []
    for r in cur.fetchall():
        d = dict(r)
        d["filters"] = json.loads(d["filters_json"])
        rows.append(d)
    conn.close()
    return rows


def delete_saved_filter(filter_id: int):
    """Deletes a saved filter by id."""
    conn = get_connection()
    conn.execute("DELETE FROM saved_filters WHERE id=?", (filter_id,))
    conn.commit()
    conn.close()


def update_saved_filter(filter_id: int, name: str, screen: str, filters: dict):
    """Updates an existing saved filter."""
    conn = get_connection()
    conn.execute(
        "UPDATE saved_filters SET name=?, screen=?, filters_json=? WHERE id=?",
        (name, screen, json.dumps(filters), filter_id)
    )
    conn.commit()
    conn.close()


def get_last_h2h_matches(team_a: str, team_b: str, limit: int = 10) -> list:
    """
    SELECT match_date, home_team, away_team, 
           ft_result, home_goals_ft, away_goals_ft, league, season
    FROM matches
    WHERE (home_team = ? AND away_team = ?)
       OR (home_team = ? AND away_team = ?)
    ORDER BY match_date DESC
    LIMIT ?
    
    Params: (team_a, team_b, team_b, team_a, limit)
    """
    conn = get_connection()
    cur = conn.execute("""
        SELECT match_date, home_team, away_team, 
               ft_result, home_goals_ft, away_goals_ft, league, season
        FROM matches
        WHERE (home_team = ? AND away_team = ?)
           OR (home_team = ? AND away_team = ?)
        ORDER BY match_date DESC
        LIMIT ?
    """, (team_a, team_b, team_b, team_a, limit))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows