"""
calculations.py — All stats, percentages, ROI simulations, live analysis, H2H
"""

import pandas as pd
import numpy as np
from utils import (
    get_half,
    get_first_goal_from_events,
    parse_goal_minute_value,
    parse_goal_timings,
    get_all_goals,
    get_sorted_goals_with_team,
)


def _parse_minute(raw) -> int:
    """Convert goal minute token to int; invalid values -> 0."""
    minute = parse_goal_minute_value(raw)
    return minute if minute is not None else 0


BUCKETS = {
    "1-15":  (1, 15),
    "16-30": (16, 30),
    "31-45": (31, 45),
    "45+":   (46, 999),
    "46-60": (46, 60),
    "61-75": (61, 75),
    "76-90": (76, 90),
    "90+":   (91, 999),
}


def _safe_pct(numerator, denominator) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator * 100, 1)


def _safe_odd(val):
    """Return odds as float if valid (>1), else None. Skips non-numeric values."""
    try:
        if val is None or (isinstance(val, float) and np.isnan(val)):
            return None
        v = float(val)
        return v if v > 1 else None
    except (ValueError, TypeError):
        return None


def _odds_from_matched(matched, col):
    vals = []
    for m in matched:
        o = _safe_odd(m["row"].get(col))
        if o is not None:
            vals.append(o)
    return vals


def _roi(wins: int, total: int, avg_odds: float) -> float:
    if total == 0 or avg_odds is None or (isinstance(avg_odds, float) and np.isnan(avg_odds)):
        return float("nan")
    losses = total - wins
    profit = wins * (avg_odds - 1) - losses * 1
    return round(profit / total * 100, 1)


def _lay_odds(back_odds: float) -> float:
    if back_odds is None or back_odds <= 1:
        return float("nan")
    return 1 / (1 - 1 / back_odds)


def _lay_roi(lay_wins: int, lay_losses: int, avg_back_odds: float) -> float:
    """Lay ROI (Andrea spec): liability = back_odds - 1;
    profit = lay_wins * 1 - lay_losses * liability;  ROI = profit / total * 100."""
    total = lay_wins + lay_losses
    if total == 0 or avg_back_odds is None or (isinstance(avg_back_odds, float) and np.isnan(avg_back_odds)):
        return float("nan")
    liability = avg_back_odds - 1.0
    profit = lay_wins * 1.0 - lay_losses * liability
    return round(profit / total * 100, 1)


LAY_00_MIN_ODDS = 10.0


def estimate_lay_00_odds(
    df: pd.DataFrame,
    min_odds: float = LAY_00_MIN_ODDS,
    default: float = 12.0,
) -> float:
    """Quota back sullo 0-0 stimata dalla frequenza nel campione (min. 10 come mercato reale)."""
    if df is None or df.empty:
        return default
    hg = pd.to_numeric(df.get("home_goals_ft"), errors="coerce")
    ag = pd.to_numeric(df.get("away_goals_ft"), errors="coerce")
    mask = hg.notna() & ag.notna()
    n = int(mask.sum())
    if n == 0:
        return default
    p_00 = float(((hg[mask] == 0) & (ag[mask] == 0)).sum()) / n
    if p_00 <= 0:
        return max(min_odds, default)
    return max(min_odds, round(1.0 / p_00, 2))


def analyze_matches(df: pd.DataFrame) -> dict:
    if df is None or len(df) == 0:
        return {}

    n = len(df)

    home_g = pd.to_numeric(df["home_goals_ft"], errors="coerce").fillna(0)
    away_g = pd.to_numeric(df["away_goals_ft"], errors="coerce").fillna(0)
    total_goals = pd.to_numeric(df["total_goals_ft"], errors="coerce").fillna(home_g + away_g)
    total_ht = pd.to_numeric(df["total_goals_ht"], errors="coerce").fillna(0)
    total_2h = pd.to_numeric(df["total_goals_2h"], errors="coerce").fillna(0)

    home_wins = int((home_g > away_g).sum())
    draws      = int((home_g == away_g).sum())
    away_wins  = int((home_g < away_g).sum())

    over_05_ft = int((total_goals >= 1).sum())
    over_15_ft = int((total_goals >= 2).sum())
    over_25_ft = int((total_goals >= 3).sum())
    over_35_ft = int((total_goals >= 4).sum())
    over_45_ft = int((total_goals >= 5).sum())
    btts        = int(((home_g >= 1) & (away_g >= 1)).sum())

    over_05_ht = int((total_ht >= 1).sum())
    over_15_ht = int((total_ht >= 2).sum())

    over_05_2h  = int((total_2h >= 1).sum())
    over_15_2h  = int((total_2h >= 2).sum())
    zero_2h     = int((total_2h == 0).sum())

    total_all  = float(total_goals.sum())
    goals_1h_pct = _safe_pct(float(total_ht.sum()), total_all)
    goals_2h_pct = _safe_pct(float(total_2h.sum()), total_all)

    # ROI 1 — Home win
    odds_h = pd.to_numeric(df["odds_home"], errors="coerce")
    valid_h = df[odds_h.notna()].copy()
    vhg = pd.to_numeric(valid_h["home_goals_ft"], errors="coerce").fillna(0)
    vag = pd.to_numeric(valid_h["away_goals_ft"], errors="coerce").fillna(0)
    roi_hw_w = int((vhg > vag).sum())
    roi_hw   = _roi(roi_hw_w, len(valid_h), float(odds_h.dropna().mean()) if len(odds_h.dropna()) else float("nan"))
    roi_hw_l = len(valid_h) - roi_hw_w

    # ROI 2 — Lay home (liability model: win +1 unit, lose -(odds-1))
    avg_back_h = float(odds_h.dropna().mean()) if len(odds_h.dropna()) else float("nan")
    roi_lh_w = int((vhg <= vag).sum())          # lay wins  = home did NOT win
    roi_lh_l = len(valid_h) - roi_lh_w           # lay losses = home won
    roi_lh   = _lay_roi(roi_lh_w, roi_lh_l, avg_back_h)

    # ROI 3 — Over 0.5 2H
    odds_o15 = pd.to_numeric(df["odds_over15"], errors="coerce")
    valid_2h = df[odds_o15.notna()].copy()
    v2h_goals = pd.to_numeric(valid_2h["total_goals_2h"], errors="coerce").fillna(0)
    roi_2h_w = int((v2h_goals >= 1).sum())
    roi_2h   = _roi(roi_2h_w, len(valid_2h), float(odds_o15.dropna().mean()) if len(odds_o15.dropna()) else float("nan"))
    roi_2h_l = len(valid_2h) - roi_2h_w

    # ROI 4 — Lay 0-0 (quota stimata da freq. 0-0, min 10 — non usa BTTS No)
    hg_raw = pd.to_numeric(df["home_goals_ft"], errors="coerce")
    ag_raw = pd.to_numeric(df["away_goals_ft"], errors="coerce")
    settled = hg_raw.notna() & ag_raw.notna()
    avg_back_00 = estimate_lay_00_odds(df)
    is_0_0 = (hg_raw[settled] == 0) & (ag_raw[settled] == 0)
    roi_00_l = int(is_0_0.sum())
    roi_00_w = int(settled.sum()) - roi_00_l
    roi_00   = _lay_roi(roi_00_w, roi_00_l, avg_back_00)

    return {
        "match_count":        n,
        "home_win_pct":       _safe_pct(home_wins, n),
        "draw_pct":           _safe_pct(draws, n),
        "away_win_pct":       _safe_pct(away_wins, n),
        "over_05_ft_pct":     _safe_pct(over_05_ft, n),
        "over_15_ft_pct":     _safe_pct(over_15_ft, n),
        "over_25_ft_pct":     _safe_pct(over_25_ft, n),
        "over_35_ft_pct":     _safe_pct(over_35_ft, n),
        "over_45_ft_pct":     _safe_pct(over_45_ft, n),
        "btts_pct":           _safe_pct(btts, n),
        "avg_goals_ft":       round(float(total_goals.mean()), 2),
        "over_05_ht_pct":     _safe_pct(over_05_ht, n),
        "over_15_ht_pct":     _safe_pct(over_15_ht, n),
        "avg_goals_ht":       round(float(total_ht.mean()), 2),
        "over_05_2h_pct":     _safe_pct(over_05_2h, n),
        "over_15_2h_pct":     _safe_pct(over_15_2h, n),
        "at_least_1_2h_pct":  _safe_pct(over_05_2h, n),
        "zero_goals_2h_pct":  _safe_pct(zero_2h, n),
        "avg_goals_2h":       round(float(total_2h.mean()), 2),
        "goals_1h_pct":       goals_1h_pct,
        "goals_2h_pct":       goals_2h_pct,
        "timing_dist":        {k: 0.0 for k in BUCKETS},
        "avg_first_goal":     float("nan"),
        "roi_home_win":       roi_hw,
        "roi_home_wins":      roi_hw_w,
        "roi_home_losses":    roi_hw_l,
        "roi_lay_home":       roi_lh,
        "roi_lay_home_wins":  roi_lh_w,
        "roi_lay_home_losses":roi_lh_l,
        "roi_over_05_2h":     roi_2h,
        "roi_2h_wins":        roi_2h_w,
        "roi_2h_losses":      roi_2h_l,
        "roi_lay_00":         roi_00,
        "roi_00_wins":        roi_00_w,
        "roi_00_losses":      roi_00_l,
    }


def enrich_with_goal_events(results: dict, goal_events: dict, match_ids: list) -> dict:
    timing_dist = {k: 0 for k in BUCKETS}
    first_goals = []

    for mid in match_ids:
        events = goal_events.get(int(mid), [])
        if not events:
            continue
        fg = get_first_goal_from_events(events)
        if fg:
            first_goals.append(fg["minute"])
        for e in events:
            m    = _parse_minute(e["minute"])
            half = e.get("half", 1 if m <= 45 else 2)
            # injury time 1st half
            if half == 1 and m > 45:
                timing_dist["45+"] += 1
            # injury time 2nd half
            elif half == 2 and m > 90:
                timing_dist["90+"] += 1
            else:
                for bucket_name, (lo, hi) in BUCKETS.items():
                    if bucket_name in ("45+", "90+"):
                        continue
                    if lo <= m <= hi:
                        timing_dist[bucket_name] += 1
                        break

    total_goals = sum(timing_dist.values())
    timing_pct = {
        k: round(v / total_goals * 100, 1) if total_goals > 0 else 0.0
        for k, v in timing_dist.items()
    }
    results["timing_dist"] = timing_pct
    results["timing_raw"]  = timing_dist
    results["avg_first_goal"] = round(float(np.mean(first_goals)), 1) if first_goals else float("nan")
    return results


def analyze_live_state(df: pd.DataFrame, goal_events: dict, from_minute: int,
                       home_score: int, away_score: int) -> dict:
    matched = []
    for _, row in df.iterrows():
        mid = row.get("match_id")
        if mid is None:
            continue
        events = goal_events.get(int(mid), [])
        home_b = sum(1 for e in events if e["is_home"] == 1 and _parse_minute(e["minute"]) <= from_minute)
        away_b = sum(1 for e in events if e["is_home"] == 0 and _parse_minute(e["minute"]) <= from_minute)
        if home_b == home_score and away_b == away_score:
            matched.append({"row": row, "goals_after": [e for e in events if _parse_minute(e["minute"]) > from_minute]})

    n = len(matched)
    if n == 0:
        return {"found": 0}

    final_res = {"home_win": 0, "draw": 0, "away_win": 0}
    goals_added = {0: 0, 1: 0, 2: 0, 3: 0}
    next_by = {"home": 0, "away": 0, "none": 0}
    next_win = {"46-60": 0, "61-75": 0, "76-90": 0, "none": 0}
    score_dist = {}

    for m in matched:
        row = m["row"]
        ga  = m["goals_after"]
        hf  = float(row.get("home_goals_ft") or 0)
        af  = float(row.get("away_goals_ft") or 0)
        if hf > af:
            final_res["home_win"] += 1
        elif hf == af:
            final_res["draw"] += 1
        else:
            final_res["away_win"] += 1

        key = f"{int(hf)}-{int(af)}"
        score_dist[key] = score_dist.get(key, 0) + 1
        goals_added[min(len(ga), 3)] += 1

        if ga:
            first = sorted(ga, key=lambda e: _parse_minute(e["minute"]))[0]
            next_by["home" if first["is_home"] == 1 else "away"] += 1
            mn = _parse_minute(first["minute"])
            if 46 <= mn <= 60:
                next_win["46-60"] += 1
            elif 61 <= mn <= 75:
                next_win["61-75"] += 1
            else:
                next_win["76-90"] += 1
        else:
            next_by["none"] += 1
            next_win["none"] += 1

    top_scores = sorted(score_dist.items(), key=lambda x: x[1], reverse=True)[:8]

    return {
        "found":           n,
        "home_win_pct":    _safe_pct(final_res["home_win"], n),
        "draw_pct":        _safe_pct(final_res["draw"], n),
        "away_win_pct":    _safe_pct(final_res["away_win"], n),
        "no_more_goals":   _safe_pct(goals_added[0], n),
        "one_more":        _safe_pct(goals_added[1], n),
        "two_or_more":     _safe_pct(goals_added[2] + goals_added[3], n),
        "next_goal_home":  _safe_pct(next_by["home"], n),
        "next_goal_away":  _safe_pct(next_by["away"], n),
        "next_goal_none":  _safe_pct(next_by["none"], n),
        "next_goal_46_60": _safe_pct(next_win["46-60"], n),
        "next_goal_61_75": _safe_pct(next_win["61-75"], n),
        "next_goal_76_90": _safe_pct(next_win["76-90"], n),
        "top_scores":      top_scores,
        "at_least_one_more_pct": _safe_pct(n - goals_added[0], n),
        "most_likely_ft":  top_scores[0][0] if top_scores else "N/A",
    }


