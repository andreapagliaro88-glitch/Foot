"""
team_dna.py — Profilo decisionale squadra (goal, difesa, ritmo, timing, insight)
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from utils import get_first_goal_detail, parse_minutes

DNA_ZONES = ("0-15", "16-30", "31-45", "46-60", "61-75", "76-90")


def _minute_to_zone(minute: int) -> str | None:
    m = int(minute)
    if 1 <= m <= 15:
        return "0-15"
    if 16 <= m <= 30:
        return "16-30"
    if 31 <= m <= 45:
        return "31-45"
    if 46 <= m <= 60:
        return "46-60"
    if 61 <= m <= 75:
        return "61-75"
    if m >= 76:
        return "76-90"
    return None


def _match_points(is_home: bool, h_ft: float, a_ft: float) -> int:
    if h_ft > a_ft:
        return 3 if is_home else 0
    if h_ft < a_ft:
        return 0 if is_home else 3
    return 1


def _derive_form(recent_points: list[int]) -> str:
    if not recent_points:
        return "N/D"
    avg = sum(recent_points) / len(recent_points)
    if avg >= 1.8:
        return "POSITIVA"
    if avg < 1.0:
        return "NEGATIVA"
    return "STABILE"


# Soglie confidenza — campione casa/trasferta è ~metà delle partite totali
_CONFIDENCE_THRESHOLDS = {
    "all":  {"alta": 40, "media": 20},
    "home": {"alta": 20, "media": 10},
    "away": {"alta": 20, "media": 10},
}


def _confidence_level(matches: int, venue: str | None = None) -> str:
    venue_key = venue if venue in ("home", "away") else "all"
    t = _CONFIDENCE_THRESHOLDS[venue_key]
    if matches >= t["alta"]:
        return "ALTA"
    if matches >= t["media"]:
        return "MEDIA"
    return "BASSA"


def calculate_team_style(stats: dict) -> dict:
    """
    Classifica stile squadra da 6 metriche fondamentali.
    Ritorna: style, tags, confidence, score.
    """
    avg_goals = float(stats.get("avg_goals", 0) or 0)
    over25 = float(stats.get("over25_pct", 0) or 0)
    btts = float(stats.get("btts_pct", 0) or 0)
    first_half = float(stats.get("first_half_pct", 0) or 0)
    late_goals = float(stats.get("late_goals_pct", 0) or 0)
    total = int(stats.get("matches", 0) or 0)
    venue = stats.get("venue")

    score = avg_goals * 10 + over25 * 0.4 + btts * 0.3 + first_half * 0.2

    if score >= 65:
        style = "OFFENSIVO"
    elif score >= 50:
        style = "EQUILIBRATO"
    else:
        style = "DIFENSIVO"

    tags: list[str] = []
    if first_half >= 60:
        tags.append("AGGRESSIVO EARLY")
    if late_goals >= 25:
        tags.append("LATE SCORER")
    if avg_goals < 2.0 and btts < 50:
        tags.append("CHIUSA")

    conf = _confidence_level(total, venue)

    return {
        "style": style,
        "tags": tags,
        "tag": tags[0] if tags else "",
        "confidence": conf,
        "score": round(score, 1),
        "confidence_matches": total,
    }


def _safe_odd(val) -> float | None:
    try:
        if val is None or (isinstance(val, float) and np.isnan(val)):
            return None
        v = float(val)
        return v if v > 1 else None
    except (TypeError, ValueError):
        return None


def _odds_profile_from_matches(subdf: pd.DataFrame, is_home: bool) -> dict:
    """Quota media e % favorita per partite in casa (is_home=True) o trasferta."""
    ctx = "in casa" if is_home else "in trasferta"
    team_odds: list[float] = []
    favorite_n = underdog_n = 0
    compared_n = 0

    for _, row in subdf.iterrows():
        oh = _safe_odd(row.get("odds_home"))
        oa = _safe_odd(row.get("odds_away"))
        team_o = oh if is_home else oa
        opp_o = oa if is_home else oh
        if team_o is None:
            continue
        team_odds.append(team_o)
        if opp_o is not None:
            compared_n += 1
            if team_o < opp_o:
                favorite_n += 1
            elif team_o > opp_o:
                underdog_n += 1

    n = len(team_odds)
    if n == 0:
        return {"has_data": False, "context": ctx}

    fav_pct = round(favorite_n / compared_n * 100, 1) if compared_n else 0.0
    dog_pct = round(underdog_n / compared_n * 100, 1) if compared_n else 0.0
    if compared_n and fav_pct >= 55:
        role = "FAVORITA"
    elif compared_n and dog_pct >= 55:
        role = "SFAVORITA"
    else:
        role = "EQUILIBRATA"

    return {
        "has_data": True,
        "context": ctx,
        "avg_odds": round(float(np.mean(team_odds)), 2),
        "favorite_pct": fav_pct,
        "underdog_pct": dog_pct,
        "market_role": role,
        "matches_with_odds": n,
    }


def _build_odds_market(tdf: pd.DataFrame, team_name: str, venue: str) -> dict:
    home_df = tdf[tdf["home_team"] == team_name] if venue in ("all", "home") else tdf.iloc[0:0]
    away_df = tdf[tdf["away_team"] == team_name] if venue in ("all", "away") else tdf.iloc[0:0]
    if venue == "home":
        home_df = tdf
    elif venue == "away":
        away_df = tdf

    home_prof = _odds_profile_from_matches(home_df, is_home=True)
    away_prof = _odds_profile_from_matches(away_df, is_home=False)
    if venue == "home":
        primary = home_prof
    elif venue == "away":
        primary = away_prof
    else:
        primary = home_prof if home_prof.get("has_data") else away_prof

    return {
        "home": home_prof,
        "away": away_prof,
        "primary": primary,
        "has_data": home_prof.get("has_data") or away_prof.get("has_data"),
    }


def _market_flat(odds_market: dict) -> dict:
    primary = odds_market.get("primary") or {}
    if not primary.get("has_data"):
        return {
            "avg_odds": 0.0,
            "favorite_pct": 0.0,
            "underdog_pct": 0.0,
            "has_data": False,
        }
    return {
        "avg_odds": primary.get("avg_odds", 0.0),
        "favorite_pct": primary.get("favorite_pct", 0.0),
        "underdog_pct": primary.get("underdog_pct", 0.0),
        "market_role": primary.get("market_role", "—"),
        "has_data": True,
    }


def _events_for_team(row, team_name: str, goal_events: dict) -> tuple[list, list]:
    """Ritorna (gol_fatti, gol_subiti) come liste di minuti."""
    is_home = row.get("home_team") == team_name
    mid = row.get("match_id")
    if mid is not None and goal_events:
        events = goal_events.get(int(mid), [])
        if events:
            scored, conceded = [], []
            for e in events:
                m = e.get("minute", 0)
                try:
                    minute = int(m)
                except (TypeError, ValueError):
                    continue
                if (e.get("is_home") == 1) == is_home:
                    scored.append(minute)
                else:
                    conceded.append(minute)
            return scored, conceded

    home_t = str(row.get("home_goal_timings") or "")
    away_t = str(row.get("away_goal_timings") or "")
    if is_home:
        return parse_minutes(home_t), parse_minutes(away_t)
    return parse_minutes(away_t), parse_minutes(home_t)


_VENUE_LABELS = {
    "all": "Tutte le partite",
    "home": "Solo in casa",
    "away": "Solo in trasferta",
}


def analyze_team_dna(
    df: pd.DataFrame,
    team_name: str,
    goal_events: dict | None = None,
    last_n: int | None = None,
    venue: str | None = None,
) -> dict:
    """
    Analisi DNA squadra.
    venue: None/'all' = tutte, 'home' = solo casa, 'away' = solo trasferta.
    goal_events: dict match_id -> eventi (opzionale, migliora timing).
    """
    goal_events = goal_events or {}
    empty = {
        "team": team_name,
        "matches": 0,
        "form": "N/D",
        "style": "N/D",
        "style_profile": {},
        "goal_profile": {},
        "defensive": {},
        "rhythm": {},
        "timing": {},
        "odds_market": {},
        "market": {},
        "interpretation": {"positives": [], "risks": [], "summary": ""},
        "venue": venue or "all",
        "venue_label": _VENUE_LABELS.get(venue or "all", "Tutte le partite"),
    }
    if df is None or df.empty or not team_name:
        return empty

    if venue == "home":
        tdf = df[df["home_team"] == team_name].copy()
    elif venue == "away":
        tdf = df[df["away_team"] == team_name].copy()
    else:
        tdf = df[(df["home_team"] == team_name) | (df["away_team"] == team_name)].copy()
    if "match_date" in tdf.columns:
        tdf["match_date"] = pd.to_datetime(tdf["match_date"], errors="coerce")
        tdf = tdf.sort_values("match_date", ascending=False)

    if last_n and last_n > 0:
        tdf = tdf.head(int(last_n))

    n = len(tdf)
    if n == 0:
        return empty

    scored_1h_n = scored_2h_n = scored_first_n = 0
    clean_sheets = concede_n = concede_2h_n = concede_after_75_n = 0
    over_25_n = btts_n = 0
    total_scored = total_conceded = 0.0
    goal_minutes: list[int] = []
    late_goals_n = 0
    zone_counts = {z: 0 for z in DNA_ZONES}
    recent_points: list[int] = []

    for _, row in tdf.iterrows():
        is_home = row.get("home_team") == team_name
        h_ft = float(pd.to_numeric(row.get("home_goals_ft"), errors="coerce") or 0)
        a_ft = float(pd.to_numeric(row.get("away_goals_ft"), errors="coerce") or 0)
        h_ht = float(pd.to_numeric(row.get("home_goals_ht"), errors="coerce") or 0)
        a_ht = float(pd.to_numeric(row.get("away_goals_ht"), errors="coerce") or 0)

        scored = h_ft if is_home else a_ft
        conceded = a_ft if is_home else h_ft
        scored_ht = h_ht if is_home else a_ht
        scored_2h = max(scored - scored_ht, 0)
        conceded_ht = a_ht if is_home else h_ht
        conceded_2h = max(conceded - conceded_ht, 0)

        total_scored += scored
        total_conceded += conceded
        recent_points.append(_match_points(is_home, h_ft, a_ft))

        if scored_ht >= 1:
            scored_1h_n += 1
        if scored_2h >= 1:
            scored_2h_n += 1

        home_t = str(row.get("home_goal_timings") or "")
        away_t = str(row.get("away_goal_timings") or "")
        first, first_team, _ = get_first_goal_detail(home_t, away_t)
        if first is not None:
            if (first_team == "home" and is_home) or (first_team == "away" and not is_home):
                scored_first_n += 1

        if conceded == 0:
            clean_sheets += 1
        else:
            concede_n += 1
        if conceded_2h >= 1:
            concede_2h_n += 1

        _, opp_goals = _events_for_team(row, team_name, goal_events)
        if opp_goals and any(m >= 76 for m in opp_goals):
            concede_after_75_n += 1

        if (h_ft + a_ft) >= 3:
            over_25_n += 1
        if h_ft >= 1 and a_ft >= 1:
            btts_n += 1

        team_goals, _ = _events_for_team(row, team_name, goal_events)
        for m in team_goals:
            goal_minutes.append(m)
            if m >= 76:
                late_goals_n += 1
            zone = _minute_to_zone(m)
            if zone:
                zone_counts[zone] += 1

    matches_with_first_data = sum(
        1 for _, r in tdf.iterrows()
        if get_first_goal_detail(str(r.get("home_goal_timings") or ""), str(r.get("away_goal_timings") or ""))[0]
        is not None
    )

    zone_total = sum(zone_counts.values()) or 1
    timing_pct = {z: round(zone_counts[z] / zone_total * 100, 1) for z in DNA_ZONES}
    peak_zone = max(timing_pct, key=timing_pct.get) if zone_total > 0 else "—"
    low_zone = min(timing_pct, key=timing_pct.get) if zone_total > 0 else "—"

    avg_scored = total_scored / n
    avg_conceded = total_conceded / n
    over_25_pct = round(over_25_n / n * 100, 1)
    btts_pct = round(btts_n / n * 100, 1)
    clean_sheet_pct = round(clean_sheets / n * 100, 1)

    form = _derive_form(recent_points[:10])
    avg_goal_min = round(float(np.mean(goal_minutes)), 1) if goal_minutes else float("nan")
    concede_2h_pct = round(concede_2h_n / concede_n * 100, 1) if concede_n else 0.0
    score_1h_pct = round(scored_1h_n / n * 100, 1)
    score_first_pct = round(scored_first_n / matches_with_first_data * 100, 1) if matches_with_first_data else 0.0
    avg_goals_match = round((total_scored + total_conceded) / n, 2)
    late_goals_pct = round(late_goals_n / len(goal_minutes) * 100, 1) if goal_minutes else 0.0

    venue_key = venue or "all"
    odds_market = _build_odds_market(tdf, team_name, venue_key)
    market = _market_flat(odds_market)

    style_profile = calculate_team_style({
        "avg_goals": avg_goals_match,
        "over25_pct": over_25_pct,
        "btts_pct": btts_pct,
        "first_goal_pct": score_first_pct,
        "first_half_pct": score_1h_pct,
        "late_goals_pct": late_goals_pct,
        "matches": n,
        "venue": venue_key,
    })

    dna = {
        "team": team_name,
        "matches": n,
        "venue": venue or "all",
        "venue_label": _VENUE_LABELS.get(venue or "all", "Tutte le partite"),
        "form": form,
        "style": style_profile["style"],
        "style_profile": style_profile,
        "goal_profile": {
            "score_1h_pct": score_1h_pct,
            "score_first_pct": score_first_pct,
            "avg_goal_minute": avg_goal_min,
            "score_2h_pct": round(scored_2h_n / n * 100, 1),
            "avg_scored": round(avg_scored, 2),
            "late_goals_pct": late_goals_pct,
        },
        "defensive": {
            "clean_sheet_pct": clean_sheet_pct,
            "concede_pct": round(concede_n / n * 100, 1),
            "concede_2h_pct": concede_2h_pct,
            "concede_after_75_pct": round(concede_after_75_n / n * 100, 1),
            "avg_conceded": round(avg_conceded, 2),
        },
        "rhythm": {
            "over_25_pct": over_25_pct,
            "btts_pct": btts_pct,
            "under_25_pct": round(100 - over_25_pct, 1),
            "avg_goals": avg_goals_match,
        },
        "timing": {
            "zones": timing_pct,
            "peak": peak_zone,
            "low": low_zone,
            "total_goals": zone_total,
        },
        "odds_market": odds_market,
        "market": market,
        "recent_form_pts": round(sum(recent_points[:10]) / min(len(recent_points), 10), 2) if recent_points else 0,
    }
    dna["interpretation"] = generate_dna_interpretation(dna)
    return dna


def generate_dna_interpretation(dna: dict) -> dict:
    gp = dna.get("goal_profile", {})
    df = dna.get("defensive", {})
    rh = dna.get("rhythm", {})
    tm = dna.get("timing", {})
    positives: list[str] = []
    risks: list[str] = []

    if gp.get("score_1h_pct", 0) >= 60:
        positives.append("Squadra che parte forte")
    if gp.get("score_first_pct", 0) >= 55:
        positives.append("Alta probabilità di segnare per prima")
    if rh.get("over_25_pct", 0) >= 58:
        positives.append("Match tendente OVER")
    if rh.get("btts_pct", 0) >= 55:
        positives.append("BTTS frequente nelle partite")

    peak = tm.get("peak", "")
    if peak in ("31-45", "46-60", "16-30"):
        positives.append(f"Gol concentrati nella fascia {peak}")

    if df.get("concede_2h_pct", 0) >= 60:
        risks.append("Subisce spesso nel 2° tempo")
    if df.get("concede_after_75_pct", 0) >= 28:
        risks.append("Calo / vulnerabilità dopo 75'")
    if df.get("clean_sheet_pct", 0) < 25 and dna.get("style") == "OFFENSIVO":
        risks.append("Pochi clean sheet — espone il match")
    if rh.get("under_25_pct", 0) >= 55 and not positives:
        risks.append("Ritmo spesso basso — attenzione agli under")

    if dna.get("form") == "POSITIVA":
        positives.append("Forma recente positiva (ultime 10)")
    elif dna.get("form") == "NEGATIVA":
        risks.append("Forma recente negativa")

    sp = dna.get("style_profile", {})
    tags = sp.get("tags", [])
    style = sp.get("style", dna.get("style", ""))

    if "AGGRESSIVO EARLY" in tags:
        positives.append("Partenza forte — aggressiva nel 1° tempo")
    if "LATE SCORER" in tags:
        positives.append("Gol tardivi frequenti — utile per trading late")
    if "CHIUSA" in tags:
        risks.append("Match spesso bloccati — bassa intensità")

    if style == "OFFENSIVO":
        summary = "Profilo offensivo — ideale per mercati gol e live over"
    elif style == "DIFENSIVO":
        summary = "Profilo difensivo — valuta under e lay over con cautela"
    else:
        summary = "Profilo equilibrato — attendi trigger live chiari"

    if gp.get("score_1h_pct", 0) < 40 and style == "DIFENSIVO":
        risks.append("Segna poco nel 1° tempo")

    mk = dna.get("market", {})
    if mk.get("has_data"):
        if mk.get("favorite_pct", 0) >= 58:
            positives.append(f"Spesso favorita al kickoff ({mk['favorite_pct']}%)")
        elif mk.get("underdog_pct", 0) >= 58:
            risks.append(f"Spesso sfavorita al kickoff ({mk['underdog_pct']}%)")

    if not positives:
        positives.append("Profilo misto — analizza matchup specifico")
    if not risks:
        risks.append("Nessun rischio strutturale evidente")

    return {"positives": positives[:5], "risks": risks[:4], "summary": summary}


# Confronto: solo rosso se peggiore — mai verde su queste metriche
DNA_RED_ONLY_METRICS: frozenset[tuple[str, str]] = frozenset({
    ("market", "underdog_pct"),
    ("defensive", "clean_sheet_pct"),
    ("defensive", "concede_pct"),
    ("defensive", "concede_2h_pct"),
    ("defensive", "concede_after_75_pct"),
    ("defensive", "avg_conceded"),
})


DNA_COMPARE_METRICS: tuple[tuple[str, str, str, str, bool], ...] = (
    ("goal_profile", "score_1h_pct", "Segna 1° tempo", "%", True),
    ("goal_profile", "score_first_pct", "Segna per prima", "%", True),
    ("goal_profile", "score_2h_pct", "Segna 2° tempo", "%", True),
    ("goal_profile", "avg_scored", "Media gol fatti", "", True),
    ("defensive", "clean_sheet_pct", "Clean sheet", "%", True),
    ("defensive", "concede_pct", "Subisce gol", "%", False),
    ("defensive", "concede_2h_pct", "Subisce nel 2° tempo", "%", False),
    ("defensive", "concede_after_75_pct", "Subisce dopo 75'", "%", False),
    ("defensive", "avg_conceded", "Media gol subiti", "", False),
    ("rhythm", "over_25_pct", "Over 2.5", "%", True),
    ("rhythm", "btts_pct", "BTTS", "%", True),
    ("rhythm", "under_25_pct", "Under 2.5", "%", False),
    ("rhythm", "avg_goals", "Media gol match", "", True),
    ("market", "avg_odds", "Quota media 1X2", "", False),
    ("market", "favorite_pct", "% da favorita", "%", True),
    ("market", "underdog_pct", "% da sfavorita", "%", False),
)


def _dna_scalar(dna: dict, section: str, key: str):
    if section == "_root":
        return dna.get(key, 0)
    return dna.get(section, {}).get(key, 0)


def build_dna_compare_rows(dna_a: dict, dna_b: dict, name_a: str, name_b: str) -> list[dict]:
    rows = []
    for section, key, label, suffix, higher_better in DNA_COMPARE_METRICS:
        va = _dna_scalar(dna_a, section, key)
        vb = _dna_scalar(dna_b, section, key)
        try:
            fa, fb = float(va), float(vb)
        except (TypeError, ValueError):
            fa, fb = 0.0, 0.0
        if fa > fb:
            winner = "a"
        elif fb > fa:
            winner = "b"
        else:
            winner = "tie"
        if not higher_better and winner in ("a", "b"):
            winner = "b" if winner == "a" else "a"
        rows.append({
            "label": label,
            "value_a": fa,
            "value_b": fb,
            "suffix": suffix,
            "winner": winner,
            "name_a": name_a,
            "name_b": name_b,
        })

    fa = float(dna_a.get("recent_form_pts", 0) or 0)
    fb = float(dna_b.get("recent_form_pts", 0) or 0)
    rows.insert(0, {
        "label": "Forma (pt/partita ultime 10)",
        "value_a": fa,
        "value_b": fb,
        "suffix": "",
        "winner": "a" if fa > fb else ("b" if fb > fa else "tie"),
        "name_a": name_a,
        "name_b": name_b,
    })
    return rows


def _compare_result(va: float, vb: float, higher_better: bool = True) -> str:
    """Ritorna 'a', 'b' o 'tie'."""
    if round(va, 2) == round(vb, 2):
        return "tie"
    if va > vb:
        raw = "a"
    elif vb > va:
        raw = "b"
    else:
        return "tie"
    if not higher_better:
        return "b" if raw == "a" else "a"
    return raw


def build_dna_highlight_map(dna_a: dict, dna_b: dict) -> dict[str, str]:
    """Mappa section.key → 'a' | 'b' | 'tie'."""
    highlights: dict[str, str] = {}

    for section, key, _label, _suffix, higher_better in DNA_COMPARE_METRICS:
        try:
            fa = float(_dna_scalar(dna_a, section, key) or 0)
            fb = float(_dna_scalar(dna_b, section, key) or 0)
        except (TypeError, ValueError):
            continue
        highlights[f"{section}.{key}"] = _compare_result(fa, fb, higher_better)

    am = dna_a.get("goal_profile", {}).get("avg_goal_minute")
    bm = dna_b.get("goal_profile", {}).get("avg_goal_minute")
    try:
        if am == am and bm == bm:
            highlights["goal_profile.avg_goal_minute"] = _compare_result(
                float(am), float(bm), higher_better=False,
            )
    except (TypeError, ValueError):
        pass

    for zone in DNA_ZONES:
        fa = float(dna_a.get("timing", {}).get("zones", {}).get(zone, 0) or 0)
        fb = float(dna_b.get("timing", {}).get("zones", {}).get(zone, 0) or 0)
        highlights[f"timing.{zone}"] = _compare_result(fa, fb, True)

    try:
        fa = float(dna_a.get("recent_form_pts", 0) or 0)
        fb = float(dna_b.get("recent_form_pts", 0) or 0)
        highlights["_root.recent_form_pts"] = _compare_result(fa, fb, True)
    except (TypeError, ValueError):
        pass

    return highlights


def compare_dna_verdict(rows: list[dict], name_a: str, name_b: str) -> dict:
    wins_a = sum(1 for r in rows if r["winner"] == "a")
    wins_b = sum(1 for r in rows if r["winner"] == "b")
    if wins_a > wins_b:
        edge = name_a
    elif wins_b > wins_a:
        edge = name_b
    else:
        edge = None
    return {"wins_a": wins_a, "wins_b": wins_b, "edge": edge, "ties": len(rows) - wins_a - wins_b}
