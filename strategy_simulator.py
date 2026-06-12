"""
strategy_simulator.py — Core engine: bet evaluation, simulation, risk metrics
"""

from __future__ import annotations

import pandas as pd
import numpy as np

from calculations import estimate_lay_00_odds, LAY_00_MIN_ODDS
from advanced_over_strategy import AdvancedOverStrategy
from utils import get_first_goal_detail

# Mercati allineati a prematch ROI / colonne odds del database
STRATEGIES: dict[str, dict] = {
    # ── 1X2 Back ──────────────────────────────────────────────────────────
    "Back Casa": {
        "type": "home_win",
        "mode": "back",
        "odds_column": "odds_home",
    },
    "Back Pareggio": {
        "type": "draw",
        "mode": "back",
        "odds_column": "odds_draw",
    },
    "Back Trasferta": {
        "type": "away_win",
        "mode": "back",
        "odds_column": "odds_away",
    },
    # ── 1X2 Lay ───────────────────────────────────────────────────────────
    "Lay Casa": {
        "type": "not_home_win",
        "mode": "lay",
        "odds_column": "odds_home",
    },
    "Lay Pareggio": {
        "type": "not_draw",
        "mode": "lay",
        "odds_column": "odds_draw",
    },
    "Lay Trasferta": {
        "type": "not_away_win",
        "mode": "lay",
        "odds_column": "odds_away",
    },
    # ── Over ──────────────────────────────────────────────────────────────
    "Over 1.5": {
        "type": "over_15",
        "mode": "back",
        "odds_column": "odds_over15",
    },
    "Over 2.5": {
        "type": "over_25",
        "mode": "back",
        "odds_column": "odds_over25",
    },
    "Over 3.5": {
        "type": "over_35",
        "mode": "back",
        "odds_column": "odds_over35",
    },
    "Over 4.5": {
        "type": "over_45",
        "mode": "back",
        "odds_column": "odds_over45",
    },
    # ── Under (quota derivata dall'over corrispondente) ───────────────────
    "Under 1.5": {
        "type": "under_15",
        "mode": "back",
        "odds_column": "odds_over15",
        "odds_derived": "under",
    },
    "Under 2.5": {
        "type": "under_25",
        "mode": "back",
        "odds_column": "odds_over25",
        "odds_derived": "under",
    },
    "Under 3.5": {
        "type": "under_35",
        "mode": "back",
        "odds_column": "odds_over35",
        "odds_derived": "under",
    },
    # ── BTTS ──────────────────────────────────────────────────────────────
    "BTTS Yes": {
        "type": "btts_yes",
        "mode": "back",
        "odds_column": "odds_btts_yes",
    },
    "BTTS No": {
        "type": "btts_no",
        "mode": "back",
        "odds_column": "odds_btts_no",
    },
    # ── Speciali ──────────────────────────────────────────────────────────
    "Lay 0-0": {
        "type": "not_0_0",
        "mode": "lay",
        "odds_derived": "lay_0_0",
    },
    "Over 0.5 Primo Tempo": {
        "type": "over_05_1h",
        "mode": "back",
        "odds_fixed": 1.4,
    },
    "Over 0.5 Secondo Tempo": {
        "type": "over_05_2h",
        "mode": "back",
        "odds_fixed": 1.3,
    },
    # ── Live / in-play (backtest su storico) ──────────────────────────────
    "Advanced Overs Trading": {
        "type": "advanced_over",
        "mode": "back",
        "odds_column": "odds_over25",
        "engine": "advanced_over",
    },
}

# Alias retrocompatibilità (non inclusi nel selectbox)
STRATEGIES["BTTS"] = STRATEGIES["BTTS Yes"]
STRATEGIES["Lay Draw"] = STRATEGIES["Lay Pareggio"]
STRATEGIES["Over 0.5 2T"] = STRATEGIES["Over 0.5 Secondo Tempo"]