H2H_MINUTE_BUCKETS = ["0-15", "16-30", "31-45", "46-60", "61-75", "76-90+"]


def _h2h_minute_bucket(minute: int) -> str:
    if minute <= 15:
        return "0-15"
    if minute <= 30:
        return "16-30"
    if minute <= 45:
        return "31-45"
    if minute <= 60:
        return "46-60"
    if minute <= 75:
        return "61-75"
    return "76-90+"


def _h2h_team_result_label(h_goals: float, a_goals: float, home_sel: str, away_sel: str, match_home: str) -> str:
    if match_home == home_sel:
        th, ta = h_goals, a_goals
    else:
        th, ta = a_goals, h_goals
    if th > ta:
        return home_sel
    if th == ta:
        return "Pareggio"
    return away_sel


def analyze_h2h(df: pd.DataFrame, home: str, away: str) -> dict:
    h2h = df[
        ((df["home_team"] == home) & (df["away_team"] == away)) |
        ((df["home_team"] == away) & (df["away_team"] == home))
    ].copy()

    n = len(h2h)
    if n == 0:
        return {"found": 0}

    h2h = h2h.sort_values("match_date", ascending=False)
    home_wins = draws = away_wins = 0
    home_goals_scored = away_goals_scored = 0.0
    minute_home = {k: 0 for k in H2H_MINUTE_BUCKETS}
    minute_away = {k: 0 for k in H2H_MINUTE_BUCKETS}
    ht_ft_counts: dict[str, int] = {}

    for _, row in h2h.iterrows():
        hg = float(row.get("home_goals_ft") or 0)
        ag = float(row.get("away_goals_ft") or 0)
        hht = float(row.get("home_goals_ht") or row.get("home_team_goal_count_half_time") or 0)
        aht = float(row.get("away_goals_ht") or row.get("away_team_goal_count_half_time") or 0)

        if row["home_team"] == home:
            if hg > ag:
                home_wins += 1
            elif hg == ag:
                draws += 1
            else:
                away_wins += 1
            home_goals_scored += hg
            away_goals_scored += ag
            home_timings = str(row.get("home_goal_timings") or "")
            away_timings = str(row.get("away_goal_timings") or "")
        else:
            if ag > hg:
                home_wins += 1
            elif hg == ag:
                draws += 1
            else:
                away_wins += 1
            home_goals_scored += ag
            away_goals_scored += hg
            home_timings = str(row.get("away_goal_timings") or "")
            away_timings = str(row.get("home_goal_timings") or "")

        for minute, _ in parse_goal_timings(home_timings):
            minute_home[_h2h_minute_bucket(minute)] += 1
        for minute, _ in parse_goal_timings(away_timings):
            minute_away[_h2h_minute_bucket(minute)] += 1

        ht_lbl = _h2h_team_result_label(hht, aht, home, away, row["home_team"])
        ft_lbl = _h2h_team_result_label(hg, ag, home, away, row["home_team"])
        combo = f"{ht_lbl} / {ft_lbl}"
        ht_ft_counts[combo] = ht_ft_counts.get(combo, 0) + 1

    total_goals = pd.to_numeric(h2h["total_goals_ft"], errors="coerce").fillna(0)
    hg_s = pd.to_numeric(h2h["home_goals_ft"], errors="coerce").fillna(0)
    ag_s = pd.to_numeric(h2h["away_goals_ft"], errors="coerce").fillna(0)
    btts = int(((hg_s >= 1) & (ag_s >= 1)).sum())
    total_2h = pd.to_numeric(h2h["total_goals_2h"], errors="coerce").fillna(0)

    over_15_n = int((total_goals >= 2).sum())
    over_25_n = int((total_goals >= 3).sum())
    over_35_n = int((total_goals >= 4).sum())
    under_25_n = n - over_25_n
    total_goals_sum = int(total_goals.sum())

    dates = pd.to_datetime(h2h["match_date"], errors="coerce").dropna()
    date_from = dates.min().strftime("%d/%m/%Y") if len(dates) else "—"
    date_to = dates.max().strftime("%d/%m/%Y") if len(dates) else "—"

    minute_total = {k: minute_home[k] + minute_away[k] for k in H2H_MINUTE_BUCKETS}
    minute_table = []
    for bucket in H2H_MINUTE_BUCKETS:
        minute_table.append({
            "bucket": bucket,
            "home": minute_home[bucket],
            "away": minute_away[bucket],
            "total": minute_total[bucket],
        })

    ht_ft_list = []
    for label, count in sorted(ht_ft_counts.items(), key=lambda x: -x[1]):
        pct = _safe_pct(count, n)
        fav = label.split(" / ")[-1]
        if fav == home:
            icon = "✅"
        elif fav == away:
            icon = "❌"
        else:
            icon = "➖"
        ht_ft_list.append({"label": label, "count": count, "pct": pct, "icon": icon})

    last10_rows = []
    for _, row in h2h.head(10).iterrows():
        hg = float(row.get("home_goals_ft") or 0)
        ag = float(row.get("away_goals_ft") or 0)
        tg = float(row.get("total_goals_ft") or hg + ag)
        hht = float(row.get("home_goals_ht") or 0)
        aht = float(row.get("away_goals_ht") or 0)
        ht_lbl = _h2h_team_result_label(hht, aht, home, away, row["home_team"])
        ft_lbl = _h2h_team_result_label(hg, ag, home, away, row["home_team"])
        if row["home_team"] == home:
            sel_hg, sel_ag = hg, ag
        else:
            sel_hg, sel_ag = ag, hg
        if sel_hg > sel_ag:
            res_color = "green"
        elif sel_hg < sel_ag:
            res_color = "red"
        else:
            res_color = "yellow"
        last10_rows.append({
            "match_date": row.get("match_date"),
            "home_team": row.get("home_team"),
            "away_team": row.get("away_team"),
            "ft_result": row.get("ft_result") or f"{int(hg)}-{int(ag)}",
            "ht_ft": f"{ht_lbl} / {ft_lbl}",
            "total_goals_ft": int(tg),
            "over_25": tg >= 3,
            "btts": hg >= 1 and ag >= 1,
            "res_color": res_color,
        })

    last10 = pd.DataFrame(last10_rows)
    goals_trend = list(pd.to_numeric(h2h.head(10)["total_goals_ft"], errors="coerce").fillna(0))

    insights = []
    if away_wins > home_wins:
        insights.append(f"{away} ha vinto più scontri diretti ({away_wins} vittorie).")
    elif home_wins > away_wins:
        insights.append(f"{home} ha vinto più scontri diretti ({home_wins} vittorie).")
    else:
        insights.append("Equilibrio negli scontri diretti tra le due squadre.")
    insights.append(f"Media gol elevata ({round(float(total_goals.mean()), 2)} a partita).")
    insights.append(f"Over 2.5 frequente ({_safe_pct(over_25_n, n):.2f}% delle partite).")
    insights.append(f"BTTS probabile ({_safe_pct(btts, n):.2f}% delle partite).")

    return {
        "found":          n,
        "home_wins":      home_wins,
        "draws":          draws,
        "away_wins":      away_wins,
        "home_win_pct":   _safe_pct(home_wins, n),
        "draw_pct":       _safe_pct(draws, n),
        "away_win_pct":   _safe_pct(away_wins, n),
        "avg_goals":      round(float(total_goals.mean()), 2),
        "home_avg_goals": round(home_goals_scored / n, 2),
        "away_avg_goals": round(away_goals_scored / n, 2),
        "total_goals_sum": total_goals_sum,
        "over_15_pct":    _safe_pct(over_15_n, n),
        "over_25_pct":    _safe_pct(over_25_n, n),
        "over_35_pct":    _safe_pct(over_35_n, n),
        "under_25_pct":   _safe_pct(under_25_n, n),
        "over_15_n":      over_15_n,
        "over_25_n":      over_25_n,
        "over_35_n":      over_35_n,
        "under_25_n":     under_25_n,
        "btts_pct":       _safe_pct(btts, n),
        "btts_n":         btts,
        "goals_2h_pct":   _safe_pct(float(total_2h.sum()), float(total_goals.sum())) if total_goals.sum() > 0 else 0.0,
        "date_from":      date_from,
        "date_to":        date_to,
        "minute_table":   minute_table,
        "ht_ft_list":     ht_ft_list,
        "last10":         last10,
        "goals_trend":    goals_trend,
        "insights":       insights,
    }


def compute_pattern_insights(df: pd.DataFrame, results: dict, full_df: pd.DataFrame) -> dict:
    if df is None or len(df) == 0 or not results:
        return {}
    n = len(df)
    full_results = analyze_matches(full_df) if full_df is not None and len(full_df) > 0 else {}

    recent = df.sort_values("match_date", ascending=False).head(10)
    trend_goals = list(pd.to_numeric(recent["total_goals_ft"], errors="coerce").fillna(0))

    roi_vals = {
        "Vittoria Casa": results.get("roi_home_win", float("nan")),
        "Lay Casa":      results.get("roi_lay_home", float("nan")),
        "Over 0.5 2°T":  results.get("roi_over_05_2h", float("nan")),
        "Lay 0-0":       results.get("roi_lay_00", float("nan")),
    }
    valid_rois = {k: v for k, v in roi_vals.items()
                  if isinstance(v, (int, float)) and not np.isnan(v)}
    best_label = max(valid_rois, key=valid_rois.get) if valid_rois else "N/A"
    best_val   = valid_rois.get(best_label, float("nan"))

    return {
        "trend_goals":     trend_goals,
        "over_25_filter":  results.get("over_25_ft_pct", 0),
        "over_25_db":      full_results.get("over_25_ft_pct", 0),
        "btts_filter":     results.get("btts_pct", 0),
        "btts_db":         full_results.get("btts_pct", 0),
        "home_win_filter": results.get("home_win_pct", 0),
        "home_win_db":     full_results.get("home_win_pct", 0),
        "best_roi_label":  best_label,
        "best_roi_val":    best_val,
        "n":               n,
    }


def calculate_over_trend_by_season(df: pd.DataFrame, half: str) -> dict:
    """
    half = '1h' or '2h'
    
    For '1h': use home_goals_ht + away_goals_ht per match
    For '2h': use total_goals_2h per match
    
    Group by season column.
    For each season calculate:
      over_05_pct = % matches where half_goals > 0
      over_15_pct = % matches where half_goals > 1
      over_25_pct = % matches where half_goals > 2
    
    Return:
    {
      "2019-2020": {"over_05": 71.4, "over_15": 33.3, "over_25": 11.1},
      "2020-2021": {...},
      ...
    }
    Sort by season ascending.
    """
    if df is None or len(df) == 0:
        return {}
    
    df_copy = df.copy()
    if half == '1h':
        home_ht = pd.to_numeric(df_copy["home_goals_ht"], errors="coerce").fillna(0)
        away_ht = pd.to_numeric(df_copy["away_goals_ht"], errors="coerce").fillna(0)
        df_copy["half_goals"] = home_ht + away_ht
    else:
        df_copy["half_goals"] = pd.to_numeric(df_copy["total_goals_2h"], errors="coerce").fillna(0)
        
    if "season" not in df_copy.columns:
        return {}
        
    df_copy = df_copy.dropna(subset=["season"])
    if len(df_copy) == 0:
        return {}
        
    seasons = sorted(df_copy["season"].unique())
    res = {}
    for season in seasons:
        season_df = df_copy[df_copy["season"] == season]
        n_matches = len(season_df)
        if n_matches == 0:
            continue
        g = season_df["half_goals"]
        over_05 = float((g > 0).sum()) / n_matches * 100
        over_15 = float((g > 1).sum()) / n_matches * 100
        over_25 = float((g > 2).sum()) / n_matches * 100
        
        res[season] = {
            "over_05": round(over_05, 1),
            "over_15": round(over_15, 1),
            "over_25": round(over_25, 1)
        }
    return res


INTERVALS_1T = {
    "0-15":  (0, 15),
    "16-30": (16, 30),
    "31-45": (31, 45),
    "45+":   (46, 60),
}

INTERVALS_2T = {
    "46-60": (46, 60),
    "61-75": (61, 75),
    "76-90": (76, 90),
    "90+":   (91, 120),
}


def _events_for_match(goal_events, match_id):
    if isinstance(goal_events, dict):
        return goal_events.get(match_id, [])
    return [e for e in goal_events if e.get("match_id") == match_id]


def _count_goals_in_interval(events, start: int, end: int) -> int:
    return sum(
        1 for e in events
        if start <= _parse_minute(e.get("minute", 0)) <= end
    )


