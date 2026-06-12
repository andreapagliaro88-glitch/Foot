"""
screens/live.py — Live Analysis screen (v4 — layout logico)

Ordine pagina (dall'alto):
  0. Header — squadre, score, timer, evento live
  1. KPI live — Next Goal | BTTS | Esito finale
  2. Statistiche per tempo — 1° tempo | 2° tempo
  3. Proiezione live — intervalli dinamici + best interval
  4. Distribuzioni gol — grafici 1H / 2H
  5. Scenari vantaggio/svantaggio (blocchi 4-5)
  6. Pattern attivi
  7. ROI Simulazione Live — mercati e top ROI

Fixes vs v2:
  - st.set_page_config no longer overrides padding from main app
  - Charts rendered with st.plotly_chart outside markdown divs (no code bleed)
  - Decision Engine uses pure HTML in st.markdown — no nested st calls
  - Dynamic timeframe filter: only future buckets shown
  - Consistent card heights via min-height, not fixed height (avoids overlap)
"""

import streamlit as st
import pandas as pd
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from screen_cache import load_live_data, build_prematch_frame

from database import get_goal_events_for_matches, get_matches_dataframe
from filters import (
    render_filter_sidebar,
    apply_filters,
    should_run_analysis,
    tick_live_match_clock,
    LIVE_TIMER_REFRESH_SEC,
)
from calculations import (
    analyze_live_state_v2,
    build_score_index,
    calc_live_roi_simulation,
    calc_live_goal_probability,
    filter_matches_by_goal_criteria,
    get_similar_matches_dataframe,
    build_future_intervals,
    get_best_interval,
    prob_goal_within_minutes,
    live_entry_signal,
    live_odds_trigger,
    calc_post_goal_future_analysis,
    generate_live_trigger,
)
from screens.roi_dashboard import render_roi_dashboard
from screens.momentum_chart import render_similar_momentum_block
from screens.first_goal_outcome import render_first_goal_outcome_block
from utils import format_pct, get_sorted_goals_with_team

# ── Palette — matches prematch.py exactly ─────────────────────────────────────
C_BLUE   = "#1e3a5f"
C_GREEN  = "#064e3b"
C_DARK   = "#111827"   # pm-card bg
C_CARD   = "#111827"   # same — use pm-card style
C_CARD_B = "#1e293b"   # inner cells (prematch uses #1e293b for inner boxes)
C_BORDER = "#1f2937"   # pm border color
C_TEXT   = "#f1f5f9"   # prematch main text
C_MUTED  = "#94a3b8"   # prematch label color
C_MUTED2 = "#64748b"   # prematch sub color
C_GREEN2 = "#22c55e"   # prematch green (was #10b981, prematch uses #22c55e)
C_BLUE2  = "#3b82f6"   # prematch blue
C_RED    = "#ef4444"   # same
C_YELLOW = "#f59e0b"   # same
C_ORANGE = "#f97316"   # same
C_BG     = "#0d1117"

PLOT_BG = "rgba(0,0,0,0)"
GRID_C  = "#1f2937"
FONT    = dict(color="#e2e8f0", size=10)

_LAYOUT_BASE = dict(
    plot_bgcolor=PLOT_BG,
    paper_bgcolor=PLOT_BG,
    font=dict(color="#e2e8f0"),
    showlegend=False,
    margin=dict(l=8, r=8, t=30, b=8),
)


# ── Chart helpers — prematch-matching style ────────────────────────────────────

def _bar_fig(labels, values, colors=None, title="", h=165):
    import plotly.graph_objects as go
    if not labels or not values:
        return None
    fig = go.Figure(go.Bar(
        x=labels, y=values,
        marker_color=colors if colors else "#22c55e",
        text=[f"{v:.1f}%" for v in values],
        textposition="outside",
        textfont=dict(size=11, color="#f1f5f9"),
        cliponaxis=False,
    ))
    fig.update_layout(
        **_LAYOUT_BASE,
        title=dict(text=title, font=dict(color="#94a3b8", size=13), x=0),
        height=h,
        bargap=0.3,
        xaxis=dict(showgrid=False, zeroline=False,
                   tickfont=dict(color="#94a3b8", size=10), tickangle=-20),
        yaxis=dict(showgrid=True, gridcolor=GRID_C, zeroline=False,
                   visible=False,
                   range=[0, max(values)*1.3] if values else [0, 100]),
    )
    return fig


def _hbar_fig(labels, values, colors=None, title="", h=165):
    import plotly.graph_objects as go
    if not labels or not values:
        return None
    bar_colors = colors if colors else ["#22c55e"] * len(values)
    fig = go.Figure(go.Bar(
        y=labels, x=values,
        orientation="h",
        marker_color=bar_colors,
        text=[f"{v:.1f}%" for v in values],
        textposition="auto",
        textfont=dict(size=11, color="#f1f5f9"),
    ))
    fig.update_layout(
        **_LAYOUT_BASE,
        title=dict(text=title, font=dict(color="#94a3b8", size=13), x=0),
        height=h,
        xaxis=dict(showgrid=False, zeroline=False, visible=False),
        yaxis=dict(showgrid=False, zeroline=False,
                   tickfont=dict(color="#94a3b8", size=11), autorange="reversed"),
    )
    return fig


def _donut_fig(labels, values, colors, h=155):
    import plotly.graph_objects as go
    if not values or sum(values) == 0:
        return None
    fig = go.Figure(go.Pie(
        labels=labels, values=values,
        hole=0.6,
        marker=dict(colors=colors),
        textinfo="percent",
        textfont=dict(size=11, color="#f1f5f9"),
        showlegend=True,
    ))
    fig.update_layout(
        height=h,
        margin=dict(l=4, r=4, t=8, b=4),
        plot_bgcolor=PLOT_BG, paper_bgcolor=PLOT_BG,
        font=dict(color="#e2e8f0"),
        legend=dict(font=dict(size=10, color="#94a3b8"), orientation="v", x=0.7, y=0.5),
    )
    return fig


def _color_val(v, high_good=True):
    if high_good:
        return C_GREEN2 if v >= 55 else (C_YELLOW if v >= 40 else C_RED)
    return C_RED if v >= 55 else (C_YELLOW if v >= 40 else C_GREEN2)


def _card_start(extra_style=""):
    """Card matching prematch pm-box: dark bg, 1px border, 8px radius."""
    return (
        f'<div style="background:#111827;border:1px solid #1f2937;'
        f'border-radius:8px;padding:12px 14px;{extra_style}">'
    )

_CARD_END = "</div>"


def _mini_bar(label, val, max_val, color, width_label="70px"):
    bw = int(val / max_val * 100) if max_val > 0 else 0
    fire = "🔥" if val == max_val and max_val > 0 else ""
    return f"""
    <div style="display:flex;align-items:center;margin:3px 0;font-size:11px;">
        <div style="width:{width_label};color:{C_MUTED};white-space:nowrap;overflow:hidden;">{label}</div>
        <div style="flex:1;background:#374151;height:6px;border-radius:3px;margin:0 4px;">
            <div style="width:{bw}%;background:{color};height:100%;border-radius:3px;"></div>
        </div>
        <div style="width:35px;color:{C_TEXT};text-align:right">{val:.0f}% {fire}</div>
    </div>"""


def _live_team_key(label):
    """Map sidebar label Casa/Trasferta → home/away."""
    return "home" if label == "Casa" else "away"


def _build_goal_criteria(filters):
    """Build sorted [(minute, home|away), ...] from validated sidebar goals."""
    if not filters.get("goals_time_valid", True):
        return []
    criteria = []
    for minute, team in filters.get("valid_goals", []):
        criteria.append((int(minute), _live_team_key(team)))
    criteria.sort(key=lambda x: x[0])
    return criteria


def _goal_tolerance(goal_index, base_tolerance, expanded=False):
    """
    Per-goal minute window.
    1° gol: ±4 min (±5 se campione < 5 partite).
    2° e 3° gol: minimo ±5; se campione < 5 partite si amplia di +2.
    """
    if goal_index == 0:
        return 5 if expanded else 4
    tol = max(base_tolerance, 5)
    if expanded:
        tol += 2
    return tol


def _filter_matches_by_goals(matches_df, criteria, tolerance, current_minute):
    """
    Similar matches: 1°/2°/3° gol con stesso minuto (±tol) e stessa squadra.
    Espande ±2 su ogni gol se meno di 5 partite.
    """

    def _collect(expanded):
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
                tol_i = _goal_tolerance(i, tolerance, expanded)
                if not (target_m - tol_i <= m <= target_m + tol_i) or team != target_team:
                    matched = False
                    break
            if not matched:
                continue
            after = [m for m, _ in match_goals if m >= current_minute]
            selected.append((match_goals[0][0], after))
        return selected

    expanded = False
    selected = _collect(expanded)
    if len(selected) < 5:
        expanded = True
        selected = _collect(expanded)

    ranges = [
        (
            max(0, m - _goal_tolerance(i, tolerance, expanded)),
            min(90, m + _goal_tolerance(i, tolerance, expanded)),
            team,
        )
        for i, (m, team) in enumerate(criteria)
    ]
    return selected, ranges, expanded


