"""
pages/prematch.py — Prematch Analysis screen (Dark Redesign)
"""

import streamlit as st
import pandas as pd
import io
import sys
import os
import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database import get_goal_events_for_matches, get_last_h2h_matches, get_matches_dataframe
from filters import render_filter_sidebar, apply_filters, should_run_analysis
from screen_cache import load_prematch_data, build_prematch_frame
from calculations import (
    analyze_matches, enrich_with_goal_events, BUCKETS,
    calculate_over_trend_by_season, calculate_interval_distribution_1h,
    calculate_interval_distribution_2h, calculate_at_least_one_goal_half_pct,
    calculate_timing_distribution_total,
    INTERVALS_1T, INTERVALS_2T, get_team_stats_all_competitions
)
from utils import format_pct, format_roi, format_num, get_pct_color
from screens.goal_comparison import render_goal_comparison
from screens.roi_dashboard import render_roi_dashboard
from screens.equilibrium_block import render_equilibrium_block
from screens.first_goal_chart import build_first_goal_data, render_first_goal_chart
from screens.match_header import compute_header_insights, render_premium_header
from screens.goal_timing import render_goal_timing
from screens.momentum_chart import render_similar_momentum_block


_PLOTLY_CONFIG = {"displayModeBar": False, "staticPlot": False}


def _section_header(
    number: str,
    title: str,
    subtitle: str = "",
    color: str = "#3b82f6",
    first: bool = False,
):
    margin_top = "4px" if first else "32px"
    sub_html = (
        f'<div style="font-size:12px; color:#64748b; margin-top:3px; line-height:1.4;">{subtitle}</div>'
        if subtitle else ""
    )
    st.html(f"""
    <div class="pm-section" style="margin:{margin_top} 0 14px 0; padding-bottom:10px;
                border-bottom:1px solid #1f2937;">
        <div style="display:flex; align-items:flex-start; gap:10px;">
            <div style="background:{color}18; border:1px solid {color}45; color:{color};
                        font-size:11px; font-weight:800; padding:4px 9px; border-radius:6px;
                        min-width:30px; text-align:center; flex-shrink:0;">
                {number}
            </div>
            <div>
                <div style="font-size:15px; font-weight:800; color:#f1f5f9; letter-spacing:0.2px;">
                    {title}
                </div>
                {sub_html}
            </div>
        </div>
    </div>
    """)


def _compute_prematch_data(filters: dict) -> dict | None:
    df, filtered, goal_events, match_ids = build_prematch_frame(filters)
    if df.empty or filtered.empty:
        return None
    results = analyze_matches(filtered)
    results = enrich_with_goal_events(results, goal_events, match_ids)
    return {
        "df": df,
        "filtered": filtered,
        "goal_events": goal_events,
        "match_ids": match_ids,
        "results": results,
    }


