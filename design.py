"""
design.py — SkillPulse Design System v2
  bg: #0A0A0A  accent: #5E6AD2  text: #FFFFFF
  Font: Inter (Google Fonts)
  Icons: Phosphor Icons (CDN)
"""
import streamlit as st

# ─────────────────────────────────────────────────────────────────────────────
# Renk sabitleri
# ─────────────────────────────────────────────────────────────────────────────
C = {
    "bg":      "#080B14",
    "bg1":     "#0D1117",
    "bg2":     "#141820",
    "bg3":     "#1A1E2A",
    "border":  "#1E2330",
    "border2": "#2A3040",
    "accent":  "#5E6AD2",
    "accent2": "#818CF8",
    "text1":   "#FFFFFF",
    "text2":   "#9CA3AF",
    "text3":   "#6B7280",
    "success": "#4ADE80",
    "warning": "#FBBF24",
    "danger":  "#F87171",
}

# ─────────────────────────────────────────────────────────────────────────────
# Plotly
# ─────────────────────────────────────────────────────────────────────────────
BAR_COLOR      = "#5E6AD2"
BAR_RISE_COLOR = "#4ADE80"
BAR_FALL_COLOR = "#F87171"
LINE_COLORS    = ["#5E6AD2", "#818CF8", "#4ADE80", "#FBBF24", "#F87171", "#A78BFA"]

PLOTLY_LAYOUT = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter, sans-serif", color="#8B8B8B", size=11),
    colorway=LINE_COLORS,
    margin=dict(l=0, r=0, t=32, b=0),
    showlegend=True,
    legend=dict(
        bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter", size=11, color="#8B8B8B"),
        borderwidth=0,
    ),
    hoverlabel=dict(
        bgcolor="#141414",
        bordercolor="#5E6AD2",
        font=dict(family="Inter, sans-serif", size=13, color="#FFFFFF"),
        namelength=-1,
    ),
    xaxis=dict(
        gridcolor="#1A1A1A",
        linecolor="#1E1E1E",
        zerolinecolor="#1E1E1E",
        tickfont=dict(family="JetBrains Mono", size=10, color="#4A4A4A"),
        title_font=dict(family="Inter", size=11, color="#8B8B8B"),
    ),
    yaxis=dict(
        gridcolor="#1A1A1A",
        linecolor="#1E1E1E",
        zerolinecolor="#1E1E1E",
        tickfont=dict(family="JetBrains Mono", size=10, color="#4A4A4A"),
        title_font=dict(family="Inter", size=11, color="#8B8B8B"),
    ),
)


def apply_chart_theme(fig, height: int = 380, show_legend: bool = True):
    layout = dict(PLOTLY_LAYOUT)
    layout["height"] = height
    layout["showlegend"] = show_legend
    fig.update_layout(**layout)
    try:
        fig.update_traces(
            marker_line_width=0,
            marker_cornerradius=4,
        )
    except Exception:
        pass
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# Global CSS
# ─────────────────────────────────────────────────────────────────────────────
GLOBAL_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;700&display=swap');

*, *::before, *::after { box-sizing: border-box; }

:root {
  --bg:      #080B14;
  --bg1:     #0D1117;
  --bg2:     #141820;
  --bg3:     #1A1E2A;
  --border:  #1E2330;
  --border2: #2A3040;
  --accent:  #5E6AD2;
  --accent2: #818CF8;
  --t1:      #FFFFFF;
  --t2:      #9CA3AF;
  --t3:      #6B7280;
  --ok:      #4ADE80;
  --warn:    #FBBF24;
  --err:     #F87171;
  --r:       8px;
  --sans:    'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  --mono:    'JetBrains Mono', 'Fira Code', monospace;
}

/* ── Animations ── */
@keyframes count-up {
  from { opacity: 0; transform: translateY(6px); }
  to   { opacity: 1; transform: translateY(0); }
}
@keyframes tab-slide {
  from { transform: scaleX(0); }
  to   { transform: scaleX(1); }
}
@keyframes pulse-glow {
  0%, 100% { box-shadow: 0 0 0 0 rgba(94,106,210,0); }
  50%       { box-shadow: 0 0 14px 2px rgba(94,106,210,0.18); }
}
@keyframes loading-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}


/* ── Hide Streamlit chrome ── */
#MainMenu, footer, header,
[data-testid="stDecoration"],
[data-testid="stToolbar"],
[data-testid="stStatusWidget"],
[data-testid="stSidebarNav"] { display: none !important; }

