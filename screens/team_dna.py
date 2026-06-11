"""
screens/team_dna.py — Team DNA: profilo decisionale squadra
"""

import streamlit as st
import pandas as pd
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database import get_all_matches, get_goal_events_for_matches
from filters import (
    _get_teams_by_league,
    _get_all_teams,
    _sidebar_label,
    prepare_screen_sidebar,
    render_league_picker,
)
from team_dna import (
    DNA_RED_ONLY_METRICS,
    DNA_ZONES,
    analyze_team_dna,
    build_dna_highlight_map,
)
from utils import team_logo_html

C_BG = "#111827"
C_BORDER = "#1f2937"
C_TEXT = "#f1f5f9"
C_MUTED = "#94a3b8"
C_MUTED2 = "#64748b"
C_DNA = "#e879f9"
C_GREEN = "#22c55e"
C_RED = "#ef4444"
C_CYAN = "#38bdf8"
C_YELLOW = "#f59e0b"
C_HOME = "#3b82f6"
C_AWAY = "#f59e0b"


def _inject_styles():
    st.html(f"""
    <style>
        .dna-box {{
            background:{C_BG}; border:1px solid {C_BORDER}; border-radius:8px;
            padding:18px; margin-bottom:14px; height:100%;
        }}
        .dna-title {{
            font-size:11px; color:{C_MUTED2}; text-transform:uppercase;
            letter-spacing:1px; margin-bottom:12px; font-weight:700;
        }}
        .dna-row {{
            display:flex; justify-content:space-between; align-items:center;
            padding:7px 0; border-bottom:1px solid {C_BORDER};
            font-size:13px; color:{C_MUTED};
        }}
        .dna-row:last-child {{ border-bottom:none; }}
        .dna-row-win {{
            background:rgba(34,197,94,0.1); border-radius:6px;
            padding-left:6px !important; padding-right:6px !important;
            border-bottom-color:transparent !important;
        }}
        .dna-row-lose {{
            background:rgba(239,68,68,0.1); border-radius:6px;
            padding-left:6px !important; padding-right:6px !important;
            border-bottom-color:transparent !important;
        }}
        .dna-row-tie {{
            background:rgba(245,158,11,0.12); border-radius:6px;
            padding-left:6px !important; padding-right:6px !important;
            border-bottom-color:transparent !important;
        }}
        .dna-val {{ color:{C_TEXT}; font-weight:700; }}
        .dna-val-win {{
            color:{C_GREEN} !important; font-weight:800;
            text-shadow:0 0 10px rgba(34,197,94,0.35);
        }}
        .dna-val-lose {{
            color:{C_RED} !important; font-weight:800;
            text-shadow:0 0 10px rgba(239,68,68,0.35);
        }}
        .dna-val-tie {{
            color:{C_YELLOW} !important; font-weight:800;
            text-shadow:0 0 10px rgba(245,158,11,0.35);
        }}
        .dna-bar-track {{
            background:#1f2937; border-radius:4px; height:8px; margin-top:6px;
            overflow:hidden;
        }}
        .dna-bar-fill {{ height:8px; border-radius:4px; background:{C_DNA}; }}
        .dna-zone-row {{
            display:flex; align-items:center; gap:10px; margin-bottom:8px;
            font-size:12px; color:{C_MUTED};
        }}
        .dna-zone-label {{ width:42px; font-weight:600; }}
        .dna-insight-li {{
            font-size:13px; color:{C_MUTED}; padding:4px 0;
        }}
    </style>
    """)


def _cmp_status(highlights: dict | None, side: str, section: str, key: str) -> str | None:
    """
    Pari → giallo su entrambe le colonne.
    Red-only: solo rosso se peggiore.
    Altre: solo verde se migliore.
    """
    if not highlights:
        return None
    winner = highlights.get(f"{section}.{key}")
    if winner is None:
        return None
    if winner == "tie":
        return "tie"
    status = "win" if winner == side else "lose"
    if (section, key) in DNA_RED_ONLY_METRICS:
        return "lose" if status == "lose" else None
    return "win" if status == "win" else None


