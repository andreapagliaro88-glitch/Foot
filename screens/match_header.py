import streamlit as st
import pandas as pd

from strategy_simulator import find_best_strategy


def calculate_edges(probabilities, odds):
    edges = {}
    for key in probabilities:
        prob = probabilities[key]
        odd = odds.get(key)
        if odd and prob and odd > 1:
            edges[key] = (prob * odd) - 1

    if not edges:
        return None

    edge_max = max(edges.values())
    edge_min = min(edges.values())
    edge_avg = sum(edges.values()) / len(edges)
    return {
        "edges": edges,
        "edge_max": edge_max,
        "edge_min": edge_min,
        "edge_avg": edge_avg,
        "edge_spread": edge_max - edge_min,
        "best_market": max(edges, key=edges.get),
        "worst_market": min(edges, key=edges.get),
    }


def _avg_odd(filtered, col, fallback):
    s = pd.to_numeric(filtered.get(col, pd.Series(dtype=float)), errors="coerce").dropna()
    return float(s.mean()) if len(s) > 0 else fallback


def _extract_all_goal_minutes(goal_events, match_ids, parse_minute) -> list[int]:
    minutes: list[int] = []
    for mid in match_ids:
        for e in goal_events.get(int(mid), []):
            m = parse_minute(e["minute"])
            if m is not None and m >= 0:
                minutes.append(int(m))
    return minutes


_GOAL_TIMING_INTERVALS = (
    ("0-30", lambda m: m <= 30, "#3b82f6"),
    ("31-60", lambda m: 31 <= m <= 60, "#38bdf8"),
    ("61-90", lambda m: m >= 61, "#f97316"),
)


def _compute_tempo_gol(all_minutes: list[int]) -> dict:
    if not all_minutes:
        return {
            "timing_label": "N/D",
            "timing_color": "#94a3b8",
            "timing_pct": 0.0,
        }

    n = len(all_minutes)
    best_label, best_count, best_color = "N/D", 0, "#94a3b8"
    for label, pred, color in _GOAL_TIMING_INTERVALS:
        count = sum(1 for m in all_minutes if pred(m))
        if count > best_count:
            best_label, best_count, best_color = label, count, color

    timing_pct = round(best_count / n * 100, 1)
    return {
        "timing_label": best_label,
        "timing_color": best_color,
        "timing_pct": timing_pct,
    }


def _compute_goal_range(filtered: pd.DataFrame) -> tuple[str, str, float]:
    ranges = {"0-1": 0, "2-3": 0, "4+": 0}
    tg = pd.to_numeric(
        filtered.get("total_goals_ft", pd.Series(dtype=float)),
        errors="coerce",
    ).dropna()
    for g in tg:
        gi = int(g)
        if gi <= 1:
            ranges["0-1"] += 1
        elif gi <= 3:
            ranges["2-3"] += 1
        else:
            ranges["4+"] += 1
    n = sum(ranges.values())
    if n == 0:
        return "2-3", "2 – 3 GOL", 0.0
    best_range = max(ranges, key=ranges.get)
    pct_range = round(ranges[best_range] / n * 100, 1)
    labels = {"0-1": "0 – 1 GOL", "2-3": "2 – 3 GOL", "4+": "4+ GOL"}
    return best_range, labels[best_range], pct_range


def _compute_edge_over25(filtered: pd.DataFrame, over25_pct: float) -> tuple[float, str]:
    prob = over25_pct / 100
    if prob <= 0:
        return 0.0, "NEUTRO"
    avg_odds = _avg_odd(filtered, "odds_over25", 0.0)
    if avg_odds <= 1:
        return 0.0, "NEUTRO"
    fair_odds = 1 / prob
    edge = (avg_odds - fair_odds) / fair_odds * 100
    if edge > 5:
        edge_label = "VALUE"
    elif edge < -5:
        edge_label = "NO VALUE"
    else:
        edge_label = "NEUTRO"
    return round(edge, 1), edge_label


