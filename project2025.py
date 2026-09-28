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

# ==============================================================================
# 0. הגדרות מערכת, ספריות ו-API (OpenRouter + DuckDuckGo - חינם!)
# ==============================================================================
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

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

# --- קונפיגורציה ---
ADMIN_USERNAME = "admin_ism"
ADMIN_PASSWORD = "123"

def _get_secret(key, default=""):
    """קורא מפתח מ-st.secrets בבטחה, גם כשלא קיים קובץ secrets.toml כלל."""
    try:
        return st.secrets.get(key, default)
    except Exception:
        return default

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
    """יוצר גרף Plotly אינטראקטיבי ומרשים."""
    df = micmac_df.copy()
    df['Factor'] = df.index

    avg_dp = df['DP'].mean()
    avg_dep = df['DEP'].mean()

    fig = px.scatter(
        df, x='DEP', y='DP',
        text='Factor',
        color='Classification',
        size=[25]*len(df),
        hover_name='Factor',
        hover_data={'DP': True, 'DEP': True, 'Classification': True, 'Factor': False},
        title="<b>מפת ניתוח MICMAC - מיפוי גורמים</b>",
    )

    fig.add_hline(y=avg_dp, line_dash="dash", line_color="gray", annotation_text="ממוצע השפעה")
    fig.add_vline(x=avg_dep, line_dash="dash", line_color="gray", annotation_text="ממוצע תלות")

    fig.update_traces(textposition='top center', textfont_size=14)
    fig.update_layout(
        xaxis_title="<b>Dependence Power (תלות)</b>",
        yaxis_title="<b>Driving Power (השפעה)</b>",
        font=dict(family="Arial", size=16),
        plot_bgcolor='#f8fafc',
        showlegend=True,
        legend_title_text='סיווג הגורם',
        height=700,
        margin=dict(l=40, r=40, t=60, b=40)
    )

    return fig

