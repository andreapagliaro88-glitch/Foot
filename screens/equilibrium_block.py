import streamlit as st


def render_equilibrium_block(home_pct, draw_pct, away_pct, total_matches):
    equilibrium_score = 100 - abs(home_pct - away_pct)
    delta = abs(home_pct - away_pct)

    if home_pct > away_pct:
        fav = "🏠 CASA"
        fav_color = "#3b82f6"
    elif away_pct > home_pct:
        fav = "✈️ TRASFERTA"
        fav_color = "#f97316"
    else:
        fav = "⚖️ EQUILIBRIO"
        fav_color = "#22c55e"

    if equilibrium_score >= 70:
        eq_label = "⚖️ MOLTO EQUILIBRATA"
        eq_color = "#22c55e"
    elif equilibrium_score >= 50:
        eq_label = "⚖️ EQUILIBRATA"
        eq_color = "#3b82f6"
    else:
        eq_label = "📉 SBILANCIATA"
        eq_color = "#ef4444"

    if total_matches >= 50:
        confidence = "ALTA"
    elif total_matches >= 20:
        confidence = "MEDIA"
    else:
        confidence = "BASSA"

    signal = ""
    if draw_pct < 25 and delta > 20:
        signal = "💡 Evita pareggio (bassa probabilità)"
    elif 45 <= equilibrium_score <= 65:
        signal = "⚡ Match ideale per trading live"
    elif delta > 30:
        signal = f"🔥 Forte vantaggio {fav}"

    glow = f"0 0 {10 + equilibrium_score / 5}px {eq_color}"

    st.html(f"""
    <div style="
        padding:16px;
        border-radius:12px;
        background:#111827;
        border:1px solid #1f2937;
        height:100%;
    ">
        <div style="
            font-size:34px;
            font-weight:800;
            color:{eq_color};
            text-align:center;
            text-shadow:{glow};
        ">
            {equilibrium_score:.0f}
        </div>
        <div style="text-align:center; font-size:11px; color:#64748b;">
            0 → sbilanciata • 100 → equilibrata
        </div>
        <div style="
            margin-top:10px;
            height:10px;
            background:#1f2937;
            border-radius:6px;
            overflow:hidden;
        ">
            <div style="
                width:{equilibrium_score}%;
                height:100%;
                background:{eq_color};
                box-shadow:{glow};
                transition:all 0.5s ease;
            "></div>
        </div>
        <div style="
            margin-top:10px;
            text-align:center;
            font-weight:700;
            color:{eq_color};
        ">
            {eq_label}
        </div>
        <div style="
            margin-top:8px;
            font-size:12px;
            color:#94a3b8;
            text-align:center;
        ">
            🏠 {home_pct:.1f}% • 🤝 {draw_pct:.1f}% • ✈️ {away_pct:.1f}%
        </div>
        <div style="
            margin-top:6px;
            font-size:12px;
            text-align:center;
            color:#94a3b8;
        ">
            📊 Squilibrio: <b>{delta:.1f}%</b> •
            <span style="color:{fav_color}; font-weight:700;">{fav}</span>
        </div>
        <div style="
            margin-top:6px;
            font-size:11px;
            text-align:center;
            color:#64748b;
        ">
            📦 Campione: {total_matches} partite • Affidabilità: {confidence}
        </div>
        <div style="
            margin-top:10px;
            font-size:13px;
            font-weight:700;
            text-align:center;
            color:#fbbf24;
        ">
            {signal}
        </div>
    </div>
    """)
