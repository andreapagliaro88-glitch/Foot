"""
pages/saved_filters.py — Saved Filters manager screen
"""

import streamlit as st
import pandas as pd
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database import get_saved_filters, delete_saved_filter, save_filter, update_saved_filter
from filters import render_filter_sidebar


SCREEN_LABELS = {
    "prematch": "Prematch",
    "live":     "Live",
    "h2h":      "Testa a Testa",
    "pattern":  "Pattern Explorer",
}


def render():
    st.title("📁 Filtri Salvati")
    st.markdown("Gestisci i tuoi filtri personalizzati — visualizza, applica, modifica o elimina.")

    all_filters = get_saved_filters()

    if not all_filters:
        st.info("💡 Non hai ancora salvato nessun filtro. Vai su **Prematch** o **Pattern Explorer** per crearne uno.")
    else:
        st.subheader(f"📂 {len(all_filters)} Filtri Salvati")

        for f in all_filters:
            _render_filter_card(f)

    st.divider()

    # ── Create new filter ─────────────────────────────────────────────────
    st.subheader("➕ Crea Nuovo Filtro")
    with st.form("new_filter_form"):
        col1, col2 = st.columns(2)
        with col1:
            new_name = st.text_input("Nome filtro *", key="new_fname")
        with col2:
            new_screen = st.selectbox(
                "Schermata di destinazione *",
                options=list(SCREEN_LABELS.keys()),
                format_func=lambda x: SCREEN_LABELS[x],
                key="new_fscreen"
            )

        st.markdown("**Configura i filtri:**")

        # Inline filter preview for the chosen screen
        odds_home_range = st.slider("Quote Casa", 1.0, 20.0, (1.0, 20.0), 0.1, key="new_odds_home")
        odds_draw_range = st.slider("Quote Pareggio", 1.0, 20.0, (1.0, 20.0), 0.1, key="new_odds_draw")
        odds_away_range = st.slider("Quote Trasferta", 1.0, 20.0, (1.0, 20.0), 0.1, key="new_odds_away")
        gw_range = st.slider("Giornata", 1, 38, (1, 38), key="new_gw")

        submitted = st.form_submit_button("💾 Salva Filtro")
        if submitted:
            if not new_name.strip():
                st.error("Il nome del filtro è obbligatorio.")
            else:
                new_filters = {
                    "odds_home_min": odds_home_range[0],
                    "odds_home_max": odds_home_range[1],
                    "odds_draw_min": odds_draw_range[0],
                    "odds_draw_max": odds_draw_range[1],
                    "odds_away_min": odds_away_range[0],
                    "odds_away_max": odds_away_range[1],
                    "game_week_min": gw_range[0],
                    "game_week_max": gw_range[1],
                }
                ok = save_filter(new_name.strip(), new_screen, new_filters)
                if ok:
                    st.success(f"✅ Filtro '{new_name}' salvato per **{SCREEN_LABELS[new_screen]}**!")
                    st.rerun()
                else:
                    st.error("Errore nel salvataggio. Il nome potrebbe essere già in uso.")


def _render_filter_card(f: dict):
    """Renders a single saved filter card."""
    fid      = f["id"]
    name     = f["name"]
    screen   = f["screen"]
    created  = f.get("created_at", "")[:10]
    fdata    = f.get("filters", {})

    screen_label = SCREEN_LABELS.get(screen, screen)

    with st.container():
        col1, col2, col3, col4 = st.columns([4, 2, 1, 1])

        with col1:
            st.markdown(f"### 🔖 {name}")
            st.caption(f"📺 Schermata: **{screen_label}** · 📅 Creato: {created}")

            # Show filter preview
            preview_items = []
            if fdata.get("league") and fdata["league"] not in ("Tutti", "Tutte"):
                preview_items.append(f"Campionato: {fdata['league']}")
            if fdata.get("season") and fdata["season"] not in ("Tutti", "Tutte"):
                preview_items.append(f"Stagione: {fdata['season']}")
            if fdata.get("odds_home_min") and fdata.get("odds_home_max"):
                preview_items.append(f"Quote Casa: {fdata['odds_home_min']}–{fdata['odds_home_max']}")
            if fdata.get("odds_draw_min") and fdata.get("odds_draw_max"):
                preview_items.append(f"Quote X: {fdata['odds_draw_min']}–{fdata['odds_draw_max']}")
            if fdata.get("game_week_min") and fdata.get("game_week_max"):
                preview_items.append(f"Giornata: {fdata['game_week_min']}–{fdata['game_week_max']}")

            if preview_items:
                st.caption(" · ".join(preview_items))
            else:
                st.caption("_Nessun filtro specifico configurato_")

        with col2:
            # Apply button — navigate hint
            if st.button(f"▶ Applica", key=f"apply_{fid}"):
                st.session_state["loaded_filter"] = f
                st.session_state["loaded_filter_screen"] = screen
                st.info(
                    f"Filtro **'{name}'** caricato. "
                    f"Vai su **{screen_label}** e selezionalo dal menu 'Carica Filtro Salvato'."
                )

        with col3:
            # Edit with expander
            if st.button("✏️", key=f"edit_{fid}", help="Modifica nome"):
                st.session_state[f"editing_{fid}"] = True

        with col4:
            if st.button("🗑️", key=f"del_{fid}", help="Elimina filtro"):
                delete_saved_filter(fid)
                st.success(f"Filtro '{name}' eliminato.")
                st.rerun()

        # Inline edit form
        if st.session_state.get(f"editing_{fid}"):
            with st.form(f"edit_form_{fid}"):
                new_name = st.text_input("Nuovo nome", value=name, key=f"editname_{fid}")
                new_screen = st.selectbox(
                    "Schermata", list(SCREEN_LABELS.keys()),
                    format_func=lambda x: SCREEN_LABELS[x],
                    index=list(SCREEN_LABELS.keys()).index(screen) if screen in SCREEN_LABELS else 0,
                    key=f"editscreen_{fid}"
                )
                col_save, col_cancel = st.columns(2)
                with col_save:
                    if st.form_submit_button("💾 Salva modifiche"):
                        update_saved_filter(fid, new_name.strip(), new_screen, fdata)
                        st.session_state.pop(f"editing_{fid}", None)
                        st.success("Filtro aggiornato.")
                        st.rerun()
                with col_cancel:
                    if st.form_submit_button("Annulla"):
                        st.session_state.pop(f"editing_{fid}", None)
                        st.rerun()

        st.divider()
