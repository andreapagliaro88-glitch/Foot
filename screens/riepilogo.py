"""
screens/riepilogo.py — Dashboard riepilogo: migliori insight da ogni modulo analitico.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database import get_all_matches_unfiltered
from filters import render_filter_sidebar, should_run_analysis, _ALL_LEAGUES_LABEL
from screen_cache import load_prematch_data, build_prematch_frame
from calculations import analyze_matches, enrich_with_goal_events, analyze_h2h, analyze_live_state_v2
from strategy_simulator import find_best_strategy
from team_dna import analyze_team_dna
from match_timeline import (
    build_timeline,
    build_intensity_zones,
    calculate_timeline_kpi,
    calculate_first_goal_avg,
    detect_key_moments,
    generate_timeline_insight,
)
from utils import get_pct_color, team_logo_html
from screens.match_header import compute_header_insights, render_premium_header
from screens.momentum_chart import render_similar_momentum_block
from screens.match_timeline import (
    _plot_timeline_bars,
    _plot_zone_heatmap,
    _metric_card,
)
from screens.h2h import (
    _filter_h2h_matches,
    _summary_card,
    _donut_chart,
    _over_under_bars,
    _insights_html,
)
from screens.first_goal_chart import build_first_goal_data, render_first_goal_chart

C_BG = "#111827"
C_BORDER = "#1f2937"
C_TEXT = "#f1f5f9"
C_MUTED = "#94a3b8"
C_MUTED2 = "#64748b"
C_CYAN = "#38bdf8"
C_GREEN = "#22c55e"
C_RED = "#ef4444"
C_PURPLE = "#a855f7"
C_AMBER = "#f59e0b"

_PLOTLY_CONFIG = {"displayModeBar": False}


def _inject_styles():
    if st.session_state.get("_riepilogo_css"):
        return
    st.session_state._riepilogo_css = True
    st.html(f"""
    <style>
        .rp-hero {{
            background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 50%, #0f172a 100%);
            border: 1px solid {C_BORDER}; border-radius: 12px;
            padding: 20px 24px; margin-bottom: 20px;
        }}
        .rp-section {{
            margin: 28px 0 14px 0; padding-bottom: 10px;
            border-bottom: 1px solid {C_BORDER};
            display: flex; align-items: flex-start; gap: 12px;
        }}
        .rp-badge {{
            font-size: 10px; font-weight: 800; padding: 4px 8px;
            border-radius: 6px; letter-spacing: 0.05em; flex-shrink: 0;
        }}
        .rp-title {{ font-size: 15px; font-weight: 800; color: {C_TEXT}; }}
        .rp-sub {{ font-size: 11px; color: {C_MUTED2}; margin-top: 3px; }}
        .rp-source {{
            font-size: 9px; color: {C_MUTED}; text-transform: uppercase;
            letter-spacing: 0.08em; margin-left: auto; padding-top: 2px;
        }}
        .rp-box {{
            background: {C_BG}; border: 1px solid {C_BORDER};
            border-radius: 8px; padding: 14px 16px; margin-bottom: 14px;
        }}
        div[data-testid="stPlotlyChart"] {{
            background: {C_BG}; border: 1px solid {C_BORDER};
            border-radius: 8px; padding: 2px;
        }}
    </style>
    """)


def _section_header(number: str, title: str, subtitle: str, source: str, color: str, first: bool = False):
    margin = "4px" if first else "28px"
    st.html(f"""
    <div class="rp-section" style="margin-top:{margin};">
        <div class="rp-badge" style="background:{color}22;border:1px solid {color}55;color:{color};">{number}</div>
        <div style="flex:1;">
            <div class="rp-title">{title}</div>
            <div class="rp-sub">{subtitle}</div>
        </div>
        <div class="rp-source">da {source}</div>
    </div>
    """)


def _parse_minute(raw):
    try:
        s = str(raw).strip()
        if "+" in s:
            base, extra = s.split("+", 1)
            return int(base) + int(extra)
        return int(float(s))
    except (ValueError, TypeError):
        return 0


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


def _over_cell(label: str, count: int, n: int, highlight: bool = False) -> str:
    pct = round(count / n * 100, 1) if n > 0 else 0.0
    color = get_pct_color(pct)
    border = f"border-top: 2px solid {color};" if highlight else ""
    return f"""
    <div style="background:#1e293b;border-radius:6px;padding:8px 4px;text-align:center;{border}">
        <div style="font-size:9px;color:#94a3b8;font-weight:700;text-transform:uppercase;
                    letter-spacing:0.8px;margin-bottom:3px;">{label}</div>
        <div style="font-size:18px;font-weight:800;color:{color};line-height:1;">{pct:.1f}%</div>
        <div style="font-size:10px;color:#64748b;margin-top:2px;">{count}/{n}</div>
    </div>
    """


def _render_over_under_grid(filtered: pd.DataFrame, n: int) -> None:
    tg_ht = pd.to_numeric(filtered["total_goals_ht"], errors="coerce").fillna(0)
    tg_2h = pd.to_numeric(filtered["total_goals_2h"], errors="coerce").fillna(0)
    tg_ft = pd.to_numeric(filtered["total_goals_ft"], errors="coerce").fillna(0)
    hg = pd.to_numeric(filtered["home_goals_ft"], errors="coerce").fillna(0)
    ag = pd.to_numeric(filtered["away_goals_ft"], errors="coerce").fillna(0)

    o_cells_ft = "".join([
        _over_cell("O0.5", int((tg_ft >= 1).sum()), n, True),
        _over_cell("O1.5", int((tg_ft >= 2).sum()), n, True),
        _over_cell("O2.5", int((tg_ft >= 3).sum()), n, True),
        _over_cell("O3.5", int((tg_ft >= 4).sum()), n, True),
        _over_cell("O4.5", int((tg_ft >= 5).sum()), n, True),
        _over_cell("BTTS", int(((hg > 0) & (ag > 0)).sum()), n, True),
    ])
    o_cells_1h = "".join([
        _over_cell("1T O0.5", int((tg_ht >= 1).sum()), n),
        _over_cell("1T O1.5", int((tg_ht >= 2).sum()), n),
        _over_cell("1T O2.5", int((tg_ht >= 3).sum()), n),
    ])
    o_cells_2h = "".join([
        _over_cell("2T O0.5", int((tg_2h >= 1).sum()), n),
        _over_cell("2T O1.5", int((tg_2h >= 2).sum()), n),
        _over_cell("2T O2.5", int((tg_2h >= 3).sum()), n),
    ])
    st.html(f"""
    <div class="rp-box">
        <div style="font-size:10px;color:#64748b;font-weight:700;text-transform:uppercase;
                    letter-spacing:1px;margin-bottom:10px;">Over / Under — tempo pieno</div>
        <div style="display:grid;grid-template-columns:repeat(6,1fr);gap:8px;margin-bottom:10px;">{o_cells_ft}</div>
        <div style="border-top:1px solid #1f2937;margin:8px 0;"></div>
        <div style="display:grid;grid-template-columns:auto 1fr 1fr 1fr;gap:8px;margin-bottom:8px;">
            <div style="font-size:9px;color:#64748b;font-weight:700;display:flex;align-items:center;">1° T</div>
            {o_cells_1h}
        </div>
        <div style="display:grid;grid-template-columns:auto 1fr 1fr 1fr;gap:8px;">
            <div style="font-size:9px;color:#64748b;font-weight:700;display:flex;align-items:center;">2° T</div>
            {o_cells_2h}
        </div>
    </div>
    """)


def _goal_dist_fig(g_dist: dict, n: int) -> go.Figure:
    labels = ["0", "1", "2", "3", "4", "5+"]
    counts = [g_dist.get(k, g_dist.get(str(k), 0)) for k in [0, 1, 2, 3, 4, "5+"]]
    pcts = [round(c / n * 100, 1) if n else 0 for c in counts]
    fig = go.Figure(go.Bar(
        x=labels, y=pcts,
        marker_color=[C_CYAN if p >= max(pcts, default=0) * 0.85 else "#334155" for p in pcts],
        text=[f"{p:.1f}%" for p in pcts],
        textposition="outside",
        hovertemplate="%{x} gol → %{y:.1f}%<extra></extra>",
    ))
    fig.update_layout(
        paper_bgcolor=C_BG, plot_bgcolor=C_BG,
        font=dict(color=C_MUTED, size=11),
        margin=dict(l=40, r=20, t=40, b=40),
        height=260,
        title=dict(text="Distribuzione gol a partita", font=dict(color=C_TEXT, size=13)),
        xaxis=dict(title="Gol FT", gridcolor=C_BORDER),
        yaxis=dict(title="%", gridcolor=C_BORDER),
    )
    return fig


def _dna_card(team: str, dna: dict) -> str:
    style = dna.get("style", "N/D")
    form = dna.get("form", "N/D")
    rh = dna.get("rhythm", {})
    interp = dna.get("interpretation", {})
    summary = interp.get("summary", "—")
    over25 = rh.get("over_25_pct", 0)
    btts = rh.get("btts_pct", 0)
    timing = dna.get("timing", {})
    peak = timing.get("peak", "—")
    style_color = C_GREEN if "OFF" in str(style).upper() else (
        C_RED if "DIF" in str(style).upper() else C_AMBER
    )
    return f"""
    <div class="rp-box" style="height:100%;">
        <div style="font-size:11px;color:{C_MUTED2};text-transform:uppercase;letter-spacing:0.08em;">{team}</div>
        <div style="font-size:20px;font-weight:800;color:{style_color};margin:6px 0;">{style}</div>
        <div style="font-size:12px;color:{C_MUTED};margin-bottom:10px;">Forma: <b style="color:{C_TEXT};">{form}</b></div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:10px;">
            <div style="text-align:center;background:#1e293b;border-radius:6px;padding:8px;">
                <div style="font-size:9px;color:{C_MUTED2};">O2.5</div>
                <div style="font-size:16px;font-weight:700;color:{C_GREEN};">{over25:.0f}%</div>
            </div>
            <div style="text-align:center;background:#1e293b;border-radius:6px;padding:8px;">
                <div style="font-size:9px;color:{C_MUTED2};">BTTS</div>
                <div style="font-size:16px;font-weight:700;color:{C_CYAN};">{btts:.0f}%</div>
            </div>
        </div>
        <div style="font-size:11px;color:{C_MUTED};">Zona picco: <b style="color:{C_TEXT};">{peak}</b></div>
        <div style="font-size:11px;color:{C_MUTED2};margin-top:8px;line-height:1.45;">{summary}</div>
    </div>
    """


def _live_kpi_card(label: str, value: str, sub: str = "", color: str = C_TEXT) -> str:
    return f"""
    <div class="rp-box" style="text-align:center;padding:12px;">
        <div style="font-size:10px;color:{C_MUTED2};text-transform:uppercase;letter-spacing:0.06em;">{label}</div>
        <div style="font-size:22px;font-weight:800;color:{color};margin:4px 0;">{value}</div>
        <div style="font-size:10px;color:{C_MUTED};">{sub}</div>
    </div>
    """


def render():
    _inject_styles()

    filters = render_filter_sidebar("riepilogo")
    if not should_run_analysis(filters):
        st.info("👈 Imposta i filtri e clicca **📊 AGGIORNA RIEPILOGO** per visualizzare il dashboard.")
        return

    with st.spinner("Generazione riepilogo..."):
        data = load_prematch_data(filters, lambda: _compute_prematch_data(filters))
    if not data:
        st.warning("🔍 Nessun dato trovato con i filtri selezionati.")
        return

    filtered = data["filtered"]
    goal_events = data["goal_events"]
    match_ids = data["match_ids"]
    results = data["results"]
    n = results["match_count"]

    league = filters.get("league", _ALL_LEAGUES_LABEL)
    home_team = filters.get("home_team")
    away_team = filters.get("away_team")
    home_lbl = home_team or "Casa"
    away_lbl = away_team or "Trasferta"

    # ── Hero ──────────────────────────────────────────────────────────────
    teams_html = ""
    if home_team and away_team:
        teams_html = (
            f'<div style="display:flex;align-items:center;justify-content:center;gap:24px;margin-top:12px;">'
            f'{team_logo_html(home_team, size=48)}'
            f'<div style="font-size:18px;font-weight:900;color:{C_MUTED2};">VS</div>'
            f'{team_logo_html(away_team, size=48)}</div>'
        )
    st.html(f"""
    <div class="rp-hero">
        <div style="font-size:11px;color:{C_PURPLE};font-weight:700;letter-spacing:0.12em;text-transform:uppercase;">
            Dashboard Unificato
        </div>
        <div style="font-size:26px;font-weight:900;color:{C_TEXT};margin:4px 0;">📊 Riepilogo Analisi</div>
        <div style="font-size:13px;color:{C_MUTED};">
            {league} · <b style="color:{C_CYAN};">{n}</b> partite nel campione
        </div>
        {teams_html}
    </div>
    """)

    # Goal distribution for header insights
    g_dist = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, "5+": 0}
    for g in pd.to_numeric(filtered["total_goals_ft"], errors="coerce").fillna(0):
        if g >= 5:
            g_dist["5+"] += 1
        else:
            g_dist[int(g)] += 1

    hw_pct = results["home_win_pct"]
    dr_pct = results["draw_pct"]
    aw_pct = results["away_win_pct"]

    # ── 01 Prematch ───────────────────────────────────────────────────────
    _section_header(
        "01", "Esiti & Edge",
        "Probabilità 1X2, equilibrio match e strategie migliori sul campione",
        "Prematch", C_CYAN, first=True,
    )
    header_insights = compute_header_insights(
        hw_pct, dr_pct, aw_pct, n, results, filtered,
        goal_events, match_ids, _parse_minute, g_dist,
    )
    render_premium_header(hw_pct, dr_pct, aw_pct, n, header_insights)
    _render_over_under_grid(filtered, n)

    # ── 02 Momentum ───────────────────────────────────────────────────────
    _section_header(
        "02", "Pressione & Momentum",
        "Profilo atteso di intensità casa/trasferta sui 90 minuti",
        "Prematch / Live", C_GREEN,
    )
    render_similar_momentum_block(
        goal_events, match_ids, n,
        home_lbl, away_lbl,
        chart_key="rp_momentum",
        show_minute_marker=False,
        subtitle="Intensità attesa da gol storici nel campione filtrato",
    )

    # ── 03 Timeline ───────────────────────────────────────────────────────
    _section_header(
        "03", "Timeline & Tempi",
        "Distribuzione gol per minuto, zone di intensità e insight temporale",
        "Timeline", C_CYAN,
    )
    timeline = build_timeline(filtered)
    zones = build_intensity_zones(timeline)
    kpi = calculate_timeline_kpi(timeline)
    moments = detect_key_moments(zones)
    fg_avg = calculate_first_goal_avg(filtered)
    insight = generate_timeline_insight(kpi, moments)

    k1, k2, k3, k4, k5 = st.columns(5)
    with k1:
        st.html(_metric_card("Primo gol medio", f"{fg_avg}'", C_CYAN))
    with k2:
        st.html(_metric_card("Gol 1° tempo", f"{kpi['first_half_pct']:.1f}%", C_GREEN))
    with k3:
        st.html(_metric_card("Gol 2° tempo", f"{kpi['second_half_pct']:.1f}%", C_AMBER))
    with k4:
        st.html(_metric_card("Zona picco", moments.get("peak", "—"), C_TEXT))
    with k5:
        st.html(_metric_card("Intensità", f"{kpi['intensity']:.1f}%", C_PURPLE))

    st.html(f'<div class="rp-box" style="font-size:12px;color:{C_MUTED};">{insight}</div>')

    tc1, tc2 = st.columns(2)
    with tc1:
        st.plotly_chart(_plot_timeline_bars(timeline), use_container_width=True, config=_PLOTLY_CONFIG)
    with tc2:
        st.plotly_chart(_plot_zone_heatmap(zones), use_container_width=True, config=_PLOTLY_CONFIG)

    # ── 04 Gol & Risultati ────────────────────────────────────────────────
    _section_header(
        "04", "Gol & Primo Gol",
        "Distribuzione risultati e probabilità primo gol per tempo",
        "Prematch", C_AMBER,
    )
    fg1t_home_mins, fg1t_away_mins = [], []
    fg_intervals_1t = {"0-15": [0, 0], "16-30": [0, 0], "31-45": [0, 0], "45+": [0, 0]}
    fg1t_none_count = 0
    for mid in match_ids:
        events = goal_events.get(int(mid), [])
        sorted_evs = sorted(events, key=lambda x: _parse_minute(x["minute"])) if events else []
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
    total_fg1t = len(fg1t_home_mins) + len(fg1t_away_mins)
    pct_no_fg1t = round(fg1t_none_count / n * 100, 1) if n > 0 else 0.0
    pct_fg1t_with = round(total_fg1t / n * 100, 1) if n > 0 else 0.0
    data_1t = build_first_goal_data(
        fg1t_home_mins, fg1t_away_mins, fg_intervals_1t,
        [("0–15", ["0-15"]), ("16–30", ["16-30"]), ("31–45", ["31-45", "45+"])],
        30, n, 45,
    )

    gc1, gc2 = st.columns(2)
    with gc1:
        st.plotly_chart(_goal_dist_fig(g_dist, n), use_container_width=True, config=_PLOTLY_CONFIG)
    with gc2:
        render_first_goal_chart(
            data_1t, "⏱ PRIMO GOL — 1° TEMPO", "#3b82f6", "#3b82f640",
            total_fg1t, fg1t_none_count, pct_fg1t_with, pct_no_fg1t,
        )

    # ── 05 H2H ────────────────────────────────────────────────────────────
    _section_header(
        "05", "Testa a Testa",
        "Scontri diretti tra le squadre selezionate (se disponibili)",
        "H2H", C_AMBER,
    )
    if home_team and away_team and home_team != away_team:
        all_rows = get_all_matches_unfiltered()
        if all_rows:
            full_df = pd.DataFrame(all_rows)
            h2h_filters = dict(filters)
            h2h_filters["home_team"] = home_team
            h2h_filters["away_team"] = away_team
            h2h_df = _filter_h2h_matches(full_df, home_team, away_team, h2h_filters)
            if h2h_df.empty:
                st.info(f"Nessuno scontro diretto tra **{home_team}** e **{away_team}** con i filtri attuali.")
            else:
                h2h = analyze_h2h(h2h_df, home_team, away_team)
                hn = h2h["found"]
                hcols = st.columns(6)
                cards = [
                    ("Scontri", str(hn), f"media {h2h['avg_goals']} gol", C_TEXT, 0),
                    (f"Vitt. {home_team[:12]}", str(h2h["home_wins"]), f"{h2h['home_win_pct']:.1f}%", C_GREEN, 0),
                    ("Pareggi", str(h2h["draws"]), f"{h2h['draw_pct']:.1f}%", C_AMBER, 0),
                    (f"Vitt. {away_team[:12]}", str(h2h["away_wins"]), f"{h2h['away_win_pct']:.1f}%", C_RED, 0),
                    ("Over 2.5", str(h2h["over_25_n"]), f"{h2h['over_25_pct']:.1f}%", C_GREEN, h2h["over_25_pct"]),
                    ("BTTS", str(h2h["btts_n"]), f"{h2h['btts_pct']:.1f}%", C_CYAN, h2h["btts_pct"]),
                ]
                for col, (lbl, val, sub, colr, bar) in zip(hcols, cards):
                    with col:
                        st.html(_summary_card(lbl, val, sub, colr, bar))
                hc1, hc2, hc3 = st.columns([2, 2, 2])
                with hc1:
                    st.plotly_chart(_donut_chart(home_team, away_team, h2h), use_container_width=True)
                with hc2:
                    st.html(_over_under_bars(h2h))
                with hc3:
                    st.html(_insights_html(h2h.get("insights", [])))
    else:
        st.info("Seleziona **Casa** e **Trasferta** nei filtri per vedere il riepilogo H2H.")

    # ── 06 Team DNA ───────────────────────────────────────────────────────
    _section_header(
        "06", "Team DNA",
        "Profilo stilistico e interpretazione rapida per squadra",
        "Team DNA", C_PURPLE,
    )
    if home_team or away_team:
        dcols = st.columns(2 if home_team and away_team else 1)
        teams_dna = [(home_team, 0), (away_team, 1)] if home_team and away_team else [
            (home_team or away_team, 0)
        ]
        for team, idx in teams_dna:
            if not team:
                continue
            dna = analyze_team_dna(filtered, team, goal_events=goal_events)
            with dcols[idx if len(dcols) > 1 else 0]:
                st.html(_dna_card(team, dna))
    else:
        st.info("Seleziona almeno una squadra per il profilo DNA.")

    # ── 07 Simulator ──────────────────────────────────────────────────────
    _section_header(
        "07", "Strategie & ROI",
        "Classifica strategie sul campione filtrato (backtest rapido)",
        "Simulator", C_PURPLE,
    )
    ranking = find_best_strategy(filtered)
    if ranking.empty:
        st.info("Nessuna strategia applicabile su questo campione.")
    else:
        top3 = ranking.head(3)
        scols = st.columns(3)
        medals = ["🥇", "🥈", "🥉"]
        for i, (_, row) in enumerate(top3.iterrows()):
            roi = row["roi"]
            color = C_GREEN if roi > 0 else C_RED
            with scols[i]:
                st.html(f"""
                <div class="rp-box" style="text-align:center;">
                    <div style="font-size:22px;">{medals[i]}</div>
                    <div style="font-size:12px;font-weight:700;color:{C_TEXT};margin:6px 0;">{row['strategy']}</div>
                    <div style="font-size:24px;font-weight:900;color:{color};">{roi:+.1f}%</div>
                    <div style="font-size:10px;color:{C_MUTED};margin-top:4px;">
                        Strike {row['strike_rate']:.0f}% · {int(row['total_bets'])} bet
                    </div>
                    <div style="font-size:10px;color:{C_MUTED2};">Profit {row['profit']:+.0f}€</div>
                </div>
                """)
        st.dataframe(
            ranking[["strategy", "avg_odds", "roi", "profit", "strike_rate", "total_bets", "max_drawdown"]].rename(columns={
                "strategy": "Strategia",
                "avg_odds": "Quota",
                "roi": "ROI %",
                "profit": "Profitto",
                "strike_rate": "Strike %",
                "total_bets": "Bet",
                "max_drawdown": "Max DD",
            }).style.format({"Quota": "@{:.2f}"}),
            use_container_width=True,
            hide_index=True,
        )

    # ── 08 Live snapshot ──────────────────────────────────────────────────
    _section_header(
        "08", "Snapshot Live",
        "Proiezione live da partite simili (stato da filtri Live o 0-0 al minuto 0)",
        "Live", C_GREEN,
    )
    live_saved = st.session_state.get("_saved_filters_live", {})
    minute = int(live_saved.get("current_minute", 0) or 0)
    h_score = int(live_saved.get("home_score", 0) or 0)
    a_score = int(live_saved.get("away_score", 0) or 0)
    if minute <= 0:
        minute, h_score, a_score = 1, 0, 0
        live_note = "Stato base 0-0 al minuto 1 (imposta minuto/gol in Live per snapshot personalizzato)"
    else:
        live_note = f"Stato da Live: {h_score}-{a_score} al {minute}'"

    live_state = analyze_live_state_v2(
        filtered, goal_events, minute, h_score, a_score,
        odds_home_ref=filters.get("odds_home_min"),
    )
    conf = live_state.get("confidence", "—")
    found = live_state.get("found", 0)
    st.caption(live_note + f" · {found} partite simili · affidabilità {conf}")

    lc1, lc2, lc3, lc4 = st.columns(4)
    with lc1:
        ng = live_state.get("next_goal_home", 0)
        st.html(_live_kpi_card("Prossimo gol Casa", f"{ng:.0f}%", "", C_CYAN))
    with lc2:
        na = live_state.get("next_goal_away", 0)
        st.html(_live_kpi_card("Prossimo gol Trasf.", f"{na:.0f}%", "", C_AMBER))
    with lc3:
        btts = live_state.get("btts_si", 0)
        st.html(_live_kpi_card("BTTS", f"{btts:.0f}%", "probabilità residua", C_GREEN))
    with lc4:
        fh = live_state.get("final_home", 0)
        fd = live_state.get("final_draw", 0)
        fa = live_state.get("final_away", 0)
        best = max(fh, fd, fa)
        label = "Casa" if best == fh else ("Pareggio" if best == fd else "Trasferta")
        st.html(_live_kpi_card("Esito finale", label, f"{best:.0f}%", C_TEXT))
