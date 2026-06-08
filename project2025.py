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
    from duckduckgo_search import DDGS
    API_AVAILABLE = True
except ImportError:
    API_AVAILABLE = False

# --- קונפיגורציה ---
ADMIN_USERNAME = "admin_ism"
ADMIN_PASSWORD = "123"

# קריאת מפתח OpenRouter מ-Streamlit Secrets
if "OPENROUTER_API_KEY" in st.secrets:
    AI_API_KEY = st.secrets["OPENROUTER_API_KEY"]
else:
    # מפתח דמה למקרה שאין סודות (ה-AI לא יעבוד בלי הגדרה)
    AI_API_KEY = "PLACEHOLDER"

AI_MODEL_NAME = "google/gemma-4-31b-it:free"

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
    """מזריק CSS מתקדם לתיקון RTL, פונטים יוקרתיים וצבעים."""
    st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Heebo:wght@300;400;700;900&display=swap');
html, body, [class*="css"] {
    font-family: 'Heebo', 'Segoe UI', sans-serif;
    direction: rtl;
    text-align: right;
}
.stDataFrame, code, .stCodeBlock, .stJson, .stMetricValue, .js-plotly-plot {
    font-family: 'Times New Roman', Times, serif !important;
    direction: ltr !important;
    text-align: left !important;
}
h1 {
    color: #1E3A8A;
    font-family: 'Heebo', sans-serif;
    font-weight: 900;
    text-align: right;
    border-bottom: 2px solid #eee;
    padding-bottom: 10px;
    font-size: 3rem !important;
}
h2, h3 {
    color: #1E40AF;
    font-weight: 700;
    text-align: right;
}
[data-testid="stSidebar"] {
    text-align: right;
    background-color: #f8fafc;
    border-left: 1px solid #e2e8f0;
}
.stButton button {
    width: 100%;
    border-radius: 8px;
    font-weight: bold;
    font-size: 18px;
    background-color: #2563EB;
    color: white;
    border: none;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    transition: 0.3s;
    padding: 0.6rem;
}
.stButton button:hover {
    background-color: #1d4ed8;
    transform: translateY(-2px);
    box-shadow: 0 4px 6px rgba(0,0,0,0.15);
}
.stTextInput label, .stTextArea label, .stSelectbox label {
    font-size: 1.1rem;
    font-weight: 600;
    color: #334155;
    text-align: right;
}
div[data-testid="metric-container"] {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    padding: 15px;
    border-radius: 10px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    text-align: center;
}
.stRadio > label {
    float: right;
    font-weight: bold;
    font-size: 1.1rem;
    margin-bottom: 10px;
}
div[role="radiogroup"] {
    direction: ltr;
    justify-content: flex-end;
    gap: 15px;
}
div[role="radiogroup"] label {
    background: #eff6ff;
    padding: 8px 25px;
    border-radius: 20px;
    border: 1px solid #bfdbfe;
    font-family: 'Times New Roman', serif;
    font-weight: bold;
    font-size: 20px;
    color: #1e3a8a;
    cursor: pointer;
    transition: 0.2s;
}
div[role="radiogroup"] label:hover {
    background: #dbeafe;
    border-color: #2563eb;
}
.stAlert {
    direction: rtl;
    border-radius: 10px;
    font-size: 1.1rem;
}
button[data-baseweb="tab"] {
    font-size: 1.2rem;
    font-weight: bold;
}
div[data-testid="stChatMessage"] {
    direction: rtl !important;
    text-align: right !important;
    unicode-bidi: plaintext;
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

# ==============================================================================
# III. לוגיקה מתמטית (The Brain)
# ==============================================================================
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

    return final_ssim, irm, frm_df, micmac

# ==============================================================================
# IV. מנוע AI מאוחד (OpenRouter + DuckDuckGo - חינם!)
# ==============================================================================
def _ddg_search(query, max_results=4):
    """חיפוש אינטרנטי חינמי דרך DuckDuckGo."""
    try:
        with DDGS() as ddgs:
            return list(ddgs.text(query, max_results=max_results))
    except:
        return []

def call_ai_unified(prompt, system_context="", use_search=False):
    """
    פונקציית-העל היחידה לכל קריאות ה-AI באפליקציה.
    מחזירה: (תשובה, רשימת מקורות)
    """
    if not API_AVAILABLE:
        raise Exception("ספריות openai/duckduckgo לא מותקנות")
    
    client = OpenAI(api_key=AI_API_KEY, base_url="https://openrouter.ai/api/v1")
    
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
            return response.choices[0].message.content, citations
        except Exception as e:
            if attempt == 2:
                raise
            time.sleep(2)

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
    """ייעוץ AI לבחירת מומחים - גרסת OpenRouter."""
    prompt = f"""המלץ על {num_experts} תפקידי מומחים לבעיה: "{topic}". גורמים: {factors}.
החזר רק JSON:
[{{"role": "שם התפקיד", "expertise": "מומחיות", "rationale": "נימוק"}}]"""
    
    text, _ = call_ai_unified(prompt, "אתה יועץ אסטרטגי ל-ISM.", use_search=True)
    match = re.search(r'\[.*\]', text, re.DOTALL)
    return json.loads(match.group(0)) if match else []

def _simulate_synthetic_expert(role_info, factors):
    """סימולציית סוכן AI עם חיפוש אינטרנטי - גרסת OpenRouter."""
    role = role_info['role']
    
    prompt = f"""נתח גורמים: {factors}. קבע קשרים (V/A/X/O) לזוגות (i<j) עם נימוק.
החזר JSON:
{{"{role}": {{"Factor_i": {{"Factor_j": {{"relation": "V", "justification": "..."}}}}}}}}"""
    
    text, citations = call_ai_unified(
        prompt,
        f"אתה מומחה: {role}. {role_info.get('expertise','')}",
        use_search=True
    )
    
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if not match:
        return {}, []
    data = json.loads(match.group(0))
    return data.get(role, data), citations

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

# ==============================================================================
# V. מסכים (Screens)
# ==============================================================================
def screen_login():
    """מסך הכניסה הראשי."""
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("<h1 style='text-align: center; font-size: 3.5rem;'>🚦 מערכת ISM MICMAC Pro</h1>", unsafe_allow_html=True)
    st.markdown("<h3 style='text-align: center; color: #64748b;'>כלי תומך החלטה לניתוח מערכתי מורכב</h3>", unsafe_allow_html=True)
    st.markdown("---")
    c1, c2 = st.columns(2, gap="large")

    with c1:
        st.info("🔐 **כניסת מנהל מערכת**")
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
        st.success("📝 **כניסת מומחה / משתתף**")
        st.write("אין צורך בסיסמה. מלא את פרטיך כדי להתחיל.")
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
        status_icon = '✅' if API_AVAILABLE and AI_API_KEY != "PLACEHOLDER" else '❌'
        st.info(f"API סטטוס: {status_icon}")
        
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

    tab1, tab2, tab3, tab4 = st.tabs(["📝 הגדרות שאלון", " מעקב וניתוח", " תוצאות סופיות", "🤖 מרכז AI מתקדם"])

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
                st.success("הגדרות עודכנו בהצלחה! (כל הנתונים הקודמים אופסו)")
                st.rerun()
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
            
            if conflicts:
                st.error(f"️ נמצאו {len(conflicts)} קונפליקטים הדורשים הכרעה.")
                
                with st.expander("צפה בפרטי הקונפליקטים"):
                    for c in conflicts:
                        st.write(f"**{c['pair']}**: {dict(c['counts'])}")
                
                if st.button(f"🤖 הפעל AI לפתרון {len(conflicts)} קונפליקטים", key="btn_solve_conflicts"):
                    with st.spinner("ה-AI מנתח נימוקים ומבצע חישובים..."):
                        final_ssim, _, frm, micmac = solve_conflicts_and_finalize(ssim_init, conflicts)
                        st.session_state['RESULTS'] = (frm, micmac)
                        st.rerun()
            
            elif not conflicts and 'RESULTS' not in st.session_state:
                final_ssim, _, frm, micmac = solve_conflicts_and_finalize(ssim_init, [])
                st.session_state['RESULTS'] = (frm, micmac)
                st.rerun()

            if 'RESULTS' in st.session_state:
                frm, micmac = st.session_state['RESULTS']
                st.success("✅ הניתוח הושלם.")
                
                if st.session_state['AI_LOG']:
                    st.markdown("### 🧠 דוח החלטות ה-AI")
                    st.dataframe(pd.DataFrame(st.session_state['AI_LOG']), use_container_width=True)

    # --- טאב 3: תוצאות ---
    with tab3:
        if 'RESULTS' in st.session_state:
            frm, micmac = st.session_state['RESULTS']
            
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
        
        if not API_AVAILABLE or AI_API_KEY == "PLACEHOLDER":
            st.error("⚠️ מפתח API חסר או לא פעיל. לא ניתן להפעיל מודולים אלו.")
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
