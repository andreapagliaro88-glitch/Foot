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
    get_first_goal_outcome_percentages,
)


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
) -> None:
    """Tabella esito finale dopo primo gol per fascia temporale."""
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