def _stat_row(label: str, value: str, emoji: str = "", status: str | None = None) -> str:
    if status == "win":
        row_cls, val_cls, badge = "dna-row dna-row-win", "dna-val dna-val-win", " ▲"
    elif status == "lose":
        row_cls, val_cls, badge = "dna-row dna-row-lose", "dna-val dna-val-lose", " ▼"
    elif status == "tie":
        row_cls, val_cls, badge = "dna-row dna-row-tie", "dna-val dna-val-tie", " ="
    else:
        row_cls, val_cls, badge = "dna-row", "dna-val", ""
    return (
        f'<div class="{row_cls}">'
        f'<span>{emoji} {label}</span>'
        f'<span class="{val_cls}">{value}{badge}</span>'
        f'</div>'
    )


def _zone_bar(label: str, pct: float, is_peak: bool = False, status: str | None = None) -> str:
    blocks = int(round(pct / 4))
    bar_chars = "█" * blocks
    fire = " 🔥" if is_peak else ""
    if status == "win":
        color, row_style, val_cls, badge = C_GREEN, "background:rgba(34,197,94,0.1);border-radius:6px;padding:4px 6px;", "dna-val dna-val-win", " ▲"
    elif status == "lose":
        color, row_style, val_cls, badge = C_RED, "background:rgba(239,68,68,0.1);border-radius:6px;padding:4px 6px;", "dna-val dna-val-lose", " ▼"
    elif status == "tie":
        color, row_style, val_cls, badge = C_YELLOW, "background:rgba(245,158,11,0.12);border-radius:6px;padding:4px 6px;", "dna-val dna-val-tie", " ="
    else:
        color = C_GREEN if is_peak else C_DNA
        row_style, val_cls, badge = "", "dna-val", ""
    return f"""
    <div class="dna-zone-row" style="{row_style}">
        <span class="dna-zone-label">{label}</span>
        <span style="color:{color};font-family:monospace;min-width:90px;">{bar_chars}</span>
        <span class="{val_cls}">{pct}%{fire}{badge}</span>
    </div>
    """


def _style_color(style: str) -> str:
    if style == "OFFENSIVO":
        return C_GREEN
    if style == "DIFENSIVO":
        return C_CYAN
    return C_DNA


def _conf_color(conf: str) -> str:
    if conf == "ALTA":
        return C_GREEN
    if conf == "MEDIA":
        return C_YELLOW
    return C_RED


def _role_color(role: str) -> str:
    if role == "FAVORITA":
        return C_GREEN
    if role == "SFAVORITA":
        return C_RED
    return C_MUTED


def _render_odds_profile_block(prof: dict, highlights: dict | None, side: str, prefix: str) -> str:
    if not prof.get("has_data"):
        return (
            f'<div style="font-size:12px;color:{C_MUTED2};margin-bottom:8px;">'
            f'{prefix}: dati quote non disponibili</div>'
        )
    role = prof.get("market_role", "—")
    rc = _role_color(role)
    return (
        f'<div style="margin-bottom:10px;">'
        f'<div style="font-size:11px;color:{C_MUTED2};text-transform:uppercase;margin-bottom:6px;">{prefix}</div>'
        + _stat_row(
            "Quota media 1X2", f"{prof.get('avg_odds', '—')}",
            status=_cmp_status(highlights, side, "market", "avg_odds"),
        )
        + _stat_row(
            "Da favorita", f"{prof.get('favorite_pct', 0)}%", "⭐",
            status=_cmp_status(highlights, side, "market", "favorite_pct"),
        )
        + _stat_row(
            "Da sfavorita", f"{prof.get('underdog_pct', 0)}%", "📉",
            status=_cmp_status(highlights, side, "market", "underdog_pct"),
        )
        + f'<div style="font-size:12px;color:{C_MUTED};margin-top:6px;">'
        f'Ruolo mercato: <b style="color:{rc};">{role}</b>'
        f' <span style="color:{C_MUTED2};">({prof.get("matches_with_odds", 0)} partite con quote)</span>'
        f'</div></div>'
    )


def _render_odds_market(dna: dict, highlights: dict | None = None, side: str = "a") -> str:
    om = dna.get("odds_market", {})
    venue = dna.get("venue", "all")
    if not om.get("has_data"):
        return (
            f'<div class="dna-box"><div class="dna-title">💰 QUOTE MERCATO</div>'
            f'<div style="font-size:12px;color:{C_MUTED2};">Nessuna quota 1X2 nel campione selezionato.</div></div>'
        )

    body = ""
    if venue == "home":
        body = _render_odds_profile_block(om.get("home", {}), highlights, side, "In casa")
    elif venue == "away":
        body = _render_odds_profile_block(om.get("away", {}), highlights, side, "In trasferta")
    else:
        body = _render_odds_profile_block(om.get("home", {}), highlights, side, "In casa")
        body += _render_odds_profile_block(om.get("away", {}), highlights, side, "In trasferta")

    return f'<div class="dna-box"><div class="dna-title">💰 QUOTE MERCATO</div>{body}</div>'


