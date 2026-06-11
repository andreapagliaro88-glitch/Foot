"""
screens/strategy_simulator.py — Strategy Simulator UI
"""

import streamlit as st
import pandas as pd
import io
import datetime
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database import get_all_matches
from filters import (
    render_filter_sidebar,
    apply_filters,
    should_run_analysis,
    _sidebar_label,
    _sidebar_divider,
)
from calculations import LAY_00_MIN_ODDS
from strategy_simulator import (
    STRATEGY_NAMES,
    LIVE_STRATEGY_NAMES,
    calculate_risk_metrics,
    find_best_strategy,
    get_strategy_config,
    run_simulation,
)

_ADVANCED_STRATEGIES = set(LIVE_STRATEGY_NAMES)

C_BG = "#111827"
C_BORDER = "#1f2937"
C_TEXT = "#f1f5f9"
C_MUTED = "#94a3b8"
C_GREEN = "#22c55e"
C_RED = "#ef4444"
C_YELLOW = "#f59e0b"


def _inject_styles():
    st.html(f"""
    <style>
        .ss-card {{
            background:{C_BG}; border:1px solid {C_BORDER}; border-radius:8px;
            padding:16px; text-align:center; height:100%;
        }}
        .ss-label {{
            font-size:11px; color:{C_MUTED}; text-transform:uppercase;
            letter-spacing:1px; margin-bottom:8px;
        }}
        .ss-val {{
            font-size:28px; font-weight:700; color:{C_TEXT};
        }}
        .ss-sub {{
            font-size:12px; color:{C_MUTED}; margin-top:6px; line-height:1.4;
        }}
        .ss-badge {{
            font-size:11px; font-weight:600; margin-top:8px;
            letter-spacing:0.5px;
        }}
        .ss-box {{
            background:{C_BG}; border:1px solid {C_BORDER};
            border-radius:8px; padding:16px; margin-bottom:16px;
        }}
    </style>
    """)


def _metric_card(label: str, value: str, color: str = C_TEXT):
    return (
        f'<div class="ss-card">'
        f'<div class="ss-label">{label}</div>'
        f'<div class="ss-val" style="color:{color};">{value}</div>'
        f'</div>'
    )


def _risk_card(
    label: str,
    value: str,
    *,
    value_color: str = C_TEXT,
    subs: list[tuple[str, str]] | None = None,
    badge: str | None = None,
    badge_color: str = C_MUTED,
) -> str:
    subs_html = "".join(
        f'<div class="ss-sub" style="color:{color};">{text}</div>'
        for text, color in (subs or [])
    )
    badge_html = (
        f'<div class="ss-badge" style="color:{badge_color};">{badge}</div>'
        if badge else ""
    )
    return (
        f'<div class="ss-card">'
        f'<div class="ss-label">{label}</div>'
        f'<div class="ss-val" style="color:{value_color};">{value}</div>'
        f'{subs_html}{badge_html}'
        f'</div>'
    )