def _early30_pct(goal_events, match_ids, parse_minute):
    """% gol entro 30' su tutti i gol (non solo primo gol partita)."""
    all_minutes = _extract_all_goal_minutes(goal_events, match_ids, parse_minute)
    if not all_minutes:
        return 0.0
    return round(sum(1 for g in all_minutes if g <= 30) / len(all_minutes) * 100, 1)


def _key_moment(goal_events, match_ids, parse_minute):
    buckets = {"0-15": 0, "16-30": 0, "31-45": 0, "46-60": 0, "61-75": 0, "76-90": 0}
    for mid in match_ids:
        for e in goal_events.get(int(mid), []):
            m = parse_minute(e["minute"])
            if m <= 15:
                buckets["0-15"] += 1
            elif m <= 30:
                buckets["16-30"] += 1
            elif m <= 45:
                buckets["31-45"] += 1
            elif m <= 60:
                buckets["46-60"] += 1
            elif m <= 75:
                buckets["61-75"] += 1
            else:
                buckets["76-90"] += 1
    if not any(buckets.values()):
        return "N/D", "N/D", 0.0
    best = max(buckets, key=buckets.get)
    total = sum(buckets.values())
    pct = round(buckets[best] / total * 100, 1)
    label = best.replace("-", "' – ") + "'"
    return best, label, pct


def _edge_confidence(edge_val):
    return min(10, max(1, round(abs(edge_val) * 35 + 3)))


def _match_quality(spread):
    if spread > 0.30:
        return "🔥 FORTE", "#22c55e"
    if spread > 0.15:
        return "⚖️ MEDIO", "#3b82f6"
    return "❌ CONFUSO", "#ef4444"


def _eq_label(hw_pct, aw_pct, eq_score):
    if eq_score >= 70:
        return "⚖️ MOLTO EQUILIBRATO"
    if eq_score >= 50:
        return "⚖️ EQUILIBRATO"
    return "📉 SBILANCIATO"


def _eq_subtext(hw_pct, aw_pct, eq_score):
    if eq_score >= 50:
        delta = hw_pct - aw_pct
        if abs(delta) <= 5:
            return "Match equilibrato"
        fav = "CASA" if delta > 0 else "TRASFERTA"
        return f"Match equilibrato, leggero vantaggio {fav}"
    return "Squilibrio evidente tra le squadre"


def _reliability(n):
    if n >= 200:
        return "ALTA", "#22c55e"
    if n >= 80:
        return "MEDIA", "#f59e0b"
    return "BASSA", "#ef4444"


def _reliability_bar_pct(label: str) -> float:
    return {"ALTA": 100.0, "MEDIA": 60.0, "BASSA": 30.0}.get(label, 0.0)


def _strategy_confidence(affidabilita: str) -> str:
    return "ALTA" if affidabilita == "ALTA" else "MEDIA"


def _conf_from_bets(affidabilita: str, bets: int) -> str:
    if affidabilita == "ALTA" and bets >= 20:
        return "ALTA"
    if bets >= 10:
        return "MEDIA"
    return "BASSA"


def _strategy_rank_icon(rank: int, roi: float) -> str:
    if rank == 1:
        return "🏆" if roi > 0 else "📉" if roi < 0 else "⚖️"
    return {2: "🥈", 3: "🥉"}.get(rank, "•")


def _simulator_recommended_strategy(
    filtered: pd.DataFrame,
    affidabilita: str,
    stake: float = 10.0,
    bankroll_start: float = 1000.0,
) -> tuple[list[dict], str]:
    """Top 3 strategie per ROI dal simulator sul campione filtrato (interesse composto)."""
    conf = _strategy_confidence(affidabilita)
    ranking = find_best_strategy(filtered, stake=stake, bankroll_start=bankroll_start)
    playable = ranking[ranking["total_bets"] > 0] if not ranking.empty else ranking

    if playable.empty:
        return [{
            "title": "⚖️ Nessuna strategia",
            "subtitle": "Nessuna bet simulabile con quote e risultati nel campione",
            "timing": "",
            "conf": conf,
        }], ""

    strategies = []
    for i, (_, row) in enumerate(playable.head(3).iterrows()):
        rank = i + 1
        roi = float(row["roi"])
        profit = float(row["profit"])
        bets = int(row["total_bets"])
        strike = float(row["strike_rate"])
        name = str(row["strategy"])
        icon = _strategy_rank_icon(rank, roi)
        strategies.append({
            "title": f"{icon} {name}",
            "subtitle": f"ROI {roi:+.1f}% · Profit {profit:+.0f}€ · {bets} bet",
            "timing": f"Strike {strike:.1f}% · interesse composto su {bets} partite",
            "conf": _conf_from_bets(affidabilita, bets),
        })

    edge_warning = ""
    if float(playable.iloc[0]["roi"]) < 0:
        edge_warning = "📊 ROI negativo nel campione — valuta rischio"

    return strategies, edge_warning