/* ── Custom tab bar (Rakip Zekası) ── */
.rz-tab-row { display:flex; gap:6px; margin-bottom:20px; }
.rz-tab-btn > button {
  background: transparent !important;
  border: 1px solid #1E1E1E !important;
  border-radius: 6px !important;
  color: #4A4A4A !important;
  font-family: var(--sans) !important;
  font-size: 0.78rem !important;
  font-weight: 500 !important;
  width: 100% !important;
  transition: border-color 0.15s, color 0.15s !important;
}
.rz-tab-btn > button:hover {
  border-color: rgba(94,106,210,0.4) !important;
  color: #FFFFFF !important;
  background: rgba(94,106,210,0.06) !important;
}
.rz-tab-active > button {
  background: #5E6AD2 !important;
  border-color: #5E6AD2 !important;
  color: #FFFFFF !important;
  font-weight: 600 !important;
}
.rz-tab-active > button:hover {
  background: #818CF8 !important;
  border-color: #818CF8 !important;
}

/* ── Sidebar içindeki kapat butonunu gizle ── */
[data-testid="stSidebar"] button[data-testid="baseButton-headerNoPadding"],
[data-testid="stSidebar"] [data-testid="SidebarCollapseButton"],
[data-testid="stSidebar"] [data-testid="collapsedControl"] { display: none !important; }

/* ── Sidebar butonları (tüm normal butonlar) ── */
[data-testid="stSidebar"] [data-testid="stButton"] > button,
[data-testid="stSidebar"] [data-testid="stFormSubmitButton"] > button {
  width: 100% !important;
  background: var(--bg2) !important;
  border: 1px solid var(--border2) !important;
  color: var(--t2) !important;
  font-family: var(--sans) !important;
  font-size: 0.82rem !important;
  font-weight: 500 !important;
  border-radius: 6px !important;
  padding: 9px 14px !important;
  text-align: left !important;
  transition: background 0.15s, border-color 0.15s, color 0.15s !important;
  box-shadow: none !important;
  letter-spacing: 0.01em !important;
}
[data-testid="stSidebar"] [data-testid="stButton"] > button:hover {
  background: var(--bg3) !important;
  border-color: var(--accent) !important;
  color: var(--t1) !important;
}

/* ── Sidebar tazele butonu (sp-refresh-btn sarmalı) ── */
[data-testid="stSidebar"] .sp-refresh-btn [data-testid="stButton"] > button,
[data-testid="stSidebar"] .sp-refresh-btn > div > button,
[data-testid="stSidebar"] .sp-refresh-btn button {
  background: var(--accent) !important;
  border: none !important;
  border-radius: 6px !important;
  color: #FFFFFF !important;
  font-family: var(--sans) !important;
  font-size: 0.84rem !important;
  font-weight: 600 !important;
  width: 100% !important;
  padding: 10px 16px !important;
  letter-spacing: 0.01em !important;
  cursor: pointer !important;
  transition: background 0.15s, box-shadow 0.15s !important;
  box-shadow: 0 2px 8px rgba(94,106,210,0.25) !important;
}
[data-testid="stSidebar"] .sp-refresh-btn [data-testid="stButton"] > button:hover,
[data-testid="stSidebar"] .sp-refresh-btn button:hover {
  background: #7C85E0 !important;
  box-shadow: 0 4px 16px rgba(94,106,210,0.4) !important;
}
[data-testid="stSidebar"] .sp-refresh-btn [data-testid="stButton"] > button:active,
[data-testid="stSidebar"] .sp-refresh-btn button:active {
  background: #4B56C0 !important;
  box-shadow: none !important;
}

/* ── Sidebar caption / küçük yazı ── */
[data-testid="stSidebar"] .stMarkdown p,
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
[data-testid="stSidebar"] small,
[data-testid="stSidebar"] .stCaption,
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] {
  color: var(--t2) !important;
  font-family: var(--sans) !important;
  font-size: 0.74rem !important;
  line-height: 1.5 !important;
}

/* ── Sidebar success / error mesajları ── */
[data-testid="stSidebar"] [data-testid="stAlert"] {
  background: var(--bg2) !important;
  border: 1px solid var(--border2) !important;
  border-radius: 6px !important;
  font-family: var(--sans) !important;
  font-size: 0.78rem !important;
}

