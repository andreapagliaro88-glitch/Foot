"""
Critical test — goal timing merge + first goal logic.
Run: python tests/test_goal_timings.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from utils import get_all_goals, get_first_goal, get_first_goal_with_team, get_first_and_after

HOME = "41,54,60"
AWAY = "32,50,59"

all_goals = get_all_goals(HOME, AWAY)
print(all_goals)
assert all_goals == [32, 41, 50, 54, 59, 60], f"expected [32,41,50,54,59,60], got {all_goals}"

first = get_first_goal(HOME, AWAY)
print(first)
assert first == 32, f"expected 32, got {first}"

first_team = get_first_goal_with_team(HOME, AWAY)
print(first_team)
assert first_team == (32, "away"), f"expected (32, 'away'), got {first_team}"

# Bonus: stoppage time + empty columns
assert get_first_goal("41,45+2", "") == 41
assert get_first_goal_with_team("41,45+2", "") == (41, "home")
assert get_all_goals("", "") == []

first, after = get_first_and_after("41,54,60", "32,50,59")
assert first == 32 and after == [41, 50, 54, 59, 60], (first, after)

print("OK — tutti i test superati")