LIVE_STRATEGY_NAMES = (
    "Advanced Overs Trading",
)

STRATEGY_NAMES = (
    *LIVE_STRATEGY_NAMES,
    "Back Casa",
    "Back Pareggio",
    "Back Trasferta",
    "Lay Casa",
    "Lay Pareggio",
    "Lay Trasferta",
    "Over 1.5",
    "Over 2.5",
    "Over 3.5",
    "Over 4.5",
    "Under 1.5",
    "Under 2.5",
    "Under 3.5",
    "BTTS Yes",
    "BTTS No",
    "Lay 0-0",
    "Over 0.5 Primo Tempo",
    "Over 0.5 Secondo Tempo",
)


def get_strategy_config(strategy_name: str) -> dict | None:
    cfg = STRATEGIES.get(strategy_name)
    return dict(cfg) if cfg else None


def _safe_float(val) -> float | None:
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return None
    try:
        f = float(val)
        return None if np.isnan(f) else f
    except (TypeError, ValueError):
        return None


def _derive_under_odds(over_odds: float | None) -> float | None:
    if over_odds is None or over_odds <= 1:
        return None
    p_under = 1.0 - (1.0 / over_odds)
    if p_under <= 0:
        return None
    return 1.0 / p_under


def _resolve_odds(row, strategy_config: dict) -> float | None:
    fixed = strategy_config.get("odds_fixed")
    if fixed is not None:
        odds = _safe_float(fixed)
        return odds if odds is not None and odds > 1 else None

    derived = strategy_config.get("odds_derived")
    if derived == "lay_0_0":
        odds = _safe_float(strategy_config.get("_lay_00_odds"))
        return odds if odds is not None and odds > 1 else None

    col = strategy_config.get("odds_column")
    if not col:
        return None
    odds = _safe_float(row.get(col))
    if odds is None or odds <= 1:
        return None
    if derived == "under":
        return _derive_under_odds(odds)
    return odds


def _match_settled(row) -> bool:
    home = _safe_float(row.get("home_goals_ft"))
    away = _safe_float(row.get("away_goals_ft"))
    return home is not None and away is not None


def _match_stats(row) -> dict:
    home = _safe_float(row.get("home_goals_ft")) or 0.0
    away = _safe_float(row.get("away_goals_ft")) or 0.0
    total = _safe_float(row.get("total_goals_ft"))
    if total is None:
        total = home + away
    goals_2h = _safe_float(row.get("total_goals_2h"))
    if goals_2h is None:
        goals_2h = 0.0
    goals_1h = _safe_float(row.get("total_goals_ht"))
    if goals_1h is None:
        home_ht = _safe_float(row.get("home_goals_ht"))
        away_ht = _safe_float(row.get("away_goals_ht"))
        if home_ht is not None and away_ht is not None:
            goals_1h = home_ht + away_ht
        else:
            goals_1h = None
    return {
        "home": home,
        "away": away,
        "total": total,
        "goals_1h": goals_1h,
        "goals_2h": goals_2h,
        "is_draw": home == away,
        "home_win": home > away,
        "away_win": home < away,
        "is_0_0": total == 0,
    }


def _strategy_wins(row, strategy_config: dict) -> bool:
    stype = strategy_config.get("type")
    s = _match_stats(row)

    if stype == "home_win":
        return s["home_win"]
    if stype == "draw":
        return s["is_draw"]
    if stype == "away_win":
        return s["away_win"]
    if stype == "not_home_win":
        return not s["home_win"]
    if stype == "not_draw":
        return not s["is_draw"]
    if stype == "not_away_win":
        return not s["away_win"]
    if stype == "over_15":
        return s["total"] >= 2
    if stype == "over_25":
        return s["total"] >= 3
    if stype == "over_35":
        return s["total"] >= 4
    if stype == "over_45":
        return s["total"] >= 5
    if stype == "under_15":
        return s["total"] < 2
    if stype == "under_25":
        return s["total"] < 3
    if stype == "under_35":
        return s["total"] < 4
    if stype == "btts_yes":
        return s["home"] > 0 and s["away"] > 0
    if stype == "btts_no":
        return not (s["home"] > 0 and s["away"] > 0)
    if stype == "not_0_0":
        return not s["is_0_0"]
    if stype == "over_05_1h":
        return s["goals_1h"] is not None and s["goals_1h"] >= 1
    if stype == "over_05_2h":
        return s["goals_2h"] >= 1
    return False


