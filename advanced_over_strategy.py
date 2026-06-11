"""
advanced_over_strategy.py — Advanced Overs Trading (split staking Over 2.5 in-play)
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

STRATEGY_NAME = "Advanced Overs Trading"

DEFAULT_CONFIG = {
    "total_stake": 1.0,
    "split_levels": [2.5, 3.5, 4.5, 5.5],
    "loss_cut": -0.6,
    "min_shots_2T": 4,
}


class AdvancedOverStrategy:
    """Split staking su Over 2.5 con gestione post-gol e fase 3."""

    def __init__(self, config: dict | None = None):
        self.config = {**DEFAULT_CONFIG, **(config or {})}

    def generate_orders(self, base_odds: float) -> list[dict]:
        stake_per_split = self.config["total_stake"] / len(self.config["split_levels"])
        return [
            {
                "type": "BACK",
                "market": "OVER_2.5",
                "odds": float(level),
                "stake": stake_per_split,
                "matched": False,
            }
            for level in self.config["split_levels"]
        ]

    def update_matched_orders(self, orders: list[dict], current_odds: float) -> list[dict]:
        updated = deepcopy(orders)
        for order in updated:
            if not order["matched"] and float(current_odds) >= float(order["odds"]):
                order["matched"] = True
        return updated

    def handle_goal(self, orders: list[dict]) -> dict | None:
        matched = [o for o in orders if o["matched"]]
        count = len(matched)

        if count == 1:
            return {"action": "REMOVE_RISK", "msg": "Cancella ordini restanti"}
        if count == 2:
            return {"action": "CASHOUT_PARTIAL", "msg": "Free bet"}
        if count >= 3:
            return {"action": "FULL_CASHOUT", "msg": "Equalizza profit"}
        return None

    def check_loss(self, current_pnl: float) -> dict | None:
        if current_pnl <= self.config["loss_cut"]:
            return {"action": "GO_TO_PHASE_3", "msg": "Loss 60% raggiunta"}
        return None

    def check_extra_entry(self, data: dict) -> dict | None:
        shots_2t = int(data.get("shots_on_target_2T") or 0)
        minute = int(data.get("minute") or 0)
        rating = float(data.get("attack_rating") or 0)

        if minute >= 60 and shots_2t >= self.config["min_shots_2T"] and rating >= 0.7:
            return {
                "action": "ENTER_OVER_NEXT",
                "market": "OVER_3.5",
                "stake": 1.0,
                "reason": "Match acceso",
            }
        return None

    def final_exit(self, data: dict) -> dict | None:
        minute = int(data.get("minute") or 0)
        shots_2t = int(data.get("shots_on_target_2T") or 0)
        rating = float(data.get("attack_rating") or 0)

        if minute >= 80 and (shots_2t < self.config["min_shots_2T"] or rating < 0.5):
            return {
                "action": "EXIT_LOSS",
                "loss": self.config["loss_cut"],
                "msg": "Partita spenta",
            }
        return None

    def evaluate(self, state: dict, data: dict) -> dict:
        phase = state.get("phase", "WAIT")

        if phase == "WAIT":
            orders = self.generate_orders(float(data["odds_over25"]))
            return {
                "phase": "ENTERED",
                "orders": orders,
                "action": "ENTER",
                "msg": "Split staking attivo",
            }

        if phase == "ENTERED":
            orders = self.update_matched_orders(state.get("orders", []), float(data["current_odds"]))

            if data.get("goal"):
                goal_action = self.handle_goal(orders)
                if goal_action:
                    goal_action["phase"] = "ENTERED"
                    goal_action["orders"] = orders
                    return goal_action

            loss_check = self.check_loss(float(data.get("pnl") or 0))
            if loss_check:
                loss_check["phase"] = "PHASE_3"
                loss_check["orders"] = orders
                return loss_check

            return {"phase": "ENTERED", "orders": orders, "action": "HOLD"}

        if phase == "PHASE_3":
            extra = self.check_extra_entry(data)
            if extra:
                extra["phase"] = "PHASE_3"
                return extra

            exit_final = self.final_exit(data)
            if exit_final:
                exit_final["phase"] = "PHASE_3"
                return exit_final

        return {"action": "HOLD", "phase": phase}


def build_live_data(
    *,
    odds_over25: float,
    current_odds: float,
    pnl: float = 0.0,
    goal: bool = False,
    minute: int,
    shots_on_target_2t: int = 0,
    attack_rating: float = 0.5,
) -> dict:
    return {
        "odds_over25": odds_over25,
        "current_odds": current_odds,
        "pnl": pnl,
        "goal": goal,
        "minute": minute,
        "shots_on_target_2T": shots_on_target_2t,
        "attack_rating": attack_rating,
    }


def build_live_state(*, phase: str = "WAIT", orders: list[dict] | None = None) -> dict:
    state: dict[str, Any] = {"phase": phase}
    if orders is not None:
        state["orders"] = orders
    return state
