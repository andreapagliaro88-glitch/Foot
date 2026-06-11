"""
screens/match_timeline.py — Full Story: timeline gol minuto per minuto
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database import get_all_matches
from filters import render_filter_sidebar, apply_filters, should_run_analysis
from match_timeline import (
    ZONE_LABELS,
    build_intensity_zones,
    build_split_timeline,
    build_timeline,
    calculate_first_goal_avg,
    calculate_timeline_kpi,
    detect_key_moments,
    generate_timeline_insight,
)
from utils import team_logo_html

C_BG = "#111827"
C_BORDER = "#1f2937"
C_TEXT = "#f1f5f9"
C_MUTED = "#94a3b8"
C_MUTED2 = "#64748b"
C_CYAN = "#38bdf8"
C_GREEN = "#22c55e"
C_RED = "#ef4444"
C_HOME = "#3b82f6"
C_AWAY = "#f59e0b"

_PLOTLY_LAYOUT = dict(
    paper_bgcolor=C_BG,
    plot_bgcolor=C_BG,
    font=dict(color=C_MUTED, size=11),
    margin=dict(l=40, r=20, t=44, b=40),
)


def _inject_styles():
    st.html(f"""
    <style>
        .mt-box {{
            background:{C_BG}; border:1px solid {C_BORDER}; border-radius:8px;
            padding:16px; margin-bottom:16px;
        }}
        .mt-card {{
            background:{C_BG}; border:1px solid {C_BORDER}; border-radius:8px;
            padding:16px; text-align:center; height:100%;
        }}
        .mt-lbl {{
            font-size:11px; color:{C_MUTED2}; text-transform:uppercase;
            letter-spacing:1px; margin-bottom:8px;
        }}
        .mt-val {{ font-size:28px; font-weight:700; color:{C_TEXT}; }}
        div[data-testid="stPlotlyChart"] {{
            background:{C_BG}; border:1px solid {C_BORDER};
            border-radius:8px; padding:2px;
        }}
    </style>
    """)


def _metric_card(label: str, value: str, color: str = C_TEXT) -> str:
    return (
        f'<div class="mt-card">'
        f'<div class="mt-lbl">{label}</div>'
        f'<div class="mt-val" style="color:{color};">{value}</div>'
        f'</div>'
    )


def _render_match_header(
    home: str | None,
    away: str | None,
    league: str,
    n_matches: int,
):
    if home and away and home not in ("Tutte le squadre", "") and away not in ("Tutte le squadre", ""):
        st.html(f"""
        <div class="mt-box" style="display:flex;align-items:center;justify-content:space-between;gap:16px;">
            <div style="flex:1;text-align:center;">{team_logo_html(home, size=56)}</div>
            <div style="flex:1.2;text-align:center;">
                <div style="font-size:11px;color:{C_MUTED2};letter-spacing:1px;">TIMELINE MATCH</div>
                <div style="font-size:22px;font-weight:800;color:{C_CYAN};margin:6px 0;">FULL STORY</div>
                <div style="font-size:12px;color:{C_MUTED};">{league} · {n_matches} partite</div>
            </div>
            <div style="flex:1;text-align:center;">{team_logo_html(away, size=56)}</div>
        </div>
        """)
    else:
        st.html(f"""
        <div class="mt-box">
            <div style="font-size:11px;color:{C_MUTED2};">TIMELINE MATCH</div>
            <div style="font-size:20px;font-weight:800;color:{C_CYAN};">FULL STORY</div>
            <div style="font-size:12px;color:{C_MUTED};margin-top:6px;">
                {league} · {n_matches} partite analizzate
            </div>
        </div>
        """)


def _plot_timeline_bars(timeline: dict[int, int]) -> go.Figure:
    minutes = list(range(1, 91))
    values = [timeline.get(m, 0) for m in minutes]
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=minutes,
        y=values,
        marker_color=[C_CYAN if v > 0 else "#1f2937" for v in values],
        marker_line_width=0,
        hovertemplate="Min %{x}<br>Gol: %{y}<extra></extra>",
    ))
    fig.update_layout(
        **_PLOTLY_LAYOUT,
        height=300,
        title=dict(text="Distribuzione gol per minuto", font=dict(color=C_TEXT, size=13)),
        xaxis=dict(title="Minuto", dtick=15, gridcolor=C_BORDER, zeroline=False),
        yaxis=dict(title="Gol", gridcolor=C_BORDER, zeroline=False),
        bargap=0.05,
    )
    return fig


def _plot_event_strip(home_tl: dict[int, int], away_tl: dict[int, int]) -> go.Figure:
    fig = go.Figure()
    minutes = list(range(1, 91))

    home_x, home_sz = [], []
    away_x, away_sz = [], []
    for m in minutes:
        if home_tl.get(m, 0):
            home_x.append(m)
            home_sz.append(8 + home_tl[m] * 3)
        if away_tl.get(m, 0):
            away_x.append(m)
            away_sz.append(8 + away_tl[m] * 3)

    fig.add_hline(y=0.5, line_width=8, line_color="#1f2937")
    for tick in [0, 15, 30, 45, 60, 75, 90]:
        fig.add_vline(x=tick if tick else 1, line_width=1, line_color="#334155", line_dash="dot")

    if home_x:
        fig.add_trace(go.Scatter(
            x=home_x, y=[1.0] * len(home_x), mode="markers",
            name="Casa",
            marker=dict(size=home_sz, color=C_HOME, symbol="circle", line=dict(width=1, color="#fff")),
            hovertemplate="Min %{x}<br>Casa<extra></extra>",
        ))
    if away_x:
        fig.add_trace(go.Scatter(
            x=away_x, y=[0.0] * len(away_x), mode="markers",
            name="Trasferta",
            marker=dict(size=away_sz, color=C_AWAY, symbol="circle", line=dict(width=1, color="#fff")),
            hovertemplate="Min %{x}<br>Trasferta<extra></extra>",
        ))

    fig.update_layout(
        **_PLOTLY_LAYOUT,
        height=180,
        title=dict(text="Timeline visiva 0 → 90", font=dict(color=C_TEXT, size=13)),
        xaxis=dict(range=[0, 91], dtick=15, title="Minuto", gridcolor=C_BORDER),
        yaxis=dict(
            range=[-0.5, 1.5], showticklabels=True,
            tickvals=[0, 1], ticktext=["Trasferta", "Casa"],
            gridcolor=C_BORDER,
        ),
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
    )
    return fig


def _plot_zone_heatmap(zones: dict[str, int]) -> go.Figure:
    labels = list(ZONE_LABELS)
    values = [zones.get(z, 0) for z in labels]
    max_v = max(values) if values and max(values) > 0 else 1
    fig = go.Figure(data=go.Heatmap(
        z=[values],
        x=labels,
        y=["Gol"],
        colorscale=[
            [0, "#1f2937"],
            [0.25, "#1e3a5f"],
            [0.5, "#2563eb"],
            [0.75, "#38bdf8"],
            [1.0, "#22c55e"],
        ],
        zmin=0,
        zmax=max_v,
        hovertemplate="%{x}: %{z} gol<extra></extra>",
        showscale=False,
    ))
    for i, (label, val) in enumerate(zip(labels, values)):
        fig.add_annotation(
            x=label, y=0, text=str(val),
            showarrow=False, font=dict(color=C_TEXT, size=12),
        )
    fig.update_layout(
        **_PLOTLY_LAYOUT,
        height=160,
        title=dict(text="Heatmap intensità per fascia", font=dict(color=C_TEXT, size=13)),
        xaxis=dict(side="bottom"),
        yaxis=dict(showticklabels=False),
    )
    return fig


def _plot_zone_bars(zones: dict[str, int]) -> go.Figure:
    labels = list(ZONE_LABELS)
    values = [zones.get(z, 0) for z in labels]
    colors = [C_GREEN if v == max(values) and v > 0 else C_CYAN for v in values]
    fig = go.Figure(go.Bar(x=labels, y=values, marker_color=colors))
    fig.update_layout(
        **_PLOTLY_LAYOUT,
        height=260,
        title=dict(text="Gol per fascia di gioco", font=dict(color=C_TEXT, size=13)),
        xaxis=dict(title="Fascia"),
        yaxis=dict(title="Gol", gridcolor=C_BORDER),
    )
    return fig


def render():
    _inject_styles()

    filters = render_filter_sidebar("timeline")
    if not should_run_analysis(filters):
        st.info("👈 Imposta i filtri e clicca **ANALIZZA** per visualizzare la timeline.")
        return

    rows = get_all_matches()
    if not rows:
        st.warning("⚠️ Nessun dato nel database.")
        return

    df = pd.DataFrame(rows)
    filtered = apply_filters(df, filters)
    if filtered.empty:
        st.warning("🔍 Nessuna partita con i filtri selezionati.")
        return

    home = filters.get("home_team", "")
    away = filters.get("away_team", "")
    league = filters.get("league", "Tutte le competizioni")
    if league in ("Tutti", "Tutte", "Tutte le competizioni"):
        league = "Tutte le competizioni"

    timeline = build_timeline(filtered)
    home_tl, away_tl = build_split_timeline(filtered)
    zones = build_intensity_zones(timeline)
    kpi = calculate_timeline_kpi(timeline)
    moments = detect_key_moments(zones)
    first_goal_avg = calculate_first_goal_avg(filtered)
    insight = generate_timeline_insight(kpi, moments)

    if kpi["total_goals"] == 0:
        st.warning(
            "Nessun gol con timing disponibile nel campione filtrato. "
            "Verifica che i CSV importati includano `home_team_goal_timings` / `away_team_goal_timings`."
        )
        return

    _render_match_header(home, away, league, len(filtered))

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.html(_metric_card("⏱️ Primo gol medio", f"{first_goal_avg}'", C_CYAN))
    with c2:
        st.html(_metric_card("1T %", f"{kpi['first_half_pct']}%"))
    with c3:
        st.html(_metric_card("2T %", f"{kpi['second_half_pct']}%"))
    with c4:
        st.html(_metric_card("🔥 Intensità picco", f"{kpi['intensity']}%", C_GREEN))

    st.plotly_chart(_plot_event_strip(home_tl, away_tl), use_container_width=True)
    st.plotly_chart(_plot_timeline_bars(timeline), use_container_width=True)

    h_left, h_right = st.columns(2)
    with h_left:
        st.plotly_chart(_plot_zone_heatmap(zones), use_container_width=True)
    with h_right:
        st.plotly_chart(_plot_zone_bars(zones), use_container_width=True)

    st.markdown("### ⚡ Momenti chiave")
    st.html(f"""
    <div class="mt-box">
        <div style="color:{C_GREEN};font-size:14px;font-weight:700;margin-bottom:8px;">
            🔥 Picco gol: {moments['peak']} ({zones.get(moments['peak'], 0)} gol)
        </div>
        <div style="color:{C_RED};font-size:14px;font-weight:700;">
            ❄️ Zona calma: {moments['low']} ({zones.get(moments['low'], 0)} gol)
        </div>
    </div>
    """)

    c_a, c_b, c_c = st.columns(3)
    with c_a:
        st.html(_metric_card("Minuto medio gol", f"{kpi['avg_minute']}'", C_CYAN))
    with c_b:
        st.html(_metric_card("Gol totali", str(kpi["total_goals"])))
    with c_c:
        st.html(_metric_card("Partite", str(len(filtered))))

    st.markdown("### 🧠 Insight finale")
    st.html(f"""
    <div class="mt-box" style="border-color:#334155;">
        <div style="font-size:15px;font-weight:700;color:{C_TEXT};">{insight}</div>
        <div style="font-size:12px;color:{C_MUTED};margin-top:8px;">
            Basato su {kpi['total_goals']} gol in {len(filtered)} partite filtrate.
        </div>
    </div>
    """)