/* ── Sidebar selectbox dropdown ── */
[data-testid="stSidebar"] .stSelectbox [data-baseweb="select"] > div {
  background: var(--bg2) !important;
  border: 1px solid var(--border2) !important;
  color: var(--t1) !important;
  font-family: var(--sans) !important;
  font-size: 0.82rem !important;
  border-radius: 6px !important;
}
[data-testid="stSidebar"] .stSelectbox [data-baseweb="select"] > div:hover {
  border-color: var(--accent) !important;
}

/* ── Sidebar progress bar ── */
[data-testid="stSidebar"] [data-testid="stProgress"] > div > div {
  background: var(--bg3) !important;
  border-radius: 4px !important;
}
[data-testid="stSidebar"] [data-testid="stProgress"] > div > div > div {
  background: var(--accent) !important;
  border-radius: 4px !important;
}

/* ── Base ── */
html, body,
[data-testid="stAppViewContainer"],
[data-testid="stAppViewContainer"] > .main,
[data-testid="stMainBlockContainer"] {
  background-color: var(--bg) !important;
  background-image: radial-gradient(circle, #ffffff08 1px, transparent 1px) !important;
  background-size: 24px 24px !important;
  font-family: var(--sans) !important;
  color: var(--t1) !important;
}
.main .block-container {
  background: transparent !important;
  padding: 24px 32px 48px !important;
  max-width: 1400px !important;
}

/* ── Sidebar ── */
[data-testid="stSidebar"] {
  background-color: var(--bg1) !important;
  background-image: radial-gradient(circle, #ffffff05 1px, transparent 1px) !important;
  background-size: 24px 24px !important;
  border-right: 1px solid var(--border) !important;
}
[data-testid="stSidebarContent"] { padding: 0 !important; }
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] [data-testid="stWidgetLabel"] {
  font-family: var(--sans) !important;
  color: var(--t3) !important;
  font-size: 0.69rem !important;
  font-weight: 600 !important;
  text-transform: uppercase !important;
  letter-spacing: 0.07em !important;
}
[data-testid="stSidebar"] .stSelectbox > div > div,
[data-testid="stSidebar"] .stTextInput > div > div > input {
  background: var(--bg2) !important;
  border: 1px solid var(--border2) !important;
  color: var(--t1) !important;
  font-family: var(--sans) !important;
  font-size: 0.82rem !important;
  border-radius: var(--r) !important;
}
[data-testid="stSidebar"] hr {
  border: none !important;
  border-top: 1px solid var(--border) !important;
  margin: 10px 0 !important;
}

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
  background: transparent !important;
  border-bottom: 1px solid var(--border) !important;
  gap: 0 !important;
  padding: 0 !important;
}
.stTabs [data-baseweb="tab"] {
  background: transparent !important;
  border: none !important;
  border-bottom: 2px solid transparent !important;
  color: var(--t3) !important;
  font-family: var(--sans) !important;
  font-size: 0.78rem !important;
  font-weight: 500 !important;
  padding: 10px 16px !important;
  margin-bottom: -1px !important;
  letter-spacing: 0.01em !important;
  transition: color 0.2s, border-bottom-color 0.2s !important;
}
.stTabs [data-baseweb="tab"]:hover { color: var(--t2) !important; }
.stTabs [aria-selected="true"] {
  color: var(--t1) !important;
  border-bottom-color: var(--accent) !important;
}
.stTabs [data-baseweb="tab-highlight"] {
  background: linear-gradient(90deg, var(--accent), var(--accent2)) !important;
  height: 2px !important;
  border-radius: 2px 2px 0 0 !important;
  animation: tab-slide 0.25s cubic-bezier(0.4,0,0.2,1) !important;
  transform-origin: left center !important;
}
.stTabs [data-baseweb="tab-panel"] {
  background: transparent !important;
  padding: 24px 0 !important;
}

/* ── Buttons ── */
[data-testid="stButton"] > button,
[data-testid="stFormSubmitButton"] > button {
  background: var(--bg2) !important;
  border: 1px solid var(--border2) !important;
  color: var(--t2) !important;
  font-family: var(--sans) !important;
  font-size: 0.79rem !important;
  font-weight: 500 !important;
  border-radius: var(--r) !important;
  padding: 7px 14px !important;
  transition: all 0.15s !important;
  box-shadow: none !important;
}
[data-testid="stButton"] > button:hover {
  background: var(--accent) !important;
  border-color: var(--accent) !important;
  color: #fff !important;
}
[data-testid="stButton"] > button[kind="primary"],
[data-testid="stFormSubmitButton"] > button[kind="primary"] {
  background: var(--accent) !important;
  border-color: var(--accent) !important;
  color: #fff !important;
}
[data-testid="stButton"] > button[kind="primary"]:hover {
  background: var(--accent2) !important;
  border-color: var(--accent2) !important;
}