def _render_strategies_html(strategies: list[dict], edge_warning: str = "") -> str:
    blocks = []
    for i, s in enumerate(strategies):
        timing = s.get("timing") or ""
        timing_html = (
            f'<div style="font-size:10px; color:#38bdf8; margin-top:4px;">{timing}</div>'
            if timing else ""
        )
        border = "" if i == len(strategies) - 1 else "border-bottom:1px solid #1f2937;"
        blocks.append(
            f'<div style="margin-bottom:10px; padding-bottom:8px; {border}">'
            f'<div style="font-size:13px; font-weight:800; color:#f1f5f9; margin-bottom:3px;">'
            f'{s["title"]} '
            f'<span style="color:#64748b; font-weight:600; font-size:10px;">(CONF: {s["conf"]})</span>'
            f'</div>'
            f'<div style="font-size:11px; color:#94a3b8; line-height:1.4;">{s["subtitle"]}</div>'
            f'{timing_html}'
            f'</div>'
        )
    edge_html = (
        f'<div style="font-size:10px; color:#f59e0b; margin-top:4px;">{edge_warning}</div>'
        if edge_warning else ""
    )
    return "".join(blocks) + edge_html


def _early15_pct(goal_events, match_ids, parse_minute):
    early = total = 0
    for mid in match_ids:
        events = goal_events.get(int(mid), [])
        if not events:
            continue
        total += 1
        if min(parse_minute(e["minute"]) for e in events) <= 15:
            early += 1
    return round(early / total * 100, 1) if total else 0.0


def _late_goal_pct(goal_events, match_ids, parse_minute):
    late = total = 0
    for mid in match_ids:
        events = goal_events.get(int(mid), [])
        if not events:
            continue
        total += 1
        if min(parse_minute(e["minute"]) for e in events) > 45:
            late += 1
    return round(late / total * 100, 1) if total else 0.0


def _dynamic_title(over25_pct, btts_pct):
    if over25_pct > 65 and btts_pct > 60:
        return "🔥 MATCH OFFENSIVO — OVER 2.5 FORTE + BTTS ALTO"
    if over25_pct > 65:
        return "🔥 MATCH OFFENSIVO — OVER FORTE"
    if over25_pct < 45:
        return "❌ MATCH CHIUSO — UNDER"
    return "⚖️ MATCH EQUILIBRATO"


def _timing_text(early15_pct, late_goal_pct):
    if early15_pct > 60:
        return "Alta probabilità di gol nei primi 15 minuti → ingresso early"
    if late_goal_pct > 65:
        return "Gol concentrati nel 2° tempo → valore live"
    return "Distribuzione equilibrata → attendere sviluppo match"


def _insight_body(over25_pct, btts_pct, avg_goals):
    if over25_pct >= 55:
        return (
            f"Alta concentrazione di partite con <b>3+ gol ({over25_pct:.0f}%)</b> e "
            f"<b>BTTS ({btts_pct:.0f}%)</b>. "
            f"Il modello indica una struttura offensiva stabile, non casuale."
        )
    if over25_pct < 45:
        return (
            f"Match tendenzialmente chiuso: solo <b>{over25_pct:.0f}%</b> supera 2.5 gol. "
            f"BTTS al <b>{btts_pct:.0f}%</b> — cautela su mercati offensivi."
        )
    return (
        f"Profilo equilibrato: <b>{over25_pct:.0f}%</b> over 2.5, media <b>{avg_goals:.1f}</b> gol. "
        f"BTTS <b>{btts_pct:.0f}%</b> — attendere segnali live."
    )