def _render_style_profile(dna: dict) -> str:
    sp = dna.get("style_profile") or {}
    style = sp.get("style", dna.get("style", "N/D"))
    tags = sp.get("tags") or []
    score = sp.get("score", 0)
    conf = sp.get("confidence", "BASSA")
    tags_txt = " • ".join(tags) if tags else "—"
    sc = _style_color(style)
    cc = _conf_color(conf)
    return f"""
    <div class="dna-box" style="margin-bottom:14px;">
        <div style="font-size:11px;color:{C_MUTED2};text-transform:uppercase;letter-spacing:1px;margin-bottom:10px;">
            🧬 PROFILO STILE
        </div>
        <div style="font-size:18px;font-weight:900;color:{sc};margin-bottom:8px;">
            🔥 STILE: {style}
        </div>
        <div style="font-size:13px;color:{C_MUTED};margin-bottom:10px;">
            🧬 DNA: <span style="color:{C_TEXT};font-weight:700;">{tags_txt}</span>
        </div>
        <div style="display:flex;justify-content:space-between;font-size:13px;color:{C_MUTED};">
            <span>📊 Score: <b style="color:{C_TEXT};">{score}</b></span>
            <span>🎯 Confidenza: <b style="color:{cc};">{conf}</b></span>
        </div>
    </div>
    """


def _render_header(team: str, dna: dict, highlights: dict | None = None, side: str = "a"):
    form = dna.get("form", "N/D")
    form_color = C_GREEN if form == "POSITIVA" else (C_RED if form == "NEGATIVA" else C_YELLOW)
    form_cmp = _cmp_status(highlights, side, "_root", "recent_form_pts")
    form_badge = ""
    if form_cmp == "win":
        form_color = C_GREEN
        form_badge = " ▲"
    elif form_cmp == "lose":
        form_color = C_RED
        form_badge = " ▼"
    elif form_cmp == "tie":
        form_color = C_YELLOW
        form_badge = " ="

    st.html(f"""
    <div class="dna-box" style="text-align:center;margin-bottom:14px;">
        <div style="margin-bottom:12px;">{team_logo_html(team, size=72)}</div>
        <div style="font-size:11px;color:{C_MUTED2};letter-spacing:2px;">━━━━━━━━━━━━━━━━━━━━━━</div>
        <div style="font-size:22px;font-weight:900;color:{C_DNA};margin:8px 0;">
            🧬 {team.upper()} — TEAM DNA
        </div>
        <div style="font-size:11px;color:{C_MUTED2};letter-spacing:2px;margin-bottom:14px;">
            ━━━━━━━━━━━━━━━━━━━━━━
        </div>
        <div style="display:flex;justify-content:center;gap:28px;flex-wrap:wrap;font-size:13px;">
            <span>📊 Partite: <b style="color:{C_TEXT};">{dna['matches']}</b></span>
            <span>📈 Forma: <b style="color:{form_color};">{form}{form_badge}</b></span>
        </div>
        <div style="font-size:11px;color:{C_MUTED2};margin-top:10px;">
            📍 {dna.get('venue_label', 'Tutte le partite')}
        </div>
    </div>
    """)


def _render_goal_profile(gp: dict, highlights: dict | None = None, side: str = "a") -> str:
    avg_min = gp.get("avg_goal_minute", float("nan"))
    avg_str = f"{avg_min}'" if avg_min == avg_min else "—"
    return (
        f'<div class="dna-box"><div class="dna-title">⚽ GOAL PROFILE</div>'
        + _stat_row("Segna 1° tempo", f"{gp.get('score_1h_pct', 0)}%",
                    status=_cmp_status(highlights, side, "goal_profile", "score_1h_pct"))
        + _stat_row("Segna per prima", f"{gp.get('score_first_pct', 0)}%", "🔥",
                    status=_cmp_status(highlights, side, "goal_profile", "score_first_pct"))
        + _stat_row("Minuto medio gol", avg_str, "⏱️",
                    status=_cmp_status(highlights, side, "goal_profile", "avg_goal_minute"))
        + _stat_row("Segna 2° tempo", f"{gp.get('score_2h_pct', 0)}%", "📈",
                    status=_cmp_status(highlights, side, "goal_profile", "score_2h_pct"))
        + _stat_row("Media gol fatti", f"{gp.get('avg_scored', 0)}", "⚽",
                    status=_cmp_status(highlights, side, "goal_profile", "avg_scored"))
        + "</div>"
    )