/* ── Inputs ── */
[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea,
[data-testid="stNumberInput"] input {
  background: var(--bg2) !important;
  border: 1px solid var(--border2) !important;
  color: var(--t1) !important;
  font-family: var(--sans) !important;
  font-size: 0.83rem !important;
  border-radius: var(--r) !important;
  transition: border-color 0.15s !important;
  box-shadow: none !important;
}
[data-testid="stTextInput"] input:focus,
[data-testid="stTextArea"] textarea:focus {
  border-color: var(--accent) !important;
  box-shadow: 0 0 0 3px rgba(94,106,210,0.12) !important;
}
[data-testid="stTextInput"] input::placeholder,
[data-testid="stTextArea"] textarea::placeholder { color: var(--t3) !important; }
[data-testid="stTextInput"] label,
[data-testid="stTextArea"] label,
[data-testid="stNumberInput"] label {
  color: var(--t3) !important;
  font-family: var(--sans) !important;
  font-size: 0.69rem !important;
  font-weight: 600 !important;
  text-transform: uppercase !important;
  letter-spacing: 0.07em !important;
}

/* ── Selectbox / Multiselect ── */
[data-testid="stSelectbox"] > div > div,
[data-testid="stMultiSelect"] > div > div {
  background: var(--bg2) !important;
  border: 1px solid var(--border2) !important;
  border-radius: var(--r) !important;
  color: var(--t1) !important;
  font-family: var(--sans) !important;
  font-size: 0.83rem !important;
}
[data-testid="stSelectbox"] label,
[data-testid="stMultiSelect"] label {
  color: var(--t3) !important;
  font-family: var(--sans) !important;
  font-size: 0.69rem !important;
  font-weight: 600 !important;
  text-transform: uppercase !important;
  letter-spacing: 0.07em !important;
}

/* ── Native Metrics (fallback) ── */
[data-testid="stMetric"] {
  background: var(--bg1) !important;
  border: 1px solid var(--border) !important;
  border-radius: var(--r) !important;
  padding: 18px 20px !important;
  position: relative !important;
  overflow: hidden !important;
  transition: box-shadow 0.25s, border-color 0.25s !important;
}
[data-testid="stMetric"]::before {
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(94,106,210,0.4), rgba(129,140,248,0.3), transparent);
}
[data-testid="stMetric"]:hover {
  border-color: rgba(94,106,210,0.3) !important;
  box-shadow: 0 0 20px rgba(94,106,210,0.08), 0 4px 24px rgba(0,0,0,0.4) !important;
}
[data-testid="stMetricLabel"] > div {
  color: var(--t3) !important;
  font-family: var(--sans) !important;
  font-size: 0.69rem !important;
  text-transform: uppercase !important;
  letter-spacing: 0.07em !important;
  font-weight: 600 !important;
}
[data-testid="stMetricValue"] > div {
  color: var(--t1) !important;
  font-family: var(--mono) !important;
  font-size: 2rem !important;
  font-weight: 700 !important;
}

/* ── Alerts ── */
[data-testid="stAlert"],
[data-testid="stNotification"] {
  background: var(--bg2) !important;
  border: 1px solid var(--border2) !important;
  border-radius: var(--r) !important;
  font-family: var(--sans) !important;
  font-size: 0.81rem !important;
  color: var(--t2) !important;
}
[data-testid="stNotificationContentInfo"]    { border-left: 2px solid var(--accent) !important; }
[data-testid="stNotificationContentSuccess"] { border-left: 2px solid var(--ok) !important; }
[data-testid="stNotificationContentWarning"] { border-left: 2px solid var(--warn) !important; }
[data-testid="stNotificationContentError"]   { border-left: 2px solid var(--err) !important; }

/* ── Dataframe ── */
[data-testid="stDataFrame"] {
  border: 1px solid var(--border) !important;
  border-radius: var(--r) !important;
  overflow: hidden !important;
}

/* ── Expander ── */
[data-testid="stExpander"] {
  border: 1px solid var(--border) !important;
  border-radius: var(--r) !important;
  background: var(--bg1) !important;
}
[data-testid="stExpander"] summary {
  font-family: var(--sans) !important;
  color: var(--t2) !important;
  font-size: 0.81rem !important;
  font-weight: 500 !important;
}
[data-testid="stExpander"] summary:hover { color: var(--t1) !important; }