def render():
    # ═══════════════════════════════════════════
    # GLOBAL STYLES
    # ═══════════════════════════════════════════
    if not st.session_state.get("_pm_css_loaded"):
        st.session_state._pm_css_loaded = True
        st.html("""
    <style>
        .pm-card {
            background:#111827; 
            border:1px solid #1f2937; 
            border-radius:8px; 
            padding:16px; 
            text-align:center;
            height: 100%;
        }
        .pm-label {
            font-size:11px; 
            color:#94a3b8; 
            text-transform:uppercase; 
            letter-spacing:1px; 
            margin-bottom:8px;
        }
        .pm-val {
            font-size:28px; 
            font-weight:700;
        }
        .pm-sub {
            font-size:11px; 
            color:#64748b; 
            margin-top:4px;
        }
        .pm-box {
            background:#111827; 
            border:1px solid #1f2937; 
            border-radius:8px; 
            padding:16px; 
            margin-bottom: 16px;
        }
        .pm-score-table {
            width: 100%;
            border-collapse: collapse;
        }
        .pm-score-table th, .pm-score-table td {
            border: 1px solid #1f2937;
            padding: 8px;
            text-align: center;
        }
        .pm-score-table th {
            color: #94a3b8;
            font-size: 12px;
            font-weight: 600;
        }
    </style>
    """)

    # ── Sidebar Filters ────────────────────────────────────────────────────────
    filters = render_filter_sidebar("prematch")

    if not should_run_analysis(filters):
        st.info("👈 Imposta i filtri e clicca **⚡ ANALISI RAPIDA** per visualizzare i risultati.")
        return

    # ── Load Data (cached) ───────────────────────────────────────────────
    with st.spinner("Analisi in corso..."):
        data = load_prematch_data(filters, lambda: _compute_prematch_data(filters))
    if not data:
        st.warning("🔍 Nessun dato trovato con i filtri selezionati.")
        return

    df = data["df"]
    filtered = data["filtered"]
    goal_events = data["goal_events"]
    match_ids = data["match_ids"]
    results = data["results"]

    # ── Inline Calculations for UI ────────────────────────────────────────────────────────
    n = results["match_count"]
    
    def _parse_minute(raw):
        """Convert '45+2' -> 47, '90+6' -> 96, 45 -> 45."""
        try:
            s = str(raw).strip()
            if "+" in s:
                base, extra = s.split("+", 1)
                return int(base) + int(extra)
            return int(float(s))
        except (ValueError, TypeError):
            return 0

    # Goal distribution
    g_dist = {0:0, 1:0, 2:0, 3:0, 4:0, "5+":0}
    total_goals_ft = pd.to_numeric(filtered["total_goals_ft"], errors="coerce").fillna(0)
    for g in total_goals_ft:
        if g >= 5:
            g_dist["5+"] += 1
        else:
            g_dist[int(g)] += 1

    # Exact scores
    filtered["score_str"] = filtered.apply(
        lambda r: f"{int(r.get('home_goals_ft',0))}-{int(r.get('away_goals_ft',0))}", axis=1
    )
    hw_scores = filtered[pd.to_numeric(filtered["home_goals_ft"], errors="coerce") > pd.to_numeric(filtered["away_goals_ft"], errors="coerce")]["score_str"].value_counts()
    dr_scores = filtered[pd.to_numeric(filtered["home_goals_ft"], errors="coerce") == pd.to_numeric(filtered["away_goals_ft"], errors="coerce")]["score_str"].value_counts()
    aw_scores = filtered[pd.to_numeric(filtered["home_goals_ft"], errors="coerce") < pd.to_numeric(filtered["away_goals_ft"], errors="coerce")]["score_str"].value_counts()


    # Over/Under Counts
    tg_ht = pd.to_numeric(filtered["total_goals_ht"], errors="coerce").fillna(0)
    tg_2h = pd.to_numeric(filtered["total_goals_2h"], errors="coerce").fillna(0)
    o05_1t = int((tg_ht >= 1).sum())
    o15_1t = int((tg_ht >= 2).sum())
    o25_1t = int((tg_ht >= 3).sum())
    o05_2t = int((tg_2h >= 1).sum())
    o15_2t = int((tg_2h >= 2).sum())
    o25_2t = int((tg_2h >= 3).sum())

    # Overall FT overs
    tg_ft_s = pd.to_numeric(filtered["total_goals_ft"], errors="coerce").fillna(0)
    o05_ft = int((tg_ft_s >= 1).sum())
    o15_ft = int((tg_ft_s >= 2).sum())
    o25_ft = int((tg_ft_s >= 3).sum())
    o35_ft = int((tg_ft_s >= 4).sum())
    o45_ft = int((tg_ft_s >= 5).sum())
    hg_s   = pd.to_numeric(filtered["home_goals_ft"], errors="coerce").fillna(0)
    ag_s   = pd.to_numeric(filtered["away_goals_ft"], errors="coerce").fillna(0)
    btts_ft = int(((hg_s > 0) & (ag_s > 0)).sum())

    # ═══════════════════════════════════════════
    # SEZIONE 01 — RIEPILOGO ANALISI
    # ═══════════════════════════════════════════
    _section_header(
        "01", "Riepilogo Analisi",
        "Esiti 1X2, edge, equilibrio e strategie sul campione filtrato",
        color="#38bdf8", first=True,
    )
    hw_pct = results["home_win_pct"]
    dr_pct = results["draw_pct"]
    aw_pct = results["away_win_pct"]
    avg_g = results.get("avg_goals_ft", 0.0)

    home_win_count = round(hw_pct / 100 * n)
    draw_count = round(dr_pct / 100 * n)
    away_win_count = round(aw_pct / 100 * n)

    header_insights = compute_header_insights(
        hw_pct, dr_pct, aw_pct, n, results, filtered,
        goal_events, match_ids, _parse_minute, g_dist,
    )
    render_premium_header(hw_pct, dr_pct, aw_pct, n, header_insights)

    pm_home = filters.get("home_team") or "Casa"
    pm_away = filters.get("away_team") or "Trasferta"
    render_similar_momentum_block(
        goal_events, match_ids, n,
        pm_home, pm_away,
        chart_key="pm_similar_momentum",
        show_minute_marker=False,
        subtitle="Intensità attesa casa vs trasferta sui 90 minuti (da gol storici nel campione)",
    )

    # ═══════════════════════════════════════════
    # SEZIONE 02 — OVER / UNDER
    # ═══════════════════════════════════════════
    _section_header(
        "02", "Over / Under",
        "Percentuali goal market su tempo pieno, 1° e 2° tempo",
        color="#22c55e",
    )

    def _over_cell(label, count, n, highlight=False):
        pct = round(count / n * 100, 1) if n > 0 else 0.0
        color = get_pct_color(pct)
        border = f"border-top: 2px solid {color};" if highlight else ""
        return f"""
        <div style="background:#1e293b; border-radius:6px; padding:8px 4px; text-align:center; {border}">
            <div style="font-size:9px; color:#94a3b8; font-weight:700; text-transform:uppercase; letter-spacing:0.8px; margin-bottom:3px;">{label}</div>
            <div style="font-size:18px; font-weight:800; color:{color}; line-height:1;">{pct:.1f}%</div>
            <div style="font-size:10px; color:#64748b; margin-top:2px;">{count}/{n}</div>
        </div>
        """

    # Row 1: Overall FT
    o_cells_ft = "".join([
        _over_cell("OVER 0.5", o05_ft, n, True),
        _over_cell("OVER 1.5", o15_ft, n, True),
        _over_cell("OVER 2.5", o25_ft, n, True),
        _over_cell("OVER 3.5", o35_ft, n, True),
        _over_cell("OVER 4.5", o45_ft, n, True),
        _over_cell("BTTS",     btts_ft, n, True),
    ])

    # Row 2: 1st Half
    o_cells_1h = "".join([
        _over_cell("1T OVER 0.5", o05_1t, n),
        _over_cell("1T OVER 1.5", o15_1t, n),
        _over_cell("1T OVER 2.5", o25_1t, n),
    ])

    # Row 3: 2nd Half
    o_cells_2h = "".join([
        _over_cell("2T OVER 0.5", o05_2t, n),
        _over_cell("2T OVER 1.5", o15_2t, n),
        _over_cell("2T OVER 2.5", o25_2t, n),
    ])

    st.html(f"""
    <div class="pm-box" style="padding:14px 16px; margin-bottom:16px;">
        <div style="font-size:10px; color:#64748b; font-weight:700; text-transform:uppercase;
                    letter-spacing:1px; margin-bottom:10px;">RIEPILOGO OVER / UNDER — TEMPO PIENO</div>
        <div style="display:grid; grid-template-columns:repeat(6,1fr); gap:8px; margin-bottom:10px;">
            {o_cells_ft}
        </div>
        <div style="border-top:1px solid #1f2937; margin:8px 0;"></div>
        <div style="display:grid; grid-template-columns:auto 1fr 1fr 1fr; gap:8px; margin-bottom:8px;">
            <div style="font-size:9px; color:#64748b; font-weight:700; text-transform:uppercase;
                        letter-spacing:0.8px; display:flex; align-items:center; white-space:nowrap; padding-right:4px;">1° TEMPO</div>
            {o_cells_1h}
        </div>
        <div style="display:grid; grid-template-columns:auto 1fr 1fr 1fr; gap:8px;">
            <div style="font-size:9px; color:#64748b; font-weight:700; text-transform:uppercase;
                        letter-spacing:0.8px; display:flex; align-items:center; white-space:nowrap; padding-right:4px;">2° TEMPO</div>
            {o_cells_2h}
        </div>
    </div>
    """)

    pm_view = st.radio(
        "Sezione analisi",
        ["Tutte", "Riepilogo", "Gol & Risultati", "Tempi & Strategia", "Squadre & Export"],
        horizontal=True,
        key="pm_view",
        label_visibility="collapsed",
    )

    def _pm_show(section: str) -> bool:
        return pm_view == "Tutte" or pm_view == section

    if _pm_show("Riepilogo"):
        import plotly.graph_objects as go
        # ═══════════════════════════════════════════
        # SEZIONE 03 — DISTRIBUZIONE GOL
        # ═══════════════════════════════════════════
        _section_header(
            "03", "Distribuzione Gol",
            "Istogramma per numero di gol, cluster e KPI del campione",
            color="#a855f7",
        )

        # ── Pre-calculate cluster values ──────────────────────────────────
        g0_count = g_dist.get(0, 0)
        g1_count = g_dist.get(1, 0)
        g2_count = g_dist.get(2, 0)
        g3_count = g_dist.get(3, 0)
        g4p_count = g_dist.get(4, 0) + g_dist.get("5+", 0)

        def _goal_cluster_pct(count: int) -> float:
            return round(count / n * 100, 1) if n > 0 else 0.0

        pct_0_gol = _goal_cluster_pct(g0_count)
        pct_1_2_gol = _goal_cluster_pct(g1_count + g2_count)
        pct_1_3_gol = _goal_cluster_pct(g1_count + g2_count + g3_count)
        pct_2_3_gol = _goal_cluster_pct(g2_count + g3_count)
        pct_2_4p_gol = _goal_cluster_pct(g2_count + g3_count + g4p_count)

        cl_02_pct = _goal_cluster_pct(g0_count + g1_count + g2_count)
        cl_3_pct = _goal_cluster_pct(g3_count)
        cl_4p_pct = _goal_cluster_pct(g4p_count)

        # Median & avg goals — total_goals_ft is already a numeric Series
        median_goals = float(total_goals_ft.median()) if len(total_goals_ft) > 0 else 0.0
        avg_goals_val = results.get("avg_goals_ft", 0.0)

        bar_col, kpi_col = st.columns([3, 1])

        # ── Left: Plotly bar chart ────────────────────────────────────────
        with bar_col:
            _cluster_cards = [
                ("0 GOL", pct_0_gol, "#64748b"),
                ("1-2 GOL", pct_1_2_gol, "#22c55e"),
                ("1-3 GOL", pct_1_3_gol, "#38bdf8"),
                ("2-3 GOL", pct_2_3_gol, "#f59e0b"),
                ("2-4+ GOL", pct_2_4p_gol, "#ef4444"),
            ]
            _bar_colors = [c[2] for c in _cluster_cards]

            bar_labels = [str(k) if k != "5+" else "5+" for k in g_dist.keys()]
            bar_pcts   = [round(v / n * 100, 1) if n > 0 else 0.0 for v in g_dist.values()]
            bar_colors = [
                _bar_colors[min(i, len(_bar_colors) - 1)]
                for i, _ in enumerate(bar_labels)
            ]

            fig_bar = go.Figure(go.Bar(
                x=bar_labels,
                y=bar_pcts,
                marker_color=bar_colors,
                text=[f"{p}%" for p in bar_pcts],
                textposition="outside",
                textfont=dict(color="#f1f5f9", size=11),
                cliponaxis=False,
            ))
            fig_bar.update_layout(
                margin=dict(t=24, b=8, l=8, r=8),
                height=210,
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                showlegend=False,
                xaxis=dict(
                    title=dict(text="Numero di gol", font=dict(color="#94a3b8", size=11)),
                    tickfont=dict(color="#94a3b8", size=11),
                    showgrid=False,
                    zeroline=False,
                ),
                yaxis=dict(
                    title=dict(text="% Partite", font=dict(color="#94a3b8", size=11)),
                    tickfont=dict(color="#94a3b8", size=10),
                    ticksuffix="%",
                    showgrid=True,
                    gridcolor="#1f2937",
                    zeroline=False,
                    range=[0, max(bar_pcts) * 1.25 if bar_pcts else 40],
                ),
                bargap=0.3,
            )
            st.plotly_chart(fig_bar, use_container_width=True, key="pm_goal_dist_bar")

            cb_cols = st.columns(5)
            for col, (label, pct, color) in zip(cb_cols, _cluster_cards):
                with col:
                    st.html(f"""
                    <div style="background:#111827; border:1px solid #1f2937; border-radius:8px;
                                padding:10px; text-align:center;">
                        <div style="color:{color}; font-size:10px; font-weight:700;
                                    text-transform:uppercase; letter-spacing:0.5px; margin-bottom:4px;">
                            {label}
                        </div>
                        <div style="color:{color}; font-size:20px; font-weight:800; line-height:1;">
                            {pct}%
                        </div>
                    </div>
                    """)

        with kpi_col:
            st.html(f"""
            <div style="display:flex; flex-direction:column; gap:10px; padding-top:4px;">

                <div style="background:#111827; border:1px solid #1f2937; border-radius:8px;
                            padding:12px; text-align:center;">
                    <div style="color:#94a3b8; font-size:10px; font-weight:600;
                                text-transform:uppercase; letter-spacing:0.8px; margin-bottom:6px;">
                        TOTALE PARTITE
                    </div>
                    <div style="color:#f1f5f9; font-size:22px; font-weight:800; line-height:1;">
                        {n:,}
                    </div>
                </div>

                <div style="background:#111827; border:1px solid #1f2937; border-radius:8px;
                            padding:12px; text-align:center;">
                    <div style="color:#94a3b8; font-size:10px; font-weight:600;
                                text-transform:uppercase; letter-spacing:0.8px; margin-bottom:6px;">
                        &#9917; MEDIA GOL
                    </div>
                    <div style="color:#22c55e; font-size:26px; font-weight:800; line-height:1;">
                        {avg_goals_val:.2f}
                    </div>
                </div>

                <div style="background:#111827; border:1px solid #1f2937; border-radius:8px;
                            padding:12px; text-align:center;">
                    <div style="color:#94a3b8; font-size:10px; font-weight:600;
                                text-transform:uppercase; letter-spacing:0.8px; margin-bottom:6px;">
                        &#128200; GOAL AVERAGE
                    </div>
                    <div style="color:#22c55e; font-size:26px; font-weight:800; line-height:1;">
                        {int(median_goals)}
                    </div>
                </div>

            </div>
            """)

        over25_pct = cl_3_pct + cl_4p_pct
        under25_pct = cl_02_pct
        range_2_3_pct = pct_2_3_gol

        if over25_pct >= 65:
            over_signal = "🔥 OVER 2.5 FORTE"
            over_color = "#22c55e"
        elif over25_pct >= 55:
            over_signal = "⚡ OVER 2.5 BUONO"
            over_color = "#f59e0b"
        else:
            over_signal = "❄️ UNDER FAVORITO"
            over_color = "#ef4444"

        over_glow = f"0 0 12px {over_color}"
        _o25_s = pd.to_numeric(filtered.get("odds_over25", pd.Series(dtype=float)), errors="coerce").dropna()
        _avg_o25 = float(_o25_s.mean()) if len(_o25_s) > 0 else 1.85
        _implied_o25 = (1 / _avg_o25 * 100) if _avg_o25 > 1 else 50.0
        edge_o25 = over25_pct - _implied_o25
        edge_color = "#22c55e" if edge_o25 > 0 else "#ef4444"

        st.html(f"""
        <div style="margin-top:12px; padding:12px; background:#111827; border-radius:10px;
                    border:1px solid #1f2937; font-size:13px; color:#e2e8f0; line-height:1.8;">
            <div style="font-weight:700; color:{over_color}; text-shadow:{over_glow}; margin-bottom:4px;">
                {over_signal}
            </div>
            <div>
                🎯 Over 2.5:
                <b style="color:{over_color}; text-shadow:{over_glow};">{over25_pct:.1f}%</b>
            </div>
            <div>📉 Under 2.5: {under25_pct:.1f}%</div>
            <div>⚖️ Range dominante: <b>2–3 gol ({range_2_3_pct:.1f}%)</b></div>
            <div>
                💰 Edge:
                <b style="color:{edge_color}; text-shadow:0 0 10px {edge_color};">{edge_o25:+.1f}%</b>
                <span style="color:#64748b; font-size:11px;"> (vs quota {_avg_o25:.2f})</span>
            </div>
        </div>
        """)

    if _pm_show("Gol & Risultati"):
        # ═══════════════════════════════════════════
        # SEZIONE 04 — PRIMO GOL
        # ═══════════════════════════════════════════
        _section_header(
            "04", "Primo Gol",
            "Minuto medio e distribuzione del primo gol per tempo",
            color="#3b82f6",
        )

        # Calculate 1T and 2T first goal stats from goal_events
        fg1t_home_mins, fg1t_away_mins = [], []
        fg2t_home_mins, fg2t_away_mins = [], []

        fg_intervals_1t = {"0-15": [0, 0], "16-30": [0, 0], "31-45": [0, 0], "45+": [0, 0]}
        fg_intervals_2t = {"46-60": [0, 0], "61-75": [0, 0], "76-90": [0, 0], "90+": [0, 0]}

        fg1t_none_count = 0  # matches with no goal in 1T
        fg2t_none_count = 0  # matches with no goal in 2T

        for mid in match_ids:
            events = goal_events.get(int(mid), [])
            sorted_evs = sorted(events, key=lambda x: _parse_minute(x["minute"])) if events else []

            # First goal in 1T (minute <= 45, including 45+)
            evs_1t = [e for e in sorted_evs if _parse_minute(e["minute"]) <= 45]
            if not evs_1t:
                fg1t_none_count += 1
            if evs_1t:
                fg1 = evs_1t[0]
                m = _parse_minute(fg1["minute"])
                bucket = "0-15" if m <= 15 else "16-30" if m <= 30 else "31-45" if m <= 44 else "45+"
                if fg1["is_home"] == 1:
                    fg1t_home_mins.append(m)
                    fg_intervals_1t[bucket][0] += 1
                else:
                    fg1t_away_mins.append(m)
                    fg_intervals_1t[bucket][1] += 1

            # First goal in 2T (minute > 45, including 90+)
            evs_2t = [e for e in sorted_evs if _parse_minute(e["minute"]) > 45]
            if not evs_2t:
                fg2t_none_count += 1
            if evs_2t:
                fg2 = evs_2t[0]
                m = _parse_minute(fg2["minute"])
                bucket = "46-60" if m <= 60 else "61-75" if m <= 75 else "76-90" if m <= 90 else "90+"
                if fg2["is_home"] == 1:
                    fg2t_home_mins.append(m)
                    fg_intervals_2t[bucket][0] += 1
                else:
                    fg2t_away_mins.append(m)
                    fg_intervals_2t[bucket][1] += 1

        total_fg1t = len(fg1t_home_mins) + len(fg1t_away_mins)
        total_fg2t = len(fg2t_home_mins) + len(fg2t_away_mins)

        pct_no_fg1t = round(fg1t_none_count / n * 100, 1) if n > 0 else 0.0
        pct_no_fg2t = round(fg2t_none_count / n * 100, 1) if n > 0 else 0.0
        pct_fg1t_with = round(total_fg1t / n * 100, 1) if n > 0 else 0.0
        pct_fg2t_with = round(total_fg2t / n * 100, 1) if n > 0 else 0.0

        data_1t = build_first_goal_data(
            fg1t_home_mins, fg1t_away_mins, fg_intervals_1t,
            [("0–15", ["0-15"]), ("16–30", ["16-30"]), ("31–45", ["31-45", "45+"])],
            30, n, 45,
        )
        data_2t = build_first_goal_data(
            fg2t_home_mins, fg2t_away_mins, fg_intervals_2t,
            [("46–60", ["46-60"]), ("61–75", ["61-75"]), ("76–90", ["76-90", "90+"])],
            60, n, 90,
        )

        col_1t, col_2t = st.columns(2)

        with col_1t:
            render_first_goal_chart(
                data_1t, "⏱ PRIMO GOL — 1° TEMPO (0' – 45')", "#3b82f6", "#3b82f640",
                total_fg1t, fg1t_none_count, pct_fg1t_with, pct_no_fg1t,
            )

        with col_2t:
            render_first_goal_chart(
                data_2t, "⏱ PRIMO GOL — 2° TEMPO (46' – 90')", "#f97316", "#f9741640",
                total_fg2t, fg2t_none_count, pct_fg2t_with, pct_no_fg2t,
            )

        # ═══════════════════════════════════════════
        # SEZIONE 05 — RISULTATI ESATTI
        # ═══════════════════════════════════════════
        _section_header(
            "05", "Risultati Esatti",
            "Scoreline più frequenti per esito e top 5 assoluto",
            color="#f59e0b",
        )

        def _get_top(series, k=5):
            res = []
            for s, v in series.head(k).items():
                res.append((s, int(v), round(v / n * 100, 1) if n > 0 else 0.0))
            while len(res) < k:
                res.append(("-", 0, 0.0))
            top3_cum = round(series.head(3).sum() / n * 100, 1) if n > 0 else 0.0
            top5_cum = round(series.head(5).sum() / n * 100, 1) if n > 0 else 0.0
            return res, top3_cum, top5_cum

        def _cluster_scores(series):
            tight = wide = 0
            for score, count in series.items():
                if score == "-":
                    continue
                h, a = map(int, score.split("-"))
                margin = abs(h - a)
                if margin == 1:
                    tight += count
                elif margin >= 3:
                    wide += count
            tight_pct = round(tight / n * 100, 1) if n > 0 else 0.0
            wide_pct = round(wide / n * 100, 1) if n > 0 else 0.0
            return tight_pct, wide_pct

        t_hw, top3_hw, top5_hw = _get_top(hw_scores)
        t_dr, top3_dr, top5_dr = _get_top(dr_scores)
        t_aw, top3_aw, top5_aw = _get_top(aw_scores)

        tight_hw, wide_hw = _cluster_scores(hw_scores)
        tight_dr, wide_dr = _cluster_scores(dr_scores)
        tight_aw, wide_aw = _cluster_scores(aw_scores)

        all_score_counts = filtered["score_str"].value_counts()
        global_best = all_score_counts.index[0] if len(all_score_counts) else "-"
        global_best_pct = round(all_score_counts.iloc[0] / n * 100, 1) if len(all_score_counts) and n > 0 else 0.0
        global_top5_conf = round(all_score_counts.head(5).sum() / n * 100, 1) if n > 0 else 0.0

        low_goals_n = high_goals_n = 0
        for score, count in all_score_counts.items():
            h, a = map(int, score.split("-"))
            if h + a <= 2:
                low_goals_n += count
            else:
                high_goals_n += count
        low_goals_pct = round(low_goals_n / n * 100, 1) if n > 0 else 0.0
        high_goals_pct = round(high_goals_n / n * 100, 1) if n > 0 else 0.0
        over25_pct = results.get("over_25_ft_pct", 0.0)

        dominance = round(hw_pct - aw_pct, 1)
        if dominance > 5:
            dom_text = f"CASA dominante: +{dominance}% vs trasferta"
            dom_color = "#22c55e"
        elif dominance < -5:
            dom_text = f"TRASFERTA dominante: +{abs(dominance)}% vs casa"
            dom_color = "#ef4444"
        else:
            dom_text = f"Equilibrio ({dominance:+.1f}%)"
            dom_color = "#f59e0b"

        st.html(f"""
        <div class="pm-box" style="padding:10px 14px; margin-bottom:8px; display:flex; flex-wrap:wrap; gap:12px; align-items:center;">
            <div style="font-size:12px; font-weight:700; color:{dom_color};">
                ⚡ {dom_text}
            </div>
            <div style="font-size:11px; color:#94a3b8;">
                🔥 Più probabile: <span style="color:#f59e0b; font-weight:700; text-shadow:0 0 8px #f59e0b60;">{global_best} ({global_best_pct}%)</span>
            </div>
            <div style="font-size:11px; color:#94a3b8;">
                TOP 5 coprono <span style="color:#3b82f6; font-weight:700;">{global_top5_conf}%</span> dei casi
            </div>
            <div style="font-size:11px; color:#94a3b8;">
                📊 {low_goals_pct}% risultati 0-2 gol · {high_goals_pct}% 3+ gol
                <span style="color:#64748b;">(Over 2.5: {over25_pct:.1f}%)</span>
            </div>
        </div>
        """)

        st.html('<div id="risultati-card" class="pm-box" style="padding:0; overflow:hidden; margin-top:4px;">')
        r_col1, r_col2, r_col3, r_col4 = st.columns(4)

        def _score_col_html(header_color, header_label, scores, top3_cum, top5_cum,
                            esiti_pct, esiti_count, esiti_label, tight_pct, wide_pct):
            best_score = scores[0][0] if scores and scores[0][0] != "-" else None
            top5_rows = ""
            for score, count, pct in scores:
                is_best = score == best_score and score != "-"
                score_style = (
                    "color:#f59e0b; font-weight:800; text-shadow:0 0 8px #f59e0b80;"
                    if is_best else "color:#f1f5f9; font-weight:500;"
                )
                badge = "🔥 " if is_best else ""
                pct_color = "#f59e0b" if is_best else header_color
                top5_rows += f"""
                <div style="display:flex; justify-content:space-between; align-items:center;
                            padding:5px 0; border-bottom:1px solid #1f2937;">
                    <span style="{score_style} font-size:12px;">{badge}{score}</span>
                    <span style="font-size:11px; font-weight:600; white-space:nowrap;">
                        <span style="color:#64748b;">{count}</span>
                        <span style="color:#475569; margin:0 4px;">·</span>
                        <span style="color:{pct_color};">{pct}%</span>
                    </span>
                </div>
                """

            conf_width = min(top5_cum, 100)
            return f"""
            <div style="padding:12px 14px; height:100%;">
                <div style="color:{header_color}; font-size:13px; font-weight:700;
                            text-transform:uppercase; letter-spacing:0.5px;
                            padding-bottom:8px; border-bottom:2px solid {header_color}40;
                            margin-bottom:10px;">
                    {header_label}
                </div>
                <div style="display:flex; gap:12px;">
                    <div style="flex:1; border-right:1px solid #1f2937; padding-right:10px;">
                        <div style="font-size:9px; color:#64748b; text-transform:uppercase;
                                    letter-spacing:0.8px; margin-bottom:3px;">ESITI PRINCIPALI</div>
                        <div style="color:{header_color}; font-size:26px; font-weight:800; line-height:1;">
                            {esiti_pct:.1f}%
                        </div>
                        <div style="color:#64748b; font-size:10px; margin-top:4px;">
                            {esiti_count} {esiti_label}
                        </div>
                        <div style="margin-top:10px; font-size:10px; color:#64748b; line-height:1.6;">
                            <div>TOP 3 cumulativo: <span style="color:#cbd5e1; font-weight:600;">{top3_cum}%</span></div>
                            <div>TOP 5 cumulativo: <span style="color:#cbd5e1; font-weight:600;">{top5_cum}%</span></div>
                        </div>
                        <div style="margin-top:8px; font-size:10px; color:#64748b; line-height:1.5;">
                            <div>🎯 Stretti (±1): <span style="color:#94a3b8;">{tight_pct}%</span></div>
                            <div>💣 Larghi (3+): <span style="color:#94a3b8;">{wide_pct}%</span></div>
                        </div>
                        <div style="margin-top:10px;">
                            <div style="font-size:9px; color:#64748b; margin-bottom:4px;">
                                Confidenza TOP 5: {top5_cum}%
                            </div>
                            <div style="background:#1f2937; height:6px; border-radius:4px; overflow:hidden;">
                                <div style="width:{conf_width}%; background:{header_color}; height:100%;
                                            box-shadow:0 0 6px {header_color}80;"></div>
                            </div>
                        </div>
                    </div>
                    <div style="flex:1; padding-left:2px;">
                        <div style="font-size:10px; color:#64748b; text-transform:uppercase;
                                    letter-spacing:0.8px; margin-bottom:6px;">TOP 5 RISULTATI</div>
                        {top5_rows}
                    </div>
                </div>
            </div>
            """

        def _global_top5_col_html(score_counts):
            header_color = "#38bdf8"
            scores = [
                (s, int(c), round(c / n * 100, 1) if n > 0 else 0.0)
                for s, c in score_counts.head(5).items()
            ]
            while len(scores) < 5:
                scores.append(("-", 0, 0.0))
            top3_cum = round(score_counts.head(3).sum() / n * 100, 1) if n > 0 else 0.0
            top5_cum = round(score_counts.head(5).sum() / n * 100, 1) if n > 0 else 0.0
            best_score = scores[0][0] if scores[0][0] != "-" else None
            best_count = scores[0][1] if scores else 0
            best_pct = scores[0][2] if scores else 0.0
            tight_g, wide_g = _cluster_scores(score_counts)

            top5_rows = ""
            for score, count, pct in scores:
                is_best = score == best_score and score != "-"
                score_style = (
                    "color:#f59e0b; font-weight:800; text-shadow:0 0 8px #f59e0b80;"
                    if is_best else "color:#f1f5f9; font-weight:500;"
                )
                badge = "🔥 " if is_best else ""
                pct_color = "#f59e0b" if is_best else header_color
                top5_rows += f"""
                <div style="display:flex; justify-content:space-between; align-items:center;
                            padding:5px 0; border-bottom:1px solid #1f2937;">
                    <span style="{score_style} font-size:12px;">{badge}{score}</span>
                    <span style="font-size:11px; font-weight:600; white-space:nowrap;">
                        <span style="color:#64748b;">{count}</span>
                        <span style="color:#475569; margin:0 4px;">·</span>
                        <span style="color:{pct_color};">{pct}%</span>
                    </span>
                </div>
                """

            conf_width = min(top5_cum, 100)
            return f"""
            <div style="padding:12px 14px; height:100%;">
                <div style="color:{header_color}; font-size:13px; font-weight:700;
                            text-transform:uppercase; letter-spacing:0.5px;
                            padding-bottom:8px; border-bottom:2px solid {header_color}40;
                            margin-bottom:10px;">
                    🏆 — Top 5 Assoluto
                </div>
                <div style="display:flex; gap:12px;">
                    <div style="flex:1; border-right:1px solid #1f2937; padding-right:10px;">
                        <div style="font-size:9px; color:#64748b; text-transform:uppercase;
                                    letter-spacing:0.8px; margin-bottom:3px;">ESITI PRINCIPALI</div>
                        <div style="color:{header_color}; font-size:26px; font-weight:800; line-height:1;">
                            {best_pct:.1f}%
                        </div>
                        <div style="color:#64748b; font-size:10px; margin-top:4px;">
                            {best_count} partite
                        </div>
                        <div style="margin-top:10px; font-size:10px; color:#64748b; line-height:1.6;">
                            <div>TOP 3 cumulativo: <span style="color:#cbd5e1; font-weight:600;">{top3_cum}%</span></div>
                            <div>TOP 5 cumulativo: <span style="color:#cbd5e1; font-weight:600;">{top5_cum}%</span></div>
                        </div>
                        <div style="margin-top:8px; font-size:10px; color:#64748b; line-height:1.5;">
                            <div>🎯 Stretti (±1): <span style="color:#94a3b8;">{tight_g}%</span></div>
                            <div>💣 Larghi (3+): <span style="color:#94a3b8;">{wide_g}%</span></div>
                        </div>
                        <div style="margin-top:10px;">
                            <div style="font-size:9px; color:#64748b; margin-bottom:4px;">
                                Confidenza TOP 5: {top5_cum}%
                            </div>
                            <div style="background:#1f2937; height:6px; border-radius:4px; overflow:hidden;">
                                <div style="width:{conf_width}%; background:{header_color}; height:100%;
                                            box-shadow:0 0 6px {header_color}80;"></div>
                            </div>
                        </div>
                    </div>
                    <div style="flex:1; padding-left:2px;">
                        <div style="font-size:10px; color:#64748b; text-transform:uppercase;
                                    letter-spacing:0.8px; margin-bottom:6px;">TOP 5 RISULTATI</div>
                        {top5_rows}
                    </div>
                </div>
            </div>
            """

        with r_col1:
            st.html(_score_col_html(
                "#22c55e", "1 — Vittoria Casa",
                t_hw, top3_hw, top5_hw,
                hw_pct, home_win_count, "vittorie", tight_hw, wide_hw,
            ))

        with r_col2:
            st.html(_score_col_html(
                "#f59e0b", "X — Pareggio",
                t_dr, top3_dr, top5_dr,
                dr_pct, draw_count, "pareggi", tight_dr, wide_dr,
            ))

        with r_col3:
            st.html(_score_col_html(
                "#ef4444", "2 — Vittoria Trasferta",
                t_aw, top3_aw, top5_aw,
                aw_pct, away_win_count, "vittorie", tight_aw, wide_aw,
            ))

        with r_col4:
            st.html(_global_top5_col_html(all_score_counts))

        st.html('</div>')

    if _pm_show("Tempi & Strategia"):
        import plotly.graph_objects as go
        # ═══════════════════════════════════════════
        # SEZIONE 06 — OVER / UNDER PER TEMPO
        # ═══════════════════════════════════════════
        _section_header(
            "06", "Over / Under per Tempo",
            "Breakdown over e under su primo e secondo tempo",
            color="#22c55e",
        )
        c1, c2 = st.columns(2)
    
        def _render_ou_panel(title, o05, o15, o25):
            u05 = n - o05
            u15 = n - o15
            u25 = n - o25
        
            items = [
                ("OVER 0.5", o05), ("OVER 1.5", o15), ("OVER 2.5", o25),
                ("UNDER 0.5", u05), ("UNDER 1.5", u15), ("UNDER 2.5", u25)
            ]
        
            html = f'<div class="pm-box"><div style="color:#f1f5f9;font-weight:600;margin-bottom:12px;">{title}</div>'
            html += '<div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:12px;">'
        
            for label, count in items:
                pct = round(count / n * 100, 1) if n > 0 else 0.0
                color = get_pct_color(pct)
                calculated_count = round(pct / 100 * n)
            
                html += f"""
                <div style="background:#1e293b; border-radius:6px; padding:12px; text-align:center;">
                    <div style="font-size:10px; color:#94a3b8; font-weight:600;">{label}</div>
                    <p style="color:{color}; font-size:1.4rem; font-weight:bold; margin:0;">{pct:.1f}%</p>
                    <div style="font-size:11px; color:#64748b; margin-top:4px;">{calculated_count}/{n}</div>
                </div>
                """
            html += '</div></div>'
            return html

        with c1:
            st.html(_render_ou_panel("OVER / UNDER — PRIMO TEMPO (1T)", o05_1t, o15_1t, o25_1t))
        with c2:
            st.html(_render_ou_panel("OVER / UNDER — SECONDO TEMPO (2T)", o05_2t, o15_2t, o25_2t))

        # ═══════════════════════════════════════════
        # SECTION 4B — CONFRONTO GOL 1T vs 2T
        # ═══════════════════════════════════════════
        hg_1t_s = pd.to_numeric(filtered["home_goals_ht"], errors="coerce").fillna(0)
        ag_1t_s = pd.to_numeric(filtered["away_goals_ht"], errors="coerce").fillna(0)
        hg_ft_s = pd.to_numeric(filtered["home_goals_ft"], errors="coerce").fillna(0)
        ag_ft_s = pd.to_numeric(filtered["away_goals_ft"], errors="coerce").fillna(0)

        total_goals_1t = float((hg_1t_s + ag_1t_s).sum())
        total_goals_2t = float(((hg_ft_s - hg_1t_s) + (ag_ft_s - ag_1t_s)).sum())
        total_goals_all = total_goals_1t + total_goals_2t

        pct_1t = round(total_goals_1t / total_goals_all * 100, 1) if total_goals_all > 0 else 0.0
        pct_2t = round(100.0 - pct_1t, 1)

        # ═══════════════════════════════════════════
        # SEZIONE 07 — TIMING DEI GOL
        # ═══════════════════════════════════════════
        _section_header(
            "07", "Timing dei Gol",
            "Distribuzione per intervalli, medie per tempo e heatmap",
            color="#06b6d4",
        )
        c1, c2 = st.columns([3, 1])
    
        with c1:
            timing_total = calculate_timing_distribution_total(goal_events, match_ids)
            timing = timing_total["timing_dist"]
            best_tf = timing_total["best_tf"]
            worst_tf = timing_total["worst_tf"]
            best_val = timing_total["best_val"]
            worst_val = timing_total["worst_val"]

            if timing_total["total_goals"] > 0:
                bar_colors = []
                values = list(timing.values())
                min_val = min(values)
                max_val = max(values)
                val_range = max_val - min_val if max_val != min_val else 1

                for k, v in timing.items():
                    if k == best_tf:
                        bar_colors.append("#22c55e")
                    elif k == worst_tf:
                        bar_colors.append("#ef4444")
                    else:
                        ratio = (v - min_val) / val_range
                        if ratio < 0.5:
                            r = int(239 + (245 - 239) * (ratio / 0.5))
                            g = int(68  + (158 - 68)  * (ratio / 0.5))
                            b = int(68  + (11  - 68)  * (ratio / 0.5))
                        else:
                            r = int(245 + (34  - 245) * ((ratio - 0.5) / 0.5))
                            g = int(158 + (197 - 158) * ((ratio - 0.5) / 0.5))
                            b = int(11  + (94  - 11)  * ((ratio - 0.5) / 0.5))
                        bar_colors.append(f"rgb({r},{g},{b})")
            else:
                bar_colors = ["#64748b"] * len(timing)
                best_tf = worst_tf = "N/A"
                best_val = worst_val = 0.0

            fig_bar = go.Figure(go.Bar(
                x=list(timing.keys()),
                y=list(timing.values()),
                marker_color=bar_colors,
                text=[f"{v:.1f}%" for v in timing.values()],
                textposition="outside",
            ))
            fig_bar.update_layout(
                margin=dict(t=10, b=30, l=10, r=10),
                height=260,
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#e2e8f0"),
                yaxis=dict(range=[0, max(timing.values()) * 1.2 if timing.values() else 100], showgrid=True, gridcolor="#334155"),
                xaxis=dict(showgrid=False)
            )
            st.plotly_chart(fig_bar, width="stretch", key="pm_timing_bar")

            # Smart Timeframe labels below chart
            st.html(f"""
            <div style="display:flex; gap:12px; margin-top:-8px; margin-bottom:8px;">
                <div style="background:#1e293b; border-left:3px solid #22c55e; border-radius:4px;
                            padding:6px 12px; flex:1; text-align:center;">
                    <div style="font-size:9px; color:#22c55e; font-weight:700;
                                text-transform:uppercase; letter-spacing:1px;">🔥 Periodo più Produttivo</div>
                    <div style="font-size:16px; font-weight:800; color:#f1f5f9;">{best_tf}</div>
                    <div style="font-size:11px; color:#94a3b8;">{best_val:.1f}%</div>
                </div>
                <div style="background:#1e293b; border-left:3px solid #06b6d4; border-radius:4px;
                            padding:6px 12px; flex:1; text-align:center;">
                    <div style="font-size:9px; color:#06b6d4; font-weight:700;
                                text-transform:uppercase; letter-spacing:1px;">❄️ Periodo meno Produttivo</div>
                    <div style="font-size:16px; font-weight:800; color:#f1f5f9;">{worst_tf}</div>
                    <div style="font-size:11px; color:#94a3b8;">{worst_val:.1f}%</div>
                </div>
            </div>
            """)

        with c2:
            hg_1t = pd.to_numeric(filtered["home_goals_ht"], errors="coerce").fillna(0)
            ag_1t = pd.to_numeric(filtered["away_goals_ht"], errors="coerce").fillna(0)
            hg_ft = pd.to_numeric(filtered["home_goals_ft"], errors="coerce").fillna(0)
            ag_ft = pd.to_numeric(filtered["away_goals_ft"], errors="coerce").fillna(0)
        
            hg_2t = hg_ft - hg_1t
            ag_2t = ag_ft - ag_1t
        
            av_1t_h = round(float(hg_1t.mean()),2) if n>0 else 0
            av_1t_a = round(float(ag_1t.mean()),2) if n>0 else 0
            av_1t_t = round(av_1t_h + av_1t_a, 2)
        
            av_2t_h = round(float(hg_2t.mean()),2) if n>0 else 0
            av_2t_a = round(float(ag_2t.mean()),2) if n>0 else 0
            av_2t_t = round(av_2t_h + av_2t_a, 2)
        
            render_goal_timing(av_1t_t, av_2t_t, av_1t_h, av_1t_a, av_2t_h, av_2t_a)

        # New 2-column layout for interval tables
        st.markdown("<br>", unsafe_allow_html=True)
        col_1h_table, col_2h_table = st.columns(2)

        def _heatmap_bg(val, max_val, rgb):
            if max_val <= 0 or val <= 0:
                return "transparent"
            return f"rgba({rgb}, {min(val / max_val, 1.0)})"

        def _heatmap_cell(val, max_val, rgb, bold=False):
            bg = _heatmap_bg(val, max_val, rgb)
            weight = 700 if bold else 600
            return (
                f"background:{bg}; color:#f1f5f9; font-weight:{weight}; "
                f"border:none; text-align:center; padding:10px 6px;"
            )

        def _plain_cell(val):
            return (
                f"color:#94a3b8; border:none; text-align:center; "
                f"padding:10px 6px; font-weight:500;"
            )

        def _build_interval_table(dist, intervals, rgb, accent, totale_pct, title):
            g1_vals = [dist.get(i, {}).get("1_gol", 0.0) for i in intervals]
            ge1_vals = [dist.get(i, {}).get("ge1", 0.0) for i in intervals]
            max_g1 = max(g1_vals) if g1_vals else 0.0
            max_ge1 = max(ge1_vals) if ge1_vals else 0.0

            rows = ""
            for inter in intervals:
                vals = dist.get(inter, {"0_gol": 0.0, "1_gol": 0.0, "2_gol": 0.0, "3plus": 0.0, "ge1": 0.0})
                label = inter.replace("-", " – ")
                rows += (
                    f"<tr>"
                    f"<td style='color:#cbd5e1; font-weight:600; border:none; padding:10px 8px;'>{label}</td>"
                    f"<td style='{_heatmap_cell(vals['1_gol'], max_g1, rgb)}'>{vals['1_gol']:.1f}%</td>"
                    f"<td style='{_plain_cell(vals['2_gol'])}'>{vals['2_gol']:.1f}%</td>"
                    f"<td style='{_plain_cell(vals['3plus'])}'>{vals['3plus']:.1f}%</td>"
                    f"<td style='{_heatmap_cell(vals['ge1'], max_ge1, rgb, bold=True)}'>{vals['ge1']:.1f}%</td>"
                    f"</tr>"
                )

            totale_alpha = min(totale_pct / max(max_ge1, totale_pct, 1.0), 0.65)
            totale_bg = f"rgba({rgb}, {totale_alpha})"
            totale_row = (
                f"<tr style='border-top:1px solid #334155;'>"
                f"<td style='color:{accent}; font-weight:700; border:none; padding:10px 8px;'>TOTALE</td>"
                f"<td style='color:#475569; border:none; text-align:center;'>—</td>"
                f"<td style='color:#475569; border:none; text-align:center;'>—</td>"
                f"<td style='color:#475569; border:none; text-align:center;'>—</td>"
                f"<td style='background:{totale_bg}; color:#f8fafc; font-weight:700; "
                f"border:none; text-align:center; padding:10px 6px;'>{totale_pct:.1f}%</td>"
                f"</tr>"
            )

            return f"""
            <div style="font-size:11px; font-weight:700; color:{accent}; letter-spacing:0.3px; margin-bottom:8px;">
                {title}
            </div>
            <div class="pm-box" style="padding:0; overflow:hidden; border:1px solid #1e293b; border-radius:10px;">
                <table class="pm-score-table" style="width:100%; border-collapse:collapse; border:none;">
                    <tr style="background:#111827;">
                        <th style="border:none; padding:10px 8px; color:#64748b; font-size:10px; text-align:left;">Intervallo</th>
                        <th style="border:none; padding:8px 4px; color:#64748b; font-size:10px; text-align:center;">
                            1 Gol %<br><span style="font-weight:400; font-size:9px;">(delle partite)</span>
                        </th>
                        <th style="border:none; padding:8px 4px; color:#64748b; font-size:10px; text-align:center;">
                            2 Gol %<br><span style="font-weight:400; font-size:9px;">(delle partite)</span>
                        </th>
                        <th style="border:none; padding:8px 4px; color:#64748b; font-size:10px; text-align:center;">
                            3+ Gol %<br><span style="font-weight:400; font-size:9px;">(delle partite)</span>
                        </th>
                        <th style="border:none; padding:8px 4px; color:{accent}; font-size:10px; text-align:center;">
                            ≥ 1 Gol %<br><span style="font-weight:400; font-size:9px; color:#64748b;">(almeno un gol)</span>
                        </th>
                    </tr>
                    {rows}
                    {totale_row}
                </table>
            </div>
            """

        ge1_totale_1t, ge1_totale_2t = calculate_at_least_one_goal_half_pct(goal_events, match_ids)
        intervals_1h = list(INTERVALS_1T.keys())
        intervals_2h = list(INTERVALS_2T.keys())
        dist_1h = calculate_interval_distribution_1h(goal_events, match_ids)
        dist_2h = calculate_interval_distribution_2h(goal_events, match_ids)

        best_1h = max(intervals_1h, key=lambda inter: dist_1h.get(inter, {}).get("ge1", 0.0))
        best_2h = max(intervals_2h, key=lambda inter: dist_2h.get(inter, {}).get("ge1", 0.0))
        best_1h_pct = dist_1h.get(best_1h, {}).get("ge1", 0.0)
        best_2h_pct = dist_2h.get(best_2h, {}).get("ge1", 0.0)
        best_1h_label = best_1h.replace("-", " – ")
        best_2h_label = best_2h.replace("-", " – ")

        with col_1h_table:
            st.html(_build_interval_table(
                dist_1h, intervals_1h, "59,130,246", "#3b82f6", ge1_totale_1t,
                "DISTRIBUZIONE GOL PER INTERVALLI — PRIMO TEMPO (1T)"
            ))
            st.html(f"""
            <div style="font-size:11px; color:#64748b; margin-top:8px; padding-left:2px;">
                ⓘ Il <span style="color:#3b82f6; font-weight:600;">{ge1_totale_1t:.1f}%</span>
                delle partite ha almeno un gol nel 1° tempo
            </div>
            """)

        with col_2h_table:
            st.html(_build_interval_table(
                dist_2h, intervals_2h, "249,115,22", "#f97316", ge1_totale_2t,
                "DISTRIBUZIONE GOL PER INTERVALLI — SECONDO TEMPO (2T)"
            ))
            st.html(f"""
            <div style="font-size:11px; color:#64748b; margin-top:8px; padding-left:2px;">
                ⓘ Il <span style="color:#f97316; font-weight:600;">{ge1_totale_2t:.1f}%</span>
                delle partite ha almeno un gol nel 2° tempo
            </div>
            """)

        st.markdown("<br>", unsafe_allow_html=True)
        st.html(f"""
        <div class="pm-box" style="padding:14px 20px; border:1px solid #1e293b; border-radius:10px;">
            <div style="font-size:11px; font-weight:700; color:#94a3b8; letter-spacing:0.5px; margin-bottom:6px;">
                INSIGHT RAPIDO
            </div>
            <div style="font-size:12px; color:#94a3b8;">
                1T forte tra
                <span style="color:#3b82f6; font-weight:700;">{best_1h_label} ({best_1h_pct:.1f}%)</span>
                almeno un gol
                <span style="color:#334155; margin:0 6px;">·</span>
                2T più forte tra
                <span style="color:#f97316; font-weight:700;">{best_2h_label} ({best_2h_pct:.1f}%)</span>
                almeno un gol
            </div>
        </div>
        """)


        # ═══════════════════════════════════════════
        # SEZIONE 08 — STRATEGIA E VALORE
        # ═══════════════════════════════════════════
        _section_header(
            "08", "Strategia e Valore",
            "Equilibrio partita, insight chiave, confronto tempi e simulazione ROI",
            color="#f97316",
        )

        # ── Row 1: 3 charts side by side ─────────────────────────────────────────
        c_bal, c2, c_confronto = st.columns([1.5, 2, 1.5])

        with c_bal:
            st.markdown("**EQUILIBRIO PARTITA**")
            render_equilibrium_block(hw_pct, dr_pct, aw_pct, n)

        with c2:
            over25_pct = results.get("over_25_ft_pct", 0.0)
            btts_pct = results.get("btts_pct", 0.0)
            avg_goals = results.get("avg_goals_ft", 0.0)
            zero_zero_pct = round(g_dist.get(0, 0) / n * 100, 1) if n > 0 else 0.0

            if over25_pct >= 65:
                over_level = "🔥 ALTA"
            elif over25_pct >= 50:
                over_level = "⚖️ MEDIA"
            else:
                over_level = "❄️ BASSA"

            btts_tag = ""
            if btts_pct > 60 and over25_pct > 60:
                btts_tag = '<span style="color:#22c55e; font-weight:600;"> · 🔥 FORTE CORRELAZIONE</span>'

            if pct_2t > 55:
                tempo_label = "📈 Secondo tempo dominante"
            elif pct_2t < 45:
                tempo_label = "📉 Primo tempo dominante"
            else:
                tempo_label = "⚖️ Tempi equilibrati"

            _insight_timing = timing_total["timing_dist"] if timing_total else results.get("timing_dist", {})
            best_interval = max(_insight_timing, key=_insight_timing.get) if _insight_timing else "N/A"
            best_pct = _insight_timing.get(best_interval, 0.0) if _insight_timing else 0.0
            if best_pct > 30:
                interval_strength = "🔥 MOLTO FORTE"
            elif best_pct > 20:
                interval_strength = "⚡ BUONO"
            else:
                interval_strength = "debole"

            if zero_zero_pct < 5:
                zero_label = "🚫 0-0 improbabile"
            elif zero_zero_pct > 15:
                zero_label = "⚠️ Rischio 0-0"
            else:
                zero_label = "⚖️ 0-0 nella media"

            if 2.5 <= avg_goals <= 3.2:
                balance_goals_label = "⚖️ Match bilanciato"
            elif avg_goals > 3.2:
                balance_goals_label = "🔥 Match offensivo"
            else:
                balance_goals_label = "❄️ Match chiuso"

            _o25_series = pd.to_numeric(filtered.get("odds_over25", pd.Series(dtype=float)), errors="coerce").dropna()
            avg_odds_o25 = float(_o25_series.mean()) if len(_o25_series) > 0 else 1.85
            implied_over25 = (1 / avg_odds_o25 * 100) if avg_odds_o25 > 1 else 50.0
            edge_over25 = over25_pct - implied_over25
            edge_color = "#22c55e" if edge_over25 > 0 else "#ef4444"

            suggestions = []
            if over25_pct >= 65 and edge_over25 > 0:
                suggestions.append("💡 Gioca Over 2.5")
            elif over25_pct < 45 or edge_over25 < -5:
                suggestions.append("💡 Evita Over 2.5")
            if btts_pct < 40:
                suggestions.append("💡 Evita BTTS")
            elif btts_pct > 65 and over25_pct > 60:
                suggestions.append("💡 Gioca BTTS Yes")
            suggestion_html = "".join(
                f'<div style="margin-top:6px; color:#f59e0b; font-size:12px; font-weight:600;">{s}</div>'
                for s in suggestions[:2]
            )

            st.html(f"""
            <div class="pm-box" style="height:100%; border-color:#f59e0b40;">
                <div style="font-size:11px; font-weight:700; color:#f59e0b; text-transform:uppercase;
                            letter-spacing:1px; margin-bottom:12px;">&#128161; INSIGHT CHIAVE</div>
                <div style="padding:12px; border-radius:10px; background:#111827; font-size:13px;
                            color:#e2e8f0; line-height:1.7;">
                    <div>🔥 <b>{over_level} probabilità Over 2.5</b> ({over25_pct:.1f}%)</div>
                    <div>⚽ BTTS: <b>{btts_pct:.1f}%</b>{btts_tag}</div>
                    <div>⏱️ {tempo_label} ({pct_2t:.1f}% gol nel 2T)</div>
                    <div>📊 Intervallo top: <b>{best_interval}</b> ({best_pct:.1f}%) — {interval_strength}</div>
                    <div>{zero_label}: {zero_zero_pct:.1f}%</div>
                    <div>{balance_goals_label} · Media gol: <b>{avg_goals:.2f}</b></div>
                    <div>💰 Edge Over 2.5: <b style="color:{edge_color};">{edge_over25:+.1f}%</b>
                        <span style="color:#64748b; font-size:11px;"> (quota media {avg_odds_o25:.2f})</span>
                    </div>
                    {suggestion_html}
                </div>
            </div>
            """)

        with c_confronto:
            st.markdown("**CONFRONTO GOL 1T vs 2T**")
            render_goal_comparison(pct_1t, pct_2t)


        # ── Row 2: ROI Simulation full width ──────────────────────────────────────
        st.markdown(
            '<div style="font-size:12px; font-weight:700; color:#94a3b8; text-transform:uppercase; '
            'letter-spacing:0.6px; margin:12px 0 8px 0;">Simulazione ROI — Market reali (quote presenti)</div>',
            unsafe_allow_html=True,
        )
        # ── Average odds from filtered dataframe ─────────────────────────────
        avg_odds_home  = pd.to_numeric(filtered.get("odds_home",  pd.Series(dtype=float)), errors="coerce").mean()
        avg_odds_draw  = pd.to_numeric(filtered.get("odds_draw",  pd.Series(dtype=float)), errors="coerce").mean()
        avg_odds_away  = pd.to_numeric(filtered.get("odds_away",  pd.Series(dtype=float)), errors="coerce").mean()

        avg_odds_home  = round(avg_odds_home,  2) if pd.notna(avg_odds_home)  else 2.00
        avg_odds_draw  = round(avg_odds_draw,  2) if pd.notna(avg_odds_draw)  else 3.20
        avg_odds_away  = round(avg_odds_away,  2) if pd.notna(avg_odds_away)  else 2.95

        # Lay odds = 1 / (1 - 1/back_odds)  →  simplified: same as back for lay market
        # For lay: win = opponent wins, loss = bet team wins. Liability = (lay_odds-1)*stake
        # We use back odds as reference for lay too (standard exchange logic)

        # Over/Under & BTTS average odds — computed from filtered matches.
        # Falls back to a default only if the column is missing or empty.
        def _avg_odds_col(col, fallback):
            if col in filtered.columns:
                s = pd.to_numeric(filtered[col], errors="coerce").dropna()
                if len(s) > 0:
                    return round(float(s.mean()), 2)
            return fallback

        avg_odds_over15 = _avg_odds_col("odds_over15", 1.32)
        avg_odds_over25 = _avg_odds_col("odds_over25", 1.85)
        avg_odds_over35 = _avg_odds_col("odds_over35", 2.55)
        avg_odds_over45 = _avg_odds_col("odds_over45", 4.00)
        avg_odds_btts_y = _avg_odds_col("odds_btts_yes", 1.78)
        avg_odds_btts_n = _avg_odds_col("odds_btts_no", 2.00)

        # ── Core calculation function ─────────────────────────────────────────
        # Formula: Profitto = (Vittorie × (Quota Media - 1)) - Perdite
        # ROI     = Profitto / Numero Scommesse × 100
        def calc_roi_row(label, wins, losses, avg_odds):
            total = wins + losses
            if total == 0:
                return label, total, avg_odds, wins, losses, 0.0, 0.0
            profit = (wins * (avg_odds - 1.0)) - losses
            profit = round(profit, 1)
            roi_pct = round((profit / total) * 100, 2)
            return label, total, avg_odds, wins, losses, profit, roi_pct

        def calc_lay_row(label, back_wins, back_losses, back_odds):
            # Lay: wins when back loses, loses when back wins
            lay_wins   = back_losses
            lay_losses = back_wins
            total = lay_wins + lay_losses
            if total == 0:
                return label, total, back_odds, lay_wins, lay_losses, 0.0, 0.0
            # Lay profit: win +1 unit per win, lose (odds-1) per loss
            profit = lay_wins - (lay_losses * (back_odds - 1.0))
            profit = round(profit, 1)
            roi_pct = round((profit / total) * 100, 2)
            return label, total, back_odds, lay_wins, lay_losses, profit, roi_pct

        # ── Match outcome counts from filtered data ───────────────────────────
        hg = pd.to_numeric(filtered["home_goals_ft"], errors="coerce").fillna(0)
        ag = pd.to_numeric(filtered["away_goals_ft"], errors="coerce").fillna(0)
        tg = hg + ag

        home_wins_n  = int((hg > ag).sum())
        draw_n       = int((hg == ag).sum())
        away_wins_n  = int((hg < ag).sum())

        over15_n = int((tg >= 2).sum())
        over25_n = int((tg >= 3).sum())
        over35_n = int((tg >= 4).sum())
        over45_n = int((tg >= 5).sum())

        btts_y_n = int(((hg > 0) & (ag > 0)).sum())
        btts_n_n = n - btts_y_n

        def _roi_entry(row):
            label, _total, odds, _wins, _losses, profit, roi_pct = row
            return {"name": label, "roi": roi_pct, "profit": profit, "odds": odds}

        def _ou_entry(row):
            label, _total, odds, wins, losses, profit, roi_pct = row
            return {
                "name": label,
                "odds": odds,
                "wins": losses,
                "losses": wins,
                "roi": roi_pct,
                "profit": profit,
            }

        roi_data = {
            "1x2_back": [
                _roi_entry(calc_roi_row("Back Casa", home_wins_n, n - home_wins_n, avg_odds_home)),
                _roi_entry(calc_roi_row("Back Pareggio", draw_n, n - draw_n, avg_odds_draw)),
                _roi_entry(calc_roi_row("Back Trasferta", away_wins_n, n - away_wins_n, avg_odds_away)),
            ],
            "1x2_lay": [
                _roi_entry(calc_lay_row("Lay Casa", home_wins_n, n - home_wins_n, avg_odds_home)),
                _roi_entry(calc_lay_row("Lay Pareggio", draw_n, n - draw_n, avg_odds_draw)),
                _roi_entry(calc_lay_row("Lay Trasferta", away_wins_n, n - away_wins_n, avg_odds_away)),
            ],
            "over_under": [
                _ou_entry(calc_roi_row("Over 1.5", over15_n, n - over15_n, avg_odds_over15)),
                _ou_entry(calc_roi_row("Over 2.5", over25_n, n - over25_n, avg_odds_over25)),
                _ou_entry(calc_roi_row("Over 3.5", over35_n, n - over35_n, avg_odds_over35)),
                _ou_entry(calc_roi_row("Over 4.5", over45_n, n - over45_n, avg_odds_over45)),
            ],
            "btts": [
                _roi_entry(calc_roi_row("BTTS Yes", btts_y_n, n - btts_y_n, avg_odds_btts_y)),
                _roi_entry(calc_roi_row("BTTS No", btts_n_n, n - btts_n_n, avg_odds_btts_n)),
            ],
        }

        render_roi_dashboard(roi_data)

    if _pm_show("Squadre & Export"):
        import plotly.graph_objects as go
        # ═══════════════════════════════════════════
        # SEZIONE 09 — PERFORMANCE SQUADRE
        # ═══════════════════════════════════════════
        home_team_sel = filters.get("home_team")
        away_team_sel = filters.get("away_team")
    
        if home_team_sel:
            _section_header(
                "09", "Performance Squadre",
                "Forma recente, statistiche e indice di pericolosità",
                color="#3b82f6",
            )
            def get_team_recent_stats(team_name, source_df):
                t_matches = source_df[(source_df["home_team"] == team_name) | (source_df["away_team"] == team_name)].copy()
                if "match_date" in t_matches.columns:
                    t_matches = t_matches.sort_values(by="match_date", ascending=False)
                elif "timestamp" in t_matches.columns:
                    t_matches = t_matches.sort_values(by="timestamp", ascending=False)
                else:
                    t_matches = t_matches.sort_values(by="match_id", ascending=False)
                
                t_matches = t_matches.head(20)
                n_t = len(t_matches)
                if n_t == 0:
                    return None
                
                wins = 0
                draws = 0
                losses = 0
                goals_scored = 0
                goals_conceded = 0
                points = 0
                over_25_count = 0
                btts_count = 0
                clean_sheets = 0
            
                intervals_goals = {"1-15": 0, "16-30": 0, "31-45": 0, "46-60": 0, "61-75": 0, "76-90": 0}
                sot_total = 0.0
            
                recent_mids = list(t_matches["match_id"].dropna().astype(int))
                recent_events = get_goal_events_for_matches(recent_mids)
            
                for _, row in t_matches.iterrows():
                    mid = int(row["match_id"])
                    h_goals = pd.to_numeric(row.get("home_goals_ft", 0), errors="coerce")
                    a_goals = pd.to_numeric(row.get("away_goals_ft", 0), errors="coerce")
                    is_home = (row["home_team"] == team_name)
                
                    scored = h_goals if is_home else a_goals
                    conceded = a_goals if is_home else h_goals
                
                    goals_scored += scored
                    goals_conceded += conceded
                
                    sot_col = "home_shots_on_target" if is_home else "away_shots_on_target"
                    sot = pd.to_numeric(row.get(sot_col, 0), errors="coerce")
                    if pd.notna(sot):
                        sot_total += sot
                
                    if h_goals > a_goals:
                        res = "H"
                    elif h_goals == a_goals:
                        res = "D"
                    else:
                        res = "A"
                    
                    if (res == "H" and is_home) or (res == "A" and not is_home):
                        wins += 1
                        points += 3
                    elif res == "D":
                        draws += 1
                        points += 1
                    else:
                        losses += 1
                    
                    if (h_goals + a_goals) > 2.5:
                        over_25_count += 1
                    if h_goals > 0 and a_goals > 0:
                        btts_count += 1
                    if conceded == 0:
                        clean_sheets += 1
                    
                    events = recent_events.get(mid, [])
                    for e in events:
                        goal_by_our_team = (e["is_home"] == 1 and is_home) or (e["is_home"] == 0 and not is_home)
                        if goal_by_our_team:
                            m = e["minute"]
                            if 1 <= m <= 15:
                                intervals_goals["1-15"] += 1
                            elif 16 <= m <= 30:
                                intervals_goals["16-30"] += 1
                            elif 31 <= m <= 45:
                                intervals_goals["31-45"] += 1
                            elif 46 <= m <= 60:
                                intervals_goals["46-60"] += 1
                            elif 61 <= m <= 75:
                                intervals_goals["61-75"] += 1
                            elif 76 <= m:
                                intervals_goals["76-90"] += 1
                            
                return {
                    "n_matches": n_t,
                    "wins": wins,
                    "draws": draws,
                    "losses": losses,
                    "goals_scored": goals_scored,
                    "goals_conceded": goals_conceded,
                    "points": points,
                    "avg_scored": float(goals_scored) / n_t,
                    "avg_conceded": float(goals_conceded) / n_t,
                    "avg_sot": float(sot_total) / n_t,
                    "points_avg": float(points) / n_t,
                    "over_25_pct": float(over_25_count) / n_t * 100,
                    "btts_pct": float(btts_count) / n_t * 100,
                    "cs_pct": float(clean_sheets) / n_t * 100,
                    "intervals": intervals_goals
                }
            
            h_stats = get_team_recent_stats(home_team_sel, df)
            a_stats = get_team_recent_stats(away_team_sel, df) if away_team_sel else None
        
            if h_stats and a_stats:
                st.markdown(
                    '<div style="font-size:12px; font-weight:700; color:#94a3b8; text-transform:uppercase; '
                    'letter-spacing:0.6px; margin:8px 0 10px 0;">Ultime 20 partite</div>',
                    unsafe_allow_html=True,
                )
                col_l, col_c, col_r = st.columns(3)
            
                with col_l:
                    st.html(f"""
                    <div class="pm-box" style="height:100%; display:flex; flex-direction:column; justify-content:space-between;">
                        <div style="font-size:14px; font-weight:700; color:#3b82f6; text-transform:uppercase; margin-bottom:12px;">
                            🔵 {home_team_sel} (Ultimi {h_stats['n_matches']} match)
                        </div>
                        <div style="display:grid; grid-template-columns:repeat(6, 1fr); gap:4px; text-align:center; margin-bottom:12px;">
                            <div style="background:#1e293b; border-radius:4px; padding:4px 2px;">
                                <div style="font-size:8px; color:#94a3b8; font-weight:600; text-transform:uppercase;">WIN</div>
                                <div style="font-size:14px; font-weight:bold; color:#22c55e;">{h_stats['wins']}</div>
                                <div style="font-size:8px; color:#64748b;">{h_stats['wins']/h_stats['n_matches']*100:.0f}%</div>
                            </div>
                            <div style="background:#1e293b; border-radius:4px; padding:4px 2px;">
                                <div style="font-size:8px; color:#94a3b8; font-weight:600; text-transform:uppercase;">DRW</div>
                                <div style="font-size:14px; font-weight:bold; color:#f59e0b;">{h_stats['draws']}</div>
                                <div style="font-size:8px; color:#64748b;">{h_stats['draws']/h_stats['n_matches']*100:.0f}%</div>
                            </div>
                            <div style="background:#1e293b; border-radius:4px; padding:4px 2px;">
                                <div style="font-size:8px; color:#94a3b8; font-weight:600; text-transform:uppercase;">LOS</div>
                                <div style="font-size:14px; font-weight:bold; color:#ef4444;">{h_stats['losses']}</div>
                                <div style="font-size:8px; color:#64748b;">{h_stats['losses']/h_stats['n_matches']*100:.0f}%</div>
                            </div>
                            <div style="background:#1e293b; border-radius:4px; padding:4px 2px;">
                                <div style="font-size:8px; color:#94a3b8; font-weight:600; text-transform:uppercase;">GF</div>
                                <div style="font-size:14px; font-weight:bold; color:#cbd5e1;">{int(h_stats['goals_scored'])}</div>
                                <div style="font-size:8px; color:#64748b;">{h_stats['avg_scored']:.1f}/g</div>
                            </div>
                            <div style="background:#1e293b; border-radius:4px; padding:4px 2px;">
                                <div style="font-size:8px; color:#94a3b8; font-weight:600; text-transform:uppercase;">GS</div>
                                <div style="font-size:14px; font-weight:bold; color:#cbd5e1;">{int(h_stats['goals_conceded'])}</div>
                                <div style="font-size:8px; color:#64748b;">{h_stats['avg_conceded']:.1f}/g</div>
                            </div>
                            <div style="background:#1e293b; border-radius:4px; padding:4px 2px;">
                                <div style="font-size:8px; color:#94a3b8; font-weight:600; text-transform:uppercase;">PTS</div>
                                <div style="font-size:14px; font-weight:bold; color:#cbd5e1;">{h_stats['points']}</div>
                                <div style="font-size:8px; color:#64748b;">{h_stats['points_avg']:.1f}/g</div>
                            </div>
                        </div>
                    
                        <div style="display:grid; grid-template-columns:repeat(3, 1fr); gap:6px; text-align:center; margin-bottom:12px;">
                            <div style="background:#1e293b; border-radius:6px; padding:8px 4px;">
                                <div style="font-size:8px; color:#94a3b8; font-weight:600;">OVER 2.5</div>
                                <div style="font-size:16px; font-weight:bold; color:#3b82f6;">{h_stats['over_25_pct']:.1f}%</div>
                            </div>
                            <div style="background:#1e293b; border-radius:6px; padding:8px 4px;">
                                <div style="font-size:8px; color:#94a3b8; font-weight:600;">BTTS</div>
                                <div style="font-size:16px; font-weight:bold; color:#3b82f6;">{h_stats['btts_pct']:.1f}%</div>
                            </div>
                            <div style="background:#1e293b; border-radius:6px; padding:8px 4px;">
                                <div style="font-size:8px; color:#94a3b8; font-weight:600;">CLEAN SH.</div>
                                <div style="font-size:16px; font-weight:bold; color:#3b82f6;">{h_stats['cs_pct']:.1f}%</div>
                            </div>
                        </div>
                    </div>
                    """)
                
                    fig_mini_h = go.Figure(go.Bar(
                        x=list(h_stats['intervals'].keys()),
                        y=list(h_stats['intervals'].values()),
                        marker_color="#3b82f6",
                        text=list(h_stats['intervals'].values()),
                        textposition="outside"
                    ))
                    fig_mini_h.update_layout(
                        title=dict(text="Gol segnati per intervallo", font=dict(color="#94a3b8", size=10)),
                        margin=dict(t=30, b=10, l=5, r=5),
                        height=130,
                        plot_bgcolor="rgba(0,0,0,0)",
                        paper_bgcolor="rgba(0,0,0,0)",
                        showlegend=False,
                        xaxis=dict(showgrid=False, tickfont=dict(color='#64748b', size=8)),
                        yaxis=dict(visible=False)
                    )
                    st.plotly_chart(fig_mini_h, width="stretch", key="pm_add_mini_h")
                
                with col_r:
                    st.html(f"""
                    <div class="pm-box" style="height:100%; display:flex; flex-direction:column; justify-content:space-between;">
                        <div style="font-size:14px; font-weight:700; color:#ef4444; text-transform:uppercase; margin-bottom:12px;">
                            🔴 {away_team_sel} (Ultimi {a_stats['n_matches']} match)
                        </div>
                        <div style="display:grid; grid-template-columns:repeat(6, 1fr); gap:4px; text-align:center; margin-bottom:12px;">
                            <div style="background:#1e293b; border-radius:4px; padding:4px 2px;">
                                <div style="font-size:8px; color:#94a3b8; font-weight:600; text-transform:uppercase;">WIN</div>
                                <div style="font-size:14px; font-weight:bold; color:#22c55e;">{a_stats['wins']}</div>
                                <div style="font-size:8px; color:#64748b;">{a_stats['wins']/a_stats['n_matches']*100:.0f}%</div>
                            </div>
                            <div style="background:#1e293b; border-radius:4px; padding:4px 2px;">
                                <div style="font-size:8px; color:#94a3b8; font-weight:600; text-transform:uppercase;">DRW</div>
                                <div style="font-size:14px; font-weight:bold; color:#f59e0b;">{a_stats['draws']}</div>
                                <div style="font-size:8px; color:#64748b;">{a_stats['draws']/a_stats['n_matches']*100:.0f}%</div>
                            </div>
                            <div style="background:#1e293b; border-radius:4px; padding:4px 2px;">
                                <div style="font-size:8px; color:#94a3b8; font-weight:600; text-transform:uppercase;">LOS</div>
                                <div style="font-size:14px; font-weight:bold; color:#ef4444;">{a_stats['losses']}</div>
                                <div style="font-size:8px; color:#64748b;">{a_stats['losses']/a_stats['n_matches']*100:.0f}%</div>
                            </div>
                            <div style="background:#1e293b; border-radius:4px; padding:4px 2px;">
                                <div style="font-size:8px; color:#94a3b8; font-weight:600; text-transform:uppercase;">GF</div>
                                <div style="font-size:14px; font-weight:bold; color:#cbd5e1;">{int(a_stats['goals_scored'])}</div>
                                <div style="font-size:8px; color:#64748b;">{a_stats['avg_scored']:.1f}/g</div>
                            </div>
                            <div style="background:#1e293b; border-radius:4px; padding:4px 2px;">
                                <div style="font-size:8px; color:#94a3b8; font-weight:600; text-transform:uppercase;">GS</div>
                                <div style="font-size:14px; font-weight:bold; color:#cbd5e1;">{int(a_stats['goals_conceded'])}</div>
                                <div style="font-size:8px; color:#64748b;">{a_stats['avg_conceded']:.1f}/g</div>
                            </div>
                            <div style="background:#1e293b; border-radius:4px; padding:4px 2px;">
                                <div style="font-size:8px; color:#94a3b8; font-weight:600; text-transform:uppercase;">PTS</div>
                                <div style="font-size:14px; font-weight:bold; color:#cbd5e1;">{a_stats['points']}</div>
                                <div style="font-size:8px; color:#64748b;">{a_stats['points_avg']:.1f}/g</div>
                            </div>
                        </div>
                    
                        <div style="display:grid; grid-template-columns:repeat(3, 1fr); gap:6px; text-align:center; margin-bottom:12px;">
                            <div style="background:#1e293b; border-radius:6px; padding:8px 4px;">
                                <div style="font-size:8px; color:#94a3b8; font-weight:600;">OVER 2.5</div>
                                <div style="font-size:16px; font-weight:bold; color:#ef4444;">{a_stats['over_25_pct']:.1f}%</div>
                            </div>
                            <div style="background:#1e293b; border-radius:6px; padding:8px 4px;">
                                <div style="font-size:8px; color:#94a3b8; font-weight:600;">BTTS</div>
                                <div style="font-size:16px; font-weight:bold; color:#ef4444;">{a_stats['btts_pct']:.1f}%</div>
                            </div>
                            <div style="background:#1e293b; border-radius:6px; padding:8px 4px;">
                                <div style="font-size:8px; color:#94a3b8; font-weight:600;">CLEAN SH.</div>
                                <div style="font-size:16px; font-weight:bold; color:#ef4444;">{a_stats['cs_pct']:.1f}%</div>
                            </div>
                        </div>
                    </div>
                    """)
                
                    fig_mini_a = go.Figure(go.Bar(
                        x=list(a_stats['intervals'].keys()),
                        y=list(a_stats['intervals'].values()),
                        marker_color="#ef4444",
                        text=list(a_stats['intervals'].values()),
                        textposition="outside"
                    ))
                    fig_mini_a.update_layout(
                        title=dict(text="Gol segnati per intervallo", font=dict(color="#94a3b8", size=10)),
                        margin=dict(t=30, b=10, l=5, r=5),
                        height=130,
                        plot_bgcolor="rgba(0,0,0,0)",
                        paper_bgcolor="rgba(0,0,0,0)",
                        showlegend=False,
                        xaxis=dict(showgrid=False, tickfont=dict(color='#64748b', size=8)),
                        yaxis=dict(visible=False)
                    )
                    st.plotly_chart(fig_mini_a, width="stretch", key="pm_add_mini_a")
                
                with col_c:
                    st.markdown("<div style='text-align:center; font-size:11px; font-weight:700; color:#cbd5e1; margin-bottom:8px;'>CONFRONTO RILEVANTE</div>", unsafe_allow_html=True)
                
                    y_labels = [
                        "Punti / Partita",
                        "BTTS %",
                        "Over 2.5 %",
                        "Clean Sheet %",
                        "Subiti / Partita",
                        "Fatti / Partita"
                    ]
                
                    h_text = [f"{h_stats['points_avg']:.2f}", f"{h_stats['btts_pct']:.1f}%", f"{h_stats['over_25_pct']:.1f}%", f"{h_stats['cs_pct']:.1f}%", f"{h_stats['avg_conceded']:.2f}", f"{h_stats['avg_scored']:.2f}"]
                    a_text = [f"{a_stats['points_avg']:.2f}", f"{a_stats['btts_pct']:.1f}%", f"{a_stats['over_25_pct']:.1f}%", f"{a_stats['cs_pct']:.1f}%", f"{a_stats['avg_conceded']:.2f}", f"{a_stats['avg_scored']:.2f}"]
                
                    h_widths = [h_stats['points_avg'], h_stats['btts_pct']/20.0, h_stats['over_25_pct']/20.0, h_stats['cs_pct']/20.0, h_stats['avg_conceded'], h_stats['avg_scored']]
                    a_widths = [a_stats['points_avg'], a_stats['btts_pct']/20.0, a_stats['over_25_pct']/20.0, a_stats['cs_pct']/20.0, a_stats['avg_conceded'], a_stats['avg_scored']]
                
                    h_widths_neg = [-w for w in h_widths]
                
                    fig_comp = go.Figure()
                    fig_comp.add_trace(go.Bar(
                        y=y_labels,
                        x=h_widths_neg,
                        orientation='h',
                        name=home_team_sel,
                        marker_color='#3b82f6',
                        text=h_text,
                        textposition='inside',
                        insidetextanchor='end',
                        hoverinfo='none'
                    ))
                    fig_comp.add_trace(go.Bar(
                        y=y_labels,
                        x=a_widths,
                        orientation='h',
                        name=away_team_sel,
                        marker_color='#ef4444',
                        text=a_text,
                        textposition='inside',
                        insidetextanchor='start',
                        hoverinfo='none'
                    ))
                    fig_comp.update_layout(
                        barmode='relative',
                        height=300,
                        margin=dict(t=10, b=10, l=5, r=5),
                        plot_bgcolor="rgba(0,0,0,0)",
                        paper_bgcolor="rgba(0,0,0,0)",
                        showlegend=False,
                        xaxis=dict(showgrid=False, zeroline=True, zerolinecolor='#334155', showticklabels=False),
                        yaxis=dict(showgrid=False, tickfont=dict(color='#cbd5e1', size=9), position=0.5)
                    )
                    st.plotly_chart(fig_comp, width="stretch", key="pm_add_confronto_bar")
                
            st.markdown(
                '<div style="font-size:12px; font-weight:700; color:#94a3b8; text-transform:uppercase; '
                'letter-spacing:0.6px; margin:16px 0 8px 0;">Indice di pericolosità</div>',
                unsafe_allow_html=True,
            )

            # Formula uses filtered H2H match data (results dict)
            # Danger = ((avg_goals/4)*0.4 + over_2.5*0.3 + btts*0.2 + over_0.5*0.1) * 2
            _avg_goals   = results.get("avg_goals_ft", 0.0)
            _over_25     = results.get("over_25_ft_pct", 0.0) / 100.0
            _btts        = results.get("btts_pct", 0.0) / 100.0
            # over_0.5 ft = at least 1 goal scored in the match
            _over_05_ft  = results.get("over_05_ft_pct", 0.0) / 100.0
            if _over_05_ft == 0.0:
                # fallback: calculate from goal distribution
                _zero_goal_matches = g_dist.get(0, 0)
                _over_05_ft = (n - _zero_goal_matches) / n if n > 0 else 0.0

            danger_index = (
                (_avg_goals / 4.0) * 0.4 +
                _over_25 * 0.3 +
                _btts * 0.2 +
                _over_05_ft * 0.1
            ) * 2.0
            danger_index = round(min(danger_index, 2.0), 2)

            if danger_index >= 1.4:
                d_label = "ALTO"
                d_color = "#ef4444"
                d_gauge_color = "#ef4444"
            elif danger_index >= 0.8:
                d_label = "MEDIO"
                d_color = "#f59e0b"
                d_gauge_color = "#f59e0b"
            else:
                d_label = "BASSO"
                d_color = "#22c55e"
                d_gauge_color = "#22c55e"

            col_gauge_l, col_gauge_c, col_gauge_r = st.columns([1, 2, 1])
            with col_gauge_c:
                st.html(f"""
                <div class="pm-box" style="text-align:center; padding:16px 16px 4px 16px;">
                    <div style="font-size:11px; font-weight:700; color:#94a3b8; text-transform:uppercase; letter-spacing:1px; margin-bottom:6px;">
                        Indice di Pericolosità — {n} Partite Filtrate
                    </div>
                    <div style="font-size:22px; font-weight:800; color:{d_color}; text-transform:uppercase; letter-spacing:2px;">
                        {d_label}
                    </div>
                    <div style="font-size:11px; color:#64748b; margin-top:4px;">
                        Scala: 0 (bassa) — 2 (alta)
                    </div>
                </div>
                """)
                fig_danger = go.Figure(go.Indicator(
                    mode="gauge+number",
                    value=danger_index,
                    number={'font': {'color': d_color, 'size': 48}},
                    domain={'x': [0, 1], 'y': [0, 1]},
                    gauge={
                        'axis': {
                            'range': [0, 2],
                            'tickwidth': 1,
                            'tickcolor': "#cbd5e1",
                            'tickvals': [0, 0.4, 0.8, 1.2, 1.6, 2.0],
                        },
                        'bar': {'color': d_gauge_color},
                        'bgcolor': "#1e293b",
                        'borderwidth': 2,
                        'bordercolor': "#1f2937",
                        'steps': [
                            {'range': [0, 0.8],  'color': 'rgba(34, 197, 94, 0.12)'},
                            {'range': [0.8, 1.4], 'color': 'rgba(245, 158, 11, 0.12)'},
                            {'range': [1.4, 2.0], 'color': 'rgba(239, 68, 68, 0.12)'}
                        ],
                        'threshold': {
                            'line': {'color': d_gauge_color, 'width': 3},
                            'thickness': 0.75,
                            'value': danger_index
                        }
                    }
                ))
                fig_danger.update_layout(
                    height=220,
                    margin=dict(t=10, b=10, l=30, r=30),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#e2e8f0")
                )
                st.plotly_chart(fig_danger, use_container_width=True, key="pm_danger_gauge")

        if home_team_sel and away_team_sel and home_team_sel != "Tutte" and away_team_sel != "Tutte":
            _section_header(
                "10", "Confronto Globale & Head-to-Head",
                "Performance su tutto il database e serie storica tra le due squadre",
                color="#ef4444",
            )
            st.markdown(
                '<div style="font-size:12px; font-weight:700; color:#94a3b8; text-transform:uppercase; '
                'letter-spacing:0.6px; margin:8px 0 10px 0;">Performance su intero database</div>',
                unsafe_allow_html=True,
            )
        
            full_df = get_matches_dataframe()
        
            home_all = get_team_stats_all_competitions(full_df, home_team_sel)
            away_all = get_team_stats_all_competitions(full_df, away_team_sel)
        
            col_h, col_mid, col_a = st.columns([2, 1.5, 2])
        
            with col_h:
                st.html(f"""
                <div class="pm-box" style="height:100%; display:flex; flex-direction:column; justify-content:space-between;">
                    <div style="font-size:14px; font-weight:700; color:#3b82f6; text-transform:uppercase; margin-bottom:12px;">
                        🔵 {home_team_sel} — Tutte le Competizioni
                    </div>
                    <div style="display:grid; grid-template-columns:repeat(7, 1fr); gap:4px; text-align:center; margin-bottom:12px;">
                        <div style="background:#1e293b; border-radius:4px; padding:4px 2px;">
                            <div style="font-size:8px; color:#94a3b8; font-weight:600; text-transform:uppercase;">MAT</div>
                            <div style="font-size:14px; font-weight:bold; color:#cbd5e1;">{home_all.get('total_matches', 0)}</div>
                        </div>
                        <div style="background:#1e293b; border-radius:4px; padding:4px 2px;">
                            <div style="font-size:8px; color:#94a3b8; font-weight:600; text-transform:uppercase;">WIN</div>
                            <div style="font-size:14px; font-weight:bold; color:#22c55e;">{home_all.get('wins', 0)}</div>
                        </div>
                        <div style="background:#1e293b; border-radius:4px; padding:4px 2px;">
                            <div style="font-size:8px; color:#94a3b8; font-weight:600; text-transform:uppercase;">DRW</div>
                            <div style="font-size:14px; font-weight:bold; color:#f59e0b;">{home_all.get('draws', 0)}</div>
                        </div>
                        <div style="background:#1e293b; border-radius:4px; padding:4px 2px;">
                            <div style="font-size:8px; color:#94a3b8; font-weight:600; text-transform:uppercase;">LOS</div>
                            <div style="font-size:14px; font-weight:bold; color:#ef4444;">{home_all.get('losses', 0)}</div>
                        </div>
                        <div style="background:#1e293b; border-radius:4px; padding:4px 2px;">
                            <div style="font-size:8px; color:#94a3b8; font-weight:600; text-transform:uppercase;">GF</div>
                            <div style="font-size:12px; font-weight:bold; color:#cbd5e1;">{int(home_all.get('goals_scored_avg', 0) * home_all.get('total_matches', 0))}</div>
                            <div style="font-size:8px; color:#64748b;">{home_all.get('goals_scored_avg', 0.0):.1f}/g</div>
                        </div>
                        <div style="background:#1e293b; border-radius:4px; padding:4px 2px;">
                            <div style="font-size:8px; color:#94a3b8; font-weight:600; text-transform:uppercase;">GS</div>
                            <div style="font-size:12px; font-weight:bold; color:#cbd5e1;">{int(away_all.get('goals_conceded_avg', 0) * away_all.get('total_matches', 0))}</div>
                            <div style="font-size:8px; color:#64748b;">{home_all.get('goals_conceded_avg', 0.0):.1f}/g</div>
                        </div>
                        <div style="background:#1e293b; border-radius:4px; padding:4px 2px;">
                            <div style="font-size:8px; color:#94a3b8; font-weight:600; text-transform:uppercase;">PTS</div>
                            <div style="font-size:14px; font-weight:bold; color:#cbd5e1;">{home_all.get('points', 0)}</div>
                        </div>
                    </div>
                </div>
                """)
            
                col_p1, col_p2, col_p3 = st.columns(3)
                with col_p1:
                    val = home_all.get('over_25_pct', 0.0)
                    color = get_pct_color(val)
                    st.markdown(f"""
                    <div style="background:#1e293b; border-radius:6px; padding:8px 4px; text-align:center;">
                        <div style="font-size:8px; color:#94a3b8; font-weight:600;">OVER 2.5</div>
                        <p style="color:{color}; font-size:1.1rem; font-weight:bold; margin:0;">{val:.1f}%</p>
                    </div>
                    """, unsafe_allow_html=True)
                with col_p2:
                    val = home_all.get('btts_pct', 0.0)
                    color = get_pct_color(val)
                    st.markdown(f"""
                    <div style="background:#1e293b; border-radius:6px; padding:8px 4px; text-align:center;">
                        <div style="font-size:8px; color:#94a3b8; font-weight:600;">BTTS</div>
                        <p style="color:{color}; font-size:1.1rem; font-weight:bold; margin:0;">{val:.1f}%</p>
                    </div>
                    """, unsafe_allow_html=True)
                with col_p3:
                    val = home_all.get('clean_sheet_pct', 0.0)
                    color = get_pct_color(val)
                    st.markdown(f"""
                    <div style="background:#1e293b; border-radius:6px; padding:8px 4px; text-align:center;">
                        <div style="font-size:8px; color:#94a3b8; font-weight:600;">CLEAN SH.</div>
                        <p style="color:{color}; font-size:1.1rem; font-weight:bold; margin:0;">{val:.1f}%</p>
                    </div>
                    """, unsafe_allow_html=True)
                
                fig_mini_h = go.Figure(go.Bar(
                    x=list(home_all.get('goals_per_interval', {}).keys()),
                    y=list(home_all.get('goals_per_interval', {}).values()),
                    marker_color="#3b82f6",
                    text=[f"{v:.2f}" for v in home_all.get('goals_per_interval', {}).values()],
                    textposition="outside"
                ))
                fig_mini_h.update_layout(
                    title=dict(text="Gol segnati per intervallo", font=dict(color="#94a3b8", size=10)),
                    margin=dict(t=30, b=10, l=5, r=5),
                    height=130,
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)",
                    showlegend=False,
                    xaxis=dict(showgrid=False, tickfont=dict(color='#64748b', size=8)),
                    yaxis=dict(visible=False),
                    font=dict(color="#e2e8f0")
                )
                st.plotly_chart(fig_mini_h, use_container_width=True, key="pm_home_all_interval")
            
            with col_mid:
                st.markdown("<div style='text-align:center; font-size:11px; font-weight:700; color:#cbd5e1; margin-bottom:8px;'>CONFRONTO GLOBALE</div>", unsafe_allow_html=True)
            
                y_labels = [
                    "Punti / Partita",
                    "BTTS %",
                    "Over 2.5 %",
                    "Clean Sheet %",
                    "Subiti / Partita",
                    "Fatti / Partita"
                ]
            
                h_pts_avg = home_all.get("points", 0) / home_all.get("total_matches", 1) if home_all.get("total_matches", 0) > 0 else 0.0
                a_pts_avg = away_all.get("points", 0) / away_all.get("total_matches", 1) if away_all.get("total_matches", 0) > 0 else 0.0
            
                h_text = [
                    f"{h_pts_avg:.2f}",
                    f"{home_all.get('btts_pct', 0.0):.1f}%",
                    f"{home_all.get('over_25_pct', 0.0):.1f}%",
                    f"{home_all.get('clean_sheet_pct', 0.0):.1f}%",
                    f"{home_all.get('goals_conceded_avg', 0.0):.2f}",
                    f"{home_all.get('goals_scored_avg', 0.0):.2f}"
                ]
                a_text = [
                    f"{a_pts_avg:.2f}",
                    f"{away_all.get('btts_pct', 0.0):.1f}%",
                    f"{away_all.get('over_25_pct', 0.0):.1f}%",
                    f"{away_all.get('clean_sheet_pct', 0.0):.1f}%",
                    f"{away_all.get('goals_conceded_avg', 0.0):.2f}",
                    f"{away_all.get('goals_scored_avg', 0.0):.2f}"
                ]
            
                h_widths = [
                    h_pts_avg,
                    home_all.get('btts_pct', 0.0)/20.0,
                    home_all.get('over_25_pct', 0.0)/20.0,
                    home_all.get('clean_sheet_pct', 0.0)/20.0,
                    home_all.get('goals_conceded_avg', 0.0),
                    home_all.get('goals_scored_avg', 0.0)
                ]
                a_widths = [
                    a_pts_avg,
                    away_all.get('btts_pct', 0.0)/20.0,
                    away_all.get('over_25_pct', 0.0)/20.0,
                    away_all.get('clean_sheet_pct', 0.0)/20.0,
                    away_all.get('goals_conceded_avg', 0.0),
                    away_all.get('goals_scored_avg', 0.0)
                ]
            
                h_widths_neg = [-w for w in h_widths]
            
                fig_comp = go.Figure()
                fig_comp.add_trace(go.Bar(
                    y=y_labels,
                    x=h_widths_neg,
                    orientation='h',
                    name=home_team_sel,
                    marker_color='#3b82f6',
                    text=h_text,
                    textposition='inside',
                    insidetextanchor='end',
                    hoverinfo='none'
                ))
                fig_comp.add_trace(go.Bar(
                    y=y_labels,
                    x=a_widths,
                    orientation='h',
                    name=away_team_sel,
                    marker_color='#ef4444',
                    text=a_text,
                    textposition='inside',
                    insidetextanchor='start',
                    hoverinfo='none'
                ))
                fig_comp.update_layout(
                    barmode='relative',
                    height=300,
                    margin=dict(t=10, b=10, l=5, r=5),
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)",
                    showlegend=False,
                    xaxis=dict(showgrid=False, zeroline=True, zerolinecolor='#334155', showticklabels=False),
                    yaxis=dict(showgrid=False, tickfont=dict(color='#cbd5e1', size=9), position=0.5),
                    font=dict(color="#cbd5e1")
                )
                st.plotly_chart(fig_comp, use_container_width=True, key="pm_comparison_all")
            
            with col_a:
                st.html(f"""
                <div class="pm-box" style="height:100%; display:flex; flex-direction:column; justify-content:space-between;">
                    <div style="font-size:14px; font-weight:700; color:#ef4444; text-transform:uppercase; margin-bottom:12px;">
                        🔴 {away_team_sel} — Tutte le Competizioni
                    </div>
                    <div style="display:grid; grid-template-columns:repeat(7, 1fr); gap:4px; text-align:center; margin-bottom:12px;">
                        <div style="background:#1e293b; border-radius:4px; padding:4px 2px;">
                            <div style="font-size:8px; color:#94a3b8; font-weight:600; text-transform:uppercase;">MAT</div>
                            <div style="font-size:14px; font-weight:bold; color:#cbd5e1;">{away_all.get('total_matches', 0)}</div>
                        </div>
                        <div style="background:#1e293b; border-radius:4px; padding:4px 2px;">
                            <div style="font-size:8px; color:#94a3b8; font-weight:600; text-transform:uppercase;">WIN</div>
                            <div style="font-size:14px; font-weight:bold; color:#22c55e;">{away_all.get('wins', 0)}</div>
                        </div>
                        <div style="background:#1e293b; border-radius:4px; padding:4px 2px;">
                            <div style="font-size:8px; color:#94a3b8; font-weight:600; text-transform:uppercase;">DRW</div>
                            <div style="font-size:14px; font-weight:bold; color:#f59e0b;">{away_all.get('draws', 0)}</div>
                        </div>
                        <div style="background:#1e293b; border-radius:4px; padding:4px 2px;">
                            <div style="font-size:8px; color:#94a3b8; font-weight:600; text-transform:uppercase;">LOS</div>
                            <div style="font-size:14px; font-weight:bold; color:#ef4444;">{away_all.get('losses', 0)}</div>
                        </div>
                        <div style="background:#1e293b; border-radius:4px; padding:4px 2px;">
                            <div style="font-size:8px; color:#94a3b8; font-weight:600; text-transform:uppercase;">GF</div>
                            <div style="font-size:12px; font-weight:bold; color:#cbd5e1;">{int(away_all.get('goals_scored_avg', 0) * away_all.get('total_matches', 0))}</div>
                            <div style="font-size:8px; color:#64748b;">{away_all.get('goals_scored_avg', 0.0):.1f}/g</div>
                        </div>
                        <div style="background:#1e293b; border-radius:4px; padding:4px 2px;">
                            <div style="font-size:8px; color:#94a3b8; font-weight:600; text-transform:uppercase;">GS</div>
                            <div style="font-size:12px; font-weight:bold; color:#cbd5e1;">{int(away_all.get('goals_conceded_avg', 0) * away_all.get('total_matches', 0))}</div>
                            <div style="font-size:8px; color:#64748b;">{away_all.get('goals_conceded_avg', 0.0):.1f}/g</div>
                        </div>
                        <div style="background:#1e293b; border-radius:4px; padding:4px 2px;">
                            <div style="font-size:8px; color:#94a3b8; font-weight:600; text-transform:uppercase;">PTS</div>
                            <div style="font-size:14px; font-weight:bold; color:#cbd5e1;">{away_all.get('points', 0)}</div>
                        </div>
                    </div>
                </div>
                """)
            
                col_ap1, col_ap2, col_ap3 = st.columns(3)
                with col_ap1:
                    val = away_all.get('over_25_pct', 0.0)
                    color = get_pct_color(val)
                    st.markdown(f"""
                    <div style="background:#1e293b; border-radius:6px; padding:8px 4px; text-align:center;">
                        <div style="font-size:8px; color:#94a3b8; font-weight:600;">OVER 2.5</div>
                        <p style="color:{color}; font-size:1.1rem; font-weight:bold; margin:0;">{val:.1f}%</p>
                    </div>
                    """, unsafe_allow_html=True)
                with col_ap2:
                    val = away_all.get('btts_pct', 0.0)
                    color = get_pct_color(val)
                    st.markdown(f"""
                    <div style="background:#1e293b; border-radius:6px; padding:8px 4px; text-align:center;">
                        <div style="font-size:8px; color:#94a3b8; font-weight:600;">BTTS</div>
                        <p style="color:{color}; font-size:1.1rem; font-weight:bold; margin:0;">{val:.1f}%</p>
                    </div>
                    """, unsafe_allow_html=True)
                with col_ap3:
                    val = away_all.get('clean_sheet_pct', 0.0)
                    color = get_pct_color(val)
                    st.markdown(f"""
                    <div style="background:#1e293b; border-radius:6px; padding:8px 4px; text-align:center;">
                        <div style="font-size:8px; color:#94a3b8; font-weight:600;">CLEAN SH.</div>
                        <p style="color:{color}; font-size:1.1rem; font-weight:bold; margin:0;">{val:.1f}%</p>
                    </div>
                    """, unsafe_allow_html=True)
                
                fig_mini_a = go.Figure(go.Bar(
                    x=list(away_all.get('goals_per_interval', {}).keys()),
                    y=list(away_all.get('goals_per_interval', {}).values()),
                    marker_color="#ef4444",
                    text=[f"{v:.2f}" for v in away_all.get('goals_per_interval', {}).values()],
                    textposition="outside"
                ))
                fig_mini_a.update_layout(
                    title=dict(text="Gol segnati per intervallo", font=dict(color="#94a3b8", size=10)),
                    margin=dict(t=30, b=10, l=5, r=5),
                    height=130,
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)",
                    showlegend=False,
                    xaxis=dict(showgrid=False, tickfont=dict(color='#64748b', size=8)),
                    yaxis=dict(visible=False),
                    font=dict(color="#e2e8f0")
                )
                st.plotly_chart(fig_mini_a, use_container_width=True, key="pm_away_all_interval")

            st.markdown(
                '<div style="font-size:12px; font-weight:700; color:#94a3b8; text-transform:uppercase; '
                'letter-spacing:0.6px; margin:20px 0 10px 0;">Serie storica — ultime 10 sfide</div>',
                unsafe_allow_html=True,
            )
        
            h2h_matches = get_last_h2h_matches(home_team_sel, away_team_sel)
            if not h2h_matches:
                st.info("Nessun precedente trovato tra queste due squadre.")
            else:
                h2h_df = pd.DataFrame(h2h_matches)
            
                h2h_df = h2h_df.rename(columns={
                    "match_date": "Data",
                    "home_team": "Casa",
                    "away_team": "Trasferta",
                    "ft_result": "Risultato",
                    "league": "Campionato",
                    "season": "Stagione"
                })
            
                h2h_df = h2h_df[["Data", "Casa", "Risultato", "Trasferta", "Campionato", "Stagione", "home_goals_ft", "away_goals_ft"]]
            
                def style_h2h_rows(row):
                    hg = float(row.get("home_goals_ft", 0) or 0)
                    ag = float(row.get("away_goals_ft", 0) or 0)
                    styles = [""] * len(row)
                    cols = list(row.index)
                    casa_idx = cols.index("Casa")
                    trasferta_idx = cols.index("Trasferta")
                
                    if hg > ag:
                        styles[casa_idx] = "color: #22c55e; font-weight: bold;"
                        styles[trasferta_idx] = "color: #ef4444;"
                    elif ag > hg:
                        styles[casa_idx] = "color: #ef4444;"
                        styles[trasferta_idx] = "color: #22c55e; font-weight: bold;"
                    else:
                        styles[casa_idx] = "color: #94a3b8;"
                        styles[trasferta_idx] = "color: #94a3b8;"
                    return styles

                styled_h2h = h2h_df.style.apply(style_h2h_rows, axis=1)
                styled_h2h = styled_h2h.hide(["home_goals_ft", "away_goals_ft"], axis="columns")
            
                st.dataframe(styled_h2h, use_container_width=True, hide_index=True, key="pm_h2h_history")


        # ═══════════════════════════════════════════
        # SEZIONE 11 — ESPORTA
        # ═══════════════════════════════════════════
        _section_header(
            "11", "Esporta",
            "Scarica riepilogo, partite filtrate e ROI in Excel",
            color="#64748b",
        )
        buf = _export_excel(results, filtered)
        st.download_button(
            label="📊 Esporta in Excel",
            data=buf,
            file_name="prematch_analysis.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="pm_download_btn",
        )
    
        st.html(f"""
        <div style="text-align:center; font-size:10px; color:#64748b; margin-top:32px;">
            I dati si riferiscono alle partite presenti nel database e possono variare in base ai filtri applicati. 
            — Ultimo aggiornamento: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        </div>
        """)


