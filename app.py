"""
app.py — Main Streamlit entry point, page routing + Upload Dati
"""

import streamlit as st
import pandas as pd
import sys
import os

# ── Page config must be FIRST Streamlit call ──────────────────────────────
st.set_page_config(
    page_title="Football Analytics Dashboard",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Ensure project root is on path ────────────────────────────────────────
sys.path.insert(0, os.path.dirname(__file__))

from database import init_db, get_league_season_stats, delete_league_data, get_leagues
from data_loader import load_csv
from utils import build_league_name, split_league_name

# ── Initialise database on startup ────────────────────────────────────────
init_db()

# ── Custom CSS (injected once per session) ────────────────────────────────
if not st.session_state.get("_app_css_loaded"):
    st.session_state._app_css_loaded = True
    st.html("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .stApp { background-color: #0f172a; color: #e2e8f0; }
    @import url('https://fonts.googleapis.com/css2?family=Rajdhani:wght@600;700&display=swap');
    [data-testid="stSidebar"] {
        background: #0d1b2a !important;
        border-right: 1px solid #1e3a5f !important;
        padding-top: 0 !important;
    }
    [data-testid="stSidebar"] .stMarkdown { color: #94a3b8; }
    /* Remove default top padding so FILTRI header touches the top */
    [data-testid="stSidebar"] > div:first-child { padding-top: 0 !important; }
    /* Nav radio styling */
    [data-testid="stSidebar"] .stRadio label { color: #cbd5e1 !important; font-size: 0.88rem !important; }
    [data-testid="stSidebar"] .stRadio [data-baseweb="radio"] div { border-color: #3b82f6 !important; }
    /* Caption */
    [data-testid="stSidebar"] .stCaption { color: #475569 !important; font-size: 0.72rem !important; }
    [data-testid="stMetric"] {
        background: #1e293b;
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 16px 20px;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    [data-testid="stMetric"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 24px rgba(0,0,0,0.3);
    }
    [data-testid="stMetricLabel"] { color: #94a3b8 !important; font-size: 0.8rem; }
    [data-testid="stMetricValue"] { color: #f1f5f9 !important; font-size: 1.6rem; font-weight: 700; }
    .stButton > button {
        background: linear-gradient(135deg, #3b82f6, #2563eb);
        color: white;
        border: none;
        border-radius: 8px;
        font-weight: 600;
        transition: all 0.2s ease;
    }
    .stButton > button:hover {
        background: linear-gradient(135deg, #2563eb, #1d4ed8);
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(59,130,246,0.4);
    }
    .stDataFrame { border-radius: 10px; overflow: hidden; }
    [data-testid="stDataFrame"] > div { background: #1e293b; }
    h1 { color: #f1f5f9 !important; font-weight: 700; }
    h2, h3 { color: #cbd5e1 !important; font-weight: 600; }
    .stAlert { border-radius: 10px; }
    .stTabs [data-baseweb="tab-list"] { background: #1e293b; border-radius: 10px; padding: 4px; }
    .stTabs [data-baseweb="tab"] { color: #94a3b8; border-radius: 8px; }
    .stTabs [aria-selected="true"] { background: #3b82f6 !important; color: white !important; }
    hr { border-color: #334155; }
</style>
""")

    # ── GOAL EDGE sticky top header CSS (additive) ──────────────────
    st.html("""
<style>
/* Streamlit's transparent top header used to overlay our header and eat all
   clicks. Make it click-through, but keep its own controls clickable. */
[data-testid="stHeader"] {
    background: transparent !important;
    box-shadow: none !important;
    pointer-events: none !important;
}
/* Hide only Deploy + main menu, NOT the sidebar expand/collapse control */
[data-testid="stAppDeployButton"],
[data-testid="stMainMenu"],
#MainMenu { display: none !important; }
/* Re-enable clicks ONLY on the sidebar expand control (not the full-width header,
   which would otherwise sit over our tabs and block them) */
[data-testid="stSidebarCollapsedControl"],
[data-testid="collapsedControl"] {
    display: flex !important;
    pointer-events: auto !important;
    z-index: 1000002 !important;
}
section[data-testid="stMain"] .block-container { padding-top: 0.8rem !important; }

.st-key-goaledge_header {
    position: sticky;
    top: 0;
    z-index: 1000001;
    pointer-events: auto;
    background: #0a1120;
    border-bottom: 1px solid #1e293b;
    padding: 6px 14px 0 14px;
    margin: -0.8rem -1rem 1rem -1rem;
    box-shadow: 0 4px 14px rgba(0,0,0,0.35);
}

/* Make sure all interactive children of our header stay clickable even though
   the parent stHeader layer is pointer-events:none */
.st-key-goaledge_header [class*="st-key-nav_tab_"] .stButton > button,
.st-key-goaledge_header .stButton > button {
    pointer-events: auto !important;
}

/* Logo */
.goaledge-logo { display:flex; align-items:center; gap:8px; }
.goaledge-logo .mark { color:#ef4444; font-size:1.5rem; line-height:1; }
.goaledge-logo .txt {
    font-family:'Rajdhani','Oswald',sans-serif; font-weight:700;
    font-size:1.25rem; letter-spacing:0.1em; color:#f8fafc;
}
.goaledge-logo .txt b { color:#ef4444; font-weight:700; }

/* Nav tabs (buttons styled as tabs) */
.st-key-goaledge_header [class*="st-key-nav_tab_"] .stButton > button {
    background:transparent !important;
    border:none !important;
    border-bottom:3px solid transparent !important;
    border-radius:0 !important;
    color:#94a3b8 !important;
    font-family:'Rajdhani','Inter',sans-serif;
    font-weight:700; font-size:0.8rem; letter-spacing:0.07em;
    text-transform:uppercase;
    padding:12px 16px 10px 16px !important;
    height:auto !important;
    box-shadow:none !important;
    transform:none !important;
}
.st-key-goaledge_header [class*="st-key-nav_tab_"] .stButton > button:hover {
    color:#e2e8f0 !important;
    background:rgba(148,163,184,0.06) !important;
    box-shadow:none !important;
    transform:none !important;
}

/* Right-side action buttons (solo colonna azioni, non le tab) */
.st-key-goaledge_actions .stButton > button {
    background:transparent !important;
    border:1px solid #334155 !important;
    color:#cbd5e1 !important; border-radius:7px !important;
    font-size:0.68rem !important; font-weight:600 !important;
    letter-spacing:0.04em !important; padding:8px 6px !important; height:auto !important;
    border-bottom:1px solid #334155 !important;
    box-shadow:none !important; transform:none !important;
}
.st-key-goaledge_actions .stButton > button:hover {
    border-color:#ef4444 !important; color:#ffffff !important;
    transform:none !important; box-shadow:none !important;
}
</style>
""")



# ── Upload Dati page ───────────────────────────────────────────────────────
def _render_upload():
    st.title("📤 Upload Dati")
    st.markdown("Carica file CSV o Excel per aggiornare il database delle partite.")

    with st.form("upload_form"):
        uploaded_file = st.file_uploader(
            "Seleziona file",
            type=["csv", "xlsx", "xls"],
            help="Accetta file CSV o Excel con dati di partite di calcio",
            key="app_file"
        )
        existing_nations = sorted({
            split_league_name(lg)[0]
            for lg in (get_leagues() or [])
            if lg and " - " in lg
        })

        col1, col2 = st.columns(2)
        with col1:
            nation_pick = st.selectbox(
                "Nazione",
                ["— Nuova nazione —"] + existing_nations,
                help="Scegli una nazione già presente o inseriscine una nuova",
                key="app_nation_pick",
            )
            if nation_pick == "— Nuova nazione —":
                country = st.text_input(
                    "Nome nazione",
                    placeholder="es. Argentina",
                    key="app_country_new",
                )
            else:
                country = nation_pick
        with col2:
            championship = st.text_input(
                "Campionato",
                placeholder="es. Primera B",
                help="Nome del campionato (senza la nazione)",
                key="app_championship",
            )

        league_name = build_league_name(country, championship)
        if league_name:
            st.caption(f"Salvato nel database come: **{league_name}**")

        submitted = st.form_submit_button("📥 Importa", use_container_width=True)

        if submitted:
            if uploaded_file is None:
                st.error("⚠️ Seleziona un file prima di importare.")
            elif not (country or "").strip():
                st.error("⚠️ Inserisci la nazione.")
            elif not (championship or "").strip():
                st.error("⚠️ Inserisci il nome del campionato.")
            else:
                with st.spinner("Importazione in corso..."):
                    result = load_csv(uploaded_file, league_name)

                rows_added   = result.get("rows_added", 0)
                rows_skipped = result.get("rows_skipped", 0)
                errors       = result.get("errors", [])

                if rows_added > 0:
                    st.success(
                        f"✅ Importati **{rows_added}** risultati in **{league_name}**. "
                        f"{rows_skipped} duplicati saltati."
                    )
                elif rows_skipped > 0 and rows_added == 0:
                    st.warning(
                        f"⚠️ Tutte le {rows_skipped} partite erano già nel database (duplicati saltati)."
                    )

                if errors:
                    with st.expander(f"⚠️ {len(errors)} errori durante l'importazione"):
                        for e in errors[:20]:
                            st.text(str(e))
                        if len(errors) > 20:
                            st.caption(f"... e altri {len(errors) - 20} errori")

    st.divider()
    st.subheader("🗑️ Elimina campionato")
    st.caption(
        "Rimuove dal database tutte le partite del campionato selezionato. "
        "L'operazione è irreversibile."
    )

    league_stats = get_league_season_stats()
    if not league_stats:
        st.info("Nessun campionato presente nel database.")
    else:
        def _league_label(row: dict) -> str:
            season = row.get("season") or "—"
            count = row.get("match_count", 0)
            return f"{row['league']} — {season} ({count} partite)"

        labels = [_league_label(r) for r in league_stats]
        label_to_row = {label: row for label, row in zip(labels, league_stats)}

        selected_label = st.selectbox(
            "Campionato da eliminare",
            labels,
            key="upload_delete_league_pick",
        )
        selected = label_to_row[selected_label]
        st.warning(
            f"Verranno eliminate **{selected['match_count']}** partite di "
            f"**{selected['league']}** ({selected.get('season') or 'stagione non indicata'})."
        )

        confirm = st.checkbox(
            "Confermo di voler eliminare definitivamente questo campionato",
            key="upload_delete_confirm",
        )
        if st.button(
            "🗑 Elimina campionato",
            type="primary",
            disabled=not confirm,
            use_container_width=True,
            key="upload_delete_btn",
        ):
            result = delete_league_data(selected["league"], selected.get("season"))
            deleted = result.get("matches_deleted", 0)
            if deleted > 0:
                try:
                    from database import invalidate_db_cache
                    invalidate_db_cache()
                except ImportError:
                    pass
                st.success(
                    f"Eliminate **{deleted}** partite per "
                    f"**{result['league']}** ({result.get('season') or 'tutte le stagioni'})."
                )
                st.rerun()
            else:
                st.error("Nessuna partita eliminata. Il campionato potrebbe essere già stato rimosso.")

    with st.expander("ℹ️ Formato file supportato"):
        st.markdown("""
        **Colonne richieste (minimo):**
        - `home_team_name` — Nome squadra casa
        - `away_team_name` — Nome squadra trasferta
        - `date_GMT` — Data della partita

        **Colonne opzionali:**
        - Goal count FT/HT, corner, shots, possession
        - Odds (home, draw, away, over lines, BTTS)
        - Goal timings (es. `"37,90'4,49,88"`)

        **Duplicati:** Saltati automaticamente in base a `squadra casa + squadra trasferta + data`.
        """)


# ── Top navigation header (GOAL EDGE) ────────────────────────
TOP_PAGES = {
    "PREMATCH":         "prematch",
    "LIVE":             "live",
    "TESTA A TESTA":    "h2h",
    "SIMULATOR":        "simulator",
    "TIMELINE":         "timeline",
    "TEAM DNA":         "dna",
}
_NAV_LABELS = list(TOP_PAGES.keys())

# color, bg, hover_color, hover_bg
_NAV_TAB_THEME = {
    "prematch":  ("#3b82f6", "rgba(59,130,246,0.14)", "#60a5fa", "rgba(59,130,246,0.22)"),
    "live":      ("#22c55e", "rgba(34,197,94,0.14)",  "#4ade80", "rgba(34,197,94,0.22)"),
    "h2h":       ("#f59e0b", "rgba(245,158,11,0.14)", "#fbbf24", "rgba(245,158,11,0.22)"),
    "simulator": ("#a855f7", "rgba(168,85,247,0.14)", "#c084fc", "rgba(168,85,247,0.22)"),
    "timeline":  ("#38bdf8", "rgba(56,189,248,0.14)", "#7dd3fc", "rgba(56,189,248,0.22)"),
    "dna":       ("#e879f9", "rgba(232,121,249,0.14)", "#f0abfc", "rgba(232,121,249,0.22)"),
}
_DEFAULT_TAB_THEME = ("#94a3b8", "rgba(148,163,184,0.10)", "#cbd5e1", "rgba(148,163,184,0.18)")


def _nav_tab_active_css(page: str) -> str:
    color, bg, hover_color, hover_bg = _NAV_TAB_THEME.get(page, _DEFAULT_TAB_THEME)
    return f"""
    .st-key-goaledge_header .st-key-nav_tab_{page} .stButton > button {{
        color:{color} !important;
        border-bottom:3px solid {color} !important;
        background:{bg} !important;
    }}
    .st-key-goaledge_header .st-key-nav_tab_{page} .stButton > button:hover {{
        color:{hover_color} !important;
        background:{hover_bg} !important;
    }}
    """


if "active_page" not in st.session_state:
    st.session_state.active_page = "prematch"


def _request_aux_page(page_key: str):
    """Apre una pagina ausiliaria (upload, filtri salvati, ecc.)."""
    if st.session_state.active_page in TOP_PAGES.values():
        st.session_state._last_main_page = st.session_state.active_page
    st.session_state.active_page = page_key
    st.rerun()


_active_nav = st.session_state.active_page
_active_css = ""
if _active_nav in TOP_PAGES.values():
    _active_css = _nav_tab_active_css(_active_nav)
elif _active_nav == "upload":
    _active_css = """
    .st-key-goaledge_actions .st-key-hdr_upload .stButton > button {
        border-color:#ef4444 !important;
        color:#ef4444 !important;
        background:rgba(239,68,68,0.12) !important;
    }
    """
elif _active_nav == "saved_filters":
    _active_css = """
    .st-key-goaledge_actions .st-key-hdr_saved .stButton > button {
        border-color:#ef4444 !important;
        color:#ef4444 !important;
        background:rgba(239,68,68,0.12) !important;
    }
    """
elif _active_nav == "team_logos":
    _active_css = """
    .st-key-goaledge_actions .st-key-hdr_settings .stButton > button {
        border-color:#3b82f6 !important;
        color:#3b82f6 !important;
        background:rgba(59,130,246,0.12) !important;
    }
    """
if _active_css:
    st.html(f"<style>{_active_css}</style>")

with st.container(key="goaledge_header"):
    _c_spacer, c_nav, c_actions = st.columns([0.8, 6, 4], vertical_alignment="center")

    with c_nav:
        nav_cols = st.columns(len(_NAV_LABELS))
        for col, label in zip(nav_cols, _NAV_LABELS):
            page = TOP_PAGES[label]
            with col:
                with st.container(key=f"nav_tab_{page}"):
                    if st.button(label, key=f"hdr_nav_{page}", use_container_width=True):
                        st.session_state.active_page = page
                        st.session_state._last_main_page = page
                        st.rerun()

    with c_actions:
        with st.container(key="goaledge_actions"):
            a1, a2, a3 = st.columns([4, 4, 2])
            with a1:
                if st.button("FILTRI SALVATI", key="hdr_saved", use_container_width=True):
                    _request_aux_page("saved_filters")
            with a2:
                if st.button("UPLOAD DATI", key="hdr_upload", use_container_width=True):
                    _request_aux_page("upload")
            with a3:
                if st.button("⚙", key="hdr_settings", use_container_width=True):
                    _request_aux_page("team_logos")

page_key = st.session_state.active_page
if page_key == "pattern":
    st.session_state.active_page = "prematch"
    page_key = "prematch"


# ── Render selected page ───────────────────────────────────────────────────
if page_key == "upload":
    _render_upload()
elif page_key == "prematch":
    from screens.prematch import render
    render()
elif page_key == "live":
    from screens.live import render
    render()
elif page_key == "h2h":
    from screens.h2h import render
    render()
elif page_key == "simulator":
    from screens.strategy_simulator import render
    render()
elif page_key == "timeline":
    from screens.match_timeline import render
    render()
elif page_key == "dna":
    from screens.team_dna import render
    render()
elif page_key == "saved_filters":
    from screens.saved_filters import render
    render()
elif page_key == "team_logos":
    from screens.team_logos import render
    render()