def plot_ism_hierarchy(levels, irm_df):
    """
    מצייר את דיאגרמת המבנה ההיררכי של ISM (Level Partitioning): הרמה העליונה
    (Level I) היא הגורמים הכי תלויים (ה"תוצאות"), הרמה התחתונה היא הגורמים
    הכי מניעים (ה"שורשים"). גורמים באותה רמה עם יותר מגורם אחד מציינים
    מעגל השפעה הדדי (SCC) שאוחד לרמה משותפת.
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

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=edge_x, y=edge_y, mode='lines',
        line=dict(color='#94a3b8', width=1.5),
        hoverinfo='none', showlegend=False,
    ))
    node_x = [pos[f][0] for f in factors]
    node_y = [pos[f][1] for f in factors]
    node_colors = ['#7C3AED' if len(levels[num_levels - int(pos[f][1])]) > 1 else '#2563EB' for f in factors]
    fig.add_trace(go.Scatter(
        x=node_x, y=node_y, mode='markers+text',
        text=factors, textposition='top center', textfont=dict(size=13),
        marker=dict(size=28, color=node_colors, line=dict(width=2, color='white')),
        hoverinfo='text', showlegend=False,
    ))
    fig.update_layout(
        title="<b>דיאגרמת מבנה ISM היררכית</b> (למעלה: הכי תלוי ⬆️ | למטה: הכי מניע ⬇️ | סגול = חלק ממעגל השפעה הדדי)",
        xaxis=dict(visible=False),
        yaxis=dict(visible=False, range=[0.3, num_levels + 0.7]),
        plot_bgcolor='#f8fafc',
        height=max(400, 130 * num_levels + 120),
        margin=dict(l=40, r=40, t=70, b=40),
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
    if 'AI_USAGE' not in st.session_state:
        st.session_state['AI_USAGE'] = {'calls': 0, 'input_tokens': 0, 'output_tokens': 0, 'cost': 0.0, 'history': []}
    if 'ANTHROPIC_API_KEY' not in st.session_state:
        st.session_state['ANTHROPIC_API_KEY'] = _get_secret('ANTHROPIC_API_KEY', '')
    if 'ANTHROPIC_WORKSPACE_ID' not in st.session_state:
        st.session_state['ANTHROPIC_WORKSPACE_ID'] = _get_secret('ANTHROPIC_WORKSPACE_ID', '')
    if 'AI_PROVIDER' not in st.session_state:
        # אם מוגדר מפתח Anthropic ב-Secrets, זהו יהיה ספק ברירת המחדל
        st.session_state['AI_PROVIDER'] = 'anthropic' if st.session_state['ANTHROPIC_API_KEY'] else 'openrouter'

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

def compute_ism_levels(frm_df):
    """
    Level Partitioning קלאסי ל-ISM (Warfield): לכל גורם מחשבים קבוצת נגישות
    (Reachability Set - מה שהוא מגיע אליו) וקבוצת קודמים (Antecedent Set - מי
    מגיע אליו). גורם שייך לרמה הנוכחית אם חיתוך שתי הקבוצות שווה לקבוצת הנגישות
    שלו. גורמים שנמצאים באותו מעגל השפעה הדדי (SCC) יוכנסו תמיד לאותה רמה,
    ובכך נמנעת "הצפה" מלאכותית של הרמה ע"י מעגלים.
    מחזיר רשימת רמות; levels[0] = הכי תלוי (Level I), levels[-1] = הכי מניע (השורש).
    """
    factors = list(frm_df.index)
    remaining = set(factors)
    levels = []

    while remaining:
        level_factors = []
        for f in remaining:
            reach = {g for g in remaining if frm_df.loc[f, g] == 1}
            antecedent = {g for g in remaining if frm_df.loc[g, f] == 1}
            if reach == (reach & antecedent):
                level_factors.append(f)
        if not level_factors:
            level_factors = list(remaining)  # הגנה מפני לולאה אינסופית במקרה קצה לא תקין
        levels.append(level_factors)
        remaining -= set(level_factors)

    return levels

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
        
        rec = 'O'
        explanation = "לא זוהה הסבר"
        
        if "RECOMMENDATION:" in ai_res:
            try:
                parts = ai_res.split("RATIONALE:")
                rec_part = parts[0].split("RECOMMENDATION:")[1].strip()
                rec = rec_part.replace(',', '').replace('.', '').strip()
                if len(parts) > 1:
                    explanation = parts[1].strip()
            except:
                pass
        
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
                
    frm = irm.values.copy()
    n = len(factors)
    while True:
        prev_frm = frm.copy()
        for i in range(n):
            for j in range(n):
                for k in range(n):
                    if frm[i, k] == 1 and frm[k, j] == 1:
                        frm[i, j] = 1
        if np.array_equal(frm, prev_frm):
            break

    frm_df = pd.DataFrame(frm, index=factors, columns=factors)

    dp = frm_df.sum(axis=1)
    dep = frm_df.sum(axis=0)
    micmac = pd.DataFrame({'DP': dp, 'DEP': dep})

    avg_dp = dp.mean()
    avg_dep = dep.mean()

    def classify(row):
        d, p = row['DP'], row['DEP']
        if d > avg_dp and p <= avg_dep:
            return 'Driving (מניע) 🚀'
        if d > avg_dp and p > avg_dep:
            return 'Linkage (קישור) 🔗'
        if d <= avg_dp and p > avg_dep:
            return 'Dependent (תלוי) 🎯'
        return 'Autonomous (אוטונומי) 🏝️'
        
    micmac['Classification'] = micmac.apply(classify, axis=1)
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

def call_ai_unified(prompt, system_context="", use_search=False):
    """
    פונקציית-העל היחידה לכל קריאות ה-AI באפליקציה.
    מנתבת לספק שנבחר (OpenRouter החינמי או Claude Sonnet 5 של Anthropic).
    מחזירה: (תשובה, רשימת מקורות)
    """
    provider = st.session_state.get('AI_PROVIDER', 'openrouter')

    full_prompt = prompt
    citations = []

    if use_search:
        results = _ddg_search(f"{system_context} {prompt[:150]}", max_results=4)
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

def call_ai_json(prompt, system_context, open_char='{', close_char='}', max_retries=2, use_search=False):
    """
    קורא ל-AI ומצפה לתשובת JSON. אם הפרסור נכשל (שגיאת פורמט נפוצה אצל מודלי שפה),
    מנסה שוב עד max_retries פעמים תוך שליחת שגיאת הפרסור בחזרה למודל לתיקון עצמי.
    """
    current_prompt = prompt
    last_error = None
    for attempt in range(max_retries + 1):
        text, citations = call_ai_unified(current_prompt, system_context, use_search=(use_search and attempt == 0))
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
        counts_str = ", ".join([f"{k}: {v}" for k, v in conflict_data['counts'].items()])
        justs_text = "\n".join([f"- {j['expert']} ({j['symbol']}): {j['text']}" for j in justifications])
        
        prompt = f"""הוכרע בין מומחים לגבי הקשר בין {f_i} ל-{f_j}.