def _render_risk_panel(sim: dict, bankroll_start: float, stake: float) -> None:
    risk = calculate_risk_metrics(sim, bankroll_start, stake)

    dd_colors = {"ALTO": C_RED, "MEDIO": C_YELLOW, "BASSO": C_GREEN}
    dd_badges = {
        "ALTO": ("🔥 RISCHIO ALTO", C_RED),
        "MEDIO": ("⚠️ RISCHIO MEDIO", C_YELLOW),
        "BASSO": ("✅ RISCHIO BASSO", C_GREEN),
    }
    dd_badge, dd_badge_color = dd_badges[risk["dd_risk_level"]]

    score_colors = {"Alto": C_RED, "Moderato": C_YELLOW, "Basso": C_GREEN}
    score_emojis = {"Alto": "🔴", "Moderato": "🟡", "Basso": "🟢"}
    stab_emojis = {"Alta": "🟢", "Media": "🟡", "Bassa": "🔴"}
    stab_colors = {"Alta": C_GREEN, "Media": C_YELLOW, "Bassa": C_RED}

    streak_color = C_RED if risk["losing_streak"] >= 7 else (C_YELLOW if risk["losing_streak"] >= 3 else C_TEXT)
    streak_badge = "⚠️ Critico sopra 7" if risk["losing_streak"] >= 7 else "⚠️ Critico sopra 7"
    streak_badge_color = C_RED if risk["losing_streak"] >= 7 else C_MUTED

    ev_color = C_GREEN if risk["ev_profitable"] else C_RED
    ev_badge = "🟢 Profittevole" if risk["ev_profitable"] else "🔴 Non profittevole"

    st.markdown("### ⚠️ Risk panel")
    r1, r2, r3, r4 = st.columns(4)
    with r1:
        st.html(_risk_card(
            "Max Drawdown",
            f"{risk['max_drawdown']:.0f}€  (-{risk['drawdown_pct']:.0f}%)",
            value_color=dd_colors[risk["dd_risk_level"]],
            badge=dd_badge,
            badge_color=dd_badge_color,
        ))
    with r2:
        st.html(_risk_card(
            "Losing Streak",
            str(risk["losing_streak"]),
            value_color=streak_color,
            subs=[(f"💸 Perdita potenziale: -{risk['loss_impact']:.0f}€", C_MUTED)],
            badge=streak_badge,
            badge_color=streak_badge_color,
        ))
    with r3:
        st.html(_risk_card(
            "Win Rate",
            f"{risk['strike_rate']:.0f}%",
            value_color=C_TEXT,
            subs=[(f"{risk['wins']}W / {risk['losses']}L", C_MUTED)],
        ))
    with r4:
        st.html(_risk_card(
            "Risk Score",
            f"{risk['risk_score']} / 100",
            value_color=score_colors[risk["risk_score_label"]],
            badge=f"{score_emojis[risk['risk_score_label']]} {risk['risk_score_label']}",
            badge_color=score_colors[risk["risk_score_label"]],
        ))

    r5, r6 = st.columns(2)
    with r5:
        st.html(_risk_card(
            "Expected Value",
            f"{risk['expected_value']:+.2f} per bet",
            value_color=ev_color,
            badge=ev_badge,
            badge_color=ev_color,
        ))
    with r6:
        st.html(_risk_card(
            "Stabilità bankroll",
            risk["stability"],
            value_color=stab_colors[risk["stability"]],
            subs=[(f"Volatilità: {risk['volatility']:.2f}", C_MUTED)],
            badge=f"{stab_emojis[risk['stability']]} Volatilità {risk['stability'].lower()}",
            badge_color=stab_colors[risk["stability"]],
        ))


def _build_bets_export_df(
    sim: dict,
    strategy_name: str,
    source_df: pd.DataFrame | None,
) -> pd.DataFrame:
    """Ricostruisce le bet con tutte le colonne del campione filtrato."""
    details = sim.get("bet_details", [])
    if not details:
        return pd.DataFrame()

    sim_df = pd.DataFrame(details)
    sim_cols = [c for c in ("stake", "odds_used", "result", "bankroll") if c in sim_df.columns]

    if source_df is not None and not source_df.empty:
        source = source_df.copy()

        if "_row_index" in sim_df.columns:
            try:
                rows = source.loc[sim_df["_row_index"].tolist()].copy()
                rows = rows.reset_index(drop=True)
                for col in sim_cols:
                    rows[col] = sim_df[col].values
                rows.insert(0, "strategia", strategy_name)
                tail = [c for c in sim_cols if c in rows.columns]
                body = [c for c in rows.columns if c not in {"strategia", *tail}]
                return rows[["strategia", *body, *tail]]
            except KeyError:
                pass

        merge_keys = (
            ["match_id"]
            if "match_id" in sim_df.columns and "match_id" in source.columns
            else ["home_team", "away_team", "match_date"]
        )
        if all(k in sim_df.columns for k in merge_keys):
            source = source.drop_duplicates(subset=merge_keys, keep="first")
            sim_part = sim_df[merge_keys + sim_cols].copy()
            merged = sim_part.merge(source, on=merge_keys, how="left")
            merged.insert(0, "strategia", strategy_name)
            tail = [c for c in sim_cols if c in merged.columns]
            body = [c for c in merged.columns if c not in {"strategia", *tail}]
            return merged[["strategia", *body, *tail]]

    bets = sim_df.copy()
    drop_cols = [c for c in ("_row_index",) if c in bets.columns]
    if drop_cols:
        bets = bets.drop(columns=drop_cols)
    bets.insert(0, "strategia", strategy_name)
    tail = [c for c in sim_cols if c in bets.columns]
    body = [c for c in bets.columns if c not in {"strategia", *tail}]
    return bets[["strategia", *body, *tail]]