def _render_defensive(df: dict, highlights: dict | None = None, side: str = "a") -> str:
    return (
        f'<div class="dna-box"><div class="dna-title">🧊 DEFENSIVE DNA</div>'
        + _stat_row("Clean sheet", f"{df.get('clean_sheet_pct', 0)}%", "🧊",
                    status=_cmp_status(highlights, side, "defensive", "clean_sheet_pct"))
        + _stat_row("Subisce gol", f"{df.get('concede_pct', 0)}%", "❌",
                    status=_cmp_status(highlights, side, "defensive", "concede_pct"))
        + _stat_row("Subisce nel 2° tempo", f"{df.get('concede_2h_pct', 0)}%", "⚠️",
                    status=_cmp_status(highlights, side, "defensive", "concede_2h_pct"))
        + _stat_row("Subisce dopo 75'", f"{df.get('concede_after_75_pct', 0)}%", "🔥",
                    status=_cmp_status(highlights, side, "defensive", "concede_after_75_pct"))
        + _stat_row("Media gol subiti", f"{df.get('avg_conceded', 0)}", "📉",
                    status=_cmp_status(highlights, side, "defensive", "avg_conceded"))
        + "</div>"
    )


def _render_rhythm(rh: dict, highlights: dict | None = None, side: str = "a") -> str:
    return (
        f'<div class="dna-box"><div class="dna-title">🔥 MATCH RHYTHM</div>'
        + _stat_row("Over 2.5", f"{rh.get('over_25_pct', 0)}%", "🔥",
                    status=_cmp_status(highlights, side, "rhythm", "over_25_pct"))
        + _stat_row("BTTS", f"{rh.get('btts_pct', 0)}%", "⚽",
                    status=_cmp_status(highlights, side, "rhythm", "btts_pct"))
        + _stat_row("Under 2.5", f"{rh.get('under_25_pct', 0)}%", "📉",
                    status=_cmp_status(highlights, side, "rhythm", "under_25_pct"))
        + _stat_row("Media gol match", f"{rh.get('avg_goals', 0)}", "📊",
                    status=_cmp_status(highlights, side, "rhythm", "avg_goals"))
        + "</div>"
    )


def _render_timing(tm: dict, highlights: dict | None = None, side: str = "a") -> str:
    zones = tm.get("zones", {})
    peak = tm.get("peak", "—")
    low = tm.get("low", "—")
    rows = "".join(
        _zone_bar(
            z, zones.get(z, 0),
            is_peak=(z == peak),
            status=_cmp_status(highlights, side, "timing", z),
        )
        for z in DNA_ZONES
    )
    return (
        f'<div class="dna-box"><div class="dna-title">⏱️ TIMING DNA</div>'
        f'{rows}'
        f'<div style="margin-top:12px;font-size:12px;">'
        f'<span style="color:{C_GREEN};">🔥 PICCO: {peak}</span> &nbsp;|&nbsp; '
        f'<span style="color:{C_CYAN};">❄️ CALO: {low}</span>'
        f'</div></div>'
    )


def _render_interpretation(interp: dict, team: str = "") -> str:
    pos = "".join(f'<div class="dna-insight-li">✔ {p}</div>' for p in interp.get("positives", []))
    risks = "".join(f'<div class="dna-insight-li" style="color:{C_RED};">❗ {r}</div>' for r in interp.get("risks", []))
    title = f"🧬 {team.upper()} DNA" if team else "🧬 DNA INTERPRETAZIONE"
    return f"""
    <div class="dna-box">
        <div class="dna-title">{title}</div>
        <div style="font-size:14px;font-weight:700;color:{C_TEXT};margin-bottom:10px;">
            {interp.get('summary', '')}
        </div>
        {pos}
        <div style="margin-top:12px;font-size:11px;color:{C_MUTED2};text-transform:uppercase;">Rischi</div>
        {risks}
    </div>
    """


