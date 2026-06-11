"""
data_loader.py — CSV/Excel ingestion, column normalization, DB insert
"""

import pandas as pd
import numpy as np
import re
import sqlite3
from database import get_connection, init_db
from utils import parse_goal_timings, get_half, build_league_name

# ── Column normalization map ───────────────────────────────────────────────

COLUMN_MAP = {
    # Identity / date
    "timestamp":                          "timestamp",
    "date_gmt":                           "match_date",
    "status":                             "status",
    "attendance":                         "attendance",
    # Teams / match info
    "home_team_name":                     "home_team",
    "away_team_name":                     "away_team",
    "referee":                            "referee",
    "game week":                          "game_week",
    "game_week":                          "game_week",
    # PPG
    "pre-match ppg (home)":               "pre_match_ppg_home",
    "pre-match ppg (away)":               "pre_match_ppg_away",
    "home_ppg":                           "home_ppg",
    "away_ppg":                           "away_ppg",
    # Goals FT
    "home_team_goal_count":               "home_goals_ft",
    "away_team_goal_count":               "away_goals_ft",
    "total_goal_count":                   "total_goals_ft",
    # Goals HT
    "total_goals_at_half_time":           "total_goals_ht",
    "home_team_goal_count_half_time":     "home_goals_ht",
    "away_team_goal_count_half_time":     "away_goals_ht",
    # Goal timings
    "home_team_goal_timings":             "home_goal_timings",
    "away_team_goal_timings":             "away_goal_timings",
    # Corners
    "home_team_corner_count":             "home_corners",
    "away_team_corner_count":             "away_corners",
    # Cards
    "home_team_yellow_cards":             "home_yellow_cards",
    "home_team_red_cards":                "home_red_cards",
    "away_team_yellow_cards":             "away_yellow_cards",
    "away_team_red_cards":                "away_red_cards",
    "home_team_first_half_cards":         "home_first_half_cards",
    "home_team_second_half_cards":        "home_second_half_cards",
    "away_team_first_half_cards":         "away_first_half_cards",
    "away_team_second_half_cards":        "away_second_half_cards",
    # Shots
    "home_team_shots":                    "home_shots",
    "away_team_shots":                    "away_shots",
    "home_team_shots_on_target":          "home_shots_on_target",
    "away_team_shots_on_target":          "away_shots_on_target",
    "home_team_shots_off_target":         "home_shots_off_target",
    "away_team_shots_off_target":         "away_shots_off_target",
    # Fouls
    "home_team_fouls":                    "home_fouls",
    "away_team_fouls":                    "away_fouls",
    # Possession
    "home_team_possession":               "home_possession",
    "away_team_possession":               "away_possession",
    # xG
    "home team pre-match xg":             "home_xg_pre",
    "away team pre-match xg":             "away_xg_pre",
    "team_a_xg":                          "home_xg",
    "team_b_xg":                          "away_xg",
    # Pre-match stats
    "average_goals_per_match_pre_match":  "avg_goals_pre_match",
    "btts_percentage_pre_match":          "btts_pct_pre_match",
    "over_15_percentage_pre_match":       "over_15_pct_pre_match",
    "over_25_percentage_pre_match":       "over_25_pct_pre_match",
    "over_35_percentage_pre_match":       "over_35_pct_pre_match",
    "over_45_percentage_pre_match":       "over_45_pct_pre_match",
    "over_15_ht_fhg_percentage_pre_match":"over_15_ht_pct_pre_match",
    "over_05_ht_fhg_percentage_pre_match":"over_05_ht_pct_pre_match",
    "over_15_2hg_percentage_pre_match":   "over_15_2h_pct_pre_match",
    "over_05_2hg_percentage_pre_match":   "over_05_2h_pct_pre_match",
    "average_corners_per_match_pre_match":"avg_corners_pre_match",
    "average_cards_per_match_pre_match":  "avg_cards_pre_match",
    # Odds
    "odds_ft_home_team_win":              "odds_home",
    "odds_ft_draw":                       "odds_draw",
    "odds_ft_away_team_win":              "odds_away",
    "odds_ft_over15":                     "odds_over15",
    "odds_ft_over25":                     "odds_over25",
    "odds_ft_over35":                     "odds_over35",
    "odds_ft_over45":                     "odds_over45",
    "odds_btts_yes":                      "odds_btts_yes",
    "odds_btts_no":                       "odds_btts_no",
    # Stadium
    "stadium_name":                       "stadium_name",
}