def _final_decision(best_edge_pct, edge_spread_pct, best_market):
    if best_edge_pct > 20 and edge_spread_pct > 25:
        return f"FORTE VALUE su {best_market}"
    if best_edge_pct > 10:
        return f"Value moderato su {best_market}"
    return "Nessun edge chiaro → evitare"


def _render_power_insight(insights):
    ed = insights["edge_data"]
    best_edge = ed["edge_max"] * 100 if ed else 0
    worst_edge = ed["edge_min"] * 100 if ed else 0
    edge_spread = ed["edge_spread"] * 100 if ed else 0
    best_market = ed["best_market"] if ed else "N/D"
    worst_market = ed["worst_market"] if ed else "N/D"

    return f"""
    <div style="background:#0f172a; border:1px solid #1e293b; border-radius:10px; padding:18px;">

        <div style="font-size:11px; color:#64748b; font-weight:700; letter-spacing:1px;
                    text-transform:uppercase; margin-bottom:6px;">
            💡 INSIGHT PRINCIPALE
        </div>

        <div style="font-size:20px; font-weight:800; color:#f59e0b; margin-bottom:8px;">
            {insights["insight_title"]}
        </div>

        <div style="font-size:13px; color:#cbd5e1; line-height:1.5; margin-bottom:12px;">
            {insights["insight_body"]}
        </div>

        <div style="display:flex; gap:12px; margin-bottom:12px;">
            <div style="flex:1; background:#111827; border:1px solid #1f2937; border-radius:8px; padding:10px;">
                <div style="font-size:10px; color:#64748b;">🟢 EDGE MIGLIORE</div>
                <div style="font-size:18px; font-weight:800; color:#22c55e;">{best_edge:+.0f}%</div>
                <div style="font-size:10px; color:#94a3b8;">{best_market}</div>
            </div>
            <div style="flex:1; background:#111827; border:1px solid #1f2937; border-radius:8px; padding:10px;">
                <div style="font-size:10px; color:#64748b;">🔴 RISCHIO</div>
                <div style="font-size:18px; font-weight:800; color:#ef4444;">{worst_edge:.0f}%</div>
                <div style="font-size:10px; color:#94a3b8;">{worst_market}</div>
            </div>
            <div style="flex:1; background:#111827; border:1px solid #1f2937; border-radius:8px; padding:10px;">
                <div style="font-size:10px; color:#64748b;">⚖️ QUALITÀ</div>
                <div style="font-size:18px; font-weight:800; color:#3b82f6;">{edge_spread:.0f}%</div>
                <div style="font-size:10px; color:#94a3b8;">{insights["quality_label"]}</div>
            </div>
        </div>

        <div style="background:#111827; border:1px solid #1f2937; border-radius:8px; padding:10px; margin-bottom:10px;">
            <div style="font-size:10px; color:#64748b; margin-bottom:4px;">⏱ TIMING EDGE</div>
            <div style="font-size:13px; color:#e2e8f0;">{insights["timing_text"]}</div>
        </div>

        <div style="font-size:13px; color:#94a3b8; border-top:1px solid #1f2937; padding-top:10px;">
            🎯 <b>Strategia:</b> {insights["final_decision"]}
        </div>
    </div>
    """


