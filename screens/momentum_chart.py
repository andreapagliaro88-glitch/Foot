"""Grafico profilo momentum atteso (casa vs trasferta) da minuti gol del campione."""

from __future__ import annotations

import streamlit as st
from utils import parse_goal_minute_value

C_BLUE2 = "#3b82f6"
C_RED = "#ef4444"
C_MUTED = "#94a3b8"
C_MUTED2 = "#64748b"
PLOT_BG = "rgba(0,0,0,0)"


def _parse_minute(raw) -> int:
    minute = parse_goal_minute_value(raw)
    return minute if minute is not None else 0


def _events_for_match(goal_events, match_id):
    if isinstance(goal_events, dict):
        return goal_events.get(match_id, [])
    return [e for e in goal_events if e.get("match_id") == match_id]


def build_similar_match_momentum(
    goal_events,
    match_ids: list,
    window: int = 2,
    smooth: int = 5,
    top_markers: int = 4,
) -> dict:
    """
    Profilo atteso casa/trasferta dai minuti gol del campione (partite simili).
    Ogni gol distribuisce peso su ±window minuti; curva smussata e normalizzata 0–100.
    """
    n_matches = len(match_ids or [])
    home_raw = [0.0] * 91
    away_raw = [0.0] * 91

    if n_matches == 0:
        return {
            "minutes": list(range(1, 91)),
            "home": [0.0] * 90,
            "away": [0.0] * 90,
            "home_markers": [],
            "away_markers": [],
            "n_matches": 0,
        }

    for mid in match_ids:
        for e in _events_for_match(goal_events, mid):
            m = _parse_minute(e.get("minute", 0))
            if m < 1:
                continue
            m = min(m, 90)
            is_home = e.get("is_home", 0) == 1
            target = home_raw if is_home else away_raw
            for d in range(-window, window + 1):
                mm = m + d
                if 1 <= mm <= 90:
                    weight = 1.0 - (abs(d) / (window + 1))
                    target[mm] += weight

    def _smooth_series(raw: list, radius: int) -> list:
        out = []
        for i in range(1, 91):
            lo = max(1, i - radius)
            hi = min(90, i + radius)
            span = hi - lo + 1
            out.append(sum(raw[lo:hi + 1]) / (span * n_matches))
        return out

    radius = max(1, smooth // 2)
    home_sm = _smooth_series(home_raw, radius)
    away_sm = _smooth_series(away_raw, radius)
    peak = max(max(home_sm, default=0), max(away_sm, default=0), 1e-9)
    home_norm = [round(v / peak * 100, 2) for v in home_sm]
    away_norm = [round(v / peak * 100, 2) for v in away_sm]

    def _top_markers(values: list, raw: list) -> list:
        ranked = sorted(
            ((i + 1, values[i], raw[i + 1]) for i in range(90)),
            key=lambda x: (x[2], x[1]),
            reverse=True,
        )
        chosen = []
        used = set()
        for minute, val, _ in ranked:
            if len(chosen) >= top_markers or val <= 0:
                break
            if any(abs(minute - u) <= 3 for u in used):
                continue
            chosen.append({"minute": minute, "value": val})
            used.add(minute)
        return chosen

    return {
        "minutes": list(range(1, 91)),
        "home": home_norm,
        "away": away_norm,
        "home_markers": _top_markers(home_norm, home_raw),
        "away_markers": _top_markers(away_norm, away_raw),
        "n_matches": n_matches,
    }


def build_momentum_insights(
    profile: dict,
    home_team: str,
    away_team: str,
) -> list[str]:
    """2–3 frasi leggibili dal profilo intensità gol."""
    home = profile.get("home") or []
    away = profile.get("away") or []
    if not home or not away:
        return []

    home_lbl = (home_team or "Casa").strip()
    away_lbl = (away_team or "Trasferta").strip()
    if home_lbl in ("Casa", "Tutte le squadre"):
        home_lbl = "Casa"
    if away_lbl in ("Trasferta", "Tutte le squadre"):
        away_lbl = "Trasferta"

    insights: list[str] = []
    h_avg = sum(home) / len(home)
    a_avg = sum(away) / len(away)

    if h_avg > a_avg * 1.12:
        insights.append(f"🏠 {home_lbl} domina il profilo storico")
    elif a_avg > h_avg * 1.12:
        insights.append(f"✈️ {away_lbl} più pericolosa in media")
    else:
        insights.append("⚖️ Equilibrio tra casa e trasferta")

    first_half = sum(home[:45]) + sum(away[:45])
    second_half = sum(home[45:]) + sum(away[45:])
    if second_half > first_half * 1.15:
        insights.append("📈 2° tempo più vivace nel campione")
    elif first_half > second_half * 1.15:
        insights.append("🌅 1° tempo più intenso del solito")

    late = sum(home[75:]) + sum(away[75:])
    overall = (sum(home) + sum(away)) / 2
    late_avg = late / 30 if late else 0
    if late_avg > overall * 0.55:
        insights.append("🔥 Finale vivace (76'–90')")

    h_peak = home.index(max(home)) + 1
    a_peak = away.index(max(away)) + 1
    insights.append(f"⏱ Picchi tipici: {home_lbl} ~{h_peak}' · {away_lbl} ~{a_peak}'")

    return insights[:3]


def similar_momentum_fig(
    profile: dict,
    home_team: str,
    away_team: str,
    current_minute: int = 90,
    show_minute_marker: bool = False,
):
    """Grafico profilo atteso (casa vs trasferta) da partite simili."""
    import plotly.graph_objects as go

    if not profile or profile.get("n_matches", 0) == 0:
        return None

    minutes = profile["minutes"]
    home_y = profile["home"]
    away_y = profile["away"]
    cur = max(1, min(int(current_minute), 90))

    def _split_series(xs, ys, cutoff):
        past_x, past_y, fut_x, fut_y = [], [], [], []
        for x, y in zip(xs, ys):
            if x <= cutoff:
                past_x.append(x)
                past_y.append(y)
            else:
                fut_x.append(x)
                fut_y.append(y)
        if past_x and fut_x:
            past_x.append(fut_x[0])
            past_y.append(fut_y[0])
        return past_x, past_y, fut_x, fut_y

    if show_minute_marker and cur < 90:
        h_past_x, h_past_y, h_fut_x, h_fut_y = _split_series(minutes, home_y, cur)
        a_past_x, a_past_y, a_fut_x, a_fut_y = _split_series(minutes, away_y, cur)
    else:
        h_past_x, h_past_y, h_fut_x, h_fut_y = minutes, home_y, [], []
        a_past_x, a_past_y, a_fut_x, a_fut_y = minutes, away_y, [], []

    home_lbl = (home_team or "Casa")[:18]
    away_lbl = (away_team or "Trasferta")[:18]

    fig = go.Figure()
    _ht = "%{x}' · %{y:.0f}<extra></extra>"

    if h_fut_x:
        fig.add_trace(go.Scatter(
            x=h_fut_x, y=h_fut_y,
            mode="lines",
            line=dict(color="rgba(59,130,246,0.25)", width=2),
            showlegend=False, hoverinfo="skip",
        ))
    fig.add_trace(go.Scatter(
        x=h_past_x, y=h_past_y, name=home_lbl,
        mode="lines",
        line=dict(color=C_BLUE2, width=2.5),
        hovertemplate=_ht,
    ))

    if a_fut_x:
        fig.add_trace(go.Scatter(
            x=a_fut_x, y=a_fut_y,
            mode="lines",
            line=dict(color="rgba(239,68,68,0.25)", width=2),
            showlegend=False, hoverinfo="skip",
        ))
    fig.add_trace(go.Scatter(
        x=a_past_x, y=a_past_y, name=away_lbl,
        mode="lines",
        line=dict(color=C_RED, width=2.5),
        hovertemplate=_ht,
    ))

    for mk in profile.get("home_markers", []):
        fig.add_trace(go.Scatter(
            x=[mk["minute"]], y=[mk["value"]],
            mode="markers+text",
            marker=dict(size=9, color=C_BLUE2, symbol="circle"),
            text=["⚽"], textposition="top center",
            textfont=dict(size=11),
            showlegend=False,
            hovertemplate=f"Casa · min {mk['minute']}'<extra></extra>",
        ))
    for mk in profile.get("away_markers", []):
        fig.add_trace(go.Scatter(
            x=[mk["minute"]], y=[mk["value"]],
            mode="markers+text",
            marker=dict(size=9, color=C_RED, symbol="circle"),
            text=["⚽"], textposition="top center",
            textfont=dict(size=11),
            showlegend=False,
            hovertemplate=f"Trasferta · min {mk['minute']}'<extra></extra>",
        ))

    if show_minute_marker and cur < 90:
        fig.add_vline(x=cur, line_width=1, line_dash="dot", line_color="#64748b")
        fig.add_annotation(
            x=cur, y=1.04, yref="paper", text=f"{cur}'",
            showarrow=False, font=dict(size=10, color="#94a3b8"),
        )

    tick_vals = list(range(0, 91, 5))
    fig.update_layout(
        height=200,
        margin=dict(l=8, r=8, t=36, b=24),
        plot_bgcolor=PLOT_BG,
        paper_bgcolor=PLOT_BG,
        font=dict(color="#94a3b8", size=10),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02,
            xanchor="center", x=0.5,
            font=dict(size=10, color="#e2e8f0"),
            bgcolor="rgba(0,0,0,0)",
        ),
        xaxis=dict(
            range=[0, 90],
            tickvals=tick_vals,
            ticktext=[f"{t}'" for t in tick_vals],
            showgrid=False,
            zeroline=False,
            title="",
        ),
        yaxis=dict(visible=False, range=[-5, 115]),
        hovermode="x unified",
    )
    return fig