/* ── Slider ── */
[data-testid="stSlider"] [role="slider"] { background: var(--accent) !important; }
[data-testid="stSlider"] label {
  color: var(--t3) !important;
  font-size: 0.69rem !important;
  font-family: var(--sans) !important;
  font-weight: 600 !important;
  text-transform: uppercase !important;
  letter-spacing: 0.07em !important;
}

/* ── Checkbox / Radio ── */
[data-testid="stCheckbox"] label,
[data-testid="stRadio"] label {
  color: var(--t2) !important;
  font-family: var(--sans) !important;
  font-size: 0.81rem !important;
}
[data-testid="stRadio"] label:hover { color: var(--t1) !important; }

/* ── Spinner ── */
[data-testid="stSpinner"] > div { border-top-color: var(--accent) !important; }

/* ── Typography ── */
h1, h2, h3, h4, h5, h6 {
  font-family: var(--sans) !important;
  color: var(--t1) !important;
  letter-spacing: -0.02em !important;
  font-weight: 600 !important;
}
h1 { font-size: 1.25rem !important; }
h2 { font-size: 1rem !important; }
h3 { font-size: 0.9rem !important; }
p, .stMarkdown p {
  font-family: var(--sans) !important;
  color: var(--t2) !important;
  font-size: 0.83rem !important;
  line-height: 1.65 !important;
}
.stCaption, [data-testid="stCaptionContainer"] {
  color: var(--t3) !important;
  font-family: var(--sans) !important;
  font-size: 0.72rem !important;
}

/* ── Divider ── */
hr {
  border: none !important;
  border-top: 1px solid var(--border) !important;
  margin: 18px 0 !important;
}

/* ── Form ── */
[data-testid="stForm"] {
  border: none !important;
  background: transparent !important;
  padding: 0 !important;
}

/* ── Column padding ── */
[data-testid="column"] { padding: 0 5px !important; }
[data-testid="column"]:first-child { padding-left: 0 !important; }
[data-testid="column"]:last-child  { padding-right: 0 !important; }

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: var(--bg); }
::-webkit-scrollbar-thumb { background: var(--border2); border-radius: 2px; }
::-webkit-scrollbar-thumb:hover { background: var(--t3); }

/* ── Design components ── */
.sp-page-header {
  padding: 0 0 20px;
  border-bottom: 1px solid var(--border);
  margin-bottom: 24px;
}
.sp-page-header h1 {
  font-size: 1.1rem !important;
  font-weight: 700 !important;
  color: var(--t1) !important;
  margin: 0 0 3px !important;
  letter-spacing: -0.02em !important;
  font-family: var(--sans) !important;
}
.sp-page-header p {
  font-size: 0.78rem !important;
  color: var(--t3) !important;
  margin: 0 !important;
  font-family: var(--sans) !important;
}

.sp-metric {
  background: var(--bg1);
  border: 1px solid var(--border);
  border-radius: var(--r);
  padding: 18px 20px;
  height: 100%;
  position: relative;
  overflow: hidden;
  transition: box-shadow 0.25s, border-color 0.25s;
}
.sp-metric::before {
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(94,106,210,0.4), rgba(129,140,248,0.3), transparent);
}
.sp-metric:hover {
  border-color: rgba(94,106,210,0.3);
  box-shadow: 0 0 20px rgba(94,106,210,0.08), 0 4px 24px rgba(0,0,0,0.4);
}
.sp-metric-label {
  font-family: var(--sans);
  font-size: 0.67rem;
  font-weight: 600;
  color: var(--t3);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  gap: 6px;
}
.sp-metric-value {
  font-family: var(--mono);
  font-size: 2rem;
  font-weight: 700;
  color: var(--t1);
  line-height: 1;
  letter-spacing: -0.03em;
  animation: count-up 0.4s ease both;
}
.sp-metric-sub {
  font-family: var(--sans);
  font-size: 0.71rem;
  color: var(--t3);
  margin-top: 6px;
  line-height: 1.5;
}
.sp-metric-accent .sp-metric-value { color: var(--accent); }
.sp-metric-ok      .sp-metric-value { color: var(--ok); }