def compute_header_insights(hw_pct, dr_pct, aw_pct, n, results, filtered,
                            goal_events, match_ids, parse_minute, g_dist,
                            edge_results=None, edge_df=None):
    avg_goals = results.get("avg_goals_ft", 0.0)
    over25_pct = results.get("over_25_ft_pct", 0.0)
    over15_pct = results.get("over_15_ft_pct", results.get("over_05_ft_pct", 50.0))
    btts_pct = results.get("btts_pct", 0.0)
    goals_1h_pct = results.get("goals_1h_pct", 50.0)

    er = edge_results if edge_results is not None else results
    edf = edge_df if edge_df is not None else filtered
    e_hw = er.get("home_win_pct", hw_pct)
    e_dr = er.get("draw_pct", dr_pct)
    e_aw = er.get("away_win_pct", aw_pct)
    e_over25 = er.get("over_25_ft_pct", over25_pct)
    e_over15 = er.get("over_15_ft_pct", er.get("over_05_ft_pct", over15_pct))
    e_btts = er.get("btts_pct", btts_pct)
    e_goals_1h = er.get("goals_1h_pct", goals_1h_pct)

    avg_over25 = _avg_odd(edf, "odds_over25", 1.85)
    avg_over15 = _avg_odd(edf, "odds_over15", 1.32)
    avg_under25 = 1 / (1 - 1 / avg_over25) if avg_over25 > 1 else 2.0
    avg_home = _avg_odd(edf, "odds_home", 2.00)
    avg_draw = _avg_odd(edf, "odds_draw", 3.20)
    avg_away = _avg_odd(edf, "odds_away", 2.95)
    avg_btts_y = _avg_odd(edf, "odds_btts_yes", 1.78)
    avg_btts_n = _avg_odd(edf, "odds_btts_no", 2.00)

    probabilities = {
        "1": e_hw / 100,
        "X": e_dr / 100,
        "2": e_aw / 100,
        "OVER 2.5": e_over25 / 100,
        "UNDER 2.5": (100 - e_over25) / 100,
        "OVER 1.5": e_over15 / 100,
        "BTTS YES": e_btts / 100,
        "BTTS NO": (100 - e_btts) / 100,
        "GOL 1T": e_goals_1h / 100,
    }
    odds_map = {
        "1": avg_home,
        "X": avg_draw,
        "2": avg_away,
        "OVER 2.5": avg_over25,
        "UNDER 2.5": avg_under25,
        "OVER 1.5": avg_over15,
        "BTTS YES": avg_btts_y,
        "BTTS NO": avg_btts_n,
        "GOL 1T": avg_over15,
    }

    edge_data = calculate_edges(probabilities, odds_map)
    eq_score = int(round(100 - abs(hw_pct - aw_pct), 0))

    all_goal_minutes = _extract_all_goal_minutes(goal_events, match_ids, parse_minute)
    tempo = _compute_tempo_gol(all_goal_minutes)
    timing_pct = tempo["timing_pct"]
    timing_label = tempo["timing_label"]
    timing_color = tempo["timing_color"]

    early15 = _early15_pct(goal_events, match_ids, parse_minute)
    late_goal = _late_goal_pct(goal_events, match_ids, parse_minute)
    key_moment_zone, key_moment, key_moment_pct = _key_moment(
        goal_events, match_ids, parse_minute,
    )
    avg_minute = (
        round(sum(all_goal_minutes) / len(all_goal_minutes), 1)
        if all_goal_minutes else 0.0
    )

    _best_range_key, best_range_label, range_pct = _compute_goal_range(filtered)
    edge_o25, edge_label = _compute_edge_over25(filtered, over25_pct)
    rel_label, rel_color = _reliability(n)
    strategies, strategy_edge_warning = _simulator_recommended_strategy(
        filtered, rel_label,
    )

    tg = pd.to_numeric(filtered.get("total_goals_ft", pd.Series(dtype=float)), errors="coerce").fillna(0)
    total_goals = int(tg.sum())

    insight_title = _dynamic_title(over25_pct, btts_pct)
    spread_pct = edge_data["edge_spread"] * 100 if edge_data else 0
    best_edge_pct = edge_data["edge_max"] * 100 if edge_data else 0
    quality_label, quality_color = _match_quality(
        edge_data["edge_spread"] if edge_data else 0
    )
    timing_text = _timing_text(early15, late_goal)
    final_decision = _final_decision(
        best_edge_pct, spread_pct,
        edge_data["best_market"] if edge_data else "N/D",
    )

    return {
        "avg_goals": avg_goals,
        "edge_data": edge_data,
        "edge_o25": edge_o25,
        "eq_score": eq_score,
        "eq_label": _eq_label(hw_pct, aw_pct, eq_score),
        "eq_subtext": _eq_subtext(hw_pct, aw_pct, eq_score),
        "timing_pct": timing_pct,
        "timing_label": timing_label,
        "timing_color": timing_color,
        "timing_text": timing_text,
        "best_range_label": best_range_label,
        "range_pct": range_pct,
        "edge_label": edge_label,
        "reliability_bar": _reliability_bar_pct(rel_label),
        "total_goals": total_goals,
        "over25_pct": over25_pct,
        "btts_pct": btts_pct,
        "insight_title": insight_title,
        "insight_body": _insight_body(over25_pct, btts_pct, avg_goals),
        "final_decision": final_decision,
        "reliability": rel_label,
        "reliability_color": rel_color,
        "quality_label": quality_label,
        "quality_color": quality_color,
        "key_moment": key_moment,
        "key_moment_zone": key_moment_zone,
        "key_moment_pct": key_moment_pct,
        "strategies": strategies,
        "strategy_edge_warning": strategy_edge_warning,
        "conf_max": _edge_confidence(edge_data["edge_max"]) if edge_data else 5,
        "conf_min": _edge_confidence(edge_data["edge_min"]) if edge_data else 3,
        "edge_match_count": int(er.get("match_count") or len(edf)),
    }


