import streamlit as st


def render_goal_timing(avg_1t, avg_2t, home_1t, away_1t, home_2t, away_2t):
    diff = avg_2t - avg_1t

    if diff > 0.5:
        label = "📈 2° TEMPO DOMINANTE"
        color = "#22c55e"
    elif diff < -0.5:
        label = "📉 1° TEMPO DOMINANTE"
        color = "#3b82f6"
    else:
        label = "⚖️ EQUILIBRATO"
        color = "#f59e0b"

    st.html(f"""
    <div class="pm-box" style="background:#111827; padding:12px; border-radius:8px;">

        <div style="font-size:10px; color:#64748b; font-weight:700; text-transform:uppercase;
                    letter-spacing:0.8px; margin-bottom:8px;">MEDIA GOL PER TEMPO</div>

        <div style="font-weight:700; color:{color}; margin-bottom:8px; font-size:14px;">
            {label}
        </div>

        <div style="font-size:12px; color:#94a3b8;">
            Differenza: <b style="color:{color};">{diff:+.2f}</b> gol
        </div>

        <div style="margin-top:10px; font-size:13px; color:#e2e8f0;">
            1T: <b>{avg_1t}</b> &nbsp;·&nbsp; 2T: <b>{avg_2t}</b>
        </div>

        <div style="margin-top:8px; font-size:12px; color:#94a3b8; line-height:1.7;">
            🏠 Casa: <span style="color:#3b82f6;">{home_1t}</span> → <span style="color:#3b82f6;">{home_2t}</span><br>
            ✈️ Trasferta: <span style="color:#f97316;">{away_1t}</span> → <span style="color:#f97316;">{away_2t}</span>
        </div>

    </div>
    """)
