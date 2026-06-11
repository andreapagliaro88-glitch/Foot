"""
match_timeline.py — Aggregazione eventi gol, timeline, zone intensità, insight
"""

from __future__ import annotations

import pandas as pd

from utils import get_first_goal, parse_minutes

ZONE_LABELS = ("0-15", "16-30", "31-45", "46-60", "61-75", "76-90")
ZONE_RANGES = {
    "0-15": range(1, 16),
    "16-30": range(16, 31),
    "31-45": range(31, 46),
    "46-60": range(46, 61),
    "61-75": range(61, 76),
    "76-90": range(76, 91),
}


def _clamp_minute(minute: int) -> int:
    return min(max(int(minute), 1), 90)


def extract_events(row) -> list[dict]:
    """Estrae eventi gol da una riga match (home_goal_timings / away_goal_timings)."""
    home_str = row.get("home_goal_timings") or row.get("home_team_goal_timings") or ""
    away_str = row.get("away_goal_timings") or row.get("away_team_goal_timings") or ""
    events = []
    for minute in parse_minutes(home_str):
        events.append({"minute": _clamp_minute(minute), "team": "home"})
    for minute in parse_minutes(away_str):
        events.append({"minute": _clamp_minute(minute), "team": "away"})
    return sorted(events, key=lambda x: x["minute"])


def build_timeline(matches: pd.DataFrame) -> dict[int, int]:
    timeline = {i: 0 for i in range(1, 91)}
    if matches is None or matches.empty:
        return timeline
    for _, row in matches.iterrows():
        for event in extract_events(row):
            timeline[event["minute"]] += 1
    return timeline


def build_split_timeline(matches: pd.DataFrame) -> tuple[dict[int, int], dict[int, int]]:
    home_tl = {i: 0 for i in range(1, 91)}
    away_tl = {i: 0 for i in range(1, 91)}
    if matches is None or matches.empty:
        return home_tl, away_tl
    for _, row in matches.iterrows():
        home_str = row.get("home_goal_timings") or row.get("home_team_goal_timings") or ""
        away_str = row.get("away_goal_timings") or row.get("away_team_goal_timings") or ""
        for minute in parse_minutes(home_str):
            home_tl[_clamp_minute(minute)] += 1
        for minute in parse_minutes(away_str):
            away_tl[_clamp_minute(minute)] += 1
    return home_tl, away_tl


def build_intensity_zones(timeline: dict[int, int]) -> dict[str, int]:
    return {
        label: sum(timeline.get(i, 0) for i in ZONE_RANGES[label])
        for label in ZONE_LABELS
    }


def detect_key_moments(zones: dict[str, int]) -> dict[str, str]:
    if not zones or sum(zones.values()) == 0:
        return {"peak": "—", "low": "—"}
    best = max(zones, key=zones.get)
    worst = min(zones, key=zones.get)
    return {"peak": best, "low": worst}


def calculate_timeline_kpi(timeline: dict[int, int]) -> dict:
    total_goals = sum(timeline.values())
    first_half = sum(timeline.get(i, 0) for i in range(1, 46))
    second_half = sum(timeline.get(i, 0) for i in range(46, 91))
    avg_minute = (
        sum(m * c for m, c in timeline.items()) / total_goals
        if total_goals else 0
    )
    zones = build_intensity_zones(timeline)
    peak_val = max(zones.values()) if zones else 0
    intensity = round(peak_val / total_goals * 100, 1) if total_goals else 0.0
    return {
        "avg_minute": round(avg_minute, 1),
        "first_half_pct": round(first_half / total_goals * 100, 1) if total_goals else 0.0,
        "second_half_pct": round(second_half / total_goals * 100, 1) if total_goals else 0.0,
        "total_goals": total_goals,
        "intensity": intensity,
    }


def calculate_first_goal_avg(matches: pd.DataFrame) -> float:
    if matches is None or matches.empty:
        return 0.0
    first_goals = []
    for _, row in matches.iterrows():
        home_str = row.get("home_goal_timings") or row.get("home_team_goal_timings") or ""
        away_str = row.get("away_goal_timings") or row.get("away_team_goal_timings") or ""
        fg = get_first_goal(home_str, away_str)
        if fg is not None:
            first_goals.append(_clamp_minute(fg))
    return round(sum(first_goals) / len(first_goals), 1) if first_goals else 0.0


def generate_timeline_insight(kpi: dict, moments: dict) -> str:
    peak = moments.get("peak", "")
    if peak in ("0-15", "16-30"):
        return "⚡ Partite aggressive early → ideale per over live"
    if peak in ("61-75", "76-90"):
        return "🔥 Gol tardivi → perfetto per trading late"
    if kpi.get("second_half_pct", 0) > 58:
        return "📈 Il 2° tempo concentra più gol → valuta entry post-intervallo"
    if kpi.get("first_half_pct", 0) > 58:
        return "🌅 Primo tempo vivace → attenzione ai mercati HT"
    return "⚖️ Distribuzione equilibrata nel corso dei 90 minuti"


def collect_all_events(matches: pd.DataFrame) -> list[dict]:
    """Lista piatta di tutti gli eventi (per strip visiva)."""
    events = []
    if matches is None or matches.empty:
        return events
    for _, row in matches.iterrows():
        for event in extract_events(row):
            events.append(event)
    return events