def _outcome_bar(pct, color, icon, label):
    w = min(max(pct, 0), 100)
    return f"""
    <div style="margin-bottom:6px;">
        <div style="display:flex; justify-content:space-between; font-size:10px; color:#94a3b8;">
            <span>{icon} {label}</span><span style="font-weight:700; color:#e2e8f0;">{pct:.1f}%</span>
        </div>
        <div style="background:#1f2937; height:5px; border-radius:3px; overflow:hidden;">
            <div style="width:{w}%; height:100%; background:{color};"></div>
        </div>
    </div>
    """


def _seg_bar(pct, color, segments=10):
    filled = round(min(pct, 100) / 100 * segments)
    cells = "".join(
        f'<div style="flex:1; height:4px; background:{color if i < filled else "#1f2937"}; '
        f'border-radius:2px; margin:0 1px;"></div>'
        for i in range(segments)
    )
    return f'<div style="display:flex; margin-top:6px;">{cells}</div>'


def _donut_esiti(hw, dr, aw):
    return f"""
    <div style="display:flex; align-items:center; gap:10px;">
        <div style="width:72px; height:72px; border-radius:50%; flex-shrink:0;
                    background:conic-gradient(
                        #3b82f6 0% {hw}%,
                        #f59e0b {hw}% {hw + dr}%,
                        #f97316 {hw + dr}% 100%
                    ); position:relative;">
            <div style="position:absolute; inset:14px; background:#111827; border-radius:50%;
                        display:flex; align-items:center; justify-content:center;
                        font-size:9px; color:#64748b; font-weight:700;">1X2</div>
        </div>
        <div style="flex:1;">
            {_outcome_bar(hw, "#3b82f6", "🏠", "Casa")}
            {_outcome_bar(dr, "#f59e0b", "🤝", "X")}
            {_outcome_bar(aw, "#f97316", "✈️", "2")}
        </div>
    </div>
    """


