# עדכון הקוד ופריסה ב-GitHub וב-Streamlit Community Cloud

המסמך מסביר איך מעבירים גרסה חדשה של האפליקציה מהמחשב המקומי אל GitHub, ומשם אל Streamlit Community Cloud.

## איך הקוד זורם

| מקום | תפקיד |
|---|---|
| המחשב המקומי (Windows) | פיתוח ובדיקה בעזרת `.\dev.ps1` |
| `osher2002/project2025` (fork) | ענפי עבודה (feature branches) |
| `matanrauf1-lgtm/project2025`, ענף `main` | הגרסה הרשמית. Streamlit Cloud פורס ממנה |
| Streamlit Community Cloud | האפליקציה הציבורית. כל push ל-`main` מפעיל פריסה מחדש באופן אוטומטי |

הקוד מגיע לענף `main` הרשמי רק דרך Pull Request (PR).

## שלב חד-פעמי: מיזוג PR #4

נכון לנובמבר 2026, ענף `main` במאגר הרשמי עדיין מכיל את הגרסה הישנה: קובץ אחד עם סיסמת מנהל קבועה בקוד, בלי `ism_core.py` ובלי `storage.py`. הגרסה שעבודת הגמר מתארת נמצאת בענף `persistence-katz-security`, שמחכה ב-PR #4.

1. בעל המאגר (מתן) פותח את https://github.com/matanrauf1-lgtm/project2025/pull/4.
2. מוודאים שבדיקות ה-CI (Tests) ירוקות. הן רצות על Python 3.11, 3.12 ו-3.13, ובונות גם את קובץ ה-Docker.
3. לוחצים על **Merge pull request**. הענף מכיל כבר את כל ההיסטוריה של `main`, לכן לא צפויות התנגשויות (conflicts).
4. בונים מחדש את קובץ ה-secrets ב-Streamlit Cloud לפי הסעיף הבא, כי הגרסה החדשה קוראת את הסיסמה ומפתחות ה-API משם.
5. מעדכנים גם את `main` ב-fork: ב-GitHub, בדף של `osher2002/project2025`, לוחצים על **Sync fork**.

## הגדרת האפליקציה ב-Streamlit Community Cloud

### אפליקציה חדשה

ב-https://share.streamlit.io לוחצים על **Create app**, ובוחרים:

- **Repository:** `matanrauf1-lgtm/project2025`
- **Branch:** `main`
- **Main file path:** `project2025.py`
- **Advanced settings > Python version:** 3.12. אפשר לבחור את הגרסה רק בזמן היצירה; כדי להחליף אותה צריך למחוק את האפליקציה וליצור אותה מחדש. הקוד נבדק על 3.11 עד 3.13.

### Secrets (חובה)

ב-**App > Settings > Secrets** מדביקים את המפתחות לפי `.streamlit/secrets.toml.example`, עם ערכים אמיתיים:

```toml
ADMIN_USERNAME = "admin_ism"
ADMIN_PASSWORD = "סיסמה חזקה וחדשה"     # בלי ערך כאן כניסת המנהל חסומה

# ספקי AI (לפחות אחד, כדי שסוכני ה-AI יפעלו)
ANTHROPIC_API_KEY = "sk-ant-..."
OPENROUTER_API_KEY = "sk-or-..."

# אופציונלי
# ANTHROPIC_MODEL = "claude-sonnet-5-5"
# ANTHROPIC_EFFORT = "medium"
# ANTHROPIC_MAX_TOKENS = "32000"
# ANTHROPIC_WORKSPACE_ID = ""
```

אחרי שמירה האפליקציה עולה מחדש. אסור להכניס את הערכים האלה לקובץ ב-Git.

### מגבלה: מסד הנתונים נמחק

