"""
Test fasce 45+ / 90+ — solo recupero, non minuti regolamentari del 2T.
Run: python tests/test_interval_stoppage.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from utils import parse_goal_minute_value, get_half
from calculations import calculate_interval_distribution_1h, calculate_interval_distribution_2h

# CSV token parsing
assert parse_goal_minute_value("45'3") == 48
assert parse_goal_minute_value("90'2") == 92
assert parse_goal_minute_value("45+2") == 47
assert get_half(48, "45'3") == 1
assert get_half(92, "90'2") == 2
assert get_half(47, "45+2") == 1

# Simula goal_events come dal DB (minute parsato + half)
match_id = 1
goal_events = {
    match_id: [
        {"minute": 20, "half": 1, "is_home": 1},   # 0-15 no, 16-30 sì
        {"minute": 45, "half": 1, "is_home": 1},   # 31-45
        {"minute": 47, "half": 1, "is_home": 0},   # 45'2 → 45+
        {"minute": 50, "half": 2, "is_home": 1},  # 46-60 (2T regolare)
        {"minute": 90, "half": 2, "is_home": 0},  # 76-90
        {"minute": 92, "half": 2, "is_home": 1},  # 90'2 → 90+
    ],
}

dist_1h = calculate_interval_distribution_1h(goal_events, [match_id])
dist_2h = calculate_interval_distribution_2h(goal_events, [match_id])

# 1T: un gol in 16-30, uno in 31-45, uno in 45+ (il 47' half=1)
assert dist_1h["16-30"]["1_gol"] == 100.0
assert dist_1h["31-45"]["1_gol"] == 100.0
assert dist_1h["45+"]["1_gol"] == 100.0
assert dist_1h["0-15"]["0_gol"] == 100.0

# 2T: gol al 50' NON deve finire in 45+ del 1T (già verificato sopra)
assert dist_2h["46-60"]["1_gol"] == 100.0
assert dist_2h["76-90"]["1_gol"] == 100.0
assert dist_2h["90+"]["1_gol"] == 100.0

print("OK — fasce 45+/90+ e parsing recupero corretti")