def render_premium_header(hw_pct, dr_pct, aw_pct, n, insights):
    avg = insights["avg_goals"]
    goal_color = "#22c55e" if avg >= 2.5 else "#ef4444"
    goal_w = min(max(avg / 4 * 100, 0), 100)
    eq = insights["eq_score"]
    eq_color = "#22c55e" if eq >= 70 else "#3b82f6" if eq >= 50 else "#ef4444"
    ed = insights["edge_data"]

    em = ed["edge_max"] * 100 if ed else 0
    en = ed["edge_min"] * 100 if ed else 0
    best_m = ed["best_market"] if ed else "N/D"
    worst_m = ed["worst_market"] if ed else "N/D"
    conf_max = insights["conf_max"]
    conf_min = insights["conf_min"]
    edge_n = insights.get("edge_match_count", n)

    strat_html = _render_strategies_html(
        insights["strategies"],
        insights.get("strategy_edge_warning", ""),
    )

    st.html(f"""
    <div class="pm-box" style="padding:14px; margin-bottom:16px;">
        <div style="font-size:13px; font-weight:700; color:#f1f5f9; margin-bottom:14px;
                    letter-spacing:0.5px;">RIEPILOGO ANALISI</div>

        <!-- ROW 1: 5 cards -->
        <div style="display:grid; grid-template-columns:1.4fr 1fr 1fr 1fr 1fr; gap:10px; margin-bottom:12px;">

            <div style="background:#111827; padding:12px; border-radius:10px; border:1px solid #1f2937;">
                <div style="font-size:9px; color:#64748b; font-weight:700; text-transform:uppercase;
                            margin-bottom:8px;">ESITI FINALI</div>
                {_donut_esiti(hw_pct, dr_pct, aw_pct)}
                <div style="font-size:9px; color:#64748b; margin-top:8px; border-top:1px solid #1f2937;
                            padding-top:6px;">PARTITE ANALIZZATE: <b style="color:#f1f5f9;">{n}</b></div>
            </div>

            <div style="background:#111827; padding:12px; border-radius:10px; border:1px solid #1f2937;
                        text-align:center;">
                <div style="font-size:9px; color:#64748b; font-weight:700; text-transform:uppercase;">
                    MEDIA GOL PARTITA</div>
                <div style="font-size:30px; color:{goal_color}; font-weight:800; margin:6px 0;">{avg:.2f}</div>
                <div style="font-size:9px; color:{goal_color}; font-weight:700;">
                    {"OVER 2.5" if avg >= 2.5 else "UNDER 2.5"}</div>
                <div style="height:5px; background:#1f2937; border-radius:3px; margin:8px 4px 0; overflow:hidden;">
                    <div style="width:{goal_w}%; height:100%; background:{goal_color};"></div>
                </div>
                <div style="font-size:8px; color:#64748b; margin-top:6px;">
                    {n:,} PARTITE FILTRATE · {insights["total_goals"]} GOL TOTALI</div>
            </div>

            <div style="background:#111827; padding:12px; border-radius:10px; text-align:center;
                        border:2px solid #22c55e; box-shadow:0 0 14px #22c55e35;">
                <div style="font-size:9px; color:#64748b; font-weight:700;">🟢 EDGE PIÙ ALTO</div>
                <div style="font-size:26px; font-weight:800; color:#22c55e; margin:6px 0;">{em:+.0f}%</div>
                <div style="font-size:9px; color:#22c55e; font-weight:600;">{best_m}</div>
                <div style="font-size:8px; color:#64748b; margin-top:8px;">CONFIDENCE</div>
                <div style="height:4px; background:#1f2937; border-radius:3px; margin-top:3px;">
                    <div style="width:{conf_max * 10}%; height:100%; background:#22c55e;"></div>
                </div>
                <div style="font-size:10px; color:#22c55e; font-weight:700;">{conf_max}/10</div>
                <div style="font-size:8px; color:#64748b; margin-top:6px;">su {edge_n:,} partite filtrate</div>
            </div>

            <div style="background:#111827; padding:12px; border-radius:10px; text-align:center;
                        border:2px solid #ef4444;">
                <div style="font-size:9px; color:#64748b; font-weight:700;">🔴 EDGE PIÙ BASSO</div>
                <div style="font-size:26px; font-weight:800; color:#ef4444; margin:6px 0;">{en:+.0f}%</div>
                <div style="font-size:9px; color:#ef4444; font-weight:600;">{worst_m}</div>
                <div style="font-size:8px; color:#64748b; margin-top:8px;">CONFIDENCE</div>
                <div style="height:4px; background:#1f2937; border-radius:3px; margin-top:3px;">
                    <div style="width:{conf_min * 10}%; height:100%; background:#ef4444;"></div>
                </div>
                <div style="font-size:10px; color:#ef4444; font-weight:700;">{conf_min}/10</div>
                <div style="font-size:8px; color:#64748b; margin-top:6px;">su {edge_n:,} partite filtrate</div>
            </div>

            <div style="background:#111827; padding:12px; border-radius:10px; border:1px solid #1f2937;
                        text-align:center;">
                <div style="font-size:9px; color:#64748b; font-weight:700; text-transform:uppercase;">
                    EQUILIBRIO PARTITA</div>
                <div style="font-size:30px; font-weight:800; color:{eq_color}; margin:6px 0;">{eq}</div>
                <div style="height:5px; background:#1f2937; border-radius:3px; overflow:hidden;">
                    <div style="width:{eq}%; height:100%; background:{eq_color};"></div>
                </div>
                <div style="font-size:10px; color:{eq_color}; font-weight:700; margin-top:6px;">
                    {insights["eq_label"]}</div>
                <div style="font-size:8px; color:#64748b; margin-top:3px;">{insights["eq_subtext"]}</div>
            </div>
        </div>
    """)

    st.html(f"""
        <!-- ROW 2: 4 mini-cards -->
        <div style="display:grid; grid-template-columns:repeat(4,1fr); gap:8px; margin-bottom:12px;">
            <div style="background:#111827; padding:10px; border-radius:8px; border:1px solid #1f2937;">
                <div style="font-size:8px; color:#64748b; font-weight:700;">⚡ TEMPO DEL GOL</div>
                <div style="font-size:13px; font-weight:800; color:{insights["timing_color"]}; margin:4px 0;">
                    {insights["timing_label"]}</div>
                <div style="font-size:9px; color:#94a3b8;">{insights["timing_pct"]:.0f}% dei gol</div>
                {_seg_bar(insights["timing_pct"], insights["timing_color"])}
            </div>
            <div style="background:#111827; padding:10px; border-radius:8px; border:1px solid #1f2937;">
                <div style="font-size:8px; color:#64748b; font-weight:700;">🎯 RANGE PIÙ FREQUENTE</div>
                <div style="font-size:13px; font-weight:800; color:#f59e0b; margin:4px 0;">
                    {insights["best_range_label"]}</div>
                <div style="font-size:9px; color:#94a3b8;">{insights["range_pct"]:.0f}% delle partite</div>
                {_seg_bar(insights["range_pct"], "#f59e0b")}
            </div>
            <div style="background:#111827; padding:10px; border-radius:8px; border:1px solid #1f2937;">
                <div style="font-size:8px; color:#64748b; font-weight:700;">🛡️ AFFIDABILITÀ</div>
                <div style="font-size:13px; font-weight:800; color:{insights["reliability_color"]}; margin:4px 0;">
                    {insights["reliability"]}</div>
                <div style="font-size:9px; color:#94a3b8;">{n} partite analizzate</div>
                {_seg_bar(insights["reliability_bar"], insights["reliability_color"])}
            </div>
            <div style="background:#111827; padding:10px; border-radius:8px; border:1px solid #1f2937;">
                <div style="font-size:8px; color:#64748b; font-weight:700;">⏱️ MOMENTO CHIAVE</div>
                <div style="font-size:13px; font-weight:800; color:#a855f7; margin:4px 0;">
                    {insights["key_moment"]}</div>
                <div style="font-size:9px; color:#94a3b8;">Periodo più produttivo</div>
                {_seg_bar(insights["key_moment_pct"], "#a855f7")}
            </div>
        </div>

        <!-- ROW 3: power insight + strategy -->
        <div style="display:grid; grid-template-columns:2fr 1fr; gap:10px;">
            {_render_power_insight(insights)}
            <div style="background:#111827; padding:12px; border-radius:8px; border:1px solid #1f2937;
                        height:100%;">
                <div style="font-size:10px; color:#38bdf8; font-weight:800; letter-spacing:0.08em;
                            text-transform:uppercase; margin-bottom:10px; padding-bottom:8px;
                            border-bottom:1px solid #1e293b;">
                    🎯 Top 3 strategie (simulator)</div>
                {strat_html}
            </div>
        </div>
    </div>
    """)