מערכת הקבצים ב-Streamlit Cloud זמנית. קובץ ה-SQLite נמחק בכל הפעלה מחדש, למשל אחרי push, אחרי שינוי Secrets או אחרי תקופה בלי שימוש. לכן לפני עדכון גרסה בזמן איסוף שאלונים, מורידים את התוצאות מהאפליקציה (ייצוא ל-Excel). אם צריך שמירה קבועה, מריצים את האפליקציה מקומית (`.\dev.ps1 share`) או ב-Docker עם volume בנתיב `/data`.

## עדכון שוטף של הקוד

1. **ענף חדש:**
   ```powershell
   git checkout main
   git pull matan main
   git checkout -b שם-הענף
   ```
   (`matan` הוא ה-remote של המאגר הרשמי. אם הוא לא מוגדר: `git remote add matan https://github.com/matanrauf1-lgtm/project2025.git`.)
2. **פיתוח ובדיקה מקומית:** `.\dev.ps1 run` כדי לנסות, ואחר כך `.\dev.ps1 check`. ה-commit מתבצע רק אם הבדיקה ירוקה.
3. **תלות חדשה:** מתקינים אותה ב-venv המקומי ומוסיפים אותה ל-`requirements.txt` בגרסה המדויקת (`==`). צריך לבחור גרסה שתומכת ב-Python 3.11 עד 3.13. Streamlit Cloud מתקין רק את מה שכתוב בקובץ הזה.
4. **הגדרה חדשה:** קוראים אותה דרך `_get_secret()`, מוסיפים אותה ל-`.streamlit/secrets.toml.example`, ומוסיפים את הערך ב-Streamlit Cloud תחת Settings > Secrets.
5. **commit ו-push ל-fork:**
   ```powershell
   git add <קבצים>
   git commit -m "תיאור השינוי"
   git push -u origin שם-הענף
   ```
6. **PR:** ב-GitHub פותחים Pull Request מהענף ב-fork אל `matanrauf1-lgtm/project2025`, ענף `main`. מחכים שבדיקות ה-CI יהיו ירוקות.
7. **מיזוג:** אחרי המיזוג Streamlit Cloud מזהה את השינוי ב-`main` ופורס מחדש בתוך דקה או שתיים.
8. **בדיקה אחרי פריסה:** פותחים את האפליקציה, נכנסים כמנהל, ומריצים ניתוח קצר. אם הפריסה נתקעה או שהשתנה `requirements.txt`, בוחרים **Manage app > Reboot app**. השגיאות מופיעות ביומן שבחלון Manage app.

## אבטחה

- **מפתח Google ישן:** מפתח Gemini שמתחיל ב-`AIzaSyDUcB` נשאר בהיסטוריית ה-commits מדצמבר 2025. צריך לבטל אותו ב-Google AI Studio (API keys > Delete). אחרי הביטול אין צורך לשכתב את ההיסטוריה.
- **סיסמת המנהל הישנה:** הסיסמה `123` מהגרסה הקודמת מופיעה בהיסטוריה, ולכן אין להשתמש בה.
- **קבצים מקומיים:** `.streamlit/secrets.toml` מוחרג מ-Git. לא עושים לו `git add -f`.
- **החלפת מפתחות:** מפתח API שהופיע פעם בקוד, בצילום מסך או בהודעה מבטלים ומחליפים במפתח חדש.

## תקלות נפוצות

| תסמין | סיבה ופתרון |
|---|---|
| "כניסת מנהל חסומה" | `ADMIN_PASSWORD` לא הוגדר ב-Secrets |
| סוכני ה-AI לא עונים | חסר `ANTHROPIC_API_KEY` או `OPENROUTER_API_KEY`, או שהמפתח לא תקף |
| `ModuleNotFoundError` ביומן | חבילה חסרה ב-`requirements.txt` |
| שגיאת התקנה של numpy | גרסת ה-Python של האפליקציה ישנה מדי. הגרסאות הנעוצות תומכות ב-3.11 ומעלה |
| הנתונים נעלמו | ראו "מגבלה: מסד הנתונים נמחק" |
| הקישור של `.\dev.ps1 share` לא עובד | הקישור משתנה בכל הרצה, ופעיל רק כל עוד החלון פתוח והמחשב ער |