def _calculate_interval_distribution(goal_events, match_ids: list, intervals: dict) -> dict:
    """
    Per ogni intervallo: conta gol per match, classifica 0/1/2/3+,
    calcola % su N match. ge1 = pct_1 + pct_2 + pct_3plus.
    """
    n = len(match_ids)
    empty = {"0_gol": 0.0, "1_gol": 0.0, "2_gol": 0.0, "3plus": 0.0, "ge1": 0.0}
    if n == 0:
        return {name: dict(empty) for name in intervals}

    distribution = {name: {"0": 0, "1": 0, "2": 0, "3+": 0} for name in intervals}

    for mid in match_ids:
        events = _events_for_match(goal_events, mid)
        for name, (start, end) in intervals.items():
            g = _count_goals_in_interval(events, start, end)
            if g == 0:
                distribution[name]["0"] += 1
            elif g == 1:
                distribution[name]["1"] += 1
            elif g == 2:
                distribution[name]["2"] += 1
            else:
                distribution[name]["3+"] += 1

    res = {}
    for name, vals in distribution.items():
        pct_0 = vals["0"] / n * 100
        pct_1 = vals["1"] / n * 100
        pct_2 = vals["2"] / n * 100
        pct_3 = vals["3+"] / n * 100
        res[name] = {
            "0_gol": round(pct_0, 1),
            "1_gol": round(pct_1, 1),
            "2_gol": round(pct_2, 1),
            "3plus": round(pct_3, 1),
            "ge1":   round(pct_1 + pct_2 + pct_3, 1),
        }
    return res


def calculate_interval_distribution_1h(goal_events, match_ids: list) -> dict:
    """Distribuzione gol 1T per intervalli definiti in INTERVALS_1T."""
    return _calculate_interval_distribution(goal_events, match_ids, INTERVALS_1T)


def calculate_interval_distribution_2h(goal_events, match_ids: list) -> dict:
    """Distribuzione gol 2T per intervalli definiti in INTERVALS_2T."""
    return _calculate_interval_distribution(goal_events, match_ids, INTERVALS_2T)


def calculate_at_least_one_goal_half_pct(goal_events, match_ids: list) -> tuple:
    """
    TOTALE 1T/2T: % partite con almeno 1 gol nel tempo.
    1T: minute <= 45 | 2T: minute > 45. Denominatore: N = len(match_ids).
    """
    n = len(match_ids)
    if n == 0:
        return 0.0, 0.0

    count_1t = 0
    count_2t = 0
    for mid in match_ids:
        events = _events_for_match(goal_events, mid)
        if any(_parse_minute(e.get("minute", 0)) <= 45 for e in events):
            count_1t += 1
        if any(_parse_minute(e.get("minute", 0)) > 45 for e in events):
            count_2t += 1

    return round(count_1t / n * 100, 1), round(count_2t / n * 100, 1)


def calculate_goals_by_interval(goal_events, match_ids: list, intervals: dict) -> dict:
    """
    Conta tutti i gol (non partite) per intervallo, divisi casa/trasferta.
    Ritorna percentuali su total_goals del tempo e insight early/late.
    """
    dist = {name: {"home": 0, "away": 0} for name in intervals}

    for mid in match_ids:
        events = _events_for_match(goal_events, mid)
        for e in events:
            minute = _parse_minute(e.get("minute", 0))
            for name, (start, end) in intervals.items():
                if start <= minute <= end:
                    if e.get("is_home", 0) == 1:
                        dist[name]["home"] += 1
                    else:
                        dist[name]["away"] += 1
                    break

    raw_total = sum(dist[i]["home"] + dist[i]["away"] for i in dist)
    total_goals = raw_total if raw_total > 0 else 1

    total_home = sum(dist[i]["home"] for i in dist)
    total_away = sum(dist[i]["away"] for i in dist)

    intervals_data = {}
    for name in intervals:
        home_g = dist[name]["home"]
        away_g = dist[name]["away"]
        total_interval = home_g + away_g
        intervals_data[name] = {
            "home": home_g,
            "away": away_g,
            "total": total_interval,
            "pct_home": round(home_g / total_goals * 100, 1),
            "pct_away": round(away_g / total_goals * 100, 1),
            "pct_total": round(total_interval / total_goals * 100, 1),
        }

    early_goals = intervals_data.get("0-15", {}).get("total", 0)
    pct_early = round(early_goals / total_goals * 100, 1) if raw_total > 0 else 0.0

    late_goals = sum(
        intervals_data.get(k, {}).get("total", 0)
        for k in ("61-75", "76-90", "90+")
        if k in intervals_data
    )
    pct_late = round(late_goals / total_goals * 100, 1) if raw_total > 0 else 0.0

    return {
        "intervals": intervals_data,
        "total_goals": raw_total,
        "pct_home_total": round(total_home / total_goals * 100, 1),
        "pct_away_total": round(total_away / total_goals * 100, 1),
        "pct_early": pct_early,
        "pct_late": pct_late,
    }


def calculate_timing_distribution_total(goal_events, match_ids: list) -> dict:
    """
    Distribuzione gol per intervallo (TOTALE): conta tutti i gol su BUCKETS.
    Gestisce 45+ (recupero 1T) e 90+ (recupero 2T) tramite half.
    """
    dist = {k: {"home": 0, "away": 0} for k in BUCKETS}

    for mid in match_ids:
        events = _events_for_match(goal_events, mid)
        for e in events:
            m = _parse_minute(e.get("minute", 0))
            half = e.get("half", 1 if m <= 45 else 2)
            is_home = e.get("is_home", 0) == 1
            bucket = None

            if half == 1 and m > 45:
                bucket = "45+"
            elif half == 2 and m > 90:
                bucket = "90+"
            else:
                for name, (lo, hi) in BUCKETS.items():
                    if name in ("45+", "90+"):
                        continue
                    if lo <= m <= hi:
                        bucket = name
                        break

            if bucket:
                if is_home:
                    dist[bucket]["home"] += 1
                else:
                    dist[bucket]["away"] += 1

    raw_total = sum(dist[k]["home"] + dist[k]["away"] for k in BUCKETS)
    total_goals = raw_total if raw_total > 0 else 1

    timing_pct = {
        k: round((dist[k]["home"] + dist[k]["away"]) / total_goals * 100, 1)
        for k in BUCKETS
    }

    _filtered = {k: v for k, v in timing_pct.items() if k not in ("45+", "90+")}
    best_tf = max(timing_pct, key=timing_pct.get) if timing_pct else "N/A"
    worst_tf = min(_filtered, key=_filtered.get) if _filtered else best_tf

    return {
        "timing_dist": timing_pct,
        "timing_raw": {k: dist[k]["home"] + dist[k]["away"] for k in BUCKETS},
        "best_tf": best_tf,
        "worst_tf": worst_tf,
        "best_val": timing_pct.get(best_tf, 0.0),
        "worst_val": timing_pct.get(worst_tf, 0.0),
        "total_goals": raw_total,
    }


