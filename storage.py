"""
שמירת נתונים קבועה ב-SQLite, משותפת לכל הסשנים: מומחה שממלא את השאלון מהמכשיר
שלו נשמר כאן, והמנהל רואה אותו בסשן שלו. ללא תלות ב-Streamlit.
"""
import datetime
import json
import os
import sqlite3
from contextlib import closing

DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ism_data.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS experts (
    id             TEXT PRIMARY KEY,
    name           TEXT NOT NULL,
    role           TEXT NOT NULL DEFAULT '',
    responses      TEXT NOT NULL,
    justifications TEXT NOT NULL DEFAULT '[]',
    citations      TEXT NOT NULL DEFAULT '[]',
    created_at     TEXT NOT NULL
);
"""


def _connect(db_path):
    conn = sqlite3.connect(db_path, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")  # קוראים וכותבים במקביל מכמה סשנים
    return conn


def init_db(db_path=DEFAULT_DB_PATH):
    with closing(_connect(db_path)) as conn, conn:
        conn.executescript(_SCHEMA)


def save_settings(settings, db_path=DEFAULT_DB_PATH):
    """שומר הגדרות פרויקט (נושא, גורמים, נוסח שאלה) כ-JSON."""
    with closing(_connect(db_path)) as conn, conn:
        conn.executemany(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            [(k, json.dumps(v, ensure_ascii=False)) for k, v in settings.items()],
        )


def load_settings(db_path=DEFAULT_DB_PATH):
    with closing(_connect(db_path)) as conn:
        return {k: json.loads(v) for k, v in conn.execute("SELECT key, value FROM settings")}


def save_expert(exp_id, name, role, responses, justifications=(), citations=(), db_path=DEFAULT_DB_PATH):
    """
    שומר (או מחליף) את התשובות של מומחה אחד.
    justifications: רשימת {'pair': (fi, fj), 'expert', 'symbol', 'text'}.
    """
    justs = [{**j, 'pair': list(j['pair'])} for j in justifications]
    with closing(_connect(db_path)) as conn, conn:
        conn.execute(
            "INSERT OR REPLACE INTO experts (id, name, role, responses, justifications, citations, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (exp_id, name, role,
             json.dumps(responses, ensure_ascii=False),
             json.dumps(justs, ensure_ascii=False),
             json.dumps(list(citations), ensure_ascii=False),
             datetime.datetime.now().isoformat(timespec="seconds")),
        )


def load_experts(db_path=DEFAULT_DB_PATH):
    """
    מחזיר (expert_data, justifications, citations) במבנה שבו האפליקציה משתמשת:
    expert_data = {id: {'name', 'role', 'responses'}}, justifications = {(fi, fj): [..]},
    citations = {id: [..]}.
    """
    expert_data, justifications, citations = {}, {}, {}
    with closing(_connect(db_path)) as conn:
        rows = conn.execute(
            "SELECT id, name, role, responses, justifications, citations FROM experts ORDER BY created_at, rowid"
        ).fetchall()
    for exp_id, name, role, responses, justs, cites in rows:
        expert_data[exp_id] = {'name': name, 'role': role, 'responses': json.loads(responses)}
        for j in json.loads(justs):
            pair = tuple(j.pop('pair'))
            justifications.setdefault(pair, []).append(j)
        cites = json.loads(cites)
        if cites:
            citations[exp_id] = cites
    return expert_data, justifications, citations


def delete_experts(prefix=None, db_path=DEFAULT_DB_PATH):
    """מוחק מומחים: את כולם, או רק את אלה שהמזהה שלהם מתחיל ב-prefix (למשל 'Synth_')."""
    with closing(_connect(db_path)) as conn, conn:
        if prefix is None:
            conn.execute("DELETE FROM experts")
        else:
            conn.execute("DELETE FROM experts WHERE substr(id, 1, ?) = ?", (len(prefix), prefix))