def _format_similar_goals_label(criteria, ranges):
    """Human-readable similar-match criteria for header."""
    ordinals = ["1°", "2°", "3°"]
    team_lbl = {"home": "Casa", "away": "Trasferta"}
    parts = []
    for i, ((m, team), (lo, hi, _)) in enumerate(zip(criteria, ranges)):
        label = ordinals[i] if i < len(ordinals) else f"{i + 1}°"
        parts.append(
            f"{label} gol {lo}'–{hi}' {team_lbl.get(team, team)} (ref {m}')"
        )
    return " · ".join(parts)


def _get_row_style(pct):
    if pct >= 65:
        return "#22c55e", "0 0 12px #22c55e"
    if pct >= 50:
        return "#f59e0b", "0 0 10px #f59e0b"
    return "#ef4444", "none"


def _render_heat_bar(pct):
    intensity = min(max(pct / 100, 0.05), 1.0)
    bar_col = C_GREEN2 if pct >= 65 else (C_YELLOW if pct >= 50 else C_RED)
    return (
        f'<div style="height:8px;background:#1f2937;border-radius:4px;overflow:hidden;'
        f'margin-top:6px;">'
        f'<div style="width:{pct}%;height:100%;background:{bar_col};'
        f'opacity:{intensity};border-radius:4px;"></div></div>'
    )


def _odds_row_icon(market_odds, recommended_odds):
    _, icon, _ = live_odds_trigger(market_odds, recommended_odds)
    return icon


def _render_live_interval_table(title, table, accent, market_odds, recommended_odds, show_best=False):
    """Tabella intervalli con glow, heatmap bar e trigger quote."""
    if not table:
        return (
            f'<div style="background:#111827;border:1px solid #1f2937;border-radius:8px;'
            f'padding:12px 14px;"><div style="color:{C_MUTED};">Nessun dato</div></div>'
        )

    best_key, best_val = get_best_interval(table)
    rows = ""
    for key, v in table.items():
        pct = v["pct"]
        color, glow = _get_row_style(pct)
        signal = _odds_row_icon(market_odds, recommended_odds)
        is_best = key == best_key and pct > 0
        row_bg = "background:rgba(34,197,94,0.06);" if is_best else ""
        rows += (
            f'<div style="padding:8px;border-bottom:1px solid #1f2937;{row_bg}">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;">'
            f'<span style="color:{C_TEXT};font-weight:{"700" if is_best else "500"};">'
            f'{key}\'{" 🔥" if is_best else ""}</span>'
            f'<span style="color:{color};font-weight:700;text-shadow:{glow};">{pct}%</span>'
            f'</div>'
            f'{_render_heat_bar(pct)}'
            f'<div style="display:flex;justify-content:space-between;font-size:11px;'
            f'color:{C_MUTED};margin-top:4px;">'
            f'<span>{v["goals"]}/{v["total"]}</span>'
            f'<span>{signal}</span>'
            f'</div></div>'
        )

    best_box = ""
    if show_best and best_val.get("pct", 0) > 0:
        best_box = (
            f'<div style="margin-top:10px;padding:10px;background:#111827;border-radius:8px;'
            f'border:1px solid {C_GREEN2};">'
            f'<div style="font-size:12px;font-weight:700;color:{C_GREEN2};">'
            f'🔥 PROSSIMO GOL PIÙ PROBABILE: {best_key}\'</div>'
            f'<div style="font-size:18px;font-weight:800;color:{C_GREEN2};margin-top:4px;">'
            f'📊 {best_val["pct"]}%</div>'
            f'<div style="font-size:11px;color:{C_MUTED};margin-top:2px;">'
            f'{best_val["goals"]}/{best_val["total"]} partite</div>'
            f'</div>'
        )

    return (
        f'<div style="background:#111827;border:1px solid #1f2937;border-radius:8px;'
        f'padding:12px 14px;height:100%;">'
        f'<div style="font-size:13px;font-weight:700;color:{accent};margin-bottom:8px;">{title}</div>'
        f'{rows}{best_box}</div>'
    )


def _render_live_projection_block(
    matches_df, filters, goal_events, score_index,
    current_minute, home_score, away_score,
):
    """Proiezione live: prob gol, best interval, tabelle 5/10/15 min."""
    criteria = _build_goal_criteria(filters)
    if criteria:
        ep_df, _ = filter_matches_by_goal_criteria(matches_df, criteria, tolerance=2)
        _, ranges_5, _ = _filter_matches_by_goals(matches_df, criteria, 2, current_minute)
        similar_lbl = _format_similar_goals_label(criteria, ranges_5)
        filter_note = (
            f'<div style="font-size:11px;color:{C_MUTED};margin-bottom:8px;">'
            f'<b>Filtro gol:</b> <span style="color:{C_BLUE2};">{similar_lbl}</span></div>'
        )
    else:
        ep_df = get_similar_matches_dataframe(
            matches_df, goal_events, current_minute, home_score, away_score,
            score_index=score_index,
        )
        filter_note = (
            f'<div style="font-size:11px;color:{C_MUTED};margin-bottom:8px;">'
            f'Partite simili: risultato <b>{home_score}-{away_score}</b> al {current_minute}\' (±5 min)'
            f'</div>'
        )

    if ep_df is None or ep_df.empty:
        st.warning("Nessuna partita simile per la proiezione live.")
        return

    live_goal = calc_live_goal_probability(ep_df, current_minute, edge=0.05, min_goals_after=1)
    table_5 = build_future_intervals(ep_df, current_minute, 5)
    table_10 = build_future_intervals(ep_df, current_minute, 10)
    table_15 = build_future_intervals(ep_df, current_minute, 15)

    best_5 = get_best_interval(table_5)
    best_10 = get_best_interval(table_10)
    best_15 = get_best_interval(table_15)
    best_interval, best_stats = best_10
    best_prob = best_stats["pct"]

    cum_5 = prob_goal_within_minutes(ep_df, current_minute, 5)
    cum_10 = prob_goal_within_minutes(ep_df, current_minute, 10)
    cum_15 = prob_goal_within_minutes(ep_df, current_minute, 15)

    signal_txt, signal_col = live_entry_signal(best_prob)
    prob_1g = live_goal["prob"] if live_goal else 0.0
    prob_1g_cnt = live_goal["with_goal"] if live_goal else 0
    prob_1g_tot = live_goal["total"] if live_goal else 0
    fair_odds = live_goal["fair_odds"] if live_goal else 0.0
    recommended_odds = live_goal["recommended_odds"] if live_goal else 0.0

    if "odds_over25" in ep_df.columns:
        _odds_s = pd.to_numeric(ep_df["odds_over25"], errors="coerce").dropna()
        _default_book = round(float(_odds_s.mean()), 2) if len(_odds_s) else recommended_odds or 1.55
    else:
        _default_book = recommended_odds or 1.55

    market_odds = float(_default_book)
    value_lbl, value_icon, value_col = live_odds_trigger(market_odds, recommended_odds)
    st.markdown(
        f'<div style="padding:10px 14px;background:#0f172a;border:1px solid #1e293b;'
        f'border-radius:8px;margin-bottom:10px;">'
        f'<span style="font-size:12px;color:{C_MUTED};">Quota giusta: </span>'
        f'<b style="color:{C_TEXT};">{fair_odds}</b>'
        f'<span style="font-size:12px;color:{C_MUTED};margin-left:12px;">Consigliata (+5%): </span>'
        f'<b style="color:{C_GREEN2};">{recommended_odds}</b>'
        f'<span style="margin-left:14px;font-weight:700;color:{value_col};">'
        f'{value_icon} {value_lbl}</span></div>',
        unsafe_allow_html=True,
    )

    if best_prob > 65 and market_odds > recommended_odds and recommended_odds > 0:
        st.success(
            f"🔥 ENTRY NOW — {best_prob}% nel {best_interval}\' · "
            f"book {market_odds:.2f} > value {recommended_odds:.2f}"
        )

    st.html(
        f'<div style="padding:16px;background:#0f172a;border:1px solid #1e293b;'
        f'border-radius:10px;margin-bottom:10px;">'
        f'<div style="font-weight:700;color:#fbbf24;">'
        f'⚽ PROIEZIONE LIVE DAL {current_minute}\'</div>'
        f'{filter_note}'
        f'<div style="display:flex;justify-content:space-between;flex-wrap:wrap;'
        f'gap:12px;margin-top:12px;">'
        f'<div>'
        f'<div style="font-size:12px;color:{C_MUTED};">ALMENO 1 GOL (totale)</div>'
        f'<div style="font-size:26px;font-weight:800;color:{C_GREEN2};">{prob_1g}%</div>'
        f'<div style="font-size:11px;color:{C_MUTED};">{prob_1g_cnt}/{prob_1g_tot} partite</div>'
        f'</div>'
        f'<div>'
        f'<div style="font-size:12px;color:{C_MUTED};">PROSSIMO GOL PIÙ PROBABILE</div>'
        f'<div style="font-size:26px;font-weight:800;color:{C_GREEN2};">{best_interval}\'</div>'
        f'<div style="font-size:11px;color:{C_MUTED};">step 10 min · {best_stats["goals"]}/{best_stats["total"]}</div>'
        f'</div>'
        f'<div style="text-align:right;">'
        f'<div style="font-size:12px;color:{C_MUTED};">PROBABILITÀ INTERVALLO</div>'
        f'<div style="font-size:26px;font-weight:800;color:{C_GREEN2};">{best_prob}%</div>'
        f'<div style="font-size:12px;font-weight:700;color:{signal_col};margin-top:4px;">'
        f'{signal_txt}</div>'
        f'<div style="font-size:11px;color:{value_col};margin-top:2px;">{value_icon} {value_lbl}</div>'
        f'</div></div>'
        f'<div style="display:flex;gap:16px;flex-wrap:wrap;margin-top:12px;'
        f'font-size:12px;color:{C_MUTED};">'
        f'<span>📊 entro 5 min: <b style="color:{C_TEXT};">{cum_5["pct"] if cum_5 else 0}%</b></span>'
        f'<span>📊 entro 10 min: <b style="color:{C_GREEN2};">{cum_10["pct"] if cum_10 else 0}%</b></span>'
        f'<span>📊 entro 15 min: <b style="color:{C_TEXT};">{cum_15["pct"] if cum_15 else 0}%</b></span>'
        f'<span style="margin-left:auto;">Basato su <b style="color:{C_TEXT};">'
        f'{best_stats["total"]}</b> partite simili</span>'
        f'</div>'
        f'<div style="margin-top:8px;font-size:11px;color:{C_MUTED2};">'
        f'Best 5 min: {best_5[0]}\' ({best_5[1]["pct"]}%) · '
        f'Best 15 min: {best_15[0]}\' ({best_15[1]["pct"]}%)'
        f'</div></div>'
    )

    c1, c2, c3 = st.columns(3)
    with c1:
        st.html(_render_live_interval_table(
            "📊 INTERVALLI 5 MIN", table_5, C_BLUE2, market_odds, recommended_odds,
        ))
    with c2:
        st.html(_render_live_interval_table(
            "⏱ PROIEZIONE PROSSIMO GOL (10 MIN)", table_10, C_YELLOW,
            market_odds, recommended_odds, show_best=True,
        ))
    with c3:
        st.html(_render_live_interval_table(
            "📊 INTERVALLI 15 MIN", table_15, C_ORANGE, market_odds, recommended_odds,
        ))


