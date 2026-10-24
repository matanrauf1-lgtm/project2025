"""
ליבה מתמטית של ISM-MICMAC, ללא תלות ב-Streamlit (ניתנת לבדיקה עם pytest).
"""
import numpy as np
import pandas as pd


def transitive_closure(irm_df):
    """סגירה טרנזיטיבית בוליאנית (Warshall): מחזירה את ה-FRM מתוך ה-IRM."""
    frm = irm_df.values.astype(int).copy()
    n = len(frm)
    for k in range(n):
        frm = frm | (frm[:, [k]] & frm[[k], :])
    return pd.DataFrame(frm, index=irm_df.index, columns=irm_df.columns)


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
        for f in factors:
            if f not in remaining:
                continue
            reach = {g for g in remaining if frm_df.loc[f, g] == 1}
            antecedent = {g for g in remaining if frm_df.loc[g, f] == 1}
            if reach == (reach & antecedent):
                level_factors.append(f)
        if not level_factors:
            level_factors = [f for f in factors if f in remaining]  # הגנה מפני לולאה אינסופית במקרה קצה לא תקין
        levels.append(level_factors)
        remaining -= set(level_factors)

    return levels


def ism_cycle_members(frm_df):
    """גורמים שנמצאים במעגל השפעה הדדי: יש גורם אחר שהם מגיעים אליו וגם הוא מגיע אליהם."""
    m = frm_df.values.copy()
    np.fill_diagonal(m, 0)
    mutual = (m == 1) & (m.T == 1)
    return {f for f, row in zip(frm_df.index, mutual) if row.any()}


def classify_micmac(dp, dep):
    """מסווג כל גורם לרביע MICMAC לפי השוואה לממוצע ההשפעה (DP) והתלות (DEP)."""
    micmac = pd.DataFrame({'DP': dp, 'DEP': dep})
    avg_dp, avg_dep = dp.mean(), dep.mean()

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
    return micmac


def _as_percent(basis, index):
    """ממיר מטריצת ספירת מסלולים ל-DP/DEP כאחוזים מסך ההשפעה במערכת."""
    total = basis.sum()
    if total == 0:
        zeros = pd.Series(0.0, index=index)
        return zeros, zeros.copy()
    dp = pd.Series(basis.sum(axis=1) / total * 100, index=index)
    dep = pd.Series(basis.sum(axis=0) / total * 100, index=index)
    return dp, dep


def compute_godet_micmac(irm_df, max_power=20):
    """
    MICMAC עקיף לפי Godet: מעלים את מטריצת ההשפעה הישירה (ללא אלכסון) בחזקות עד
    שדירוג ההשפעה והתלות מתייצב. סגירה טרנזיטיבית בוליאנית (FRM) הופכת לכולה 1
    ברגע שמעגל השפעה אחד עובר דרך רוב הגורמים, ואז DP/DEP זהים לכולם; ספירת
    מסלולים ממשיכה להבחין בין הגורמים גם במצב כזה.
    בגרף ללא מעגלים החזקות מתאפסות, ולכן נספרים כל המסלולים הישירים והעקיפים.
    מגבלה ידועה: כשיש מעגל קצר (למשל באורך 2) החזקה הבודדת מתנודדת בין זוגי לאי-זוגי
    ומסלולים קצרים נעלמים ממנה; לכן קיימת גם השיטה המצטברת compute_katz_micmac.
    מחזיר (dp, dep, power) כאחוזים מסך ההשפעה.
    """
    M = irm_df.values.astype(float).copy()
    np.fill_diagonal(M, 0)
    power_k = M.copy()
    cumulative = M.copy()
    prev_rank, power, cyclic = None, 1, True
    for k in range(2, max_power + 1):
        power_k = power_k @ M
        if not power_k.any():
            cyclic = False
            break
        cumulative += power_k
        power = k
        rank = (tuple(np.argsort(-power_k.sum(axis=1), kind='stable')),
                tuple(np.argsort(-power_k.sum(axis=0), kind='stable')))
        if rank == prev_rank:
            break
        prev_rank = rank

    basis = power_k if cyclic else cumulative
    dp, dep = _as_percent(basis, irm_df.index)
    return dp, dep, power


def compute_katz_micmac(irm_df, alpha_ratio=0.5):
    """
    MICMAC עקיף מצטבר (מדד Katz, נוסחה 3.14 בספר):
        S(α) = Σ_{k≥1} α^k M^k = (I − αM)^−1 − I,   0 < α < 1/ρ(M)
    הסכום כולל מסלולים מכל אורך, ולכן בניגוד לחזקה הבודדת של Godet הוא לא מתנודד
    במעגל קצר ולא מאבד מסלולים קצרים. α נבחר כ-alpha_ratio/ρ(M).
    בגרף ללא מעגלים ρ(M)=0 והמטריצה נילפוטנטית, ולכן נלקח α=1: הסכום סופי ושווה
    לספירת כל המסלולים, בדיוק כמו Godet במקרה זה.
    מחזיר (dp, dep, alpha) כאחוזים מסך ההשפעה.
    """
    M = irm_df.values.astype(float).copy()
    np.fill_diagonal(M, 0)
    n = len(M)
    rho = float(np.max(np.abs(np.linalg.eigvals(M)))) if n else 0.0
    alpha = 1.0 if rho < 1e-9 else alpha_ratio / rho
    S = np.linalg.inv(np.eye(n) - alpha * M) - np.eye(n)
    S[np.abs(S) < 1e-12] = 0.0
    dp, dep = _as_percent(S, irm_df.index)
    return dp, dep, alpha


def build_analysis_results(irm, frm_df, micmac):
    """מרכז את כל תוצרי הניתוח, כולל מדד רוויה של ה-FRM וסיווגי MICMAC עקיפים (Godet ו-Katz)."""
    n = len(frm_df)
    off_diag = frm_df.values.copy()
    np.fill_diagonal(off_diag, 0)
    saturation = off_diag.sum() / (n * (n - 1)) if n > 1 else 0.0
    dp_g, dep_g, power = compute_godet_micmac(irm)
    dp_k, dep_k, alpha = compute_katz_micmac(irm)
    classic_degenerate = saturation >= 0.8 or (micmac['DP'].nunique() == 1 and micmac['DEP'].nunique() == 1)
    return {
        'irm': irm,
        'frm': frm_df,
        'micmac': micmac,
        'micmac_godet': classify_micmac(dp_g.round(1), dep_g.round(1)),
        'godet_power': power,
        'micmac_katz': classify_micmac(dp_k.round(1), dep_k.round(1)),
        'katz_alpha': alpha,
        'saturation': saturation,
        'classic_degenerate': classic_degenerate,
    }
