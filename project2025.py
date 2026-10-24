import streamlit as st
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from collections import Counter
import random
import time
import datetime
import json
import re
import io
import os
import hmac
import uuid

import storage
from ism_core import (
    transitive_closure, compute_ism_levels, ism_cycle_members,
    classify_micmac, build_analysis_results,
)

# ==============================================================================
# 0. הגדרות מערכת, ספריות ו-API (OpenRouter + DuckDuckGo - חינם!)
# ==============================================================================
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    from ddgs import DDGS  # השם החדש של duckduckgo_search
    DDGS_AVAILABLE = True
except ImportError:
    try:
        from duckduckgo_search import DDGS
        DDGS_AVAILABLE = True
    except ImportError:
        DDGS_AVAILABLE = False

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

API_AVAILABLE = OPENAI_AVAILABLE and DDGS_AVAILABLE

def _get_secret(key, default=""):
    """קורא מפתח מ-st.secrets בבטחה, גם כשלא קיים קובץ secrets.toml כלל. אחרת - ממשתנה סביבה."""
    try:
        value = st.secrets.get(key)
        if value:
            return value
    except Exception:
        pass
    return os.environ.get(key, default)

# --- קונפיגורציה ---
# פרטי המנהל נקראים מ-secrets.toml או ממשתני סביבה, ולא כתובים בקוד.
# אם לא הוגדרה סיסמה, כניסת המנהל חסומה.
ADMIN_USERNAME = _get_secret("ADMIN_USERNAME", "admin_ism")
ADMIN_PASSWORD = _get_secret("ADMIN_PASSWORD", "")

# מסד הנתונים המשותף לכל הסשנים (מומחים מכמה מכשירים + המנהל)
DB_PATH = _get_secret("ISM_DB_PATH", storage.DEFAULT_DB_PATH)
storage.init_db(DB_PATH)

def check_admin_credentials(username, password):
    """השוואה בזמן קבוע, כדי לא לחשוף מידע דרך זמני תגובה."""
    if not ADMIN_PASSWORD:
        return False
    return (hmac.compare_digest(username.encode(), ADMIN_USERNAME.encode())
            and hmac.compare_digest(password.encode(), ADMIN_PASSWORD.encode()))

# קריאת מפתח OpenRouter מ-Streamlit Secrets (אם קיים)
AI_API_KEY = _get_secret("OPENROUTER_API_KEY", "PLACEHOLDER") or "PLACEHOLDER"

AI_MODEL_NAME = "google/gemma-4-31b-it:free"

# מודל Claude (Anthropic) - משמש כסוכן AI חלופי (איכות גבוהה, בתשלום)
ANTHROPIC_MODEL_NAME = "claude-sonnet-5"
ANTHROPIC_EFFORT = "medium"
# תמחור Claude Sonnet 5 (דולר למיליון טוקנים)
ANTHROPIC_PRICE_INPUT_PER_M = 2.00
ANTHROPIC_PRICE_OUTPUT_PER_M = 10.00

# נתוני ברירת מחדל
DEFAULT_FACTORS = [
    'תרבות נהיגה', 'הסחות דעת', 'עייפות', 'מצב כבישים',
    'נוכחות משטרה', 'חומרת ענישה', 'טכנולוגיית אכיפה'
]
DEFAULT_GENERIC_QUESTION = "באיזו מידה גורם {i} משפיע באופן ישיר על גורם {j}? בחר V, A, X או O."
SYMBOLS = ['V', 'A', 'X', 'O']

# ==============================================================================
# I. פונקציות עיצוב ותצוגה (UI/UX - Premium Styling)
# ==============================================================================
def apply_advanced_styling():
    """מזריק CSS מתקדם לתיקון RTL, פונטים יוקרתיים, צבעים ועיצוב פרימיום."""
    st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Heebo:wght@300;400;500;700;900&display=swap');

:root {
    --brand-900: #1E3A8A;
    --brand-700: #1E40AF;
    --brand-600: #2563EB;
    --brand-500: #3B82F6;
    --brand-100: #EFF6FF;
    --brand-50: #F8FAFF;
    --accent: #7C3AED;
    --surface: #ffffff;
    --border: #E2E8F0;
    --text-main: #1E293B;
    --text-muted: #64748B;
}

html, body, [class*="css"] {
    font-family: 'Heebo', 'Segoe UI', sans-serif;
    direction: rtl;
    text-align: right;
}

