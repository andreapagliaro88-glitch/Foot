"""Tests for calc_live_goal_probability — trader logic."""

import pandas as pd

from calculations import (
    calc_live_goal_probability,
    filter_matches_by_goal_criteria,
    build_future_intervals,
    get_best_interval,
    prob_goal_within_minutes,
)


def _row(home_goals, away_goals):
    return {
        "match_id": 1,
        "home_goal_timings": home_goals,
        "away_goal_timings": away_goals,
    }


def test_calc_live_goal_probability_basic():
    df = pd.DataFrame([
        _row("10,70", ""),      # gol al 70 dopo min 55
        _row("20", ""),         # solo gol al 20
        _row("60,80", "58"),    # gol 58 e 60+ dopo 55
    ])
    result = calc_live_goal_probability(df, 55, edge=0.05, min_goals_after=1)
    assert result is not None
    assert result["total"] == 3
    assert result["with_goal"] == 2
    assert result["prob"] == round(2 / 3 * 100, 1)
    assert result["fair_odds"] == round(1 / (2 / 3), 2)
    assert result["recommended_odds"] == round(1 / ((2 / 3) * 0.95), 2)


def test_filter_matches_by_goal_criteria():
    df = pd.DataFrame([
        {**_row("32,60", "39"), "match_id": 1},
        {**_row("10,50", ""), "match_id": 2},
    ])
    criteria = [(32, "home")]
    filtered, _ = filter_matches_by_goal_criteria(df, criteria, tolerance=2)
    assert len(filtered) == 1
    assert int(filtered.iloc[0]["match_id"]) == 1


def test_build_future_intervals_and_best():
    df = pd.DataFrame([
        _row("10,62", ""),   # gol 62 dopo 55
        _row("20,58", ""),   # gol 58 dopo 55
        _row("30", ""),      # nessun gol dopo 55
    ])
    t10 = build_future_intervals(df, 55, 10)
    assert "50-60" in t10
    best_key, best_val = get_best_interval(t10)
    assert best_val["pct"] > 0

    t5 = build_future_intervals(df, 27, 5)
    assert "25-30" in t5
    t10_27 = build_future_intervals(df, 27, 10)
    assert "20-30" in t10_27
    t15_27 = build_future_intervals(df, 27, 15)
    assert "16-30" in t15_27
    assert "45+" in t5
    assert "45+" in t10_27
    assert "45+" in t15_27
    assert "90+" in t5
    assert "90+" in t10
    assert "90+" in t15_27

    cum = prob_goal_within_minutes(df, 55, 10)
    assert cum["with_goal"] == 2
    assert cum["total"] == 3


def test_stoppage_goals_in_45_90_plus_buckets():
    df = pd.DataFrame([
        _row("10,45'2,70", ""),
        _row("20", "90'3"),
        _row("30", ""),
    ])
    t5 = build_future_intervals(df, 27, 5)
    t10 = build_future_intervals(df, 27, 10)
    t15 = build_future_intervals(df, 27, 15)

    assert t5["45+"]["goals"] == 1
    assert t5["90+"]["goals"] == 1
    assert t10["45+"]["goals"] == 1
    assert t10["90+"]["goals"] == 1
    assert t15["45+"]["goals"] == 1
    assert t15["90+"]["goals"] == 1

    # 45'2 (47') non deve finire in fascia regolare 45-50
    assert t5.get("45-50", {}).get("goals", 0) == 0


def test_post_goal_uses_goal_minute_not_live_minute():
    from calculations import calc_post_goal_future_analysis

    df = pd.DataFrame([
        {**_row("27,70", ""), "match_id": 1},
        {**_row("28,80", ""), "match_id": 2},
        {**_row("10,50", ""), "match_id": 3},
    ])
    analysis = calc_post_goal_future_analysis(df, reference_minute=27, input_minute=67)
    assert analysis["reference_minute"] == 27
    assert analysis["tables"]["total"]["count"] == 2
    table = analysis["tables"]["total"]["table"]
    assert "16-30" in table
    assert "61-75" in table
