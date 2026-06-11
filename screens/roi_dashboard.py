import streamlit as st


def _badge(roi):
    if roi > 30:
        return '<span style="font-size:9px;color:#22c55e;margin-left:6px;">🔥 HOT</span>'
    if roi >= 0:
        return '<span style="font-size:9px;color:#f59e0b;margin-left:6px;">⚠️ OK</span>'
    return '<span style="font-size:9px;color:#ef4444;margin-left:6px;">❌ AVOID</span>'


def _format_profit(profit, roi):
    color = "#22c55e" if profit >= 0 else "#ef4444"
    glow = f"0 0 {10 + abs(roi) / 2}px {color}"
    return (
        f'<span style="color:{color}; font-weight:700; text-shadow:{glow}; white-space:nowrap;">'
        f"{profit:+.1f}u ({roi:+.1f}%)"
        f"</span>"
    )


def _format_odds(odds) -> str:
    if odds is None:
        return ""
    try:
        val = float(odds)
    except (TypeError, ValueError):
        return ""
    if val <= 0:
        return ""
    return (
        f'<span style="color:#64748b; font-size:11px; margin-left:6px; font-weight:600;">'
        f"@{val:.2f}</span>"
    )


def render_roi_dashboard(data):
    lay_over_results = []

    for row in data.get("over_under", []):
        odds = row["odds"]
        wins = row["wins"]
        losses = row["losses"]
        total = wins + losses
        profit = wins * 1 - losses * (odds - 1)
        roi = (profit / total) * 100 if total > 0 else 0.0
        lay_over_results.append({
            "name": f"Lay {row['name']}",
            "roi": round(roi, 1),
            "profit": round(profit, 1),
            "odds": odds,
        })

    all_markets = []
    for section in data.values():
        for row in section:
            all_markets.append({
                "name": row["name"],
                "roi": row["roi"],
                "profit": row["profit"],
                "odds": row.get("odds"),
            })
    all_markets += lay_over_results

    top_roi = sorted(all_markets, key=lambda x: x["roi"], reverse=True)[:5]
    best_pick = top_roi[0]["name"] if top_roi and top_roi[0]["roi"] > 0 else None

    total_profit = sum(m["profit"] for m in all_markets)
    avg_profit = total_profit / len(all_markets) if all_markets else 0.0
    worst_profit = min((m["profit"] for m in all_markets), default=0.0)
    total_color = "#22c55e" if total_profit >= 0 else "#ef4444"

    market_rows = ""
    for m in all_markets:
        market_rows += f"""
        <div style="display:flex; justify-content:space-between; align-items:center;
                    padding:8px; border-bottom:1px solid #1f2937;">
            <span style="color:#e2e8f0; font-size:13px;">
                {m['name']}{_format_odds(m.get('odds'))}{_badge(m['roi'])}
            </span>
            {_format_profit(m['profit'], m['roi'])}
        </div>
        """

    top_rows = ""
    for m in top_roi:
        top_rows += f"""
        <div style="display:flex; justify-content:space-between; align-items:center;
                    margin-top:8px; gap:8px;">
            <span style="color:#cbd5e1; font-size:12px;">
                {m['name']}{_format_odds(m.get('odds'))}
            </span>
            {_format_profit(m['profit'], m['roi'])}
        </div>
        """

    suggestion = ""
    if best_pick:
        best = top_roi[0]
        suggestion = f"""
        <div style="margin-top:12px; padding-top:10px; border-top:1px solid #1f2937;
                    font-size:11px; color:#94a3b8;">
            💡 Gioca: <span style="color:#22c55e; font-weight:700;">{best_pick}</span>
            {_format_odds(best.get('odds'))}
            <span style="color:#64748b;"> · {_format_profit(best['profit'], best['roi'])}</span>
        </div>
        """

    st.html(f"""
    <div class="pm-box" style="padding:16px;">
        <div style="display:flex; gap:20px; flex-wrap:wrap;">
            <div style="flex:3; min-width:280px;">
                <div style="font-size:14px; color:#94a3b8; margin-bottom:10px; font-weight:600;">
                    📊 ROI SIMULAZIONE
                </div>
                {market_rows}
                <div style="margin-top:12px; padding-top:10px; border-top:1px solid #334155;
                            display:flex; flex-wrap:wrap; gap:16px; font-size:12px;">
                    <span style="font-weight:700; color:{total_color};">
                        💰 Totale: {total_profit:+.1f} unità
                    </span>
                    <span style="color:#94a3b8;">
                        🎯 Media/bet: <span style="color:#cbd5e1; font-weight:600;">{avg_profit:+.1f}u</span>
                    </span>
                    <span style="color:#94a3b8;">
                        📉 Max loss: <span style="color:#ef4444; font-weight:600;">{worst_profit:+.1f}u</span>
                    </span>
                </div>
            </div>
            <div style="flex:1; min-width:200px; background:#111827; padding:12px; border-radius:8px;
                        border:1px solid #1f2937;">
                <div style="font-size:12px; color:#94a3b8; font-weight:700;">🔥 TOP ROI</div>
                {top_rows}
                {suggestion}
            </div>
        </div>
    </div>
    """)
