"""
screens/riepilogo.py — Riepilogo compatto: migliore % per ogni area analitica.
"""

from __future__ import annotations

import streamlit as st
import pandas as pd
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database import get_all_matches_unfiltered
from filters import render_filter_sidebar, should_run_analysis, _ALL_LEAGUES_LABEL
from screen_cache import load_prematch_data, build_prematch_frame
from calculations import analyze_matches, enrich_with_goal_events, analyze_h2h, analyze_live_state_v2
from strategy_simulator import find_best_strategy
from team_dna import analyze_team_dna
from match_timeline import build_timeline, build_intensity_zones, detect_key_moments
from utils import get_pct_color, team_logo_html
from screens.match_header import compute_header_insights
from screens.momentum_chart import build_similar_match_momentum
from screens.first_goal_chart import build_first_goal_data
from screens.h2h import _filter_h2h_matches

C_BG = "#111827"
C_BORDER = "#1f2937"
C_TEXT = "#f1f5f9"
C_MUTED = "#cbd5e1"
C_MUTED2 = "#94a3b8"
C_CYAN = "#38bdf8"
C_GREEN = "#22c55e"
C_RED = "#ef4444"
C_PURPLE = "#a855f7"
C_AMBER = "#f59e0b"


def _inject_styles():
    if st.session_state.get("_riepilogo_css"):
        return
    st.session_state._riepilogo_css = True
    st.html(f"""
    <style>
        .rp-hero {{
            background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 55%, #0f172a 100%);
            border: 1px solid {C_BORDER}; border-radius: 12px;
            padding: 20px 24px; margin-bottom: 8px;
        }}
        .rp-legend {{
            background: #0f172a; border: 1px solid {C_BORDER};
            border-radius: 10px; padding: 12px 16px; margin-bottom: 22px;
            font-size: 12px; color: {C_MUTED}; line-height: 1.55;
        }}
        .rp-block {{
            margin-bottom: 28px;
        }}
        .rp-block-head {{
            display: flex; align-items: center; gap: 12px;
            margin-bottom: 14px; padding-bottom: 10px;
            border-bottom: 1px solid {C_BORDER};
        }}
        .rp-block-num {{
            font-size: 11px; font-weight: 800; padding: 5px 9px;
            border-radius: 6px; flex-shrink: 0;
        }}
        .rp-block-title {{ font-size: 15px; font-weight: 800; color: {C_TEXT}; }}
        .rp-block-sub {{ font-size: 11px; color: {C_MUTED2}; margin-top: 2px; }}
        .rp-row {{
            display: grid; gap: 12px;
        }}
        .rp-row-4 {{ grid-template-columns: repeat(4, 1fr); }}
        .rp-row-3 {{ grid-template-columns: repeat(3, 1fr); }}
        .rp-row-2 {{ grid-template-columns: repeat(2, 1fr); }}
        @media (max-width: 1100px) {{
            .rp-row-4 {{ grid-template-columns: repeat(2, 1fr); }}
            .rp-row-3 {{ grid-template-columns: repeat(2, 1fr); }}
        }}
        .rp-card {{
            background: {C_BG}; border: 1px solid {C_BORDER};
            border-radius: 10px; padding: 16px 18px;
            border-top: 3px solid var(--accent, {C_CYAN});
            display: flex; flex-direction: column; min-height: 168px;
        }}
        .rp-card-area {{
            font-size: 11px; color: {C_MUTED2}; font-weight: 700;
            text-transform: uppercase; letter-spacing: 0.1em;
            margin-bottom: 10px;
        }}
        .rp-card-pick {{
            font-size: 14px; color: #e2e8f0; font-weight: 700;
            line-height: 1.35; flex: 1;
        }}
        .rp-card-pct {{
            font-size: 32px; font-weight: 900; line-height: 1;
            margin: 10px 0 8px;
        }}
        .rp-card-bar {{
            height: 5px; background: #1f2937; border-radius: 4px;
            overflow: hidden; margin-bottom: 8px;
        }}
        .rp-card-bar > div {{
            height: 100%; border-radius: 4px;
        }}
        .rp-card-detail {{
            font-size: 12px; color: {C_MUTED};
        }}
        .rp-card-hint {{
            font-size: 10px; color: {C_MUTED2}; margin-top: 4px;
        }}
    </style>
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


def _fmt_n(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def _pick_best(items: list[tuple[str, float, str]]) -> tuple[str, float, str]:
    if not items:
        return "—", 0.0, ""
    return max(items, key=lambda x: x[1])


def _best_card(
    area: str,
    pick: str,
    pct: float,
    detail: str = "",
    hint: str = "",
    color: str | None = None,
) -> str:
    color = color or get_pct_color(pct)
    bar_w = min(max(pct, 0), 100)
    hint_html = f'<div class="rp-card-hint">{hint}</div>' if hint else ""
    return f"""
    <div class="rp-card" style="--accent:{color};">
        <div class="rp-card-area">{area}</div>
        <div class="rp-card-pick">{pick}</div>
        <div class="rp-card-pct" style="color:{color};">{pct:.1f}%</div>
        <div class="rp-card-bar"><div style="width:{bar_w}%;background:{color};"></div></div>
        <div class="rp-card-detail">{detail}</div>
        {hint_html}
    </div>
    """


def _section(num: str, title: str, subtitle: str, color: str, cards: list[str], cols: int = 4) -> None:
    row_cls = f"rp-row rp-row-{cols}"
    st.html(f"""
    <div class="rp-block">
        <div class="rp-block-head">
            <div class="rp-block-num" style="background:{color}22;border:1px solid {color}55;color:{color};">{num}</div>
            <div>
                <div class="rp-block-title">{title}</div>
                <div class="rp-block-sub">{subtitle}</div>
            </div>
        </div>
        <div class="{row_cls}">{"".join(cards)}</div>
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


def _best_over_under(filtered: pd.DataFrame, n: int) -> tuple[str, float, str]:
    tg_ht = pd.to_numeric(filtered["total_goals_ht"], errors="coerce").fillna(0)
    tg_2h = pd.to_numeric(filtered["total_goals_2h"], errors="coerce").fillna(0)
    tg_ft = pd.to_numeric(filtered["total_goals_ft"], errors="coerce").fillna(0)
    hg = pd.to_numeric(filtered["home_goals_ft"], errors="coerce").fillna(0)
    ag = pd.to_numeric(filtered["away_goals_ft"], errors="coerce").fillna(0)
    lines = [
        ("Over 0.5 FT", int((tg_ft >= 1).sum())),
        ("Over 1.5 FT", int((tg_ft >= 2).sum())),
        ("Over 2.5 FT", int((tg_ft >= 3).sum())),
        ("Over 3.5 FT", int((tg_ft >= 4).sum())),
        ("Over 4.5 FT", int((tg_ft >= 5).sum())),
        ("BTTS FT", int(((hg > 0) & (ag > 0)).sum())),
        ("1T Over 0.5", int((tg_ht >= 1).sum())),
        ("1T Over 1.5", int((tg_ht >= 2).sum())),
        ("2T Over 0.5", int((tg_2h >= 1).sum())),
        ("2T Over 1.5", int((tg_2h >= 2).sum())),
    ]
    items = [
        (label, round(cnt / n * 100, 1) if n else 0.0, f"{cnt} su {_fmt_n(n)} partite")
        for label, cnt in lines
    ]
    return _pick_best(items)


def _best_goal_distribution(filtered: pd.DataFrame, n: int) -> tuple[str, float, str]:
    counts: dict[str, int] = {"0 gol": 0, "1 gol": 0, "2 gol": 0, "3 gol": 0, "4 gol": 0, "5+ gol": 0}
    for g in pd.to_numeric(filtered["total_goals_ft"], errors="coerce").fillna(0):
        if g >= 5:
            counts["5+ gol"] += 1
        elif int(g) == 4:
            counts["4 gol"] += 1
        else:
            counts[f"{int(g)} gol"] += 1
    items = [
        (lbl, round(c / n * 100, 1) if n else 0.0, f"{c} partite su {_fmt_n(n)}")
        for lbl, c in counts.items()
    ]
    return _pick_best(items)


def _best_momentum_peak(goal_events, match_ids, home_lbl: str, away_lbl: str) -> tuple[str, float, str]:
    profile = build_similar_match_momentum(goal_events, match_ids)
    home = profile.get("home") or []
    away = profile.get("away") or []
    if not home or not away:
        return "Nessun dato", 0.0, "—"
    hi = max(range(len(home)), key=lambda i: home[i])
    ai = max(range(len(away)), key=lambda i: away[i])
    if home[hi] >= away[ai]:
        return f"Picco {home_lbl} al {hi + 1}'", home[hi], "Intensità gol casa"
    return f"Picco {away_lbl} al {ai + 1}'", away[ai], "Intensità gol trasferta"


def _best_timeline_zone(filtered: pd.DataFrame) -> tuple[str, float, str]:
    timeline = build_timeline(filtered)
    zones = build_intensity_zones(timeline)
    total = sum(zones.values()) or 1
    peak = detect_key_moments(zones).get("peak", "—")
    cnt = zones.get(peak, 0)
    pct = round(cnt / total * 100, 1) if peak != "—" else 0.0
    return f"Fascia {peak} minuti", pct, f"{cnt} gol su {total} totali"


def _best_first_goal_1t(match_ids, goal_events, n: int) -> tuple[str, float, str]:
    fg1t_home_mins, fg1t_away_mins = [], []
    fg_intervals_1t = {"0-15": [0, 0], "16-30": [0, 0], "31-45": [0, 0], "45+": [0, 0]}
    for mid in match_ids:
        events = goal_events.get(int(mid), [])
        sorted_evs = sorted(events, key=lambda x: _parse_minute(x["minute"])) if events else []
        evs_1t = [e for e in sorted_evs if _parse_minute(e["minute"]) <= 45]
        if not evs_1t:
            continue
        fg1 = evs_1t[0]
        m = _parse_minute(fg1["minute"])
        bucket = "0-15" if m <= 15 else "16-30" if m <= 30 else "31-45" if m <= 44 else "45+"
        if fg1["is_home"] == 1:
            fg1t_home_mins.append(m)
            fg_intervals_1t[bucket][0] += 1
        else:
            fg1t_away_mins.append(m)
            fg_intervals_1t[bucket][1] += 1
    data_1t = build_first_goal_data(
        fg1t_home_mins, fg1t_away_mins, fg_intervals_1t,
        [("0–15", ["0-15"]), ("16–30", ["16-30"]), ("31–45", ["31-45", "45+"])],
        30, n, 45,
    )
    dist = data_1t.get("distribution") or {}
    if not dist:
        return "Nessun gol nel 1T", 0.0, "—"
    best_lbl = max(dist, key=dist.get)
    return f"Primo gol tra {best_lbl}'", float(dist[best_lbl]), "1° tempo"


def _best_h2h(home_team: str, away_team: str, filters: dict) -> tuple[str, float, str] | None:
    all_rows = get_all_matches_unfiltered()
    if not all_rows:
        return None
    h2h_df = _filter_h2h_matches(pd.DataFrame(all_rows), home_team, away_team, filters)
    if h2h_df.empty:
        return None
    h2h = analyze_h2h(h2h_df, home_team, away_team)
    hn = h2h["found"]
    items = [
        (f"Vittoria {home_team[:20]}", float(h2h["home_win_pct"]), f"{h2h['home_wins']} su {hn} H2H"),
        ("Pareggio", float(h2h["draw_pct"]), f"{h2h['draws']} su {hn} H2H"),
        (f"Vittoria {away_team[:20]}", float(h2h["away_win_pct"]), f"{h2h['away_wins']} su {hn} H2H"),
        ("Over 2.5", float(h2h["over_25_pct"]), f"{h2h['over_25_n']} su {hn} H2H"),
        ("BTTS", float(h2h["btts_pct"]), f"{h2h['btts_n']} su {hn} H2H"),
    ]
    return _pick_best(items)


def _best_dna_metric(dna: dict) -> tuple[str, float, str]:
    gp = dna.get("goal_profile", {})
    df = dna.get("defensive", {})
    rh = dna.get("rhythm", {})
    items = [
        ("Segna nel 1° tempo", float(gp.get("score_1h_pct", 0))),
        ("Segna per prima", float(gp.get("score_first_pct", 0))),
        ("Over 2.5 nelle partite", float(rh.get("over_25_pct", 0))),
        ("BTTS nelle partite", float(rh.get("btts_pct", 0))),
        ("Clean sheet", float(df.get("clean_sheet_pct", 0))),
    ]
    lbl, pct, _ = _pick_best([(l, p, "") for l, p in items])
    return lbl, pct, f"Stile: {dna.get('style', 'N/D')}"


def _best_live_metric(live_state: dict) -> tuple[str, float, str]:
    items = [
        ("Prossimo gol Casa", float(live_state.get("next_goal_home", 0) or 0)),
        ("Prossimo gol Trasferta", float(live_state.get("next_goal_away", 0) or 0)),
        ("BTTS residuo", float(live_state.get("btts_si", 0) or 0)),
        ("Esito finale Casa", float(live_state.get("final_home", 0) or 0)),
        ("Esito finale Pareggio", float(live_state.get("final_draw", 0) or 0)),
        ("Esito finale Trasferta", float(live_state.get("final_away", 0) or 0)),
    ]
    lbl, pct, _ = _pick_best([(l, p, "") for l, p in items])
    found = int(live_state.get("found", 0) or 0)
    return lbl, pct, f"Basato su {found} partite simili"


def render():
    _inject_styles()

    filters = render_filter_sidebar("riepilogo")
    if not should_run_analysis(filters):
        st.info("👈 Imposta i filtri e clicca **📊 AGGIORNA RIEPILOGO** per visualizzare il riepilogo.")
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

    g_dist = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, "5+": 0}
    for g in pd.to_numeric(filtered["total_goals_ft"], errors="coerce").fillna(0):
        if g >= 5:
            g_dist["5+"] += 1
        else:
            g_dist[int(g)] += 1

    hw_pct, dr_pct, aw_pct = results["home_win_pct"], results["draw_pct"], results["away_win_pct"]

    teams_html = ""
    if home_team and away_team:
        teams_html = (
            f'<div style="display:flex;align-items:center;justify-content:center;gap:20px;margin-top:12px;">'
            f'{team_logo_html(home_team, size=44)}'
            f'<div style="font-size:15px;font-weight:800;color:{C_MUTED2};">VS</div>'
            f'{team_logo_html(away_team, size=44)}</div>'
        )

    st.html(f"""
    <div class="rp-hero">
        <div style="font-size:11px;color:{C_PURPLE};font-weight:700;letter-spacing:0.12em;text-transform:uppercase;">
            Lettura rapida del campione
        </div>
        <div style="font-size:26px;font-weight:900;color:{C_TEXT};margin:6px 0;">📊 Riepilogo</div>
        <div style="font-size:14px;color:{C_MUTED};">
            <b style="color:{C_TEXT};">{league}</b> · <b style="color:{C_CYAN};">{_fmt_n(n)}</b> partite analizzate
        </div>
        {teams_html}
    </div>
    <div class="rp-legend">
        Ogni card mostra la <b style="color:{C_TEXT};">percentuale più alta</b> di quell’area —
        non il grafico completo. La barra colorata indica l’intensità del segnale.
    </div>
    """)

    header_insights = compute_header_insights(
        hw_pct, dr_pct, aw_pct, n, results, filtered,
        goal_events, match_ids, _parse_minute, g_dist,
    )

    hg_ft = pd.to_numeric(filtered["home_goals_ft"], errors="coerce").fillna(0)
    ag_ft = pd.to_numeric(filtered["away_goals_ft"], errors="coerce").fillna(0)
    hw_c, dr_c, aw_c = int((hg_ft > ag_ft).sum()), int((hg_ft == ag_ft).sum()), int((hg_ft < ag_ft).sum())

    esito_lbl, esito_pct, _ = _pick_best([
        (f"Vittoria {home_lbl}", hw_pct, ""),
        ("Pareggio", dr_pct, ""),
        (f"Vittoria {away_lbl}", aw_pct, ""),
    ])
    esito_counts = {
        f"Vittoria {home_lbl}": hw_c,
        "Pareggio": dr_c,
        f"Vittoria {away_lbl}": aw_c,
    }
    esito_det = f"{esito_counts.get(esito_lbl, 0)} su {_fmt_n(n)} partite"

    ed = header_insights.get("edge_data") or {}
    edge_pct = round(float(ed.get("edge_max", 0) or 0) * 100, 1)
    edge_lbl = ed.get("best_market", "—")
    ou_lbl, ou_pct, ou_det = _best_over_under(filtered, n)
    dist_lbl, dist_pct, dist_det = _best_goal_distribution(filtered, n)

    _section(
        "01", "Risultato e mercati",
        "Esito più probabile, valore atteso e linee goal più frequenti",
        C_CYAN,
        [
            _best_card("Esito 1X2", esito_lbl, esito_pct, esito_det, "Esito finale più frequente", C_CYAN),
            _best_card(
                "Edge / Valore",
                edge_lbl,
                edge_pct,
                "Miglior scostamento quota vs probabilità",
                "Mercato con più valore atteso",
                C_GREEN if edge_pct > 0 else C_RED,
            ),
            _best_card("Over / Under", ou_lbl, ou_pct, ou_det, "Linea goal con % più alta", get_pct_color(ou_pct)),
            _best_card("Totale gol", dist_lbl, dist_pct, dist_det, "Risultato gol più ripetuto", C_AMBER),
        ],
        cols=4,
    )

    mom_lbl, mom_pct, mom_det = _best_momentum_peak(goal_events, match_ids, home_lbl, away_lbl)
    tl_lbl, tl_pct, tl_det = _best_timeline_zone(filtered)
    fg_lbl, fg_pct, fg_det = _best_first_goal_1t(match_ids, goal_events, n)

    _section(
        "02", "Tempi e gol",
        "Quando si concentrano i gol e quando arriva il primo gol",
        C_GREEN,
        [
            _best_card("Momentum", mom_lbl, mom_pct, mom_det, "Minuto di massima pressione", C_GREEN),
            _best_card("Timeline", tl_lbl, tl_pct, tl_det, "Fascia con più gol segnati", C_AMBER),
            _best_card("Primo gol", fg_lbl, fg_pct, fg_det, "Intervallo più frequente nel 1T", C_CYAN),
        ],
        cols=3,
    )

    squadre_cards: list[str] = []
    if home_team and away_team and home_team != away_team:
        h2h_pick = _best_h2h(home_team, away_team, filters)
        if h2h_pick:
            h_lbl, h_pct, h_det = h2h_pick
            squadre_cards.append(_best_card("Testa a testa", h_lbl, h_pct, h_det, "Miglior segnale negli scontri diretti", C_AMBER))
        else:
            squadre_cards.append(_best_card(
                "Testa a testa", "Nessun H2H", 0.0,
                f"Nessuno scontro tra {home_lbl} e {away_lbl}", "", C_MUTED2,
            ))
    if home_team:
        dna_h = analyze_team_dna(filtered, home_team, goal_events=goal_events)
        d_lbl, d_pct, d_det = _best_dna_metric(dna_h)
        squadre_cards.append(_best_card(f"DNA {home_lbl}", d_lbl, d_pct, d_det, "Metrica più forte del profilo", C_PURPLE))
    if away_team:
        dna_a = analyze_team_dna(filtered, away_team, goal_events=goal_events)
        d_lbl, d_pct, d_det = _best_dna_metric(dna_a)
        squadre_cards.append(_best_card(f"DNA {away_lbl}", d_lbl, d_pct, d_det, "Metrica più forte del profilo", C_PURPLE))

    if squadre_cards:
        ncol = 3 if len(squadre_cards) >= 3 else len(squadre_cards)
        _section(
            "03", "Squadre",
            "Profilo delle squadre selezionate e scontri diretti",
            C_PURPLE,
            squadre_cards,
            cols=ncol,
        )
    else:
        st.html(f"""
        <div class="rp-block">
            <div class="rp-block-head">
                <div class="rp-block-num" style="background:{C_PURPLE}22;border:1px solid {C_PURPLE}55;color:{C_PURPLE};">03</div>
                <div>
                    <div class="rp-block-title">Squadre</div>
                    <div class="rp-block-sub">Seleziona Casa e/o Trasferta nei filtri per DNA e H2H</div>
                </div>
            </div>
        </div>
        """)

    ranking = find_best_strategy(filtered)
    live_saved = st.session_state.get("_saved_filters_live", {})
    minute = max(1, int(live_saved.get("current_minute", 0) or 0))
    h_score = int(live_saved.get("home_score", 0) or 0)
    a_score = int(live_saved.get("away_score", 0) or 0)
    if int(live_saved.get("current_minute", 0) or 0) <= 0:
        h_score, a_score = 0, 0
    live_state = analyze_live_state_v2(
        filtered, goal_events, minute, h_score, a_score,
        odds_home_ref=filters.get("odds_home_min"),
    )
    lv_lbl, lv_pct, lv_det = _best_live_metric(live_state)

    trading_cards = []
    if not ranking.empty:
        top = ranking.iloc[0]
        trading_cards.append(_best_card(
            "Strategia migliore",
            str(top["strategy"]),
            float(top["roi"]),
            f"Strike {top['strike_rate']:.0f}% · {int(top['total_bets'])} bet",
            "ROI più alto nel backtest",
            C_GREEN if float(top["roi"]) > 0 else C_RED,
        ))
    else:
        trading_cards.append(_best_card(
            "Strategia", "Nessuna strategia", 0.0,
            "Campione senza quote o risultati utili", "", C_MUTED2,
        ))

    live_hint = "Stato base 0-0 al 1'" if h_score == 0 and a_score == 0 and minute <= 1 else f"Risultato {h_score}-{a_score} al {minute}'"
    trading_cards.append(_best_card(
        "Proiezione live",
        lv_lbl,
        lv_pct,
        lv_det,
        live_hint,
        C_GREEN,
    ))

    _section(
        "04", "Trading e live",
        "Migliore strategia sul campione e segnale live più forte",
        C_AMBER,
        trading_cards,
        cols=2,
    )