def _section_header(num, title, color=C_ORANGE):
    return (
        f'<div style="font-size:14px;font-weight:700;color:{color};'
        f'text-transform:uppercase;letter-spacing:0.6px;margin-bottom:4px;">{num} {title}</div>'
    )


def _sub(text):
    return f'<div style="font-size:12px;color:#64748b;margin-bottom:6px;">{text}</div>'


# ── Dynamic timeframe helpers ──────────────────────────────────────────────────

ALL_BUCKETS_ORDER = ["0-15", "16-30", "31-45", "45+", "46-60", "61-75", "76-90", "90+"]
H1_BUCKETS = ["0-15", "16-30", "31-45", "45+"]
H2_BUCKETS = ["46-60", "61-75", "76-90", "90+"]

BUCKET_START = {
    "0-15": 0, "16-30": 16, "31-45": 31, "45+": 45,
    "46-60": 46, "61-75": 61, "76-90": 76, "90+": 90,
}

BUCKET_END = {
    "0-15": 15, "16-30": 30, "31-45": 45, "45+": 45,
    "46-60": 60, "61-75": 75, "76-90": 90, "90+": 999,
}


def _future_buckets(current_minute):
    """Return only timeframe buckets that are fully or partially in the future."""
    return [b for b in ALL_BUCKETS_ORDER if BUCKET_START.get(b, 999) >= current_minute - 5]


def _team_initials(name):
    """Short label for circular team badge."""
    name = (name or "").strip()
    if not name or name.lower() in ("casa", "trasferta"):
        return name[:1].upper() if name else "?"
    parts = [p for p in name.replace(".", " ").split() if p]
    if len(parts) >= 2:
        return (parts[0][0] + parts[-1][0]).upper()
    return name[:3].upper()


def _team_name_style(is_winning):
    if is_winning:
        return "color:#22c55e;text-shadow:0 0 10px #22c55e,0 0 20px rgba(34,197,94,0.45);"
    return "color:#f1f5f9;"


def _score_box_glow(home_score, away_score):
    """Glow esterno box score: blu casa, rosso trasferta, grigio pareggio."""
    if home_score > away_score:
        return "0 0 16px #3b82f6, 0 0 28px rgba(59,130,246,0.5)"
    if away_score > home_score:
        return "0 0 16px #ef4444, 0 0 28px rgba(239,68,68,0.5)"
    return "0 0 12px #64748b, 0 0 20px rgba(100,116,139,0.4)"


_GOAL_ORDINAL_LABELS = ["primo", "secondo", "terzo", "quarto", "quinto"]


def _team_goals_timeline_html(filters, team_side):
    """Gol della squadra con ordine nella partita: primo gol — 32', ecc."""
    all_goals = sorted(filters.get("valid_goals", []), key=lambda x: x[0])

    rows = []
    for i, (minute, team) in enumerate(all_goals):
        if team != team_side:
            continue
        label = (
            _GOAL_ORDINAL_LABELS[i]
            if i < len(_GOAL_ORDINAL_LABELS)
            else f"{i + 1}°"
        )
        rows.append(
            f'<div style="font-size:10px;line-height:1.4;color:#94a3b8;">'
            f'<span style="color:#64748b;text-transform:lowercase;">{label} gol</span>'
            f' — <span style="color:#22c55e;font-weight:700;">{minute}\'</span>'
            f'</div>'
        )
    if not rows:
        return ""
    return (
        f'<div style="display:flex;flex-direction:column;gap:1px;margin-top:3px;">'
        f'{"".join(rows)}</div>'
    )


def _resolve_live_phase_event(
    minute, home_score, away_score, r, filters,
    is_post_goal, first_goal_min,
):
    """Fase live + eventi collegati ai dati reali (gol, prob, over)."""
    total_goals = home_score + away_score
    prob_ng = float(r.get("prob_next_goal", 0) or 0)
    over25 = float(r.get("over_25_live", 0) or 0)
    goal_at_now = any(g[0] == minute for g in filters.get("valid_goals", []))

    if minute >= 90:
        return "🏁 FINE PARTITA", "#ef4444", "0 0 14px #ef4444"
    if is_post_goal and first_goal_min is not None:
        return (
            f"🔥 POST-GOAL MODE — Gol al {first_goal_min}'",
            "#f97316",
            "0 0 12px #f97316",
        )
    if minute == 45:
        return "⏸ FINE PRIMO TEMPO", "#f59e0b", "0 0 12px #f59e0b"
    if goal_at_now:
        return "🔥 GOAL DETECTED", "#22c55e", "0 0 14px #22c55e"
    if minute == 20 and total_goals == 0:
        return "💡 ENTRY OVER NOW — 0-0 al 20'", "#22c55e", "0 0 12px #22c55e"
    if total_goals == 0 and prob_ng >= 55 and minute >= 20:
        return f"💡 ENTRY OVER NOW — {prob_ng:.0f}%", "#22c55e", "0 0 12px #22c55e"
    if minute > 60 and over25 >= 70:
        return f"💡 OVER LIVE ENTRY — {over25:.0f}%", "#22c55e", "0 0 12px #22c55e"
    if minute < 20:
        return "⚡ FASE INIZIALE", "#3b82f6", "0 0 10px #3b82f6"
    if minute < 45:
        return "🔥 PRESSIONE GOAL", "#22c55e", "0 0 12px #22c55e"
    if minute < 70:
        return "📈 SECONDO TEMPO ATTIVO", "#22c55e", "0 0 12px #22c55e"
    return "🔥 FASE FINALE — ALTA VARIANZA", "#ef4444", "0 0 14px #ef4444"


def _team_logo_html(side, team_name, is_winning):
    """Logo squadra se configurato, altrimenti badge con iniziali."""
    from utils import get_team_logo_src, team_initials

    bg = (
        "linear-gradient(145deg,#1e3a8a 0%,#3b82f6 100%)"
        if side == "home"
        else "linear-gradient(145deg,#991b1b 0%,#ef4444 100%)"
    )
    cls = "live-team-badge live-team-badge-winning" if is_winning else "live-team-badge"
    src = get_team_logo_src(team_name)
    if src:
        return (
            f'<img src="{src}" alt="{team_name}" class="{cls}" '
            f'style="width:48px;height:48px;object-fit:contain;display:block;flex-shrink:0;" />'
        )
    init = team_initials(team_name)
    fsize = "11px" if len(init) > 2 else "15px"
    return (
        f'<div class="{cls}" style="width:48px;height:48px;border-radius:50%;'
        f'background:{bg};display:flex;align-items:center;justify-content:center;'
        f'font-size:{fsize};font-weight:900;color:#fff;letter-spacing:0.5px;'
        f'flex-shrink:0;">{init}</div>'
    )