.stApp {
    background: radial-gradient(circle at 15% 0%, #eef2ff 0%, #f8fafc 35%, #f1f5f9 100%);
}

.stDataFrame, code, .stCodeBlock, .stJson, .stMetricValue, .js-plotly-plot {
    font-family: 'Times New Roman', Times, serif !important;
    direction: ltr !important;
    text-align: left !important;
}

h1 {
    background: linear-gradient(90deg, var(--brand-900), var(--accent));
    -webkit-background-clip: text;
    background-clip: text;
    color: transparent;
    font-family: 'Heebo', sans-serif;
    font-weight: 900;
    text-align: right;
    padding-bottom: 12px;
    font-size: 3rem !important;
    letter-spacing: -0.5px;
}

h2, h3 {
    color: var(--brand-700);
    font-weight: 700;
    text-align: right;
}

h4 {
    color: var(--text-main);
    font-weight: 700;
}

/* --- כרטיסי תוכן כלליים (st.container(border=True)) --- */
[data-testid="stVerticalBlockBorderWrapper"] {
    background: var(--surface);
    border: 1px solid var(--border) !important;
    border-radius: 16px !important;
    box-shadow: 0 6px 18px rgba(15,23,42,0.06);
}

/* --- Sidebar --- */
[data-testid="stSidebar"] {
    text-align: right;
    background: linear-gradient(180deg, #0F172A 0%, #1E293B 100%);
    border-left: 1px solid #0f172a;
}
[data-testid="stSidebar"] * {
    color: #E2E8F0 !important;
}
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
    color: #F8FAFC !important;
    background: none !important;
    -webkit-text-fill-color: #F8FAFC !important;
}
[data-testid="stSidebar"] .stAlert {
    background-color: rgba(59,130,246,0.15) !important;
    border: 1px solid rgba(59,130,246,0.35);
}

/* --- כפתורים --- */
.stButton button {
    width: 100%;
    border-radius: 10px;
    font-weight: bold;
    font-size: 18px;
    background: linear-gradient(135deg, var(--brand-600), var(--accent));
    color: white;
    border: none;
    box-shadow: 0 3px 8px rgba(37,99,235,0.25);
    transition: 0.25s ease;
    padding: 0.65rem;
}
.stButton button:hover {
    filter: brightness(1.08);
    transform: translateY(-2px);
    box-shadow: 0 8px 16px rgba(37,99,235,0.3);
}
.stButton button:active {
    transform: translateY(0px);
}
.stDownloadButton button {
    width: 100%;
    border-radius: 10px;
    font-weight: bold;
    background: linear-gradient(135deg, #059669, #10B981);
    color: white;
    border: none;
    box-shadow: 0 3px 8px rgba(5,150,105,0.25);
}
.stDownloadButton button:hover {
    filter: brightness(1.08);
    transform: translateY(-2px);
}

.stTextInput label, .stTextArea label, .stSelectbox label, .stNumberInput label {
    font-size: 1.05rem;
    font-weight: 600;
    color: #334155;
    text-align: right;
}
.stTextInput input, .stTextArea textarea, .stNumberInput input {
    border-radius: 10px !important;
    border: 1px solid var(--border) !important;
}
.stTextInput input:focus, .stTextArea textarea:focus {
    border-color: var(--brand-500) !important;
    box-shadow: 0 0 0 3px rgba(59,130,246,0.15) !important;
}

div[data-testid="metric-container"] {
    background: linear-gradient(160deg, #ffffff, #f8fafc);
    border: 1px solid var(--border);
    padding: 18px;
    border-radius: 14px;
    box-shadow: 0 4px 10px rgba(15,23,42,0.05);
    text-align: center;
}

.stRadio > label {
    float: right;
    font-weight: bold;
    font-size: 1.1rem;
    margin-bottom: 10px;
    color: var(--brand-700);
}
div[role="radiogroup"] {
    direction: ltr;
    justify-content: flex-end;
    gap: 15px;
    flex-wrap: wrap;
}
div[role="radiogroup"] label {
    background: var(--brand-100);
    padding: 8px 25px;
    border-radius: 20px;
    border: 1px solid #bfdbfe;
    font-family: 'Times New Roman', serif;
    font-weight: bold;
    font-size: 20px;
    color: var(--brand-900);
    cursor: pointer;
    transition: 0.2s;
}
div[role="radiogroup"] label:hover {
    background: #dbeafe;
    border-color: var(--brand-600);
    transform: translateY(-1px);
}

.stAlert {
    direction: rtl;
    border-radius: 12px;
    font-size: 1.05rem;
    box-shadow: 0 2px 6px rgba(15,23,42,0.04);
}

/* --- טאבים --- */
div[data-testid="stTabs"] button[data-baseweb="tab"] {
    font-size: 1.15rem;
    font-weight: bold;
    border-radius: 10px 10px 0 0;
    color: var(--text-muted);
}
div[data-testid="stTabs"] button[aria-selected="true"] {
    color: var(--brand-700) !important;
    border-bottom: 3px solid var(--brand-600) !important;
}

/* --- כרטיס כניסה (Login) --- */
.hero-title {
    text-align: center;
    font-size: 3.2rem;
    font-weight: 900;
    background: linear-gradient(90deg, var(--brand-900), var(--accent));
    -webkit-background-clip: text;
    background-clip: text;
    color: transparent;
    margin-bottom: 0;
}
.hero-subtitle {
    text-align: center;
    color: var(--text-muted);
    font-size: 1.3rem;
    font-weight: 400;
    margin-top: 4px;
}
.login-card-badge {
    display: inline-block;
    font-weight: 700;
    font-size: 1.05rem;
    padding: 6px 16px;
    border-radius: 999px;
    margin-bottom: 14px;
}
.badge-admin { background: #EDE9FE; color: #5B21B6; }
.badge-expert { background: #DCFCE7; color: #14532D; }

/* --- צ'אט --- */
div[data-testid="stChatMessage"] {
    direction: rtl !important;
    text-align: right !important;
    unicode-bidi: plaintext;
    border-radius: 14px;
}
div[data-testid="stChatMessage"] .stMarkdown,
div[data-testid="stChatMessage"] p {
    direction: rtl !important;
    text-align: right !important;
}
div[data-testid="stChatMessage"] pre,
div[data-testid="stChatMessage"] code,
div[data-testid="stChatMessage"] table {
    direction: ltr !important;
    text-align: left !important;
}
.stChatMessage {
    order: 0;
}
</style>
""", unsafe_allow_html=True)

def color_micmac(val):
    """צביעת תאים בטבלת התוצאות הסופית לפי חשיבות."""
    s = str(val)
    if 'Driving' in s:
        return 'background-color: #dcfce7; color: #14532d; font-weight: 900; font-size: 18px;'
    elif 'Linkage' in s:
        return 'background-color: #fef9c3; color: #713f12; font-weight: 900; font-size: 18px;'
    elif 'Dependent' in s:
        return 'background-color: #fee2e2; color: #7f1d1d; font-size: 18px;'
    return 'font-size: 18px;'

def plot_interactive_micmac(micmac_df):
    """
    יוצר גרף Plotly אינטראקטיבי למיפוי MICMAC. גורמים עם ערכי DP/DEP זהים
    (שכיח בגורמים שבאותו מעגל השפעה הדדי) מוזזים מעט במעגל קטן כדי שלא
    יתחפפו לחלוטין, ותוויות הטקסט מתחלפות במיקומן כדי לצמצם חפיפה ביניהן.
    """
    df = micmac_df.copy()
    df['Factor'] = df.index

    avg_dp = df['DP'].mean()
    avg_dep = df['DEP'].mean()

    # --- הפרדת גורמים עם קואורדינטות זהות ---
    coord_groups = {}
    for factor in df.index:
        key = (df.loc[factor, 'DEP'], df.loc[factor, 'DP'])
        coord_groups.setdefault(key, []).append(factor)

    x_span = max(df['DEP'].max() - df['DEP'].min(), 1)
    y_span = max(df['DP'].max() - df['DP'].min(), 1)
    jitter_rx, jitter_ry = x_span * 0.05, y_span * 0.05
    has_overlap = any(len(members) > 1 for members in coord_groups.values())

    plot_x, plot_y = {}, {}
    for (bx, by), members in coord_groups.items():
        n = len(members)
        for i, factor in enumerate(members):
            if n == 1:
                plot_x[factor], plot_y[factor] = bx, by
            else:
                angle = 2 * np.pi * i / n
                plot_x[factor] = bx + jitter_rx * np.cos(angle)
                plot_y[factor] = by + jitter_ry * np.sin(angle)

    df['PlotX'] = df.index.map(plot_x)
    df['PlotY'] = df.index.map(plot_y)

    # מיקום תווית מתחלף לכל גורם, כדי לצמצם חפיפת טקסט בין נקודות סמוכות
    text_positions = ['top center', 'bottom center', 'middle right', 'middle left']
    pos_for_factor = {f: text_positions[i % len(text_positions)] for i, f in enumerate(df.index)}

    palette = px.colors.qualitative.Set1
    classes = sorted(df['Classification'].unique())
    color_map = {cls: palette[i % len(palette)] for i, cls in enumerate(classes)}

    fig = go.Figure()
    for cls in classes:
        sub = df[df['Classification'] == cls]
        fig.add_trace(go.Scatter(
            x=sub['PlotX'], y=sub['PlotY'],
            mode='markers+text',
            text=sub['Factor'],
            textposition=[pos_for_factor[f] for f in sub['Factor']],
            textfont=dict(size=13),
            marker=dict(size=24, color=color_map[cls], line=dict(width=2, color='white')),
            name=cls,
            customdata=sub[['DP', 'DEP']].values,
            hovertemplate="<b>%{text}</b><br>DP (השפעה): %{customdata[0]}<br>DEP (תלות): %{customdata[1]}<extra></extra>",
        ))

    fig.add_hline(y=avg_dp, line_dash="dash", line_color="gray", annotation_text="ממוצע השפעה")
    fig.add_vline(x=avg_dep, line_dash="dash", line_color="gray", annotation_text="ממוצע תלות")

    title = "<b>מפת ניתוח MICMAC - מיפוי גורמים</b>"
    if has_overlap:
        title += "<br><sup>נקודות עם ערכי DP/DEP זהים הוזזו מעט לצורך קריאות (הערכים המדויקים מוצגים ב-hover)</sup>"

    fig.update_layout(
        title=title,
        xaxis_title="<b>Dependence Power (תלות)</b>",
        yaxis_title="<b>Driving Power (השפעה)</b>",
        font=dict(family="Arial", size=16),
        plot_bgcolor='#f8fafc',
        showlegend=True,
        legend_title_text='סיווג הגורם',
        height=700,
        margin=dict(l=60, r=60, t=90, b=40)
    )

    return fig

def plot_ism_hierarchy(levels, irm_df, cycle_members):
    """
    מצייר את דיאגרמת המבנה ההיררכי של ISM (Level Partitioning): הרמה העליונה
    (Level I) היא הגורמים הכי תלויים (ה"תוצאות"), הרמה התחתונה היא הגורמים
    הכי מניעים (ה"שורשים"). גורמים שבמעגל השפעה הדדי (cycle_members)
    נצבעים בנפרד.
    """
    num_levels = len(levels)
    pos = {}
    for lvl_idx, lvl_factors in enumerate(levels):
        y = num_levels - lvl_idx
        count = len(lvl_factors)
        for i, f in enumerate(lvl_factors):
            pos[f] = (i - (count - 1) / 2.0, y)

    factors = list(irm_df.index)
    edge_x, edge_y = [], []
    for fi in factors:
        for fj in factors:
            if fi == fj or irm_df.loc[fi, fj] != 1:
                continue
            x0, y0 = pos[fi]
            x1, y1 = pos[fj]
            if y1 > y0:  # רק קשרים ישירים "כלפי מעלה" (מניע -> תלוי); מונע עומס ויזואלי ממעגלים
                edge_x += [x0, x1, None]
                edge_y += [y0, y1, None]

    # צבעים בעלי שוני מהותי (חם מול קר) לנגישות מקסימלית - לא כחול/סגול שקשה להבדיל ביניהם
    COLOR_CYCLE = '#EA580C'      # כתום חם - גורם שנמצא במעגל השפעה הדדי
    COLOR_STANDALONE = '#2563EB'  # כחול קר - גורם עצמאי (לא במעגל)

    is_cycle_member = {f: f in cycle_members for f in factors}

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=edge_x, y=edge_y, mode='lines',
        line=dict(color='#94a3b8', width=1.5),
        hoverinfo='none', showlegend=False,
    ))
    for group_name, color, flag in [("עצמאי", COLOR_STANDALONE, False), ("מעגל השפעה הדדי", COLOR_CYCLE, True)]:
        group_factors = [f for f in factors if is_cycle_member[f] == flag]
        if not group_factors:
            continue
        fig.add_trace(go.Scatter(
            x=[pos[f][0] for f in group_factors],
            y=[pos[f][1] for f in group_factors],
            mode='markers+text',
            text=group_factors, textposition='top center', textfont=dict(size=13),
            marker=dict(size=28, color=color, line=dict(width=2, color='white')),
            hoverinfo='text', name=group_name, showlegend=True,
        ))
    fig.update_layout(
        title="<b>דיאגרמת מבנה ISM היררכית</b> (למעלה: הכי תלוי ⬆️ | למטה: הכי מניע ⬇️)",
        xaxis=dict(visible=False),
        yaxis=dict(visible=False, range=[0.3, num_levels + 0.7]),
        plot_bgcolor='#f8fafc',
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='center', x=0.5),
        height=max(400, 130 * num_levels + 120),
        margin=dict(l=40, r=40, t=90, b=40),
    )
    return fig

# ==============================================================================
# II. ניהול מצב (State Management)
# ==============================================================================
def init_session_state():
    """מאתחל את כל משתני הזיכרון של האפליקציה."""
    if 'role' not in st.session_state:
        st.session_state['role'] = None
    if 'current_expert_name' not in st.session_state:
        st.session_state['current_expert_name'] = ""
    if 'FACTORS' not in st.session_state or not st.session_state['FACTORS']:
        st.session_state['FACTORS'] = DEFAULT_FACTORS
    if 'GENERIC_QUESTION' not in st.session_state:
        st.session_state['GENERIC_QUESTION'] = DEFAULT_GENERIC_QUESTION
    if 'EXPERT_DATA' not in st.session_state:
        st.session_state['EXPERT_DATA'] = {}
    if 'JUSTIFICATIONS' not in st.session_state:
        st.session_state['JUSTIFICATIONS'] = {}
    if 'AI_LOG' not in st.session_state:
        st.session_state['AI_LOG'] = []
    if 'TOPIC' not in st.session_state:
        st.session_state['TOPIC'] = ""
    if not isinstance(st.session_state.get('RESULTS', {}), dict) or \
            ('RESULTS' in st.session_state and 'micmac_katz' not in st.session_state['RESULTS']):
        del st.session_state['RESULTS']  # תוצאות בפורמט ישן מסשן פעיל - יחושבו מחדש
    if 'AI_USAGE' not in st.session_state:
        st.session_state['AI_USAGE'] = {'calls': 0, 'input_tokens': 0, 'output_tokens': 0, 'cost': 0.0, 'history': []}
    if 'ANTHROPIC_API_KEY' not in st.session_state:
        st.session_state['ANTHROPIC_API_KEY'] = _get_secret('ANTHROPIC_API_KEY', '')
    if 'ANTHROPIC_WORKSPACE_ID' not in st.session_state:
        st.session_state['ANTHROPIC_WORKSPACE_ID'] = _get_secret('ANTHROPIC_WORKSPACE_ID', '')
    if 'AI_PROVIDER' not in st.session_state:
        # אם מוגדר מפתח Anthropic ב-Secrets, זהו יהיה ספק ברירת המחדל
        st.session_state['AI_PROVIDER'] = 'anthropic' if st.session_state['ANTHROPIC_API_KEY'] else 'openrouter'
    sync_from_db()

def sync_from_db():
    """
    טוען מהמסד את הגדרות הפרויקט ואת כל תשובות המומחים, בכל ריצה של הסקריפט, כך
    שתשובות שנשלחו ממכשירים אחרים מופיעות אצל המנהל. אם אוסף המומחים השתנה מאז
    הניתוח האחרון, התוצאות השמורות בסשן נמחקות ויחושבו מחדש.
    """
    settings = storage.load_settings(DB_PATH)
    if settings.get('FACTORS'):
        st.session_state['FACTORS'] = settings['FACTORS']
    for key in ('TOPIC', 'GENERIC_QUESTION'):
        if key in settings:
            st.session_state[key] = settings[key]

    expert_data, justifications, citations = storage.load_experts(DB_PATH)
    st.session_state['EXPERT_DATA'] = expert_data
    st.session_state['JUSTIFICATIONS'] = justifications
    st.session_state['CITATIONS'] = citations

    results = st.session_state.get('RESULTS')
    if results is not None and results.get('expert_ids') != frozenset(expert_data):
        invalidate_results()

def invalidate_results():
    for k in ('RESULTS', 'SSIM_INIT', 'FINAL_SSIM'):
        st.session_state.pop(k, None)
    st.session_state['AI_LOG'] = []

def analyze_and_store(ssim_init, conflicts):
    """פותר קונפליקטים, מחשב את כל המטריצות ושומר את התוצאות בסשן יחד עם אוסף המומחים שעליו חושבו."""
    _, irm, frm, micmac = solve_conflicts_and_finalize(ssim_init, conflicts)
    results = build_analysis_results(irm, frm, micmac)
    results['expert_ids'] = frozenset(st.session_state['EXPERT_DATA'])
    st.session_state['RESULTS'] = results

def record_ai_usage(input_tokens, output_tokens):
    """מתעד צריכת טוקנים ועלות של קריאה למודל בתשלום."""
    cost = (input_tokens * ANTHROPIC_PRICE_INPUT_PER_M + output_tokens * ANTHROPIC_PRICE_OUTPUT_PER_M) / 1_000_000
    usage = st.session_state['AI_USAGE']
    usage['calls'] += 1
    usage['input_tokens'] += input_tokens
    usage['output_tokens'] += output_tokens
    usage['cost'] += cost
    usage['history'].append({
        "זמן": datetime.datetime.now().strftime("%H:%M:%S"),
        "טוקני קלט": input_tokens,
        "טוקני פלט": output_tokens,
        "עלות ($)": round(cost, 5),
    })

def is_ai_ready():
    """בודק האם ספק ה-AI הנבחר כרגע מוגדר ומוכן לשימוש."""
    provider = st.session_state.get('AI_PROVIDER', 'openrouter')
    if provider == 'anthropic':
        return ANTHROPIC_AVAILABLE and bool(st.session_state.get('ANTHROPIC_API_KEY'))
    return OPENAI_AVAILABLE and DDGS_AVAILABLE and AI_API_KEY != "PLACEHOLDER"

def ai_provider_label():
    provider = st.session_state.get('AI_PROVIDER', 'openrouter')
    if provider == 'anthropic':
        return f"Anthropic — {ANTHROPIC_MODEL_NAME} (effort: {ANTHROPIC_EFFORT})"
    return f"OpenRouter — {AI_MODEL_NAME}"

# ==============================================================================
# III. לוגיקה מתמטית (The Brain)
# ==============================================================================
def compute_expert_symbol_stats(factors):
    """
    מחשב פילוח תשובות (V/A/X/O) לכל מומחה/סוכן, לאיתור הטיה (למשל סוכן שמסמן
    כמעט תמיד V) שגורמת למטריצת נגישות מנוונת (כמעט כולה 1).
    """
    n = len(factors)
    rows = []
    for exp_id, info in st.session_state['EXPERT_DATA'].items():
        resp = info['responses']
        counts = Counter()
        total = 0
        for i in range(n):
            for j in range(i + 1, n):
                fi, fj = factors[i], factors[j]
                sym = resp.get(fi, {}).get(fj, 'O')
                counts[sym] += 1
                total += 1
        row = {"מומחה/סוכן": info['name'], "סוג": "🤖 סוכן AI" if exp_id.startswith('Synth_') else "🧑 אנושי", "סה\"כ זוגות": total}
        for s in SYMBOLS:
            row[f"{s} (%)"] = round((counts.get(s, 0) / total * 100) if total else 0, 1)
        row["_non_o_pct"] = round(100 - row["O (%)"], 1)
        rows.append(row)
    return pd.DataFrame(rows)

def compute_ssim_density(ssim_df, factors):
    """מחשב איזה אחוז מהזוגות במטריצת ה-SSIM סומנו כבעלי קשר ישיר (לא O ולא קונפליקט)."""
    n = len(factors)
    total, non_o, conflicts = 0, 0, 0
    for i in range(n):
        for j in range(i + 1, n):
            val = ssim_df.iloc[i, j]
            total += 1
            if val == 'C':
                conflicts += 1
            elif val not in ('O', ''):
                non_o += 1
    return non_o, conflicts, total

def calculate_ism_matrices():
    """מבצע את כל חישובי הליבה: אגרגציה וזיהוי קונפליקטים."""
    factors = st.session_state['FACTORS']
    n = len(factors)
    expert_data = st.session_state['EXPERT_DATA']
    
    counts = {}
    for i in range(n):
        for j in range(i+1, n):
            counts[(factors[i], factors[j])] = Counter()
            
    for expert in expert_data.values():
        resps = expert['responses']
        for i in range(n):
            for j in range(i+1, n):
                fi, fj = factors[i], factors[j]
                sym = resps.get(fi, {}).get(fj, 'O')
                counts[(fi, fj)][sym] += 1
                
    ssim = pd.DataFrame('', index=factors, columns=factors)
    conflicts = []
    total_experts = len(expert_data)

    if total_experts == 0:
        return None, None, None, None, None

    for (fi, fj), cnt in counts.items():
        if not cnt:
            ssim.loc[fi, fj] = 'O'
            continue
            
        top_symbol, top_count = cnt.most_common(1)[0]
        
        is_conflict = (top_count * 2 <= total_experts)
        if len(cnt) > 1:
            if top_count == cnt.most_common(2)[1][1]:
                is_conflict = True
                
        if is_conflict:
            ssim.loc[fi, fj] = 'C'
            conflicts.append({'pair': (fi, fj), 'counts': cnt})
        else:
            ssim.loc[fi, fj] = top_symbol
            
        ssim.loc[fi, fi] = '1'
        ssim.loc[fj, fj] = '1'

    return ssim, conflicts, None, None, None

def solve_conflicts_and_finalize(ssim, conflicts):
    """פותר קונפליקטים עם AI, מתעד ביומן, ומחשב את שאר המטריצות."""
    ai_logs = []

    for conf in conflicts:
        fi, fj = conf['pair']
        justs = st.session_state['JUSTIFICATIONS'].get((fi, fj), [])
        
        time.sleep(0.1)
        ai_res = call_ai_analysis(conf, justs, fi, fj)
        
        rec = None
        explanation = "לא זוהה הסבר"

        rec_match = re.search(r'RECOMMENDATION:\s*[\*\[\("\']*\s*([VAXO])\b', ai_res, re.IGNORECASE)
        if rec_match:
            rec = rec_match.group(1).upper()
        rat_match = re.search(r'RATIONALE:\s*(.*)', ai_res, re.DOTALL)
        if rat_match:
            explanation = rat_match.group(1).strip()

        if rec not in SYMBOLS:
            rec = conf['counts'].most_common(1)[0][0]
        
        ai_logs.append({
            "זוג גורמים": f"{fi} ↔ {fj}",
            "הצבעות": str(dict(conf['counts'])),
            "הכרעת AI": rec,
            "נימוק ה-AI": explanation
        })
        
        ssim.loc[fi, fj] = rec
        
    st.session_state['AI_LOG'] = ai_logs

    final_ssim = ssim.copy()
    factors = final_ssim.index
    for i in range(len(factors)):
        for j in range(i+1, len(factors)):
            sym = final_ssim.iloc[i, j]
            if sym == 'V':
                final_ssim.iloc[j, i] = 'A'
            elif sym == 'A':
                final_ssim.iloc[j, i] = 'V'
            elif sym == 'X':
                final_ssim.iloc[j, i] = 'X'
            elif sym == 'O':
                final_ssim.iloc[j, i] = 'O'
                
    irm = pd.DataFrame(0, index=factors, columns=factors)
    for i in range(len(factors)):
        for j in range(len(factors)):
            if i == j:
                irm.iloc[i, j] = 1
                continue
            sym = final_ssim.iloc[i, j]
            if sym in ['V', 'X']:
                irm.iloc[i, j] = 1
                
    frm_df = transitive_closure(irm)

    micmac = classify_micmac(frm_df.sum(axis=1), frm_df.sum(axis=0))
    st.session_state['SSIM_INIT'] = ssim.copy()  # מטריצה ראשונית עם קונפליקטים (C)
    st.session_state['FINAL_SSIM'] = final_ssim.copy()  # מטריצה אחרי פתרון קונפליקטים
    
    return final_ssim, irm, frm_df, micmac

# ==============================================================================
# IV. מנוע AI מאוחד (OpenRouter + DuckDuckGo - חינם!)
# ==============================================================================
def _ddg_search(query, max_results=4):
    """חיפוש אינטרנטי חינמי דרך DuckDuckGo."""
    if not DDGS_AVAILABLE:
        return []
    try:
        with DDGS() as ddgs:
            return list(ddgs.text(query, max_results=max_results))
    except:
        return []

def _call_openrouter(full_prompt, system_context):
    """שולח בקשה למודל החינמי דרך OpenRouter (Gemma)."""
    if not OPENAI_AVAILABLE:
        raise Exception("ספריית openai לא מותקנת")
    if AI_API_KEY == "PLACEHOLDER":
        raise Exception("לא הוגדר מפתח OpenRouter (OPENROUTER_API_KEY) ב-Secrets")

    client = OpenAI(api_key=AI_API_KEY, base_url="https://openrouter.ai/api/v1")
    messages = [
        {"role": "system", "content": system_context},
        {"role": "user", "content": full_prompt}
    ]

    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model=AI_MODEL_NAME,
                messages=messages,
                temperature=0.7,
                max_tokens=3000
            )
            return response.choices[0].message.content
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2)

def _call_anthropic(full_prompt, system_context):
    """שולח בקשה ל-Claude Sonnet 5 (Anthropic) כסוכן AI לאיכות גבוהה."""
    if not ANTHROPIC_AVAILABLE:
        raise Exception("ספריית anthropic לא מותקנת (הוסף 'anthropic' ל-requirements.txt)")

    api_key = st.session_state.get('ANTHROPIC_API_KEY', '')
    if not api_key:
        raise Exception("לא הוזן מפתח API של Anthropic. הזן אותו בטאב 'מנוע AI'.")

    workspace_id = st.session_state.get('ANTHROPIC_WORKSPACE_ID', '').strip()
    extra_headers = {"anthropic-workspace-id": workspace_id} if workspace_id else None
    client = anthropic.Anthropic(api_key=api_key, default_headers=extra_headers)

    for attempt in range(3):
        try:
            response = client.messages.create(
                model=ANTHROPIC_MODEL_NAME,
                max_tokens=3000,
                system=system_context,
                output_config={"effort": ANTHROPIC_EFFORT},
                messages=[{"role": "user", "content": full_prompt}]
            )
            record_ai_usage(response.usage.input_tokens, response.usage.output_tokens)
            return "".join(b.text for b in response.content if b.type == "text")
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2)

def call_ai_unified(prompt, system_context="", use_search=False, search_query=None):
    """
    פונקציית-העל היחידה לכל קריאות ה-AI באפליקציה.
    מנתבת לספק שנבחר (OpenRouter החינמי או Claude Sonnet 5 של Anthropic).
    מחזירה: (תשובה, רשימת מקורות)
    """
    provider = st.session_state.get('AI_PROVIDER', 'openrouter')

    full_prompt = prompt
    citations = []

    if use_search:
        results = _ddg_search(search_query or f"{system_context} {prompt[:150]}", max_results=4)
        search_ctx = "\n\nמקורות מהאינטרנט:\n"
        for r in results:
            search_ctx += f"- {r.get('title', '')}: {r.get('body', '')} ({r.get('href', '')})\n"
            if r.get('href'):
                citations.append(r.get('href'))
        full_prompt = f"{search_ctx}\n\n---\n\n{prompt}"

    if provider == 'anthropic':
        text = _call_anthropic(full_prompt, system_context)
    else:
        text = _call_openrouter(full_prompt, system_context)

    return text, citations

def _extract_balanced_json(text, open_char='{', close_char='}'):
    """מאתר את בלוק ה-JSON הראשון והמאוזן בטקסט (סופר סוגריים, מתעלם מתוכן בתוך מחרוזות)."""
    start = text.find(open_char)
    if start == -1:
        return None
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        c = text[i]
        if in_string:
            if escape:
                escape = False
            elif c == '\\':
                escape = True
            elif c == '"':
                in_string = False
        else:
            if c == '"':
                in_string = True
            elif c == open_char:
                depth += 1
            elif c == close_char:
                depth -= 1
                if depth == 0:
                    return text[start:i + 1]
    return None

def _try_parse_json(raw_text, open_char='{', close_char='}'):
    """מנסה לחלץ ולפרסר JSON מתוך תשובת AI. מחזיר (data, error) - error=None בהצלחה."""
    block = _extract_balanced_json(raw_text, open_char, close_char)
    if block is None:
        return None, "לא נמצא בלוק JSON בתשובת ה-AI"
    # תיקון נפוץ: פסיק מיותר לפני סגירת אובייקט/רשימה
    cleaned = re.sub(r',(\s*[}\]])', r'\1', block)
    try:
        return json.loads(cleaned), None
    except json.JSONDecodeError as e:
        return None, f"{e} (בבלוק שחולץ: ...{cleaned[max(0, e.pos-40):e.pos+40]}...)"

def call_ai_json(prompt, system_context, open_char='{', close_char='}', max_retries=2, use_search=False, search_query=None):
    """
    קורא ל-AI ומצפה לתשובת JSON. אם הפרסור נכשל (שגיאת פורמט נפוצה אצל מודלי שפה),
    מנסה שוב עד max_retries פעמים תוך שליחת שגיאת הפרסור בחזרה למודל לתיקון עצמי.
    """
    current_prompt = prompt
    last_error = None
    for attempt in range(max_retries + 1):
        text, citations = call_ai_unified(current_prompt, system_context, use_search=(use_search and attempt == 0), search_query=search_query)
        data, err = _try_parse_json(text, open_char, close_char)
        if err is None:
            return data, citations
        last_error = err
        current_prompt = (
            f"{prompt}\n\n---\n"
            f"שים לב: בתשובה הקודמת שלך היתה שגיאת תחביר ב-JSON: {err}\n"
            f"החזר אך ורק JSON תקין ומלא (ללא הערות, ללא ```), עם פסיק בין כל שני איברים ברשימה/אובייקט וללא פסיק אחרי האיבר האחרון."
        )
    raise ValueError(f"תשובת ה-AI לא הייתה JSON תקין גם אחרי {max_retries} ניסיונות תיקון: {last_error}")

def call_ai_analysis(conflict_data, justifications, f_i, f_j):
    """פונה ל-OpenRouter להכרעה בקונפליקטים בטאב 2."""
    try:
        counts = conflict_data['counts']
        total = sum(counts.values())
        counts_str = ", ".join(f"{k}: {v} ({v / total:.0%})" for k, v in counts.most_common())
        justs_text = "\n".join([f"- {j['expert']} ({j['symbol']}): {j['text']}" for j in justifications]) or "(לא נמסרו נימוקים)"

        prompt = f"""מומחים חלוקים לגבי הקשר הישיר בין "{f_i}" (הגורם הראשון) לבין "{f_j}" (הגורם השני).
משמעות הסימנים: V = הראשון משפיע ישירות על השני; A = השני משפיע ישירות על הראשון;
X = השפעה הדדית ישירה; O = אין השפעה ישירה ביניהם.
התפלגות ההצבעות: {counts_str}
נימוקי המומחים (ייתכן שחלק מהמצביעים לא נימקו):
{justs_text}

קבע את ההכרעה הסופית לפי עוצמת הטיעונים ולא לפי מספרם בלבד.
הערה: רק השפעה *ישירה* נחשבת - קשר עקיף דרך גורם שלישי, או מתאם כללי, מצדיקים O.
אם הטיעונים לקשר ישיר אינם משכנעים, בחר O. X רק כאשר יש טיעון משכנע לשני הכיוונים.
החזר בדיוק בפורמט:
RECOMMENDATION: <אחת מהאותיות V, A, X, O>
RATIONALE: <נימוק קצר>"""

        text, _ = call_ai_unified(prompt, "אתה שופט אקדמי אובייקטיבי בניתוח ISM.", use_search=False)
        return text
    except Exception as e:
        vote = conflict_data['counts'].most_common(1)[0][0]
        return f"RECOMMENDATION: {vote}\nRATIONALE: שגיאת AI ({str(e)})."

def _research_factors(topic, num_factors):
    """חוקר את נושא הבעיה (כולל חיפוש באינטרנט) וממליץ על גורמים לניתוח ISM-MICMAC."""
    prompt = f"""נושא הבעיה לניתוח: "{topic}".
חקור את הנושא והמלץ על {num_factors} גורמים מרכזיים לניתוח ISM-MICMAC של הבעיה.

דרישות:
- כל גורם הוא מושג אחד ברור, ברמת הפשטה דומה לשאר הגורמים, ללא חפיפה ביניהם.
- שם הגורם קצר (2-5 מילים) וללא פסיקים.
- כלול גם גורמי שורש (שמניעים אחרים) וגם גורמי תוצאה (שמושפעים מאחרים), כדי שלמבנה ההיררכי תהיה משמעות.
- העדף גורמים שמופיעים בספרות המקצועית או במקורות שנמצאו בחיפוש.

החזר אך ורק JSON (רשימה, ללא טקסט נוסף לפני/אחרי, ללא ```), עם {num_factors} רשומות בדיוק:
[{{"name": "שם הגורם", "description": "הסבר קצר מה הגורם כולל", "rationale": "למה הוא רלוונטי לבעיה"}}]"""

    data, citations = call_ai_json(
        prompt,
        "אתה חוקר מערכות מומחה בזיהוי גורמים לניתוח ISM-MICMAC.",
        open_char='[', close_char=']',
        use_search=True,
        search_query=f"{topic} גורמים משפיעים",
    )
    factors = []
    for item in (data if isinstance(data, list) else []):
        name = str(item.get("name", "")).replace(",", " -").strip()
        if name:
            factors.append({
                "name": name,
                "description": str(item.get("description", "")).strip(),
                "rationale": str(item.get("rationale", "")).strip(),
            })
    return factors, citations

def _get_ai_expert_recommendations(topic, factors, num_experts=3):
    """ייעוץ AI לבחירת מומחים."""
    prompt = f"""המלץ על {num_experts} תפקידי מומחים לבעיה: "{topic}". גורמים: {factors}.
החזר רק JSON (רשימה, ללא טקסט נוסף לפני/אחרי, ללא ```):
[{{"role": "שם התפקיד", "expertise": "מומחיות", "rationale": "נימוק"}}]"""

    data, _ = call_ai_json(prompt, "אתה יועץ אסטרטגי ל-ISM.", open_char='[', close_char=']', use_search=True)
    return data

def _simulate_synthetic_expert(role_info, factors):
    """
    סימולציית סוכן AI עם חיפוש אינטרנטי.
    הפרומפט מפרט את הזוגות בשמותיהם המלאים (במקום סכמה עם דוגמת "V" שמודלים נוטים
    להעתיק כמעט לכל זוג), ומדגיש ש-O הוא ברירת המחדל הסטטיסטית - כדי למנוע מטריצות
    שבהן כמעט כל הזוגות מסומנים כבעלי קשר ישיר.
    """
    role = role_info['role']
    n = len(factors)
    pairs = [(factors[i], factors[j]) for i in range(n) for j in range(i + 1, n)]
    pairs_list = "\n".join(f'{idx + 1}. "{fi}"  מול  "{fj}"' for idx, (fi, fj) in enumerate(pairs))

    prompt = f"""עליך להעריך קשר השפעה ישיר בין {len(pairs)} זוגות גורמים, זוג אחר זוג:
{pairs_list}

לכל זוג, קבע האם יש קשר השפעה *ישיר* (לא עקיף דרך גורם שלישי!) על פי ההגדרות:
- V: הגורם הראשון בזוג משפיע ישירות על השני.
- A: הגורם השני בזוג משפיע ישירות על הראשון.
- X: יש השפעה הדדית ישירה בין השניים.
- O: אין קשר השפעה ישיר וברור בין השניים.

חשוב מאוד: ברוב המקרים אין קשר השפעה ישיר בין שני גורמים אקראיים. סמן V/A/X רק כאשר יש לכך
הצדקה עניינית וברורה מתחום המומחיות שלך - אחרת סמן O. אל תסמן V/A/X בגלל קשר עקיף, קורלציה
כללית, או "יכול להיות שיש קשר כלשהו". צפי סביר הוא שרוב הזוגות יסומנו O.

החזר אך ורק JSON (ללא טקסט נוסף לפני/אחרי, ללא ```), כרשימה שטוחה עם רשומה אחת לכל זוג
שפורט למעלה, בדיוק בפורמט הבא (relation הוא בדיוק אחת מהאותיות V,A,X,O):
[{{"factor_i": "<הגורם הראשון בזוג>", "factor_j": "<הגורם השני בזוג>", "relation": "V", "justification": "נימוק קצר"}}]"""

    data, citations = call_ai_json(
        prompt,
        f"אתה מומחה: {role}. {role_info.get('expertise','')}",
        open_char='[', close_char=']',
        use_search=True
    )

    matrix = {}
    for item in (data if isinstance(data, list) else []):
        fi, fj = item.get("factor_i"), item.get("factor_j")
        if fi not in factors or fj not in factors:
            continue
        matrix.setdefault(fi, {})[fj] = {
            "relation": item.get("relation", "O"),
            "justification": item.get("justification", ""),
        }
    return matrix, citations

def _inject_synthetic_data_or(role_info, matrix_data, factors, citations=[], instance_label=None):
    """הזנת נתונים סינתטיים עם מקורות מהאינטרנט."""
    synth_id = f"Synth_{uuid.uuid4().hex[:10]}"

    responses, justs = {}, {}
    for f_i in factors:
        if f_i not in matrix_data:
            continue
        responses[f_i] = {}
        for f_j in factors:
            pd_ = matrix_data.get(f_i, {}).get(f_j)
            if not pd_:
                continue
            sym = pd_.get("relation", "O").upper()
            reason = pd_.get("justification", "")
            if sym not in ['V','A','X','O']:
                sym = 'O'
            responses[f_i][f_j] = sym
            # גם נימוקי O נשמרים, כדי ששופט הקונפליקטים ישמע את שני הצדדים
            if reason:
                justs.setdefault((f_i, f_j), []).append({
                    "expert": role_info['role'] + (f" {instance_label}" if instance_label else ""),
                    "symbol": sym,
                    "text": f"🤖 {reason}"
                })
    
    display_name = f"סוכן AI - {role_info['role']}"
    if instance_label:
        display_name += f" {instance_label}"
    storage.save_expert(
        synth_id, display_name, role_info.get('expertise', ''), responses,
        justifications=[{'pair': pair, **j} for pair, items in justs.items() for j in items],
        citations=citations, db_path=DB_PATH,
    )
    sync_from_db()
    return synth_id

def _call_ai_with_context(prompt, extra_context=""):
    """פונקציה מרכזית לבקשות AI עם הקשר אוטומטי של הפרויקט."""
    ctx = f"אתה יועץ אסטרטגי מומחה לניתוח ISM-MICMAC. "
    ctx += f"פרויקט נוכחי מכיל {len(st.session_state['FACTORS'])} גורמים: {', '.join(st.session_state['FACTORS'])}. "
    ctx += f"מספר מומחים שהשיבו: {len(st.session_state['EXPERT_DATA'])}. "
    if 'RESULTS' in st.session_state and st.session_state['RESULTS']:
        ctx += "הניתוח הושלם וקיימות תוצאות MICMAC. "
    if extra_context:
        ctx += f"\n הקשר ספציפי לבקשה זו: {extra_context}"

    full_prompt = f"{ctx}\n\nבקשת המשתמש:\n{prompt}"
    text, _ = call_ai_unified(full_prompt, "אתה יועץ אסטרטגי ל-ISM.", use_search=False)
    return text

def _render_ai_chat():
    """פונקציה יחידה ומלאה לניהול הצ'אט."""
    if "ai_chat_history" not in st.session_state:
        st.session_state["ai_chat_history"] = []

    col_btn, _ = st.columns([5, 1])
    with col_btn:
        if st.button("🗑️ נקה היסטוריית צ'אט", key="clear_chat_btn"):
            st.session_state["ai_chat_history"] = []
            st.rerun()

    if prompt := st.chat_input("שאל שאלה על הגורמים, המתודולוגיה, או בקש המלצות..."):
        st.session_state["ai_chat_history"].append({"role": "user", "content": prompt})
        
        with st.chat_message("assistant"):
            with st.spinner("🤖 ה-AI מנתח את נתוני הפרויקט..."):
                reply = _call_ai_with_context(prompt)
                st.markdown(reply, unsafe_allow_html=True)
                st.session_state["ai_chat_history"].append({"role": "assistant", "content": reply})

    for msg in reversed(st.session_state.get("ai_chat_history", [])):
        st.chat_message(msg["role"]).markdown(msg["content"], unsafe_allow_html=True)

def _render_ai_report_generator():
    """מחולל דוח אסטרטגי אוטומטי."""
    st.markdown("#### 📄 מחולל דוח ניתוח אסטרטגי")
    report_type = st.selectbox("בחר סוג דוח", ["דוח מנהלים תמציתי", "דוח טכני מפורט", "המלצות התערבות אופטימליות"])
    if st.button("צור דוח עכשיו", key="btn_gen_report"):
        with st.spinner("📝 כותב דוח מקצועי..."):
            prompt = f"כתוב {report_type} עבור מערכת ה-ISM הנוכחית. כלול: תקציר מנהלים, גורמי מפתח (Drivers), אזהרות סיכון, והמלצות מעשיות להשקעת משאבים."
            report = _call_ai_with_context(prompt, extra_context=f"סוג הדוח המבוקש: {report_type}")
            st.success("✅ הדוח חולל בהצלחה!")
            st.download_button("📥 הורד כקובץ טקסט", report, file_name="ISM_AI_Report.txt", mime="text/plain")
            st.markdown("---")
            st.text_area("תצוגה מקדימה של הדוח:", report, height=300)

def _render_ai_data_validator():
    """בדיקת איכות ועקביות תשובות מומחים."""
    st.markdown("#### 🔍 ניתוח איכות ואמינות נתונים")
    st.write("ה-AI ינתח את דפוסי התשובות של המומחים, יזהה סתירות פנימיות, ויחזיר דוח אובייקטיבי.")
    if st.button("הפעל בדיקת איכות נתונים", key="btn_validate"):
        if not st.session_state['EXPERT_DATA']:
            st.warning("️ אין נתוני מומחים לניתוח. אנא אסוף תשובות תחילה.")
            return
            
        with st.spinner(" מנתח עקביות והיגיון מערכתי..."):
            prompt = "נתח את איכות התשובות שנאספו מהמומחים. זהה: 1. סתירות לוגיות בין מומחים שונים. 2. גורמים שזכו להסכמה גורפת. 3. המלצות לשיפור איסוף הנתונים או ניסוח השאלות."
            validation_report = _call_ai_with_context(prompt, extra_context="נתוני מומחים קיימים במערכת.")
            st.success("✅ ניתוח האיכות הושלם!")
            st.markdown(validation_report)

def _show_saved_expert_recommendations():
    """הצגת המלצות מומחים שמורות."""
    if 'EXPERT_RECOMMENDATIONS' in st.session_state:
        with st.expander(" הצג המלצות מומחים שמורות"):
            st.markdown(st.session_state['EXPERT_RECOMMENDATIONS'])

def color_ssim_conflicts(val):
    """צביעת תאי קונפליקט במטריצת SSIM."""
    if val == 'C':
        return 'background-color: #fee2e2; color: #7f1d1d; font-weight: 900;'
    elif val == 'V':
        return 'background-color: #dcfce7; color: #14532d;'
    elif val == 'A':
        return 'background-color: #dbeafe; color: #1e3a8a;'
    elif val == 'X':
        return 'background-color: #fef9c3; color: #713f12;'
    return ''
    
def _render_factor_research():
    """חקר נושא הבעיה והמלצה על גורמים, עם אפשרות להזין אותם לדף הגדרות השאלון."""
    st.subheader("🔬 חקר הנושא והמלצה על גורמים")
    topic = (st.session_state.get('TOPIC') or st.session_state.get('txt_topic_tab1') or '').strip()
    if not topic:
        st.warning("⚠️ לא הוגדר נושא בעיה. הגדר אותו בטאב 'הגדרות שאלון' (שדה 'נושא הבעיה') כדי שה-AI יוכל לחקור אותו.")
        return
    st.write(f"📌 **נושא:** {topic}")

    num_factors = int(st.number_input("כמות גורמים מבוקשת", min_value=3, max_value=25, value=8, step=1, key="num_research_factors"))
    pairs = num_factors * (num_factors - 1) // 2
    st.caption(f"{num_factors} גורמים = {pairs} זוגות שכל מומחה או סוכן יעריך.")
    if num_factors > 15:
        st.warning(f"⚠️ {pairs} זוגות לכל משיב: הסימולציה תהיה ארוכה ויקרה יותר, ושאלון כזה קשה למילוי ע\"י מומחים אנושיים.")

    if st.button("🔬 חקור את הנושא והמלץ על גורמים", key="btn_research_factors"):
        with st.spinner("🤖 חוקר את הנושא ומחפש מקורות..."):
            try:
                recs, citations = _research_factors(topic, num_factors)
                st.session_state['AI_RECOMMENDED_FACTORS'] = recs
                st.session_state['AI_FACTOR_CITATIONS'] = citations
                st.session_state['AI_FACTOR_RECS_VERSION'] = st.session_state.get('AI_FACTOR_RECS_VERSION', 0) + 1
            except Exception as e:
                st.error(f"❌ {e}")

    recs = st.session_state.get('AI_RECOMMENDED_FACTORS')
    if not recs:
        return

    st.markdown(f"**{len(recs)} גורמים מומלצים.** סמן אילו לכלול; אפשר לערוך את שמות הגורמים ישירות בטבלה.")
    editor_df = pd.DataFrame([
        {"לכלול": True, "גורם": r["name"], "תיאור": r["description"], "נימוק": r["rationale"]} for r in recs
    ])
    edited = st.data_editor(
        editor_df,
        key=f"factor_recs_editor_{st.session_state.get('AI_FACTOR_RECS_VERSION', 0)}",
        hide_index=True,
        width="stretch",
        disabled=["תיאור", "נימוק"],
        column_config={"לכלול": st.column_config.CheckboxColumn("לכלול", width="small")},
    )

    citations = st.session_state.get('AI_FACTOR_CITATIONS') or []
    if citations:
        with st.expander("🌐 מקורות שנמצאו בחיפוש"):
            for url in citations:
                st.markdown(f"- {url}")

    mode = st.radio(
        "אופן ההזנה לדף הגדרות השאלון",
        ["החלף את רשימת הגורמים הקיימת", "הוסף לרשימת הגורמים הקיימת"],
        horizontal=True,
        key="factor_insert_mode",
    )
    if st.button("📥 הזן לדף הגדרות השאלון", key="btn_insert_factors"):
        chosen = [str(name).replace(",", " -").strip() for name, include in zip(edited["גורם"], edited["לכלול"]) if include]
        chosen = [c for c in chosen if c]
        if not chosen:
            st.error("לא נבחר אף גורם.")
            return
        merged = []
        if mode.startswith("הוסף"):
            merged = [x.strip() for x in st.session_state.get('txt_factors_tab1', '').split(',') if x.strip()]
        seen = {m.casefold() for m in merged}
        for c in chosen:
            if c.casefold() not in seen:
                merged.append(c)
                seen.add(c.casefold())
        st.session_state['PENDING_FACTORS_TEXT'] = ",\n".join(merged)
        st.session_state['FACTORS_INSERTED_NOTICE'] = len(merged)
        st.rerun()

    inserted = st.session_state.pop('FACTORS_INSERTED_NOTICE', None)
    if inserted:
        st.success(f"✅ רשימה של {inserted} גורמים הוזנה לטאב 'הגדרות שאלון'. עבור לשם, בדוק אותה ולחץ 'שמור ועדכן הכל' כדי להחיל.")

@st.fragment(run_every=2)
def _render_ai_usage_live():
    """לוח צריכת טוקנים ועלות - מתרענן אוטומטית כל 2 שניות."""
    usage = st.session_state['AI_USAGE']
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("קריאות למודל", usage['calls'])
    c2.metric("טוקני קלט", f"{usage['input_tokens']:,}")
    c3.metric("טוקני פלט", f"{usage['output_tokens']:,}")
    c4.metric("עלות מצטברת", f"${usage['cost']:.4f}")
    st.caption(
        f"תמחור {ANTHROPIC_MODEL_NAME}: ${ANTHROPIC_PRICE_INPUT_PER_M:.2f} למיליון טוקני קלט, "
        f"${ANTHROPIC_PRICE_OUTPUT_PER_M:.2f} למיליון טוקני פלט. העלות מחושבת לפי הצריכה שדווחה ע\"י ה-API, בקירוב "
        "(לא כולל cache). הנתונים נשמרים לסשן הנוכחי בלבד."
    )
    if usage['history']:
        st.dataframe(pd.DataFrame(usage['history'][::-1]), width="stretch", hide_index=True)
    else:
        st.info("טרם בוצעו קריאות למודל בתשלום בסשן זה.")

def _render_ai_engine_tab():
    """טאב בקרה ייעודי למנוע ה-AI: בחירת מודל, מפתח API ומעקב עלויות."""
    st.subheader("⚙️ מנוע ה-AI של המערכת")
    st.caption("המודל הנבחר משמש בכל מקום באפליקציה שבו מופעל AI: הכרעת קונפליקטים, סוכני מומחה סינתטיים, צ'אט חכם, מחולל דוחות ובדיקת איכות נתונים.")

    provider_options = {
        'openrouter': "🆓 חינמי — OpenRouter (Gemma)",
        'anthropic': "⭐ בתשלום — Anthropic Claude Sonnet 5 (effort: medium)",
    }
    current = st.session_state.get('AI_PROVIDER', 'openrouter')
    selected = st.radio(
        "סוג המודל",
        options=list(provider_options.values()),
        index=list(provider_options.keys()).index(current),
        key="ai_provider_radio",
    )
    st.session_state['AI_PROVIDER'] = [k for k, v in provider_options.items() if v == selected][0]

    st.markdown("---")
    st.markdown("#### 🔑 מפתח API")
    key_val = st.text_input(
        "מפתח Anthropic API",
        value=st.session_state.get('ANTHROPIC_API_KEY', ''),
        type="password",
        placeholder="sk-ant-...",
        help="נשמר בזיכרון הסשן בלבד ואינו נכתב לקובץ.",
        key="anthropic_key_input",
    )
    if key_val != st.session_state.get('ANTHROPIC_API_KEY', ''):
        st.session_state['ANTHROPIC_API_KEY'] = key_val

    ws_val = st.text_input(
        "Workspace ID (רק אם המפתח הוא מפתח ארגוני ולא משויך ל-Workspace ספציפי)",
        value=st.session_state.get('ANTHROPIC_WORKSPACE_ID', ''),
        placeholder="wrkspc-...",
        help="נדרש רק אם מתקבלת שגיאה 'API key is not scoped to a workspace'. ניתן למצוא את ה-ID בהגדרות ה-Workspace בקונסולת Anthropic.",
        key="anthropic_workspace_input",
    )
    if ws_val != st.session_state.get('ANTHROPIC_WORKSPACE_ID', ''):
        st.session_state['ANTHROPIC_WORKSPACE_ID'] = ws_val

    if not ANTHROPIC_AVAILABLE:
        st.error("ספריית `anthropic` אינה מותקנת. הוסף `anthropic` ל-requirements.txt והתקן מחדש.")
    elif key_val:
        st.success("✅ מפתח Anthropic הוזן." + (" (עם Workspace ID)" if ws_val else ""))
    else:
        st.warning("⚠️ לא הוזן מפתח Anthropic — נדרש לשימוש במודל בתשלום.")
    st.caption(f"סטטוס OpenRouter (חינמי): {'✅ מוגדר' if AI_API_KEY != 'PLACEHOLDER' else '❌ חסר OPENROUTER_API_KEY ב-Secrets'}")

    st.markdown("---")
    st.markdown("#### 📊 צריכה ועלות — מודל בתשלום (בזמן אמת)")
    _render_ai_usage_live()
    if st.button("🔄 אפס מונה צריכה", key="btn_reset_usage"):
        st.session_state['AI_USAGE'] = {'calls': 0, 'input_tokens': 0, 'output_tokens': 0, 'cost': 0.0, 'history': []}
        st.rerun()

# ==============================================================================
# V. מסכים (Screens)
# ==============================================================================
def build_excel_report():
    """דוח Excel מלא: נתוני המומחים, הנימוקים ויומן ה-AI, ואם הורץ ניתוח - גם כל המטריצות, הרמות ושלוש שיטות ה-MICMAC."""
    factors = st.session_state['FACTORS']
    expert_data = st.session_state['EXPERT_DATA']
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        pd.DataFrame(
            [{'מזהה': k, 'שם': v['name'], 'תפקיד': v['role']} for k, v in expert_data.items()],
            columns=['מזהה', 'שם', 'תפקיד'],
        ).to_excel(writer, sheet_name='מומחים', index=False)

        all_responses = []
        for expert_info in expert_data.values():
            row = {'שם המומחה': expert_info['name'], 'תפקיד': expert_info['role']}
            for i in range(len(factors)):
                for j in range(i + 1, len(factors)):
                    f_i, f_j = factors[i], factors[j]
                    row[f"{f_i} → {f_j}"] = expert_info['responses'].get(f_i, {}).get(f_j, 'O')
            all_responses.append(row)
        if all_responses:
            pd.DataFrame(all_responses).to_excel(writer, sheet_name='תשובות_מומחים', index=False)

        just_records = [
            {'זוג גורמים': f"{pair[0]} ↔ {pair[1]}", 'מומחה': j['expert'], 'סמל': j['symbol'], 'נימוק': j['text']}
            for pair, justs in st.session_state['JUSTIFICATIONS'].items() for j in justs
        ]
        if just_records:
            pd.DataFrame(just_records).to_excel(writer, sheet_name='נימוקים', index=False)

        citation_records = [
            {'סוכן': expert_data[exp_id]['name'], 'מקור': json.dumps(c, ensure_ascii=False) if isinstance(c, dict) else str(c)}
            for exp_id, cites in st.session_state.get('CITATIONS', {}).items() if exp_id in expert_data for c in cites
        ]
        if citation_records:
            pd.DataFrame(citation_records).to_excel(writer, sheet_name='מקורות_סוכנים', index=False)

        if st.session_state['AI_LOG']:
            pd.DataFrame(st.session_state['AI_LOG']).to_excel(writer, sheet_name='לוג_AI', index=False)

        results = st.session_state.get('RESULTS')
        if results:
            if 'SSIM_INIT' in st.session_state:
                st.session_state['SSIM_INIT'].to_excel(writer, sheet_name='SSIM_ראשוני')
            if 'FINAL_SSIM' in st.session_state:
                st.session_state['FINAL_SSIM'].to_excel(writer, sheet_name='SSIM_סופי')
            results['irm'].to_excel(writer, sheet_name='IRM')
            results['frm'].to_excel(writer, sheet_name='FRM')

            frm = results['frm']
            cycles = ism_cycle_members(frm)
            pd.DataFrame([
                {'רמה': idx + 1, 'גורם': f, 'במעגל השפעה הדדי': 'כן' if f in cycles else ''}
                for idx, lvl in enumerate(compute_ism_levels(frm)) for f in lvl
            ]).to_excel(writer, sheet_name='רמות_ISM', index=False)

            for key, sheet in (('micmac', 'MICMAC_קלאסי'), ('micmac_godet', 'MICMAC_Godet'), ('micmac_katz', 'MICMAC_Katz')):
                results[key].sort_values('DP', ascending=False).to_excel(writer, sheet_name=sheet)

            pd.DataFrame([
                {'מדד': 'רוויית FRM (מחוץ לאלכסון)', 'ערך': round(results['saturation'], 4)},
                {'מדד': 'FRM מנוון לסיווג קלאסי', 'ערך': 'כן' if results['classic_degenerate'] else 'לא'},
                {'מדד': 'חזקת מטריצה (Godet)', 'ערך': results['godet_power']},
                {'מדד': 'מקדם דעיכה α (Katz)', 'ערך': round(results['katz_alpha'], 6)},
                {'מדד': 'מספר מומחים בניתוח', 'ערך': len(results.get('expert_ids', ()))},
            ]).to_excel(writer, sheet_name='סיכום_ניתוח', index=False)
    return buffer.getvalue()

def screen_login():
    """מסך הכניסה הראשי."""
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("<div class='hero-title'>🚦 מערכת ISM MICMAC Pro</div>", unsafe_allow_html=True)
    st.markdown("<div class='hero-subtitle'>כלי תומך החלטה לניתוח מערכתי מורכב, מונע בינה מלאכותית</div>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    c1, c2 = st.columns(2, gap="large")

    with c1:
        with st.container(border=True):
            st.markdown("<span class='login-card-badge badge-admin'>🔐 כניסת מנהל מערכת</span>", unsafe_allow_html=True)
            if not ADMIN_PASSWORD:
                st.warning("כניסת מנהל חסומה: לא הוגדרה סיסמה. הוסף `ADMIN_PASSWORD` (ואופציונלית `ADMIN_USERNAME`) לקובץ `.streamlit/secrets.toml` או כמשתנה סביבה, והפעל מחדש.")
            with st.form("admin_login"):
                u = st.text_input("שם משתמש", placeholder="admin")
                p = st.text_input("סיסמה", type="password")
                if st.form_submit_button("התחבר כמנהל"):
                    if check_admin_credentials(u, p):
                        st.session_state['role'] = 'Admin'
                        st.rerun()
                    else:
                        st.error("פרטים שגויים")

    with c2:
        with st.container(border=True):
            st.markdown("<span class='login-card-badge badge-expert'>📝 כניסת מומחה / משתתף</span>", unsafe_allow_html=True)
            st.caption("אין צורך בסיסמה. מלא את פרטיך כדי להתחיל.")
            with st.form("expert_start"):
                name = st.text_input("שם מלא", placeholder="לדוגמה: ישראל ישראלי")
                role = st.text_input("תפקיד / מחלקה", placeholder="לדוגמה: אגף תנועה")

                if st.form_submit_button("התחל שאלון >>"):
                    if name and role:
                        new_id = f"Exp_{uuid.uuid4().hex[:10]}"
                        st.session_state['current_expert_id'] = new_id
                        st.session_state['current_expert_name'] = name
                        st.session_state['current_expert_role'] = role
                        st.session_state['role'] = 'Expert'
                        st.rerun()
                    else:
                        st.error("חובה למלא שם ותפקיד!")

def screen_expert_form():
    """טופס מילוי המטריצה למומחה."""
    exp_name = st.session_state['current_expert_name']
    factors = st.session_state['FACTORS']
    generic_q = st.session_state.get('GENERIC_QUESTION', DEFAULT_GENERIC_QUESTION)
    st.markdown(f"## 👋 שלום, **{exp_name}**")
    st.info("אנא מלא את הקשרים בין הגורמים הבאים. מטרתנו לזהות את מבנה ההשפעה המערכתי.")

    if not factors:
        st.session_state['FACTORS'] = DEFAULT_FACTORS
        st.rerun()

    with st.form("ssim_survey"):
        responses = {}
        
        for i in range(len(factors)-1):
            f_i = factors[i]
            st.markdown(f"<div style='background-color: #f0f9ff; padding: 15px; border-radius: 10px; margin-top: 30px; margin-bottom: 15px; border-right: 5px solid #0ea5e9;'><h3>🔹 האם הגורם <u>{f_i}</u> משפיע על...</h3></div>", unsafe_allow_html=True)
            
            for j in range(i+1, len(factors)):
                f_j = factors[j]
                q_text = generic_q.format(i=f_i, j=f_j)
                st.markdown(f"#### {q_text}")
                
                c_q, c_txt = st.columns([3, 4])
                
                with c_q:
                    val = st.radio(
                        "סוג הקשר:",
                        options=SYMBOLS,
                        key=f"rad_{i}_{j}",
                        horizontal=True,
                        index=3,
                        help="V: משפיע על, A: מושפע מ, X: הדדי, O: אין קשר"
                    )
                with c_txt:
                    rsn = st.text_input(
                        "נימוק (אופציונלי):",
                        key=f"txt_{i}_{j}",
                        placeholder="הסבר בקצרה..."
                    )
                
                st.markdown("<hr style='margin: 10px 0; border-top: 1px dashed #ccc;'>", unsafe_allow_html=True)
                
                if f_i not in responses:
                    responses[f_i] = {}
                responses[f_i][f_j] = {'s': val, 't': rsn}
            
        if st.form_submit_button("💾 שמור ושלח את כל התשובות"):
            exp_id = st.session_state['current_expert_id']
            clean_res = {fi: {fj: data['s'] for fj, data in row.items()} for fi, row in responses.items()}
            justs = [
                {'pair': (fi, fj), 'expert': exp_name, 'symbol': data['s'], 'text': data['t']}
                for fi, row in responses.items() for fj, data in row.items() if data['t']
            ]
            storage.save_expert(exp_id, exp_name, st.session_state['current_expert_role'],
                                clean_res, justifications=justs, db_path=DB_PATH)

            st.success("✅ התשובות נקלטו בהצלחה! תודה רבה.")
            time.sleep(2)
            st.session_state['role'] = None
            st.rerun()

def screen_admin_dashboard():
    """ממשק ניהול."""
    st.title("️ ממשק ניהול (Admin Dashboard)")
    
    with st.sidebar:
        st.header("תפריט מנהל")
        if st.button("🚪 יציאה"):
            st.session_state['role'] = None
            st.rerun()
        st.markdown("---")
        status_icon = '✅' if is_ai_ready() else '❌'
        st.info(f"🤖 מודל AI פעיל: **{ai_provider_label()}**\n\nסטטוס API: {status_icon}\n\n💰 עלות מצטברת: ${st.session_state['AI_USAGE']['cost']:.4f}")
        
        st.markdown("---")
        st.subheader("🛑 בקרת סימולציה")
        has_synth_data = any(k.startswith('Synth_') for k in st.session_state.get('EXPERT_DATA', {}))
        
        if has_synth_data:
            if st.button("️ מחק נתוני סוכני AI", key="btn_clear_synth_sidebar", type="secondary"):
                storage.delete_experts(prefix='Synth_', db_path=DB_PATH)
                st.success("✅ נתוני הסוכנים נמחקו!")
                st.rerun()
        
        if st.button("⏹️ עצור הכל ואפס", key="btn_stop_all_sidebar", type="primary"):
            factors_backup = st.session_state.get('FACTORS', [])
            topic_backup = st.session_state.get('TOPIC', '')
            question_backup = st.session_state.get('GENERIC_QUESTION', DEFAULT_GENERIC_QUESTION)
            storage.delete_experts(db_path=DB_PATH)

            for key in list(st.session_state.keys()):
                if key not in ['FACTORS', 'TOPIC', 'GENERIC_QUESTION', 'role']:
                    del st.session_state[key]
            
            st.session_state['FACTORS'] = factors_backup
            st.session_state['TOPIC'] = topic_backup
            st.session_state['GENERIC_QUESTION'] = question_backup
            
            st.success("✅ המערכת אופסה בהצלחה!")
            st.rerun()

    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📝 הגדרות שאלון", " מעקב וניתוח", " תוצאות סופיות", "🤖 מרכז AI מתקדם", "⚙️ מנוע AI"])

    # --- טאב 1: הגדרות ---
    with tab1:
        st.subheader("📌 הגדרת הבעיה והמערכת")
        
        topic_input = st.text_input(
            "נושא הבעיה / ההקשר הארגוני",
            value=st.session_state.get('TOPIC', ''),
            placeholder="לדוגמה: שיפור בטיחות באתרי בנייה, ייעול תהליכי מיון...",
            key="txt_topic_tab1"
        )
        
        st.markdown("---")
        
        st.subheader("עריכת גורמי המערכת")
        # מצב תיבת הטקסט נשמר במפתח שלה; גורמים שהומלצו במרכז ה-AI ממתינים כאן ומוזנים לפני ציור התיבה
        pending = st.session_state.pop('PENDING_FACTORS_TEXT', None)
        if pending is not None:
            st.session_state['txt_factors_tab1'] = pending
            st.info("📥 הגורמים שהומלצו ע\"י מרכז ה-AI הוזנו לרשימה למטה. עבור עליהם, ערוך במידת הצורך ולחץ **שמור ועדכן הכל** כדי להחיל אותם (השמירה מאפסת את תשובות המומחים שנאספו).")
        elif 'txt_factors_tab1' not in st.session_state:
            st.session_state['txt_factors_tab1'] = ",\n".join(st.session_state['FACTORS'])
        new_f = st.text_area("רשימת הגורמים (כל גורם מופרד בפסיק)", height=300, key="txt_factors_tab1")
        
        curr_q = st.session_state.get('GENERIC_QUESTION', DEFAULT_GENERIC_QUESTION)
        new_q = st.text_input("נוסח השאלה (השתמש ב-{i} ו-{j} כמשתנים)", value=curr_q, key="txt_question_tab1")
        
        if st.button("💾 שמור ועדכן הכל", key="btn_save_tab1"):
            cleaned = [x.strip() for x in new_f.split(',') if x.strip()]
            if cleaned:
                st.session_state['FACTORS'] = cleaned
                st.session_state['GENERIC_QUESTION'] = new_q
                st.session_state['TOPIC'] = topic_input
                storage.save_settings({'FACTORS': cleaned, 'GENERIC_QUESTION': new_q, 'TOPIC': topic_input}, DB_PATH)

                storage.delete_experts(db_path=DB_PATH)
                st.session_state['EXPERT_DATA'] = {}
                st.session_state['JUSTIFICATIONS'] = {}
                st.session_state['CITATIONS'] = {}
                invalidate_results()
                st.success("✅ הגדרות עודכנו בהצלחה! (כל הנתונים הקודמים אופסו)")
            else:
                st.error("לא ניתן לשמור רשימה ריקה.")

        st.markdown("---")
        _show_saved_expert_recommendations()

    # --- טאב 2: מעקב וניתוח ---
    with tab2:
        st.subheader("סטטוס משיבים")
        data = st.session_state['EXPERT_DATA']
        if not data:
            st.warning("טרם התקבלו תשובות ממומחים.")
        else:
            df = pd.DataFrame.from_dict(data, orient='index')[['name', 'role']]
            st.dataframe(df, width="stretch")
            c1, c2 = st.columns(2)
            c1.metric("סה\"כ משיבים", len(data))
            if c2.button("🗑️ מחק את כל הנתונים", key="btn_clear_all_tab2"):
                storage.delete_experts(db_path=DB_PATH)
                st.rerun()
            
            st.download_button(
                label="📥 הורד דוח נתונים מלא ל-Excel",
                data=build_excel_report(),
                file_name=f"ISM_Report_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="btn_download_excel"
            )

        st.markdown("---")
        st.subheader("ניתוח ופתרון קונפליקטים")
        if len(st.session_state['EXPERT_DATA']) > 0:
            ssim_init, conflicts, _, _, _ = calculate_ism_matrices()

            factors_for_stats = st.session_state['FACTORS']
            non_o, n_conflicts, n_total = compute_ssim_density(ssim_init, factors_for_stats)
            density_pct = round(non_o / n_total * 100, 1) if n_total else 0
            with st.expander("🔎 בדיקת צפיפות ואבחון תשובות", expanded=(density_pct > 60)):
                st.caption("כלי אבחון: ISM אמיתי מצפה שרוב הזוגות יהיו O (ללא קשר ישיר). צפיפות גבוהה מדי לרוב מעידה על סוכן/מומחה שסימן V/A/X כמעט לכל זוג, מה שעלול להביא למטריצת נגישות (FRM) מנוונת שבה כמעט הכל 1 - וללא יכולת להבחין בין גורמים מניעים לתלויים.")
                c1, c2, c3 = st.columns(3)
                c1.metric("זוגות עם קשר ישיר (V/A/X)", f"{non_o}/{n_total}")
                c2.metric("צפיפות קשרים", f"{density_pct}%")
                c3.metric("קונפליקטים בין מומחים", n_conflicts)
                if density_pct > 60:
                    st.warning("⚠️ צפיפות הקשרים גבוהה מהצפוי - סבירות גבוהה למטריצת נגישות מנוונת. בדוק בטבלה למטה אם מומחה/סוכן מסוים מסמן V/A/X כמעט תמיד.")

                stats_df = compute_expert_symbol_stats(factors_for_stats)
                if not stats_df.empty:
                    display_df = stats_df.drop(columns=["_non_o_pct"])
                    st.dataframe(display_df, width="stretch", hide_index=True)
                    biased = stats_df[stats_df["_non_o_pct"] > 70]
                    if not biased.empty:
                        names = ", ".join(biased["מומחה/סוכן"])
                        st.error(f"❌ נראה שהתשובות של **{names}** מוטות מאוד (מעל 70% זוגות מסומנים V/A/X) - שקול להסיר ולהריץ מחדש.")

            if conflicts:
                st.error(f"️ נמצאו {len(conflicts)} קונפליקטים הדורשים הכרעה.")
                
                with st.expander("צפה בפרטי הקונפליקטים"):
                    for c in conflicts:
                        st.write(f"**{c['pair']}**: {dict(c['counts'])}")
                
                if st.button(f"🤖 הפעל AI לפתרון {len(conflicts)} קונפליקטים", key="btn_solve_conflicts"):
                    with st.spinner("ה-AI מנתח נימוקים ומבצע חישובים..."):
                        analyze_and_store(ssim_init, conflicts)
                        st.rerun()

            elif not conflicts and 'RESULTS' not in st.session_state:
                analyze_and_store(ssim_init, [])
                st.rerun()

            if 'RESULTS' in st.session_state:
                results = st.session_state['RESULTS']
                irm, frm = results['irm'], results['frm']
                st.success("✅ הניתוח הושלם.")
                
                # === הצגת מטריצות הקשרים ===
                st.markdown("---")
                st.subheader("📊 מטריצות קשרים (SSIM)")
                
                # מטריצה ראשונית (לפני פתרון קונפליקטים)
                if 'SSIM_INIT' in st.session_state:
                    with st.expander("🔍 מטריצת קשרים ראשונית (SSIM) - לפני פתרון קונפליקטים", expanded=False):
                        st.info("💡 **מקרא:** V=משפיע על, A=מושפע מ, X=הדדי, O=אין קשר, **C=קונפליקט** (דורש הכרעת AI)")
                        st.dataframe(st.session_state['SSIM_INIT'].style.map(color_ssim_conflicts), width="stretch")
                        
                        # ספירת קונפליקטים
                        conflict_count = (st.session_state['SSIM_INIT'] == 'C').sum().sum()
                        if conflict_count > 0:
                            st.warning(f"⚠️ נמצאו **{conflict_count}** קונפליקטים במטריצה (סומנו ב-C)")
                
                # מטריצה סופית (אחרי פתרון קונפליקטים)
                if 'FINAL_SSIM' in st.session_state:
                    with st.expander("✅ מטריצת קשרים סופית (SSIM) - אחרי פתרון קונפליקטים", expanded=False):
                        st.info("💡 **מקרא:** V=משפיע על, A=מושפע מ, X=הדדי, O=אין קשר")
                        st.dataframe(st.session_state['FINAL_SSIM'], width="stretch")
                
                with st.expander("➡️ מטריצת נגישות ראשונית (IRM) - השפעות ישירות בלבד", expanded=False):
                    st.dataframe(irm, width="stretch")

                with st.expander("🎯 מטריצת נגישות סופית (FRM) - עם טרנזיטיביות", expanded=False):
                    st.info("💡 מציגה השפעות ישירות **ועקיפות** בין גורמים")
                    st.dataframe(frm, width="stretch")

                if results['classic_degenerate']:
                    st.warning(
                        f"⚠️ מטריצת הנגישות רוויה: {results['saturation']:.0%} מהתאים מחוץ לאלכסון הם 1. "
                        "זו תוצאה נכונה מתמטית כשקיים מעגל השפעה שעובר דרך רוב הגורמים, אבל הסיווג הקלאסי "
                        "לפי סכומי ה-FRM לא יכול להבחין בין גורמים במצב כזה. בטאב 'תוצאות סופיות' הסיווג "
                        "יוצג לפי MICMAC עקיף (Godet), שמבחין בין הגורמים גם כאן."
                    )
                
                # הצגת לוג ה-AI
                if st.session_state['AI_LOG']:
                    st.markdown("---")
                    st.markdown("### 🧠 דוח החלטות ה-AI")
                    st.dataframe(pd.DataFrame(st.session_state['AI_LOG']), width="stretch")

    # --- טאב 3: תוצאות ---
    with tab3:
        if 'RESULTS' in st.session_state:
            results = st.session_state['RESULTS']
            irm, frm = results['irm'], results['frm']

            st.markdown("### 🏛️ מבנה היררכי (ISM Level Partitioning)")
            st.caption("זהו הפלט המרכזי של ניתוח ה-ISM עצמו (בנפרד מ-MICMAC): חלוקה היררכית של הגורמים לרמות, מהתלוי ביותר (למעלה) למניע ביותר (למטה). גורמים שמגיעים זה לזה (מעגל השפעה הדדי) נמצאים תמיד באותה רמה ומסומנים בכתום.")
            levels = compute_ism_levels(frm)
            cycles = ism_cycle_members(frm)
            if len(levels) == 1 and len(frm) > 1:
                st.warning("⚠️ כל הגורמים נמצאים ברמה אחת: כולם מגיעים זה לזה דרך מעגלי השפעה, ולכן אין היררכיה. זה משקף צפיפות קשרים גבוהה בתשובות - ראה 'בדיקת צפיפות ואבחון תשובות' בטאב 'מעקב וניתוח'.")
            fig_h = plot_ism_hierarchy(levels, irm, cycles)
            st.plotly_chart(fig_h, width="stretch")
            with st.expander("📋 טבלת רמות"):
                level_rows = []
                for idx, lvl in enumerate(levels):
                    in_cycle = [f for f in lvl if f in cycles]
                    tag = f" (מעגל השפעה הדדי: {', '.join(in_cycle)})" if in_cycle else ""
                    level_rows.append({"רמה": f"Level {idx + 1}", "גורמים": ", ".join(lvl) + tag})
                st.dataframe(pd.DataFrame(level_rows), width="stretch", hide_index=True)

            st.markdown("---")
            st.markdown("### 📊 מפת MICMAC ויזואלית")
            method_labels = {
                'classic': "ISM-MICMAC קלאסי (סכומי FRM)",
                'godet': f"MICMAC עקיף - Godet (חזקת מטריצה {results['godet_power']})",
                'katz': f"MICMAC עקיף מצטבר - Katz (α={results['katz_alpha']:.3g})",
            }
            method = st.radio(
                "שיטת חישוב ההשפעה והתלות",
                options=list(method_labels.keys()),
                format_func=method_labels.get,
                index=2 if results['classic_degenerate'] else 0,
                horizontal=True,
                key="micmac_method",
            )
            if results['classic_degenerate']:
                st.info(f"ℹ️ ה-FRM רווי ({results['saturation']:.0%} מהתאים הם 1), ולכן בשיטה הקלאסית כמעט לכל הגורמים יש אותם DP ו-DEP. ברירת המחדל כאן היא MICMAC עקיף מצטבר (Katz), שסופר מסלולי השפעה מכל אורך עם דעיכה ומבחין בין הגורמים גם במצב כזה.")
            if method == 'godet':
                st.caption("ערכי DP/DEP בשיטה זו הם אחוז מסך ההשפעה במערכת (מחושב מחזקות מטריצת ההשפעה הישירה עד להתייצבות הדירוג). במעגל השפעה קצר החזקה הבודדת עלולה להתנודד - במקרה כזה עדיפה שיטת Katz.")
            elif method == 'katz':
                st.caption("ערכי DP/DEP בשיטה זו הם אחוז מסך ההשפעה במערכת, מחושב מסכום כל המסלולים: Σ α^k·M^k = (I − αM)⁻¹ − I, כאשר α = 0.5/ρ(M). מסלול ארוך מקבל משקל קטן יותר, ואין תנודות במעגלים קצרים.")
            micmac = results[{'classic': 'micmac', 'godet': 'micmac_godet', 'katz': 'micmac_katz'}[method]]
            fig = plot_interactive_micmac(micmac)
            st.plotly_chart(fig, width="stretch")

            st.markdown("---")
            st.markdown("### 🏆 נתונים מספריים וסיווג")
            st.dataframe(micmac.sort_values('DP', ascending=False).style.map(color_micmac, subset=['Classification']), width="stretch")

            drivers = micmac[micmac['Classification'].str.contains('Driving')]
            if not drivers.empty:
                st.success(f"📌 **גורמי המפתח המניעים (Drivers):** {', '.join(drivers.index)}")

            with st.expander("צפה במטריצת הנגישות הסופית (FRM)"):
                st.dataframe(frm)

            st.download_button(
                label="📥 הורד דוח מלא ל-Excel (נתונים + תוצאות)",
                data=build_excel_report(),
                file_name=f"ISM_Report_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="btn_download_excel_results"
            )
        else:
            st.info("אנא הרץ ניתוח בטאב הקודם.")

    # --- טאב 4: מרכז AI מתקדם ---
    with tab4:
        st.header("🧠 מרכז ייעוץ וסימולציה מערכתית")
        st.info("זרימת עבודה: 🔬 חקר הנושא והמלצה על גורמים → 1️⃣ זיהוי סוגי המומחים הנדרשים → 2️⃣ כמות מומחים מכל סוג → 3️⃣ הפעלת סוכני AI שימלאו את השאלון, עם נימוקים מבוססי גלישה באינטרנט.")

        if not is_ai_ready():
            st.error(f"⚠️ ספק ה-AI הנוכחי ({ai_provider_label()}) אינו מוגדר או שחסר מפתח API. עבור לטאב 'מנוע AI' כדי להגדיר.")
        else:
            _render_factor_research()
            st.markdown("---")
            st.subheader("שלב 1: הגדרת כמות וזיהוי סוגי מומחים נדרשים")
            st.caption("המספר כאן הוא כמות **סוגי המומחים** (תפקידים שונים, למשל: אנליסט, עורך דין, שוטר, פסיכולוג). לכמות המומחים מכל סוג יש בקרה נפרדת בשלב הבא.")

            col1, col2 = st.columns([1, 3])
            with col1:
                num_expert_types = st.number_input(
                    "כמות סוגי מומחים:",
                    min_value=1,
                    max_value=30,
                    value=3,
                    step=1,
                    help="כמה תפקידי מומחה שונים ה-AI יזהה וימליץ?",
                    key="num_expert_types_tab4"
                )

            topic_ctx = st.session_state.get('TOPIC', 'לא הוגדר')
            factors_ctx = st.session_state['FACTORS']
            with col2:
                st.write(f"📌 **נושא:** `{topic_ctx}` | **גורמים:** {len(factors_ctx)}")

            if st.button(" הפק המלצות לסוגי מומחים", key="btn_advisor_synth_v3"):
                with st.spinner(f"🤖 מנתח ומחפש {num_expert_types} תפקידים מתאימים..."):
                    try:
                        recs = _get_ai_expert_recommendations(topic_ctx, factors_ctx, num_expert_types)
                        st.session_state['AI_RECOMMENDED_EXPERTS'] = recs
                        st.session_state.pop('EXPERT_TYPE_QUANTITIES', None)
                        st.success(f"✅ זוהו {len(recs)} סוגי מומחים רלוונטיים.")
                    except Exception as e:
                        st.error(f"❌ {e}")

            if 'AI_RECOMMENDED_EXPERTS' in st.session_state:
                experts_list = st.session_state['AI_RECOMMENDED_EXPERTS']

                st.markdown("---")
                st.subheader("שלב 2: כמות מומחים מכל סוג")
                st.caption("לכל סוג מומחה שזוהה, קבע כמה סוכני AI עצמאיים (עם שיפוט משלהם) ירוצו מאותו סוג - זה מדמה כמה מומחים אמיתיים מאותו תחום שעשויים לחלוק דעות שונות.")

                quantities = st.session_state.setdefault('EXPERT_TYPE_QUANTITIES', {})
                for idx, exp in enumerate(experts_list):
                    qc1, qc2 = st.columns([4, 1])
                    with qc1:
                        st.info(f"**{idx+1}. {exp['role']}** ({exp.get('expertise','')})\n💡 {exp.get('rationale','')}")
                    with qc2:
                        quantities[idx] = st.number_input(
                            "כמות",
                            min_value=0,
                            max_value=30,
                            value=quantities.get(idx, 1),
                            step=1,
                            key=f"qty_expert_type_{idx}",
                            label_visibility="visible",
                        )

                total_agents = sum(quantities.values())
                st.metric("סה\"כ סוכני AI שיופעלו", total_agents)
                if total_agents > 15:
                    est_minutes = round(total_agents * 5 / 60, 1)
                    st.warning(f"⚠️ {total_agents} סוכנים עם השהיה של 5 שניות ביניהם ייקחו כ-{est_minutes} דקות לפחות, ובהתאם לספק AI בתשלום עלולים לעלות משמעותית יותר. אפשר לעקוב אחרי העלות בזמן אמת בטאב 'מנוע AI'.")

                st.markdown("---")
                st.subheader("שלב 3: הפעלת סוכני AI סינתטיים")
                st.warning("⚠️ הסוכנים ימלאו את השאלון במקום המומחים וינמקו בעזרת מקורות מהאינטרנט. התהליך עשוי לקחת מספר דקות.")

                if st.button("🚀 הפעל סימולציה והזן למערכת", key="btn_sim_synth_v3", disabled=(total_agents == 0)):
                    progress = st.progress(0)
                    status_text = st.empty()
                    run_queue = []
                    for idx, exp in enumerate(experts_list):
                        qty = quantities.get(idx, 0)
                        for inst in range(1, qty + 1):
                            run_queue.append((exp, inst if qty > 1 else None))

                    success_count = 0
                    for i, (exp_role, instance_num) in enumerate(run_queue):
                        label = f"{exp_role['role']}" + (f" #{instance_num}" if instance_num else "")
                        status_text.text(f"🔄 מעבד סוכן {i+1}/{len(run_queue)}: {label}...")

                        try:
                            matrix, citations = _simulate_synthetic_expert(exp_role, factors_ctx)
                            instance_label = f"#{instance_num}" if instance_num else None
                            _inject_synthetic_data_or(exp_role, matrix, factors_ctx, citations, instance_label=instance_label)
                            success_count += 1

                            if i < len(run_queue) - 1:
                                time.sleep(5)

                        except Exception as e:
                            st.error(f"❌ **שגיאה בסוכן {label}:** {e}")

                        progress.progress((i + 1) / len(run_queue))

                    progress.empty()
                    status_text.empty()

                    if success_count > 0:
                        st.success(f"✅ סימולציה הושלמה! {success_count}/{len(run_queue)} סוכנים הוזנו בהצלחה למערכת.")
                        st.info("עבור לטאב 'מעקב וניתוח' כדי לראות את המומחים החדשים ולהריץ את חישובי ה-ISM.")
                        st.rerun()
                    else:
                        st.error("❌ אף סוכן לא הוזן בהצלחה. אנא בדוק את לוג השגיאות למעלה.")
                    
            if any(k.startswith('Synth_') for k in st.session_state['EXPERT_DATA']):
                st.markdown("---")
                col_a, col_b = st.columns(2)
                with col_a:
                    st.info(f"📊 קיימים {len([k for k in st.session_state['EXPERT_DATA'] if k.startswith('Synth_')])} מומחים סינתטיים במערכת")
                with col_b:
                    if st.button("🗑️ מחק רק מומחים סינתטיים", key="btn_clear_synth_v3"):
                        storage.delete_experts(prefix='Synth_', db_path=DB_PATH)
                        st.success("✅ נתוני הסוכנים נמחקו!")
                        st.rerun()
            
            st.markdown("---")
            st.subheader("כלי AI נוספים")
            
            tool_tabs = st.tabs(["💬 צ'אט חכם", "📝 מחולל דוחות", "🔍 בדיקת איכות"])
            
            with tool_tabs[0]:
                _render_ai_chat()
            
            with tool_tabs[1]:
                _render_ai_report_generator()
            
            with tool_tabs[2]:
                _render_ai_data_validator()

    # --- טאב 5: מנוע AI ---
    with tab5:
        _render_ai_engine_tab()

# ==============================================================================
# Main Loop
# ==============================================================================
def hide_streamlit_style():
    """מסתיר את התפריט של המפתחים ואת הפוטר של סטרים-ליט."""
    hide_st_style = """
<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}
</style>
"""
    st.markdown(hide_st_style, unsafe_allow_html=True)

def main():
    st.set_page_config(layout="wide", page_title="ISM Pro 2025")
    apply_advanced_styling()
    init_session_state()
    hide_streamlit_style()

    if st.session_state['role'] == 'Admin':
        screen_admin_dashboard()
    elif st.session_state['role'] == 'Expert':
        screen_expert_form()
    else:
        screen_login()

if __name__ == '__main__':
    main()