def _first_goal_minute_row(row) -> int | None:
    home_t = str(row.get("home_goal_timings") or "")
    away_t = str(row.get("away_goal_timings") or "")
    first, _, _ = get_first_goal_detail(home_t, away_t)
    return first


def _goals_at_ht(row) -> float | None:
    ht_total = _safe_float(row.get("total_goals_ht"))
    if ht_total is not None:
        return ht_total
    _, _, all_goals = get_first_goal_detail(
        str(row.get("home_goal_timings") or ""),
        str(row.get("away_goal_timings") or ""),
    )
    if not all_goals:
        return None
    return float(sum(1 for g in all_goals if g <= 45))


def _shots_on_target_2h_proxy(row) -> int:
    home_sot = _safe_float(row.get("home_shots_on_target")) or 0.0
    away_sot = _safe_float(row.get("away_shots_on_target")) or 0.0
    return int(round((home_sot + away_sot) * 0.55))


def _attack_rating_proxy(row) -> float:
    shots = _shots_on_target_2h_proxy(row)
    return round(min(1.0, shots / 8.0), 2)


def _check_advanced_over_entry(row) -> bool:
    if not _match_settled(row):
        return False
    first_goal = _first_goal_minute_row(row)
    if first_goal is None or first_goal > 45:
        return False
    if _goals_at_ht(row) != 1:
        return False
    odds_base = _safe_float(row.get("odds_over25"))
    return odds_base is not None and odds_base > 1


def _advanced_over_bet_result(
    row,
    over_strategy: AdvancedOverStrategy,
    unit_stake: float,
) -> tuple[float, dict]:
    """Backtest split staking con proxy quote live e timing gol."""
    odds_base = float(_safe_float(row.get("odds_over25")) or 0)
    current_odds = max(odds_base * 1.45, 2.6)

    orders = over_strategy.generate_orders(odds_base)
    orders = over_strategy.update_matched_orders(orders, current_odds)

    for level, col in ((3.5, "odds_over35"), (4.5, "odds_over45")):
        col_odds = _safe_float(row.get(col))
        if col_odds and col_odds >= level:
            for order in orders:
                if order["odds"] == level:
                    order["matched"] = True

    _, _, all_goals = get_first_goal_detail(
        str(row.get("home_goal_timings") or ""),
        str(row.get("away_goal_timings") or ""),
    )
    goals_2h = [g for g in all_goals if g > 45]

    mgmt_action = None
    for _ in goals_2h:
        mgmt = over_strategy.handle_goal(orders)
        if mgmt:
            mgmt_action = mgmt.get("action")

    matched = [o for o in orders if o["matched"]]
    if not matched:
        return 0.0, {}

    total_ft = _match_stats(row)["total"]
    stake_unit = float(unit_stake) * float(over_strategy.config["total_stake"])
    pnl = 0.0

    for order in matched:
        part = float(order["stake"]) * stake_unit
        if total_ft >= 3:
            pnl += part * (float(order["odds"]) - 1)
        else:
            pnl -= part

    if mgmt_action == "CASHOUT_PARTIAL" and pnl > 0:
        pnl *= 0.65
    elif mgmt_action == "FULL_CASHOUT" and pnl > 0:
        pnl *= 0.85

    shots_proxy = _shots_on_target_2h_proxy(row)
    rating_proxy = _attack_rating_proxy(row)
    loss_ratio = pnl / unit_stake if unit_stake else 0.0

    if total_ft < 3 and loss_ratio <= over_strategy.config["loss_cut"]:
        extra = over_strategy.check_extra_entry({
            "shots_on_target_2T": shots_proxy,
            "minute": 70,
            "attack_rating": rating_proxy,
        })
        if extra:
            over35_odds = _safe_float(row.get("odds_over35")) or 3.5
            extra_stake = unit_stake * float(extra.get("stake", 1.0)) * 0.5
            if total_ft >= 4:
                pnl += extra_stake * (over35_odds - 1)
            else:
                pnl -= extra_stake

        final = over_strategy.final_exit({
            "minute": 85,
            "shots_on_target_2T": shots_proxy,
            "attack_rating": rating_proxy,
        })
        if final and total_ft < 3:
            pnl = max(pnl, unit_stake * float(final["loss"]))

    meta = {
        "matched_orders": len(matched),
        "mgmt_action": mgmt_action or "—",
        "current_odds_proxy": round(current_odds, 2),
        "goals_2h": len(goals_2h),
        "shots_2h_proxy": shots_proxy,
        "attack_rating": rating_proxy,
    }
    return round(pnl, 2), meta