def _render_post_goal_interval_rows(table: dict) -> str:
    if not table:
        return f'<div style="color:{C_MUTED};font-size:12px;">Nessun dato</div>'
    rows = ""
    best_key, best_val = get_best_interval(table)
    for key, v in table.items():
        pct = v["pct"]
        is_hot = key == best_key and pct >= 55
        color = C_GREEN2 if pct >= 55 else (C_YELLOW if pct >= 45 else C_TEXT)
        fire = " 🔥" if is_hot else ""
        rows += (
            f'<div style="display:flex;justify-content:space-between;align-items:center;'
            f'padding:6px 0;border-bottom:1px solid #1f2937;">'
            f'<span style="color:{C_TEXT};font-size:13px;font-weight:{"700" if is_hot else "500"};">'
            f'{key}{fire}</span>'
            f'<span style="color:{color};font-weight:700;font-size:13px;">{pct}%</span>'
            f'</div>'
            f'<div style="font-size:10px;color:{C_MUTED2};margin-top:-2px;margin-bottom:4px;">'
            f'{v["goals"]}/{v["total"]} partite</div>'
        )
    return rows


def _post_goal_trigger_table_key(tables: dict, first_goal_team) -> str:
    """Tabella trigger in base a chi ha segnato il primo gol."""
    if first_goal_team == "Casa" and tables["home"]["count"] >= 5:
        return "home"
    if first_goal_team == "Trasferta" and tables["away"]["count"] >= 5:
        return "away"
    return "total"


def _render_live_signal_card(data: dict, scorer_label: str) -> None:
    signal = data["signal"]
    strength = data["strength"]
    styles = {
        "FORTE":   ("#22c55e", "0 0 20px rgba(34,197,94,0.4)", "#22c55e"),
        "MEDIA":   ("#22c55e", "0 0 16px rgba(34,197,94,0.3)", "#4ade80"),
        "MONITOR": ("#f59e0b", "0 0 16px rgba(245,158,11,0.35)", "#f59e0b"),
        "LOW":     ("#f97316", "0 0 14px rgba(249,115,22,0.35)", "#f97316"),
        "WAIT":    ("#334155", "none", "#94a3b8"),
    }
    border, glow, sig_color = styles.get(strength, styles["WAIT"])

    st.markdown(
        f'<div style="padding:16px;border-radius:12px;background:#020617;'
        f'border:1px solid {border};box-shadow:{glow};">'
        f'<div style="font-size:12px;color:#86efac;">⚡ LIVE SIGNAL · {scorer_label}</div>'
        f'<div style="font-size:26px;font-weight:900;color:{sig_color};margin-top:5px;">'
        f'{signal}</div>'
        f'<div style="margin-top:10px;font-size:12px;color:#94a3b8;line-height:1.6;">'
        f'⏱ Miglior timing: <b>{data["best_interval"]}</b> ({data["best_prob"]}%)<br>'
        f'📈 Probabilità globale (≥1 gol dopo): <b>{data["global_prob_pct"]}%</b><br>'
        f'📊 Campione: <b>{data["confidence"]}</b> partite<br>'
        f'💰 Quota corretta: <b>{data["fair_odds"]}</b>'
        f'</div></div>',
        unsafe_allow_html=True,
    )


def _render_post_goal_analysis_block(
    matches_df,
    reference_minute: int,
    input_minute: int,
    home_team: str,
    away_team: str,
    first_goal_team=None,
):
    """POST GOAL ANALYSIS — dataset unico, fasce future dal minuto live."""
    analysis = calc_post_goal_future_analysis(
        matches_df, reference_minute, input_minute, tolerance=5,
    )
    tol = analysis["tolerance"]
    tables = analysis["tables"]
    n_total = tables["total"]["count"]

    if n_total == 0:
        st.warning(
            f"Nessuna partita storica con primo gol intorno al {input_minute}' "
            f"(±{tol} min)."
        )
        return

    scorer_lbl = first_goal_team or "Totale"
    trigger_key = _post_goal_trigger_table_key(tables, first_goal_team)
    trigger_pack = tables[trigger_key]
    trigger_table = trigger_pack["table"]
    trigger_matches = trigger_pack.get("matches", [])

    st.markdown(
        f'<div style="font-size:16px;font-weight:800;color:{C_ORANGE};margin:12px 0 4px 0;">'
        f'⚡ POST GOAL ANALYSIS (minuto {input_minute}\')</div>'
        f'<div style="font-size:12px;color:{C_MUTED};margin-bottom:10px;">'
        f'Filtro: primo gol tra <b>{input_minute - tol}–{input_minute + tol}\'</b> '
        f'· Gol live al <b>{reference_minute}\'</b> · Dataset: <b>{n_total}</b> partite'
        f' · Primo gol: <b>{scorer_lbl}</b></div>',
        unsafe_allow_html=True,
    )

    trigger_data = generate_live_trigger(
        trigger_table,
        filtered_matches=trigger_matches,
        input_minute=input_minute,
    )
    _render_live_signal_card(trigger_data, scorer_lbl)

    col_t, col_h, col_a = st.columns(3)
    panels = [
        (col_t, "total", "📊 TOTALE", C_ORANGE),
        (col_h, "home", f"🏠 CASA SEGNA ({home_team[:12]})", C_BLUE2),
        (col_a, "away", f"✈️ TRASFERTA SEGNA ({away_team[:12]})", C_RED),
    ]
    for col, key, title, accent in panels:
        tbl = tables[key]["table"]
        cnt = tables[key]["count"]
        with col:
            st.markdown(
                f'<div style="background:#111827;border:1px solid #1f2937;border-radius:8px;'
                f'padding:12px 14px;height:100%;">'
                f'<div style="font-size:12px;font-weight:700;color:{accent};margin-bottom:6px;">'
                f'{title}</div>'
                f'<div style="font-size:10px;color:{C_MUTED};margin-bottom:8px;">'
                f'{cnt} partite nel campione</div>'
                f'{_render_post_goal_interval_rows(tbl)}'
                f'</div>',
                unsafe_allow_html=True,
            )


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN RENDER
# ══════════════════════════════════════════════════════════════════════════════

def _auto_refresh_live_timer():
    if st.session_state.get("live_timer_running"):
        time.sleep(LIVE_TIMER_REFRESH_SEC)
        tick_live_match_clock(LIVE_TIMER_REFRESH_SEC)
        st.rerun()


def _compute_live_bundle(filters: dict, extra: dict) -> dict | None:
    df, filtered, goal_events, match_ids = build_prematch_frame(filters)
    if filtered.empty:
        return None
    score_index = build_score_index(filtered, goal_events)
    r = analyze_live_state_v2(
        filtered,
        goal_events,
        extra["current_minute"],
        extra["home_score"],
        extra["away_score"],
        first_goal_minute=extra.get("first_goal_minute"),
        odds_home_ref=extra.get("odds_home_ref"),
        score_index=score_index,
    )
    if r.get("found", 0) == 0:
        return None
    return {
        "df": df,
        "filtered": filtered,
        "goal_events": goal_events,
        "match_ids": match_ids,
        "score_index": score_index,
        "r": r,
    }