def build_similar_match_momentum(
    goal_events,
    match_ids: list,
    window: int = 2,
    smooth: int = 5,
    top_markers: int = 4,
) -> dict:
    """
    Profilo atteso casa/trasferta dai minuti gol del campione (partite simili).
    Ogni gol distribuisce peso su ±window minuti; curva smussata e normalizzata 0–100.
    """
    n_matches = len(match_ids or [])
    home_raw = [0.0] * 91
    away_raw = [0.0] * 91

    if n_matches == 0:
        return {
            "minutes": list(range(1, 91)),
            "home": [0.0] * 90,
            "away": [0.0] * 90,
            "home_markers": [],
            "away_markers": [],
            "n_matches": 0,
        }

    for mid in match_ids:
        for e in _events_for_match(goal_events, mid):
            m = _parse_minute(e.get("minute", 0))
            if m < 1:
                continue
            m = min(m, 90)
            is_home = e.get("is_home", 0) == 1
            target = home_raw if is_home else away_raw
            for d in range(-window, window + 1):
                mm = m + d
                if 1 <= mm <= 90:
                    weight = 1.0 - (abs(d) / (window + 1))
                    target[mm] += weight

    def _smooth_series(raw: list, radius: int) -> list:
        out = []
        for i in range(1, 91):
            lo = max(1, i - radius)
            hi = min(90, i + radius)
            span = hi - lo + 1
            out.append(sum(raw[lo:hi + 1]) / (span * n_matches))
        return out

    radius = max(1, smooth // 2)
    home_sm = _smooth_series(home_raw, radius)
    away_sm = _smooth_series(away_raw, radius)
    peak = max(max(home_sm, default=0), max(away_sm, default=0), 1e-9)
    home_norm = [round(v / peak * 100, 2) for v in home_sm]
    away_norm = [round(v / peak * 100, 2) for v in away_sm]

    def _top_markers(values: list, raw: list) -> list:
        ranked = sorted(
            ((i + 1, values[i], raw[i + 1]) for i in range(90)),
            key=lambda x: (x[2], x[1]),
            reverse=True,
        )
        chosen = []
        used = set()
        for minute, val, _ in ranked:
            if len(chosen) >= top_markers or val <= 0:
                break
            if any(abs(minute - u) <= 3 for u in used):
                continue
            chosen.append({"minute": minute, "value": val})
            used.add(minute)
        return chosen

    return {
        "minutes": list(range(1, 91)),
        "home": home_norm,
        "away": away_norm,
        "home_markers": _top_markers(home_norm, home_raw),
        "away_markers": _top_markers(away_norm, away_raw),
        "n_matches": n_matches,
    }


def get_team_stats_all_competitions(df: pd.DataFrame, team_name: str) -> dict:
    """
    df = FULL unfiltered dataframe (all leagues, all seasons).
    
    Get all matches where team_name appears 
    as home_team OR away_team.
    
    Calculate:
      total_matches
      wins, draws, losses
      goals_scored_avg    (per match)
      goals_conceded_avg  (per match)
      points              (W=3, D=1, L=0)
      over_25_pct
      btts_pct
      clean_sheet_pct
      goals_per_interval  (dict of bucket → avg goals)
    
    Return these as a flat dict.
    """
    if df is None or len(df) == 0:
        return {}
        
    t_matches = df[(df["home_team"] == team_name) | (df["away_team"] == team_name)].copy()
    n_t = len(t_matches)
    if n_t == 0:
        return {
            "total_matches": 0, "wins": 0, "draws": 0, "losses": 0,
            "goals_scored_avg": 0.0, "goals_conceded_avg": 0.0, "points": 0,
            "over_25_pct": 0.0, "btts_pct": 0.0, "clean_sheet_pct": 0.0,
            "goals_per_interval": {"1-15": 0.0, "16-30": 0.0, "31-45": 0.0, "46-60": 0.0, "61-75": 0.0, "76-90": 0.0}
        }
        
    wins = draws = losses = 0
    goals_scored = 0
    goals_conceded = 0
    points = 0
    over_25_count = 0
    btts_count = 0
    clean_sheets = 0
    
    intervals_goals = {"1-15": 0, "16-30": 0, "31-45": 0, "46-60": 0, "61-75": 0, "76-90": 0}
    
    from database import get_goal_events_for_matches
    match_ids = list(t_matches["match_id"].dropna().astype(int))
    recent_events = get_goal_events_for_matches(match_ids)
    
    for _, row in t_matches.iterrows():
        mid = int(row["match_id"])
        h_goals = pd.to_numeric(row.get("home_goals_ft", 0), errors="coerce")
        a_goals = pd.to_numeric(row.get("away_goals_ft", 0), errors="coerce")
        is_home = (row["home_team"] == team_name)
        
        scored = h_goals if is_home else a_goals
        conceded = a_goals if is_home else h_goals
        
        goals_scored += scored
        goals_conceded += conceded
        
        if h_goals > a_goals:
            res = "H"
        elif h_goals == a_goals:
            res = "D"
        else:
            res = "A"
            
        if (res == "H" and is_home) or (res == "A" and not is_home):
            wins += 1
            points += 3
        elif res == "D":
            draws += 1
            points += 1
        else:
            losses += 1
            
        if (h_goals + a_goals) > 2.5:
            over_25_count += 1
        if h_goals > 0 and a_goals > 0:
            btts_count += 1
        if conceded == 0:
            clean_sheets += 1
            
        events = recent_events.get(mid, [])
        for e in events:
            goal_by_our_team = (e["is_home"] == 1 and is_home) or (e["is_home"] == 0 and not is_home)
            if goal_by_our_team:
                m = _parse_minute(e["minute"])
                if 1 <= m <= 15:
                    intervals_goals["1-15"] += 1
                elif 16 <= m <= 30:
                    intervals_goals["16-30"] += 1
                elif 31 <= m <= 45:
                    intervals_goals["31-45"] += 1
                elif 46 <= m <= 60:
                    intervals_goals["46-60"] += 1
                elif 61 <= m <= 75:
                    intervals_goals["61-75"] += 1
                elif 76 <= m:
                    intervals_goals["76-90"] += 1
                    
    goals_per_interval = {k: round(v / n_t, 2) for k, v in intervals_goals.items()}
    
    return {
        "total_matches": n_t,
        "wins": wins,
        "draws": draws,
        "losses": losses,
        "goals_scored_avg": round(goals_scored / n_t, 2),
        "goals_conceded_avg": round(goals_conceded / n_t, 2),
        "points": points,
        "over_25_pct": round(over_25_count / n_t * 100, 1),
        "btts_pct": round(btts_count / n_t * 100, 1),
        "clean_sheet_pct": round(clean_sheets / n_t * 100, 1),
        "goals_per_interval": goals_per_interval
    }

# ═══════════════════════════════════════════════════════════════════════════
# LIVE ANALYSIS V2 — Full dynamic engine (Andrea spec)
# ═══════════════════════════════════════════════════════════════════════════

def _score_at_minute(events: list, minute: int) -> tuple:
    """Calculate home/away score at a specific minute from goal_events list."""
    home = sum(1 for e in events if e["is_home"] == 1 and _parse_minute(e["minute"]) <= minute)
    away = sum(1 for e in events if e["is_home"] == 0 and _parse_minute(e["minute"]) <= minute)
    return home, away


def _first_goal_minute(events: list) -> int:
    """Return minute of first goal in match, or 999 if no goals."""
    fg = get_first_goal_from_events(events)
    return fg["minute"] if fg else 999


def _get_future_timeframes(current_minute: int) -> list:
    """
    Return only timeframe buckets that are in the future relative to current_minute.
    Andrea spec: hide past timeframes.
    """
    all_buckets = [
        ("0-15",  1,  15),
        ("16-30", 16, 30),
        ("31-45", 31, 45),
        ("45+",   46, 45+999),  # 1H stoppage
        ("46-60", 46, 60),
        ("61-75", 61, 75),
        ("76-90", 76, 90),
        ("90+",   91, 91+999),  # 2H stoppage
    ]
    # Keep bucket if its END minute > current_minute
    return [(name, lo, hi) for name, lo, hi in all_buckets if hi > current_minute and lo > current_minute]


def _minute_bucket(minute: int, current_minute: int) -> str:
    """Map a future goal minute to a relative timeframe label."""
    delta = minute - current_minute
    if delta <= 10:
        return "0-10 min"
    elif delta <= 20:
        return "10-20 min"
    elif delta <= 30:
        return "20-30 min"
    else:
        return "30+ min"


def _half_from_minute(minute: int) -> int:
    return 1 if minute <= 45 else 2


def _minute_bucket_abs(goal_minute: int, current_minute: int) -> str:
    """
    Returns ABSOLUTE minute range label for next-goal distribution.
    Andrea Point 8: conditional distribution from current_minute onward,
    labeled with actual future minutes (not relative 0-10 min offsets).

    Examples (current_minute=60):
      goal at 63  →  "61'-70'"
      goal at 74  →  "71'-80'"
      goal at 85  →  "81'-90'"
      goal at 93  →  "90+'"
    """
    offset = max(goal_minute - current_minute, 1)
    slot   = (offset - 1) // 10          # 0, 1, 2, 3, …
    lo     = current_minute + slot * 10 + 1
    hi     = lo + 9
    if hi >= 90:
        return "90+'"
    return f"{lo}'-{hi}'"


def build_score_index(df, goal_events: dict) -> dict:
    """
    Andrea Point 9: pre-compute every match's score at every minute 0-95.
    Returns {match_id: [(home, away), ...]} indexed by minute (list[minute]).

    Build once per session (st.session_state in live.py), reuse across
    every Analizza click so analyze_live_state_v2 does O(1) score lookups
    instead of scanning events on every call.
    """
    index = {}
    for _, row in df.iterrows():
        mid = row.get("match_id")
        if mid is None:
            continue
        mid = int(mid)
        events = sorted(
            goal_events.get(mid, []),
            key=lambda e: _parse_minute(e["minute"]),
        )
        h = a = ev_idx = 0
        scores = []
        for minute in range(96):
            while ev_idx < len(events) and _parse_minute(events[ev_idx]["minute"]) <= minute:
                if events[ev_idx]["is_home"] == 1:
                    h += 1
                else:
                    a += 1
                ev_idx += 1
            scores.append((h, a))
        index[mid] = scores
    return index


def analyze_live_state_v2(
    df: pd.DataFrame,
    goal_events: dict,
    current_minute: int,
    home_score: int,
    away_score: int,
    first_goal_minute: int = None,   # None = no goal yet, int = minute of first goal
    minute_window: int = 5,          # ±5 default, ±10 fallback
    odds_home_ref: float = None,     # Pre-match home odds for similar range filter (None = skip)
    odds_window: float = 0.5,        # ±0.5 odds range
    score_index: dict = None,        # Pre-built index from build_score_index() for fast lookups
) -> dict:
    """
    Full live analysis engine per Andrea's spec.
    
    Filters historical matches where:
      - Score at (current_minute ± window) == (home_score, away_score)
      - Same half as current_minute
    
    Returns complete stats for all screen blocks.
    """

    current_half = _half_from_minute(current_minute)
    min_lo = max(0, current_minute - minute_window)
    min_hi = current_minute + minute_window

    matched = []  # list of dicts: {row, events_before, events_after}

    for _, row in df.iterrows():
        mid = row.get("match_id")
        if mid is None:
            continue
        events = goal_events.get(int(mid), [])

        # Check score at every minute in the window — find matches where
        # at some point in [min_lo, min_hi] the score was (home_score, away_score)
        found = False
        check_minute = None
        mid_int = int(mid)
        for chk in range(min_lo, min_hi + 1):
            # Point 9: use pre-built index for O(1) lookup if available
            if score_index and mid_int in score_index and chk < len(score_index[mid_int]):
                h, a = score_index[mid_int][chk]
            else:
                h, a = _score_at_minute(events, chk)
            if h == home_score and a == away_score:
                # Also check half matches
                if _half_from_minute(chk) == current_half:
                    found = True
                    check_minute = chk
                    break

        if not found:
            continue

        # Point 3: Similar odds range filter (skip if odds_home_ref not provided)
        if odds_home_ref is not None:
            match_odds_home = _safe_odd(row.get("odds_home"))
            if match_odds_home is not None and abs(match_odds_home - odds_home_ref) > odds_window:
                continue

        events_before = [e for e in events if _parse_minute(e["minute"]) <= current_minute]
        events_after  = [e for e in events if _parse_minute(e["minute"]) > current_minute]

        # Post-goal filter: if first_goal_minute provided, filter matches where
        # first goal was in ±10 min window of that minute
        if first_goal_minute is not None:
            fg = _first_goal_minute(events)
            if abs(fg - first_goal_minute) > 10:
                continue

        matched.append({
            "row": row,
            "events_before": events_before,
            "events_after": events_after,
            "check_minute": check_minute,
        })

    n = len(matched)

    # ── FALLBACK: widen window if sample too small ─────────────────────────
    confidence = "ALTA"
    used_window = minute_window
    if n < 20 and minute_window == 5:
        return analyze_live_state_v2(
            df, goal_events, current_minute, home_score, away_score,
            first_goal_minute, minute_window=10,
            odds_home_ref=odds_home_ref, odds_window=odds_window,
            score_index=score_index,
        )
    if n < 10:
        confidence = "BASSA"
        used_window = 10
    elif n < 30:
        confidence = "MEDIA"
        used_window = minute_window

    if n == 0:
        return {"found": 0, "confidence": "NESSUNA", "used_window": used_window}

    # ═══ BLOCK 1: EVOLUZIONE RISULTATO (state transitions) ════════════════
    transitions = {}
    for m in matched:
        row = m["row"]
        hf = float(row.get("home_goals_ft") or 0)
        af = float(row.get("away_goals_ft") or 0)
        key = f"{int(hf)}-{int(af)}"
        transitions[key] = transitions.get(key, 0) + 1

    top_transitions = sorted(transitions.items(), key=lambda x: x[1], reverse=True)[:6]

    # Current state label for display
    current_state = f"{home_score}-{away_score}"
    stays_same = transitions.get(current_state, 0)

    # ═══ BLOCK 2 & 3: CHI SEGNA DOPO + QUANDO ════════════════════════════
    next_goal_home = next_goal_away = next_goal_none = 0
    # Point 8: empty dict — keys built dynamically as absolute minute ranges
    next_goal_timing = {}

    for m in matched:
        ea = m["events_after"]
        if not ea:
            next_goal_none += 1
            continue
        first_after = sorted(ea, key=lambda e: _parse_minute(e["minute"]))[0]
        if first_after["is_home"] == 1:
            next_goal_home += 1
        else:
            next_goal_away += 1
        # Point 8: use absolute minute labels (e.g. "61'-70'") not relative ("0-10 min")
        bucket = _minute_bucket_abs(_parse_minute(first_after["minute"]), current_minute)
        next_goal_timing[bucket] = next_goal_timing.get(bucket, 0) + 1

    # ═══ BLOCK 4 & 5: VANTAGGIO / SVANTAGGIO scenarios ═══════════════════
    # Block 4: home in vantaggio (home_score > away_score)
    #   - Raddoppia vantaggio : lead aumenta (hf - af > home_score - away_score)
    #   - Subisce pareggio    : finisce in pareggio (hf == af)
    #   - Nessun altro gol    : risultato finale == stato attuale (no change)
    #
    # Block 5: away in vantaggio (away_score > home_score)
    #   Perspective: HOME team è in SVANTAGGIO
    #   - Rimonta (almeno pari): home pareggia o ribalta (hf >= af at FT)
    #   - Non segna più        : svantaggio si mantiene o peggiora, home non segna
    #   - Segna ma perde       : home segna qualcosa ma perde ancora (hf > home_score at FT, hf < af)
    home_leading = home_score > away_score
    away_leading = away_score > home_score

    home_doubles   = home_equalises = home_concedes_all = 0
    away_comebacks = away_no_more   = away_scores_loses  = 0

    for m in matched:
        row = m["row"]
        hf = float(row.get("home_goals_ft") or 0)
        af = float(row.get("away_goals_ft") or 0)

        if home_leading:
            # Home è in vantaggio — cosa succede al FT?
            if hf - af > home_score - away_score:
                # Lead aumenta (es. 1-0 → 2-0, 3-0, ecc.)
                home_doubles += 1
            elif hf == af:
                # Away pareggia (es. 1-0 → 1-1)
                home_equalises += 1
            else:
                # Tutto il resto: risultato invariato o away ribalta
                home_concedes_all += 1

        elif away_leading:
            # Home è in SVANTAGGIO — cosa succede al FT?
            home_goals_added = hf - home_score   # gol aggiuntivi fatti da home
            if hf >= af:
                # Home pareggia o ribalta: rimonta riuscita
                away_comebacks += 1
            elif home_goals_added > 0 and hf < af:
                # Home segna qualcosa ma rimane sotto
                away_scores_loses += 1
            else:
                # Home non segna più: svantaggio invariato o peggiora
                away_no_more += 1

    # ═══ BLOCK 6: RISULTATI FINALI PIÙ FREQUENTI ═════════════════════════
    # Already in top_transitions

    # ═══ BLOCK 7: GOL RIMANENTI ══════════════════════════════════════════
    goals_remaining_dist = {0: 0, 1: 0, 2: 0}  # 2 = "2+"
    goals_remaining_total = 0
    for m in matched:
        ga = len(m["events_after"])
        goals_remaining_total += ga
        if ga == 0:
            goals_remaining_dist[0] += 1
        elif ga == 1:
            goals_remaining_dist[1] += 1
        else:
            goals_remaining_dist[2] += 1

    avg_goals_remaining = round(goals_remaining_total / n, 2)

    # ═══ BLOCK 8: STABILITÀ RISULTATO ════════════════════════════════════
    result_stable = stays_same
    result_changes = n - stays_same

    # ═══ BLOCK 9: MOMENTUM POST-GOL ══════════════════════════════════════
    # Spec formula: momentum = avg_time_before / avg_time_after
    #   avg_time_before = avg gap between goals BEFORE current_minute
    #   avg_time_after  = avg gap between goals AFTER current_minute
    #   ratio > 1 → ritmo accelera (gol più frequenti dopo)
    #   ratio ≈ 1 → ritmo simile
    #   ratio < 1 → ritmo rallenta (gol meno frequenti dopo)
    #
    # Classificazione:
    #   Ritmo aumenta   (momentum_up)  : ratio >= 1.15
    #   Ritmo simile    (momentum_same): 0.85 < ratio < 1.15
    #   Ritmo diminuisce(momentum_down): ratio <= 0.85

    def _avg_inter_goal_gap(minutes_list: list, start: int, end: int) -> float:
        """Average gap between consecutive goals in [start, end] window.
        Returns 0.0 if fewer than 2 goals (can't compute gap)."""
        goals = sorted(m for m in minutes_list if start < m <= end)
        if len(goals) < 2:
            return 0.0
        gaps = [goals[i+1] - goals[i] for i in range(len(goals)-1)]
        return sum(gaps) / len(gaps)

    momentum_up = momentum_same = momentum_down = 0
    momentum_ratios = []

    for m in matched:
        mid_key = int(m["row"].get("match_id", 0))
        all_evs  = goal_events.get(mid_key, [])
        all_mins = [_parse_minute(e["minute"]) for e in all_evs]

        # Gap before current_minute (from kick-off)
        gap_before = _avg_inter_goal_gap(all_mins, 0, current_minute)
        # Gap after current_minute (up to 90')
        gap_after  = _avg_inter_goal_gap(all_mins, current_minute, 95)

        if gap_before > 0 and gap_after > 0:
            ratio = gap_before / gap_after  # >1 = faster after, <1 = slower
            momentum_ratios.append(ratio)
            if ratio >= 1.15:
                momentum_up   += 1
            elif ratio <= 0.85:
                momentum_down += 1
            else:
                momentum_same += 1
        else:
            # Can't compute ratio — classify by goal count fallback
            n_after = len(m["events_after"])
            if n_after > 1:
                momentum_up   += 1
            elif n_after == 1:
                momentum_same += 1
            else:
                momentum_down += 1

    # ═══ BLOCK 10: DEAD GAME DETECTION ═══════════════════════════════════
    # If no goal enters by minute 70, what % stay goalless after that?
    dead_game_threshold = 70
    dead_game_pct = 0.0
    if current_minute < dead_game_threshold:
        dead_game_matches = [m for m in matched if len(m["events_after"]) == 0]
        dead_game_pct = _safe_pct(len(dead_game_matches), n)
    
    if dead_game_pct > 50:
        dead_game_risk = "ALTO"
    elif dead_game_pct > 30:
        dead_game_risk = "MEDIO"
    else:
        dead_game_risk = "BASSO"

    # ═══ BLOCK 11: DEVIAZIONE xG ═════════════════════════════════════════
    # xG_diff = goals - xG  (per Andrea spec)
    # CSV fields: team_a_xg (home), team_b_xg (away)
    # DB may store them as xg_home/xg_away or team_a_xg/team_b_xg
    # Try both conventions with fallback to None

    def _get_xg(row, is_home: bool):
        """Safely extract xG from row trying multiple field name conventions."""
        if is_home:
            for field in ("xg_home", "team_a_xg", "home_xg", "xG_home"):
                v = row.get(field)
                if v is not None:
                    try:
                        f = float(v)
                        if f >= 0:
                            return f
                    except (ValueError, TypeError):
                        pass
        else:
            for field in ("xg_away", "team_b_xg", "away_xg", "xG_away"):
                v = row.get(field)
                if v is not None:
                    try:
                        f = float(v)
                        if f >= 0:
                            return f
                    except (ValueError, TypeError):
                        pass
        return None

    xg_diffs_home = []
    xg_diffs_away = []
    for m in matched:
        row = m["row"]
        hf  = float(row.get("home_goals_ft") or 0)
        af  = float(row.get("away_goals_ft") or 0)
        xg_h = _get_xg(row, is_home=True)
        xg_a = _get_xg(row, is_home=False)
        if xg_h is not None:
            xg_diffs_home.append(hf - xg_h)
        if xg_a is not None:
            xg_diffs_away.append(af - xg_a)

    # Average deviation across all similar matches
    xg_diff_home = round(sum(xg_diffs_home) / len(xg_diffs_home), 2) if xg_diffs_home else None
    xg_diff_away = round(sum(xg_diffs_away) / len(xg_diffs_away), 2) if xg_diffs_away else None
    xg_data_available = xg_diff_home is not None

    # Label: positive = team scored MORE than xG expected (lucky/clinical)
    #        negative = team scored LESS than xG expected (unlucky/wasteful)
    def _xg_label(diff):
        if diff is None:
            return "N/D"
        if diff > 0.3:
            return "SOVRAPERFORMA"   # scoring above xG
        elif diff < -0.3:
            return "SOTTOPERFORMA"   # scoring below xG
        else:
            return "IN LINEA"

    xg_label_home = _xg_label(xg_diff_home)
    xg_label_away = _xg_label(xg_diff_away)

    # ═══ BLOCK 12: QUALITÀ ULTIMO GOL ════════════════════════════════════
    # quality_score = xG_last_goal / avg_xG_goal  (per Andrea spec)
    # Since we don't have per-shot xG, we use match-level xG / total goals
    # as a proxy: avg xG per goal = total_match_xG / total_goals_ft
    # quality_last = xG of last-goal team per goal vs avg across all similar

    quality_scores = []
    for m in matched:
        row  = m["row"]
        hf   = float(row.get("home_goals_ft") or 0)
        af   = float(row.get("away_goals_ft") or 0)
        total_goals_match = hf + af
        if total_goals_match == 0:
            continue
        xg_h = _get_xg(row, is_home=True)
        xg_a = _get_xg(row, is_home=False)
        if xg_h is None or xg_a is None:
            continue
        total_xg_match = xg_h + xg_a
        # avg xG per goal in this match
        xg_per_goal = total_xg_match / total_goals_match
        quality_scores.append(xg_per_goal)

    if quality_scores:
        avg_xg_per_goal = round(sum(quality_scores) / len(quality_scores), 3)
        # Global avg across all football is ~0.10 per shot on target → ~0.35 per goal
        GLOBAL_AVG_XG_PER_GOAL = 0.35
        quality_ratio = round(avg_xg_per_goal / GLOBAL_AVG_XG_PER_GOAL, 2)
        # >1 = high quality goals (high xG chances converted)
        # <1 = low quality goals (difficult chances scored — lucky/clinical)
        if quality_ratio > 1.2:
            quality_label = "ALTA QUALITÀ"
        elif quality_ratio < 0.8:
            quality_label = "GOL DI FORTUNA"
        else:
            quality_label = "QUALITÀ MEDIA"
    else:
        avg_xg_per_goal = None
        quality_ratio   = None
        quality_label   = "N/D"

    # ═══ BLOCK 13: TIME PRESSURE FACTOR ══════════════════════════════════
    minutes_remaining = 90 - current_minute
    if minutes_remaining <= 15:
        time_pressure = "ALTA"
    elif minutes_remaining <= 30:
        time_pressure = "MEDIA"
    else:
        time_pressure = "BASSA"

    # ═══ BLOCK 14: PATTERN ATTIVI ════════════════════════════════════════
    # Simple pattern detection from historical data
    patterns = []

    # Pattern 1: Goal in next 20 min from similar matches
    goal_in_20 = sum(1 for m in matched
                     if any(_parse_minute(e["minute"]) <= current_minute + 20
                            for e in m["events_after"]))
    if _safe_pct(goal_in_20, n) > 55:
        patterns.append({
            "label": f"Gol entro {current_minute+20}'",
            "status": "ATTIVO",
            "pct": _safe_pct(goal_in_20, n)
        })

    # Pattern 2: Score stays same
    if _safe_pct(stays_same, n) > 40:
        patterns.append({
            "label": f"Risultato {current_state} si mantiene",
            "status": "FREQUENTE",
            "pct": _safe_pct(stays_same, n)
        })

    # Pattern 3: Home/Away scores next
    if _safe_pct(next_goal_home, n) > 40:
        patterns.append({
            "label": "Casa segna prossimo",
            "status": "ATTIVO",
            "pct": _safe_pct(next_goal_home, n)
        })
    elif _safe_pct(next_goal_away, n) > 40:
        patterns.append({
            "label": "Trasferta segna prossimo",
            "status": "ATTIVO",
            "pct": _safe_pct(next_goal_away, n)
        })

    patterns = patterns[:3]  # max 3 patterns shown

    # ═══ BLOCK 17: ENTRY TIMING SUGGESTION ═══════════════════════════════
    # Find the 10-min window with highest next-goal probability
    window_counts = {}
    for start in range(current_minute, 85, 5):
        end = start + 10
        cnt = sum(1 for m in matched
                  if any(start <= _parse_minute(e["minute"]) < end
                         for e in m["events_after"]))
        window_counts[f"{start}'-{end}'"] = cnt

    best_window = max(window_counts, key=window_counts.get) if window_counts else f"{current_minute}'-{current_minute+10}'"

    # ═══ DECISION ENGINE ═════════════════════════════════════════════════
    at_least_one_more = n - goals_remaining_dist[0]
    prob_next_goal    = _safe_pct(at_least_one_more, n)
    over_25_live      = _safe_pct(sum(1 for m in matched
                                      if float(m["row"].get("home_goals_ft") or 0) +
                                         float(m["row"].get("away_goals_ft") or 0) >= 3), n)
    btts_live         = _safe_pct(sum(1 for m in matched
                                      if float(m["row"].get("home_goals_ft") or 0) >= 1
                                      and float(m["row"].get("away_goals_ft") or 0) >= 1), n)
    over_15_live      = _safe_pct(sum(1 for m in matched
                                      if float(m["row"].get("home_goals_ft") or 0) +
                                         float(m["row"].get("away_goals_ft") or 0) >= 2), n)

    # Signal strength 0-100 per Andrea spec:
    # signal = (P_next_goal * 0.4 + over25 * 0.2 + btts * 0.2 + momentum * 0.2) * 100
    # Dove tutti i valori sono in [0,1] (probability fractions)
    # Poi confidence e time_pressure come moltiplicatori di aggiustamento

    _p_next  = prob_next_goal / 100   # già calcolato sopra come pct
    _p_o25   = over_25_live   / 100
    _p_btts  = btts_live      / 100
    # momentum component: usa la percentuale di partite con ritmo in aumento
    _p_mom   = _safe_pct(momentum_up, n) / 100

    raw_signal = (_p_next * 0.4 + _p_o25 * 0.2 + _p_btts * 0.2 + _p_mom * 0.2) * 100

    # Confidence multiplier
    if confidence == "ALTA":
        raw_signal = min(raw_signal * 1.10, 100)
    elif confidence == "BASSA":
        raw_signal = raw_signal * 0.70

    # Time pressure boost (poca partita rimanente = più urgenza)
    if time_pressure == "ALTA":
        raw_signal = min(raw_signal * 1.05, 100)

    signal_strength = round(raw_signal)

    if signal_strength >= 70:
        signal_label = "FORTE"
    elif signal_strength >= 50:
        signal_label = "MEDIO"
    else:
        signal_label = "DEBOLE"

    # Value vs live odds — real average odds from matched historical matches
    # Formula: value = model_prob - implied_prob, where implied_prob = 100 / avg_odds
    # Falls back to market average constants only if no odds data exists in DB
    _o25_vals  = _odds_from_matched(matched, "odds_over25")
    _btts_vals = _odds_from_matched(matched, "odds_btts_yes")
    _o15_vals  = _odds_from_matched(matched, "odds_over15")

    _avg_o25  = sum(_o25_vals)  / len(_o25_vals)  if _o25_vals  else 0
    _avg_btts = sum(_btts_vals) / len(_btts_vals) if _btts_vals else 0
    _avg_o15  = sum(_o15_vals)  / len(_o15_vals)  if _o15_vals  else 0

    value_over25 = round(over_25_live - (100 / _avg_o25  if _avg_o25  > 1 else 47.5), 1)
    value_btts   = round(btts_live    - (100 / _avg_btts if _avg_btts > 1 else 45.0), 1)
    value_over15 = round(over_15_live - (100 / _avg_o15  if _avg_o15  > 1 else 55.0), 1)

    # Rischio & Confidence
    if n >= 50:
        rischio = "BASSO"
    elif n >= 20:
        rischio = "MEDIO"
    else:
        rischio = "ALTO"

    # Azione consigliata
    if signal_strength >= 65 and prob_next_goal >= 55:
        azione = "ENTRA ORA"
        azione_markets = []
        if over_25_live >= 55:
            azione_markets.append("Over 2.5")
        if btts_live >= 55:
            azione_markets.append("BTTS")
        if over_15_live >= 65:
            azione_markets.append("Over 1.5")
        if not azione_markets:
            azione_markets = ["Over 1.5"]
    else:
        azione = "ATTENDI"
        azione_markets = []

    no_trade_reasons = []
    if next_goal_none / n > 0.5:
        no_trade_reasons.append("Nessun gol probabile")
    if momentum_down > momentum_up:
        no_trade_reasons.append("Momentum in calo significativo")
    if signal_strength < 40:
        no_trade_reasons.append("Segnale debole")

    # ═══ 1H / 2H summary stats ═══════════════════════════════════════════
    # From ALL matched matches, calculate 1H and 2H summary
    total_1h_goals = sum(
        sum(1 for e in (goal_events.get(int(m["row"].get("match_id", 0)), []))
            if e.get("half", 1) == 1)
        for m in matched
    )
    total_2h_goals = sum(
        sum(1 for e in (goal_events.get(int(m["row"].get("match_id", 0)), []))
            if e.get("half", 2) == 2)
        for m in matched
    )

    prob_1h_goal = _safe_pct(
        sum(1 for m in matched
            if any(e.get("half", 1) == 1 for e in goal_events.get(int(m["row"].get("match_id", 0)), []))),
        n
    )
    prob_2h_goal = _safe_pct(
        sum(1 for m in matched
            if any(e.get("half", 2) == 2 for e in goal_events.get(int(m["row"].get("match_id", 0)), []))),
        n
    )

    over_15_1h = _safe_pct(
        sum(1 for m in matched
            if sum(1 for e in goal_events.get(int(m["row"].get("match_id", 0)), [])
                   if e.get("half", 1) == 1) >= 2), n
    )
    over_25_1h = _safe_pct(
        sum(1 for m in matched
            if sum(1 for e in goal_events.get(int(m["row"].get("match_id", 0)), [])
                   if e.get("half", 1) == 1) >= 3), n
    )
    over_15_2h = _safe_pct(
        sum(1 for m in matched
            if sum(1 for e in goal_events.get(int(m["row"].get("match_id", 0)), [])
                   if e.get("half", 2) == 2) >= 2), n
    )
    over_25_2h = _safe_pct(
        sum(1 for m in matched
            if sum(1 for e in goal_events.get(int(m["row"].get("match_id", 0)), [])
                   if e.get("half", 2) == 2) >= 3), n
    )

    # Chi segna per 1H and 2H
    chi_segna_1h = {"casa": 0, "trasferta": 0, "nessun_gol": 0}
    chi_segna_2h = {"casa": 0, "trasferta": 0, "nessun_gol": 0}
    for m in matched:
        mid = int(m["row"].get("match_id", 0))
        evs = goal_events.get(mid, [])
        evs_1h = [e for e in evs if e.get("half", 1) == 1]
        evs_2h = [e for e in evs if e.get("half", 2) == 2]
        if not evs_1h:
            chi_segna_1h["nessun_gol"] += 1
        elif any(e["is_home"] == 1 for e in evs_1h):
            chi_segna_1h["casa"] += 1
        else:
            chi_segna_1h["trasferta"] += 1
        if not evs_2h:
            chi_segna_2h["nessun_gol"] += 1
        elif any(e["is_home"] == 1 for e in evs_2h):
            chi_segna_2h["casa"] += 1
        else:
            chi_segna_2h["trasferta"] += 1

    # HT results distribution
    ht_results = {}
    ft_results_dist = {}
    for m in matched:
        hr = m["row"].get("ht_result", "?")
        fr = m["row"].get("ft_result", "?")
        ht_results[hr] = ht_results.get(hr, 0) + 1
        ft_results_dist[fr] = ft_results_dist.get(fr, 0) + 1

    top_ht_results = sorted(ht_results.items(), key=lambda x: x[1], reverse=True)[:5]
    top_ft_results = sorted(ft_results_dist.items(), key=lambda x: x[1], reverse=True)[:5]

    # Future timeframe distribution (goal distribution from current minute onward)
    future_buckets = _get_future_timeframes(current_minute)
    future_dist = {name: 0 for name, _, _ in future_buckets}
    future_match_counts = {name: 0 for name, _, _ in future_buckets}

    for m in matched:
        for e in m["events_after"]:
            em = _parse_minute(e["minute"])
            for name, lo, hi in future_buckets:
                if lo <= em <= hi:
                    future_dist[name] = future_dist.get(name, 0) + 1
                    break

    total_future = sum(future_dist.values())
    future_pct = {
        k: round(v / total_future * 100, 1) if total_future > 0 else 0.0
        for k, v in future_dist.items()
    }

    # ESITO FINALE (1X2 from current state)
    final_home_wins = sum(1 for m in matched
                          if float(m["row"].get("home_goals_ft") or 0) >
                             float(m["row"].get("away_goals_ft") or 0))
    final_draws     = sum(1 for m in matched
                          if float(m["row"].get("home_goals_ft") or 0) ==
                             float(m["row"].get("away_goals_ft") or 0))
    final_away_wins = sum(1 for m in matched
                          if float(m["row"].get("home_goals_ft") or 0) <
                             float(m["row"].get("away_goals_ft") or 0))

    # ── FULL GOAL DISTRIBUTION (ALL goals in matched matches, no minute filter)
    # Used by live.py Row 2 charts so both 1H and 2H charts always have data
    # regardless of current_minute. Keys match H1_BUCKETS + H2_BUCKETS in live.py.
    _all_bkts = [
        ("0-15",  lambda m, h: 1  <= m <= 15  and h == 1),
        ("16-30", lambda m, h: 16 <= m <= 30  and h == 1),
        ("31-45", lambda m, h: 31 <= m <= 45  and h == 1),
        ("45+",   lambda m, h: m  >  45        and h == 1),
        ("46-60", lambda m, h: 46 <= m <= 60  and h == 2),
        ("61-75", lambda m, h: 61 <= m <= 75  and h == 2),
        ("76-90", lambda m, h: 76 <= m <= 90  and h == 2),
        ("90+",   lambda m, h: m  >  90        and h == 2),
    ]
    _full_dist_raw = {b: 0 for b, _ in _all_bkts}
    for m in matched:
        mid_key = int(m["row"].get("match_id", 0))
        for e in goal_events.get(mid_key, []):
            em = _parse_minute(e["minute"])
            eh = e.get("half", 1 if em <= 45 else 2)
            for b_name, check_fn in _all_bkts:
                if check_fn(em, eh):
                    _full_dist_raw[b_name] += 1
                    break
    _full_total = sum(_full_dist_raw.values()) or 1
    goal_distribution = {
        k: round(v / _full_total * 100, 1)
        for k, v in _full_dist_raw.items()
    }

    # Count fractions for 1H/2H panel display
    n_1h_goal_count = sum(1 for m in matched
        if any(e.get("half", 1) == 1
               for e in goal_events.get(int(m["row"].get("match_id", 0)), [])))
    n_2h_goal_count = sum(1 for m in matched
        if any(e.get("half", 2) == 2
               for e in goal_events.get(int(m["row"].get("match_id", 0)), [])))
    n_over15_1h_count = sum(1 for m in matched
        if sum(1 for e in goal_events.get(int(m["row"].get("match_id", 0)), [])
               if e.get("half", 1) == 1) >= 2)
    n_over25_1h_count = sum(1 for m in matched
        if sum(1 for e in goal_events.get(int(m["row"].get("match_id", 0)), [])
               if e.get("half", 1) == 1) >= 3)
    n_over15_2h_count = sum(1 for m in matched
        if sum(1 for e in goal_events.get(int(m["row"].get("match_id", 0)), [])
               if e.get("half", 2) == 2) >= 2)
    n_over25_2h_count = sum(1 for m in matched
        if sum(1 for e in goal_events.get(int(m["row"].get("match_id", 0)), [])
               if e.get("half", 2) == 2) >= 3)

    return {
        # Meta
        "found":           n,
        "confidence":      confidence,
        "used_window":     used_window,
        "current_state":   current_state,
        "post_goal_mode":  first_goal_minute is not None,

        # 1H summary
        "prob_1h_goal":    prob_1h_goal,
        "over_15_1h":      over_15_1h,
        "over_25_1h":      over_25_1h,
        "chi_segna_1h":    {k: _safe_pct(v, n) for k, v in chi_segna_1h.items()},

        # 2H summary
        "prob_2h_goal":    prob_2h_goal,
        "over_15_2h":      over_15_2h,
        "over_25_2h":      over_25_2h,
        "chi_segna_2h":    {k: _safe_pct(v, n) for k, v in chi_segna_2h.items()},

        # HT/FT results
        "top_ht_results":  top_ht_results,
        "top_ft_results":  top_ft_results,

        # Future timeframe
        "future_timeframes": future_pct,
        "future_buckets_order": [name for name, _, _ in future_buckets],

        # Next goal
        "next_goal_home":  _safe_pct(next_goal_home, n),
        "next_goal_away":  _safe_pct(next_goal_away, n),
        "next_goal_none":  _safe_pct(next_goal_none, n),
        "next_goal_timing": {k: _safe_pct(v, n) for k, v in next_goal_timing.items()},

        # BTTS / Final 1X2
        "btts_si":         btts_live,
        "btts_no":         round(100 - btts_live, 1),
        "final_home":      _safe_pct(final_home_wins, n),
        "final_draw":      _safe_pct(final_draws, n),
        "final_away":      _safe_pct(final_away_wins, n),

        # Block 1: Evoluzione risultato (state transitions)
        "top_transitions": top_transitions,
        "stays_same_pct":  _safe_pct(stays_same, n),

        # Block 4/5: Vantaggio/Svantaggio
        "home_doubles_pct":    _safe_pct(home_doubles, n),
        "home_equalises_pct":  _safe_pct(home_equalises, n),
        "home_concedes_pct":   _safe_pct(home_concedes_all, n),
        "away_comeback_pct":   _safe_pct(away_comebacks, n),
        "away_no_more_pct":    _safe_pct(away_no_more, n),
        "away_scores_loses_pct": _safe_pct(away_scores_loses, n),

        # Block 7: Gol rimanenti
        "gol_0_pct":           _safe_pct(goals_remaining_dist[0], n),
        "gol_1_pct":           _safe_pct(goals_remaining_dist[1], n),
        "gol_2plus_pct":       _safe_pct(goals_remaining_dist[2], n),
        "avg_goals_remaining": avg_goals_remaining,

        # Block 8: Stabilità
        "result_stable_pct":   _safe_pct(result_stable, n),
        "result_changes_pct":  _safe_pct(result_changes, n),

        # Block 9: Momentum
        "momentum_up_pct":     _safe_pct(momentum_up, n),
        "momentum_same_pct":   _safe_pct(momentum_same, n),
        "momentum_down_pct":   _safe_pct(momentum_down, n),

        # Block 10: Dead game
        "dead_game_pct":       dead_game_pct,
        "dead_game_risk":      dead_game_risk,

        # Block 11: Deviazione xG
        "xg_diff_home":        xg_diff_home,       # float or None
        "xg_diff_away":        xg_diff_away,        # float or None
        "xg_label_home":       xg_label_home,       # SOVRAPERFORMA / IN LINEA / SOTTOPERFORMA
        "xg_label_away":       xg_label_away,
        "xg_data_available":   xg_data_available,   # bool — False if DB has no xG

        # Block 12: Qualità Ultimo Gol
        "avg_xg_per_goal":     avg_xg_per_goal,     # float or None
        "quality_ratio":       quality_ratio,        # float or None (>1 = hard chances scored)
        "quality_label":       quality_label,        # ALTA QUALITÀ / QUALITÀ MEDIA / GOL DI FORTUNA

        # Block 13: Time pressure
        "time_pressure":       time_pressure,
        "minutes_remaining":   minutes_remaining,

        # Block 14: Patterns
        "patterns":            patterns,

        # Block 17: Entry timing
        "best_entry_window":   best_window,
        "entry_window_data":   window_counts,

        # Decision Engine
        "signal_strength":     signal_strength,
        "signal_label":        signal_label,
        "prob_next_goal":      prob_next_goal,
        "over_25_live":        over_25_live,
        "btts_live":           btts_live,
        "over_15_live":        over_15_live,
        "value_over25":        value_over25,
        "value_btts":          value_btts,
        "value_over15":        value_over15,
        "rischio":             rischio,
        "confidence_engine":   confidence,
        "azione":              azione,
        "azione_markets":      azione_markets,
        "no_trade_reasons":    no_trade_reasons,

        # at_least_one_more for backward compat
        "at_least_one_more_pct": _safe_pct(at_least_one_more, n),
        "most_likely_ft":        top_transitions[0][0] if top_transitions else "N/A",
        "top_scores":            top_transitions,

        # Full goal distribution (all matched matches, no minute filter)
        # Provides data for both 1H and 2H dist charts regardless of current_minute
        "goal_distribution":   goal_distribution,

        # Count fractions for 1H/2H panel header (e.g. 138/310)
        "n_1h_goal_count":     n_1h_goal_count,
        "n_2h_goal_count":     n_2h_goal_count,
        "n_over15_1h":         n_over15_1h_count,
        "n_over25_1h":         n_over25_1h_count,
        "n_over15_2h":         n_over15_2h_count,
        "n_over25_2h":         n_over25_2h_count,
        "n_1h_sample":         n,
        "n_2h_sample":         n,
    }

# ═══════════════════════════════════════════════════════════════════════════
# VALUE ENTRY THRESHOLD — Andrea spec (File 1 formulas)
# Appended — does NOT modify any existing function above
# ═══════════════════════════════════════════════════════════════════════════

def calc_value_entry_threshold(
    df: pd.DataFrame,
    goal_events: dict,
    current_minute: int,
    home_score: int,
    away_score: int,
    score_index: dict = None,
    edge: float = 0.05,
    minute_window: int = 5,
) -> dict:
    """
    Andrea File-1 formulas: Value Entry Threshold table.

    Base filter (same as analyze_live_state_v2):
        similar_matches = matches where score == (home_score, away_score)
        at some minute in [current_minute ± window]

    ALL probability calculations use ONLY future events:
        goal_minute > current_minute   ← Andrea "IMPORTANTISSIMO"

    Returns:
    {
        "total": int,                        # similar matches found
        "markets": [                         # one dict per market row
            {
              "label":     str,              # e.g. "OVER 0.5 LIVE"
              "prob":      float,            # real probability %
              "breakeven": float,            # 1 / (prob/100)
              "min_odds":  float,            # breakeven * (1 + edge)
            }, ...
        ],
        "evento_principale": {               # right-side top card
            "label":     "ALMENO 1 GOL",
            "prob":      float,
            "count":     int,
            "total":     int,
            "breakeven": float,
            "min_odds":  float,
        },
        "distribuzione": {                   # donut chart data
            "zero_zero_pct":   float,        # % ended 0-0 from this state
            "goal_pct":        float,        # % had at least 1 more goal
            "zero_zero_count": int,
            "goal_count":      int,
        },
        "next_goal_buckets": {               # relative delta buckets
            "0-10":  float,                  # % of future goals in 0-10 min
            "10-20": float,
            "20-30": float,
            "30+":   float,
        },
        "best_bucket": str,                  # bucket with highest %
        "edge_used":   float,                # edge % used
    }
    """
    # ── Step 1: find similar matches (same logic as v2 for consistency) ────
    min_lo = max(0, current_minute - minute_window)
    min_hi = current_minute + minute_window
    current_half = 1 if current_minute <= 45 else 2

    similar = []
    for _, row in df.iterrows():
        mid = row.get("match_id")
        if mid is None:
            continue
        mid_int = int(mid)
        events  = goal_events.get(mid_int, [])

        found = False
        for chk in range(min_lo, min_hi + 1):
            if score_index and mid_int in score_index and chk < len(score_index[mid_int]):
                h, a = score_index[mid_int][chk]
            else:
                h = sum(1 for e in events if e["is_home"] == 1 and _parse_minute(e["minute"]) <= chk)
                a = sum(1 for e in events if e["is_home"] == 0 and _parse_minute(e["minute"]) <= chk)
            if h == home_score and a == away_score:
                if (1 if chk <= 45 else 2) == current_half:
                    found = True
                    break
        if not found:
            continue

        # Separate future events (Andrea: goal_minute > current_minute)
        future_events = [e for e in events if _parse_minute(e["minute"]) > current_minute]
        similar.append({"row": row, "future": future_events})

    total = len(similar)

    # Fallback: widen window if sample too small
    if total < 20 and minute_window == 5:
        return calc_value_entry_threshold(
            df, goal_events, current_minute, home_score, away_score,
            score_index=score_index, edge=edge, minute_window=10,
        )

    if total == 0:
        return {"total": 0, "markets": [], "evento_principale": {}, "distribuzione": {}, "next_goal_buckets": {}, "best_bucket": "", "edge_used": edge}

    def _p(count):
        """Probability % from count/total."""
        return _safe_pct(count, total)

    def _be(prob_pct):
        """Breakeven odds from probability %."""
        if prob_pct <= 0:
            return 0.0
        return round(100 / prob_pct, 2)

    def _mo(be):
        """Min odds = breakeven * (1 + edge)."""
        return round(be * (1 + edge), 2)

    # ── Step 2: per-market counts using FUTURE events only ─────────────────

    # Over 0.5 LIVE: at least 1 future goal in match
    c_over05  = sum(1 for m in similar if len(m["future"]) >= 1)

    # Over 1.5 LIVE: at least 2 future goals
    c_over15  = sum(1 for m in similar if len(m["future"]) >= 2)

    # Over 2.5 LIVE: at least 3 future goals
    c_over25  = sum(1 for m in similar if len(m["future"]) >= 3)

    # BTTS YES: both teams score in the full match (final state)
    c_btts_yes = sum(1 for m in similar
                     if float(m["row"].get("home_goals_ft") or 0) >= 1
                     and float(m["row"].get("away_goals_ft") or 0) >= 1)
    c_btts_no  = total - c_btts_yes

    # Over 0.5 1T: at least 1 goal between current_minute and 45' (1H only)
    # Andrea Point 9 / 12: CRUCIAL — only goals after current_minute up to 45
    if current_minute < 45:
        c_o05_1t = sum(1 for m in similar
                       if any(_parse_minute(e["minute"]) > current_minute
                              and _parse_minute(e["minute"]) <= 45
                              for e in m["future"]))
        c_o15_1t = sum(1 for m in similar
                       if sum(1 for e in m["future"]
                              if _parse_minute(e["minute"]) > current_minute
                              and _parse_minute(e["minute"]) <= 45) >= 2)
    else:
        # Already in 2H — 1T markets not applicable; set to 0
        c_o05_1t = 0
        c_o15_1t = 0

    # 1X2 final (Back Casa / Pareggio / Trasferta)
    c_home  = sum(1 for m in similar
                  if float(m["row"].get("home_goals_ft") or 0) >
                     float(m["row"].get("away_goals_ft") or 0))
    c_draw  = sum(1 for m in similar
                  if float(m["row"].get("home_goals_ft") or 0) ==
                     float(m["row"].get("away_goals_ft") or 0))
    c_away  = sum(1 for m in similar
                  if float(m["row"].get("home_goals_ft") or 0) <
                     float(m["row"].get("away_goals_ft") or 0))

    # ── Step 3: build markets list ─────────────────────────────────────────
    def _row(label, count):
        p  = _p(count)
        be = _be(p)
        mo = _mo(be)
        return {"label": label, "prob": p, "breakeven": be, "min_odds": mo, "count": count}

    markets = [
        _row("OVER 0.5 LIVE",    c_over05),
        _row("OVER 1.5 LIVE",    c_over15),
        _row("OVER 2.5 LIVE",    c_over25),
        _row("BTTS YES",         c_btts_yes),
        _row("BTTS NO",          c_btts_no),
        _row("OVER 0.5 1° TEMPO", c_o05_1t),
        _row("OVER 1.5 1° TEMPO", c_o15_1t),
        _row("BACK CASA",        c_home),
        _row("BACK PAREGGIO",    c_draw),
        _row("BACK TRASFERTA",   c_away),
    ]

    # ── Step 4: Evento principale = Over 0.5 (almeno 1 gol) ───────────────
    ep_prob = _p(c_over05)
    ep_be   = _be(ep_prob)
    evento_principale = {
        "label":     "ALMENO 1 GOL",
        "prob":      ep_prob,
        "count":     c_over05,
        "total":     total,
        "breakeven": ep_be,
        "min_odds":  _mo(ep_be),
    }

    # ── Step 5: Distribuzione risultato finale (donut chart) ───────────────
    # From this state: how many ended 0-0 (no more goals) vs had 1+ more goal
    c_no_more = sum(1 for m in similar if len(m["future"]) == 0)
    c_at_least_one = total - c_no_more
    distribuzione = {
        "zero_zero_pct":   _p(c_no_more),
        "goal_pct":        _p(c_at_least_one),
        "zero_zero_count": c_no_more,
        "goal_count":      c_at_least_one,
    }

    # ── Step 6: Next goal bucket (relative delta — Andrea Points 10/11) ────
    bucket_counts = {"0-10": 0, "10-20": 0, "20-30": 0, "30+": 0}
    total_future_goals = 0
    for m in similar:
        if not m["future"]:
            continue
        # First future goal only (next goal window)
        first_fg = sorted(m["future"], key=lambda e: _parse_minute(e["minute"]))[0]
        delta = _parse_minute(first_fg["minute"]) - current_minute
        if delta <= 10:
            bucket_counts["0-10"] += 1
        elif delta <= 20:
            bucket_counts["10-20"] += 1
        elif delta <= 30:
            bucket_counts["20-30"] += 1
        else:
            bucket_counts["30+"] += 1
        total_future_goals += 1

    if total_future_goals > 0:
        next_goal_buckets = {
            k: round(v / total_future_goals * 100, 1)
            for k, v in bucket_counts.items()
        }
    else:
        next_goal_buckets = {k: 0.0 for k in bucket_counts}

    best_bucket = max(next_goal_buckets, key=next_goal_buckets.get) if total_future_goals > 0 else "0-10"

    return {
        "total":              total,
        "markets":            markets,
        "evento_principale":  evento_principale,
        "distribuzione":      distribuzione,
        "next_goal_buckets":  next_goal_buckets,
        "best_bucket":        best_bucket,
        "edge_used":          edge,
    }


# ═══════════════════════════════════════════════════════════════════════════
# LIVE GOAL PROBABILITY — filtro gol + KPI post-minuto (trader logic)
# ═══════════════════════════════════════════════════════════════════════════

def _goal_criteria_tolerance(goal_index: int, base_tolerance: int, expanded: bool = False) -> int:
    if goal_index == 0:
        return 5 if expanded else 4
    tol = max(base_tolerance, 5)
    if expanded:
        tol += 2
    return tol


def filter_matches_by_goal_criteria(
    matches_df: pd.DataFrame,
    criteria: list,
    tolerance: int = 2,
) -> tuple[pd.DataFrame, bool]:
    """
    Partite dove 1°/2°/3° gol combaciano (±tol) con minuto e squadra inseriti.
    Espande ±2 se campione < 5.
    """
    if matches_df is None or matches_df.empty or not criteria:
        return matches_df.iloc[0:0], False

    def _collect(expanded: bool) -> list:
        selected = []
        for _, row in matches_df.iterrows():
            home_t = row.get("home_goal_timings", "")
            away_t = row.get("away_goal_timings", "")
            if pd.isna(home_t):
                home_t = ""
            if pd.isna(away_t):
                away_t = ""
            match_goals = get_sorted_goals_with_team(home_t, away_t)
            if len(match_goals) < len(criteria):
                continue
            matched = True
            for i, (target_m, target_team) in enumerate(criteria):
                m, team = match_goals[i]
                tol_i = _goal_criteria_tolerance(i, tolerance, expanded)
                if not (target_m - tol_i <= m <= target_m + tol_i) or team != target_team:
                    matched = False
                    break
            if matched:
                selected.append(row)
        return selected

    expanded = False
    rows = _collect(expanded)
    if len(rows) < 5:
        expanded = True
        rows = _collect(expanded)
    if not rows:
        return matches_df.iloc[0:0], expanded
    return pd.DataFrame(rows), expanded


def get_similar_matches_dataframe(
    df: pd.DataFrame,
    goal_events: dict,
    current_minute: int,
    home_score: int,
    away_score: int,
    score_index: dict = None,
    minute_window: int = 5,
) -> pd.DataFrame:
    """Partite con stesso risultato al minuto corrente (±window), stesso tempo."""
    if df is None or df.empty:
        return df.iloc[0:0] if df is not None else pd.DataFrame()

    min_lo = max(0, current_minute - minute_window)
    min_hi = current_minute + minute_window
    current_half = 1 if current_minute <= 45 else 2
    rows = []

    for _, row in df.iterrows():
        mid = row.get("match_id")
        if mid is None:
            continue
        mid_int = int(mid)
        events = goal_events.get(mid_int, [])

        found = False
        for chk in range(min_lo, min_hi + 1):
            if score_index and mid_int in score_index and chk < len(score_index[mid_int]):
                h, a = score_index[mid_int][chk]
            else:
                h = sum(1 for e in events if e["is_home"] == 1 and _parse_minute(e["minute"]) <= chk)
                a = sum(1 for e in events if e["is_home"] == 0 and _parse_minute(e["minute"]) <= chk)
            if h == home_score and a == away_score:
                if (1 if chk <= 45 else 2) == current_half:
                    found = True
                    break
        if found:
            rows.append(row)

    if len(rows) < 20 and minute_window == 5:
        return get_similar_matches_dataframe(
            df, goal_events, current_minute, home_score, away_score,
            score_index=score_index, minute_window=10,
        )
    return pd.DataFrame(rows) if rows else df.iloc[0:0]


def calc_live_goal_probability(
    matches_df: pd.DataFrame,
    input_minute: int,
    edge: float = 0.05,
    min_goals_after: int = 1,
) -> dict | None:
    """
    P(almeno N gol dopo input_minute) su campione filtrato.
    fair_odds = 1/prob | recommended = 1/(prob*(1-edge))
    """
    if matches_df is None or matches_df.empty:
        return None

    total = 0
    with_goal = 0
    for _, row in matches_df.iterrows():
        home_t = row.get("home_goal_timings", "") or ""
        away_t = row.get("away_goal_timings", "") or ""
        if pd.isna(home_t):
            home_t = ""
        if pd.isna(away_t):
            away_t = ""
        all_goals = get_all_goals(str(home_t), str(away_t))
        if not all_goals:
            continue
        future_goals = [g for g in all_goals if g > input_minute]
        total += 1
        if len(future_goals) >= min_goals_after:
            with_goal += 1

    if total == 0:
        return None

    prob = with_goal / total
    fair_odds = round(1 / prob, 2) if prob > 0 else 0.0
    recommended_odds = round(1 / (prob * (1 - edge)), 2) if prob > 0 else 0.0
    label = "ALMENO 1 GOL" if min_goals_after == 1 else f"ALMENO {min_goals_after} GOL"

    return {
        "label": label,
        "prob": round(prob * 100, 1),
        "with_goal": with_goal,
        "total": total,
        "fair_odds": fair_odds,
        "recommended_odds": recommended_odds,
        "edge": edge,
        "min_goals_after": min_goals_after,
    }


def filter_by_first_goal_range(
    matches_df: pd.DataFrame,
    minute: int,
    tolerance: int = 5,
    team: str | None = None,
) -> list:
    """
    Partite dove il primo gol cade in [minute - tolerance, minute + tolerance].
    Opzionale: team='home' | 'away' per filtrare chi segna per primo.
    Ritorna [(first_min, first_team, all_goals), ...].
    """
    from utils import get_first_goal_detail

    if matches_df is None or matches_df.empty:
        return []

    filtered = []
    for _, row in matches_df.iterrows():
        home_t = row.get("home_goal_timings", "") or ""
        away_t = row.get("away_goal_timings", "") or ""
        if pd.isna(home_t):
            home_t = ""
        if pd.isna(away_t):
            away_t = ""
        first, first_team, _ = get_first_goal_detail(str(home_t), str(away_t))
        if first is None:
            continue
        if abs(first - minute) > tolerance:
            continue
        if team is not None and first_team != team:
            continue
        all_goals = _match_goals_with_raw(str(home_t), str(away_t))
        filtered.append((first, first_team, all_goals))
    return filtered


FIXED_MATCH_INTERVALS = [
    ("0-15",  0,  15),
    ("16-30", 16, 30),
    ("31-45", 31, 45),
    ("45+",   None, None),
    ("46-60", 46, 60),
    ("61-75", 61, 75),
    ("76-90", 76, 90),
    ("90+",   None, None),
]


def _match_goals_with_raw(home_str: str, away_str: str) -> list[tuple[int, str]]:
    """[(minute, raw_token), ...] ordinati per minuto."""
    goals = []
    for m, raw in parse_goal_timings(home_str or ""):
        goals.append((m, raw))
    for m, raw in parse_goal_timings(away_str or ""):
        goals.append((m, raw))
    goals.sort(key=lambda x: x[0])
    return goals


def _is_stoppage_goal(minute: int, raw: str, half: int) -> bool:
    """Riconosce gol in recupero 1T (45+) o 2T (90+) dal token originale."""
    raw_s = str(raw).strip()
    if "'" in raw_s:
        try:
            base = int(raw_s.split("'")[0])
            return (half == 1 and base == 45) or (half == 2 and base >= 90)
        except ValueError:
            pass
    if "+" in raw_s:
        try:
            base = int(raw_s.split("+")[0])
            return (half == 1 and base == 45) or (half == 2 and base >= 90)
        except ValueError:
            pass
    return (half == 1 and minute > 45) or (half == 2 and minute > 90)


def _goal_in_fixed_interval(minute: int, raw: str, key: str, start, end) -> bool:
    """True se il gol cade nella fascia fissa (45+/90+ con recupero)."""
    if key == "45+":
        return _is_stoppage_goal(minute, raw, half=1)
    if key == "90+":
        return _is_stoppage_goal(minute, raw, half=2)
    return start < minute <= end


def _fixed_future_intervals(input_minute: int) -> list[tuple]:
    """Fasce fisse ancora aperte (es. 64' → 61-75, 76-90, 90+)."""
    minute = int(input_minute)
    out = []
    for key, start, end in FIXED_MATCH_INTERVALS:
        if key == "45+" and minute <= 45:
            out.append((key, start, end))
        elif key == "90+" and minute <= 90:
            out.append((key, start, end))
        elif start is not None and end is not None and end > minute:
            out.append((key, start, end))
    return out


def build_dynamic_future_table(
    filtered_matches: list,
    input_minute: int,
    step: int = 15,
) -> dict:
    """
    Dataset unico: per ogni fascia fissa, % partite con ≥1 gol nel range
    (solo gol DOPO input_minute).
    """
    intervals = _fixed_future_intervals(input_minute)
    results = {}
    total_n = len(filtered_matches)
    for key, start, end in intervals:
        goals_in_interval = 0
        for _first, _team, all_goals in filtered_matches:
            future_goals = [(m, r) for m, r in all_goals if m > input_minute]
            if any(_goal_in_fixed_interval(m, r, key, start, end) for m, r in future_goals):
                goals_in_interval += 1
        pct = round(goals_in_interval / total_n * 100, 1) if total_n > 0 else 0.0
        results[key] = {
            "total": total_n,
            "goals": goals_in_interval,
            "pct": pct,
        }
    return results


def calc_post_goal_future_analysis(
    matches_df: pd.DataFrame,
    reference_minute: int,
    input_minute: int,
    tolerance: int = 5,
) -> dict:
    """
    Analisi post-gol: 3 tabelle (totale, casa primo gol, trasferta primo gol).
    Filtro: abs(primo_gol - input_minute) <= tolerance.
    """
    used_tol = tolerance
    for tol in (tolerance, tolerance + 5, tolerance + 10):
        total_matches = filter_by_first_goal_range(
            matches_df, input_minute, tolerance=tol, team=None,
        )
        if len(total_matches) >= 20 or tol == tolerance + 10:
            used_tol = tol
            break

    tables = {}
    for key, team in (
        ("total", None),
        ("home", "home"),
        ("away", "away"),
    ):
        subset = filter_by_first_goal_range(
            matches_df, input_minute, tolerance=used_tol, team=team,
        )
        tables[key] = {
            "count": len(subset),
            "matches": subset,
            "table": build_dynamic_future_table(subset, input_minute),
        }

    return {
        "reference_minute": reference_minute,
        "input_minute": input_minute,
        "tolerance": used_tol,
        "tables": tables,
    }


def generate_live_trigger(
    table: dict,
    market_odds: float | None = None,
    filtered_matches: list | None = None,
    input_minute: int | None = None,
) -> dict:
    """
    Segnale live post-gol: miglior intervallo, prob globale (≥1 gol dopo),
    fair odds, edge e trigger con controllo campione.
    """
    empty = {
        "signal": "❌ NO BET",
        "strength": "WAIT",
        "best_interval": "—",
        "best_prob": 0.0,
        "global_prob": 0.0,
        "global_prob_pct": 0.0,
        "edge": 0.0,
        "fair_odds": 0.0,
        "confidence": 0,
        "total": 0,
    }
    if not table:
        return empty

    best_key, best_val = max(table.items(), key=lambda x: x[1]["pct"])
    best_prob = float(best_val["pct"])
    total_matches = int(best_val["total"])

    matches_with_goal = 0
    if filtered_matches is not None and input_minute is not None:
        matches_with_goal = sum(
            1 for _f, _t, all_goals in filtered_matches
            if any(m > input_minute for m, _ in all_goals)
        )

    global_prob = matches_with_goal / total_matches if total_matches > 0 else 0.0
    fair_odds = round(1 / global_prob, 2) if global_prob > 0 else 99.0
    edge = (
        round(float(market_odds) - fair_odds, 2)
        if market_odds is not None else None
    )
    has_edge = edge is None or edge > 0
    confidence = total_matches

    if confidence < 20:
        signal = "⚠️ LOW SAMPLE"
        strength = "LOW"
    elif best_prob >= 70 and has_edge:
        signal = "🔥 STRONG ENTRY"
        strength = "FORTE"
    elif best_prob >= 60 and has_edge:
        signal = "⚡ ENTRY"
        strength = "MEDIA"
    elif best_prob >= 55:
        signal = "👀 MONITOR"
        strength = "MONITOR"
    else:
        signal = "❌ NO BET"
        strength = "WAIT"

    return {
        "signal": signal,
        "strength": strength,
        "best_interval": best_key,
        "best_prob": best_prob,
        "global_prob": round(global_prob, 4),
        "global_prob_pct": round(global_prob * 100, 1),
        "edge": edge,
        "fair_odds": fair_odds,
        "confidence": confidence,
        "total": total_matches,
    }


def build_future_intervals(
    matches_df: pd.DataFrame,
    input_minute: int,
    step: int,
) -> dict:
    """
    Intervalli futuri dal minuto corrente: % partite con ≥1 gol in (start, end].
    Keys es. '55-60', '60-65', …, '90+'.
    """
    intervals = {}
    start = int(input_minute)

    while start < 91:
        end = start + step
        if start >= 90:
            key = "90+"
            end_hi = 999
        else:
            end_hi = min(end, 90)
            key = f"{start}-{end_hi}" if end_hi < 90 or end <= 90 else f"{start}-90"

        total = goal_in_range = 0
        for _, row in matches_df.iterrows():
            home_t = row.get("home_goal_timings", "") or ""
            away_t = row.get("away_goal_timings", "") or ""
            if pd.isna(home_t):
                home_t = ""
            if pd.isna(away_t):
                away_t = ""
            all_goals = get_all_goals(str(home_t), str(away_t))
            future_goals = [g for g in all_goals if g > input_minute]
            total += 1
            if start >= 90:
                if any(g > 90 for g in future_goals):
                    goal_in_range += 1
            elif any(start < g <= end_hi for g in future_goals):
                goal_in_range += 1

        pct = round(goal_in_range / total * 100, 1) if total else 0.0
        intervals[key] = {
            "total": total,
            "goals": goal_in_range,
            "pct": pct,
        }
        if start >= 90:
            break
        start += step

    return intervals


def get_best_interval(table: dict) -> tuple[str, dict]:
    if not table:
        return "—", {"pct": 0.0, "total": 0, "goals": 0}
    return max(table.items(), key=lambda x: x[1]["pct"])


def prob_goal_within_minutes(
    matches_df: pd.DataFrame,
    input_minute: int,
    window_minutes: int,
) -> dict | None:
    """% partite con almeno 1 gol entro N minuti dal minuto attuale."""
    if matches_df is None or matches_df.empty:
        return None
    deadline = input_minute + window_minutes
    total = with_goal = 0
    for _, row in matches_df.iterrows():
        home_t = row.get("home_goal_timings", "") or ""
        away_t = row.get("away_goal_timings", "") or ""
        if pd.isna(home_t):
            home_t = ""
        if pd.isna(away_t):
            away_t = ""
        all_goals = get_all_goals(str(home_t), str(away_t))
        total += 1
        if any(input_minute < g <= deadline for g in all_goals):
            with_goal += 1
    if total == 0:
        return None
    pct = round(with_goal / total * 100, 1)
    return {"pct": pct, "with_goal": with_goal, "total": total, "window": window_minutes}


def live_entry_signal(best_prob: float) -> tuple[str, str]:
    if best_prob > 65:
        return "🔥 ENTRY NOW", "#22c55e"
    if best_prob > 50:
        return "⚡ MONITOR", "#f59e0b"
    return "❌ WAIT", "#ef4444"


def live_odds_trigger(market_odds: float, recommended_odds: float) -> tuple[str, str, str]:
    """Confronto quota book vs consigliata → label, icona, colore."""
    if not market_odds or not recommended_odds or recommended_odds <= 0:
        return "—", "❌", "#64748b"
    if market_odds > recommended_odds:
        return "🔥 VALUE BET", "🔥", "#22c55e"
    if abs(market_odds - recommended_odds) < 0.05:
        return "⚡ QUOTA GIUSTA", "⚡", "#f59e0b"
    return "❌ NO VALUE", "❌", "#ef4444"


def _calc_roi_row(label, wins, losses, avg_odds):
    total = wins + losses
    if total == 0:
        return label, total, avg_odds, wins, losses, 0.0, 0.0
    profit = (wins * (avg_odds - 1.0)) - losses
    profit = round(profit, 1)
    roi_pct = round((profit / total) * 100, 2)
    return label, total, avg_odds, wins, losses, profit, roi_pct


def _calc_lay_row(label, back_wins, back_losses, back_odds):
    lay_wins = back_losses
    lay_losses = back_wins
    total = lay_wins + lay_losses
    if total == 0:
        return label, total, back_odds, lay_wins, lay_losses, 0.0, 0.0
    profit = lay_wins - (lay_losses * (back_odds - 1.0))
    profit = round(profit, 1)
    roi_pct = round((profit / total) * 100, 2)
    return label, total, back_odds, lay_wins, lay_losses, profit, roi_pct


def calc_live_roi_simulation(
    df: pd.DataFrame,
    goal_events: dict,
    current_minute: int,
    home_score: int,
    away_score: int,
    score_index: dict = None,
) -> tuple[dict | None, int]:
    """
    ROI simulazione live su partite simili (stesso score @ minuto).
    Over: gol futuri dopo current_minute. 1X2/BTTS: risultato finale.
    """
    similar_df = get_similar_matches_dataframe(
        df, goal_events, current_minute, home_score, away_score,
        score_index=score_index,
    )
    n = len(similar_df)
    if n == 0:
        return None, 0

    home_wins_n = draw_n = away_wins_n = 0
    over15_n = over25_n = over35_n = over45_n = 0
    btts_y_n = 0

    for _, row in similar_df.iterrows():
        mid_int = int(row["match_id"])
        events = goal_events.get(mid_int, [])
        future = [e for e in events if _parse_minute(e["minute"]) > current_minute]
        n_future = len(future)

        h_ft = float(row.get("home_goals_ft") or 0)
        a_ft = float(row.get("away_goals_ft") or 0)

        if h_ft > a_ft:
            home_wins_n += 1
        elif h_ft == a_ft:
            draw_n += 1
        else:
            away_wins_n += 1

        if n_future >= 2:
            over15_n += 1
        if n_future >= 3:
            over25_n += 1
        if n_future >= 4:
            over35_n += 1
        if n_future >= 5:
            over45_n += 1

        if h_ft >= 1 and a_ft >= 1:
            btts_y_n += 1

    btts_n_n = n - btts_y_n

    def _avg_odds_col(col, fallback):
        if col in similar_df.columns:
            s = pd.to_numeric(similar_df[col], errors="coerce").dropna()
            if len(s) > 0:
                return round(float(s.mean()), 2)
        return fallback

    avg_odds_home = _avg_odds_col("odds_home", 2.00)
    avg_odds_draw = _avg_odds_col("odds_draw", 3.20)
    avg_odds_away = _avg_odds_col("odds_away", 2.95)
    avg_odds_over15 = _avg_odds_col("odds_over15", 1.32)
    avg_odds_over25 = _avg_odds_col("odds_over25", 1.85)
    avg_odds_over35 = _avg_odds_col("odds_over35", 2.55)
    avg_odds_over45 = _avg_odds_col("odds_over45", 4.00)
    avg_odds_btts_y = _avg_odds_col("odds_btts_yes", 1.78)
    avg_odds_btts_n = _avg_odds_col("odds_btts_no", 2.00)

    def _roi_entry(row):
        label, _total, odds, _wins, _losses, profit, roi_pct = row
        return {"name": label, "roi": roi_pct, "profit": profit, "odds": odds}

    def _ou_entry(row):
        label, _total, odds, wins, losses, profit, roi_pct = row
        return {
            "name": label,
            "odds": odds,
            "wins": losses,
            "losses": wins,
            "roi": roi_pct,
            "profit": profit,
        }

    roi_data = {
        "1x2_back": [
            _roi_entry(_calc_roi_row("Back Casa", home_wins_n, n - home_wins_n, avg_odds_home)),
            _roi_entry(_calc_roi_row("Back Pareggio", draw_n, n - draw_n, avg_odds_draw)),
            _roi_entry(_calc_roi_row("Back Trasferta", away_wins_n, n - away_wins_n, avg_odds_away)),
        ],
        "1x2_lay": [
            _roi_entry(_calc_lay_row("Lay Casa", home_wins_n, n - home_wins_n, avg_odds_home)),
            _roi_entry(_calc_lay_row("Lay Pareggio", draw_n, n - draw_n, avg_odds_draw)),
            _roi_entry(_calc_lay_row("Lay Trasferta", away_wins_n, n - away_wins_n, avg_odds_away)),
        ],
        "over_under": [
            _ou_entry(_calc_roi_row("Over 1.5", over15_n, n - over15_n, avg_odds_over15)),
            _ou_entry(_calc_roi_row("Over 2.5", over25_n, n - over25_n, avg_odds_over25)),
            _ou_entry(_calc_roi_row("Over 3.5", over35_n, n - over35_n, avg_odds_over35)),
            _ou_entry(_calc_roi_row("Over 4.5", over45_n, n - over45_n, avg_odds_over45)),
        ],
        "btts": [
            _roi_entry(_calc_roi_row("BTTS Yes", btts_y_n, n - btts_y_n, avg_odds_btts_y)),
            _roi_entry(_calc_roi_row("BTTS No", btts_n_n, n - btts_n_n, avg_odds_btts_n)),
        ],
    }
    return roi_data, n