def _match_has_ht_data(row) -> bool:
    if _safe_float(row.get("total_goals_ht")) is not None:
        return True
    home_ht = _safe_float(row.get("home_goals_ht"))
    away_ht = _safe_float(row.get("away_goals_ht"))
    return home_ht is not None and away_ht is not None


def evaluate_strategy(row, strategy_config: dict) -> bool:
    """Decide se entrare nella bet (quote disponibili e partita conclusa)."""
    if not strategy_config or not _match_settled(row):
        return False
    if strategy_config.get("engine") == "advanced_over":
        return False
    if strategy_config.get("type") == "over_05_1h" and not _match_has_ht_data(row):
        return False
    return _resolve_odds(row, strategy_config) is not None


def calculate_bet_result(row, strategy_config: dict, stake: float) -> float:
    odds = _resolve_odds(row, strategy_config)
    if odds is None or odds <= 1:
        return 0.0

    win = _strategy_wins(row, strategy_config)
    stake = float(stake)
    mode = strategy_config.get("mode", "back")
    if mode == "back":
        return stake * (odds - 1) if win else -stake
    if mode == "lay":
        liability = stake * (odds - 1)
        return stake if win else -liability
    return 0.0


def _compound_stake(bankroll: float, bankroll_start: float, stake: float) -> float:
    """Stake proporzionale al bankroll corrente (interesse composto)."""
    if bankroll <= 0 or bankroll_start <= 0 or stake <= 0:
        return 0.0
    stake_ratio = min(float(stake) / float(bankroll_start), 1.0)
    return round(bankroll * stake_ratio, 2)


def _lay_affordable(row, strategy_config: dict, stake: float, bankroll: float) -> bool:
    if strategy_config.get("mode") != "lay":
        return stake > 0 and stake <= bankroll
    odds = _resolve_odds(row, strategy_config)
    if odds is None or odds <= 1:
        return False
    liability = stake * (odds - 1)
    return stake > 0 and liability <= bankroll


