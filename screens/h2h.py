"""
screens/h2h.py — Head-to-Head Analysis dashboard (mockup layout)
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import datetime
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database import get_all_matches_unfiltered
from filters import render_filter_sidebar, should_run_analysis
from calculations import analyze_h2h, _h2h_team_result_label
from utils import team_logo_html

C_BG     = "#111827"
C_BORDER = "#1f2937"
C_TEXT   = "#f1f5f9"
C_MUTED  = "#94a3b8"
C_MUTED2 = "#64748b"
C_GREEN  = "#22c55e"
C_YELLOW = "#f59e0b"
C_RED    = "#ef4444"


def _inject_styles():
    st.html(f"""
    <style>
        .h2h-panel {{
            background:{C_BG}; border:1px solid {C_BORDER}; border-radius:8px;
            padding:14px; height:100%;
        }}
        .h2h-lbl {{
            font-size:10px; color:{C_MUTED}; text-transform:uppercase;
            letter-spacing:0.7px; margin-bottom:6px;
        }}
        .h2h-big {{ font-size:26px; font-weight:800; line-height:1.1; }}
        .h2h-sub {{ font-size:11px; color:{C_MUTED2}; margin-top:4px; }}
        .h2h-title {{
            font-size:12px; font-weight:700; color:{C_TEXT};
            margin-bottom:10px; text-transform:uppercase; letter-spacing:0.5px;
        }}
        .h2h-bar-track {{
            background:#1f2937; border-radius:4px; height:6px; margin-top:4px;
        }}
        .h2h-bar-fill {{ height:6px; border-radius:4px; }}
        .h2h-insight {{
            display:flex; gap:10px; align-items:flex-start;
            padding:8px 0; border-bottom:1px solid {C_BORDER};
            font-size:12px; color:{C_MUTED};
        }}
        div[data-testid="stPlotlyChart"] {{
            background:{C_BG}; border:1px solid {C_BORDER};
            border-radius:8px; padding:2px;
        }}
    </style>
    """)


def _summary_card(label: str, value: str, sub: str = "", color: str = C_TEXT, bar_pct: float = 0) -> str:
    bar = ""
    if bar_pct > 0:
        bar = (
            f'<div class="h2h-bar-track"><div class="h2h-bar-fill" '
            f'style="width:{min(bar_pct, 100):.0f}%;background:{C_GREEN};"></div></div>'
        )
    return (
        f'<div class="h2h-panel" style="text-align:center;">'
        f'<div class="h2h-lbl">{label}</div>'
        f'<div class="h2h-big" style="color:{color};">{value}</div>'
        f'<div class="h2h-sub">{sub}</div>{bar}</div>'
    )


def _filter_h2h_matches(df: pd.DataFrame, home: str, away: str, filters: dict) -> pd.DataFrame:
    venue = filters.get("h2h_venue", "Tutti gli scontri")
    if venue == "Solo casa (squadra casa)":
        h2h = df[(df["home_team"] == home) & (df["away_team"] == away)].copy()
    elif venue == "Solo trasferta (squadra casa)":
        h2h = df[(df["home_team"] == away) & (df["away_team"] == home)].copy()
    else:
        h2h = df[
            ((df["home_team"] == home) & (df["away_team"] == away)) |
            ((df["home_team"] == away) & (df["away_team"] == home))
        ].copy()
    if h2h.empty:
        return h2h

    league = filters.get("h2h_league", filters.get("league", "Tutti i campionati"))
    if league and league not in ("Tutte le competizioni", "Tutti i campionati", "Tutti", "Tutte") and "league" in h2h.columns:
        h2h = h2h[h2h["league"] == league]

    if "match_date" in h2h.columns:
        h2h["match_date"] = pd.to_datetime(h2h["match_date"], errors="coerce")
        h2h = h2h.sort_values("match_date", ascending=False)
        d_from = filters.get("date_from")
        d_to = filters.get("date_to")
        if d_from is not None:
            h2h = h2h[h2h["match_date"] >= pd.Timestamp(d_from)]
        if d_to is not None:
            h2h = h2h[h2h["match_date"] <= pd.Timestamp(d_to)]

    tg = pd.to_numeric(h2h["total_goals_ft"], errors="coerce").fillna(0)
    hg = pd.to_numeric(h2h["home_goals_ft"], errors="coerce").fillna(0)
    ag = pd.to_numeric(h2h["away_goals_ft"], errors="coerce").fillna(0)

    if filters.get("h2h_f_over15"):
        h2h = h2h[tg >= 2]
    if filters.get("h2h_f_over25"):
        h2h = h2h[tg >= 3]
    if filters.get("h2h_f_over35"):
        h2h = h2h[tg >= 4]
    if filters.get("h2h_f_btts"):
        h2h = h2h[(hg >= 1) & (ag >= 1)]

    res_home = filters.get("h2h_res_home")
    res_draw = filters.get("h2h_res_draw")
    res_away = filters.get("h2h_res_away")
    if res_home or res_draw or res_away:
        mask = pd.Series(False, index=h2h.index)
        for idx, row in h2h.iterrows():
            h_g = float(row.get("home_goals_ft") or 0)
            a_g = float(row.get("away_goals_ft") or 0)
            if row["home_team"] == home:
                th, ta = h_g, a_g
            else:
                th, ta = a_g, h_g
            if res_home and th > ta:
                mask.loc[idx] = True
            if res_draw and th == ta:
                mask.loc[idx] = True
            if res_away and th < ta:
                mask.loc[idx] = True
        h2h = h2h[mask]

    tg = pd.to_numeric(h2h["total_goals_ft"], errors="coerce").fillna(0)
    h2h = h2h[(tg >= int(filters.get("h2h_min_goals_total", 0)))
              & (tg <= int(filters.get("h2h_max_goals_total", 15)))]

    min_h = int(filters.get("h2h_min_goals_home", 0))
    min_a = int(filters.get("h2h_min_goals_away", 0))
    if min_h > 0 or min_a > 0:
        keep = []
        for _, row in h2h.iterrows():
            h_g = float(row.get("home_goals_ft") or 0)
            a_g = float(row.get("away_goals_ft") or 0)
            if row["home_team"] == home:
                th, ta = h_g, a_g
            else:
                th, ta = a_g, h_g
            if th >= min_h and ta >= min_a:
                keep.append(True)
            else:
                keep.append(False)
        h2h = h2h[keep]

    last_n = filters.get("h2h_last_n", "Tutte")
    if last_n and last_n != "Tutte":
        h2h = h2h.head(int(last_n))

    return h2h


def _filter_summary(filters: dict, n: int, total_db: int) -> str:
    parts = [f"<b>{n}</b> scontri su <b>{total_db}</b> nel database"]
    venue = filters.get("h2h_venue", "Tutti gli scontri")
    if venue != "Tutti gli scontri":
        parts.append(venue.lower())
    league = filters.get("h2h_league", filters.get("league", "Tutti i campionati"))
    if league and league not in ("Tutte le competizioni", "Tutti i campionati", "Tutti", "Tutte"):
        parts.append(f"campionato <b>{league}</b>")
    last_n = filters.get("h2h_last_n", "Tutte")
    if last_n and last_n != "Tutte":
        parts.append(f"ultime <b>{last_n}</b> partite")
    return " · ".join(parts)


def _count_all_h2h(df: pd.DataFrame, home: str, away: str) -> int:
    mask = (
        ((df["home_team"] == home) & (df["away_team"] == away))
        | ((df["home_team"] == away) & (df["away_team"] == home))
    )
    return int(mask.sum())


def _build_matches_df(h2h_df: pd.DataFrame, home: str, away: str) -> pd.DataFrame:
    if h2h_df is None or h2h_df.empty:
        return pd.DataFrame()

    rows = []
    for _, row in h2h_df.iterrows():
        hg = float(row.get("home_goals_ft") or 0)
        ag = float(row.get("away_goals_ft") or 0)
        tg = float(row.get("total_goals_ft") or hg + ag)
        hht = float(row.get("home_goals_ht") or 0)
        aht = float(row.get("away_goals_ht") or 0)
        ht_lbl = _h2h_team_result_label(hht, aht, home, away, row["home_team"])
        ft_lbl = _h2h_team_result_label(hg, ag, home, away, row["home_team"])
        if row["home_team"] == home:
            sel_hg, sel_ag = hg, ag
            campo = f"Casa ({home})"
        else:
            sel_hg, sel_ag = ag, hg
            campo = f"Trasferta ({home})"

        dt = row.get("match_date")
        if pd.notna(dt):
            dt = pd.Timestamp(dt).strftime("%d/%m/%Y")
        else:
            dt = "—"

        rows.append({
            "Data": dt,
            "Campionato": row.get("league") or "—",
            "Stagione": row.get("season") or "—",
            "Campo": campo,
            "Casa": row.get("home_team", ""),
            "Trasferta": row.get("away_team", ""),
            "Risultato": row.get("ft_result") or f"{int(hg)}-{int(ag)}",
            "HT/FT": f"{ht_lbl} / {ft_lbl}",
            "Gol": int(tg),
            "O2.5": "✅" if tg >= 3 else "❌",
            "BTTS": "✅" if hg >= 1 and ag >= 1 else "❌",
            "_sel_hg": sel_hg,
            "_sel_ag": sel_ag,
            "_sort_date": pd.to_datetime(row.get("match_date"), errors="coerce"),
        })

    out = pd.DataFrame(rows)
    if not out.empty and "_sort_date" in out.columns:
        out = out.sort_values("_sort_date", ascending=False, kind="stable")
    return out.drop(columns=["_sort_date"], errors="ignore")


def _render_matchup_header(home: str, away: str) -> None:
    now = datetime.datetime.now().strftime("%H:%M  %d %B %Y")
    st.html(
        f'<div style="background:{C_BG};border:1px solid {C_BORDER};border-radius:8px;'
        f'padding:16px 20px;margin-bottom:12px;display:flex;align-items:center;'
        f'justify-content:space-between;flex-wrap:wrap;gap:12px;">'
        f'<div style="display:flex;align-items:center;gap:28px;flex:1;justify-content:center;">'
        f'{team_logo_html(home, size=56, fallback_color=C_GREEN, name_color=C_TEXT)}'
        f'<div style="font-size:22px;font-weight:900;color:{C_MUTED2};">VS</div>'
        f'{team_logo_html(away, size=56, fallback_color=C_RED, name_color=C_TEXT)}'
        f'</div>'
        f'<div style="text-align:right;font-size:10px;color:{C_MUTED};">'
        f'AGGIORNATO<br><span style="color:{C_GREEN};font-weight:700;">🔄 {now}</span>'
        f'</div></div>'
    )


def _donut_chart(home: str, away: str, r: dict):
    fig = go.Figure(go.Pie(
        labels=[home, "Pareggio", away],
        values=[r["home_wins"], r["draws"], r["away_wins"]],
        hole=0.55,
        marker=dict(colors=[C_GREEN, C_YELLOW, C_RED]),
        textinfo="percent",
        textfont=dict(size=11, color=C_TEXT),
        hovertemplate="%{label}<br>%{value} (%{percent})<extra></extra>",
    ))
    fig.update_layout(
        title=dict(text="Distribuzione Risultati", font=dict(color=C_TEXT, size=12)),
        paper_bgcolor=C_BG, plot_bgcolor=C_BG,
        font=dict(color=C_MUTED, size=10),
        margin=dict(l=10, r=10, t=36, b=10),
        showlegend=True,
        legend=dict(orientation="v", x=1.02, y=0.5, font=dict(size=10)),
        height=240,
    )
    return fig


def _btts_gauge(pct: float, count: int, total: int):
    fig = go.Figure(go.Pie(
        values=[pct, max(100 - pct, 0)],
        hole=0.72,
        marker=dict(colors=[C_GREEN, C_BORDER]),
        textinfo="none",
        hoverinfo="skip",
        direction="clockwise",
        sort=False,
    ))
    fig.update_layout(
        title=dict(text="BTTS (Gol Gol)", font=dict(color=C_TEXT, size=12)),
        paper_bgcolor=C_BG, plot_bgcolor=C_BG,
        margin=dict(l=10, r=10, t=36, b=10),
        height=240,
        annotations=[dict(
            text=f"<b>{pct:.2f}%</b><br><span style='font-size:10px'>{count} su {total}</span>",
            x=0.5, y=0.5, font=dict(size=16, color=C_TEXT), showarrow=False,
        )],
    )
    return fig


def _over_under_bars(r: dict) -> str:
    rows = [
        ("Over 1.5", r["over_15_pct"], C_GREEN),
        ("Over 2.5", r["over_25_pct"], C_GREEN),
        ("Over 3.5", r["over_35_pct"], C_GREEN),
        ("Under 2.5", r["under_25_pct"], C_RED),
    ]
    html = f'<div class="h2h-title">Over / Under</div>'
    for lbl, pct, col in rows:
        html += (
            f'<div style="margin-bottom:10px;">'
            f'<div style="display:flex;justify-content:space-between;font-size:11px;color:{C_MUTED};">'
            f'<span>{lbl}</span><span style="color:{col};font-weight:700;">{pct:.2f}%</span></div>'
            f'<div class="h2h-bar-track"><div class="h2h-bar-fill" '
            f'style="width:{min(pct, 100):.0f}%;background:{col};"></div></div></div>'
        )
    return f'<div class="h2h-panel">{html}</div>'


def _avg_goals_panel(home: str, away: str, r: dict) -> str:
    return (
        f'<div class="h2h-panel" style="text-align:center;">'
        f'<div class="h2h-title">Media Gol a Partita</div>'
        f'<div style="display:flex;align-items:center;justify-content:center;gap:16px;margin-top:18px;">'
        f'<div><div style="font-size:11px;color:{C_MUTED};">{home}</div>'
        f'<div style="font-size:32px;font-weight:900;color:{C_GREEN};">{r["home_avg_goals"]}</div></div>'
        f'<div style="font-size:22px;color:{C_MUTED2};">⚽</div>'
        f'<div><div style="font-size:11px;color:{C_MUTED};">{away}</div>'
        f'<div style="font-size:32px;font-weight:900;color:{C_RED};">{r["away_avg_goals"]}</div></div>'
        f'</div></div>'
    )


def _minute_table_html(home: str, away: str, rows: list) -> str:
    hdr = (
        f'<tr style="color:{C_MUTED};font-size:10px;">'
        f'<th style="text-align:left;padding:6px 4px;"></th>'
        f'<th style="padding:6px 4px;">0-15\'</th><th>16-30\'</th><th>31-45\'</th>'
        f'<th>46-60\'</th><th>61-75\'</th><th>76-90+\'</th></tr>'
    )
    body = ""
    buckets = ["0-15", "16-30", "31-45", "46-60", "61-75", "76-90+"]
    for label, key, color in ((home, "home", C_GREEN), (away, "away", C_RED), ("Totale", "total", C_TEXT)):
        by_bucket = {b["bucket"]: b[key] for b in rows}
        cells = "".join(
            f'<td style="text-align:center;padding:6px 4px;'
            f'{"font-weight:700;" if key == "total" else ""}color:{color};">'
            f'{by_bucket.get(b, 0)}</td>'
            for b in buckets
        )
        body += (
            f'<tr style="border-top:1px solid {C_BORDER};">'
            f'<td style="padding:6px 4px;font-size:11px;color:{color};font-weight:600;">{label}</td>'
            f'{cells}</tr>'
        )
    return (
        f'<div class="h2h-panel">'
        f'<div class="h2h-title">Distribuzione Gol nei Minuti</div>'
        f'<table style="width:100%;border-collapse:collapse;font-size:11px;">'
        f'{hdr}{body}</table></div>'
    )


def _ht_ft_html(items: list) -> str:
    rows = ""
    for it in items[:8]:
        rows += (
            f'<div style="display:flex;justify-content:space-between;align-items:center;'
            f'padding:7px 0;border-bottom:1px solid {C_BORDER};font-size:11px;">'
            f'<span style="color:{C_TEXT};">{it["icon"]} {it["label"]}</span>'
            f'<span style="color:{C_MUTED};">{it["count"]} volte · '
            f'<b style="color:{C_TEXT};">{it["pct"]:.2f}%</b></span></div>'
        )
    return f'<div class="h2h-panel"><div class="h2h-title">HT / FT</div>{rows}</div>'


def _render_all_matches_table(
    h2h_df: pd.DataFrame, home: str, away: str, filters: dict, total_db: int,
) -> None:
    full_df = _build_matches_df(h2h_df, home, away)
    n = len(full_df)
    summary = _filter_summary(filters, n, total_db)
    st.html(
        f'<div class="h2h-panel" style="margin-bottom:10px;">'
        f'<div class="h2h-title">Tutti gli Scontri Diretti</div>'
        f'<div style="font-size:12px;color:{C_MUTED};">{summary}</div></div>'
    )

    if full_df.empty:
        st.info("Nessun incontro con i filtri selezionati.")
        return

    show_df = full_df.drop(columns=["_sel_hg", "_sel_ag"], errors="ignore")

    def _style_rows(row):
        idx = row.name
        hg = full_df.loc[idx, "_sel_hg"]
        ag = full_df.loc[idx, "_sel_ag"]
        styles = [""] * len(row)
        cols = list(row.index)
        if hg > ag:
            color, weight = C_GREEN, "bold"
        elif hg < ag:
            color, weight = C_RED, "normal"
        else:
            color, weight = C_YELLOW, "normal"
        if "Risultato" in cols:
            styles[cols.index("Risultato")] = f"color: {color}; font-weight: {weight};"
        return styles

    styled = show_df.style.apply(_style_rows, axis=1)
    st.dataframe(styled, use_container_width=True, hide_index=True, key="h2h_all_matches")


def _insights_html(insights: list) -> str:
    icons = ["📊", "⚽", "🎯", "⚡"]
    rows = ""
    for i, txt in enumerate(insights[:4]):
        icon = icons[i % len(icons)]
        rows += f'<div class="h2h-insight"><span>{icon}</span><span>{txt}</span></div>'
    return f'<div class="h2h-panel"><div class="h2h-title">Insight Chiave</div>{rows}</div>'


def render():
    _inject_styles()

    filters = render_filter_sidebar("h2h")
    if not filters:
        return

    if not should_run_analysis(filters):
        st.info("👈 Seleziona le squadre e clicca **🔍 ANALIZZA H2H** nella sidebar.")
        return

    home_team = filters.get("home_team", "")
    away_team = filters.get("away_team", "")
    if not home_team or not away_team:
        st.warning("Seleziona entrambe le squadre.")
        return
    if home_team == away_team:
        st.warning("Le squadre devono essere diverse.")
        return

    with st.spinner("Analisi H2H in corso..."):
        rows = get_all_matches_unfiltered()
        if not rows:
            st.warning("⚠️ Nessun dato nel database.")
            return
        df = pd.DataFrame(rows)

    total_h2h_db = _count_all_h2h(df, home_team, away_team)
    h2h_df = _filter_h2h_matches(df, home_team, away_team, filters)

    if h2h_df.empty:
        st.html(
            f'<div style="background:{C_BG};border:1px solid {C_BORDER};border-radius:8px;'
            f'padding:28px;text-align:center;color:{C_YELLOW};font-size:15px;font-weight:600;">'
            f'⚠️ Nessun scontro diretto trovato con i filtri selezionati<br>'
            f'<span style="font-size:12px;color:{C_MUTED};">'
            f'Nel database ci sono <b>{total_h2h_db}</b> incontri tra queste squadre</span></div>'
        )
        return

    results = analyze_h2h(h2h_df, home_team, away_team)

    n = results["found"]
    _render_matchup_header(home_team, away_team)

    # ── Row 1: 6 summary cards ────────────────────────────────────────────────
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    with c1:
        st.html(_summary_card(
            "Partite Totali", str(n),
            f"Dal {results['date_from']}", C_TEXT,
        ))
    with c2:
        st.html(_summary_card(
            f"Vittorie {home_team}", str(results["home_wins"]),
            f"{results['home_win_pct']:.2f}%", C_GREEN,
        ))
    with c3:
        st.html(_summary_card(
            "Pareggi", str(results["draws"]),
            f"{results['draw_pct']:.2f}%", C_YELLOW,
        ))
    with c4:
        st.html(_summary_card(
            f"Vittorie {away_team}", str(results["away_wins"]),
            f"{results['away_win_pct']:.2f}%", C_RED,
        ))
    with c5:
        st.html(_summary_card(
            "Gol Totali", str(results["total_goals_sum"]),
            f"{results['avg_goals']} a partita", C_TEXT,
        ))
    with c6:
        st.html(_summary_card(
            "Over 2.5", str(results["over_25_n"]),
            f"{results['over_25_pct']:.2f}%", C_GREEN,
            bar_pct=results["over_25_pct"],
        ))

    # ── Row 2: charts ─────────────────────────────────────────────────────────
    ch1, ch2, ch3, ch4 = st.columns(4)
    with ch1:
        st.plotly_chart(_donut_chart(home_team, away_team, results), use_container_width=True)
    with ch2:
        st.html(_avg_goals_panel(home_team, away_team, results))
    with ch3:
        st.html(_over_under_bars(results))
    with ch4:
        st.plotly_chart(
            _btts_gauge(results["btts_pct"], results["btts_n"], n),
            use_container_width=True,
        )

    # ── Row 3: minute table + HT/FT ───────────────────────────────────────────
    m1, m2 = st.columns([3, 2])
    with m1:
        st.html(_minute_table_html(home_team, away_team, results["minute_table"]))
    with m2:
        st.html(_ht_ft_html(results["ht_ft_list"]))

    # ── Row 4: all matches + insights ─────────────────────────────────────────
    b1, b2 = st.columns([3, 2])
    with b1:
        _render_all_matches_table(h2h_df, home_team, away_team, filters, total_h2h_db)
    with b2:
        st.html(_insights_html(results.get("insights", [])))
