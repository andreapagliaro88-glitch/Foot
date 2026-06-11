"""
screens/team_logos.py — Gestione loghi squadre (URL + upload locale)
"""

import base64
import html
import streamlit as st
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database import get_leagues
from utils import (
    get_team_logo_src,
    list_configured_team_logos,
    reload_team_logos,
    remove_team_logo,
    save_team_logo_bytes,
    split_league_name,
    team_initials,
    team_logo_slug,
    upsert_team_logo,
)

C_BG = "#111827"
C_BORDER = "#1f2937"
C_TEXT = "#f1f5f9"
C_MUTED = "#94a3b8"
C_GREEN = "#22c55e"
C_ACCENT = "#60a5fa"
_COLS_PER_ROW = 6


def _inject_styles():
    st.html(f"""
    <style>
        .tl-panel {{
            background:{C_BG}; border:1px solid {C_BORDER}; border-radius:8px;
            padding:16px; margin-bottom:12px;
        }}
        .tl-title {{ font-size:18px; font-weight:800; color:{C_TEXT}; }}
        .tl-sub {{ font-size:12px; color:{C_MUTED}; margin-top:4px; }}
        .tl-card {{
            background:#0f172a; border:1px solid {C_BORDER}; border-radius:8px;
            padding:12px 8px; text-align:center;
        }}
        .tl-card.has-logo {{
            border-color:#166534;
            padding:0;
            overflow:hidden;
        }}
        .tl-card.tl-card-missing {{
            border:1px dashed #475569;
        }}
        .tl-logo-cover {{
            width:100%;
            aspect-ratio:1 / 1;
            min-height:96px;
            display:flex;
            align-items:center;
            justify-content:center;
            background:#1e293b;
            overflow:hidden;
        }}
        .tl-logo-full {{
            width:100%;
            height:100%;
            object-fit:contain;
            display:block;
        }}
        .tl-card-name {{
            font-size:11px; font-weight:700; color:{C_TEXT};
            margin-top:8px; line-height:1.3; min-height:28px;
        }}
        .tl-card.has-logo .tl-card-name {{
            margin:0;
            min-height:auto;
            padding:8px 6px 10px;
            background:#0f172a;
        }}
        .tl-card-badge {{
            font-size:9px; font-weight:700; margin-top:4px;
        }}
        .tl-logo {{
            width:52px; height:52px; border-radius:50%;
            object-fit:contain; background:#1e293b;
        }}
        .tl-logo-fallback {{
            width:52px; height:52px; border-radius:50%;
            background:#334155; display:inline-flex;
            align-items:center; justify-content:center;
            font-weight:900; color:#fff; font-size:14px;
        }}
        .tl-card-missing .tl-logo-fallback {{
            background:#1e3a5f;
        }}
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.tl-card-inner) {{
            width: 100%;
        }}
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.tl-card-inner) button {{
            margin-top: 4px;
            font-size: 10px !important;
            font-weight: 700 !important;
            min-height: 28px !important;
        }}
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.tl-card-missing-marker) {{
            border-style: dashed !important;
            border-color: #475569 !important;
            cursor: pointer;
        }}
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.tl-card-missing-marker) button {{
            background: rgba(96, 165, 250, 0.12) !important;
            border: 1px dashed rgba(96, 165, 250, 0.45) !important;
            color: {C_ACCENT} !important;
            min-height: 34px !important;
        }}
        div[data-testid="column"] .tl-missing-card-col ~ div[data-testid="stVerticalBlock"] button {{
            min-height: 72px !important;
            white-space: normal !important;
            background: #0f172a !important;
            border: 1px dashed #475569 !important;
            border-radius: 8px !important;
            font-size: 11px !important;
            line-height: 1.35 !important;
            color: {C_TEXT} !important;
            font-weight: 700 !important;
            padding: 12px 8px !important;
        }}
        div[data-testid="column"] .tl-missing-card-col ~ div[data-testid="stVerticalBlock"] button:hover {{
            border-color: {C_ACCENT} !important;
            background: rgba(96, 165, 250, 0.08) !important;
            box-shadow: 0 0 0 1px rgba(96, 165, 250, 0.25);
        }}
    </style>
    """)


def _get_teams_by_league(league: str) -> list[str]:
    from database import get_teams_by_league
    return get_teams_by_league(league)


def _build_league_hierarchy() -> dict[str, list[str]]:
    by_country: dict[str, list[str]] = {}
    for league in get_leagues() or []:
        country, _ = split_league_name(league)
        by_country.setdefault(country, []).append(league)
    return {c: sorted(ls) for c, ls in sorted(by_country.items())}