def _export_excel(results: dict, df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
        summary = {k: v for k, v in results.items() if not isinstance(v, (dict, list, pd.DataFrame))}
        pd.DataFrame([summary]).to_excel(writer, sheet_name="Riepilogo", index=False)
        preferred_cols = ["match_date", "home_team", "away_team", "ft_result", "ht_result", "total_goals_ft", "odds_home", "odds_draw", "odds_away"]
        export_cols = [c for c in preferred_cols if c in df.columns]
        df[export_cols].to_excel(writer, sheet_name="Partite", index=False)
        roi_export = pd.DataFrame({
            "Scommessa": ["Vittoria Casa", "Lay Casa", "Over 0.5 2T", "Lay 0-0"],
            "Vincite": [results.get("roi_home_wins", 0), results.get("roi_lay_home_wins", 0), results.get("roi_2h_wins", 0), results.get("roi_00_wins", 0)],
            "Perdite": [results.get("roi_home_losses", 0), results.get("roi_lay_home_losses", 0), results.get("roi_2h_losses", 0), results.get("roi_00_losses", 0)],
            "ROI": [format_roi(results.get("roi_home_win")), format_roi(results.get("roi_lay_home")), format_roi(results.get("roi_over_05_2h")), format_roi(results.get("roi_lay_00"))],
        })
        roi_export.to_excel(writer, sheet_name="ROI", index=False)
    return buf.getvalue()