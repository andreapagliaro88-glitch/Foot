import streamlit as st
import time


def render_goal_comparison(pct_1T, pct_2T):
    if pct_2T > pct_1T:
        winner_text = "SECONDO TEMPO PIÙ ATTIVO"
        winner_color = "#22c55e"
    else:
        winner_text = "PRIMO TEMPO PIÙ ATTIVO"
        winner_color = "#3b82f6"

    col1, col2 = st.columns(2)
    with col1:
        progress_1 = st.empty()
    with col2:
        progress_2 = st.empty()

    for i in range(0, 101, 5):
        val1 = min(i, int(pct_1T))
        val2 = min(i, int(pct_2T))

        progress_1.html(f"""
        <div style="text-align:center;">
            <div style="font-size:12px;color:#cbd5e1;">1° TEMPO</div>
            <div style="
                width:120px;height:120px;
                border-radius:50%;
                background:conic-gradient(#3b82f6 {val1*3.6}deg, #1f2937 0deg);
                display:flex;align-items:center;justify-content:center;
                margin:auto;
                box-shadow:0 0 {val1/5}px #3b82f6;
            ">
                <div style="background:#111827;border-radius:50%;width:85px;height:85px;
                            display:flex;align-items:center;justify-content:center;
                            color:#3b82f6;font-size:22px;font-weight:800;">
                    {val1}%
                </div>
            </div>
        </div>
        """)

        progress_2.html(f"""
        <div style="text-align:center;">
            <div style="font-size:12px;color:#cbd5e1;">2° TEMPO</div>
            <div style="
                width:120px;height:120px;
                border-radius:50%;
                background:conic-gradient(#22c55e {val2*3.6}deg, #1f2937 0deg);
                display:flex;align-items:center;justify-content:center;
                margin:auto;
                box-shadow:0 0 {val2/5}px #22c55e;
            ">
                <div style="background:#111827;border-radius:50%;width:85px;height:85px;
                            display:flex;align-items:center;justify-content:center;
                            color:#22c55e;font-size:22px;font-weight:800;">
                    {val2}%
                </div>
            </div>
        </div>
        """)

        time.sleep(0.02)

    st.html(f"""
    <div class="pm-box" style="padding:12px 8px; margin-top:8px;">
        <div style="display:flex;justify-content:space-between;font-size:12px;color:#cbd5e1;">
            <span>1T</span><span>2T</span>
        </div>
        <div style="background:#1f2937;height:10px;border-radius:6px;overflow:hidden;">
            <div style="
                width:{pct_2T}%;
                background:#22c55e;
                height:100%;
                box-shadow:0 0 10px #22c55e;
            "></div>
        </div>
        <div style="
            text-align:center;
            margin-top:15px;
            font-size:14px;
            font-weight:700;
            color:{winner_color};
            text-shadow:0 0 10px {winner_color};
        ">
            ⚡ {winner_text}
        </div>
    </div>
    """)