def _league_label(league: str) -> str:
    _, name = split_league_name(league)
    return name or league


def _preview_logo(team: str, size: int = 72):
    src = get_team_logo_src(team)
    if src and src.startswith("data:"):
        _, b64 = src.split(",", 1)
        st.image(base64.b64decode(b64), width=size)
    elif src:
        st.image(src, width=size)
    else:
        st.markdown(
            f'<div style="width:{size}px;height:{size}px;border-radius:50%;'
            f'background:#334155;display:flex;align-items:center;justify-content:center;'
            f'font-weight:900;color:#fff;font-size:18px;margin:0 auto;">{team_initials(team)}</div>',
            unsafe_allow_html=True,
        )


def _logo_cover_html(team: str) -> str:
    src = get_team_logo_src(team)
    safe_team = html.escape(team)
    if src:
        return f'<img class="tl-logo-full" src="{src}" alt="{safe_team}" />'
    initials = team_initials(team)
    return (
        f'<div class="tl-logo-fallback" style="width:100%;height:100%;border-radius:0;">'
        f'{initials}</div>'
    )


def _logo_html(team: str, size: int = 52) -> str:
    src = get_team_logo_src(team)
    if src and not src.startswith("data:"):
        return (
            f'<img class="tl-logo" src="{src}" alt="{html.escape(team)}" '
            f'style="width:{size}px;height:{size}px;" />'
        )
    if src and src.startswith("data:"):
        return f'<img class="tl-logo" src="{src}" alt="{html.escape(team)}" />'
    initials = team_initials(team)
    return f'<div class="tl-logo-fallback">{initials}</div>'


def _card_html(team: str, has_logo: bool) -> str:
    card_cls = "tl-card has-logo tl-card-inner" if has_logo else "tl-card tl-card-missing tl-card-inner"
    marker = "" if has_logo else '<span class="tl-card-missing-marker" style="display:none"></span>'
    safe_team = html.escape(team)
    if has_logo:
        return (
            f'{marker}'
            f'<div class="{card_cls}">'
            f'<div class="tl-logo-cover">{_logo_cover_html(team)}</div>'
            f'<div class="tl-card-name">{safe_team}</div>'
            f'</div>'
        )
    badge_color = C_ACCENT
    badge_text = "➕ Clicca per aggiungere"
    return (
        f'{marker}'
        f'<div class="{card_cls}">'
        f'{_logo_html(team)}'
        f'<div class="tl-card-name">{safe_team}</div>'
        f'<div class="tl-card-badge" style="color:{badge_color};">{badge_text}</div>'
        f'</div>'
    )


@st.dialog("Configura logo squadra")
def _edit_team_logo_dialog(team: str) -> None:
    reload_team_logos()
    configured = list_configured_team_logos()
    entry = configured.get(team, {})
    slug = team_logo_slug(team)

    st.markdown(f"### {team}")
    _preview_logo(team, size=80)

    url_val = st.text_input(
        "Link immagine",
        value=entry.get("url", ""),
        placeholder="https://cdn.example.com/logo.jpg",
        key=f"tl_dlg_url_{slug}",
    )
    upload = st.file_uploader(
        "Oppure carica JPG / PNG",
        type=["png", "jpg", "jpeg", "webp"],
        key=f"tl_dlg_file_{slug}",
    )
    if entry.get("local"):
        st.caption(f"File locale: `{entry.get('local')}`")

    st.caption("Puoi usare il link oppure un file JPG — il file ha priorità se entrambi sono presenti.")

    c1, c2, c3 = st.columns(3)
    with c1:
        save = st.button("💾 Salva", type="primary", use_container_width=True, key=f"tl_dlg_save_{slug}")
    with c2:
        delete = st.button(
            "🗑 Rimuovi",
            use_container_width=True,
            key=f"tl_dlg_del_{slug}",
            disabled=team not in configured,
        )
    with c3:
        st.button("Chiudi", use_container_width=True, key=f"tl_dlg_close_{slug}")

    if save:
        local_path = entry.get("local", "")
        if upload is not None:
            local_path = save_team_logo_bytes(team, upload.getvalue(), upload.name)
        if not url_val.strip() and not local_path and upload is None:
            st.warning("Inserisci un link immagine o carica un file JPG/PNG.")
            return
        upsert_team_logo(team, url=url_val, local=local_path)
        reload_team_logos()
        st.success(f"Logo salvato per **{team}**")
        st.rerun()

    if delete and team in configured:
        remove_team_logo(team)
        reload_team_logos()
        st.success(f"Logo rimosso per **{team}**")
        st.rerun()