def run_simulation(
    df: pd.DataFrame,
    strategy_config: dict,
    stake: float = 10,
    bankroll_start: float = 1000,
) -> dict:
    bankroll = float(bankroll_start)
    history = [bankroll]
    results: list[float] = []
    bet_details: list[dict] = []
    wins = losses = skipped = 0
    total_staked = 0.0
    stake_ratio = min(float(stake) / float(bankroll_start), 1.0) if bankroll_start > 0 else 0.0

    cfg = dict(strategy_config) if strategy_config else {}
    if cfg.get("odds_derived") == "lay_0_0":
        cfg["_lay_00_odds"] = estimate_lay_00_odds(df)

    is_advanced_over = cfg.get("engine") == "advanced_over"
    over_strategy = AdvancedOverStrategy() if is_advanced_over else None

    if df is None or df.empty or not strategy_config:
        return {
            "profit": 0.0,
            "roi": 0.0,
            "wins": 0,
            "losses": 0,
            "strike_rate": 0.0,
            "history": history,
            "results": results,
            "bet_details": bet_details,
            "total_bets": 0,
            "bankroll_end": bankroll,
            "total_staked": 0.0,
            "stake_ratio_pct": round(stake_ratio * 100, 2),
            "compound": True,
        }

    for _, row in df.iterrows():
        entry_info = None
        over_meta = None
        size_mult = 1.0

        if is_advanced_over:
            if not _check_advanced_over_entry(row):
                continue
        elif not evaluate_strategy(row, cfg):
            continue

        current_stake = round(
            _compound_stake(bankroll, bankroll_start, stake) * size_mult, 2,
        )
        if current_stake <= 0 or not _lay_affordable(row, cfg, current_stake, bankroll):
            skipped += 1
            continue

        odds_used = _resolve_odds(row, cfg)
        if is_advanced_over and over_strategy:
            result, over_meta = _advanced_over_bet_result(row, over_strategy, current_stake)
            if result == 0.0 and not over_meta:
                continue
        else:
            result = calculate_bet_result(row, cfg, current_stake)

        bankroll += result
        bankroll = max(bankroll, 0.0)
        history.append(bankroll)
        results.append(result)
        total_staked += current_stake
        bet_row = row.to_dict()
        bet_row["_row_index"] = row.name
        bet_row["stake"] = current_stake
        bet_row["result"] = result
        bet_row["bankroll"] = round(bankroll, 2)
        if odds_used is not None:
            bet_row["odds_used"] = odds_used
        if entry_info:
            bet_row["first_goal_minute"] = entry_info.get("first_goal_minute")
            bet_row["edge"] = entry_info.get("edge")
            bet_row["fair_odds"] = entry_info.get("fair_odds")
            bet_row["prob_under25"] = entry_info.get("prob_under25")
            bet_row["stake_multiplier"] = size_mult
            bet_row["confidence"] = "ALTA" if entry_info.get("edge", 0) > 0.05 else "MEDIA"
        if over_meta:
            bet_row.update(over_meta)
        bet_details.append(bet_row)

        if result > 0:
            wins += 1
        elif result < 0:
            losses += 1

    total_bets = len(results)
    profit = round(bankroll - bankroll_start, 2)
    roi = round((bankroll / bankroll_start - 1) * 100, 2) if bankroll_start else 0.0

    return {
        "profit": profit,
        "roi": roi,
        "wins": wins,
        "losses": losses,
        "strike_rate": round(wins / total_bets * 100, 1) if total_bets else 0.0,
        "history": history,
        "results": results,
        "bet_details": bet_details,
        "total_bets": total_bets,
        "bankroll_end": round(bankroll, 2),
        "total_staked": round(total_staked, 2),
        "stake_ratio_pct": round(stake_ratio * 100, 2),
        "skipped_bets": skipped,
        "compound": True,
        "lay_00_odds": cfg.get("_lay_00_odds"),
    }


def calculate_drawdown(history: list[float]) -> float:
    if not history:
        return 0.0
    peak = history[0]
    max_dd = 0.0
    for value in history:
        if value > peak:
            peak = value
        dd = peak - value
        if dd > max_dd:
            max_dd = dd
    return round(max_dd, 2)


def average_odds_from_sim(sim: dict) -> float | None:
    """Quota media effettiva usata nelle bet simulate."""
    details = sim.get("bet_details") or []
    odds = [
        float(d["odds_used"])
        for d in details
        if d.get("odds_used") is not None and float(d["odds_used"]) > 1
    ]
    if odds:
        return round(float(np.mean(odds)), 2)
    lay = sim.get("lay_00_odds")
    if lay is not None and float(lay) > 1:
        return round(float(lay), 2)
    return None


