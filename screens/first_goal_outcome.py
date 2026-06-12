"""
screens/first_goal_outcome.py — Esito finale dopo il primo gol
"""

from __future__ import annotations

import streamlit as st

from calculations import (
    FIRST_GOAL_OUTCOME_TIMEFRAMES,
    build_first_goal_outcome_dataset,
    calc_first_goal_outcome_stats,
    first_goal_probability_color,
    get_first_goal_outcome_decision,
    get_first_goal_outcome_percentages,
    get_first_goal_outcome_timeframe,
)


def _normalize_team(team: str | None) -> str | None:
    if not team:
        return None
    t = str(team).strip().lower()
    if t in ("home", "casa"):
        return "home"
    if t in ("away", "trasferta"):
        return "away"
    return None


def _pct_row(label: str, pct: float, icon: str) -> str:
    color = first_goal_probability_color(pct)
    return (
        f'<div style="display:flex;align-items:center;justify-content:space-between;'
        f'padding:5px 0;font-size:12px;">'
        f'<span style="color:#94a3b8;">{icon} {label}</span>'
        f'<span style="color:{color};font-weight:700;">{pct}%</span></div>'
    )


def _timeframe_column_html(
    tf: str,
    p: dict,
    labels: tuple[str, str, str],
    icons: tuple[str, str, str],
    accent: str,
    highlight: bool = False,
) -> str:
    border = f"2px solid {accent}" if highlight else "1px solid #1f2937"
    glow = f"box-shadow:0 0 12px {accent}33;" if highlight else ""
    return (
        f'<div style="background:#0f172a;border:{border};border-radius:8px;'
        f'padding:10px 12px;min-height:140px;{glow}">'
        f'<div style="font-size:13px;font-weight:800;color:#f1f5f9;text-align:center;'
        f'margin-bottom:6px;">{tf}\'</div>'
        f'{_pct_row(labels[0], p["win"], icons[0])}'
        f'{_pct_row(labels[1], p["draw"], icons[1])}'
        f'{_pct_row(labels[2], p["lose"], icons[2])}'
        f'<div style="font-size:10px;color:#64748b;text-align:center;margin-top:6px;">'
        f'n={p["total"]}</div></div>'
    )