def _render_clickable_team_card(team: str, idx: int, configured: dict) -> None:
    has_logo = team in configured
    slug = team_logo_slug(team)
    key = f"tl_card_{idx}_{slug}"

    if has_logo:
        with st.container(border=True):
            st.markdown(_card_html(team, has_logo=True), unsafe_allow_html=True)
            if st.button("✏️ Modifica logo", key=key, use_container_width=True):
                _edit_team_logo_dialog(team)
        return

    label = team
    st.markdown('<div class="tl-missing-card-col"></div>', unsafe_allow_html=True)
    if st.button(label, key=key, use_container_width=True, help="Clicca per aggiungere logo (JPG o link)"):
        _edit_team_logo_dialog(team)


def _render_clickable_teams_grid(teams: list[str], configured: dict) -> None:
    for row_start in range(0, len(teams), _COLS_PER_ROW):
        cols = st.columns(_COLS_PER_ROW)
        for col_idx, col in enumerate(cols):
            team_idx = row_start + col_idx
            if team_idx >= len(teams):
                break
            with col:
                _render_clickable_team_card(teams[team_idx], team_idx, configured)


def _sync_league_on_nation(countries: list[str], hierarchy: dict[str, list[str]]) -> None:
    if "tl_nation" not in st.session_state or st.session_state.tl_nation not in countries:
        st.session_state.tl_nation = countries[0]

    prev_nation = st.session_state.get("_tl_prev_nation")
    nation = st.session_state.tl_nation
    leagues = hierarchy.get(nation, [])

    if prev_nation != nation:
        st.session_state.tl_league = leagues[0] if leagues else ""
        st.session_state._tl_prev_nation = nation

    if "tl_league" not in st.session_state or st.session_state.tl_league not in leagues:
        st.session_state.tl_league = leagues[0] if leagues else ""


def render():
    _inject_styles()

    hierarchy = _build_league_hierarchy()
    configured = list_configured_team_logos()

    st.html(
        f'<div class="tl-panel">'
        f'<div class="tl-title">🛡️ GESTIONE LOGHI SQUADRE</div>'
        f'<div class="tl-sub">Clicca sul riquadro di una squadra per aggiungere un logo (JPG o link immagine).</div>'
        f'</div>'
    )

    if not hierarchy:
        st.warning("Nessun campionato nel database. Carica prima i dati da **UPLOAD DATI**.")
        return

    countries = list(hierarchy.keys())
    _sync_league_on_nation(countries, hierarchy)

    f1, f2, f3 = st.columns([1, 1, 1])
    with f1:
        st.selectbox("🌍 Nazione", countries, key="tl_nation")
    nation = st.session_state.tl_nation
    leagues = hierarchy.get(nation, [])
    with f2:
        st.selectbox(
            "🏆 Campionato",
            leagues,
            format_func=_league_label,
            key="tl_league",
        )
    selected_league = st.session_state.tl_league

    teams = sorted(_get_teams_by_league(selected_league))
    if not teams:
        st.info("Nessuna squadra trovata per questo campionato.")
        return

    if st.session_state.get("_tl_prev_league") != selected_league:
        st.session_state._tl_prev_league = selected_league

    with f3:
        if st.button("↩ Torna all'app", use_container_width=True):
            st.session_state.active_page = st.session_state.get("_last_main_page", "prematch")
            st.rerun()

    with_logo = sum(1 for t in teams if t in configured)
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Squadre nel campionato", len(teams))
    with c2:
        st.metric("Con logo", with_logo)
    with c3:
        st.metric("Senza logo", len(teams) - with_logo)
    with c4:
        st.metric("Copertura", f"{(with_logo / len(teams) * 100):.0f}%")

    st.markdown(f"##### Squadre — {_league_label(selected_league)}")
    filter_col1, filter_col2 = st.columns([2, 1])
    with filter_col1:
        search = st.text_input("🔍 Cerca squadra", placeholder="es. Fortaleza, Milan...")
    with filter_col2:
        only_missing = st.checkbox("Solo senza logo", value=False)

    filtered = [t for t in teams if search.lower() in t.lower()] if search else teams
    if only_missing:
        filtered = [t for t in filtered if t not in configured]

    if not filtered:
        st.info("Nessuna squadra corrisponde ai filtri.")
        return

    _render_clickable_teams_grid(filtered, configured)

    st.caption(
        "Clicca su una squadra senza logo per caricare JPG o incollare un link. "
        "I loghi vengono salvati in `data/team_logos.json` e in `assets/teams/`."
    )