def calculate_losing_streak(results: list[float]) -> int:
    max_streak = 0
    current = 0
    for r in results:
        if r < 0:
            current += 1
            max_streak = max(max_streak, current)
        else:
            current = 0
    return max_streak


def calculate_risk_metrics(
    sim: dict,
    bankroll_start: float,
    stake: float,
) -> dict:
    """Metriche avanzate per il Risk Panel."""
    history = sim.get("history") or []
    results = sim.get("results") or []
    wins = int(sim.get("wins") or 0)
    losses = int(sim.get("losses") or 0)

    max_dd = calculate_drawdown(history)
    drawdown_pct = round(max_dd / bankroll_start * 100, 1) if bankroll_start else 0.0
    if drawdown_pct > 50:
        dd_risk = "ALTO"
    elif drawdown_pct > 30:
        dd_risk = "MEDIO"
    else:
        dd_risk = "BASSO"

    losing_streak = calculate_losing_streak(results)
    loss_impact = round(losing_streak * stake, 2)

    settled = wins + losses
    strike_rate = round(wins / settled * 100, 1) if settled else 0.0

    win_results = [r for r in results if r > 0]
    loss_results = [r for r in results if r < 0]
    avg_win = sum(win_results) / wins if wins else 0.0
    avg_loss = abs(sum(loss_results)) / losses if losses else 0.0
    ev = round(
        (strike_rate / 100 * avg_win) - ((1 - strike_rate / 100) * avg_loss),
        2,
    )

    risk_score_raw = 100 - (
        drawdown_pct * 0.5
        + losing_streak * 2
        + (100 - strike_rate) * 0.3
    )
    risk_score = int(round(max(0.0, min(100.0, risk_score_raw))))
    if risk_score >= 70:
        score_label = "Basso"
    elif risk_score >= 40:
        score_label = "Moderato"
    else:
        score_label = "Alto"

    volatility = float(np.std(results)) if len(results) > 1 else 0.0
    vol_ratio = volatility / stake if stake > 0 else volatility
    if vol_ratio < 1.0:
        stability = "Alta"
    elif vol_ratio < 2.5:
        stability = "Media"
    else:
        stability = "Bassa"

    return {
        "max_drawdown": max_dd,
        "drawdown_pct": drawdown_pct,
        "dd_risk_level": dd_risk,
        "losing_streak": losing_streak,
        "loss_impact": loss_impact,
        "strike_rate": strike_rate,
        "wins": wins,
        "losses": losses,
        "expected_value": ev,
        "ev_profitable": ev > 0,
        "risk_score": risk_score,
        "risk_score_label": score_label,
        "stability": stability,
        "volatility": round(volatility, 2),
    }


def find_best_strategy(
    df: pd.DataFrame,
    stake: float = 10,
    bankroll_start: float = 1000,
) -> pd.DataFrame:
    rows = []
    for name in STRATEGY_NAMES:
        cfg = get_strategy_config(name)
        if not cfg:
            continue
        sim = run_simulation(df, cfg, stake=stake, bankroll_start=bankroll_start)
        rows.append({
            "strategy": name,
            "avg_odds": average_odds_from_sim(sim),
            "roi": sim["roi"],
            "profit": sim["profit"],
            "total_bets": sim["total_bets"],
            "strike_rate": sim["strike_rate"],
            "max_drawdown": calculate_drawdown(sim["history"]),
            "losing_streak": calculate_losing_streak(sim["results"]),
        })
    if not rows:
        return pd.DataFrame(columns=["strategy", "avg_odds", "roi", "profit", "total_bets"])
    return pd.DataFrame(rows).sort_values("roi", ascending=False).reset_index(drop=True)
