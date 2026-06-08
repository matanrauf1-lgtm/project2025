import streamlit as st
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from collections import Counter
import random
import time
import datetime

# ==============================================================================
# 0. הגדרות מערכת, ספריות ו-API
# ==============================================================================

# ניסיון ייבוא ספריית גוגל בצורה בטוחה (מונע קריסה אם הספרייה חסרה)
try:
    import google.genai as genai
    from google.genai.errors import APIError
    API_AVAILABLE = True
except ImportError:
    API_AVAILABLE = False
    class MockClient:
        def models(self): return self
        def generate_content(self, model, contents):
            raise Exception("Missing google-genai library")
    genai = type('mock_genai', (), {'Client': MockClient, 'APIError': Exception})

# --- קונפיגורציה ---
ADMIN_USERNAME = "admin_ism"
ADMIN_PASSWORD = "123" 
if "GEMINI_KEY" in st.secrets:
    AI_API_KEY = st.secrets["GEMINI_KEY"]
else:
    # מפתח דמה למקרה שאין סודות (מונע שגיאה מיידית, אבל ה-AI לא יעבוד מקומית בלי הגדרה)
    AI_API_KEY = "PLACEHOLDER"
    AI_MODEL_NAME = "gemini-1.5-flash"

# נתוני ברירת מחדל (למניעת מסך ריק)
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
        /* ייבוא פונטים */
        @import url('https://fonts.googleapis.com/css2?family=Heebo:wght@300;400;700;900&display=swap');
        
        /* הגדרות בסיס - עברית */
        html, body, [class*="css"] {
            font-family: 'Heebo', 'Segoe UI', sans-serif;
            direction: rtl;
            text-align: right;
        }
        
        /* הגדרות לאנגלית ומספרים - Times New Roman */
        .stDataFrame, code, .stCodeBlock, .stJson, .stMetricValue, .js-plotly-plot {
            font-family: 'Times New Roman', Times, serif !important;
            direction: ltr !important;
            text-align: left;
        }
        
        /* כותרות */
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
        
        /* תיקון סרגל צד */
        [data-testid="stSidebar"] {
            text-align: right;
            background-color: #f8fafc;
            border-left: 1px solid #e2e8f0;
        }
        
        /* כפתורים מעוצבים */
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
        
        /* שדות קלט */
        .stTextInput label, .stTextArea label, .stSelectbox label {
            font-size: 1.1rem;
            font-weight: 600;
            color: #334155;
            text-align: right;
        }
        
        /* כרטיסיות מידע */
        div[data-testid="metric-container"] {
            background-color: #ffffff;
            border: 1px solid #e2e8f0;
            padding: 15px;
            border-radius: 10px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
            text-align: center;
        }

        /* --- עיצוב מיוחד לרדיו בוטן (בחירת V A X O) --- */
        .stRadio > label {
            float: right;
            font-weight: bold;
            font-size: 1.1rem;
            margin-bottom: 10px;
        }
        div[role="radiogroup"] {
            direction: ltr; /* משאיר את האותיות בסדר נכון */
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

        /* הודעות */
        .stAlert {
            direction: rtl;
            border-radius: 10px;
            font-size: 1.1rem;
        }
        
        /* טאבים */
        button[data-baseweb="tab"] {
            font-size: 1.2rem;
            font-weight: bold;
        }
        /* === תיקון כיוון טקסט חכם לצ'אט ה-AI (עברית) === */
        div[data-testid="stChatMessage"] {
            direction: rtl !important;
            text-align: right !important;
            unicode-bidi: plaintext; /* מזהה אוטומטית כיוון פסקה לפי התו הראשון */
        }
        div[data-testid="stChatMessage"] .stMarkdown,
        div[data-testid="stChatMessage"] p {
            direction: rtl !important;
            text-align: right !important;
        }
        /* וידוא שבלוקי קוד, טבלאות ומספרים נשארים LTR תקינים */
        div[data-testid="stChatMessage"] pre,
        div[data-testid="stChatMessage"] code,
        div[data-testid="stChatMessage"] table {
            direction: ltr !important;
            text-align: left !important;
        }
        
        /* וידוא שהצ'אט יישאר יציב */
        .stChatMessage {
            order: 0;
        }
    </style>
    """, unsafe_allow_html=True)

def color_micmac(val):
    """צביעת תאים בטבלת התוצאות הסופית לפי חשיבות."""
    s = str(val)
    if 'Driving' in s:
        return 'background-color: #dcfce7; color: #14532d; font-weight: 900; font-size: 18px;' # ירוק
    elif 'Linkage' in s:
        return 'background-color: #fef9c3; color: #713f12; font-weight: 900; font-size: 18px;' # צהוב
    elif 'Dependent' in s:
        return 'background-color: #fee2e2; color: #7f1d1d; font-size: 18px;' # אדום
    return 'font-size: 18px;'

def plot_interactive_micmac(micmac_df):
    """יוצר גרף Plotly אינטראקטיבי ומרשים."""
    
    # הכנת הנתונים
    df = micmac_df.copy()
    df['Factor'] = df.index
    
    avg_dp = df['DP'].mean()
    avg_dep = df['DEP'].mean()
    
    # מיפוי צבעים
    color_map = {
        'Driving (מניע)': '#22c55e', 
        'Linkage (קישור)': '#eab308', 
        'Dependent (תלוי)': '#ef4444', 
        'Autonomous (אוטונומי)': '#94a3b8'
    }
    
    # ניקוי המחרוזת של הסיווג כדי שתתאים למפתח
    df['Clean_Class'] = df['Classification'].apply(lambda x: x.split('(')[0].strip() if '(' in x else x)
    
    # יצירת הגרף
    fig = px.scatter(
        df, x='DEP', y='DP', 
        text='Factor', 
        color='Classification',
        size=[25]*len(df), 
        hover_name='Factor',
        hover_data={'DP': True, 'DEP': True, 'Classification': True, 'Factor': False},
        title="<b>מפת ניתוח MICMAC - מיפוי גורמים</b>",
    )
    
    # הוספת קווי החיתוך (ממוצעים)
    fig.add_hline(y=avg_dp, line_dash="dash", line_color="gray", annotation_text="ממוצע השפעה")
    fig.add_vline(x=avg_dep, line_dash="dash", line_color="gray", annotation_text="ממוצע תלות")
    
    # עיצוב הטקסט והרקע
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
    if 'role' not in st.session_state: st.session_state['role'] = None
    if 'current_expert_name' not in st.session_state: st.session_state['current_expert_name'] = ""
    
    # משתני פרויקט - בדיקה קפדנית למניעת מחיקה
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
# III. לוגיקה מתמטית ו-AI (The Brain)
# ==============================================================================

def call_ai_analysis(conflict_data, justifications, f_i, f_j):
    """פונה ל-Gemini API להכרעה בקונפליקטים."""
    # בדיקת מפתח תקין
    if not API_AVAILABLE or "PLACEHOLDER" in AI_API_KEY:
        vote = conflict_data['counts'].most_common(1)[0][0]
        return f"RECOMMENDATION: {vote}\nRATIONALE: מנגנון הרוב (ללא API)."
    
    try:
        client = genai.Client(api_key=AI_API_KEY)
        
        # בניית טקסט נימוקים
        just_text = ""
        if justifications:
            just_text = "\n".join([f"- בחירה {j['symbol']}: {j['text']}" for j in justifications if j['text']])
        else:
            just_text = "לא סופקו נימוקים מילוליים."

        prompt = f"""
        אתה יועץ אסטרטגי בכיר המנתח מערכות מורכבות בשיטת ISM (Interpretive Structural Modeling).
        ישנה מחלוקת בין מומחים לגבי כיוון ההשפעה בין שני גורמים:
        1. גורם משפיע: "{f_i}"
        2. גורם מושפע: "{f_j}"
        
        התפלגות ההצבעות: {dict(conflict_data['counts'])} (מקרא: V=א' על ב', A=ב' על א', X=הדדי, O=אין).
        
        להלן נימוקי המומחים:
        {just_text}
        
        משימה:
        נתח את ההיגיון המערכתי. אם יש פיצול קולות או טיעונים חזקים לשני הצדדים, שקול לבחור ב-X (הדדי).
        עליך להכריע על סמל אחד בלבד (V, A, X, או O).
        
        החזר את התשובה בפורמט הבא בדיוק:
        RECOMMENDATION: [הסמל הנבחר]
        RATIONALE: [הסבר קצר ותמציתי בעברית, עד 30 מילים, שמסביר את ההכרעה]
        """
        
        response = client.models.generate_content(model=AI_MODEL_NAME, contents=prompt)
        return response.text
        
    except Exception as e:
        vote = conflict_data['counts'].most_common(1)[0][0]
        return f"RECOMMENDATION: {vote}\nRATIONALE: שגיאת API ({str(e)})."

def calculate_ism_matrices():
    """מבצע את כל חישובי הליבה: אגרגציה וזיהוי קונפליקטים."""
    factors = st.session_state['FACTORS']
    n = len(factors)
    expert_data = st.session_state['EXPERT_DATA']
    
    # 1. ספירת קולות
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
                
    # 2. זיהוי קונפליקטים
    ssim = pd.DataFrame('', index=factors, columns=factors)
    conflicts = []
    total_experts = len(expert_data)
    
    if total_experts == 0: return None, None, None, None, None
    
    for (fi, fj), cnt in counts.items():
        if not cnt: 
            ssim.loc[fi, fj] = 'O'
            continue
            
        top_symbol, top_count = cnt.most_common(1)[0]
        
        # לוגיקת קונפליקט: אין רוב של 50% או שיש תיקו בראש
        is_conflict = (top_count * 2 <= total_experts)
        if len(cnt) > 1:
            if top_count == cnt.most_common(2)[1][1]: is_conflict = True
            
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
    
    # פתרון קונפליקטים עם AI
    for conf in conflicts:
        fi, fj = conf['pair']
        justs = st.session_state['JUSTIFICATIONS'].get((fi, fj), [])
        
        time.sleep(0.1) # UI Feel
        ai_res = call_ai_analysis(conf, justs, fi, fj)
        
        rec = 'O'
        explanation = "לא זוהה הסבר"
        
        if "RECOMMENDATION:" in ai_res:
            try:
                parts = ai_res.split("RATIONALE:")
                rec_part = parts[0].split("RECOMMENDATION:")[1].strip()
                rec = rec_part.replace(',', '').replace('.', '').strip()
                if len(parts) > 1: explanation = parts[1].strip()
            except: pass
        
        if rec not in SYMBOLS: rec = conf['counts'].most_common(1)[0][0]
        
        # שמירה ללוג
        ai_logs.append({
            "זוג גורמים": f"{fi} ↔ {fj}",
            "הצבעות": str(dict(conf['counts'])),
            "הכרעת AI": rec,
            "נימוק ה-AI": explanation
        })
        
        ssim.loc[fi, fj] = rec
        
    st.session_state['AI_LOG'] = ai_logs # עדכון ה-State עם הלוג החדש
        
    # השלמת מטריצה
    final_ssim = ssim.copy()
    factors = final_ssim.index
    for i in range(len(factors)):
        for j in range(i+1, len(factors)):
            sym = final_ssim.iloc[i, j]
            if sym == 'V': final_ssim.iloc[j, i] = 'A'
            elif sym == 'A': final_ssim.iloc[j, i] = 'V'
            elif sym == 'X': final_ssim.iloc[j, i] = 'X'
            elif sym == 'O': final_ssim.iloc[j, i] = 'O'
            
    # IRM
    irm = pd.DataFrame(0, index=factors, columns=factors)
    for i in range(len(factors)):
        for j in range(len(factors)):
            if i == j: 
                irm.iloc[i, j] = 1
                continue
            sym = final_ssim.iloc[i, j]
            if sym in ['V', 'X']: irm.iloc[i, j] = 1
            
    # FRM (Transitivity Calculation)
    frm = irm.values.copy()
    n = len(factors)
    while True:
        prev_frm = frm.copy()
        for i in range(n):
            for j in range(n):
                for k in range(n):
                    if frm[i, k] == 1 and frm[k, j] == 1:
                        frm[i, j] = 1
        if np.array_equal(frm, prev_frm): break
    
    frm_df = pd.DataFrame(frm, index=factors, columns=factors)
    
    # MICMAC Analysis
    dp = frm_df.sum(axis=1)
    dep = frm_df.sum(axis=0)
    micmac = pd.DataFrame({'DP': dp, 'DEP': dep})
    
    avg_dp = dp.mean()
    avg_dep = dep.mean()
    
    def classify(row):
        d, p = row['DP'], row['DEP']
        if d > avg_dp and p <= avg_dep: return 'Driving (מניע) 🚀'
        if d > avg_dp and p > avg_dep: return 'Linkage (קישור) 🔗'
        if d <= avg_dp and p > avg_dep: return 'Dependent (תלוי) 🎯'
        return 'Autonomous (אוטונומי) 🏝️'
        
    micmac['Classification'] = micmac.apply(classify, axis=1)
    
    return final_ssim, irm, frm_df, micmac

def _call_gemini_expert_recommendation(factors, problem_context=""):
    client = genai.Client(api_key=AI_API_KEY)
    prompt = f"""אתה יועץ אסטרטגי בכיר לניתוח מערכות מורכבות (ISM). 
המערכת מנתחת את הבעיה: "{problem_context or 'אופטימיזציה של גורמים מערכתיים'}"
רשימת הגורמים לניתוח: {factors}

משימה: המלץ אילו סוגי מומחים/בעלי תפקידים כדאי לגייס כדי לאסוף תובנות איכותיות על הגורמים הללו.
לכל מומחה מומלץ ציין:
1. תפקיד/תחום מומחיות (לדוגמה: "מנהל אגף תנועה", "מומחה בטיחות בדרכים", "חוקר התנהגות נהגים")
2. נימוק קצר (עד 15 מילים) מדוע מומחה זה רלוונטי
3. אילו גורמים ספציפיים מהרשימה הוא יכול לנתח בצורה הטובה ביותר

החזר תשובה בפורמט רשימת נקודות בעברית, ללא כותרות מיותרות."""
    response = client.models.generate_content(model=AI_MODEL_NAME, contents=prompt)
    return response.text

def _render_expert_advisor_panel():
    """
    פאנל יועץ מומחים - גרסה הרמטית למניעת התנגשויות ID/Key ב-Streamlit.
    כולל הגנה מובנית נגד רינדור כפול באותו מחזור סקריפט.
    """
    # מזהה ייחודי גלובלי - ודא שרצף זה לא מופיע בשום מקום אחר בקובץ
    _WIDGET_KEY = "btn_expert_advisor_hermetic_final_v4"
    
    # מניעת רינדור כפול: אם הווידג'ט כבר רונדר במחזור הנוכחי, צא מהפונקציה
    if st.session_state.get("_advisor_panel_render_guard") is True:
        return
        
    st.markdown("### 💡 טיפ מהיר: מי צריך למלא את השאלון?")
    st.write("ה-AI מנתח אוטומטית את **נושא הבעיה** ו**גורמי המערכת** שהגדרת.")
    
    topic = st.session_state.get('TOPIC', 'לא הוגדר')
    factors_count = len(st.session_state['FACTORS'])
    st.info(f"📊 **בסיס ניתוח נוכחי:** נושא: '{topic}' | מספר גורמים: {factors_count}")

    # יצירת הכפתור עם מזהה ייחודי מוחלט
    if st.button("🔍 הפק המלצות למומחים (על בסיס הגדרות קיימות)", key=_WIDGET_KEY):
        with st.spinner("🤖 מנתח נתונים קיימים..."):
            factors = st.session_state['FACTORS']
            topic_ctx = st.session_state.get('TOPIC', '')
            recommendation = _call_gemini_expert_recommendation(factors, topic_ctx if topic_ctx else None)
            st.session_state['EXPERT_RECOMMENDATIONS'] = recommendation
            st.success("✅ ההמלצות חוללו!")
            st.markdown(recommendation)
            
    # שחרור מנעול הרינדור לסוף המחזור
    st.session_state["_advisor_panel_render_guard"] = True

def _show_saved_expert_recommendations():
    if 'EXPERT_RECOMMENDATIONS' in st.session_state:
        with st.expander("📋 הצג המלצות מומחים שמורות"):
            st.markdown(st.session_state['EXPERT_RECOMMENDATIONS'])

# ==============================================================================
# V. מנוע ייעוץ וסימולציית סוכני AI (Agentic Fallback)
# ==============================================================================
import json
import re

def _get_ai_expert_recommendations(topic, factors, num_experts=3):
    """שלב 1: יועץ AI מזהה אילו תפקידי מומחים נדרשים לניתוח."""
    prompt = f"""
אתה יועץ אסטרטגי בכיר לניתוח מערכות מורכבות (ISM-MICMAC).
הפרויקט עוסק בנושא: "{topic or 'אופטימיזציה מערכתית'}"
גורמי המערכת לניתוח: {factors}

משימה: המלץ בדיוק על {num_experts} תפקידי מומחים/פרסונות ארגוניות שחיוני שימלאו את שאלון ה-ISM כדי לקבל תמונה מערכתית מלאה ומגוונת.
לכל מומחה ציין:
1. שם התפקיד/תחום מומחיות (לדוגמה: "ראש אגף בטיחות", "מומחה התנהגות אנושית", "מהנדס תהליכים")
2. תחום מומחיות קצר
3. נימוק קצר מדוע הוא קריטי לניתוח גורמים אלו

החזר אך ורק אובייקט JSON תקין בפורמט הבא (ללא טקסט נוסף):
[
  {{"role": "שם התפקיד", "expertise": "תחום מומחיות", "rationale": "נימוק"}},
  ...
]
"""
    try:
        client = genai.Client(api_key=AI_API_KEY)
        response = client.models.generate_content(model=AI_MODEL_NAME, contents=prompt)
        raw = response.text
        match = re.search(r'\[.*\]', raw, re.DOTALL)
        if not match: raise ValueError("תבנית JSON לא נמצאה בתגובה")
        return json.loads(match.group(0))
    except Exception as e:
        raise RuntimeError(f"כשל בייבוא המלצות מומחים: {str(e)}")

import time
from google.genai.errors import APIError

def _call_with_rate_limit_handling(client, prompt, max_retries=3):
    """
    מבצע קריאה ל-Gemini API עם טיפול בשגיאות Rate Limit וניסיונות חוזרים.
    """
    for attempt in range(max_retries):
        try:
            config = {"tools": [{"google_search": {}}]}
            response = client.models.generate_content(
                model=AI_MODEL_NAME, 
                contents=prompt,
                config=config
            )
            return response.text
            
        except Exception as e:
            error_str = str(e)
            
            # בדיקה אם זו שגיאת Rate Limit (429)
            if 'RESOURCE_EXHAUSTED' in error_str or '429' in error_str:
                # חילוץ זמן ההמתנה מההודעה
                retry_after = 60  # ברירת מחדל: 60 שניות
                if 'retry in' in error_str.lower():
                    try:
                        import re
                        match = re.search(r'retry in (\d+\.?\d*)', error_str.lower())
                        if match:
                            retry_after = float(match.group(1)) + 1  # הוספת שנייה אחת
                    except:
                        pass
                
                if attempt < max_retries - 1:
                    st.warning(f"⏳ הגענו למגבלת קצב בקשות. ממתינים {retry_after:.0f} שניות לפני ניסיון חוזר...")
                    time.sleep(retry_after)
                    continue
                else:
                    raise Exception(f"חריגה ממכסת הבקשות לאחר {max_retries} ניסיונות. אנא המת מספר דקות ונסה שוב.")
            else:
                # שגיאה אחרת - זרוק מיד
                raise Exception(f"שגיאת API: {str(e)}")
    
    raise Exception("שגיאה לא ידועה לאחר כל הניסיונות")

import time
import random
from google.genai.errors import APIError

def _call_api_with_retry(client, prompt, max_retries=5, base_delay=10):
    """
    מבצע קריאה ל-Gemini API עם טיפול חכם בשגיאות משאבים.
    
    Args:
        client: לקוח Gemini
        prompt: הבקשה ל-AI
        max_retries: מספר מקסימלי של ניסיונות
        base_delay: זמן המתנה בסיסי בין ניסיונות (שניות)
    
    Returns:
        תגובת ה-API
    
    Raises:
        Exception: אם כל הניסיונות נכשלו
    """
    for attempt in range(max_retries):
        try:
            # יצירת קונפיגורציה עם Google Search
            config = {"tools": [{"google_search": {}}]}
            
            # ביצוע הקריאה ל-API
            response = client.models.generate_content(
                model=AI_MODEL_NAME, 
                contents=prompt,
                config=config
            )
            
            return response.text
            
        except Exception as e:
            error_str = str(e).lower()
            
            # זיהוי סוגי שגיאות
            is_rate_limit = 'resource_exhausted' in error_str or '429' in error_str
            is_unavailable = 'unavailable' in error_str or '503' in error_str or 'high demand' in error_str
            
            if is_rate_limit or is_unavailable:
                # חישוב זמן המתנה עם jitter (רעש אקראי למניעת התנגשויות)
                if 'retry in' in str(e):
                    # חילוץ זמן ההמתנה מההודעה אם קיים
                    import re
                    match = re.search(r'retry in (\d+\.?\d*)', str(e).lower())
                    if match:
                        wait_time = float(match.group(1)) + 2  # הוספת 2 שניות buffer
                    else:
                        wait_time = base_delay * (2 ** attempt) + random.uniform(1, 3)
                else:
                    # המתנה אקספוננציאלית עם jitter
                    wait_time = base_delay * (2 ** attempt) + random.uniform(1, 3)
                
                # הגבלת זמן המתנה מקסימלי ל-120 שניות
                wait_time = min(wait_time, 120)
                
                if attempt < max_retries - 1:
                    # הצגת הודעה למשתמש
                    error_type = "עומס שרת" if is_unavailable else "חריגה ממכסה"
                    st.warning(
                        f"⏳ **שגיאת {error_type}** (ניסיון {attempt + 1}/{max_retries})\n\n"
                        f"ממתין {wait_time:.0f} שניות לפני ניסיון חוזר...\n\n"
                        f"💡 *שגיאות זמניות נובעות מעומס על השרתים ונפתרות לרוב לאחר המתנה*"
                    )
                    
                    # התקדמות ויזואלית
                    progress_placeholder = st.empty()
                    progress_bar = progress_placeholder.progress(0)
                    
                    for i in range(int(wait_time)):
                        progress_bar.progress((i + 1) / wait_time)
                        time.sleep(1)
                    
                    progress_placeholder.empty()
                    continue
                else:
                    raise Exception(
                        f"נכשל לאחר {max_retries} ניסיונות עקב {error_type}. "
                        f"אנא המת מספר דקות ונסה שוב, או הפחת את מספר הסוכנים."
                    )
            else:
                # שגיאה אחרת - זרוק מיד
                raise Exception(f"שגיאת API לא צפויה: {str(e)}")
    
    raise Exception("שגיאה לא ידועה לאחר כל הניסיונות")


def _is_api_available_with_check():
    """
    בודק אם ה-API זמין לפני תחילת עבודה.
    """
    if not API_AVAILABLE:
        return False, "ספריית google.genai לא מותקנת"
    
    if "PLACEHOLDER" in AI_API_KEY:
        return False, "מפתח API לא הוגדר"
    
    try:
        client = genai.Client(api_key=AI_API_KEY)
        # ניסיון קריאה קלה לבדיקת זמינות
        test_prompt = "Say 'OK' in Hebrew"
        config = {"tools": [{"google_search": {}}]}
        response = client.models.generate_content(
            model=AI_MODEL_NAME,
            contents=test_prompt,
            config=config
        )
        return True, "API זמין"
    except Exception as e:
        error_str = str(e).lower()
        if 'unavailable' in error_str or '503' in error_str:
            return False, "השירות לא זמין כרגע עקב עומס. אנא המתן מספר דקות."
        elif 'resource_exhausted' in error_str or '429' in error_str:
            return False, "חריגה ממכסת הבקשות. אנא המתן מספר דקות."
        else:
            return False, f"שגיאה בבדיקת API: {str(e)}"

def _simulate_synthetic_expert(role_info, factors):
    """
    שלב 2: סוכן AI ממלא מטריצת ISM עם הצדקה מבוססת גלישה באינטרנט.
    כולל הגנה מפני Rate Limit ושגיאות שרת.
    """
    role = role_info['role']
    
    prompt = f"""
אתה מומחה אקדמי בכיר בתפקיד: "{role}".
תחום המומחיות שלך: {role_info.get('expertise', 'כללי')}
הקשר לפרויקט: {role_info.get('rationale', 'ניתוח מערכתי')}

עליך לנתח את הגורמים הבאים: {factors}

**חובה**: לפני שאתה עונה, השתמש בכלי החיפוש (Google Search) כדי למצוא ספרות אקדמית, מחקרים, או עובדות תעשייתיות התומכות בקשרים בין הגורמים.

משימה: עבור כל זוג גורמים (i, j), קבע את סוג הקשר הישיר (V, A, X, O) וספק נימוק קצר (עד 25 מילים) המבוסס על המידע שמצאת או על היגיון מקצועי מבוסס מקורות.
- V: גורם i משפיע ישירות על גורם j
- A: גורם j משפיע ישירות על גורם i
- X: השפעה הדדית
- O: אין קשר ישיר (אין צורך בנימוק)

החזר אך ורק אובייקט JSON תקין בפורמט הבא:
{{
  "{role}": {{
    "Factor_i_Name": {{
       "Factor_j_Name": {{ "relation": "V", "justification": "הנימוק המבוסס על מקורות..." }},
       ...
    }}
  }}
}}
שים לב: החזר רק קשרים עבור i < j (חצי מטריצה עליונה). אל תחזור על עצמך. ודא שכל צירופי הגורמים מופיעים.
"""
    try:
        client = genai.Client(api_key=AI_API_KEY)
        
        # שימוש בפונקציה עם הגנת Retry
        raw = _call_api_with_retry(client, prompt, max_retries=5, base_delay=15)
        
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if not match: 
            raise ValueError("תבנית JSON לא נמצאה")
        
        data = json.loads(match.group(0))
        return data.get(role, data)
        
    except Exception as e:
        raise RuntimeError(f"כשל בסימולציית הסוכן {role}: {str(e)}")
        
def _inject_synthetic_data(role_info, matrix_data, factors):
    """שלב 3: הזנת הנתונים ל-State בצורה שתואמת לקוד הקיים."""
    # יצירת ID ייחודי
    synth_id = f"Synth_{len([k for k in st.session_state['EXPERT_DATA'] if k.startswith('Synth_')]) + 1}"
    
    responses = {}
    
    # עיבוד המטריצה שהוחזרה מה-AI
    for f_i in factors:
        if f_i not in matrix_data: continue
        responses[f_i] = {}
        for f_j in factors:
            pair_data = matrix_data.get(f_i, {}).get(f_j)
            if not pair_data: continue
            
            sym = pair_data.get("relation", "O").upper()
            reason = pair_data.get("justification", "")
            if sym not in ['V','A','X','O']: sym = 'O'
            
            responses[f_i][f_j] = sym
            
            # שמירת נימוקים
            if sym != 'O' and reason:
                pair = (f_i, f_j)
                if pair not in st.session_state['JUSTIFICATIONS']:
                    st.session_state['JUSTIFICATIONS'][pair] = []
                st.session_state['JUSTIFICATIONS'][pair].append({
                    "expert": role_info['role'],
                    "symbol": sym,
                    "text": f"🌐 מקורות AI: {reason}"
                })
    
    # עדכון State - מבנה תואם בדיוק לקוד הקיים שלך
    st.session_state['EXPERT_DATA'][synth_id] = {
        'name': f"סוכן AI - {role_info['role']}",
        'role': role_info.get('expertise', 'AI Agent'),
        'responses': responses
    }
    
    return synth_id
    
# ==============================================================================
# IV. מסכים (Screens)
# ==============================================================================

def screen_login():
    """מסך הכניסה הראשי."""
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("<h1 style='text-align: center; font-size: 3.5rem;'>🚦 מערכת ISM MICMAC Pro</h1>", unsafe_allow_html=True)
    st.markdown("<h3 style='text-align: center; color: #64748b;'>כלי תומך החלטה לניתוח מערכתי מורכב</h3>", unsafe_allow_html=True)
    st.markdown("---")
    
    c1, c2 = st.columns(2, gap="large")
    
    # --- צד ימין: מנהל ---
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

    # --- צד שמאל: מומחה (כניסה חכמה ללא סיסמה) ---
    with c2:
        st.success("📝 **כניסת מומחה / משתתף**")
        st.write("אין צורך בסיסמה. מלא את פרטיך כדי להתחיל.")
        with st.form("expert_start"):
            name = st.text_input("שם מלא", placeholder="לדוגמה: ישראל ישראלי")
            role = st.text_input("תפקיד / מחלקה", placeholder="לדוגמה: אגף תנועה")
            
            if st.form_submit_button("התחל שאלון >>"):
                if name and role:
                    # יצירת ID ייחודי אוטומטית (פותר את הבאג של הבחירה)
                    new_id = f"Exp_{len(st.session_state['EXPERT_DATA']) + 1}"
                    
                    # שמירת פרטי המושב
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
    
    # הגנה מפני רשימה ריקה (מונע מסך לבן)
    if not factors:
        st.session_state['FACTORS'] = DEFAULT_FACTORS
        st.rerun()

    with st.form("ssim_survey"):
        responses = {} 
        
        # לולאה כפולה ליצירת השאלות
        # רצים עד n-1 כדי למנוע הצגת הגורם האחרון ככותרת ריקה
        for i in range(len(factors)-1):
            f_i = factors[i]
            st.markdown(f"<div style='background-color: #f0f9ff; padding: 15px; border-radius: 10px; margin-top: 30px; margin-bottom: 15px; border-right: 5px solid #0ea5e9;'><h3>🔹 האם הגורם <u>{f_i}</u> משפיע על...</h3></div>", unsafe_allow_html=True)
            
            for j in range(i+1, len(factors)):
                f_j = factors[j]
                
                # יצירת השאלה
                q_text = generic_q.format(i=f_i, j=f_j)
                st.markdown(f"#### {q_text}")
                
                c_q, c_txt = st.columns([3, 4])
                
                with c_q:
                    val = st.radio(
                        "סוג הקשר:",
                        options=SYMBOLS,
                        key=f"rad_{i}_{j}",
                        horizontal=True,
                        index=3, # ברירת מחדל O
                        help="V: משפיע על, A: מושפע מ, X: הדדי, O: אין קשר"
                    )
                with c_txt:
                    rsn = st.text_input(
                        "נימוק (אופציונלי):", 
                        key=f"txt_{i}_{j}",
                        placeholder="הסבר בקצרה..."
                    )
                
                st.markdown("<hr style='margin: 10px 0; border-top: 1px dashed #ccc;'>", unsafe_allow_html=True)
                
                # שמירה זמנית במילון
                if f_i not in responses: responses[f_i] = {}
                responses[f_i][f_j] = {'s': val, 't': rsn}
            
        if st.form_submit_button("💾 שמור ושלח את כל התשובות"):
            # שמירה ל-Session State
            exp_id = st.session_state['current_expert_id']
            
            # 1. שמירת המטריצה
            clean_res = {fi: {fj: data['s'] for fj, data in row.items()} for fi, row in responses.items()}
            st.session_state['EXPERT_DATA'][exp_id] = {
                'name': exp_name,
                'role': st.session_state['current_expert_role'],
                'responses': clean_res
            }
            
            # 2. שמירת הנימוקים
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
    st.title("⚙️ ממשק ניהול (Admin Dashboard)")
    with st.sidebar:
        st.header("תפריט מנהל")
        if st.button("🚪 יציאה"):
            st.session_state['role'] = None
            st.rerun()
        st.markdown("---")
        status_icon = '✅' if API_AVAILABLE and 'PLACEHOLDER' not in AI_API_KEY else '❌'
        st.info(f"API סטטוס: {status_icon}")
            # --- כפתור עצור ומחק (בסרגל הצדדי) ---
        st.markdown("---")
        st.subheader("🛑 בקרת סימולציה")
        
        # בדיקה אם יש נתונים סינתטיים
        has_synth_data = any(k.startswith('Synth_') for k in st.session_state.get('EXPERT_DATA', {}))
        
        if has_synth_data:
            if st.button("🗑️ מחק נתוני סוכני AI", key="btn_clear_synth_sidebar", type="secondary"):
                st.session_state['EXPERT_DATA'] = {
                    k: v for k, v in st.session_state['EXPERT_DATA'].items() 
                    if not k.startswith('Synth_')
                }
                st.success("✅ נתוני הסוכנים נמחקו!")
                st.rerun()
        
        # כפתור ביטול/עצירה (למקרה של סימולציה רצה)
        if st.button("⏹️ עצור הכל ואפס", key="btn_stop_all_sidebar", type="primary"):
            # נקה הכל חוץ מהגדרות בסיס
            factors_backup = st.session_state.get('FACTORS', [])
            topic_backup = st.session_state.get('TOPIC', '')
            question_backup = st.session_state.get('GENERIC_QUESTION', DEFAULT_GENERIC_QUESTION)
            
            # איפוס מלא
            for key in list(st.session_state.keys()):
                if key not in ['FACTORS', 'TOPIC', 'GENERIC_QUESTION', 'role']:
                    del st.session_state[key]
            
            # שחזור הגדרות
            st.session_state['FACTORS'] = factors_backup
            st.session_state['TOPIC'] = topic_backup
            st.session_state['GENERIC_QUESTION'] = question_backup
            
            st.success("✅ המערכת אופסה בהצלחה!")
            st.rerun()
    
    tab1, tab2, tab3, tab4 = st.tabs(["📝 הגדרות שאלון", "📊 מעקב וניתוח", "📈 תוצאות סופיות", "🤖 מרכז AI מתקדם"])
    
    # --- טאב 1: הגדרות ---
        # --- טאב 1: הגדרות ---
    with tab1:
        st.subheader("📌 הגדרת הבעיה והמערכת")
        
        # 1. שדה חדש לנושא הבעיה
        topic_input = st.text_input(
            "נושא הבעיה / ההקשר הארגוני", 
            value=st.session_state.get('TOPIC', ''), 
            placeholder="לדוגמה: שיפור בטיחות באתרי בנייה, ייעול תהליכי מיון..."
        )
        
        st.markdown("---")
        
        # 2. הגורמים
        st.subheader("עריכת גורמי המערכת")
        curr = ",\n".join(st.session_state['FACTORS'])
        new_f = st.text_area("רשימת הגורמים (כל גורם מופרד בפסיק)", value=curr, height=300)
        
        # 3. נוסח השאלה
        curr_q = st.session_state.get('GENERIC_QUESTION', DEFAULT_GENERIC_QUESTION)
        new_q = st.text_input("נוסח השאלה (השתמש ב-{i} ו-{j} כמשתנים)", value=curr_q)
        
        if st.button(" שמור ועדכן הכל"):
            cleaned = [x.strip() for x in new_f.split(',') if x.strip()]
            if cleaned:
                st.session_state['FACTORS'] = cleaned
                st.session_state['GENERIC_QUESTION'] = new_q
                st.session_state['TOPIC'] = topic_input # שמירת הנושא החדש
                
                # איפוס נתונים למניעת התנגשות
                st.session_state['EXPERT_DATA'] = {}
                st.session_state['JUSTIFICATIONS'] = {}
                st.session_state['AI_LOG'] = []
                st.success("הגדרות עודכנו בהצלחה! (כל הנתונים הקודמים אופסו)")
                st.rerun()
            else: st.error("לא ניתן לשמור רשימה ריקה.")

        # יועץ AI (מוצג לאחר ההגדרות)
        st.markdown("---")
        _render_expert_advisor_panel()
        _show_saved_expert_recommendations()
            
    # --- טאב 2: מעקב וניתוח ---
    with tab2:
        st.subheader("סטטוס משיבים")
        data = st.session_state['EXPERT_DATA']
        if not data: st.warning("טרם התקבלו תשובות ממומחים.")
        else:
            df = pd.DataFrame.from_dict(data, orient='index')[['name', 'role']]
            st.dataframe(df, use_container_width=True)
            c1, c2 = st.columns(2)
            c1.metric("סה\"כ משיבים", len(data))
            if c2.button("🗑️ מחק את כל הנתונים"):
                st.session_state['EXPERT_DATA'] = {}
                st.session_state['JUSTIFICATIONS'] = {}
                st.rerun()
            import io
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                # גיליון 1: רשימת מומחים
                df.to_excel(writer, sheet_name='מומחים', index=False)
                
                # גיליון 2: תשובות מומחים (מטריצות מלאות) - הוספנו!
                if st.session_state['EXPERT_DATA']:
                    all_responses = []
                    factors = st.session_state['FACTORS']
                    
                    for exp_id, expert_info in st.session_state['EXPERT_DATA'].items():
                        expert_name = expert_info['name']
                        expert_role = expert_info['role']
                        responses = expert_info['responses']
                        
                        # יצירת שורה לכל מומחה עם כל התשובות שלו
                        row = {'שם המומחה': expert_name, 'תפקיד': expert_role}
                        
                        # מעבר על כל זוגות הגורמים
                        for i in range(len(factors)):
                            for j in range(i+1, len(factors)):
                                f_i, f_j = factors[i], factors[j]
                                # קבלת התשובה או 'O' כברירת מחדל
                                answer = responses.get(f_i, {}).get(f_j, 'O')
                                col_name = f"{f_i} → {f_j}"
                                row[col_name] = answer
                        
                        all_responses.append(row)
                    
                    # שמירה כטבלה רחבה ונוחה
                    if all_responses:
                        pd.DataFrame(all_responses).to_excel(writer, sheet_name='תשובות_מומחים', index=False)
                
                # גיליון 3: נימוקים (אם קיימים)
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
                    
                # גיליון 4: לוג החלטות AI (אם קיים)
                if st.session_state['AI_LOG']:
                    pd.DataFrame(st.session_state['AI_LOG']).to_excel(writer, sheet_name='לוג_AI', index=False)
            
            st.download_button(
                label="📥 הורד דוח נתונים מלא ל-Excel (כולל תשובות)",
                data=buffer.getvalue(),
                file_name=f"ISM_Report_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.xml"
            )             

        st.markdown("---")
        st.subheader("ניתוח ופתרון קונפליקטים")
        if len(st.session_state['EXPERT_DATA']) > 0:
            # חישוב ראשוני לזיהוי קונפליקטים
            ssim_init, conflicts, _, _, _ = calculate_ism_matrices()
            
            if conflicts:
                st.error(f"⚠️ נמצאו {len(conflicts)} קונפליקטים הדורשים הכרעה.")
                
                with st.expander("צפה בפרטי הקונפליקטים"):
                    for c in conflicts:
                        st.write(f"**{c['pair']}**: {dict(c['counts'])}")
                
                if st.button(f"🤖 הפעל AI לפתרון {len(conflicts)} קונפליקטים"):
                    with st.spinner("ה-AI מנתח נימוקים ומבצע חישובים..."):
                        final_ssim, _, frm, micmac = solve_conflicts_and_finalize(ssim_init, conflicts)
                        st.session_state['RESULTS'] = (frm, micmac)
                        st.rerun()
            
            elif not conflicts and 'RESULTS' not in st.session_state:
                 # חישוב מיידי אם אין קונפליקטים
                 final_ssim, _, frm, micmac = solve_conflicts_and_finalize(ssim_init, [])
                 st.session_state['RESULTS'] = (frm, micmac)
                 st.rerun()

            if 'RESULTS' in st.session_state:
                frm, micmac = st.session_state['RESULTS']
                st.success("✅ הניתוח הושלם.")
                
                # הצגת לוג ה-AI
                if st.session_state['AI_LOG']:
                    st.markdown("### 🧠 דוח החלטות ה-AI")
                    st.dataframe(pd.DataFrame(st.session_state['AI_LOG']), use_container_width=True)

    # --- טאב 3: תוצאות ---
    with tab3:
        if 'RESULTS' in st.session_state:
            frm, micmac = st.session_state['RESULTS']
            
            st.markdown("### 📊 מפת MICMAC ויזואלית")
            # יצירת הגרף האינטראקטיבי
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


    # --- טאב 4: יועץ AI & סוכנים סינתטיים ---
    with tab4:
        st.header("🧠 מרכז ייעוץ וסימולציה מערכתית")
        st.info("זרימת עבודה: 1️⃣ ה-AI מנתח את הגורמים וממליץ על מומחים נדרשים → 2️⃣ הפעלת סוכני AI שימלאו את השאלון במקומם, עם נימוקים מבוססי גלישה באינטרנט.")
        
        if not API_AVAILABLE or "PLACEHOLDER" in AI_API_KEY:
            st.error("⚠️ מפתח API חסר או לא פעיל. לא ניתן להפעיל מודולים אלו.")
        else:
            # שלב 1: ייעוץ עם בחירת מספר מומחים
            st.subheader("שלב 1: הגדרת כמות וזיהוי מומחים נדרשים")
            
            col1, col2 = st.columns([1, 3])
            with col1:
                num_experts = st.number_input(
                    "מספר מומחים רצוי:", 
                    min_value=1, 
                    max_value=10, 
                    value=3, 
                    step=1,
                    help="כמה סוכני AI תרצה שייצרו וימלאו את השאלון?"
                )
            
            topic_ctx = st.session_state.get('TOPIC', 'לא הוגדר')
            factors_ctx = st.session_state['FACTORS']
            with col2:
                st.write(f"📌 **נושא:** `{topic_ctx}` | **גורמים:** {len(factors_ctx)}")
            
            if st.button("📥 הפק המלצות למומחים", key="btn_advisor_synth_v3"):
                with st.spinner(f"🤖 מנתח ומחפש {num_experts} תפקידים מתאימים..."):
                    try:
                        recs = _get_ai_expert_recommendations(topic_ctx, factors_ctx, num_experts)
                        st.session_state['AI_RECOMMENDED_EXPERTS'] = recs
                        st.success(f"✅ זוהו {len(recs)} תפקידי מומחים רלוונטיים.")
                    except Exception as e: 
                        st.error(f"❌ {e}")

            # הצגת המלצות
            if 'AI_RECOMMENDED_EXPERTS' in st.session_state:
                st.markdown("### 👥 המומחים המומלצים:")
                for idx, exp in enumerate(st.session_state['AI_RECOMMENDED_EXPERTS']):
                    st.info(f"**{idx+1}. {exp['role']}** ({exp.get('expertise','')})\n💡 {exp.get('rationale','')}")
                
                st.markdown("---")
                # שלב 2: סימולציה
                st.subheader("שלב 2: הפעלת סוכני AI סינתטיים")
                st.warning("⚠️ הסוכנים ימלאו את השאלון במקום המומחים וינמקו בעזרת מקורות מהאינטרנט. התהליך עשוי לקחת מספר דקות.")
                
                if st.button("🚀 הפעל סימולציה והזן למערכת", key="btn_sim_synth_v3"):
                    # בדיקת זמינות API לפני התחלה
                    try:
                        client = genai.Client(api_key=AI_API_KEY)
                        test_prompt = "Say OK"
                        client.models.generate_content(model=AI_MODEL_NAME, contents=test_prompt)
                    except Exception as e:
                        error_str = str(e).lower()
                        if 'unavailable' in error_str or '503' in error_str:
                            st.error("🚫 **השירות לא זמין כרגע עקב עומס.** אנא המתן 5-10 דקות ונסה שוב.")
                            st.stop()
                        elif 'resource_exhausted' in error_str or '429' in error_str:
                            st.error("🚫 **חריגה ממכסת הבקשות.** אנא המתן מספר דקות לפני ניסיון נוסף.")
                            st.stop()
                    
                    progress = st.progress(0)
                    status_text = st.empty()
                    experts_list = st.session_state['AI_RECOMMENDED_EXPERTS']
                    success_count = 0
                    
                    for i, exp_role in enumerate(experts_list):
                        status_text.text(f"🔄 מעבד סוכן {i+1}/{len(experts_list)}: {exp_role['role']}...")
                        
                        try:
                            matrix = _simulate_synthetic_expert(exp_role, factors_ctx)
                            _inject_synthetic_data(exp_role, matrix, factors_ctx)
                            success_count += 1
                            
                            # השהיה בין סוכנים למניעת Rate Limit
                            if i < len(experts_list) - 1:
                                st.info(f"⏳ המתנה של 20 שניות לפני הסוכן הבא למניעת חריגה ממכסה...")
                                time.sleep(20)
                                
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
                    
            # כפתור איפוס סינתטי
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
           
                
def _call_gemini_with_context(prompt, extra_context=""):
    """פונקציה מרכזית לבקשות AI עם הקשר אוטומטי של הפרויקט"""
    try:
        client = genai.Client(api_key=AI_API_KEY)
        
        # בניית הקשר דינמי מה-State
        ctx = f"אתה יועץ אסטרטגי מומחה לניתוח ISM-MICMAC. "
        ctx += f"פרויקט נוכחי מכיל {len(st.session_state['FACTORS'])} גורמים: {', '.join(st.session_state['FACTORS'])}. "
        ctx += f"מספר מומחים שהשיבו: {len(st.session_state['EXPERT_DATA'])}. "
        if 'RESULTS' in st.session_state and st.session_state['RESULTS']:
            ctx += "הניתוח הושלם וקיימות תוצאות MICMAC (זוהו גורמי Driving/Linkage/Dependent). "
        if extra_context:
            ctx += f"\n📌 הקשר ספציפי לבקשה זו: {extra_context}"

        full_prompt = f"{ctx}\n\n בקשת המשתמש:\n{prompt}"
        response = client.models.generate_content(model=AI_MODEL_NAME, contents=full_prompt)
        return response.text
    except Exception as e:
        return f"❌ שגיאת תקשורת עם ה-AI: {str(e)}"

def _render_ai_chat():
    """פונקציה יחידה ומלאה לניהול הצ'אט (כפתורים, לוגיקה ותצוגה)"""
    
    # 1. וידוא שהרשימה קיימת
    if "ai_chat_history" not in st.session_state:
        st.session_state["ai_chat_history"] = []

    # 2. כפתור מחיקה (למעלה)
    col_btn, _ = st.columns([5, 1])
    with col_btn:
        if st.button("🗑️ נקה היסטוריית צ'אט", key="clear_chat_btn"):
            st.session_state["ai_chat_history"] = []
            st.rerun()

    # 3. קליטת קלט המשתמש
    if prompt := st.chat_input("שאל שאלה על הגורמים, המתודולוגיה, או בקש המלצות..."):
        # הוספת הודעת המשתמש
        st.session_state["ai_chat_history"].append({"role": "user", "content": prompt})
        
        # קבלת תשובת ה-AI מיד (באותו ריצה)
        with st.chat_message("assistant"):
            with st.spinner("🤖 ה-AI מנתח את נתוני הפרויקט..."):
                reply = _call_gemini_with_context(prompt)
                st.markdown(reply, unsafe_allow_html=True)
                # הוספת תשובת ה-AI
                st.session_state["ai_chat_history"].append({"role": "assistant", "content": reply})

    # 4. הצגת ההודעות בסדר הפוך (החדש ביותר למעלה)
    # השימוש ב-reversed מבטיח שההודעה האחרונה שנוספה תוצג ראשונה
    for msg in reversed(st.session_state.get("ai_chat_history", [])):
        st.chat_message(msg["role"]).markdown(msg["content"], unsafe_allow_html=True)

def _render_ai_report_generator():
    """מחולל דוח אסטרטגי אוטומטי"""
    st.markdown("#### 📄 מחולל דוח ניתוח אסטרטגי")
    report_type = st.selectbox("בחר סוג דוח", ["דוח מנהלים תמציתי", "דוח טכני מפורט", "המלצות התערבות אופטימליות"])
    
    if st.button("צור דוח עכשיו"):
        with st.spinner("📝 כותב דוח מקצועי..."):
            prompt = f"כתוב {report_type} עבור מערכת ה-ISM הנוכחית. כלול: תקציר מנהלים, גורמי מפתח (Drivers), אזהרות סיכון, והמלצות מעשיות להשקעת משאבים. השתמש בטרמינולוגיה אקדמית ומקצועית."
            report = _call_gemini_with_context(prompt, extra_context=f"סוג הדוח המבוקש: {report_type}")
            st.success("✅ הדוח חולל בהצלחה!")
            st.download_button(" הורד כקובץ טקסט", report, file_name="ISM_AI_Report.txt", mime="text/plain")
            st.markdown("---")
            st.text_area("תצוגה מקדימה של הדוח:", report, height=300)

def _render_ai_data_validator():
    """בדיקת איכות ועקביות תשובות מומחים"""
    st.markdown("#### 🔍 ניתוח איכות ואמינות נתונים")
    st.write("ה-AI ינתח את דפוסי התשובות של המומחים, יזהה סתירות פנימיות, ויחזיק דוח אובייקטיבי.")
    
    if st.button("הפעל בדיקת איכות נתונים"):
        if not st.session_state['EXPERT_DATA']:
            st.warning("⚠️ אין נתוני מומחים לניתוח. אנא אסוף תשובות תחילה.")
            return
            
        with st.spinner("🔍 מנתח עקביות והיגיון מערכתי..."):
            prompt = "נתח את איכות התשובות שנאספו מהמומחים. זהה: 1. סתירות לוגיות בין מומחים שונים. 2. גורמים שזכו להסכמה גורפת (חזקים/חלשים). 3. המלצות לשיפור איסוף הנתונים או ניסוח השאלות. החזר תשובה מובנית עם נקודות."
            validation_report = _call_gemini_with_context(prompt, extra_context="נתוני מומחים קיימים במערכת. נתח דפוסים ואיכות.")
            st.success("✅ ניתוח האיכות הושלם!")
            st.markdown(validation_report)
# ==============================================================================
# Main Loop
# ==============================================================================

def hide_streamlit_style():
    """מסתיר את התפריט של המפתחים ואת הפוטר של סטרים-ליט"""
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