def render():
    # ── Global CSS: zero top-padding, tight columns ──────────────────────────
    if not st.session_state.get("_live_css_loaded"):
        st.session_state._live_css_loaded = True
        st.html("""
    <style>
        /* ── Prematch-matching card/box classes ── */
        .pm-card {
            background: #111827;
            border: 1px solid #1f2937;
            border-radius: 8px;
            padding: 14px 6px;
            text-align: center;
            height: 100%;
        }
        .pm-label {
            font-size: 10px;
            color: #94a3b8;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 6px;
            font-weight: 600;
        }
        .pm-val {
            font-size: 26px;
            font-weight: 800;
            line-height: 1;
        }
        .pm-sub {
            font-size: 11px;
            color: #64748b;
            margin-top: 4px;
        }
        .pm-box {
            background: #111827;
            border: 1px solid #1f2937;
            border-radius: 8px;
            padding: 14px 16px;
            margin-bottom: 10px;
        }
        /* Layout */
        .main .block-container {
            padding-top: 0.5rem !important;
            padding-bottom: 0.5rem !important;
            max-width: 100% !important;
        }
        [data-testid="stDecoration"]    { display: none !important; }
        [data-testid="stToolbarActions"] { display: none !important; }
        div[data-testid="column"]       { padding: 2px 4px !important; }
        div[data-testid="stVerticalBlock"] > div { gap: 0.2rem !important; }
        .stPlotlyChart { margin-bottom: 0 !important; margin-top: 0 !important; }
        /* ── Equal-height cards in 5-column ROW 1 ── */
        [data-testid="stHorizontalBlock"] { align-items: stretch !important; }
        [data-testid="stHorizontalBlock"] [data-testid="stVerticalBlock"] { height: 100% !important; min-height: 100% !important; }
        [data-testid="stHorizontalBlock"] [data-testid="stMarkdownContainer"] { height: 100% !important; }
        [data-testid="stHorizontalBlock"] [data-testid="stMarkdownContainer"] > div { height: 100% !important; }
        @keyframes live-pulse-glow {
            0%, 100% { box-shadow: 0 0 8px #22c55e, 0 0 18px rgba(34,197,94,0.35); }
            50%      { box-shadow: 0 0 14px #22c55e, 0 0 28px rgba(34,197,94,0.6); }
        }
        .live-team-badge {
            border: 2px solid #334155;
            box-shadow: 0 2px 8px rgba(0,0,0,0.35);
            transition: box-shadow 0.3s ease, border-color 0.3s ease;
        }
        .live-team-badge-winning {
            border: 2px solid #22c55e !important;
            animation: live-pulse-glow 2.2s ease-in-out infinite;
        }
        .live-team-block-winning {
            box-shadow: 0 0 10px rgba(34,197,94,0.25);
            border-radius: 12px;
        }
    </style>
    """)

    # ── Sidebar — all inputs now come from filters.py _render_live_filters ──────
    filters = render_filter_sidebar("live")

    # Extract values from filter dict (set by new sidebar)
    current_minute  = max(1, int(filters.get("current_minute", 1)))
    current_second  = int(filters.get("current_second", 0))
    home_score      = int(filters.get("home_score", 0))
    away_score      = int(filters.get("away_score", 0))
    home_team       = filters.get("home_team") or "Casa"
    away_team       = filters.get("away_team") or "Trasferta"
    first_goal_min  = filters.get("first_goal_minute", None)
    odds_home_ref   = filters.get("odds_home", None)
    if odds_home_ref is not None and float(odds_home_ref) <= 1.0:
        odds_home_ref = None
    current_half    = "1° Tempo" if current_minute <= 45 else "2° Tempo"

    # ── Next-Over highlight: per-half goals (client request) ─────────
    # NOTE: only live total score is available, no half-time breakdown.
    # 1st half live -> all current goals belong to 1H, 2H = 0
    # 2nd half live -> 1H split unknown (no HT score) -> no highlight; 2H uses total
    _total_goals = home_score + away_score
    if current_minute <= 45:
        goals_1h = _total_goals      # all goals so far are in the 1st half
        goals_2h = 0                 # 2nd half not started
    else:
        goals_1h = None              # 1st half finished, exact split unknown -> no highlight
        goals_2h = _total_goals      # best available estimate for 2nd half

    def _next_over_idx(goals):
        # which column to highlight: 0=PROB(Over0.5), 1=Over1.5, 2=Over2.5, -1=none
        if goals is None:
            return -1
        if goals <= 0:
            return 0
        if goals == 1:
            return 1
        return 2

    _HL_BORDER = f"border:1px solid {C_GREEN2};border-radius:6px;background:rgba(34,197,94,0.10);"
    def _hl(col_idx, this_idx):
        return f'padding:3px 2px;{_HL_BORDER}' if col_idx == this_idx else 'padding:3px 2px;'
    if not filters.get("goals_time_valid", True):
        errs = filters.get("goal_time_errors", [])
        st.error(
            "⚠️ Minuto gol non valido: un gol è stato inserito **oltre** il minuto di gioco attuale "
            f"({current_minute}'). Correggi i dati nella sidebar."
        )
        for e in errs:
            st.warning(
                f"{e['label']} gol al **{e['display']}** ({e['team']}) — "
                f"non può essere dopo il {current_minute}'"
            )
        _auto_refresh_live_timer()
        return

    if not should_run_analysis(filters):
        st.markdown(f"""
        <div style="text-align:center;padding:60px 20px;color:{C_MUTED};">
            <div style="font-size:40px;margin-bottom:12px;">📺</div>
            <h3 style="color:{C_TEXT};">Analisi Live</h3>
            <p>Imposta i filtri in <b>Prematch</b> e clicca <b>Analizza</b>, oppure usa la barra laterale qui</p>
        </div>
        """, unsafe_allow_html=True)
        _auto_refresh_live_timer()
        return

    # ── Load & filter (cached) ──────────────────────────────────────────────
    live_extra = {
        "current_minute": current_minute,
        "current_second": current_second,
        "home_score": home_score,
        "away_score": away_score,
        "first_goal_minute": first_goal_min,
        "odds_home_ref": odds_home_ref,
    }
    with st.spinner("Ricerca scenari storici..."):
        bundle = load_live_data(
            filters,
            live_extra,
            lambda: _compute_live_bundle(filters, live_extra),
        )
    if not bundle:
        st.warning("Nessuna partita con i filtri selezionati.")
        _auto_refresh_live_timer()
        return

    filtered = bundle["filtered"]
    goal_events = bundle["goal_events"]
    match_ids = bundle["match_ids"]
    score_index = bundle["score_index"]
    r = bundle["r"]

    n             = r["found"]
    win           = r.get("used_window", 5)
    conf          = r.get("confidence", "?")
    current_state = r.get("current_state", f"{home_score}-{away_score}")
    is_post_goal  = bool(r.get("post_goal_mode"))

    # ═══════════════════════════════════════════════════════════════
    # SEZIONE 0 — HEADER (squadre, score, timer, evento live)
    # ═══════════════════════════════════════════════════════════════
    conf_color   = _color_val(n / 50 * 100)
    home_winning = home_score > away_score
    away_winning = away_score > home_score
    home_block_cls = "live-team-block-winning" if home_winning else ""
    away_block_cls = "live-team-block-winning" if away_winning else ""
    home_logo = _team_logo_html("home", home_team, home_winning)
    away_logo = _team_logo_html("away", away_team, away_winning)
    home_goals_html = _team_goals_timeline_html(filters, "Casa")
    away_goals_html = _team_goals_timeline_html(filters, "Trasferta")
    event_text, event_color, event_glow = _resolve_live_phase_event(
        current_minute, home_score, away_score, r, filters,
        is_post_goal, first_goal_min,
    )
    score_glow = _score_box_glow(home_score, away_score)
    st.html(f"""
    <div style="background:#0f172a;border:1px solid #1e293b;border-radius:12px;
                padding:14px 20px;margin-bottom:10px;">
        <div style="display:flex;align-items:center;justify-content:space-between;">

            <!-- LEFT: Home team -->
            <div class="{home_block_cls}" style="display:flex;align-items:center;gap:12px;flex:1;padding:6px 10px;">
                {home_logo}
                <div>
                    <div style="font-size:20px;font-weight:800;letter-spacing:1px;{_team_name_style(home_winning)}">
                        {home_team.upper()}
                    </div>
                    {home_goals_html}
                </div>
            </div>

            <!-- CENTER: Score + timer glow + evento live -->
            <div style="text-align:center;flex:1;">
                <div style="display:inline-block;background:#0d1117;border:1px solid #334155;
                            border-radius:10px;padding:8px 28px;box-shadow:{score_glow};">
                    <div style="font-size:32px;font-weight:900;color:#22c55e;line-height:1;
                                letter-spacing:4px;text-shadow:0 0 12px #22c55e;">
                        {home_score} &nbsp;-&nbsp; {away_score}
                    </div>
                    <div style="font-size:18px;font-weight:700;color:{event_color};margin-top:4px;
                                text-shadow:{event_glow};">
                        {current_minute:02d}:{current_second:02d}
                    </div>
                    <div style="font-size:11px;font-weight:700;color:{event_color};margin-top:4px;
                                letter-spacing:0.5px;text-shadow:{event_glow};">
                        {event_text}
                    </div>
                    <div style="font-size:10px;font-weight:600;color:#64748b;margin-top:3px;
                                letter-spacing:0.08em;">
                        {current_half.upper()}
                    </div>
                </div>
            </div>

            <!-- RIGHT: Away team + info badges -->
            <div style="display:flex;align-items:center;gap:12px;flex:1;justify-content:flex-end;">
                <div class="{away_block_cls}" style="display:flex;align-items:center;gap:12px;padding:6px 10px;">
                    <div style="text-align:right;">
                        <div style="font-size:20px;font-weight:800;letter-spacing:1px;{_team_name_style(away_winning)}">
                            {away_team.upper()}
                        </div>
                        {away_goals_html}
                    </div>
                    {away_logo}
                </div>
                <div style="display:flex;flex-direction:column;gap:4px;margin-left:8px;">
                    <div style="background:#1e293b;border:1px solid #334155;border-radius:12px;
                                padding:3px 12px;font-size:11px;font-weight:600;color:#cbd5e1;
                                text-align:center;white-space:nowrap;">
                        {n} PARTITE SIMILI
                    </div>
                    <div style="background:#1e293b;border:1px solid #334155;border-radius:12px;
                                padding:3px 12px;font-size:12px;font-weight:600;
                                color:{conf_color};text-align:center;white-space:nowrap;">
                        {current_state} &nbsp;|&nbsp; Conf: {conf}
                    </div>
                </div>
            </div>

        </div>
    </div>
    """)

    # ═══════════════════════════════════════════════════════════════
    # SEZIONE 0b — PROFILO PARTITA SIMILE (momentum atteso da campione)
    # ═══════════════════════════════════════════════════════════════
    render_similar_momentum_block(
        goal_events, match_ids, n,
        home_team, away_team,
        chart_key="live_similar_momentum",
        current_minute=current_minute,
        show_minute_marker=True,
        subtitle="Intensità attesa da gol storici · linea tratteggiata = minuto attuale",
    )

    # ═══════════════════════════════════════════════════════════════
    # SEZIONE 1 — KPI LIVE (azioni immediate: prossimo gol, BTTS, esito)
    # ═══════════════════════════════════════════════════════════════

    # ── compute all values first ───────────────────────────────────
    cs1h     = r.get("chi_segna_1h", {})
    n1h      = r.get("n_1h_sample", n)
    cs1h_max = max(cs1h.get("casa",0), cs1h.get("trasferta",0), cs1h.get("nessun_gol",0)) or 1

    cs2h     = r.get("chi_segna_2h", {})
    n2h      = r.get("n_2h_sample", n)
    cs2h_max = max(cs2h.get("casa",0), cs2h.get("trasferta",0), cs2h.get("nessun_gol",0)) or 1

    ng_h  = r.get("next_goal_home", 0)
    ng_a  = r.get("next_goal_away", 0)
    ng_n  = r.get("next_goal_none", 0)

    btts_si = r.get("btts_si", 0)
    btts_no = r.get("btts_no", 0)
    si_bw   = int(btts_si)

    f1    = r.get("final_home", 0)
    fx    = r.get("final_draw", 0)
    f2    = r.get("final_away", 0)
    f_max = max(f1, fx, f2) or 1

    # ── helper: CHI SEGNA bar ──────────────────────────────────────
    def _cs_bar(label, val, max_v, color):
        bw = int(val / max_v * 100) if max_v > 0 else 0
        return (
            f'<div style="display:flex;align-items:center;margin:3px 0;font-size:11px;">'
            f'<div style="width:60px;color:{C_MUTED};">{label}</div>'
            f'<div style="flex:1;background:#374151;height:5px;border-radius:3px;margin:0 4px;">'
            f'<div style="width:{bw}%;background:{color};height:100%;border-radius:3px;"></div></div>'
            f'<div style="width:34px;color:{color};font-weight:bold;text-align:right;">{val:.1f}%</div>'
            f'</div>'
        )

    # ── helper: ESITO col ──────────────────────────────────────────
    def _esito_col(label, val, max_v, color):
        bw = int(val / max_v * 100) if max_v > 0 else 0
        return (
            f'<div style="text-align:center;">'
            f'<div style="font-size:11px;font-weight:bold;color:{C_MUTED};">{label}</div>'
            f'<div style="font-size:20px;font-weight:bold;color:{color};line-height:1.1;">{val:.0f}%</div>'
            f'<div style="background:#374151;height:5px;border-radius:3px;margin-top:3px;">'
            f'<div style="width:{bw}%;background:{color};height:100%;border-radius:3px;"></div></div>'
            f'</div>'
        )

    # ── build card HTML strings ────────────────────────────────────
    _CARD_STYLE = "background:#111827;border:1px solid #1f2937;border-radius:8px;padding:10px 12px;height:100%;box-sizing:border-box;"

    card_1h = (
        f'<div style="{_CARD_STYLE}border-top:2px solid #3b82f6;">'
        f'<div style="font-size:14px;font-weight:bold;color:{C_TEXT};text-align:center;margin-bottom:8px;">1° TEMPO (0\' — 45\')</div>'
        f'<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:6px;text-align:center;margin-bottom:8px;">'
        f'<div style="{_hl(_next_over_idx(goals_1h), 0)}">'
        f'<div style="font-size:11px;color:{C_MUTED};margin-bottom:2px;">PROB. ALMENO 1 GOL</div>'
        f'<div style="font-size:20px;font-weight:bold;color:{C_GREEN2};">{r.get("prob_1h_goal",0):.0f}%</div>'
        f'<div style="font-size:12px;color:{C_MUTED2};">{r.get("n_1h_goal_count",0)}/{n1h}</div></div>'
        f'<div style="{_hl(_next_over_idx(goals_1h), 1)}">'
        f'<div style="font-size:11px;color:{C_MUTED};margin-bottom:2px;">OVER 1.5</div>'
        f'<div style="font-size:20px;font-weight:bold;color:{C_TEXT};">{r.get("over_15_1h",0):.1f}%</div>'
        f'<div style="font-size:12px;color:{C_MUTED2};">{r.get("n_over15_1h",0)}/{n1h}</div></div>'
        f'<div style="{_hl(_next_over_idx(goals_1h), 2)}">'
        f'<div style="font-size:11px;color:{C_MUTED};margin-bottom:2px;">OVER 2.5</div>'
        f'<div style="font-size:20px;font-weight:bold;color:{C_TEXT};">{r.get("over_25_1h",0):.1f}%</div>'
        f'<div style="font-size:12px;color:{C_MUTED2};">{r.get("n_over25_1h",0)}/{n1h}</div></div>'
        f'</div>'
        f'<div style="border-top:1px solid #1f2937;padding-top:6px;">'
        f'<div style="font-size:11px;color:{C_MUTED};font-weight:600;margin-bottom:4px;">CHI SEGNA?</div>'
        f'{_cs_bar("Casa", cs1h.get("casa",0), cs1h_max, C_GREEN2)}'
        f'{_cs_bar("Trasferta", cs1h.get("trasferta",0), cs1h_max, C_YELLOW)}'
        f'{_cs_bar("Nessun gol", cs1h.get("nessun_gol",0), cs1h_max, C_MUTED)}'
        f'</div></div>'
    )

    card_2h = (
        f'<div style="{_CARD_STYLE}border-top:2px solid #22c55e;">'
        f'<div style="font-size:14px;font-weight:bold;color:{C_TEXT};text-align:center;margin-bottom:8px;">2° TEMPO (46\' — 90\'+)</div>'
        f'<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:6px;text-align:center;margin-bottom:8px;">'
        f'<div style="{_hl(_next_over_idx(goals_2h), 0)}">'
        f'<div style="font-size:11px;color:{C_MUTED};margin-bottom:2px;">PROB. ALMENO 1 GOL</div>'
        f'<div style="font-size:20px;font-weight:bold;color:{C_GREEN2};">{r.get("prob_2h_goal",0):.0f}%</div>'
        f'<div style="font-size:12px;color:{C_MUTED2};">{r.get("n_2h_goal_count",0)}/{n2h}</div></div>'
        f'<div style="{_hl(_next_over_idx(goals_2h), 1)}">'
        f'<div style="font-size:11px;color:{C_MUTED};margin-bottom:2px;">OVER 1.5</div>'
        f'<div style="font-size:20px;font-weight:bold;color:{C_TEXT};">{r.get("over_15_2h",0):.1f}%</div>'
        f'<div style="font-size:12px;color:{C_MUTED2};">{r.get("n_over15_2h",0)}/{n2h}</div></div>'
        f'<div style="{_hl(_next_over_idx(goals_2h), 2)}">'
        f'<div style="font-size:11px;color:{C_MUTED};margin-bottom:2px;">OVER 2.5</div>'
        f'<div style="font-size:20px;font-weight:bold;color:{C_TEXT};">{r.get("over_25_2h",0):.1f}%</div>'
        f'<div style="font-size:12px;color:{C_MUTED2};">{r.get("n_over25_2h",0)}/{n2h}</div></div>'
        f'</div>'
        f'<div style="border-top:1px solid #1f2937;padding-top:6px;">'
        f'<div style="font-size:11px;color:{C_MUTED};font-weight:600;margin-bottom:4px;">CHI SEGNA?</div>'
        f'{_cs_bar("Casa", cs2h.get("casa",0), cs2h_max, C_GREEN2)}'
        f'{_cs_bar("Trasferta", cs2h.get("trasferta",0), cs2h_max, C_YELLOW)}'
        f'{_cs_bar("Nessun gol", cs2h.get("nessun_gol",0), cs2h_max, C_MUTED)}'
        f'</div></div>'
    )

    card_ng = (
        f'<div style="{_CARD_STYLE}display:flex;flex-direction:column;justify-content:center;">'
        f'<div style="font-size:14px;font-weight:bold;color:{C_TEXT};text-align:center;">NEXT GOAL</div>'
        f'<div style="font-size:11px;color:{C_MUTED};text-align:center;margin-bottom:6px;">Chi segna prossimo?</div>'
        f'<div style="display:flex;justify-content:space-around;margin-top:4px;">'
        f'<div style="text-align:center;"><div style="font-size:12px;color:{C_MUTED};">{home_team[:6]}</div>'
        f'<div style="font-size:22px;font-weight:bold;color:{C_GREEN2};">{ng_h:.0f}%</div></div>'
        f'<div style="text-align:center;"><div style="font-size:12px;color:{C_MUTED};">Nessuno</div>'
        f'<div style="font-size:22px;font-weight:bold;color:{C_MUTED};">{ng_n:.0f}%</div></div>'
        f'<div style="text-align:center;"><div style="font-size:12px;color:{C_MUTED};">{away_team[:6]}</div>'
        f'<div style="font-size:22px;font-weight:bold;color:{C_YELLOW};">{ng_a:.0f}%</div></div>'
        f'</div></div>'
    )

    card_btts = (
        f'<div style="{_CARD_STYLE}display:flex;flex-direction:column;justify-content:center;">'
        f'<div style="font-size:14px;font-weight:bold;color:{C_TEXT};text-align:center;margin-bottom:6px;">⚽ BTTS LIVE</div>'
        f'<div style="display:flex;justify-content:space-around;margin-bottom:6px;">'
        f'<div style="text-align:center;"><div style="font-size:11px;color:{C_MUTED};">Si</div>'
        f'<div style="font-size:22px;font-weight:bold;color:{C_GREEN2};">{btts_si:.0f}%</div></div>'
        f'<div style="text-align:center;"><div style="font-size:11px;color:{C_MUTED};">No</div>'
        f'<div style="font-size:22px;font-weight:bold;color:{C_RED};">{btts_no:.0f}%</div></div>'
        f'</div>'
        f'<div style="background:#374151;height:6px;border-radius:3px;overflow:hidden;">'
        f'<div style="width:{si_bw}%;background:{C_GREEN2};height:100%;border-radius:3px;float:left;"></div>'
        f'</div></div>'
    )

    card_esito = (
        f'<div style="{_CARD_STYLE}display:flex;flex-direction:column;justify-content:center;">'
        f'<div style="font-size:14px;font-weight:bold;color:{C_TEXT};text-align:center;margin-bottom:8px;">📊 ESITO FINALE LIVE</div>'
        f'<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:6px;">'
        f'{_esito_col("1", f1, f_max, C_GREEN2)}'
        f'{_esito_col("X", fx, f_max, C_YELLOW)}'
        f'{_esito_col("2", f2, f_max, C_RED)}'
        f'</div></div>'
    )

    st.html(f"""
    <div style="display:flex;gap:8px;align-items:stretch;margin-bottom:8px;">
        <div style="flex:1;min-width:0;">{card_ng}</div>
        <div style="flex:1;min-width:0;">{card_btts}</div>
        <div style="flex:1;min-width:0;">{card_esito}</div>
    </div>
    """)

    # ═══════════════════════════════════════════════════════════════
    # SEZIONE 2 — STATISTICHE PER TEMPO (1° e 2° tempo)
    # ═══════════════════════════════════════════════════════════════
    st.html(f"""
    <div style="display:flex;gap:8px;align-items:stretch;margin-bottom:8px;">
        <div style="flex:1;min-width:0;">{card_1h}</div>
        <div style="flex:1;min-width:0;">{card_2h}</div>
    </div>
    """)

    live_view = st.radio(
        "Dettaglio live",
        ["Essenziale", "Grafici & Scenari"],
        horizontal=True,
        key="live_view",
        label_visibility="collapsed",
    )

    if live_view == "Grafici & Scenari":
        import plotly.graph_objects as go

        # ═══════════════════════════════════════════════════════════════
        # SEZIONE 2b — POST GOAL ANALYSIS (dataset unico, fasce future)
        # ═══════════════════════════════════════════════════════════════
        _ref_goal_min = first_goal_min
        if _ref_goal_min is None and filters.get("valid_goals"):
            _ref_goal_min = filters["valid_goals"][0][0]
        if _ref_goal_min is not None and (home_score + away_score) >= 1:
            _render_post_goal_analysis_block(
                filtered, int(_ref_goal_min), int(current_minute),
                home_team, away_team,
                first_goal_team=filters.get("first_goal_team"),
            )

        # ═══════════════════════════════════════════════════════════════
        # SEZIONE 2c — ESITO FINALE DOPO IL PRIMO GOL
        # ═══════════════════════════════════════════════════════════════
        _fgo_min = first_goal_min
        if _fgo_min is None and filters.get("valid_goals"):
            _fgo_min = filters["valid_goals"][0][0]
        render_first_goal_outcome_block(
            filtered,
            goal_events,
            live_minute=int(_fgo_min) if _fgo_min is not None else None,
            live_team=filters.get("first_goal_team"),
        )

        # ═══════════════════════════════════════════════════════════════
        # SEZIONE 3 — PROIEZIONE LIVE (intervalli dinamici 5/10/15 min)
        # ═══════════════════════════════════════════════════════════════
        _render_live_projection_block(
            filtered, filters, goal_events, score_index,
            int(current_minute), home_score, away_score,
        )

        # ═══════════════════════════════════════════════════════════════
        # SEZIONE 4 — DISTRIBUZIONI GOL (grafici per tempo)
        # ROW 2 — 4 CHARTS
        # Order: DIST GOL 1H | RISULTATI 1H | DIST GOL 2H | RISULTATI 2H
        # Blue = 1° tempo, Green = 2° tempo (matches panel colors above)
        # ═══════════════════════════════════════════════════════════════
        rc1, rc2, rc3, rc4 = st.columns(4)

        # Dynamic: only future buckets
        future_bkts  = _future_buckets(current_minute)
        timing_data  = r.get("future_timeframes", {})

        # ── rc1: DISTRIBUZIONE GOL 1° TEMPO — only future 1H buckets (Point 2) ──
        with rc1:
            full_timing = r.get("goal_distribution", timing_data)
            h1_keys = [b for b in H1_BUCKETS if BUCKET_END.get(b, 999) >= current_minute]
            if not h1_keys:
                st.markdown(
                    f'<div style="background:#111827;border:1px solid #1f2937;border-radius:8px;'
                    f'padding:0;height:175px;display:flex;align-items:center;justify-content:center;">'
                    f'<div style="font-size:12px;color:#64748b;text-align:center;">'
                    f'<div style="font-size:14px;font-weight:700;color:#3b82f6;margin-bottom:6px;">DISTRIBUZIONE GOL 1° TEMPO</div>'
                    f'1° Tempo completato</div></div>',
                    unsafe_allow_html=True,
                )
            else:
                h1_vals = [full_timing.get(k, 0) for k in h1_keys]
                h1_max  = max(h1_vals) if max(h1_vals) > 0 else 1
                h1_text = [f"{v:.1f}%" if v > 0 else "" for v in h1_vals]
                fig = go.Figure(go.Bar(
                    x=h1_keys, y=h1_vals,
                    marker_color="#3b82f6",
                    text=h1_text,
                    textposition="outside",
                    textfont=dict(size=12, color="#f1f5f9"),
                    cliponaxis=False,
                ))
                fig.update_layout(
                    **_LAYOUT_BASE,
                    title=dict(text="DISTRIBUZIONE GOL 1° TEMPO",
                               font=dict(color="#3b82f6", size=14, family="Arial Black"), x=0),
                    height=175,
                    bargap=0.25,
                    xaxis=dict(showgrid=False, zeroline=False,
                               tickfont=dict(color="#94a3b8", size=11)),
                    yaxis=dict(visible=False, range=[0, h1_max * 1.4]),
                )
                st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

        # ── rc2: RISULTATI 1° TEMPO PIÙ COMUNI — pure HTML bars ─
        with rc2:
            ht_res = r.get("top_ht_results", [])
            items2 = [(x[0], round(x[1] / n * 100, 1)) for x in ht_res[:5]] if ht_res else [("N/A", 0)]
            max_v2 = max(v for _, v in items2) if items2 else 1
            rows2 = ""
            for lbl, val in items2:
                bw = int(val / max_v2 * 100) if max_v2 > 0 else 0
                rows2 += f'<div style="display:flex;align-items:center;margin:5px 0;gap:6px;"><div style="width:28px;font-size:11px;font-weight:700;color:#f1f5f9;text-align:right;flex-shrink:0;">{lbl}</div><div style="flex:1;background:#1e293b;border-radius:3px;height:14px;"><div style="width:{bw}%;background:#3b82f6;height:100%;border-radius:3px;"></div></div><div style="width:38px;font-size:12px;color:#f1f5f9;flex-shrink:0;">{val:.1f}%</div></div>'
            html2 = f'<div style="padding:4px 2px;"><div style="font-size:14px;font-weight:700;color:#3b82f6;text-transform:uppercase;letter-spacing:0.4px;margin-bottom:8px;">RISULTATI 1&#176; TEMPO PI&#217; COMUNI</div>{rows2}</div>'
            st.markdown(html2, unsafe_allow_html=True)

        # ── rc3: DISTRIBUZIONE GOL 2° TEMPO — only future 2H buckets (Point 2) ─────
        with rc3:
            h2_keys = [b for b in H2_BUCKETS if BUCKET_END.get(b, 999) >= current_minute]
            if not h2_keys:
                st.markdown(
                    f'<div style="background:#111827;border:1px solid #1f2937;border-radius:8px;'
                    f'padding:0;height:175px;display:flex;align-items:center;justify-content:center;">'
                    f'<div style="font-size:12px;color:#64748b;text-align:center;">'
                    f'<div style="font-size:14px;font-weight:700;color:#22c55e;margin-bottom:6px;">DISTRIBUZIONE GOL 2° TEMPO</div>'
                    f'Nessun timeframe futuro</div></div>',
                    unsafe_allow_html=True,
                )
            else:
                h2_vals = [full_timing.get(k, 0) for k in h2_keys]
                h2_max  = max(h2_vals) if max(h2_vals) > 0 else 1
                h2_text = [f"{v:.1f}%" if v > 0 else "" for v in h2_vals]
                fig = go.Figure(go.Bar(
                    x=h2_keys, y=h2_vals,
                    marker_color="#22c55e",
                    text=h2_text,
                    textposition="outside",
                    textfont=dict(size=12, color="#f1f5f9"),
                    cliponaxis=False,
                ))
                fig.update_layout(
                    **_LAYOUT_BASE,
                    title=dict(text="DISTRIBUZIONE GOL 2° TEMPO",
                               font=dict(color="#22c55e", size=14, family="Arial Black"), x=0),
                    height=175,
                    bargap=0.25,
                    xaxis=dict(showgrid=False, zeroline=False,
                               tickfont=dict(color="#94a3b8", size=11)),
                    yaxis=dict(visible=False, range=[0, h2_max * 1.4]),
                )
                st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

        # ── rc4: RISULTATI 2° TEMPO PIÙ COMUNI — pure HTML bars ─
        with rc4:
            ft_res = r.get("top_ft_results", [])
            items4 = [(x[0], round(x[1] / n * 100, 1)) for x in ft_res[:5]] if ft_res else [("N/A", 0)]
            max_v4 = max(v for _, v in items4) if items4 else 1
            rows4 = ""
            for lbl, val in items4:
                bw = int(val / max_v4 * 100) if max_v4 > 0 else 0
                rows4 += f'<div style="display:flex;align-items:center;margin:5px 0;gap:6px;"><div style="width:28px;font-size:11px;font-weight:700;color:#f1f5f9;text-align:right;flex-shrink:0;">{lbl}</div><div style="flex:1;background:#1e293b;border-radius:3px;height:14px;"><div style="width:{bw}%;background:#22c55e;height:100%;border-radius:3px;"></div></div><div style="width:38px;font-size:12px;color:#f1f5f9;flex-shrink:0;">{val:.1f}%</div></div>'
            html4 = f'<div style="padding:4px 2px;"><div style="font-size:14px;font-weight:700;color:#22c55e;text-transform:uppercase;letter-spacing:0.4px;margin-bottom:8px;">RISULTATI 2&#176; TEMPO PI&#217; COMUNI</div>{rows4}</div>'
            st.markdown(html4, unsafe_allow_html=True)

        # ═══════════════════════════════════════════════════════════════
        # SEZIONE 5 — SCENARI VANTAGGIO / SVANTAGGIO (blocchi 4-5)
        # ═══════════════════════════════════════════════════════════════
        r4top1, r4top2 = st.columns(2)

        # Block 4 — Advantage scenario (home leading) — Image 1 style bars
        with r4top1:
            if home_score > away_score:
                score_label = f"({home_score}-{away_score})"
                title4b = f"SE {home_team.upper()[:8]} IN VANTAGGIO {score_label}"
                sub4b   = "Cosa succede più spesso?"
                items4b = [
                    ("Raddoppia il vantaggio", r.get("home_doubles_pct", 0),   C_GREEN2),
                    ("Subisce pareggio",       r.get("home_equalises_pct", 0), C_YELLOW),
                    ("Nessun altro gol",       r.get("home_concedes_pct", 0),  C_MUTED),
                ]
            else:
                title4b = "SCENARIO VANTAGGIO"
                sub4b   = "N/A per il punteggio attuale"
                items4b = []

            if items4b:
                max_v4b = max(v for _, v, _ in items4b) or 1

                def _b4_bar(label, val, col, max_v):
                    bw   = int(val / max_v * 100) if max_v > 0 else 0
                    fire = " 🔥" if val == max_v and max_v > 0 else ""
                    return (
                        f'<div style="display:flex;align-items:center;margin:8px 0;">'
                        f'<div style="flex:1;font-size:11px;color:{C_TEXT};white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{label}</div>'
                        f'<div style="width:80px;background:#1e293b;height:10px;border-radius:5px;margin:0 8px;flex-shrink:0;">'
                        f'<div style="width:{bw}%;background:{col};height:100%;border-radius:5px;"></div>'
                        f'</div>'
                        f'<div style="width:42px;font-size:12px;font-weight:700;color:{col};text-align:right;white-space:nowrap;">'
                        f'{val:.0f}%{fire}</div>'
                        f'</div>'
                    )

                rows4b = "".join(_b4_bar(lab, val, col, max_v4b) for lab, val, col in items4b)
            else:
                rows4b = f'<div style="font-size:11px;color:{C_MUTED};margin-top:10px;">{sub4b}</div>'

            st.markdown(f"""
            {_card_start("min-height:160px;")}
            {_section_header("4", title4b)}
            {f'<div style="font-size:12px;color:{C_MUTED};margin-bottom:6px;">{sub4b}</div>' if items4b else ''}
            {rows4b}
            {_CARD_END}
            """, unsafe_allow_html=True)

        # Block 5 — Away disadvantage scenario
        with r4top2:
            if away_score > home_score:
                title5b = f"SE {away_team.upper()[:10]} IN VANTAGGIO"
                items5b = [
                    ("Rimonta (almeno pari)", r.get("away_comeback_pct", 0), C_GREEN2),
                    ("Non segna più",         r.get("away_no_more_pct", 0), C_RED),
                    ("Segna ma perde",        r.get("away_scores_loses_pct", 0), C_YELLOW),
                ]
            else:
                title5b = "SCENARIO SVANTAGGIO"
                items5b = []

            rows5b = "".join(
                f'<div style="background:{col}22;border-radius:4px;padding:4px 8px;margin:4px 0;'
                f'font-size:11px;display:flex;justify-content:space-between;">'
                f'<span style="color:{C_TEXT}">{lab}</span>'
                f'<span style="font-weight:bold;color:{col}">{val:.0f}%</span></div>'
                for lab, val, col in items5b
            ) if items5b else f'<div style="font-size:11px;color:{C_MUTED};margin-top:10px;">N/A per il punteggio attuale</div>'

            st.markdown(f"""
            {_card_start("min-height:160px;")}
            {_section_header("5", title5b)}
            {rows5b}
            {_CARD_END}
            """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # ═══════════════════════════════════════════════════════════════
        # SEZIONE 6 — PATTERN ATTIVI
        # ═══════════════════════════════════════════════════════════════
        patterns = r.get("patterns", [])
        pat_rows = ""
        for p in patterns:
            status_color = C_GREEN2 if p["status"] == "ATTIVO" else C_YELLOW
            pat_rows += (
                f'<div style="font-size:11px;display:flex;justify-content:space-between;margin:3px 0;">'
                f'<span>✅ {p["label"]} ({p["pct"]:.0f}%)</span>'
                f'<span style="color:{status_color};font-weight:bold;">{p["status"]}</span></div>'
            )
        if not patterns:
            pat_rows = f'<div style="font-size:11px;color:{C_MUTED};">Nessun pattern rilevante</div>'
        total_p = len(patterns)
        st.markdown(f"""
        {_card_start()}
        {_section_header("14", "PATTERN ATTIVI", C_TEXT)}
        {_sub("Pattern rilevati in questo match")}
        {pat_rows}
        <div style="font-size:11px;color:{C_MUTED};margin-top:4px;">{total_p} pattern attivi su 3 rilevati</div>
        {_CARD_END}
        """, unsafe_allow_html=True)

        # ═══════════════════════════════════════════════════════════════
        # SEZIONE 7 — ROI SIMULAZIONE LIVE
        # ═══════════════════════════════════════════════════════════════
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(
            f'<div style="background:#111827;border:1px solid #1f2937;border-radius:8px;'
            f'padding:10px 16px;margin-bottom:8px;">'
            f'<div style="display:flex;align-items:center;gap:8px;">'
            f'<span style="font-size:16px;">📊</span>'
            f'<span style="font-size:16px;font-weight:800;color:{C_TEXT};letter-spacing:1px;">'
            f'ROI SIMULAZIONE LIVE</span>'
            f'</div>'
            f'<div style="font-size:12px;color:{C_MUTED};margin-top:4px;">'
            f'Minuto: {current_minute}\' &nbsp;•&nbsp; Risultato: {home_score}-{away_score}'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        with st.spinner("Calcolo ROI simulazione..."):
            roi_data, roi_n = calc_live_roi_simulation(
                filtered, goal_events,
                current_minute, home_score, away_score,
                score_index=score_index,
            )

        if not roi_data or roi_n == 0:
            st.warning("Nessuna partita sufficiente per la simulazione ROI.")
        else:
            st.caption(
                f"Campione: {roi_n} partite simili ({home_score}-{away_score} al {current_minute}') "
                f"— Over su gol futuri, 1X2/BTTS su risultato finale"
            )
            render_roi_dashboard(roi_data)

        _auto_refresh_live_timer()