def _export_simulation_excel(
    sim: dict,
    strategy_name: str,
    stake: float,
    bankroll_start: float,
    source_df: pd.DataFrame | None = None,
) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
        summary = pd.DataFrame([{
            "Strategia": strategy_name,
            "Bankroll iniziale": bankroll_start,
            "Stake iniziale": stake,
            "Stake % bankroll": sim.get("stake_ratio_pct"),
            "Profit": sim.get("profit"),
            "ROI %": sim.get("roi"),
            "Bankroll finale": sim.get("bankroll_end"),
            "Bet totali": sim.get("total_bets"),
            "Vittorie": sim.get("wins"),
            "Perdite": sim.get("losses"),
            "Strike rate %": sim.get("strike_rate"),
            "Bet saltate": sim.get("skipped_bets", 0),
            "Interesse composto": "Sì",
        }])
        summary.to_excel(writer, sheet_name="Riepilogo", index=False)

        bets = _build_bets_export_df(sim, strategy_name, source_df)
        if not bets.empty:
            bets.to_excel(writer, sheet_name="Bet", index=False)

        history = pd.DataFrame({
            "Step": range(len(sim.get("history", []))),
            "Bankroll": sim.get("history", []),
        })
        history.to_excel(writer, sheet_name="Bankroll", index=False)

    return buf.getvalue()


def _cache_simulation(
    sim: dict,
    strategy_name: str,
    config: dict,
    stake: float,
    bankroll_start: float,
    filtered_count: int,
    filtered_df: pd.DataFrame,
) -> None:
    st.session_state["sim_cached"] = {
        "sim": sim,
        "strategy_name": strategy_name,
        "config": config,
        "stake": stake,
        "bankroll_start": bankroll_start,
        "filtered_count": filtered_count,
        "filtered_df": filtered_df.copy(),
    }