def _render_team_column(
    team: str,
    dna: dict,
    side_label: str,
    accent: str,
    highlights: dict | None = None,
    side_key: str = "a",
):
    """Colonna verticale con tutti i blocchi DNA (come vista singola, impilati)."""
    st.html(f"""
    <div style="text-align:center;margin-bottom:12px;">
        <span style="font-size:10px;font-weight:800;letter-spacing:1px;color:{accent};
                     border:1px solid {accent};border-radius:4px;padding:3px 10px;">
            {side_label}
        </span>
    </div>
    """)
    _render_header(team, dna, highlights, side_key)
    st.html(_render_style_profile(dna))
    st.html(_render_odds_market(dna, highlights, side_key))
    st.html(_render_goal_profile(dna["goal_profile"], highlights, side_key))
    st.html(_render_defensive(dna["defensive"], highlights, side_key))
    st.html(_render_rhythm(dna["rhythm"], highlights, side_key))
    st.html(_render_timing(dna["timing"], highlights, side_key))
    st.html(_render_interpretation(dna["interpretation"], team))
    pts = dna.get("recent_form_pts", 0)
    pts_cmp = _cmp_status(highlights, side_key, "_root", "recent_form_pts")
    if pts_cmp == "win":
        pts_color, pts_badge = C_GREEN, " ▲"
    elif pts_cmp == "lose":
        pts_color, pts_badge = C_RED, " ▼"
    elif pts_cmp == "tie":
        pts_color, pts_badge = C_YELLOW, " ="
    else:
        pts_color, pts_badge = C_TEXT, ""
    st.markdown(
        f'<p style="font-size:12px;color:{C_MUTED};margin:4px 0 0;">'
        f'Forma ultime 10: <span style="color:{pts_color};font-weight:700;">{pts}{pts_badge}</span> pt/partita</p>',
        unsafe_allow_html=True,
    )


def _render_compare_view(dna_a: dict, dna_b: dict, team_a: str, team_b: str):
    highlights = build_dna_highlight_map(dna_a, dna_b)
    st.caption(
        "📍 Casa / Trasferta · 🟢 migliore · 🟡 **Giallo =** pari · "
        "🔴 peggiore solo su *Da sfavorita* e *Defensive DNA*"
    )
    col_home, col_away = st.columns(2, gap="large")
    with col_home:
        with st.container():
            _render_team_column(team_a, dna_a, "CASA", C_HOME, highlights, "a")
    with col_away:
        with st.container():
            _render_team_column(team_b, dna_b, "TRASFERTA", C_AWAY, highlights, "b")


def _load_team_dna(df: pd.DataFrame, team: str, goal_events: dict, last_n, venue: str | None = None):
    if venue == "home":
        tdf = df[df["home_team"] == team]
    elif venue == "away":
        tdf = df[df["away_team"] == team]
    else:
        tdf = df[(df["home_team"] == team) | (df["away_team"] == team)]
    if tdf.empty:
        return None
    return analyze_team_dna(df, team, goal_events, last_n=last_n, venue=venue)


def _render_single_view(team: str, dna: dict):
    _render_header(team, dna)
    st.html(_render_style_profile(dna))
    st.html(_render_odds_market(dna))
    c1, c2 = st.columns(2)
    with c1:
        st.html(_render_goal_profile(dna["goal_profile"]))
    with c2:
        st.html(_render_defensive(dna["defensive"]))
    c3, c4 = st.columns(2)
    with c3:
        st.html(_render_rhythm(dna["rhythm"]))
    with c4:
        st.html(_render_timing(dna["timing"]))
    st.html(_render_interpretation(dna["interpretation"], team))
    st.caption(
        f"Forma ultime 10: **{dna.get('recent_form_pts', 0)}** pt/partita · "
        f"Riutilizzabile in **LIVE** per hedge / lay dopo lettura timing DNA."
    )