הצבעות: {counts_str}
נימוקים:
{justs_text}

קבע את ההכרעה הסופית (V, A, X, או O) ונמק.
החזר בפורמט:
RECOMMENDATION: [הסימבול]
RATIONALE: [הנימוק]"""
        
        text, _ = call_ai_unified(prompt, "אתה שופט אקדמי אובייקטיבי ל-ISM.", use_search=False)
        return text
    except Exception as e:
        vote = conflict_data['counts'].most_common(1)[0][0]
        return f"RECOMMENDATION: {vote}\nRATIONALE: שגיאת AI ({str(e)})."

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

def _inject_synthetic_data_or(role_info, matrix_data, factors, citations=[]):
    """הזנת נתונים סינתטיים עם מקורות מהאינטרנט."""
    synth_id = f"Synth_{len([k for k in st.session_state['EXPERT_DATA'] if k.startswith('Synth_')]) + 1}"
    
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
            if sym != 'O':
                pair = (f_i, f_j)
                justs.setdefault(pair, []).append({
                    "expert": role_info['role'],
                    "symbol": sym,
                    "text": f"🌐 OpenRouter: {reason}"
                })
    
    st.session_state['EXPERT_DATA'][synth_id] = {
        'name': f"סוכן AI - {role_info['role']}",
        'role': role_info.get('expertise',''),
        'responses': responses
    }
    for k, v in justs.items():
        st.session_state['JUSTIFICATIONS'].setdefault(k, []).extend(v)
    if citations:
        st.session_state[f'CITATIONS_{synth_id}'] = citations
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
        st.dataframe(pd.DataFrame(usage['history'][::-1]), use_container_width=True, hide_index=True)
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
            with st.form("admin_login"):
                u = st.text_input("שם משתמש", placeholder="admin")
                p = st.text_input("סיסמה", type="password")
                if st.form_submit_button("התחבר כמנהל"):
                    if u == ADMIN_USERNAME and p == ADMIN_PASSWORD:
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
                        new_id = f"Exp_{len(st.session_state['EXPERT_DATA']) + 1}"
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
            st.session_state['EXPERT_DATA'][exp_id] = {
                'name': exp_name,
                'role': st.session_state['current_expert_role'],
                'responses': clean_res
            }
            
            for fi, row in responses.items():
                for fj, data in row.items():
                    if data['t']:
                        pair = (fi, fj)
                        entry = {'expert': exp_name, 'symbol': data['s'], 'text': data['t']}
                        if pair not in st.session_state['JUSTIFICATIONS']:
                            st.session_state['JUSTIFICATIONS'][pair] = []
                        st.session_state['JUSTIFICATIONS'][pair].append(entry)
                            
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
                st.session_state['EXPERT_DATA'] = {
                    k: v for k, v in st.session_state['EXPERT_DATA'].items()
                    if not k.startswith('Synth_')
                }
                st.success("✅ נתוני הסוכנים נמחקו!")
                st.rerun()
        
        if st.button("⏹️ עצור הכל ואפס", key="btn_stop_all_sidebar", type="primary"):
            factors_backup = st.session_state.get('FACTORS', [])
            topic_backup = st.session_state.get('TOPIC', '')
            question_backup = st.session_state.get('GENERIC_QUESTION', DEFAULT_GENERIC_QUESTION)
            
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
        curr = ",\n".join(st.session_state['FACTORS'])
        new_f = st.text_area("רשימת הגורמים (כל גורם מופרד בפסיק)", value=curr, height=300, key="txt_factors_tab1")
        
        curr_q = st.session_state.get('GENERIC_QUESTION', DEFAULT_GENERIC_QUESTION)
        new_q = st.text_input("נוסח השאלה (השתמש ב-{i} ו-{j} כמשתנים)", value=curr_q, key="txt_question_tab1")
        
        if st.button("💾 שמור ועדכן הכל", key="btn_save_tab1"):
            cleaned = [x.strip() for x in new_f.split(',') if x.strip()]
            if cleaned:
                st.session_state['FACTORS'] = cleaned
                st.session_state['GENERIC_QUESTION'] = new_q
                st.session_state['TOPIC'] = topic_input

                st.session_state['EXPERT_DATA'] = {}
                st.session_state['JUSTIFICATIONS'] = {}
                st.session_state['AI_LOG'] = []
                for k in ('RESULTS', 'SSIM_INIT', 'FINAL_SSIM'):
                    st.session_state.pop(k, None)
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
            st.dataframe(df, use_container_width=True)
            c1, c2 = st.columns(2)
            c1.metric("סה\"כ משיבים", len(data))
            if c2.button("🗑️ מחק את כל הנתונים", key="btn_clear_all_tab2"):
                st.session_state['EXPERT_DATA'] = {}
                st.session_state['JUSTIFICATIONS'] = {}
                st.rerun()
            
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='מומחים', index=False)
                
                if st.session_state['EXPERT_DATA']:
                    all_responses = []
                    factors = st.session_state['FACTORS']
                    
                    for exp_id, expert_info in st.session_state['EXPERT_DATA'].items():
                        expert_name = expert_info['name']
                        expert_role = expert_info['role']
                        responses = expert_info['responses']
                        
                        row = {'שם המומחה': expert_name, 'תפקיד': expert_role}
                        
                        for i in range(len(factors)):
                            for j in range(i+1, len(factors)):
                                f_i, f_j = factors[i], factors[j]
                                answer = responses.get(f_i, {}).get(f_j, 'O')
                                col_name = f"{f_i} → {f_j}"
                                row[col_name] = answer
                        
                        all_responses.append(row)
                    
                    if all_responses:
                        pd.DataFrame(all_responses).to_excel(writer, sheet_name='תשובות_מומחים', index=False)
                
                if st.session_state['JUSTIFICATIONS']:
                    just_records = []
                    for pair, justs in st.session_state['JUSTIFICATIONS'].items():
                        for j in justs:
                            just_records.append({
                                'זוג גורמים': f"{pair[0]} ↔ {pair[1]}",
                                'מומחה': j['expert'],
                                'סמל': j['symbol'],
                                'נימוק': j['text']
                            })
                    pd.DataFrame(just_records).to_excel(writer, sheet_name='נימוקים', index=False)
                
                if st.session_state['AI_LOG']:
                    pd.DataFrame(st.session_state['AI_LOG']).to_excel(writer, sheet_name='לוג_AI', index=False)
            
            st.download_button(
                label="📥 הורד דוח נתונים מלא ל-Excel",
                data=buffer.getvalue(),
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
                    st.dataframe(display_df, use_container_width=True, hide_index=True)
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
                        final_ssim, irm, frm, micmac = solve_conflicts_and_finalize(ssim_init, conflicts)
                        st.session_state['RESULTS'] = (irm, frm, micmac)
                        st.rerun()

            elif not conflicts and 'RESULTS' not in st.session_state:
                final_ssim, irm, frm, micmac = solve_conflicts_and_finalize(ssim_init, [])
                st.session_state['RESULTS'] = (irm, frm, micmac)
                st.rerun()

            if 'RESULTS' in st.session_state:
                irm, frm, micmac = st.session_state['RESULTS']
                st.success("✅ הניתוח הושלם.")
                
                # === הצגת מטריצות הקשרים ===
                st.markdown("---")
                st.subheader("📊 מטריצות קשרים (SSIM)")
                
                # מטריצה ראשונית (לפני פתרון קונפליקטים)
                if 'SSIM_INIT' in st.session_state:
                    with st.expander("🔍 מטריצת קשרים ראשונית (SSIM) - לפני פתרון קונפליקטים", expanded=False):
                        st.info("💡 **מקרא:** V=משפיע על, A=מושפע מ, X=הדדי, O=אין קשר, **C=קונפליקט** (דורש הכרעת AI)")
                        st.dataframe(st.session_state['SSIM_INIT'].style.map(color_ssim_conflicts), use_container_width=True)
                        
                        # ספירת קונפליקטים
                        conflict_count = (st.session_state['SSIM_INIT'] == 'C').sum().sum()
                        if conflict_count > 0:
                            st.warning(f"⚠️ נמצאו **{conflict_count}** קונפליקטים במטריצה (סומנו ב-C)")
                
                # מטריצה סופית (אחרי פתרון קונפליקטים)
                if 'FINAL_SSIM' in st.session_state:
                    with st.expander("✅ מטריצת קשרים סופית (SSIM) - אחרי פתרון קונפליקטים", expanded=False):
                        st.info("💡 **מקרא:** V=משפיע על, A=מושפע מ, X=הדדי, O=אין קשר")
                        st.dataframe(st.session_state['FINAL_SSIM'], use_container_width=True)
                
                # מטריצת נגישות סופית (FRM)
                with st.expander("🎯 מטריצת נגישות סופית (FRM) - עם טרנזיטיביות", expanded=False):
                    st.info("💡 מציגה השפעות ישירות **ועקיפות** בין גורמים")
                    st.dataframe(frm, use_container_width=True)
                
                # הצגת לוג ה-AI
                if st.session_state['AI_LOG']:
                    st.markdown("---")
                    st.markdown("### 🧠 דוח החלטות ה-AI")
                    st.dataframe(pd.DataFrame(st.session_state['AI_LOG']), use_container_width=True)

    # --- טאב 3: תוצאות ---
    with tab3:
        if 'RESULTS' in st.session_state:
            irm, frm, micmac = st.session_state['RESULTS']

            st.markdown("### 🏛️ מבנה היררכי (ISM Level Partitioning)")
            st.caption("זהו הפלט המרכזי של ניתוח ה-ISM עצמו (בנפרד מ-MICMAC): חלוקה היררכית של הגורמים לרמות, מהתלוי ביותר (למעלה) למניע ביותר (למטה). גורמים שנמצאים במעגל השפעה הדדי מאוחדים לאותה רמה (מסומנים בסגול).")
            levels = compute_ism_levels(frm)
            fig_h = plot_ism_hierarchy(levels, irm)
            st.plotly_chart(fig_h, use_container_width=True)
            with st.expander("📋 טבלת רמות"):
                level_rows = []
                for idx, lvl in enumerate(levels):
                    tag = " (מעגל השפעה הדדי)" if len(lvl) > 1 else ""
                    level_rows.append({"רמה": f"Level {idx + 1}{tag}", "גורמים": ", ".join(lvl)})
                st.dataframe(pd.DataFrame(level_rows), use_container_width=True, hide_index=True)

            st.markdown("---")
            st.markdown("### 📊 מפת MICMAC ויזואלית")
            fig = plot_interactive_micmac(micmac)
            st.plotly_chart(fig, use_container_width=True)

            st.markdown("---")
            st.markdown("### 🏆 נתונים מספריים וסיווג")
            st.dataframe(micmac.sort_values('DP', ascending=False).style.map(color_micmac, subset=['Classification']), use_container_width=True)

            drivers = micmac[micmac['Classification'].str.contains('Driving')]
            if not drivers.empty:
                st.success(f"📌 **גורמי המפתח המניעים (Drivers):** {', '.join(drivers.index)}")

            with st.expander("צפה במטריצת הנגישות הסופית (FRM)"):
                st.dataframe(frm)
        else:
            st.info("אנא הרץ ניתוח בטאב הקודם.")

    # --- טאב 4: מרכז AI מתקדם ---
    with tab4:
        st.header("🧠 מרכז ייעוץ וסימולציה מערכתית")
        st.info("זרימת עבודה: 1️⃣ ה-AI מנתח את הגורמים וממליץ על מומחים נדרשים → 2️⃣ הפעלת סוכני AI שימלאו את השאלון במקומם, עם נימוקים מבוססי גלישה באינטרנט.")
        
        if not is_ai_ready():
            st.error(f"⚠️ ספק ה-AI הנוכחי ({ai_provider_label()}) אינו מוגדר או שחסר מפתח API. עבור לטאב 'מנוע AI' כדי להגדיר.")
        else:
            st.subheader("שלב 1: הגדרת כמות וזיהוי מומחים נדרשים")
            
            col1, col2 = st.columns([1, 3])
            with col1:
                num_experts = st.number_input(
                    "מספר מומחים רצוי:",
                    min_value=1,
                    max_value=10,
                    value=3,
                    step=1,
                    help="כמה סוכני AI תרצה שייצרו וימלאו את השאלון?",
                    key="num_experts_tab4"
                )
            
            topic_ctx = st.session_state.get('TOPIC', 'לא הוגדר')
            factors_ctx = st.session_state['FACTORS']
            with col2:
                st.write(f"📌 **נושא:** `{topic_ctx}` | **גורמים:** {len(factors_ctx)}")
            
            if st.button(" הפק המלצות למומחים", key="btn_advisor_synth_v3"):
                with st.spinner(f"🤖 מנתח ומחפש {num_experts} תפקידים מתאימים..."):
                    try:
                        recs = _get_ai_expert_recommendations(topic_ctx, factors_ctx, num_experts)
                        st.session_state['AI_RECOMMENDED_EXPERTS'] = recs
                        st.success(f"✅ זוהו {len(recs)} תפקידי מומחים רלוונטיים.")
                    except Exception as e:
                        st.error(f"❌ {e}")

            if 'AI_RECOMMENDED_EXPERTS' in st.session_state:
                st.markdown("###  המומחים המומלצים:")
                for idx, exp in enumerate(st.session_state['AI_RECOMMENDED_EXPERTS']):
                    st.info(f"**{idx+1}. {exp['role']}** ({exp.get('expertise','')})\n💡 {exp.get('rationale','')}")
                
                st.markdown("---")
                st.subheader("שלב 2: הפעלת סוכני AI סינתטיים")
                st.warning("⚠️ הסוכנים ימלאו את השאלון במקום המומחים וינמקו בעזרת מקורות מהאינטרנט. התהליך עשוי לקחת מספר דקות.")
                
                if st.button("🚀 הפעל סימולציה והזן למערכת", key="btn_sim_synth_v3"):
                    progress = st.progress(0)
                    status_text = st.empty()
                    experts_list = st.session_state['AI_RECOMMENDED_EXPERTS']
                    success_count = 0
                    
                    for i, exp_role in enumerate(experts_list):
                        status_text.text(f"🔄 מעבד סוכן {i+1}/{len(experts_list)}: {exp_role['role']}...")
                        
                        try:
                            matrix, citations = _simulate_synthetic_expert(exp_role, factors_ctx)
                            _inject_synthetic_data_or(exp_role, matrix, factors_ctx, citations)
                            success_count += 1
                            
                            if i < len(experts_list) - 1:
                                st.info(f"⏳ המתנה של 5 שניות לפני הסוכן הבא...")
                                time.sleep(5)
                                
                        except Exception as e:
                            st.error(f"❌ **שגיאה בסוכן {exp_role['role']}:** {e}")
                            if st.button("⏹️ עצור סימולציה", key=f"btn_stop_{i}"):
                                st.warning("הסימולציה הופסקה על ידי המשתמש")
                                break
                        
                        progress.progress((i + 1) / len(experts_list))
                    
                    progress.empty()
                    status_text.empty()
                    
                    if success_count > 0:
                        st.success(f"✅ סימולציה הושלמה! {success_count}/{len(experts_list)} סוכנים הוזנו בהצלחה למערכת.")
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
                        st.session_state['EXPERT_DATA'] = {
                            k: v for k, v in st.session_state['EXPERT_DATA'].items()
                            if not k.startswith('Synth_')
                        }
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