# DB columns in insertion order (must match matches table)
DB_COLUMNS = [
    "timestamp", "match_date", "status", "attendance",
    "home_team", "away_team", "referee", "game_week",
    "pre_match_ppg_home", "pre_match_ppg_away", "home_ppg", "away_ppg",
    "home_goals_ft", "away_goals_ft", "total_goals_ft",
    "total_goals_ht", "home_goals_ht", "away_goals_ht",
    "home_goal_timings", "away_goal_timings",
    "home_corners", "away_corners",
    "home_yellow_cards", "home_red_cards", "away_yellow_cards", "away_red_cards",
    "home_first_half_cards", "home_second_half_cards",
    "away_first_half_cards", "away_second_half_cards",
    "home_shots", "away_shots",
    "home_shots_on_target", "away_shots_on_target",
    "home_shots_off_target", "away_shots_off_target",
    "home_fouls", "away_fouls",
    "home_possession", "away_possession",
    "home_xg_pre", "away_xg_pre", "home_xg", "away_xg",
    "avg_goals_pre_match", "btts_pct_pre_match",
    "over_15_pct_pre_match", "over_25_pct_pre_match",
    "over_35_pct_pre_match", "over_45_pct_pre_match",
    "over_15_ht_pct_pre_match", "over_05_ht_pct_pre_match",
    "over_15_2h_pct_pre_match", "over_05_2h_pct_pre_match",
    "avg_corners_pre_match", "avg_cards_pre_match",
    "odds_home", "odds_draw", "odds_away",
    "odds_over15", "odds_over25", "odds_over35", "odds_over45",
    "odds_btts_yes", "odds_btts_no",
    "stadium_name",
    # derived
    "ht_result", "ft_result",
    "goals_2h_home", "goals_2h_away", "total_goals_2h",
    "season", "league",
]


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Maps all CSV column names to internal standard names (case-insensitive)."""
    rename = {}
    for col in df.columns:
        key = col.strip().lower()
        if key in COLUMN_MAP:
            rename[col] = COLUMN_MAP[key]
    df = df.rename(columns=rename)
    return df


def _extract_season(date_str: str) -> str:
    """Extracts season string e.g. '2025-2026' from a date string."""
    if not date_str or pd.isna(date_str):
        return "Unknown"
    years = re.findall(r"\b(20\d{2})\b", str(date_str))
    if years:
        y = int(years[0])
        return f"{y}-{y+1}"
    return "Unknown"


def _clamp_possession(df: pd.DataFrame) -> pd.DataFrame:
    """Clamps possession values to [0, 100]."""
    for col in ["home_possession", "away_possession"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").clip(0, 100)
    return df


def load_csv(
    file_obj,
    league_name: str = "",
    season: str = "",
    *,
    country: str = "",
    championship: str = "",
) -> dict:
    """
    Main entry point for CSV/Excel ingestion.

    Args:
        file_obj: file path string OR file-like object (from st.file_uploader)
        league_name: full league label (es. "Argentina - Primera B")
        season: season string (e.g. "2025-2026")
        country: nazione (alternativa a league_name, combinata con championship)
        championship: nome campionato senza nazione

    Returns:
        {"rows_added": int, "rows_skipped": int, "errors": list[str]}
    """
    if country or championship:
        league_name = build_league_name(country, championship) or league_name
    league_name = (league_name or "").strip()
    if not league_name:
        return {
            "rows_added": 0,
            "rows_skipped": 0,
            "errors": ["Nazione e campionato obbligatori."],
        }

    init_db()
    errors = []

    # ── Read file ──────────────────────────────────────────────────────────
    try:
        fname = getattr(file_obj, "name", str(file_obj))
        if fname.endswith(".csv"):
            df = pd.read_csv(file_obj, encoding="utf-8", sep=None, engine="python")
        else:
            df = pd.read_excel(file_obj)
    except Exception as e:
        return {"rows_added": 0, "rows_skipped": 0, "errors": [f"Errore lettura file: {e}"]}

    # ── Normalize columns ─────────────────────────────────────────────────
    df = normalize_columns(df)

    # ── Validate minimum required columns ─────────────────────────────────
    required = ["home_team", "away_team", "match_date"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        return {
            "rows_added": 0, "rows_skipped": 0,
            "errors": [f"Colonne mancanti: {', '.join(missing)}"]
        }

    # ── Data cleaning ─────────────────────────────────────────────────────
    df = _clamp_possession(df)

    # ── Derived columns ───────────────────────────────────────────────────
    def safe_num(series, col):
        return pd.to_numeric(df[col], errors="coerce") if col in df.columns else pd.Series([np.nan] * len(df))

    home_goals_ft = safe_num(df, "home_goals_ft")
    away_goals_ft = safe_num(df, "away_goals_ft")
    home_goals_ht = safe_num(df, "home_goals_ht")
    away_goals_ht = safe_num(df, "away_goals_ht")

    df["ht_result"] = home_goals_ht.fillna(0).astype(int).astype(str) + "-" + away_goals_ht.fillna(0).astype(int).astype(str)
    df["ft_result"] = home_goals_ft.fillna(0).astype(int).astype(str) + "-" + away_goals_ft.fillna(0).astype(int).astype(str)
    df["goals_2h_home"] = (home_goals_ft - home_goals_ht).clip(lower=0)
    df["goals_2h_away"] = (away_goals_ft - away_goals_ht).clip(lower=0)
    df["total_goals_2h"] = df["goals_2h_home"] + df["goals_2h_away"]

    # Season from date if not provided or "Unknown"
    if not season or season.strip() == "":
        if "match_date" in df.columns:
            df["season"] = df["match_date"].apply(_extract_season)
        else:
            df["season"] = "Unknown"
    else:
        df["season"] = season

    df["league"] = league_name

    # ── Insert rows ───────────────────────────────────────────────────────
    conn = get_connection()
    rows_added = 0
    rows_skipped = 0

    placeholders = ", ".join(["?"] * len(DB_COLUMNS))
    col_names = ", ".join(DB_COLUMNS)
    insert_sql = f"INSERT OR IGNORE INTO matches ({col_names}) VALUES ({placeholders})"

    for _, row in df.iterrows():
        try:
            values = []
            for col in DB_COLUMNS:
                val = row.get(col, np.nan)
                if pd.isna(val) if not isinstance(val, str) else False:
                    values.append(None)
                else:
                    values.append(val)

            cur = conn.execute(insert_sql, values)
            if cur.rowcount > 0:
                match_id = cur.lastrowid
                rows_added += 1

                # Insert goal events
                _insert_goal_events(conn, match_id, row)
            else:
                rows_skipped += 1
        except Exception as e:
            rows_skipped += 1
            errors.append(str(e))

    # Register league
    try:
        conn.execute(
            "INSERT OR IGNORE INTO leagues (name, season) VALUES (?,?)",
            (league_name, season or "Unknown")
        )
    except Exception:
        pass

    conn.commit()
    conn.close()

    if rows_added > 0:
        try:
            from database import invalidate_db_cache
            invalidate_db_cache()
        except ImportError:
            pass

    return {"rows_added": rows_added, "rows_skipped": rows_skipped, "errors": errors}


def _insert_goal_events(conn: sqlite3.Connection, match_id: int, row):
    """Parses goal timings and inserts rows into goal_events table."""
    home_team = row.get("home_team", "")
    away_team = row.get("away_team", "")

    # parse_goal_timings now returns list of (minute, original_token) tuples
    home_timings = parse_goal_timings(row.get("home_goal_timings", None))
    away_timings = parse_goal_timings(row.get("away_goal_timings", None))

    for minute, token in home_timings:
        conn.execute(
            "INSERT INTO goal_events (match_id, team_name, is_home, minute, half) VALUES (?,?,?,?,?)",
            (match_id, home_team, 1, minute, get_half(minute, token))
        )

    for minute, token in away_timings:
        conn.execute(
            "INSERT INTO goal_events (match_id, team_name, is_home, minute, half) VALUES (?,?,?,?,?)",
            (match_id, away_team, 0, minute, get_half(minute, token))
        )