.sp-section {
  display: flex;
  align-items: center;
  gap: 7px;
  margin: 24px 0 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border);
}
.sp-section-label {
  font-family: var(--sans);
  font-size: 0.69rem;
  font-weight: 700;
  color: var(--t3);
  text-transform: uppercase;
  letter-spacing: 0.09em;
}
.sp-section-sub {
  font-family: var(--sans);
  font-size: 0.69rem;
  color: var(--t3);
  margin-left: 4px;
}
.sp-section i { color: var(--t3); font-size: 14px; }

.sp-card {
  background: var(--bg1);
  border: 1px solid var(--border);
  border-radius: var(--r);
  padding: 18px 20px;
  margin-bottom: 6px;
  position: relative;
  overflow: hidden;
  transition: box-shadow 0.25s, border-color 0.25s;
}
.sp-card::after {
  content: '';
  position: absolute;
  top: 0; left: 0;
  width: 2px; height: 100%;
  background: linear-gradient(180deg, var(--accent), var(--accent2));
  opacity: 0;
  transition: opacity 0.25s;
}
.sp-card:hover {
  border-color: rgba(94,106,210,0.25);
  box-shadow: 0 0 18px rgba(94,106,210,0.07), 0 4px 20px rgba(0,0,0,0.35);
}
.sp-card:hover::after { opacity: 1; }

.sp-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  border-radius: 4px;
  padding: 2px 7px;
  font-family: var(--mono);
  font-size: 0.65rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}
