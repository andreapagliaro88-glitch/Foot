"""
ui_theme.py — Colori e CSS condivisi per contrasto leggibile (tema scuro).
"""

# Testo su sfondo #0f172a / #111827
C_BG = "#111827"
C_BORDER = "#1f2937"
C_TEXT = "#f1f5f9"
C_MUTED = "#cbd5e1"       # etichette, testo secondario
C_MUTED2 = "#94a3b8"      # hint, meta
C_LABEL = "#e2e8f0"       # label piccole maiuscole
C_HIGH = "#f8fafc"        # numeri / enfasi

# Stili inline riutilizzabili
STYLE_LABEL = (
    "font-size:11px;color:#e2e8f0;font-weight:700;"
    "text-transform:uppercase;letter-spacing:0.05em;"
)
STYLE_META = "font-size:12px;color:#f1f5f9;font-weight:500;"
STYLE_BODY = "font-size:14px;color:#f1f5f9;line-height:1.6;font-weight:500;"
STYLE_COUNT = "color:#f8fafc;font-weight:800;"

GLOBAL_READABILITY_CSS = """
/* ── Testo principale Streamlit ───────────────────────────── */
section[data-testid="stMain"] .stMarkdown p,
section[data-testid="stMain"] .stMarkdown li,
section[data-testid="stMain"] .stMarkdown span {
    color: #e2e8f0;
}
section[data-testid="stMain"] h1 { color: #f8fafc !important; }
section[data-testid="stMain"] h2,
section[data-testid="stMain"] h3 { color: #e2e8f0 !important; }

/* Caption e label */
[data-testid="stCaptionContainer"],
.stCaption,
section[data-testid="stMain"] .stCaption {
    color: #cbd5e1 !important;
    font-size: 0.85rem !important;
}
label,
.stWidgetLabel p,
[data-testid="stWidgetLabel"] {
    color: #e2e8f0 !important;
}

/* Alert / info */
.stAlert p,
.stAlert span,
[data-testid="stNotificationContent"] {
    color: #e2e8f0 !important;
}

/* Metriche */
[data-testid="stMetricLabel"] {
    color: #cbd5e1 !important;
    font-size: 0.85rem !important;
}
[data-testid="stMetricValue"] {
    color: #f8fafc !important;
}

/* Sidebar */
[data-testid="stSidebar"] .stMarkdown,
[data-testid="stSidebar"] .stMarkdown p {
    color: #cbd5e1 !important;
}
[data-testid="stSidebar"] .stCaption {
    color: #94a3b8 !important;
    font-size: 0.8rem !important;
}
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] .stWidgetLabel p {
    color: #cbd5e1 !important;
}

/* Tab */
.stTabs [data-baseweb="tab"] {
    color: #cbd5e1 !important;
    font-weight: 600 !important;
}
.stTabs [aria-selected="true"] {
    color: #ffffff !important;
}

/* Classi dashboard condivise */
.pm-label {
    font-size: 11px !important;
    color: #e2e8f0 !important;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-weight: 700;
}
.pm-sub {
    font-size: 12px !important;
    color: #cbd5e1 !important;
    margin-top: 4px;
}
.pm-box {
    color: #e2e8f0;
}
.pm-score-table th {
    color: #cbd5e1 !important;
    font-size: 12px !important;
    font-weight: 600;
}
"""
