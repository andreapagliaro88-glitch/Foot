import streamlit as st
import pandas as pd


def build_first_goal_data(
    home_mins, away_mins, intervals, dist_bands, window_minute,
    n_matches, max_minute,
):
    """
    dist_bands: list of (label, [interval_keys...]) e.g. ("0–15", ["0-15"])
    """
    all_mins = home_mins + away_mins
    median_val = int(round(pd.Series(all_mins).median())) if all_mins else 0

    window_pct = round(
        sum(1 for m in all_mins if m <= window_minute) / n_matches * 100, 1
    ) if n_matches > 0 else 0.0

    median_h = float(pd.Series(home_mins).median()) if home_mins else 0.0
    median_a = float(pd.Series(away_mins).median()) if away_mins else 0.0
    if median_h < median_a - 1:
        first_team = "Casa prima"
    elif median_a < median_h - 1:
        first_team = "Trasferta prima"
    else:
        first_team = "Equilibrato"

    counts = []
    for _label, keys in dist_bands:
        counts.append(sum(intervals[k][0] + intervals[k][1] for k in keys))
    band_total = sum(counts)

    distribution = {}
    for (label, _keys), cnt in zip(dist_bands, counts):
        distribution[label] = round(cnt / band_total * 100, 1) if band_total else 0.0

    early_pct = list(distribution.values())[0] if distribution else 0.0
    if early_pct > 40:
        signal = "GOL PRECOCE PROBABILE"
    elif early_pct < 25:
        signal = "GOL TARDIVO"
    else:
        signal = "RITMO MEDIO"

    timeline_pct = min(max(median_val / max_minute * 100, 0), 100) if max_minute > 0 else 0

    return {
        "median": median_val,
        "early30": window_pct,
        "first_team": first_team,
        "distribution": distribution,
        "signal": signal,
        "timeline_pct": timeline_pct,
        "max_minute": max_minute,
    }


def render_first_goal_chart(data, title, color, border_color="#1f2937",
                            total_fg=0, none_count=0, pct_with=0.0, pct_without=0.0):
    bars_html = ""
    max_val = max(data["distribution"].values()) if data["distribution"] else 1
    window_label = 30 if data.get("max_minute", 45) <= 45 else 60

    for label, val in data["distribution"].items():
        intensity = val / max_val if max_val > 0 else 0
        glow = f"0 0 {6 + intensity * 14}px {color}"
        bar_width = max(val, 2) if val > 0 else 0
        bars_html += f"""
        <div style="margin-bottom:8px;">
            <div style="display:flex; justify-content:space-between; font-size:12px; color:#cbd5e1;">
                <span>{label}</span>
                <span style="font-weight:600;">{val}%</span>
            </div>
            <div style="height:8px; background:#1f2937; border-radius:6px; overflow:hidden;">
                <div style="width:{bar_width}%; height:100%; background:{color};
                            box-shadow:{glow}; transition:width 0.4s ease;"></div>
            </div>
        </div>
        """

    timeline_pct = data.get("timeline_pct", 0)
    max_min = data.get("max_minute", 45)
    median = data.get("median", 0)

    st.html(f"""
    <div class="pm-box" style="padding:14px; border-color:{border_color}; height:100%;">
        <div style="color:{color}; font-size:11px; font-weight:700; text-transform:uppercase;
                    letter-spacing:1px; margin-bottom:12px;">{title}</div>

        <div style="display:flex; justify-content:space-around; margin-bottom:14px;
                    padding:10px; background:#111827; border-radius:8px; font-size:13px; color:#e2e8f0;">
            <div style="text-align:center;">⏱️ <b style="color:{color}; font-size:18px;">{data['median']}'</b></div>
            <div style="text-align:center;">⚡ <b style="color:{color};">{data['early30']}%</b><br>
                <span style="font-size:9px; color:#64748b;">entro {window_label}'</span>
            </div>
            <div style="text-align:center;">🏠 <b style="color:{color};">{data['first_team']}</b></div>
        </div>

        <div style="margin-bottom:14px; padding:0 4px;">
            <div style="position:relative; height:4px; background:#1f2937; border-radius:4px;">
                <div style="position:absolute; left:{timeline_pct}%; top:50%; transform:translate(-50%,-50%);
                            width:10px; height:10px; background:{color}; border-radius:50%;
                            box-shadow:0 0 10px {color};"></div>
            </div>
            <div style="display:flex; justify-content:space-between; font-size:9px; color:#64748b; margin-top:4px;">
                <span>0</span><span style="color:{color}; font-weight:700;">{median}'</span><span>{max_min}</span>
            </div>
        </div>

        {bars_html}

        <div style="margin-top:12px; font-weight:700; color:{color}; font-size:13px;
                    text-shadow:0 0 10px {color}80;">
            ⚡ {data['signal']}
        </div>

        <div style="margin-top:10px; padding-top:8px; border-top:1px solid #1f2937;
                    display:flex; justify-content:space-between; font-size:11px; color:#64748b;">
            <span>Con gol: <b style="color:{color};">{total_fg}</b> ({pct_with}%)</span>
            <span>Senza: <b>{none_count}</b> ({pct_without}%)</span>
        </div>
    </div>
    """)