.sp-badge-accent  { background: rgba(94,106,210,0.12); color: #818CF8; border: 1px solid rgba(94,106,210,0.2); }
.sp-badge-ok      { background: rgba(74,222,128,0.1);  color: #4ADE80; border: 1px solid rgba(74,222,128,0.2); }
.sp-badge-warn    { background: rgba(251,191,36,0.1);  color: #FBBF24; border: 1px solid rgba(251,191,36,0.2); }
.sp-badge-err     { background: rgba(248,113,113,0.1); color: #F87171; border: 1px solid rgba(248,113,113,0.2); }
.sp-badge-muted   { background: rgba(74,74,74,0.15);   color: #8B8B8B; border: 1px solid rgba(74,74,74,0.2); }

.sp-match-card {
  background: var(--bg1);
  border: 1px solid var(--border);
  border-radius: var(--r);
  padding: 12px 16px;
  margin-bottom: 5px;
  display: flex;
  align-items: flex-start;
  gap: 14px;
  position: relative;
  overflow: hidden;
  transition: border-color 0.2s, box-shadow 0.2s;
}
.sp-match-card::before {
  content: '';
  position: absolute;
  top: 0; left: 0;
  width: 2px; height: 100%;
  background: linear-gradient(180deg, var(--accent), var(--accent2));
  opacity: 0;
  transition: opacity 0.2s;
}
.sp-match-card:hover {
  border-color: rgba(94,106,210,0.3);
  box-shadow: 0 0 16px rgba(94,106,210,0.1), 0 2px 12px rgba(0,0,0,0.3);
}
.sp-match-card:hover::before { opacity: 1; }
.sp-match-pct {
  font-family: var(--mono);
  font-size: 1.15rem;
  font-weight: 700;
  color: var(--accent);
  min-width: 48px;
  text-align: right;
  line-height: 1;
  padding-top: 2px;
}
.sp-match-title { font-family: var(--sans); font-size: 0.83rem; font-weight: 600; color: var(--t1); }
.sp-match-meta  { font-family: var(--sans); font-size: 0.74rem; color: var(--t3); margin-top: 2px; }
.sp-tag {
  display: inline-block;
  background: var(--bg3);
  border: 1px solid var(--border2);
  border-radius: 4px;
  padding: 1px 6px;
  font-family: var(--mono);
  font-size: 0.68rem;
  color: var(--t2);
  margin: 2px 2px 2px 0;
}
.sp-tag-accent {
  background: rgba(94,106,210,0.08);
  border-color: rgba(94,106,210,0.2);
  color: #818CF8;
}

.sp-insight-card {
  background: var(--bg1);
  border: 1px solid var(--border);
  border-left: 2px solid var(--accent);
  border-radius: var(--r);
  padding: 14px 18px;
  margin-bottom: 6px;
}
.sp-insight-card.rise { border-left-color: var(--ok); }
.sp-insight-card.fall { border-left-color: var(--err); }
.sp-insight-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}
.sp-insight-skill {
  font-family: var(--mono);
  font-size: 0.81rem;
  font-weight: 700;
  color: var(--t1);
}
.sp-insight-delta {
  font-family: var(--mono);
  font-size: 0.7rem;
}
.sp-insight-body {
  font-family: var(--sans);
  font-size: 0.81rem;
  color: var(--t2);
  line-height: 1.6;
}

.sp-empty {
  background: var(--bg1);
  border: 1px solid var(--border);
  border-radius: var(--r);
  padding: 40px 24px;
  text-align: center;
}
.sp-empty i { font-size: 28px; color: var(--border2); margin-bottom: 10px; display: block; }
.sp-empty-title { font-family: var(--sans); font-size: 0.88rem; font-weight: 500; color: var(--t2); }
.sp-empty-sub   { font-family: var(--sans); font-size: 0.76rem; color: var(--t3); margin-top: 4px; }

.sp-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 18px 16px 14px;
  border-bottom: 1px solid var(--border);
  margin-bottom: 12px;
}
.sp-brand-icon {
  width: 28px; height: 28px;
  background: rgba(94,106,210,0.1);
  border: 1px solid rgba(94,106,210,0.2);
  border-radius: 7px;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.sp-brand-name { font-family: var(--sans); font-size: 0.92rem; font-weight: 700; color: var(--t1); }
.sp-brand-sub  { font-family: var(--sans); font-size: 0.67rem; color: var(--t3); margin-top: 1px; }

.sp-sb-section {
  padding: 10px 16px 3px;
  font-family: var(--sans);
  font-size: 0.63rem;
  font-weight: 700;
  color: var(--t3);
  text-transform: uppercase;
  letter-spacing: 0.09em;
}
.sp-sb-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 16px;
  font-family: var(--sans);
  font-size: 0.75rem;
  color: var(--t2);
}
.sp-sb-dot {
  width: 5px; height: 5px;
  border-radius: 50%;
  flex-shrink: 0;
}
.sp-sb-dot.on  { background: var(--ok); }
.sp-sb-dot.off { background: var(--border2); }
</style>
"""

# Phosphor Icons CDN script (markdown ile enjekte edilir)
PHOSPHOR_CDN = """
<link rel="stylesheet" href="https://unpkg.com/@phosphor-icons/web@2.1.1/src/regular/style.css">
<link rel="stylesheet" href="https://unpkg.com/@phosphor-icons/web@2.1.1/src/bold/style.css">
"""

# Sidebar brand HTML
SIDEBAR_BRAND = """
<div class="sp-brand">
  <div class="sp-brand-icon">
    <i class="ph ph-lightning" style="color:#5E6AD2;font-size:15px;"></i>
  </div>
  <div>
    <div class="sp-brand-name">puoS</div>
    <div class="sp-brand-sub">Skill trend engine</div>
  </div>
</div>
"""


def sidebar_source_list(sources: dict) -> str:
    rows = "".join(
        f'<div class="sp-sb-item">'
        f'<div class="sp-sb-dot {"on" if active else "off"}"></div>'
        f'<span>{label}</span></div>'
        for label, active in sources.items()
    )
    return f'<div class="sp-sb-section">Data Sources</div>{rows}'


# ─────────────────────────────────────────────────────────────────────────────
# HTML bileşenler
# ─────────────────────────────────────────────────────────────────────────────

def page_header(title: str, subtitle: str = "") -> str:
    sub = f'<p>{subtitle}</p>' if subtitle else ""
    return f'<div class="sp-page-header"><h1>{title}</h1>{sub}</div>'


def metric_card(label: str, value, sub: str = "",
                variant: str = "", icon: str = "",
                trend: str = "") -> str:
    """trend: 'up' | 'down' | '' """
    cls = f"sp-metric sp-metric-{variant}" if variant else "sp-metric"
    icon_html = f'<i class="ph ph-{icon}"></i>' if icon else ""
    sub_html = f'<div class="sp-metric-sub">{sub}</div>' if sub else ""
    if trend == "up":
        trend_html = ('<span style="font-family:var(--mono);font-size:0.75rem;'
                      'color:#4ADE80;margin-left:8px">&#8593;</span>')
    elif trend == "down":
        trend_html = ('<span style="font-family:var(--mono);font-size:0.75rem;'
                      'color:#F87171;margin-left:8px">&#8595;</span>')
    else:
        trend_html = ""
    return f"""
<div class="{cls}">
  <div class="sp-metric-label">{icon_html}{label}</div>
  <div class="sp-metric-value">{value}{trend_html}</div>
  {sub_html}
</div>"""


def section_header(title: str, icon: str = "", sub: str = "") -> str:
    icon_html = f'<i class="ph ph-{icon}"></i>' if icon else ""
    sub_html = f'<span class="sp-section-sub">— {sub}</span>' if sub else ""
    return (f'<div class="sp-section">{icon_html}'
            f'<span class="sp-section-label">{title}</span>{sub_html}</div>')


def badge(text: str, variant: str = "accent") -> str:
    return f'<span class="sp-badge sp-badge-{variant}">{text}</span>'


def tag(text: str, accent: bool = False) -> str:
    cls = "sp-tag sp-tag-accent" if accent else "sp-tag"
    return f'<span class="{cls}">{text}</span>'


def empty_state(title: str, sub: str = "", icon: str = "tray") -> str:
    sub_html = f'<div class="sp-empty-sub">{sub}</div>' if sub else ""
    return (f'<div class="sp-empty">'
            f'<i class="ph ph-{icon}"></i>'
            f'<div class="sp-empty-title">{title}</div>{sub_html}</div>')


def match_card(title: str, company: str, country: str,
               pct: float, matched: list, missing: list) -> str:
    matched_tags = "".join(tag(s, accent=True) for s in matched[:6])
    miss_tags = "".join(tag(s) for s in missing[:4])
    if len(missing) > 4:
        miss_tags += f'<span class="sp-tag" style="color:#4A4A4A">+{len(missing)-4}</span>'
    miss_html = (f'<div style="margin-top:5px;font-family:var(--mono);'
                 f'font-size:0.69rem;color:#4A4A4A;">Missing: {miss_tags}</div>'
                 if missing else "")
    return f"""
<div class="sp-match-card">
  <div style="text-align:right;min-width:48px">
    <div class="sp-match-pct">{pct:.0f}%</div>
    <div style="font-family:var(--sans);font-size:0.65rem;color:#4A4A4A;margin-top:2px">match</div>
  </div>
  <div style="flex:1;min-width:0">
    <div class="sp-match-title">{title}</div>
    <div class="sp-match-meta">{company} · {country}</div>
    <div style="margin-top:6px">{matched_tags}</div>
    {miss_html}
  </div>
</div>"""


def hero_banner(title: str, desc: str) -> str:
    return f"""
<div style="background:#111111;border:1px solid #1E1E1E;border-left:3px solid #5E6AD2;
     border-radius:8px;padding:16px 22px;margin-bottom:24px;">
  <div style="font-family:var(--sans);font-size:0.92rem;font-weight:600;
       color:#FFFFFF;margin-bottom:4px;letter-spacing:-0.01em;">{title}</div>
  <div style="font-family:var(--sans);font-size:0.78rem;color:#8B8B8B;">{desc}</div>
</div>"""


def loading_banner(text: str = "Veriler yükleniyor...") -> str:
    return f"""
<div style="background:#0D1117;border:1px solid #1E2330;border-left:3px solid #5E6AD2;
     border-radius:8px;padding:14px 20px;margin-bottom:16px;
     display:flex;align-items:center;gap:12px;
     animation:loading-pulse 1.4s ease-in-out infinite;">
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#5E6AD2" stroke-width="2"
       stroke-linecap="round" stroke-linejoin="round">
    <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83
             M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/>
  </svg>
  <span style="font-family:var(--sans);font-size:0.82rem;color:#9CA3AF;">{text}</span>
</div>"""


def insight_card(skill: str, delta: float, text: str) -> str:
    cls = "rise" if delta > 0 else "fall"
    delta_color = "#4ADE80" if delta > 0 else "#F87171"
    icon = "trend-up" if delta > 0 else "trend-down"
    return f"""
<div class="sp-insight-card {cls}">
  <div class="sp-insight-head">
    <i class="ph ph-{icon}" style="color:{delta_color};font-size:14px;"></i>
    <span class="sp-insight-skill">{skill}</span>
    <span class="sp-insight-delta" style="color:{delta_color}">{delta*100:+.1f} pts</span>
  </div>
  <div class="sp-insight-body">{text}</div>
</div>"""


# ─────────────────────────────────────────────────────────────────────────────
# apply_global_css
# ─────────────────────────────────────────────────────────────────────────────
def apply_global_css() -> None:
    st.markdown(PHOSPHOR_CDN, unsafe_allow_html=True)
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)


# Backward compat aliases
ICONS = {}