def render_first_goal_outcome_block(
    matches_df,
    goal_events: dict | None = None,
    live_minute: int | None = None,
    live_team: str | None = None,
) -> None:
    """Tabella esito finale dopo primo gol + simulazione live."""
    dataset = build_first_goal_outcome_dataset(matches_df, goal_events)
    if not dataset:
        st.info("Nessuna partita con primo gol e risultato finale nel campione filtrato.")
        return

    stats = calc_first_goal_outcome_stats(dataset)
    n_matches = len(dataset)

    st.markdown(
        f'<div style="font-size:16px;font-weight:800;color:#f97316;margin:16px 0 4px 0;">'
        f'⚽ ESITO FINALE DOPO IL PRIMO GOL</div>'
        f'<div style="font-size:12px;color:#94a3b8;margin-bottom:12px;">'
        f'Analisi basata su <b>{n_matches:,}</b> partite con primo gol nel campione filtrato</div>',
        unsafe_allow_html=True,
    )

    # ── Casa segna per prima ──────────────────────────────────────────────
    st.markdown(
        '<div style="font-size:13px;font-weight:700;color:#3b82f6;margin:8px 0 10px 0;">'
        '🏠 SQUADRA CASA SEGNA PER PRIMA</div>',
        unsafe_allow_html=True,
    )
    cols_h = st.columns(len(FIRST_GOAL_OUTCOME_TIMEFRAMES))
    for i, tf in enumerate(FIRST_GOAL_OUTCOME_TIMEFRAMES):
        p = get_first_goal_outcome_percentages(stats[tf]["home"])
        html = _timeframe_column_html(
            tf, p,
            ("Vittoria casa", "Pareggio", "Sconfitta casa"),
            ("🏆", "🤝", "🛡️"),
            accent="#3b82f6",
        )
        with cols_h[i]:
            st.markdown(html, unsafe_allow_html=True)

    # ── Trasferta segna per prima ───────────────────────────────────────
    st.markdown(
        '<div style="font-size:13px;font-weight:700;color:#ef4444;margin:20px 0 10px 0;">'
        '✈️ SQUADRA TRASFERTA SEGNA PER PRIMA</div>',
        unsafe_allow_html=True,
    )
    cols_a = st.columns(len(FIRST_GOAL_OUTCOME_TIMEFRAMES))
    for i, tf in enumerate(FIRST_GOAL_OUTCOME_TIMEFRAMES):
        p = get_first_goal_outcome_percentages(stats[tf]["away"])
        html = _timeframe_column_html(
            tf, p,
            ("Vittoria trasf.", "Pareggio", "Sconfitta trasf."),
            ("🏆", "🤝", "🛡️"),
            accent="#ef4444",
        )
        with cols_a[i]:
            st.markdown(html, unsafe_allow_html=True)

    # ── Simulazione live ──────────────────────────────────────────────────
    st.markdown("---")
    st.markdown(
        '<div style="font-size:14px;font-weight:700;color:#f1f5f9;margin-bottom:8px;">'
        '⚽ Simulazione live / Esempio pratico</div>',
        unsafe_allow_html=True,
    )

    norm_live = _normalize_team(live_team)
    default_min = int(live_minute) if live_minute is not None else 67
    default_team_idx = 0 if norm_live != "away" else 1

    c1, c2 = st.columns(2)
    with c1:
        sim_minute = st.slider(
            "Minuto primo gol", 1, 90, default_min, key="fgo_live_minute",
        )
    with c2:
        sim_team_label = st.selectbox(
            "Chi segna per primo?",
            ["Casa", "Trasferta"],
            index=default_team_idx,
            key="fgo_live_team",
        )
    sim_team = "home" if sim_team_label == "Casa" else "away"

    decision = get_first_goal_outcome_decision(sim_minute, sim_team, stats)
    win_c = first_goal_probability_color(decision["win"])
    draw_c = first_goal_probability_color(decision["draw"])
    lose_c = first_goal_probability_color(decision["lose"])
    team_lbl = "CASA" if sim_team == "home" else "TRASFERTA"
    accent = "#3b82f6" if sim_team == "home" else "#ef4444"

    active_tf = get_first_goal_outcome_timeframe(sim_minute)
    st.markdown(
        f'<div style="font-size:11px;color:#64748b;margin-bottom:8px;">'
        f'Fascia attiva evidenziata: <b style="color:{accent};">{active_tf}\'</b></div>',
        unsafe_allow_html=True,
    )

    # Riga riepilogo con colonna attiva evidenziata
    recap_cols = st.columns(len(FIRST_GOAL_OUTCOME_TIMEFRAMES))
    side_key = sim_team
    for i, tf in enumerate(FIRST_GOAL_OUTCOME_TIMEFRAMES):
        p = get_first_goal_outcome_percentages(stats[tf][side_key])
        labels = (
            ("Vittoria casa", "Pareggio", "Sconfitta casa")
            if side_key == "home"
            else ("Vittoria trasf.", "Pareggio", "Sconfitta trasf.")
        )
        html = _timeframe_column_html(
            tf, p, labels, ("🏆", "🤝", "🛡️"), accent,
            highlight=(tf == active_tf),
        )
        with recap_cols[i]:
            st.markdown(html, unsafe_allow_html=True)

    st.markdown(
        f'<div style="background:#020617;border:2px solid {accent};border-radius:10px;'
        f'padding:16px 18px;margin-top:12px;">'
        f'<div style="font-size:11px;color:#86efac;font-weight:700;">LIVE · ESEMPIO PRATICO</div>'
        f'<div style="font-size:14px;color:#f1f5f9;margin-top:8px;line-height:1.7;">'
        f'Primo gol al <b>{sim_minute}\'</b> — squadra <b>{team_lbl}</b><br>'
        f'Fascia: <b>{decision["timeframe"]}\'</b> · Campione fascia: <b>{decision["total"]}</b> partite</div>'
        f'<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:12px;">'
        f'<div style="text-align:center;"><div style="font-size:11px;color:#94a3b8;">Vittoria</div>'
        f'<div style="font-size:22px;font-weight:800;color:{win_c};">{decision["win"]}%</div></div>'
        f'<div style="text-align:center;"><div style="font-size:11px;color:#94a3b8;">Pareggio</div>'
        f'<div style="font-size:22px;font-weight:800;color:{draw_c};">{decision["draw"]}%</div></div>'
        f'<div style="text-align:center;"><div style="font-size:11px;color:#94a3b8;">Sconfitta</div>'
        f'<div style="font-size:22px;font-weight:800;color:{lose_c};">{decision["lose"]}%</div></div>'
        f'</div>'
        f'<div style="font-size:18px;font-weight:900;color:#f97316;margin-top:14px;">'
        f'👉 {decision["decision"]}</div>'
        f'<div style="font-size:12px;color:#94a3b8;margin-top:6px;">{decision["hint"]}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )
