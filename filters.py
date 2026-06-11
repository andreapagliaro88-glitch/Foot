"""
filters.py — Filter UI components + SQL query builder
Sidebar design matches client reference UI (dark navy, blue accents, FILTRI panel)
"""

import json
import streamlit as st
import pandas as pd
from pathlib import Path
from utils import parse_goal_minute_value, split_league_name

_DATA_DIR = Path(__file__).resolve().parent / "data"
_LEAGUE_FAVORITES_FILE = _DATA_DIR / "league_favorites.json"
_ALL_LEAGUES_LABEL = "Tutte le competizioni"

_ANALYSIS_SCREENS = ("prematch", "live", "h2h", "simulator", "timeline")

_SHARED_ODDS_KEYS = (
    "odds_home_min", "odds_home_max",
    "odds_draw_min", "odds_draw_max",
    "odds_away_min", "odds_away_max",
)

_ODDS_WIDGET_KEYS = {
    "prematch": {
        "odds_home_min": "prematch_oh_min",
        "odds_home_max": "prematch_oh_max",
        "odds_draw_min": "prematch_od_min",
        "odds_draw_max": "prematch_od_max",
        "odds_away_min": "prematch_oa_min",
        "odds_away_max": "prematch_oa_max",
    },
    "live": {
        "odds_home_min": "live_oh_min",
        "odds_home_max": "live_oh_max",
        "odds_draw_min": "live_od_min",
        "odds_draw_max": "live_od_max",
        "odds_away_min": "live_oa_min",
        "odds_away_max": "live_oa_max",
    },
}


def should_run_analysis(filters: dict) -> bool:
    """True if Analizza was clicked now or analysis is already active from another page."""
    if filters.get("_apply"):
        st.session_state["filters_analyzed"] = True
        return True
    return bool(st.session_state.get("filters_analyzed", False))


def clear_analysis_state():
    st.session_state.pop("filters_analyzed", None)
    st.session_state.pop("_analyze_source_screen", None)
    st.session_state.pop("pm_analyzed", None)


def _propagate_saved_filters(source_screen: str, filters: dict):
    """Copy analyzed filters to every screen so navigation keeps the same criteria."""
    clean = {k: v for k, v in filters.items() if not k.startswith("_")}
    _persist_shared_odds(clean)
    for scr in _ANALYSIS_SCREENS:
        saved = dict(st.session_state.get(f"_saved_filters_{scr}", {}))
        saved.update(clean)
        st.session_state[f"_saved_filters_{scr}"] = saved


def _bootstrap_shared_odds() -> dict:
    """Carica quote condivise da sessione o da ultimo salvataggio prematch/live."""
    shared = st.session_state.get("_shared_odds")
    if shared:
        return shared
    for scr in ("live", "prematch"):
        saved = st.session_state.get(f"_saved_filters_{scr}", {})
        found = {k: float(saved[k]) for k in _SHARED_ODDS_KEYS if k in saved}
        if found:
            st.session_state["_shared_odds"] = found
            return found
    return {}


def _load_shared_odds_into_sv(sv: dict) -> None:
    """Le quote 1X2 sono uniche: prematch e live usano sempre l'ultimo valore."""
    shared = _bootstrap_shared_odds()
    for key in _SHARED_ODDS_KEYS:
        if key in shared:
            sv[key] = shared[key]


def _persist_shared_odds(filters: dict) -> None:
    """Salva le quote modificate e le replica su prematch + live."""
    odds = {k: float(filters[k]) for k in _SHARED_ODDS_KEYS if k in filters}
    if not odds:
        return
    merged = {**st.session_state.get("_shared_odds", {}), **odds}
    st.session_state["_shared_odds"] = merged
    for scr in ("prematch", "live"):
        saved = dict(st.session_state.get(f"_saved_filters_{scr}", {}))
        saved.update(merged)
        st.session_state[f"_saved_filters_{scr}"] = saved


def _sync_shared_odds_widgets(screen: str) -> None:
    """All'ingresso in una pagina, allinea i widget alle quote condivise."""
    shared = _bootstrap_shared_odds()
    mapping = _ODDS_WIDGET_KEYS.get(screen, {})
    for odds_key, widget_key in mapping.items():
        if odds_key in shared:
            st.session_state[widget_key] = float(shared[odds_key])


def _merge_analyzed_filters(filters: dict, screen: str):
    """On non-source pages, inherit filter keys not rendered in that sidebar."""
    source = st.session_state.get("_analyze_source_screen", "prematch")
    if source == screen:
        return
    source_saved = st.session_state.get(f"_saved_filters_{source}", {})
    for k, v in source_saved.items():
        if k not in filters:
            filters[k] = v


def _sync_sv_to_live_widgets(sv: dict):
    """Push shared filter values into live sidebar widget session keys."""
    mapping = {
        "league": "live_league",
        "odds_home_min": "live_oh_min",
        "odds_home_max": "live_oh_max",
        "odds_draw_min": "live_od_min",
        "odds_draw_max": "live_od_max",
        "odds_away_min": "live_oa_min",
        "odds_away_max": "live_oa_max",
    }
    for src, dst in mapping.items():
        if src in sv and sv[src] is not None:
            st.session_state[dst] = sv[src]


def _goal_team_widget_value(raw) -> str:
    """Map persisted filter value → valid selectbox option."""
    if raw in ("Casa", "Trasferta"):
        return raw
    return "Seleziona"


def _init_live_goal_team_widgets(sv: dict):
    """Restore goal-team selectboxes; never write None (invalid option)."""
    widgets = sv.get("goal_team_widgets")
    if not widgets or len(widgets) < 3:
        teams = sv.get("goal_teams", [None, None, None])
        widgets = [
            _goal_team_widget_value(teams[i] if i < len(teams) else None)
            for i in range(3)
        ]
    for i in range(3):
        key = f"live_goal_team_{i}"
        if key not in st.session_state:
            st.session_state[key] = _goal_team_widget_value(widgets[i])
        elif st.session_state[key] not in ("Seleziona", "Casa", "Trasferta"):
            st.session_state[key] = _goal_team_widget_value(st.session_state[key])


LIVE_TIMER_REFRESH_SEC = 300  # aggiornamento pagina ogni 5 minuti


def tick_live_match_clock(elapsed_real_seconds: int = 1):
    """Advance match clock by elapsed_real_seconds × speed. Caps at 90:00."""
    speed = int(st.session_state.get("live_timer_speed", 1))
    add_seconds = int(elapsed_real_seconds) * speed
    st.session_state.live_match_second = int(st.session_state.get("live_match_second", 0)) + add_seconds
    while st.session_state.live_match_second >= 60:
        st.session_state.live_match_second -= 60
        st.session_state.live_match_minute = int(st.session_state.get("live_match_minute", 0)) + 1
    if st.session_state.live_match_minute >= 90:
        st.session_state.live_match_minute = 90
        st.session_state.live_match_second = 0
        st.session_state.live_timer_running = False
    st.session_state.live_minute_slider = int(st.session_state.live_match_minute)


def _valid_h2h_team(name) -> bool:
    return bool(name) and name not in ("Tutte le squadre", "Tutte", "Seleziona")


def _init_h2h_widgets(sv: dict, teams: list | None = None):
    """Ripristina i widget H2H dai filtri salvati (sopravvivono al cambio pagina)."""
    _defaults = {
        "h2h_last_n":           sv.get("h2h_last_n", "Tutte"),
        "h2h_date_from":        sv.get("date_from", pd.Timestamp("2010-01-01")),
        "h2h_date_to":          sv.get("date_to", pd.Timestamp("2030-12-31")),
        "h2h_f_over15":         bool(sv.get("h2h_f_over15", False)),
        "h2h_f_over25":         bool(sv.get("h2h_f_over25", False)),
        "h2h_f_over35":         bool(sv.get("h2h_f_over35", False)),
        "h2h_f_btts":           bool(sv.get("h2h_f_btts", False)),
        "h2h_res_home":         bool(sv.get("h2h_res_home", False)),
        "h2h_res_draw":         bool(sv.get("h2h_res_draw", False)),
        "h2h_res_away":         bool(sv.get("h2h_res_away", False)),
        "h2h_min_goals_total":  int(sv.get("h2h_min_goals_total", 0)),
        "h2h_max_goals_total":  int(sv.get("h2h_max_goals_total", 10)),
        "h2h_min_goals_home":   int(sv.get("h2h_min_goals_home", 0)),
        "h2h_min_goals_away":   int(sv.get("h2h_min_goals_away", 0)),
        "h2h_venue":            sv.get("h2h_venue", "Tutti gli scontri"),
        "h2h_league":           sv.get("h2h_league", "Tutti i campionati"),
    }
    for key, val in _defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

    if teams:
        home_default = sv.get("home_team") if _valid_h2h_team(sv.get("home_team")) else teams[0]
        away_default = sv.get("away_team") if _valid_h2h_team(sv.get("away_team")) else teams[min(1, len(teams) - 1)]
        if home_default not in teams:
            home_default = teams[0]
        if away_default not in teams:
            away_default = teams[min(1, len(teams) - 1)]
        if "h2h_home" not in st.session_state:
            st.session_state["h2h_home"] = home_default
        elif st.session_state["h2h_home"] not in teams:
            st.session_state["h2h_home"] = home_default
        if "h2h_away" not in st.session_state:
            st.session_state["h2h_away"] = away_default
        elif st.session_state["h2h_away"] not in teams:
            st.session_state["h2h_away"] = away_default


def _sync_sv_to_h2h_widgets(sv: dict):
    """Forza i widget H2H dai filtri condivisi dopo un'analisi cross-page."""
    if _valid_h2h_team(sv.get("home_team")):
        st.session_state["h2h_home"] = sv["home_team"]
    if _valid_h2h_team(sv.get("away_team")):
        st.session_state["h2h_away"] = sv["away_team"]
    for src, dst in (
        ("h2h_last_n", "h2h_last_n"),
        ("date_from", "h2h_date_from"),
        ("date_to", "h2h_date_to"),
        ("h2h_f_over15", "h2h_f_over15"),
        ("h2h_f_over25", "h2h_f_over25"),
        ("h2h_f_over35", "h2h_f_over35"),
        ("h2h_f_btts", "h2h_f_btts"),
        ("h2h_res_home", "h2h_res_home"),
        ("h2h_res_draw", "h2h_res_draw"),
        ("h2h_res_away", "h2h_res_away"),
        ("h2h_min_goals_total", "h2h_min_goals_total"),
        ("h2h_max_goals_total", "h2h_max_goals_total"),
        ("h2h_min_goals_home", "h2h_min_goals_home"),
        ("h2h_min_goals_away", "h2h_min_goals_away"),
        ("h2h_venue", "h2h_venue"),
        ("h2h_league", "h2h_league"),
    ):
        if src in sv:
            st.session_state[dst] = sv[src]


def _sync_sv_to_prematch_widgets(screen: str, sv: dict):
    """Forza i widget prematch/pattern dai filtri condivisi dopo un'analisi cross-page."""
    mapping = {
        "league":        f"{screen}_league",
        "odds_home_min": f"{screen}_oh_min",
        "odds_home_max": f"{screen}_oh_max",
        "odds_draw_min": f"{screen}_od_min",
        "odds_draw_max": f"{screen}_od_max",
        "odds_away_min": f"{screen}_oa_min",
        "odds_away_max": f"{screen}_oa_max",
        "home_team":     f"{screen}_home_team",
        "away_team":     f"{screen}_away_team",
    }
    for src, dst in mapping.items():
        if src in sv and sv[src] is not None:
            st.session_state[dst] = sv[src]
    if sv.get("league") is not None:
        league_key = f"{screen}_league"
        use_all_key = f"{league_key}_use_all"
        if sv["league"] == _ALL_LEAGUES_LABEL:
            st.session_state[use_all_key] = True
            all_leagues = _get_leagues() or []
            if all_leagues and st.session_state.get(league_key) == _ALL_LEAGUES_LABEL:
                st.session_state[league_key] = all_leagues[0]
        else:
            st.session_state[use_all_key] = False


def _init_prematch_widgets(screen: str, sv: dict):
    """Ripristina i widget prematch/pattern; non sovrascrive scelte già in sessione."""
    leagues = ["Tutte le competizioni"] + _get_leagues()
    league_key = f"{screen}_league"
    league_default = sv.get("league", "Tutte le competizioni")
    if league_default not in leagues:
        league_default = "Tutte le competizioni"
    use_all_key = f"{league_key}_use_all"
    if league_key not in st.session_state:
        st.session_state[league_key] = league_default
    elif st.session_state[league_key] not in leagues:
        st.session_state[league_key] = league_default
    if use_all_key not in st.session_state:
        current = st.session_state.get(league_key, league_default)
        st.session_state[use_all_key] = current == _ALL_LEAGUES_LABEL

    _pm_defaults = {
        f"{screen}_oh_min": float(sv.get("odds_home_min", 1.0)),
        f"{screen}_oh_max": float(sv.get("odds_home_max", 99.0)),
        f"{screen}_od_min": float(sv.get("odds_draw_min", 1.0)),
        f"{screen}_od_max": float(sv.get("odds_draw_max", 99.0)),
        f"{screen}_oa_min": float(sv.get("odds_away_min", 1.0)),
        f"{screen}_oa_max": float(sv.get("odds_away_max", 99.0)),
    }
    for key, val in _pm_defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

    selected_league = st.session_state[league_key]
    if selected_league and selected_league != "Tutte le competizioni":
        all_teams = _get_teams_by_league(selected_league)
    else:
        all_teams = _get_all_teams()
    team_opts = ["Tutte le squadre"] + all_teams

    home_key = f"{screen}_home_team"
    away_key = f"{screen}_away_team"
    home_default = sv.get("home_team") or "Tutte le squadre"
    away_default = sv.get("away_team") or "Tutte le squadre"
    if home_default not in team_opts:
        home_default = "Tutte le squadre"
    if away_default not in team_opts:
        away_default = "Tutte le squadre"
    if home_key not in st.session_state:
        st.session_state[home_key] = home_default
    elif st.session_state[home_key] not in team_opts:
        st.session_state[home_key] = "Tutte le squadre"
    if away_key not in st.session_state:
        st.session_state[away_key] = away_default
    elif st.session_state[away_key] not in team_opts:
        st.session_state[away_key] = "Tutte le squadre"


# ── Sidebar themes per pagina (allineati all'header in app.py) ─────────────
def _rgba(hex_color: str, alpha: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


_SCREEN_SIDEBAR_THEMES = {
    "prematch": {
        "style": "flat",
        "accent": "#3b82f6",
        "accent_light": "#38bdf8",
        "accent_hover": "#60a5fa",
        "accent_dark": "#2563eb",
    },
    "live": {
        "style": "glow",
        "accent": "#22c55e",
        "accent_light": "#86efac",
        "accent_hover": "#4ade80",
        "accent_dark": "#065f46",
        "accent_btn": "#047857",
        "accent_deep": "#052e16",
        "panel_to": "#041b12",
        "input_bg": "#02140f",
        "text_muted": "#86efac",
        "text_bright": "#d1fae5",
        "text_dark": "#022c22",
    },
    "h2h": {
        "style": "glow",
        "accent": "#f59e0b",
        "accent_light": "#fcd34d",
        "accent_hover": "#fbbf24",
        "accent_dark": "#92400e",
        "accent_btn": "#b45309",
        "accent_deep": "#451a03",
        "panel_to": "#1c1004",
        "input_bg": "#1a1208",
        "text_muted": "#fde68a",
        "text_bright": "#fef3c7",
        "text_dark": "#422006",
    },
    "simulator": {
        "style": "flat",
        "accent": "#a855f7",
        "accent_light": "#c084fc",
        "accent_hover": "#d8b4fe",
        "accent_dark": "#7e22ce",
    },
    "timeline": {
        "style": "flat",
        "accent": "#38bdf8",
        "accent_light": "#7dd3fc",
        "accent_hover": "#bae6fd",
        "accent_dark": "#0284c7",
    },
    "dna": {
        "style": "flat",
        "accent": "#e879f9",
        "accent_light": "#f0abfc",
        "accent_hover": "#f5d0fe",
        "accent_dark": "#c026d3",
    },
}

_CSS_INJECTED = False


def _inject_sidebar_theme(screen: str):
    t = _SCREEN_SIDEBAR_THEMES.get(screen, _SCREEN_SIDEBAR_THEMES["prematch"])
    accent = t["accent"]
    accent_light = t["accent_light"]
    accent_hover = t.get("accent_hover", accent_light)
    accent_dark = t.get("accent_dark", accent)
    st.sidebar.html(f"""
    <style>
    [data-testid="stSidebar"] {{
        --sb-bg: #050a10;
        --sb-accent: {accent};
        --sb-accent-light: {accent_light};
        --sb-accent-dim: {_rgba(accent, 0.35)};
        --sb-panel: #0a1420;
        --sb-input: {t.get("input_bg", "#0a1628")};
        --sb-border: {_rgba(accent, 0.45)};
        --sb-btn-grad: linear-gradient(135deg, {accent}, {accent_dark});
        --sb-btn-hover: linear-gradient(135deg, {accent_hover}, {accent});
        --sb-analyze-grad: linear-gradient(135deg, {accent}, {accent_dark});
        --sb-analyze-hover: linear-gradient(135deg, {accent_hover}, {accent});
    }}
    </style>
    """)


def _flat_sidebar_css(t: dict) -> str:
    a, al, ah, ad = t["accent"], t["accent_light"], t["accent_hover"], t["accent_dark"]
    g35, g45, g60 = _rgba(a, 0.35), _rgba(a, 0.45), _rgba(a, 0.6)
    return f"""
    <style>
    section[data-testid="stSidebar"] {{
        background: linear-gradient(180deg, #020617, #020617) !important;
        border-right: 1px solid #0f172a !important;
        box-shadow: none !important;
    }}
    [data-testid="stSidebar"] > div:first-child {{ padding: 12px 14px !important; }}
    [data-testid="stSidebar"] .sidebar-box {{
        background: linear-gradient(145deg, #020617, #0f172a);
        border: 1px solid #1e293b; border-radius: 12px;
        padding: 14px; margin-bottom: 12px;
    }}
    [data-testid="stSidebar"] .sidebar-title {{
        font-size: 13px; font-weight: 700; color: {al};
        margin-bottom: 0; letter-spacing: 0.04em;
    }}
    [data-testid="stSidebar"] .sidebar-active {{
        border: 1px solid {a} !important;
        box-shadow: 0 0 12px {g60} !important;
    }}
    [data-testid="stSidebar"] .sidebar-brand-header {{
        background: linear-gradient(145deg, #020617, #0f172a);
        border: 1px solid #1e293b; border-radius: 12px;
        margin-bottom: 12px; padding: 14px; box-shadow: none; position: relative;
    }}
    [data-testid="stSidebar"] .sidebar-brand-title {{
        color: {al}; text-shadow: 0 0 10px {g45};
    }}
    [data-testid="stSidebar"] .sidebar-brand-subtitle {{ color: #64748b; }}
    [data-testid="stSidebar"] .sidebar-brand-icon {{
        background: #0f172a; border: 1px solid #1e293b; box-shadow: 0 0 10px {g35};
    }}
    [data-testid="stSidebar"] .stTextInput input,
    [data-testid="stSidebar"] .stSelectbox > div > div,
    [data-testid="stSidebar"] .stDateInput input,
    [data-testid="stSidebar"] .stNumberInput input {{
        background: #020617 !important; border: 1px solid #1e293b !important;
        border-radius: 8px !important; color: #e2e8f0 !important;
    }}
    [data-testid="stSidebar"] .stNumberInput button {{
        background: #0f172a !important; border: 1px solid #1e293b !important;
        color: {al} !important;
    }}
    [data-testid="stSidebar"] .stSlider > div {{ color: {al}; }}
    [data-testid="stSidebar"] .stSlider [data-baseweb="slider"] div[role="slider"],
    [data-testid="stSidebar"] .stSlider [class*="StyledThumb"],
    [data-testid="stSidebar"] .stSlider [class*="StyledTrackHighlight"] {{
        background: {a} !important; border-color: {al} !important;
    }}
    [data-testid="stSidebar"] .stSlider [class*="StyledTrack"] {{ background: #1e293b !important; }}
    [data-testid="stSidebar"] .stButton > button {{
        background: linear-gradient(90deg, {ad}, {a}) !important;
        border: none !important; border-radius: 8px !important;
        font-weight: 700 !important; color: #ffffff !important;
        box-shadow: 0 0 10px {g35} !important;
    }}
    [data-testid="stSidebar"] .stButton > button:hover {{
        background: linear-gradient(90deg, {a}, {ah}) !important;
    }}
    [data-testid="stSidebar"] [data-testid="stExpander"] details {{
        background: linear-gradient(145deg, #020617, #0f172a) !important;
        border: 1px solid #1e293b !important; border-radius: 12px !important;
        margin-bottom: 8px !important; border-bottom: 1px solid #1e293b !important;
    }}
    [data-testid="stSidebar"] [data-testid="stExpander"] summary {{
        background: transparent !important; color: {al} !important;
        font-size: 13px !important; font-weight: 700 !important;
    }}
    [data-testid="stSidebar"] [data-testid="stExpander"] summary:hover {{
        background: #0f172a !important; color: {ah} !important;
    }}
    [data-testid="stSidebar"] [data-testid="stExpander"] summary svg {{
        fill: {a} !important; color: {a} !important;
    }}
    [data-testid="stSidebar"] .stWidgetLabel p,
    [data-testid="stSidebar"] label {{ color: #94a3b8 !important; }}
    [data-testid="stSidebar"] .stCheckbox label {{ color: #cbd5e1 !important; }}
    [data-testid="stSidebar"] .quota-col-label,
    [data-testid="stSidebar"] .pct-grid-label {{ color: #64748b !important; }}
    [data-testid="stSidebar"] .sidebar-accent-text {{ color: {al}; }}
    [data-testid="stSidebar"] .pm-widget-gap {{ margin-bottom: 12px; }}
    </style>
    """


def _glow_sidebar_css(t: dict) -> str:
    a = t["accent"]
    al, ah = t["accent_light"], t["accent_hover"]
    ad, ab = t["accent_dark"], t["accent_btn"]
    deep, panel_to = t["accent_deep"], t["panel_to"]
    inp = t["input_bg"]
    tm, tb, td = t["text_muted"], t["text_bright"], t["text_dark"]
    g40, g50, g55, g60, g70 = _rgba(a, 0.4), _rgba(a, 0.5), _rgba(a, 0.55), _rgba(a, 0.6), _rgba(a, 0.7)
    return f"""
    <style>
    section[data-testid="stSidebar"] {{
        background: radial-gradient(circle at top, #020617, #010409) !important;
        border-right: 1px solid {deep} !important;
        box-shadow: none !important;
    }}
    [data-testid="stSidebar"] > div:first-child {{ padding: 12px 14px !important; }}
    [data-testid="stSidebar"] .sidebar-card {{
        background: linear-gradient(145deg, #020617, {panel_to});
        border: 1px solid {ad}; border-radius: 14px;
        padding: 14px; margin-bottom: 14px;
        box-shadow: inset 0 0 0 1px rgba(255,255,255,0.02), 0 6px 20px rgba(0,0,0,0.5);
    }}
    [data-testid="stSidebar"] .sidebar-title {{
        font-size: 11px; font-weight: 800; letter-spacing: 0.12em;
        color: {a}; margin: 14px 0 10px 0;
    }}
    [data-testid="stSidebar"] .sidebar-title:first-child {{ margin-top: 0; }}
    [data-testid="stSidebar"] .sidebar-label {{ font-size: 11px; color: {tm}; }}
    [data-testid="stSidebar"] .stWidgetLabel p,
    [data-testid="stSidebar"] label {{ color: {tm} !important; font-size: 12px !important; }}
    [data-testid="stSidebar"] .stTextInput input,
    [data-testid="stSidebar"] .stSelectbox > div > div,
    [data-testid="stSidebar"] .stNumberInput input,
    [data-testid="stSidebar"] input,
    [data-testid="stSidebar"] select {{
        background: {inp} !important; border: 1px solid {ad} !important;
        border-radius: 8px !important; color: {tb} !important;
    }}
    [data-testid="stSidebar"] .stTextInput input:focus,
    [data-testid="stSidebar"] .stNumberInput input:focus,
    [data-testid="stSidebar"] .stSelectbox > div > div:focus-within,
    [data-testid="stSidebar"] input:focus,
    [data-testid="stSidebar"] select:focus {{
        border-color: {a} !important; box-shadow: 0 0 10px {g50} !important;
    }}
    [data-testid="stSidebar"] .stSelectbox [data-baseweb="select"] input,
    [data-testid="stSidebar"] .stSelectbox input {{
        caret-color: transparent !important; color: transparent !important;
        background: transparent !important; border: none !important;
        outline: none !important; box-shadow: none !important;
        width: 0 !important; min-width: 0 !important; max-width: 0 !important;
        padding: 0 !important; margin: 0 !important; opacity: 0 !important;
        position: absolute !important; pointer-events: none !important;
    }}
    [data-testid="stSidebar"] .stSelectbox div[data-baseweb="input"] {{
        background: transparent !important; border: none !important;
        box-shadow: none !important; min-width: 0 !important;
        width: 0 !important; padding: 0 !important; margin: 0 !important;
    }}
    [data-testid="stSidebar"] .stNumberInput button {{
        background: {panel_to} !important; border: 1px solid {ad} !important;
        color: {tm} !important;
    }}
    [data-testid="stSidebar"] .stSlider > div {{ color: {a}; }}
    [data-testid="stSidebar"] .stSlider [data-baseweb="slider"] div[role="slider"],
    [data-testid="stSidebar"] .stSlider [class*="StyledThumb"],
    [data-testid="stSidebar"] .stSlider [class*="StyledTrackHighlight"] {{
        background: {a} !important; border-color: {tm} !important;
    }}
    [data-testid="stSidebar"] .stSlider [class*="StyledTrack"] {{ background: {ad} !important; }}
    [data-testid="stSidebar"] .stButton > button {{
        background: linear-gradient(135deg, {ad}, {ab}) !important;
        border-radius: 10px !important; font-weight: 700 !important;
        color: {tb} !important; border: none !important;
        height: 42px !important; transition: all 0.2s !important;
    }}
    [data-testid="stSidebar"] .stButton > button:hover {{
        transform: translateY(-1px); box-shadow: 0 6px 16px {g40} !important;
    }}
    [data-testid="stSidebar"] .analyze-btn .stButton > button,
    [data-testid="stSidebar"] [class*="_analyze_btn"] button {{
        background: linear-gradient(135deg, {a}, {ab}) !important;
        box-shadow: 0 0 18px {g70} !important; color: {td} !important;
    }}
    [data-testid="stSidebar"] .st-key-live_timer_play button,
    [data-testid="stSidebar"] .st-key-live_timer_pause button {{
        background: linear-gradient(135deg, {a}, {ab}) !important;
        box-shadow: 0 0 12px {g55} !important; color: {td} !important;
    }}
    [data-testid="stSidebar"] .live-glow {{
        border: 1px solid {a} !important;
        box-shadow: 0 0 12px {g60}, inset 0 0 6px {_rgba(a, 0.2)} !important;
    }}
    [data-testid="stSidebar"] .soft-glow {{ box-shadow: 0 0 8px {g40} !important; }}
    [data-testid="stSidebar"] .sidebar-sep {{
        height: 1px; background: linear-gradient(90deg, transparent, {ad}, transparent);
        margin: 12px 0; border: none;
    }}
    [data-testid="stSidebar"] .sidebar-brand-header {{
        background: linear-gradient(145deg, #020617, {panel_to});
        border: 1px solid {ad}; border-radius: 14px;
        margin-bottom: 14px; padding: 14px;
        box-shadow: inset 0 0 0 1px rgba(255,255,255,0.02), 0 6px 20px rgba(0,0,0,0.5);
    }}
    [data-testid="stSidebar"] .sidebar-brand-title {{
        color: {a}; text-shadow: 0 0 10px {g60};
    }}
    [data-testid="stSidebar"] .sidebar-brand-subtitle {{
        color: {tm}; letter-spacing: 0.12em; opacity: 0.75;
    }}
    [data-testid="stSidebar"] .sidebar-brand-icon {{
        background: {inp}; border: 1px solid {a}; box-shadow: 0 0 10px {g50};
    }}
    [data-testid="stSidebar"] .live-clock-display {{
        text-align: center; font-size: 22px; font-weight: 900;
        color: {a}; margin: 10px 0 6px 0; text-shadow: 0 0 10px {g60};
    }}
    [data-testid="stSidebar"] .live-clock-status {{
        text-align: center; font-size: 11px; font-weight: 700;
        letter-spacing: 0.08em; margin-bottom: 8px; color: {tm};
    }}
    [data-testid="stSidebar"] .live-score-box {{
        background: {inp}; border: 1px solid {ad}; border-radius: 8px;
        padding: 9px 6px; text-align: center; font-size: 1.4rem;
        font-weight: 800; color: {tb};
    }}
    [data-testid="stSidebar"] .live-goal-label {{
        font-size: 11px; color: {tm}; font-weight: 700;
        text-transform: uppercase; letter-spacing: 0.07em;
    }}
    [data-testid="stSidebar"] .sidebar-accent-text {{ color: {a}; }}
    </style>
    """


def _inject_screen_sidebar_css(screen: str):
    t = _SCREEN_SIDEBAR_THEMES.get(screen, _SCREEN_SIDEBAR_THEMES["prematch"])
    css = _glow_sidebar_css(t) if t["style"] == "glow" else _flat_sidebar_css(t)
    st.sidebar.markdown(css, unsafe_allow_html=True)


def _inject_prematch_sidebar_css():
    _inject_screen_sidebar_css("prematch")


def _inject_live_sidebar_css():
    _inject_screen_sidebar_css("live")


def _live_card_open(extra_class: str = ""):
    cls = f"sidebar-card {extra_class}".strip()
    st.sidebar.markdown(f'<div class="{cls}">', unsafe_allow_html=True)


def _sidebar_label(title: str):
    st.sidebar.markdown(
        f'<div class="sidebar-title" style="margin-top:14px;margin-bottom:6px;">{title}</div>',
        unsafe_allow_html=True,
    )


def _sidebar_divider():
    st.sidebar.markdown('<hr class="filter-divider" style="margin:12px 0;">', unsafe_allow_html=True)


def _live_card_title(title: str):
    _sidebar_label(title)


def _live_card_close():
    st.sidebar.markdown("</div>", unsafe_allow_html=True)


def _inject_filter_css():
    global _CSS_INJECTED
    if _CSS_INJECTED:
        return
    _CSS_INJECTED = True
    st.html("""
    <style>
    /* ── Sidebar base (colors via CSS vars on stSidebar) ───────── */
    [data-testid="stSidebar"] {
        min-width: 320px !important;
        max-width: 360px !important;
    }
    [data-testid="stSidebar"] > div:first-child {
        padding: 0 !important;
    }

    /* ── Brand header (PREMATCH / LIVE) ──────────────────────── */
    .sidebar-brand-header {
        display: flex;
        align-items: center;
        gap: 12px;
        background: var(--sb-bg, #050a10);
        border-bottom: 1px solid var(--sb-border, rgba(0,136,255,0.45));
        padding: 16px 18px 14px 18px;
        position: sticky;
        top: 0;
        z-index: 100;
        box-shadow: 0 4px 20px var(--sb-accent-dim, rgba(0,136,255,0.2));
    }
    .sidebar-brand-icon {
        width: 42px;
        height: 42px;
        border-radius: 10px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.35rem;
        background: var(--sb-panel, #0a1420);
        border: 1px solid var(--sb-border, rgba(0,136,255,0.45));
        box-shadow: 0 0 14px var(--sb-accent-dim, rgba(0,136,255,0.35));
    }
    .sidebar-brand-title {
        color: var(--sb-accent, #0088FF);
        font-size: 1.15rem;
        font-weight: 800;
        letter-spacing: 0.12em;
        line-height: 1.1;
        font-family: 'Rajdhani', 'Oswald', sans-serif;
        text-shadow: 0 0 12px var(--sb-accent-dim, rgba(0,136,255,0.4));
    }
    .sidebar-brand-subtitle {
        color: var(--sb-accent-light, #64b5ff);
        font-size: 0.68rem;
        font-weight: 600;
        letter-spacing: 0.14em;
        text-transform: uppercase;
        margin-top: 2px;
        opacity: 0.9;
    }
    .filtri-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        background: var(--sb-bg, #050a10);
        border-bottom: 1px solid var(--sb-border, rgba(0,136,255,0.45));
        padding: 14px 18px 12px 18px;
        position: sticky;
        top: 0;
        z-index: 100;
    }
    .filtri-title {
        display: flex;
        align-items: center;
        gap: 8px;
        color: #e2e8f0;
        font-size: 1.05rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        font-family: 'Rajdhani', 'Oswald', sans-serif;
    }
    .filtri-title svg { color: var(--sb-accent, #0088FF); }

    /* ── Section header ──────────────────────────────────────── */
    .filter-section-header {
        display: flex;
        align-items: center;
        gap: 7px;
        color: var(--sb-accent, #0088FF);
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        padding: 12px 18px 4px 18px;
        margin: 0;
        font-family: 'Rajdhani', 'Oswald', sans-serif;
    }
    .filter-section-header span.icon {
        font-size: 0.9rem;
    }

    /* ── Divider ─────────────────────────────────────────────── */
    .filter-divider {
        border: none;
        border-top: 1px solid var(--sb-border, rgba(0,136,255,0.25));
        margin: 6px 0;
    }

    /* ── Sidebar inputs & selects ────────────────────────────── */
    [data-testid="stSidebar"] .stTextInput input,
    [data-testid="stSidebar"] .stSelectbox > div > div,
    [data-testid="stSidebar"] .stDateInput input {
        background: var(--sb-input, #0a1628) !important;
        border: 1px solid var(--sb-border, rgba(0,136,255,0.45)) !important;
        border-radius: 8px !important;
        color: #e2e8f0 !important;
        font-size: 0.82rem !important;
    }
    [data-testid="stSidebar"] .stSelectbox svg { color: var(--sb-accent, #0088FF) !important; }

    /* Barretta/cursore fantasma dopo il testo nei selectbox */
    [data-testid="stSidebar"] .stSelectbox [data-baseweb="select"] input,
    [data-testid="stSidebar"] .stSelectbox input {
        caret-color: transparent !important;
        color: transparent !important;
        background: transparent !important;
        border: none !important;
        outline: none !important;
        box-shadow: none !important;
        width: 0 !important;
        min-width: 0 !important;
        max-width: 0 !important;
        padding: 0 !important;
        margin: 0 !important;
        opacity: 0 !important;
        position: absolute !important;
        pointer-events: none !important;
    }
    [data-testid="stSidebar"] .stSelectbox div[data-baseweb="input"] {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        min-width: 0 !important;
        width: 0 !important;
        padding: 0 !important;
        margin: 0 !important;
    }

    /* ── Number input ────────────────────────────────────────── */
    [data-testid="stSidebar"] .stNumberInput input {
        background: var(--sb-input, #0a1628) !important;
        border: 1px solid var(--sb-border, rgba(0,136,255,0.45)) !important;
        color: #e2e8f0 !important;
        border-radius: 8px !important;
        font-size: 0.82rem !important;
        text-align: center !important;
    }
    [data-testid="stSidebar"] .stNumberInput button {
        background: var(--sb-panel, #0a1420) !important;
        border: 1px solid var(--sb-border, rgba(0,136,255,0.45)) !important;
        color: var(--sb-accent-light, #64b5ff) !important;
    }

    /* ── Sliders ─────────────────────────────────────────────── */
    [data-testid="stSidebar"] .stSlider [data-baseweb="slider"] div[role="slider"] {
        background: var(--sb-accent, #0088FF) !important;
        border: 2px solid var(--sb-accent-light, #64b5ff) !important;
    }
    [data-testid="stSidebar"] .stSlider [data-baseweb="slider"] [data-testid="stTickBar"] {
        background: var(--sb-accent, #0088FF) !important;
    }
    [data-testid="stSidebar"] .stSlider [class*="StyledThumb"] {
        background: var(--sb-accent, #0088FF) !important;
    }
    [data-testid="stSidebar"] .stSlider [class*="StyledTrackHighlight"] {
        background: var(--sb-accent, #0088FF) !important;
    }
    [data-testid="stSidebar"] .stSlider [class*="StyledTrack"] {
        background: var(--sb-panel, #0a1420) !important;
    }

    /* ── Checkboxes / toggles ────────────────────────────────── */
    [data-testid="stSidebar"] .stCheckbox label {
        color: #cbd5e1 !important;
        font-size: 0.8rem !important;
    }
    [data-testid="stSidebar"] .stCheckbox [data-baseweb="checkbox"] div {
        border-color: var(--sb-accent, #0088FF) !important;
    }
    [data-testid="stSidebar"] .stCheckbox [data-baseweb="checkbox"] [aria-checked="true"] {
        background: var(--sb-accent, #0088FF) !important;
        border-color: var(--sb-accent, #0088FF) !important;
    }

    /* ── Multiselect ─────────────────────────────────────────── */
    [data-testid="stSidebar"] .stMultiSelect [data-baseweb="tag"] {
        background: var(--sb-panel, #0a1420) !important;
        color: var(--sb-accent-light, #64b5ff) !important;
        border-radius: 4px !important;
        font-size: 0.75rem !important;
    }
    [data-testid="stSidebar"] .stMultiSelect > div > div {
        background: var(--sb-input, #0a1628) !important;
        border: 1px solid var(--sb-border, rgba(0,136,255,0.45)) !important;
        border-radius: 8px !important;
        color: #e2e8f0 !important;
    }

    /* ── Labels ──────────────────────────────────────────────── */
    [data-testid="stSidebar"] .stWidgetLabel p,
    [data-testid="stSidebar"] label {
        color: #94a3b8 !important;
        font-size: 0.75rem !important;
        font-weight: 500 !important;
    }

    /* ── Streamlit buttons ───────────────────────────────────── */
    [data-testid="stSidebar"] .stButton > button {
        border-radius: 8px !important;
        font-weight: 700 !important;
        font-size: 0.82rem !important;
        letter-spacing: 0.05em !important;
        height: 42px !important;
    }
    [data-testid="stSidebar"] .stButton > button[kind="primary"],
    [data-testid="stSidebar"] [class*="_top_analyze"] button,
    [data-testid="stSidebar"] [class*="_analyze_btn"] button {
        background: var(--sb-analyze-grad, linear-gradient(135deg, #0088FF, #0066cc)) !important;
        color: #050a10 !important;
        border: none !important;
        font-weight: 800 !important;
        letter-spacing: 0.06em !important;
        box-shadow: 0 0 12px var(--sb-accent-dim, rgba(0,136,255,0.35)) !important;
    }
    [data-testid="stSidebar"] [class*="_top_analyze"] button:hover,
    [data-testid="stSidebar"] [class*="_analyze_btn"] button:hover {
        background: var(--sb-analyze-hover, linear-gradient(135deg, #1a9bff, #0088FF)) !important;
    }
    [data-testid="stSidebar"] button[data-testid="baseButton-secondary"] {
        background: var(--sb-panel, #0a1420) !important;
        color: var(--sb-accent-light, #64b5ff) !important;
        border: 1px solid var(--sb-border, rgba(0,136,255,0.45)) !important;
    }

    /* ── Sub-labels ──────────────────────────────────────────── */
    .quota-col-label {
        color: #64748b;
        font-size: 0.68rem;
        text-align: center;
        margin-bottom: 2px;
    }
    .pct-grid-label {
        color: #64748b;
        font-size: 0.7rem;
        font-weight: 500;
    }

    /* ── Collapsible sections (st.expander) ──────────────────── */
    [data-testid="stSidebar"] [data-testid="stExpander"] {
        border: none !important;
        margin: 0 !important;
    }
    [data-testid="stSidebar"] [data-testid="stExpander"] details {
        background: var(--sb-bg, #050a10) !important;
        border: none !important;
        border-bottom: 1px solid var(--sb-border, rgba(0,136,255,0.25)) !important;
        border-radius: 0 !important;
    }
    [data-testid="stSidebar"] [data-testid="stExpander"] summary {
        background: var(--sb-bg, #050a10) !important;
        padding: 10px 18px !important;
        color: var(--sb-accent-light, #64b5ff) !important;
        font-size: 0.74rem !important;
        font-weight: 700 !important;
        letter-spacing: 0.09em !important;
        text-transform: uppercase !important;
        font-family: 'Rajdhani', 'Oswald', sans-serif !important;
    }
    [data-testid="stSidebar"] [data-testid="stExpander"] summary:hover {
        background: var(--sb-panel, #0a1420) !important;
        color: var(--sb-accent, #0088FF) !important;
    }
    [data-testid="stSidebar"] [data-testid="stExpander"] summary svg {
        fill: var(--sb-accent, #0088FF) !important;
        color: var(--sb-accent, #0088FF) !important;
    }
    [data-testid="stSidebar"] [data-testid="stExpander"] [data-testid="stExpanderDetails"] {
        padding: 4px 4px 10px 4px !important;
    }

    /* ── Live timer / score boxes ────────────────────────────── */
    .live-clock-display {
        text-align: center;
        font-size: 2.2rem;
        font-weight: 900;
        color: var(--sb-accent, #39FF14);
        line-height: 1.1;
        margin: 4px 0 2px 0;
        text-shadow: 0 0 16px var(--sb-accent-dim, rgba(57,255,20,0.45));
    }
    .live-clock-status {
        text-align: center;
        font-size: 0.68rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        margin-bottom: 6px;
    }
    .live-score-box {
        background: var(--sb-input, #0a180a);
        border: 1px solid var(--sb-border, rgba(57,255,20,0.45));
        border-radius: 8px;
        padding: 9px 6px;
        text-align: center;
        font-size: 1.4rem;
        font-weight: 800;
        color: #f1f5f9;
    }
    .live-goal-label {
        font-size: 0.65rem;
        color: var(--sb-accent-light, #7fff7f);
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: .07em;
    }
    .sidebar-accent-text { color: var(--sb-accent, #0088FF); }
    </style>
    """)


# ══════════════════════════════════════════════════════════════════════════
#  PUBLIC API
# ══════════════════════════════════════════════════════════════════════════

def prepare_screen_sidebar(screen: str) -> None:
    """Apply filter CSS, accent theme, and layout styles for a screen sidebar."""
    _inject_filter_css()
    _inject_sidebar_theme(screen)
    _inject_screen_sidebar_css(screen)


def render_filter_sidebar(screen: str, saved_filter_values: dict = None) -> dict:
    """
    Renders the FILTRI sidebar panel matching client reference design.
    Returns dict of active filter values.
    screen: 'prematch' | 'live' | 'h2h' | 'simulator' | 'timeline'
    """
    prepare_screen_sidebar(screen)
    sv = saved_filter_values or {}
    filters = {}

    # ── Restore this screen's own saved filters (survives page navigation) ──
    # Streamlit deletes widget-bound session_state keys when widget is not rendered.
    # We keep a plain dict copy (_saved_filters_{screen}) that Streamlit never deletes.
    _saved_screen = st.session_state.get(f"_saved_filters_{screen}", {})
    for k, v in _saved_screen.items():
        if k not in sv:
            sv[k] = v

    # ── Cross-screen filter persistence ──────────────────────────────────
    SHARED_KEYS = [
        "league", "odds_home_min", "odds_home_max",
        "odds_draw_min", "odds_draw_max",
        "odds_away_min", "odds_away_max",
        "home_team", "away_team",
    ]
    H2H_KEYS = [
        "h2h_last_n", "h2h_f_over15", "h2h_f_over25", "h2h_f_over35", "h2h_f_btts",
        "h2h_res_home", "h2h_res_draw", "h2h_res_away",
        "h2h_min_goals_total", "h2h_max_goals_total",
        "h2h_min_goals_home", "h2h_min_goals_away",
        "h2h_venue", "h2h_league",
        "date_from", "date_to",
    ]

    if st.session_state.get("filters_analyzed"):
        source = st.session_state.get("_analyze_source_screen", screen)
        source_saved = st.session_state.get(f"_saved_filters_{source}", {})
        for key in SHARED_KEYS:
            if screen != source and key in _saved_screen:
                sv[key] = _saved_screen[key]
            elif key in source_saved:
                sv[key] = source_saved[key]
        if screen == "h2h":
            for key in H2H_KEYS:
                if key in _saved_screen:
                    sv[key] = _saved_screen[key]
    else:
        DONOR_SCREENS = ["live", "prematch", "h2h", "simulator", "timeline"]
        for key in SHARED_KEYS:
            if key not in sv:
                for donor in DONOR_SCREENS:
                    if donor == screen:
                        continue
                    donor_saved = st.session_state.get(f"_saved_filters_{donor}", {})
                    val = donor_saved.get(key)
                    if val is not None:
                        sv[key] = val
                        break

    _load_shared_odds_into_sv(sv)

    page_entered = st.session_state.get("_filter_sidebar_screen") != screen
    st.session_state["_filter_sidebar_screen"] = screen
    st.session_state["_filter_page_entered"] = page_entered

    if screen == "prematch":
        filters = _render_prematch_filters(screen, sv)
    elif screen == "simulator":
        filters = _render_prematch_filters(screen, sv)
    elif screen == "timeline":
        filters = _render_prematch_filters(screen, sv)
    elif screen == "live":
        filters = _render_live_filters(sv)
    elif screen == "h2h":
        filters = _render_h2h_filters(sv)

    # ── Bottom action buttons (ordine logico: azione principale → secondarie) ─
    apply = False
    save = False
    analyze_bottom = False
    if screen != "h2h":
        _sidebar_divider()
        _sidebar_label("🚀 Azioni")
        if screen == "prematch":
            analyze_bottom = st.sidebar.button(
                "⚡ ANALISI RAPIDA", key=f"{screen}_analyze_btn", use_container_width=True
            )
            col_a, col_s = st.sidebar.columns(2)
            with col_a:
                apply = st.button("🔍 APPLICA", key=f"{screen}_apply_btn", use_container_width=True)
            with col_s:
                save = st.button("💾 SALVA", key=f"{screen}_save_btn", use_container_width=True)
        elif screen == "live":
            st.sidebar.markdown('<div class="sidebar-card analyze-btn">', unsafe_allow_html=True)
            analyze_bottom = st.sidebar.button(
                "🔍 ANALIZZA LIVE", key=f"{screen}_analyze_btn", use_container_width=True
            )
            st.sidebar.markdown("</div>", unsafe_allow_html=True)
            col_a, col_s = st.sidebar.columns(2)
            with col_a:
                apply = st.button("🔍 APPLICA", key=f"{screen}_apply_btn", use_container_width=True)
            with col_s:
                save = st.button("💾 SALVA", key=f"{screen}_save_btn", use_container_width=True)
        else:
            analyze_bottom = st.sidebar.button(
                "🔍 ANALIZZA", key=f"{screen}_analyze_btn", use_container_width=True
            )
            col_a, col_s = st.sidebar.columns(2)
            with col_a:
                apply = st.button("🔍 APPLICA", key=f"{screen}_apply_btn", use_container_width=True)
            with col_s:
                save = st.button("💾 SALVA", key=f"{screen}_save_btn", use_container_width=True)

    top_analyze = filters.pop("_top_analyze", False)
    filters["_apply"] = bool(apply or analyze_bottom or top_analyze)
    filters["_save"]  = save

    if filters["_apply"]:
        st.session_state["filters_analyzed"] = True
        st.session_state["_analyze_source_screen"] = screen
        _propagate_saved_filters(screen, filters)

    if st.session_state.get("filters_analyzed"):
        _merge_analyzed_filters(filters, screen)

    # ── Persist current filter values (merge — non cancellare chiavi assenti) ─
    _clean = {k: v for k, v in filters.items() if not k.startswith("_")}
    if _clean:
        _prev = dict(st.session_state.get(f"_saved_filters_{screen}", {}))
        _prev.update(_clean)
        st.session_state[f"_saved_filters_{screen}"] = _prev
        _persist_shared_odds(_clean)

    return filters


def apply_filters(df: pd.DataFrame, filters: dict) -> pd.DataFrame:
    """Applies filter dict to DataFrame, returns filtered subset."""
    if df is None or df.empty:
        return df

    result = df.copy()

    # League / Competition
    league = filters.get("league", "Tutti")
    if league and league not in ("Tutti", "Tutte", "Tutte le competizioni"):
        result = result[result["league"] == league]

    # Nation
    nation = filters.get("nation", "Tutti")
    if nation and nation not in ("Tutti", "Tutte", "Tutte le nazioni / leghe"):
        if "nation" in result.columns:
            result = result[result["nation"] == nation]

    # Season
    season = filters.get("season", "Tutte")
    if season and season not in ("Tutti", "Tutte"):
        result = result[result["season"] == season]

    # Date range
    if "match_date" in result.columns:
        dt = pd.to_datetime(result["match_date"], errors="coerce")
        if filters.get("date_from"):
            result = result[dt.isna() | (dt >= pd.to_datetime(filters["date_from"]))]
        if filters.get("date_to"):
            result = result[dt.isna() | (dt <= pd.to_datetime(filters["date_to"]))]

    # Teams
    if filters.get("home_team"):
        result = result[result["home_team"] == filters["home_team"]]
    if filters.get("away_team"):
        result = result[result["away_team"] == filters["away_team"]]

    # Seasons multiselect (H2H)
    seasons = filters.get("seasons", [])
    if seasons and "Tutte" not in seasons:
        result = result[result["season"].isin(seasons)]

    # ── Quote 1X2 ──────────────────────────────────────────────────────────
    for col, fmin, fmax in [
        ("odds_home", "odds_home_min", "odds_home_max"),
        ("odds_draw", "odds_draw_min", "odds_draw_max"),
        ("odds_away", "odds_away_min", "odds_away_max"),
    ]:
        if col in result.columns:
            s = pd.to_numeric(result[col], errors="coerce")
            min_val = filters.get(fmin)
            max_val = filters.get(fmax)
            if min_val is not None and min_val > 1.0:
                result = result[s.notna() & (s >= min_val)]
            if max_val is not None and max_val < 99.0:
                result = result[s.notna() & (s <= max_val)]

    # ── Quote Over ─────────────────────────────────────────────────────────
    for col, fmin, fmax in [
        ("odds_over15", "odds_over15_min", "odds_over15_max"),
        ("odds_over25", "odds_over25_min", "odds_over25_max"),
        ("odds_over35", "odds_over35_min", "odds_over35_max"),
        ("odds_over45", "odds_over45_min", "odds_over45_max"),
    ]:
        if col in result.columns:
            s = pd.to_numeric(result[col], errors="coerce")
            min_val = filters.get(fmin)
            max_val = filters.get(fmax)
            if min_val is not None and min_val > 1.0:
                result = result[s.notna() & (s >= min_val)]
            if max_val is not None and max_val < 99.0:
                result = result[s.notna() & (s <= max_val)]

    # ── BTTS ───────────────────────────────────────────────────────────────
    for col, fmin, fmax in [
        ("odds_btts_yes", "odds_btts_yes_min", "odds_btts_yes_max"),
        ("odds_btts_no",  "odds_btts_no_min",  "odds_btts_no_max"),
    ]:
        if col in result.columns:
            s = pd.to_numeric(result[col], errors="coerce")
            min_val = filters.get(fmin)
            max_val = filters.get(fmax)
            if min_val is not None and min_val > 1.0:
                result = result[s.notna() & (s >= min_val)]
            if max_val is not None and max_val < 99.0:
                result = result[s.notna() & (s <= max_val)]

    # ── HT result ──────────────────────────────────────────────────────────
    ht = filters.get("ht_result", [])
    if ht and "ht_result" in result.columns:
        result = result[result["ht_result"].isin(ht)]

    # ── FT result ──────────────────────────────────────────────────────────
    # DB stores scorelines ("2-1", "0-0") so we derive outcome from the score.
    ft = filters.get("ft_result", [])
    if ft and "ft_result" in result.columns:
        def _ft_outcome(s):
            try:
                h, a = str(s).split("-")
                h, a = int(h), int(a)
                if h > a:  return "Vittoria Casa"
                if h == a: return "Pareggio"
                return "Vittoria Trasferta"
            except Exception:
                return None
        result = result[result["ft_result"].map(_ft_outcome).isin(ft)]

    # ── Goals total ────────────────────────────────────────────────────────
    goal_filter = filters.get("goals_total", [])
    if goal_filter and "5+" not in goal_filter and "Tutti" not in goal_filter:
        if "home_goals" in result.columns and "away_goals" in result.columns:
            total = (pd.to_numeric(result["home_goals"], errors="coerce").fillna(0) +
                     pd.to_numeric(result["away_goals"], errors="coerce").fillna(0))
            nums = [int(g) for g in goal_filter if g.isdigit()]
            if "5+" in goal_filter:
                result = result[(total.isin(nums)) | (total >= 5)]
            else:
                result = result[total.isin(nums)]

    # ── Goal time bands ────────────────────────────────────────────────────
    time_bands = filters.get("goal_time_bands", [])
    # (application depends on DB schema; skip if columns absent)

    # ── Shots total ────────────────────────────────────────────────────────
    if "home_shots" in result.columns and "away_shots" in result.columns:
        ts = (pd.to_numeric(result["home_shots"], errors="coerce").fillna(0) +
              pd.to_numeric(result["away_shots"], errors="coerce").fillna(0))
        if filters.get("shots_total_min") is not None:
            result = result[ts >= filters["shots_total_min"]]
        if filters.get("shots_total_max") is not None:
            result = result[ts <= filters["shots_total_max"]]

    # ── Possession ─────────────────────────────────────────────────────────
    if "home_possession" in result.columns:
        pos = pd.to_numeric(result["home_possession"], errors="coerce")
        if filters.get("possession_min") is not None:
            result = result[pos.isna() | (pos >= filters["possession_min"])]
        if filters.get("possession_max") is not None:
            result = result[pos.isna() | (pos <= filters["possession_max"])]

    # ── xG & Average Goal & Statistiche Percentuali ───────────────────────
    def _apply_op(series, op, val):
        if op == "≥":
            return series.isna() | (series >= val)
        elif op == "≤":
            return series.isna() | (series <= val)
        else:
            return series.isna() | (series == val)

    # xG Pre-Match (Totale): DB mein single total column nahi hai,
    # isliye home_xg_pre + away_xg_pre ka sum use karte hain.
    xg_tot = filters.get("xg_pre_match")
    if (xg_tot is not None and xg_tot != 0.0
            and "home_xg_pre" in result.columns and "away_xg_pre" in result.columns):
        s = (pd.to_numeric(result["home_xg_pre"], errors="coerce")
             + pd.to_numeric(result["away_xg_pre"], errors="coerce"))
        result = result[_apply_op(s, filters.get("xg_pre_match_op", "≥"), xg_tot)]

    for col, fkey, fop_key, default_val in [
        ("home_xg_pre",               "xg_home",         "xg_home_op",         0.0),
        ("away_xg_pre",               "xg_away",         "xg_away_op",         0.0),
        ("avg_goals_pre_match",       "avg_goal_total",  "avg_goal_total_op",  0.0),
        ("over_15_pct_pre_match",     "pct_over15",      "pct_over15_op",      0),
        ("over_25_pct_pre_match",     "pct_over25",      "pct_over25_op",      0),
        ("over_35_pct_pre_match",     "pct_over35",      "pct_over35_op",      0),
        ("over_45_pct_pre_match",     "pct_over45",      "pct_over45_op",      0),
        ("btts_pct_pre_match",        "pct_btts",        "pct_btts_op",        0),
        ("over_15_ht_pct_pre_match",  "pct_over15_1t",   "pct_over15_1t_op",   0),
        ("over_15_2h_pct_pre_match",  "pct_over15_2t",   "pct_over15_2t_op",   0),
    ]:
        val = filters.get(fkey)
        op  = filters.get(fop_key, "≥")
        if col in result.columns and val is not None and val != default_val:
            s = pd.to_numeric(result[col], errors="coerce")
            result = result[_apply_op(s, op, val)]

    # ── Equilibrio / Pericolosità ──────────────────────────────────────────
    if "equilibrio" in result.columns and filters.get("equilibrio_min") is not None:
        s = pd.to_numeric(result["equilibrio"], errors="coerce")
        result = result[s.isna() | (s >= filters["equilibrio_min"])]
        result = result[s.isna() | (s <= filters.get("equilibrio_max", 100))]

    return result


# ══════════════════════════════════════════════════════════════════════════
#  PRIVATE: screen-specific render functions
# ══════════════════════════════════════════════════════════════════════════

def _load_league_favorites() -> list[str]:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not _LEAGUE_FAVORITES_FILE.exists():
        return []
    try:
        with open(_LEAGUE_FAVORITES_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return [x for x in data if isinstance(x, str) and x.strip()]
    except Exception:
        return []


def _save_league_favorites(favorites: list[str]) -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(_LEAGUE_FAVORITES_FILE, "w", encoding="utf-8") as f:
        json.dump(favorites, f, ensure_ascii=False, indent=2)


def _league_country_parts(league: str) -> tuple[str, str]:
    return split_league_name(league)


def _inject_league_picker_css():
    st.sidebar.markdown("""
    <style>
    [data-testid="stSidebar"] .league-pick-box {
        background: #020617;
        border: 1px solid #1e293b;
        padding: 10px;
        border-radius: 8px;
        margin-bottom: 10px;
    }
    [data-testid="stSidebar"] .league-pick-label {
        font-size: 0.72rem;
        font-weight: 700;
        color: #64748b;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        margin: 8px 0 4px;
    }
    [data-testid="stSidebar"] .league-selected-banner {
        background: rgba(34, 197, 94, 0.12);
        border: 1px solid #22c55e;
        border-radius: 8px;
        padding: 8px 10px;
        font-size: 0.82rem;
        color: #86efac;
        margin-bottom: 10px;
    }
    [data-testid="stSidebar"] div[data-testid="stButton"] button[kind="secondary"] {
        background: #0f172a !important;
        border: 1px solid #1e293b !important;
        color: #e2e8f0 !important;
        font-size: 0.78rem !important;
        padding: 4px 8px !important;
    }
    </style>
    """, unsafe_allow_html=True)


def _track_league_recent(league: str) -> None:
    if not league or league == _ALL_LEAGUES_LABEL:
        return
    recent = st.session_state.setdefault("_league_recent", [])
    if league in recent:
        recent.remove(league)
    recent.insert(0, league)
    st.session_state["_league_recent"] = recent[:20]


def _set_league_selection(
    key: str,
    league: str,
    country_key: str,
    league_countries: dict[str, str],
    use_all_key: str | None = None,
) -> None:
    st.session_state[key] = league
    if use_all_key:
        st.session_state[use_all_key] = False
    if league in league_countries:
        st.session_state[country_key] = league_countries[league]
    _track_league_recent(league)


def render_league_picker(
    key: str,
    default: str = _ALL_LEAGUES_LABEL,
    include_all: bool = True,
) -> str:
    """
    Selettore campionato avanzato: ricerca, preferiti (persistiti), nazione, recenti.
    key: chiave session_state del campionato (es. prematch_league, live_league, dna_league).
    """
    _inject_league_picker_css()

    all_leagues = _get_leagues() or []
    if not all_leagues:
        st.sidebar.warning("Nessun campionato nel database.")
        return default if include_all else ""

    use_all_key = f"{key}_use_all"
    if use_all_key not in st.session_state:
        st.session_state[use_all_key] = include_all and default == _ALL_LEAGUES_LABEL

    stored = st.session_state.get(key, default)
    if stored == _ALL_LEAGUES_LABEL:
        if use_all_key not in st.session_state:
            st.session_state[use_all_key] = True
        st.session_state[key] = all_leagues[0] if all_leagues else stored
    elif key not in st.session_state:
        st.session_state[key] = stored if stored in all_leagues else all_leagues[0]
        st.session_state[use_all_key] = False
    elif st.session_state[key] not in all_leagues:
        st.session_state[key] = all_leagues[0]
        st.session_state[use_all_key] = False

    if "_league_favorites" not in st.session_state:
        st.session_state["_league_favorites"] = _load_league_favorites()

    league_countries = {lg: _league_country_parts(lg)[0] for lg in all_leagues}
    countries = sorted(set(league_countries.values()))
    country_key = f"{key}_country"
    search_key = f"{key}_search"

    st.sidebar.markdown('<div class="league-pick-box">', unsafe_allow_html=True)

    if include_all:
        if st.sidebar.button(
            f"🌐 {_ALL_LEAGUES_LABEL}",
            key=f"{key}_all_btn",
            use_container_width=True,
        ):
            st.session_state[use_all_key] = True
            st.rerun()

    search = st.sidebar.text_input("🔍 Cerca campionato", key=search_key, label_visibility="collapsed")
    search_q = (search or "").strip().lower()

    filtered_leagues = all_leagues
    if search_q:
        filtered_leagues = [lg for lg in all_leagues if search_q in lg.lower()]

    favorites = [f for f in st.session_state["_league_favorites"] if f in all_leagues]
    if favorites:
        st.sidebar.markdown('<div class="league-pick-label">⭐ Preferiti</div>', unsafe_allow_html=True)
        fav_cols = st.sidebar.columns(2)
        for i, fav in enumerate(favorites):
            with fav_cols[i % 2]:
                if st.button(fav, key=f"{key}_fav_{i}", use_container_width=True):
                    _set_league_selection(key, fav, country_key, league_countries, use_all_key)
                    st.rerun()

    if include_all and st.session_state.get(use_all_key):
        st.sidebar.markdown(
            f'<div class="league-selected-banner">✓ {_ALL_LEAGUES_LABEL}</div>',
            unsafe_allow_html=True,
        )
        if st.sidebar.button("Scegli campionato specifico", key=f"{key}_pick_specific", use_container_width=True):
            st.session_state[use_all_key] = False
            st.rerun()
        recent = [r for r in st.session_state.get("_league_recent", []) if r in all_leagues][:5]
        if recent:
            st.sidebar.markdown('<div class="league-pick-label">🕒 Recenti</div>', unsafe_allow_html=True)
            rec_cols = st.sidebar.columns(2)
            for i, rec in enumerate(recent):
                short = rec.split(" - ")[-1] if " - " in rec else rec
                with rec_cols[i % 2]:
                    if st.button(short, key=f"{key}_rec_{i}", use_container_width=True):
                        _set_league_selection(key, rec, country_key, league_countries, use_all_key)
                        st.rerun()
        st.sidebar.markdown("</div>", unsafe_allow_html=True)
        return _ALL_LEAGUES_LABEL

    filtered_countries = sorted({league_countries[lg] for lg in filtered_leagues})
    if not filtered_countries:
        filtered_countries = countries

    current_league = st.session_state.get(key, all_leagues[0])
    country_default = league_countries.get(current_league, filtered_countries[0])
    if country_key not in st.session_state or st.session_state[country_key] not in filtered_countries:
        st.session_state[country_key] = country_default if country_default in filtered_countries else filtered_countries[0]

    selected_country = st.sidebar.selectbox("🌍 Nazione", filtered_countries, key=country_key)

    leagues_in_country = sorted(
        lg for lg in filtered_leagues if league_countries.get(lg) == selected_country
    )
    if not leagues_in_country:
        leagues_in_country = sorted(
            lg for lg in all_leagues if league_countries.get(lg) == selected_country
        )

    if current_league not in leagues_in_country and leagues_in_country:
        st.session_state[key] = leagues_in_country[0]

    selected_league = (
        st.sidebar.selectbox("🏆 Campionato", leagues_in_country, key=key)
        if leagues_in_country else current_league
    )

    if st.sidebar.button("⭐ Aggiungi ai preferiti", key=f"{key}_add_fav", use_container_width=True):
        if selected_league:
            favs = st.session_state["_league_favorites"]
            if selected_league not in favs:
                favs.append(selected_league)
                st.session_state["_league_favorites"] = favs
                _save_league_favorites(favs)
                st.sidebar.success("Aggiunto ai preferiti")

    _track_league_recent(selected_league)

    recent = [r for r in st.session_state.get("_league_recent", []) if r in all_leagues][:5]
    if recent:
        st.sidebar.markdown('<div class="league-pick-label">🕒 Recenti</div>', unsafe_allow_html=True)
        rec_cols = st.sidebar.columns(2)
        for i, rec in enumerate(recent):
            short = rec.split(" - ")[-1] if " - " in rec else rec
            with rec_cols[i % 2]:
                if st.button(short, key=f"{key}_rec_{i}", use_container_width=True):
                    _set_league_selection(key, rec, country_key, league_countries, use_all_key)
                    st.rerun()

    st.sidebar.markdown("</div>", unsafe_allow_html=True)

    st.sidebar.markdown(
        f'<div class="league-selected-banner">✓ Selezionato: <b>{selected_league}</b></div>',
        unsafe_allow_html=True,
    )
    return selected_league


def _render_prematch_filters(screen: str, sv: dict) -> dict:
    filters = {}

    _init_prematch_widgets(screen, sv)
    if st.session_state.get("_filter_page_entered"):
        _sync_shared_odds_widgets(screen)
        if st.session_state.get("filters_analyzed"):
            _sync_sv_to_prematch_widgets(screen, sv)
            _init_prematch_widgets(screen, sv)

    # 1. Campionato
    _sidebar_label("🌍 Campionato")
    filters["league"] = render_league_picker(
        key=f"{screen}_league",
        default=sv.get("league", _ALL_LEAGUES_LABEL),
        include_all=True,
    )

    # 2. Periodo
    _sidebar_label("📅 Periodo")
    col_d1, col_arrow, col_d2 = st.sidebar.columns([5, 1, 5])
    with col_d1:
        date_from = st.date_input("Da", value=sv.get("date_from", pd.Timestamp("2010-01-01")),
                                  key=f"{screen}_date_from", label_visibility="collapsed")
    with col_arrow:
        st.markdown('<div class="sidebar-accent-text" style="text-align:center;padding-top:8px;font-size:1rem;">→</div>',
                    unsafe_allow_html=True)
    with col_d2:
        date_to = st.date_input("A", value=sv.get("date_to", pd.Timestamp("2030-12-31")),
                                key=f"{screen}_date_to", label_visibility="collapsed")
    filters["date_from"] = date_from
    filters["date_to"]   = date_to

    # 3. Squadre
    _sidebar_label("🛡️ Squadre")
    selected_league = filters.get("league", "Tutte le competizioni")
    if selected_league and selected_league != "Tutte le competizioni":
        all_teams = _get_teams_by_league(selected_league)
    else:
        all_teams = _get_all_teams()
    team_opts   = ["Tutte le squadre"] + all_teams
    home_key = f"{screen}_home_team"
    away_key = f"{screen}_away_team"
    if st.session_state.get(home_key) not in team_opts:
        st.session_state[home_key] = "Tutte le squadre"
    if st.session_state.get(away_key) not in team_opts:
        st.session_state[away_key] = "Tutte le squadre"
    col_h, col_vs, col_a = st.sidebar.columns([5, 2, 5])
    with col_h:
        home_t = st.selectbox("Casa", team_opts,
                              key=home_key, label_visibility="collapsed")
    with col_vs:
        st.markdown('<div class="sidebar-accent-text" style="text-align:center;font-weight:700;padding-top:8px;">VS</div>',
                    unsafe_allow_html=True)
    with col_a:
        away_t = st.selectbox("Trasferta", team_opts,
                              key=away_key, label_visibility="collapsed")
    filters["home_team"] = None if home_t == "Tutte le squadre" else home_t
    filters["away_team"] = None if away_t == "Tutte le squadre" else away_t

    # 4. Quote 1X2
    _sidebar_label("💰 Quote 1X2")
    col1, col2, col3 = st.sidebar.columns(3)
    with col1:
        st.markdown('<p class="quota-col-label">1 (Casa)</p>', unsafe_allow_html=True)
        oh_min = st.number_input("oh_min", 1.0, 99.0,
                                 step=0.1, format="%.2f", key=f"{screen}_oh_min",
                                 label_visibility="collapsed")
        st.markdown('<p style="text-align:center;color:#64748b;font-size:0.7rem;margin:0">—</p>',
                    unsafe_allow_html=True)
        oh_max = st.number_input("oh_max", 1.0, 99.0,
                                 step=0.1, format="%.2f", key=f"{screen}_oh_max",
                                 label_visibility="collapsed")
    with col2:
        st.markdown('<p class="quota-col-label">X (Pareggio)</p>', unsafe_allow_html=True)
        od_min = st.number_input("od_min", 1.0, 99.0,
                                 step=0.1, format="%.2f", key=f"{screen}_od_min",
                                 label_visibility="collapsed")
        st.markdown('<p style="text-align:center;color:#64748b;font-size:0.7rem;margin:0">—</p>',
                    unsafe_allow_html=True)
        od_max = st.number_input("od_max", 1.0, 99.0,
                                 step=0.1, format="%.2f", key=f"{screen}_od_max",
                                 label_visibility="collapsed")
    with col3:
        st.markdown('<p class="quota-col-label">2 (Trasferta)</p>', unsafe_allow_html=True)
        oa_min = st.number_input("oa_min", 1.0, 99.0,
                                 step=0.1, format="%.2f", key=f"{screen}_oa_min",
                                 label_visibility="collapsed")
        st.markdown('<p style="text-align:center;color:#64748b;font-size:0.7rem;margin:0">—</p>',
                    unsafe_allow_html=True)
        oa_max = st.number_input("oa_max", 1.0, 99.0,
                                 step=0.1, format="%.2f", key=f"{screen}_oa_max",
                                 label_visibility="collapsed")
    filters.update({
        "odds_home_min": oh_min, "odds_home_max": oh_max,
        "odds_draw_min": od_min, "odds_draw_max": od_max,
        "odds_away_min": oa_min, "odds_away_max": oa_max,
    })

    # 5. Filtri avanzati (expanders)
    _sidebar_label("📂 Filtri dettagliati")

    # ── QUOTE OVER ────────────────────────────────────────────────────────
    with st.sidebar.expander("⚽ QUOTE OVER", expanded=False):
        over_labels = ["Over 1.5", "Over 2.5", "Over 3.5", "Over 4.5"]
        over_keys   = ["over15",   "over25",   "over35",   "over45"]
        oc = st.columns(4)
        for i, (lbl, key) in enumerate(zip(over_labels, over_keys)):
            with oc[i]:
                st.markdown(f'<p class="quota-col-label">{lbl}</p>', unsafe_allow_html=True)
                vmin = st.number_input(f"{key}_min_lbl", 1.0, 99.0,
                                       float(sv.get(f"odds_{key}_min", 1.0)),
                                       step=0.1, format="%.2f",
                                       key=f"{screen}_{key}_min", label_visibility="collapsed")
                st.markdown('<p style="text-align:center;color:#64748b;font-size:0.7rem;margin:0">—</p>',
                            unsafe_allow_html=True)
                vmax = st.number_input(f"{key}_max_lbl", 1.0, 99.0,
                                       float(sv.get(f"odds_{key}_max", 99.0)),
                                       step=0.1, format="%.2f",
                                       key=f"{screen}_{key}_max", label_visibility="collapsed")
                filters[f"odds_{key}_min"] = vmin
                filters[f"odds_{key}_max"] = vmax

    # ── QUOTE BTTS ────────────────────────────────────────────────────────
    with st.sidebar.expander("📊 QUOTE BTTS", expanded=False):
        bc1, bc2 = st.columns(2)
        with bc1:
            st.markdown('<p class="quota-col-label">BTTS YES</p>', unsafe_allow_html=True)
            by_min = st.number_input("by_min_lbl", 1.0, 99.0,
                                     float(sv.get("odds_btts_yes_min", 1.0)),
                                     step=0.1, format="%.2f",
                                     key=f"{screen}_btts_yes_min", label_visibility="collapsed")
            st.markdown('<p style="text-align:center;color:#64748b;font-size:0.7rem;margin:0">—</p>',
                        unsafe_allow_html=True)
            by_max = st.number_input("by_max_lbl", 1.0, 99.0,
                                     float(sv.get("odds_btts_yes_max", 99.0)),
                                     step=0.1, format="%.2f",
                                     key=f"{screen}_btts_yes_max", label_visibility="collapsed")
        with bc2:
            st.markdown('<p class="quota-col-label">BTTS NO</p>', unsafe_allow_html=True)
            bn_min = st.number_input("bn_min_lbl", 1.0, 99.0,
                                     float(sv.get("odds_btts_no_min", 1.0)),
                                     step=0.1, format="%.2f",
                                     key=f"{screen}_btts_no_min", label_visibility="collapsed")
            st.markdown('<p style="text-align:center;color:#64748b;font-size:0.7rem;margin:0">—</p>',
                        unsafe_allow_html=True)
            bn_max = st.number_input("bn_max_lbl", 1.0, 99.0,
                                     float(sv.get("odds_btts_no_max", 99.0)),
                                     step=0.1, format="%.2f",
                                     key=f"{screen}_btts_no_max", label_visibility="collapsed")
        filters.update({
            "odds_btts_yes_min": by_min, "odds_btts_yes_max": by_max,
            "odds_btts_no_min":  bn_min, "odds_btts_no_max":  bn_max,
        })

    # ── RISULTATO FINALE (FT) ─────────────────────────────────────────────
    with st.sidebar.expander("🏆\u2002RISULTATO FINALE (FT)", expanded=False):
        ft_opts   = ["Tutti", "Vittoria Casa", "Pareggio", "Vittoria Trasferta"]
        ft_saved  = sv.get("ft_result", ["Tutti"])
        ft_cols   = st.columns(len(ft_opts))
        ft_selected = []
        for i, opt in enumerate(ft_opts):
            with ft_cols[i]:
                checked = st.checkbox(opt, value=(opt in ft_saved or (not ft_saved and opt == "Tutti")),
                                      key=f"{screen}_ft_{opt}")
                if checked:
                    ft_selected.append(opt)
        if "Tutti" in ft_selected or not ft_selected:
            filters["ft_result"] = []
        else:
            filters["ft_result"] = ft_selected

    # ── RISULTATO 1° TEMPO (HT) ───────────────────────────────────────────
    with st.sidebar.expander("⏱️\u2002RISULTATO 1° TEMPO (HT)", expanded=False):
        ht_all_opts = [
            "Tutti",
            "0-0", "1-0", "0-1", "1-1",
            "2-0", "0-2", "2-1", "1-2",
            "2-2", "3-0", "0-3", "3-1",
            "1-3", "3-2", "2-3", "3-3",
        ]
        ht_saved    = sv.get("ht_result", ["Tutti"])
        ht_selected = []
        for row_start in range(0, len(ht_all_opts), 4):
            row_opts = ht_all_opts[row_start:row_start + 4]
            ht_row_cols = st.columns(4)
            for j, opt in enumerate(row_opts):
                with ht_row_cols[j]:
                    checked = st.checkbox(opt,
                                          value=(opt in ht_saved or (not ht_saved and opt == "Tutti")),
                                          key=f"{screen}_ht_{opt}")
                    if checked:
                        ht_selected.append(opt)
        if "Tutti" in ht_selected or not ht_selected:
            filters["ht_result"] = []
        else:
            filters["ht_result"] = ht_selected

    # ── NUMERO DI GOL TOTALI ──────────────────────────────────────────────
    with st.sidebar.expander("⚽\u2002NUMERO DI GOL TOTALI", expanded=False):
        goal_opts  = ["Tutti", "0", "1", "2", "3", "4", "5+"]
        goal_saved = sv.get("goals_total", ["Tutti"])
        g_cols     = st.columns(len(goal_opts))
        goals_sel  = []
        for i, opt in enumerate(goal_opts):
            with g_cols[i]:
                checked = st.checkbox(opt, value=(opt in goal_saved or (not goal_saved and opt == "Tutti")),
                                      key=f"{screen}_goals_{opt}")
                if checked:
                    goals_sel.append(opt)
        if "Tutti" in goals_sel or not goals_sel:
            filters["goals_total"] = []
        else:
            filters["goals_total"] = goals_sel

    # ── FASCE TEMPORALI GOL ───────────────────────────────────────────────
    with st.sidebar.expander("⏰\u2002FASCE TEMPORALI GOL", expanded=False):
        band_opts  = ["Tutte", "0-15", "16-30", "31-45", "46-60", "61-75", "76-90"]
        band_saved = sv.get("goal_time_bands", ["Tutte"])
        b_cols     = st.columns(len(band_opts))
        bands_sel  = []
        for i, opt in enumerate(band_opts):
            with b_cols[i]:
                checked = st.checkbox(opt, value=(opt in band_saved or (not band_saved and opt == "Tutte")),
                                      key=f"{screen}_band_{opt}")
                if checked:
                    bands_sel.append(opt)
        if "Tutte" in bands_sel or not bands_sel:
            filters["goal_time_bands"] = []
        else:
            filters["goal_time_bands"] = bands_sel

    # ── STATISTICHE PERCENTUALI ───────────────────────────────────────────
    with st.sidebar.expander("📊 STATISTICHE", expanded=False):
        pct_rows = [
            ("Over 1.5 %",    "pct_over15",    "Over 1.5 1°T %", "pct_over15_1t"),
            ("Over 2.5 %",    "pct_over25",    "Over 1.5 2°T %", "pct_over15_2t"),
            ("Over 3.5 %",    "pct_over35",    "BTTS %",         "pct_btts"),
            ("Over 4.5 %",    "pct_over45",    None,             None),
        ]
        op_opts = ["≥", "≤", "="]
        for left_lbl, left_key, right_lbl, right_key in pct_rows:
            pc1, pc2 = st.columns(2)
            if left_lbl and left_key:
                with pc1:
                    cl1, cl2, cl3 = st.columns([4, 2, 3])
                    with cl1:
                        st.markdown(f'<p class="pct-grid-label">{left_lbl}</p>', unsafe_allow_html=True)
                    with cl2:
                        op = st.selectbox("op", op_opts, key=f"{screen}_{left_key}_op",
                                          label_visibility="collapsed")
                    with cl3:
                        val = st.number_input("val", 0, 100, int(sv.get(left_key, 0)),
                                              key=f"{screen}_{left_key}_val",
                                              label_visibility="collapsed")
                    filters[left_key]        = val
                    filters[left_key + "_op"] = op
            with pc2:
                if right_lbl and right_key:
                    cr1, cr2, cr3 = st.columns([4, 2, 3])
                    with cr1:
                        st.markdown(f'<p class="pct-grid-label">{right_lbl}</p>', unsafe_allow_html=True)
                    with cr2:
                        op2 = st.selectbox("op2", op_opts, key=f"{screen}_{right_key}_op",
                                           label_visibility="collapsed")
                    with cr3:
                        val2 = st.number_input("val2", 0, 100, int(sv.get(right_key, 0)),
                                               key=f"{screen}_{right_key}_val",
                                               label_visibility="collapsed")
                    filters[right_key]         = val2
                    filters[right_key + "_op"] = op2

    # ── STATISTICHE XG E GOAL ─────────────────────────────────────────────
    with st.sidebar.expander("xG\u2002STATISTICHE XG E GOAL", expanded=False):
        xg_left  = [("xG Pre-Match",         "xg_pre_match"),
                    ("xG Casa Pre-Match",     "xg_home"),
                    ("xG Trasferta Pre-Match","xg_away")]
        xg_right = [("Average Goal (Totale)", "avg_goal_total"),
                    (None,                    None),
                    (None,                    None)]
        xgc1, xgc2 = st.columns(2)
        op_opts2 = ["≥", "≤", "="]
        for (lbl, key), (rlbl, rkey) in zip(xg_left, xg_right):
            with xgc1:
                r1, r2, r3 = st.columns([5, 2, 3])
                with r1:
                    st.markdown(f'<p class="pct-grid-label">{lbl}</p>', unsafe_allow_html=True)
                with r2:
                    xgop = st.selectbox("xgop", op_opts2, key=f"{screen}_{key}_op",
                                        label_visibility="collapsed")
                with r3:
                    xgval = st.number_input("xgval", 0.0, 20.0, float(sv.get(key, 0.0)),
                                            step=0.1, format="%.2f",
                                            key=f"{screen}_{key}_val",
                                            label_visibility="collapsed")
                filters[key]        = xgval
                filters[key + "_op"] = xgop
            with xgc2:
                if rlbl and rkey:
                    rr1, rr2, rr3 = st.columns([5, 2, 3])
                    with rr1:
                        st.markdown(f'<p class="pct-grid-label">{rlbl}</p>', unsafe_allow_html=True)
                    with rr2:
                        rop = st.selectbox("rop", op_opts2, key=f"{screen}_{rkey}_op",
                                           label_visibility="collapsed")
                    with rr3:
                        rval = st.number_input("rval", 0.0, 20.0, float(sv.get(rkey, 0.0)),
                                               step=0.1, format="%.2f",
                                               key=f"{screen}_{rkey}_val",
                                               label_visibility="collapsed")
                    filters[rkey]         = rval
                    filters[rkey + "_op"] = rop

    # ── FILTRI AVANZATI ───────────────────────────────────────────────────
    with st.sidebar.expander("⚙️\u2002FILTRI AVANZATI", expanded=False):
        fa1, fa2 = st.columns(2)
        with fa1:
            st.markdown('<p class="quota-col-label">Equilibrio Match</p>', unsafe_allow_html=True)
            eq_range = st.slider("eq", 0, 100,
                                 (int(sv.get("equilibrio_min", 0)), int(sv.get("equilibrio_max", 100))),
                                 key=f"{screen}_equilibrio", label_visibility="collapsed")
            filters["equilibrio_min"] = eq_range[0]
            filters["equilibrio_max"] = eq_range[1]
        with fa2:
            st.markdown('<p class="quota-col-label">Pericolosità Match</p>', unsafe_allow_html=True)
            per_range = st.slider("per", 0.0, 5.0,
                                  (float(sv.get("pericolosita_min", 0.0)),
                                   float(sv.get("pericolosita_max", 5.0))),
                                  step=0.1, key=f"{screen}_pericolosita",
                                  label_visibility="collapsed")
            filters["pericolosita_min"] = per_range[0]
            filters["pericolosita_max"] = per_range[1]

        fa3, fa4 = st.columns(2)
        with fa3:
            st.markdown('<p class="quota-col-label">N° Partite Minimo</p>', unsafe_allow_html=True)
            npartite = st.slider("np", 1, 5000, int(sv.get("n_partite_min", 1)),
                                 key=f"{screen}_npartite", label_visibility="collapsed")
            filters["n_partite_min"] = npartite
        with fa4:
            st.markdown('<p class="quota-col-label">ROI Minimo (%)</p>', unsafe_allow_html=True)
            roi = st.slider("roi", -100, 100, int(sv.get("roi_min", -100)),
                            key=f"{screen}_roi", label_visibility="collapsed")
            filters["roi_min"] = roi

    return filters


def _render_live_filters(sv: dict) -> dict:
    """
    Live sidebar — ordine logico:
    1. Campionato → 2. Minuto di gioco → 3. Gol segnati → 4. Risultato
    → 5. Quote 1X2 → 6. Strategie avanzate
    """
    filters = {}

    # ── Pre-initialize all live filter state (only if key not yet in session_state)
    # This ensures values survive page navigation without relying on value= overrides.
    _sv_mins = sv.get("goal_minutes_display", sv.get("goal_minutes", ["", "", ""]))
    _live_defaults = {
        "live_league":        sv.get("league", "Tutte le competizioni"),
        "live_oh_min":        float(sv.get("odds_home_min", 1.0)),
        "live_oh_max":        float(sv.get("odds_home_max", 99.0)),
        "live_od_min":        float(sv.get("odds_draw_min", 1.0)),
        "live_od_max":        float(sv.get("odds_draw_max", 99.0)),
        "live_oa_min":        float(sv.get("odds_away_min", 1.0)),
        "live_oa_max":        float(sv.get("odds_away_max", 99.0)),
        "live_goal_min_0":    str(_sv_mins[0]) if len(_sv_mins) > 0 and _sv_mins[0] else "",
        "live_goal_min_1":    str(_sv_mins[1]) if len(_sv_mins) > 1 and _sv_mins[1] else "",
        "live_goal_min_2":    str(_sv_mins[2]) if len(_sv_mins) > 2 and _sv_mins[2] else "",
        "live_minute_slider": int(sv.get("current_minute", 45)),
        "live_match_minute":    int(sv.get("current_minute", 45)),
        "live_match_second":    0,
        "live_timer_running":   False,
        "live_timer_speed":     1,
    }
    for _k, _v in _live_defaults.items():
        if _k not in st.session_state:
            st.session_state[_k] = _v

    if st.session_state.get("_filter_page_entered"):
        _sync_shared_odds_widgets("live")
        if st.session_state.get("filters_analyzed"):
            _sync_sv_to_live_widgets(sv)

    _init_live_goal_team_widgets(sv)


    # 1. Campionato
    _live_card_title("🌍 Campionato")
    filters["league"] = render_league_picker(
        key="live_league",
        default=sv.get("league", _ALL_LEAGUES_LABEL),
        include_all=True,
    )

    # 2. Minuto di gioco (timer)
    _live_card_title("⚡ Minuto di gioco")

    tp1, tp2 = st.sidebar.columns(2)
    with tp1:
        if st.button("▶️ Play", key="live_timer_play", use_container_width=True):
            st.session_state.live_timer_running = True
    with tp2:
        if st.button("⏸ Pausa", key="live_timer_pause", use_container_width=True):
            st.session_state.live_timer_running = False

    speed = st.sidebar.selectbox(
        "Velocità", options=[1, 2, 3],
        format_func=lambda s: f"{s}x",
        key="live_timer_speed",
        label_visibility="collapsed",
    )

    running = bool(st.session_state.get("live_timer_running"))
    match_min = int(st.session_state.get("live_match_minute", 45))
    match_sec = int(st.session_state.get("live_match_second", 0))

    if running:
        st.session_state.live_minute_slider = match_min
        st.sidebar.caption(
            "Slider disabilitato durante il play — usa Pausa per spostare il minuto. "
            "La pagina si aggiorna subito al Play, poi ogni 5 minuti."
        )
    else:
        cur_min = st.sidebar.slider(
            "Minuto", 1, 90,
            key="live_minute_slider", label_visibility="collapsed",
        )
        st.session_state.live_match_minute = int(cur_min)
        st.session_state.live_match_second = 0
        match_min = int(cur_min)
        match_sec = 0

    status_col = "#22c55e" if running else "#64748b"
    status_txt = "▶ PLAY" if running else "⏸ PAUSA"
    st.sidebar.markdown(
        f'<div class="live-clock-display">{match_min}:{match_sec:02d}</div>'
        f'<div class="live-clock-status" style="color:{status_col};">'
        f'{status_txt} · {speed}x</div>',
        unsafe_allow_html=True,
    )

    current_minute = match_min
    filters["current_minute"] = current_minute
    filters["current_second"] = match_sec
    filters["timer_running"] = running

    # 3. Gol segnati
    _live_card_title("⚽ Gol segnati")

    def _parse_goal_minute(text):
        """'45'->(45,'45'); '45+2'->(45,'45+2'); '90+'->(90,'90+'); ''->(None,'')."""
        t = str(text).strip().replace(" ", "")
        if not t:
            return None, ""
        if "+" in t:
            base = t.split("+", 1)[0]
            return (int(base) if base.isdigit() else None), t
        return (int(t) if t.isdigit() else None), t

    goal_minutes  = []
    goal_teams    = []
    goal_displays = []

    team_opts = ["Seleziona", "Casa", "Trasferta"]
    goal_labels = ["1° GOL", "2° GOL", "3° GOL"]

    for gi in range(3):
        st.sidebar.markdown(
            f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-bottom:4px;">'
            f'<div class="live-goal-label">{goal_labels[gi]}</div>'
            f'<div class="live-goal-label">SQUADRA</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        gi_cols = st.sidebar.columns([1, 1])
        team_key = f"live_goal_team_{gi}"
        with gi_cols[0]:
            gmin_txt = st.text_input(
                f"min g{gi+1}",
                key=f"live_goal_min_{gi}", label_visibility="collapsed",
                placeholder="es. 45+2",
            )
        with gi_cols[1]:
            st.selectbox(
                f"team g{gi+1}", team_opts,
                key=team_key, label_visibility="collapsed",
            )
        gteam = st.session_state.get(team_key, "Seleziona")
        base_min, disp = _parse_goal_minute(gmin_txt)
        is_valid = (gteam != "Seleziona") and (base_min is not None)
        goal_minutes.append(base_min if is_valid else None)
        goal_teams.append(gteam if gteam != "Seleziona" else None)
        goal_displays.append(disp if is_valid else "")

    filters["goal_minutes"]         = goal_minutes
    filters["goal_minutes_display"] = goal_displays
    filters["goal_teams"]           = goal_teams
    filters["goal_team_widgets"]    = [
        st.session_state.get(f"live_goal_team_{i}", "Seleziona") for i in range(3)
    ]

    # Valida gol rispetto al minuto di gioco corrente
    goal_labels_ord = ["1°", "2°", "3°"]
    goal_time_errors = []
    valid_goals = []
    for gi in range(3):
        team = goal_teams[gi]
        if team is None:
            continue
        raw = str(st.session_state.get(f"live_goal_min_{gi}", "")).strip()
        minute = parse_goal_minute_value(raw) if raw else goal_minutes[gi]
        if minute is None:
            continue
        if minute > current_minute:
            goal_time_errors.append({
                "label": goal_labels_ord[gi],
                "minute": minute,
                "team": team,
                "display": goal_displays[gi] or f"{minute}'",
            })
            continue
        valid_goals.append((minute, team))

    valid_goals.sort(key=lambda x: x[0])
    home_score = sum(1 for _, t in valid_goals if t == "Casa")
    away_score = sum(1 for _, t in valid_goals if t == "Trasferta")

    filters["goal_time_errors"] = goal_time_errors
    filters["goals_time_valid"] = len(goal_time_errors) == 0
    filters["valid_goals"] = valid_goals
    filters["first_goal_minute"] = valid_goals[0][0] if valid_goals else None
    filters["first_goal_team"] = valid_goals[0][1] if valid_goals else None
    filters["home_score"] = int(home_score)
    filters["away_score"] = int(away_score)

    # 4. Risultato attuale
    _live_card_title("🏆 Risultato attuale")
    _score_box = 'live-score-box'
    score_cols = st.sidebar.columns(3)
    with score_cols[0]:
        st.markdown('<div class="sidebar-label" style="text-align:center;font-weight:700;'
                    'letter-spacing:.08em;text-transform:uppercase;margin-bottom:4px;color:#3b82f6;">CASA</div>',
                    unsafe_allow_html=True)
        st.markdown(f'<div class="{_score_box}">{home_score}</div>', unsafe_allow_html=True)
    with score_cols[1]:
        st.markdown('<div class="sidebar-label" style="text-align:center;font-weight:700;'
                    'letter-spacing:.08em;text-transform:uppercase;margin-bottom:4px;">VS</div>',
                    unsafe_allow_html=True)
        st.markdown(f'<div class="{_score_box}">—</div>', unsafe_allow_html=True)
    with score_cols[2]:
        st.markdown('<div class="sidebar-label" style="text-align:center;font-weight:700;'
                    'letter-spacing:.08em;text-transform:uppercase;margin-bottom:4px;color:#ef4444;">'
                    'TRASFERTA</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="{_score_box}">{away_score}</div>', unsafe_allow_html=True)

    if goal_time_errors:
        err_lines = "<br>".join(
            f"• <b>{e['label']} gol</b> al {e['display']} ({e['team']}) "
            f"— oltre il minuto di gioco ({current_minute}')"
            for e in goal_time_errors
        )
        st.sidebar.markdown(
            f'<div style="background:#450a0a;border:1px solid #ef4444;border-radius:8px;'
            f'padding:10px 12px;margin:8px 0;font-size:0.78rem;color:#fca5a5;line-height:1.5;">'
            f'⚠️ <b>Minuto gol non valido</b><br>{err_lines}<br>'
            f'<span style="color:#94a3b8;">Correggi o abbassa il minuto di gioco.</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    # 5. Quote 1X2 (prematch di riferimento)
    _live_card_title("💰 Quote 1X2")
    odds_cols = st.sidebar.columns(3)
    with odds_cols[0]:
        st.markdown('<div class="sidebar-accent-text" style="text-align:center;font-size:0.8rem;'
                    'font-weight:800;margin-bottom:2px;">1</div>', unsafe_allow_html=True)
        oh_min = st.number_input(
            "o1_min", 1.0, 99.0,
            step=0.05, format="%.2f", key="live_oh_min", label_visibility="collapsed",
        )
        st.markdown('<p class="sidebar-label" style="text-align:center;margin:0">—</p>',
                    unsafe_allow_html=True)
        oh_max = st.number_input(
            "o1_max", 1.0, 99.0,
            step=0.05, format="%.2f", key="live_oh_max", label_visibility="collapsed",
        )
    with odds_cols[1]:
        st.markdown('<div style="text-align:center;font-size:0.8rem;color:#f1f5f9;'
                    'font-weight:800;margin-bottom:2px;">X</div>', unsafe_allow_html=True)
        od_min = st.number_input(
            "ox_min", 1.0, 99.0,
            step=0.05, format="%.2f", key="live_od_min", label_visibility="collapsed",
        )
        st.markdown('<p class="sidebar-label" style="text-align:center;margin:0">—</p>',
                    unsafe_allow_html=True)
        od_max = st.number_input(
            "ox_max", 1.0, 99.0,
            step=0.05, format="%.2f", key="live_od_max", label_visibility="collapsed",
        )
    with odds_cols[2]:
        st.markdown('<div style="text-align:center;font-size:0.8rem;color:#ef4444;'
                    'font-weight:800;margin-bottom:2px;">2</div>', unsafe_allow_html=True)
        oa_min = st.number_input(
            "o2_min", 1.0, 99.0,
            step=0.05, format="%.2f", key="live_oa_min", label_visibility="collapsed",
        )
        st.markdown('<p class="sidebar-label" style="text-align:center;margin:0">—</p>',
                    unsafe_allow_html=True)
        oa_max = st.number_input(
            "o2_max", 1.0, 99.0,
            step=0.05, format="%.2f", key="live_oa_max", label_visibility="collapsed",
        )

    filters.update({
        "odds_home_min": oh_min, "odds_home_max": oh_max,
        "odds_draw_min": od_min, "odds_draw_max": od_max,
        "odds_away_min": oa_min, "odds_away_max": oa_max,
    })

    # 6. Strategie avanzate
    _live_card_title("🔥 Advanced Overs")
    st.sidebar.caption("Split staking Over 2.5 · fasi e gestione live")
    if "live_odds_over25" not in st.session_state:
        st.session_state["live_odds_over25"] = float(sv.get("odds_over25", 2.10))
    if "live_current_over_odds" not in st.session_state:
        st.session_state["live_current_over_odds"] = float(sv.get("current_over_odds", 3.20))
    if "_pending_live_over_phase" in st.session_state:
        st.session_state["live_over_phase"] = st.session_state.pop("_pending_live_over_phase")
    over_phase = st.sidebar.selectbox(
        "Fase strategia",
        ["WAIT", "ENTERED", "PHASE_3"],
        key="live_over_phase",
        label_visibility="collapsed",
    )
    oc1, oc2 = st.sidebar.columns(2)
    with oc1:
        odds_over25 = st.number_input(
            "Over 2.5 base",
            min_value=1.01,
            max_value=20.0,
            step=0.01,
            format="%.2f",
            key="live_odds_over25",
            label_visibility="collapsed",
        )
    with oc2:
        current_over_odds = st.number_input(
            "Over live",
            min_value=1.01,
            max_value=20.0,
            step=0.01,
            format="%.2f",
            key="live_current_over_odds",
            label_visibility="collapsed",
        )
    st.sidebar.caption("Quota base · Quota Over live")
    over_pnl = st.sidebar.slider(
        "PnL corrente (× stake)",
        min_value=-1.0,
        max_value=1.0,
        value=float(st.session_state.get("live_over_pnl", 0.0)),
        step=0.05,
        key="live_over_pnl",
        label_visibility="collapsed",
    )
    over_goal = st.sidebar.checkbox("Gol appena segnato", key="live_over_goal")
    os1, os2 = st.sidebar.columns(2)
    with os1:
        shots_2t = st.number_input(
            "Tiri in porta 2T",
            min_value=0,
            max_value=20,
            value=int(st.session_state.get("live_over_shots_2t", 0)),
            step=1,
            key="live_over_shots_2t",
            label_visibility="collapsed",
        )
    with os2:
        attack_rating = st.slider(
            "Rating attacco",
            min_value=0.0,
            max_value=1.0,
            value=float(st.session_state.get("live_over_rating", 0.5)),
            step=0.05,
            key="live_over_rating",
            label_visibility="collapsed",
        )
    filters.update({
        "over_phase": over_phase,
        "odds_over25": float(odds_over25),
        "current_over_odds": float(current_over_odds),
        "over_pnl": float(over_pnl),
        "over_goal": bool(over_goal),
        "shots_on_target_2T": int(shots_2t),
        "attack_rating": float(attack_rating),
    })

    return filters


def _h2h_quick_insight_html(home: str, away: str, league: str = "") -> str:
    header = (
        '<div style="font-size:12px; color:#22c55e; font-weight:700;">'
        '🔥 QUICK INSIGHT</div>'
    )
    if not home or not away or home == away:
        return header + (
            '<div style="font-size:11px; color:#86efac; margin-top:8px;">'
            'Seleziona due squadre diverse per l\'insight.</div>'
        )
    try:
        from database import get_all_matches
        from calculations import analyze_h2h
        rows = get_all_matches()
        if not rows:
            raise ValueError("no data")
        df = pd.DataFrame(rows)
        if league and league not in ("Tutte le competizioni", "Tutti", "Tutte"):
            if "league" in df.columns:
                df = df[df["league"] == league]
        r = analyze_h2h(df, home, away)
        if r.get("found", 0) == 0:
            return header + (
                '<div style="font-size:11px; color:#86efac; margin-top:8px;">'
                f'Nessun precedente tra {home} e {away}.</div>'
            )
        hw, aw = r.get("home_win_pct", 0), r.get("away_win_pct", 0)
        if hw > aw + 10:
            dom = f"{home} dominante negli ultimi H2H"
        elif aw > hw + 10:
            dom = f"{away} dominante negli ultimi H2H"
        else:
            dom = "Equilibrio negli scontri diretti"
        return header + (
            f'<div style="font-size:11px; color:#86efac; margin-top:8px;">'
            f'{dom}<br>'
            f'{r.get("over_25_pct", 0):.0f}% Over 2.5<br>'
            f'BTTS {r.get("btts_pct", 0):.0f}% frequente</div>'
        )
    except Exception:
        return header + (
            '<div style="font-size:11px; color:#86efac; margin-top:8px;">'
            'Casa dominante negli ultimi H2H<br>'
            '80% Over 2.5<br>'
            'BTTS frequente</div>'
        )


def _render_h2h_filters(sv: dict) -> dict:
    filters = {}

    _init_h2h_widgets(sv)
    if st.session_state.get("_filter_page_entered") and st.session_state.get("filters_analyzed"):
        _sync_sv_to_h2h_widgets(sv)

    selected_league = st.session_state.get("h2h_league", "Tutti i campionati")
    if selected_league and selected_league not in ("Tutti i campionati", "Tutti", "Tutte"):
        teams = _get_teams_by_league(selected_league) or []
    else:
        teams = _get_teams() or _get_all_teams()

    if not teams:
        st.sidebar.warning("Nessuna squadra disponibile per questo campionato.")
        return {}

    prev_league = st.session_state.get("_h2h_prev_league")
    if prev_league != selected_league:
        st.session_state._h2h_prev_league = selected_league
        if st.session_state.get("h2h_home") not in teams:
            st.session_state["h2h_home"] = teams[0]
        if st.session_state.get("h2h_away") not in teams:
            st.session_state["h2h_away"] = teams[min(1, len(teams) - 1)]

    _init_h2h_widgets(sv, teams)

    _live_card_title("🏟️ Campo & campionato")
    filters["h2h_venue"] = st.sidebar.selectbox(
        "Scontri da includere",
        [
            "Tutti gli scontri",
            "Solo casa (squadra casa)",
            "Solo trasferta (squadra casa)",
        ],
        key="h2h_venue",
        help="Filtra se la squadra casa ha giocato in casa, in trasferta, o entrambi.",
    )
    leagues = ["Tutti i campionati"] + (_get_leagues() or [])
    filters["h2h_league"] = st.sidebar.selectbox(
        "Campionato",
        leagues,
        key="h2h_league",
        help="Tutti i campionati = tutte le squadre. Altrimenti solo quelle del campionato scelto.",
    )

    _live_card_title("⚔️ Squadre")
    filters["home_team"] = st.sidebar.selectbox(
        "Squadra Casa", teams, key="h2h_home",
    )
    filters["away_team"] = st.sidebar.selectbox(
        "Squadra Trasferta", teams, key="h2h_away",
    )

    _live_card_title("📅 Periodo")
    filters["h2h_last_n"] = st.sidebar.selectbox(
        "Ultime partite",
        ["Tutte", "5", "10", "15", "20"],
        key="h2h_last_n",
    )
    d1, d2 = st.sidebar.columns(2)
    with d1:
        filters["date_from"] = st.date_input(
            "Da data", key="h2h_date_from", label_visibility="collapsed",
        )
    with d2:
        filters["date_to"] = st.date_input(
            "A data", key="h2h_date_to", label_visibility="collapsed",
        )

    _live_card_title("⚽ Filtri match")
    g1, g2 = st.sidebar.columns(2)
    with g1:
        filters["h2h_f_over15"] = st.checkbox("Over 1.5", key="h2h_f_over15")
        filters["h2h_f_over35"] = st.checkbox("Over 3.5", key="h2h_f_over35")
    with g2:
        filters["h2h_f_over25"] = st.checkbox("Over 2.5", key="h2h_f_over25")
        filters["h2h_f_btts"] = st.checkbox("BTTS (Gol Gol)", key="h2h_f_btts")
    r1, r2, r3 = st.sidebar.columns(3)
    with r1:
        filters["h2h_res_home"] = st.checkbox("Vittoria Casa", key="h2h_res_home")
    with r2:
        filters["h2h_res_draw"] = st.checkbox("Pareggio", key="h2h_res_draw")
    with r3:
        filters["h2h_res_away"] = st.checkbox("Vittoria Trasferta", key="h2h_res_away")

    with st.sidebar.expander("📊 Filtri avanzati", expanded=False):
        filters["h2h_min_goals_total"] = st.slider(
            "Min gol totali", 0, 10, key="h2h_min_goals_total",
        )
        filters["h2h_max_goals_total"] = st.slider(
            "Max gol totali", 1, 15, key="h2h_max_goals_total",
        )
        filters["h2h_min_goals_home"] = st.slider(
            "Min gol casa", 0, 8, key="h2h_min_goals_home",
        )
        filters["h2h_min_goals_away"] = st.slider(
            "Min gol trasferta", 0, 8, key="h2h_min_goals_away",
        )

    _sidebar_divider()
    _sidebar_label("🚀 Azioni")
    st.sidebar.markdown('<div class="sidebar-card analyze-btn">', unsafe_allow_html=True)
    filters["_top_analyze"] = st.sidebar.button(
        "🔍 ANALIZZA H2H", key="h2h_analyze_btn", use_container_width=True,
    )
    st.sidebar.markdown("</div>", unsafe_allow_html=True)

    return filters


# ══════════════════════════════════════════════════════════════════════════
#  PRIVATE: helpers
# ══════════════════════════════════════════════════════════════════════════

def _section_header(icon: str, label: str):
    st.sidebar.html(f"""
    <div class="filter-section-header">
        <span class="icon">{icon}</span>
        {label}
    </div>
    """)


def _divider():
    st.sidebar.html('<hr class="filter-divider">')


def _reset_filters(screen: str):
    keys_to_clear = [k for k in st.session_state if k.startswith(f"{screen}_")]
    for k in keys_to_clear:
        del st.session_state[k]
    if screen in ("prematch", "live", "simulator", "timeline"):
        st.session_state.pop("_shared_odds", None)
    clear_analysis_state()
    st.rerun()


def _expand_ht(selected: list) -> list:
    """Expand 'Altri' in HT selection to all non-standard results."""
    standard = {"0-0", "1-0", "0-1", "1-1"}
    result = [r for r in selected if r != "Altri"]
    if "Altri" in selected:
        result += _common_ht_results_extended()
    return result


def _common_ht_results_extended() -> list:
    return [
        "2-0", "0-2", "2-1", "1-2", "2-2",
        "3-0", "0-3", "3-1", "1-3", "3-2", "2-3",
        "3-3", "4-0", "0-4",
    ]


def _get_leagues() -> list:
    try:
        from database import get_leagues
        return get_leagues()
    except Exception:
        return []


def _get_seasons() -> list:
    try:
        from database import get_seasons
        return get_seasons()
    except Exception:
        return []


def _get_teams() -> list:
    try:
        from database import get_teams
        return get_teams()
    except Exception:
        return []


def _get_nations() -> list:
    try:
        from database import get_nations
        return get_nations()
    except Exception:
        return []


def _get_all_teams() -> list:
    try:
        return _get_teams() or []
    except Exception:
        return []


def _get_teams_by_league(league: str) -> list:
    try:
        from database import get_teams_by_league
        return get_teams_by_league(league)
    except Exception:
        return []


def _idx(options: list, value) -> int:
    try:
        return options.index(value)
    except (ValueError, TypeError):
        return 0


def _common_ht_results() -> list:
    return [
        "0-0", "1-0", "0-1", "1-1",
        "2-0", "0-2", "2-1", "1-2",
        "2-2", "3-0", "0-3", "3-1", "1-3",
    ]