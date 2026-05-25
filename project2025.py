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
AI_MODEL_NAME = "gemini-2.5-flash"

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
    
    tab1, tab2, tab3, tab4 = st.tabs(["📝 הגדרות שאלון", "📊 מעקב וניתוח", "📈 תוצאות סופיות", "🤖 מרכז AI מתקדם"])
    
    # --- טאב 1: הגדרות ---
    with tab1:
        st.subheader("עריכת גורמי המערכת")
        curr = ",\n".join(st.session_state['FACTORS'])
        new_f = st.text_area("רשימת הגורמים (כל גורם מופרד בפסיק)", value=curr, height=300)
        
        curr_q = st.session_state.get('GENERIC_QUESTION', DEFAULT_GENERIC_QUESTION)
        new_q = st.text_input("נוסח השאלה (השתמש ב-{i} ו-{j} כמשתנים)", value=curr_q)
        
        if st.button("שמור ועדכן גורמים"):
            cleaned = [x.strip() for x in new_f.split(',') if x.strip()]
            if cleaned:
                st.session_state['FACTORS'] = cleaned
                st.session_state['GENERIC_QUESTION'] = new_q
                # איפוס נתונים למניעת התנגשות
                st.session_state['EXPERT_DATA'] = {}
                st.session_state['JUSTIFICATIONS'] = {}
                st.session_state['AI_LOG'] = []
                st.success("הגדרות עודכנו בהצלחה! (כל הנתונים הקודמים אופסו)")
                st.rerun()
            else: st.error("לא ניתן לשמור רשימה ריקה.")

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


    # --- טאב 4: מרכז AI מתקדם (יחיד ומודולרי) ---
    with tab4:
        if not API_AVAILABLE or "PLACEHOLDER" in AI_API_KEY:
            st.error("⚠️ מפתח ה-Gemini API אינו פעיל. אנא הגדר `GEMINI_KEY` ב-st.secrets או ישירות בקוד כדי להפעיל את מרכז ה-AI.")
        else:
            st.header("🧠 מרכז כוח AI & אוטומציה חכמה")
            st.markdown("כל יכולות הבינה המלאכותית מרוכזות כאן. המערכת טוענת אוטומטית את נתוני הפרויקט הנוכחי להקשר מלא.")
            
            # מבנה תת-טאבים לכלי AI (קל להוסיף עוד בעתיד)
            ai_tools = st.tabs([
                "💬 צ'אט חכם עם הקשר פרויקט", 
                "📝 מחולל דוח אסטרטגי", 
                "🔍 בדיקת איכות תשובות מומחים", 
                "➕ תבנית להוספת כלי חדש"
            ])

            with ai_tools[0]:
                _render_ai_chat()
            with ai_tools[1]:
                _render_ai_report_generator()
            with ai_tools[2]:
                _render_ai_data_validator()
            with ai_tools[3]:
                st.info("💡 **מדריך הוספת כלי AI חדש:**\n1. הוסף שם חדש לרשימת `ai_tools` למעלה.\n2. צור פונקציה `_render_your_tool()`.\n3. קרא לה בתוך `with ai_tools[N]: _render_your_tool()`.\n4. השתמש בפונקציה `_call_gemini_with_context(prompt)` לשליחת הבקשה.")

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
    """צ'אט אינטראקטיבי עם זיכרון והקשר פרויקט"""
    if "ai_chat_history" not in st.session_state:
        st.session_state["ai_chat_history"] = []
        
    for msg in st.session_state["ai_chat_history"]:
        st.chat_message(msg["role"]).write(msg["content"])
        
    if prompt := st.chat_input("שאל שאלה על הגורמים, המתודולוגיה, או בקש המלצות לשיפור המערכת..."):
        st.session_state["ai_chat_history"].append({"role": "user", "content": prompt})
        st.chat_message("user").write(prompt)
        
        with st.chat_message("assistant"):
            with st.spinner("🤖 מעבד בקשה עם הקשר פרויקט..."):
                reply = _call_gemini_with_context(prompt)
                st.write(reply)
                st.session_state["ai_chat_history"].append({"role": "assistant", "content": reply})

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