def _render_dna_sidebar() -> dict:
    """Sidebar dedicata: lega, squadra, ultime N partite."""
    prepare_screen_sidebar("dna")

    _sidebar_label("🌍 Campionato")
    league = render_league_picker(key="dna_league", include_all=True)

    if league and league != "Tutte le competizioni":
        teams = sorted(_get_teams_by_league(league) or [])
    else:
        teams = sorted(_get_all_teams() or [])

    if not teams:
        st.sidebar.warning("Nessuna squadra disponibile.")
        return {}

    _sidebar_label("⚙️ Modalità")
    mode = st.sidebar.radio(
        "Modalità",
        ["Singola squadra", "Confronto"],
        key="dna_mode",
        horizontal=True,
        label_visibility="collapsed",
    )
    compare_mode = mode == "Confronto"

    if "dna_team" not in st.session_state or st.session_state.dna_team not in teams:
        st.session_state.dna_team = teams[0]
    if "dna_team_b" not in st.session_state or st.session_state.dna_team_b not in teams:
        st.session_state.dna_team_b = teams[1] if len(teams) > 1 else teams[0]

    _sidebar_label("🛡️ Squadre")
    if compare_mode:
        c_h, c_vs, c_a = st.sidebar.columns([5, 1, 5])
        with c_h:
            team_a = st.selectbox("Casa", teams, key="dna_team", label_visibility="collapsed")
        with c_vs:
            st.markdown(
                '<div style="text-align:center;font-weight:800;color:#64748b;padding-top:8px;">VS</div>',
                unsafe_allow_html=True,
            )
        with c_a:
            team_b = st.selectbox("Trasferta", teams, key="dna_team_b", label_visibility="collapsed")
        team = team_a
    else:
        team = st.sidebar.selectbox("Squadra", teams, key="dna_team", label_visibility="collapsed")
        team_a = team_b = None

    _sidebar_label("📊 Campione")
    last_n = st.sidebar.selectbox(
        "Campione",
        [("Ultime 10", 10), ("Ultime 20", 20), ("Ultime 50", 50), ("Tutte", 0)],
        format_func=lambda x: x[0],
        key="dna_last_n_pick",
        label_visibility="collapsed",
    )[1]

    return {
        "league": league,
        "team": team,
        "team_a": team_a,
        "team_b": team_b,
        "compare_mode": compare_mode,
        "last_n": last_n if last_n > 0 else None,
        "_apply": True,
    }


def render():
    _inject_styles()
    filters = _render_dna_sidebar()

    if not filters or not filters.get("team"):
        return

    rows = get_all_matches()
    if not rows:
        st.warning("⚠️ Nessun dato nel database.")
        return

    df = pd.DataFrame(rows)
    league = filters.get("league")
    if league and league not in ("Tutti", "Tutte", "Tutte le competizioni"):
        df = df[df["league"] == league]

    last_n = filters.get("last_n")

    if filters.get("compare_mode"):
        team_a = filters["team_a"]
        team_b = filters["team_b"]
        if team_a == team_b:
            st.warning("Seleziona due squadre diverse per il confronto.")
            return

        tdf_home = df[df["home_team"] == team_a]
        tdf_away = df[df["away_team"] == team_b]
        match_ids = set()
        match_ids.update(tdf_home["match_id"].dropna().astype(int).tolist())
        match_ids.update(tdf_away["match_id"].dropna().astype(int).tolist())
        goal_events = get_goal_events_for_matches(list(match_ids))

        with st.spinner(f"Confronto {team_a} (casa) vs {team_b} (trasferta)..."):
            dna_a = _load_team_dna(df, team_a, goal_events, last_n, venue="home")
            dna_b = _load_team_dna(df, team_b, goal_events, last_n, venue="away")

        if not dna_a or dna_a["matches"] == 0:
            st.warning(f"Dati insufficienti per **{team_a}** in casa.")
            return
        if not dna_b or dna_b["matches"] == 0:
            st.warning(f"Dati insufficienti per **{team_b}** in trasferta.")
            return

        _render_compare_view(dna_a, dna_b, team_a, team_b)
        return

    team = filters["team"]
    tdf = df[(df["home_team"] == team) | (df["away_team"] == team)]
    if tdf.empty:
        st.warning(f"Nessuna partita trovata per **{team}**.")
        return

    match_ids = list(tdf["match_id"].dropna().astype(int))
    goal_events = get_goal_events_for_matches(match_ids)

    with st.spinner(f"Analisi DNA {team}..."):
        dna = _load_team_dna(df, team, goal_events, last_n)

    if not dna or dna["matches"] == 0:
        st.warning("Dati insufficienti per questa squadra.")
        return

    _render_single_view(team, dna)