def render_similar_momentum_block(
    goal_events,
    match_ids: list,
    n_matches: int,
    home_team: str,
    away_team: str,
    *,
    chart_key: str,
    current_minute: int = 90,
    show_minute_marker: bool = False,
    subtitle: str | None = None,
) -> None:
    profile = build_similar_match_momentum(goal_events, match_ids)
    fig = similar_momentum_fig(
        profile, home_team, away_team,
        current_minute=current_minute,
        show_minute_marker=show_minute_marker,
    )
    if fig is None:
        return

    if subtitle is None:
        subtitle = (
            "Intensità attesa da gol storici nel campione filtrato"
            if not show_minute_marker
            else "Intensità attesa da gol storici · linea tratteggiata = minuto attuale"
        )

    st.markdown(
        f'<div style="font-size:11px;font-weight:700;color:{C_MUTED};letter-spacing:0.08em;'
        f'text-transform:uppercase;margin:4px 0 6px 0;">'
        f'📈 Profilo partita · {n_matches} partite nel campione</div>'
        f'<div style="font-size:10px;color:{C_MUTED2};margin-bottom:6px;">{subtitle}</div>',
        unsafe_allow_html=True,
    )
    st.plotly_chart(
        fig,
        use_container_width=True,
        config={"displayModeBar": False},
        key=chart_key,
    )

    insights = build_momentum_insights(profile, home_team, away_team)
    if insights:
        items = "".join(
            f'<li style="margin:4px 0;color:{C_MUTED};font-size:11px;line-height:1.5;">{txt}</li>'
            for txt in insights
        )
        st.markdown(
            f'<ul style="margin:8px 0 12px 0;padding-left:18px;list-style:none;">{items}</ul>',
            unsafe_allow_html=True,
        )