def render():
    _inject_styles()

    filters = render_filter_sidebar("simulator")
    _sidebar_divider()
    _sidebar_label("🎯 Simulazione")
    _legacy_strategy = {
        "BTTS": "BTTS Yes",
        "Lay Draw": "Lay Pareggio",
        "Over 0.5 2T": "Over 0.5 Secondo Tempo",
    }
    if st.session_state.get("sim_strategy") in _legacy_strategy:
        st.session_state["sim_strategy"] = _legacy_strategy[st.session_state["sim_strategy"]]
    if st.session_state.get("sim_strategy") not in STRATEGY_NAMES:
        st.session_state["sim_strategy"] = STRATEGY_NAMES[0]
    if st.session_state.get("sim_strategy") in ("Timeframe Snipe Engine", "Advanced Under Trading"):
        st.session_state["sim_strategy"] = STRATEGY_NAMES[0]

    def _strategy_label(name: str) -> str:
        if name in _ADVANCED_STRATEGIES:
            return f"🔥 {name}"
        return name

    _sidebar_label("📈 Strategia")
    strategy_name = st.sidebar.selectbox(
        "Strategia",
        list(STRATEGY_NAMES),
        format_func=_strategy_label,
        key="sim_strategy",
        label_visibility="collapsed",
    )
    st.sidebar.caption(
        f"{len(STRATEGY_NAMES)} strategie · live: "
        + ", ".join(LIVE_STRATEGY_NAMES)
    )
    _sidebar_label("💰 Bankroll")
    bankroll_start = st.sidebar.number_input(
        "Bankroll iniziale (€)", min_value=10.0, value=1000.0, step=50.0, key="sim_bankroll",
        label_visibility="collapsed",
    )
    stake = st.sidebar.number_input(
        "Stake iniziale (€)",
        min_value=1.0,
        value=10.0,
        step=1.0,
        key="sim_stake",
        label_visibility="collapsed",
        help="Interesse composto: ogni bet usa la stessa % del bankroll corrente "
             "(es. 10€ su 1000€ = 1% reinvestito ad ogni scommessa).",
    )
    _sidebar_divider()
    run_sim = st.sidebar.button("🚀 Avvia simulazione", key="sim_run_btn", use_container_width=True)
    auto_find = st.sidebar.button("🔥 Trova migliore strategia", key="sim_auto_btn", use_container_width=True)

    st.html(f"""
    <div style="padding:12px 0;">
        <h1 style="color:{C_TEXT}; margin:0;">🧮 STRATEGY SIMULATOR</h1>
        <p style="color:{C_MUTED}; margin:6px 0 0;">Testa strategie su dati reali — calcolo sempre con <b>interesse composto</b></p>
    </div>
    """)

    if not should_run_analysis(filters) and not run_sim and not auto_find:
        st.info("👈 Imposta i filtri nella sidebar e clicca **ANALIZZA** o **Avvia simulazione**.")
        return

    rows = get_all_matches()
    if not rows:
        st.warning("⚠️ Nessun dato nel database. Carica partite da **UPLOAD DATI**.")
        return

    df = pd.DataFrame(rows)
    filtered = apply_filters(df, filters)
    if filtered.empty:
        st.warning("🔍 Nessuna partita con i filtri selezionati.")
        return

    stake_pct = round(stake / bankroll_start * 100, 2) if bankroll_start else 0
    st.caption(
        f"**{len(filtered)}** partite nel campione · "
        f"Stake composto: **{stake_pct}%** del bankroll corrente "
        f"(partenza {stake:.0f}€ su {bankroll_start:.0f}€)"
    )
    if strategy_name == "Lay 0-0":
        from calculations import estimate_lay_00_odds
        est = estimate_lay_00_odds(filtered)
        st.caption(
            f"Lay 0-0: quota stimata **@{est:.2f}** "
            f"(da freq. 0-0 nel campione, minimo **{LAY_00_MIN_ODDS:.0f}**)"
        )
    if strategy_name == "Advanced Overs Trading":
        st.caption(
            "🔥 **Advanced Overs Trading** — split staking @2.5/@3.5/@4.5/@5.5 dopo 1 gol a HT. "
            "Gestione post-gol, loss cut -60%, fase 3 su match acceso."
        )
    if auto_find:
        ranking = find_best_strategy(filtered, stake=stake, bankroll_start=bankroll_start)
        if ranking.empty:
            st.warning("Nessun risultato: verifica che le partite abbiano quote e risultati.")
            return
        st.session_state["sim_ranking_cached"] = ranking
        strategy_name = ranking.iloc[0]["strategy"]
    elif run_sim:
        st.session_state.pop("sim_ranking_cached", None)

    if st.session_state.get("sim_ranking_cached") is not None:
        ranking = st.session_state["sim_ranking_cached"]
        st.markdown("### 🔥 Confronto strategie")
        best = ranking.iloc[0]
        st.success(
            f"Migliore: **{best['strategy']}** — ROI **{best['roi']}%**, "
            f"profit **{best['profit']:.2f}€** su **{int(best['total_bets'])}** bet."
        )
        st.dataframe(
            ranking.style.format({
                "roi": "{:.2f}%",
                "profit": "{:.2f}",
                "strike_rate": "{:.1f}%",
                "max_drawdown": "{:.2f}",
            }),
            use_container_width=True,
            hide_index=True,
        )

    sim_triggered = run_sim or auto_find
    cached = st.session_state.get("sim_cached")

    if sim_triggered:
        config = get_strategy_config(strategy_name)
        if not config:
            st.error("Strategia non valida.")
            return
        with st.spinner("Simulazione in corso..."):
            sim = run_simulation(filtered, config, stake=stake, bankroll_start=bankroll_start)
        _cache_simulation(sim, strategy_name, config, stake, bankroll_start, len(filtered), filtered)
    elif cached:
        sim = cached["sim"]
        strategy_name = cached["strategy_name"]
        config = cached["config"]
    else:
        st.info("Clicca **🚀 Avvia simulazione** o **🔥 Trova migliore strategia** nella sidebar.")
        return

    if strategy_name == "Lay 0-0" and sim.get("lay_00_odds"):
        st.caption(f"Quota Lay 0-0 usata nella simulazione: **@{sim['lay_00_odds']:.2f}**")

    if sim["total_bets"] == 0:
        extra = ""
        if strategy_name == "Advanced Overs Trading":
            extra = (
                " Servono timing gol, 1 gol a fine 1T, quote Over 2.5 "
                "e almeno un ordine split matchato nel backtest."
            )
        elif config.get("odds_column"):
            extra = f" Servono partite con risultato finale e quote (`{config['odds_column']}`)."
        st.warning(f"Nessuna bet simulata per **{strategy_name}**.{extra}")
        return

    profit_color = C_GREEN if sim["profit"] >= 0 else C_RED
    roi_color = C_GREEN if sim["roi"] >= 0 else C_RED

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.html(_metric_card("Profit", f"{sim['profit']:+.2f}€", profit_color))
    with c2:
        st.html(_metric_card("ROI", f"{sim['roi']:+.2f}%", roi_color))
    with c3:
        st.html(_metric_card("Strike Rate", f"{sim['strike_rate']}%"))
    with c4:
        st.html(_metric_card("Bets", str(sim["total_bets"])))
    with c5:
        st.html(_metric_card("Bankroll finale", f"{sim['bankroll_end']:.2f}€"))

    st.markdown("### 📈 Andamento bankroll")
    chart_df = pd.DataFrame({"Bankroll": sim["history"]})
    st.line_chart(chart_df, height=280)

    sim_meta = st.session_state.get("sim_cached", {})
    _render_risk_panel(
        sim,
        sim_meta.get("bankroll_start", bankroll_start),
        sim_meta.get("stake", stake),
    )

    if sim.get("skipped_bets", 0) > 0:
        st.caption(f"⏭️ {sim['skipped_bets']} bet saltate (bankroll insufficiente o lay non coperto).")

    with st.expander("📋 Dettaglio bet"):
        details = pd.DataFrame(sim.get("bet_details", []))
        if details.empty:
            st.info("Nessuna bet simulata.")
        else:
            total = len(details)

            def _bet_limit_label(n: int) -> str:
                return f"Tutte ({total})" if n == 0 else str(n)

            limit = st.radio(
                "Quante bet visualizzare",
                options=[10, 25, 50, 100, 0],
                format_func=_bet_limit_label,
                horizontal=True,
                key="sim_bet_rows_limit",
            )
            if limit == 0:
                show = details.copy()
                st.caption(f"Tutte le **{total}** bet simulate.")
            else:
                show = details.tail(min(limit, total)).copy()
                st.caption(f"Ultime **{len(show)}** di **{total}** bet simulate.")

            display_cols = [
                c for c in [
                    "match_date", "league", "season", "home_team", "away_team",
                    "stake", "result", "bankroll",
                ] if c in show.columns
            ]
            view = show[display_cols] if display_cols else show
            if "stake" in view.columns:
                view["stake"] = view["stake"].map(lambda x: f"{x:.2f}")
            if "bankroll" in view.columns:
                view["bankroll"] = view["bankroll"].map(lambda x: f"{x:.2f}")
            view["result"] = view["result"].map(lambda x: f"{x:+.2f}")
            st.dataframe(view, use_container_width=True, hide_index=True)

            sim_meta = st.session_state.get("sim_cached", {})
            export_source = sim_meta.get("filtered_df", filtered)
            export_buf = _export_simulation_excel(
                sim,
                strategy_name,
                sim_meta.get("stake", stake),
                sim_meta.get("bankroll_start", bankroll_start),
                source_df=export_source,
            )
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M")
            safe_name = strategy_name.replace(" ", "_").replace(".", "")
            st.download_button(
                label="📥 Esporta tutte le bet in Excel",
                data=export_buf,
                file_name=f"simulator_{safe_name}_{ts}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="sim_export_bets_btn",
                use_container_width=True,
            )
