"""
בדיקת עשן של האפליקציה המלאה דרך AppTest של Streamlit (ללא דפדפן): מומחה ממלא שאלון בסשן אחד, והמנהל רואה
אותו בסשן אחר דרך מסד הנתונים, מריץ ניתוח ומחליף שיטת MICMAC. רצה גם מקומית (dev.ps1 check) וגם ב-CI.
"""
import os

import pytest
from streamlit.testing.v1 import AppTest

APP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "project2025.py")


@pytest.fixture
def new_session(tmp_path, monkeypatch):
    db = str(tmp_path / "smoke.db")
    monkeypatch.setenv("ISM_DB_PATH", db)
    monkeypatch.setenv("ADMIN_PASSWORD", "smoke-pass")

    def make():
        at = AppTest.from_file(APP, default_timeout=120)
        # secrets מפורשים, כדי שקובץ secrets.toml מקומי לא ישפיע על הבדיקה
        at.secrets["ISM_DB_PATH"] = db
        at.secrets["ADMIN_USERNAME"] = "admin_ism"
        at.secrets["ADMIN_PASSWORD"] = "smoke-pass"
        at.run()
        assert not at.exception, at.exception
        return at
    return make


def test_expert_answers_reach_admin_and_analysis_runs(new_session):
    expert = new_session()
    expert.text_input[2].input("מומחה בדיקה")
    expert.text_input[3].input("אגף תנועה")
    expert.button[1].click().run()
    radios = {r.key: r for r in expert.radio}
    for key, sym in {"rad_0_1": "V", "rad_1_2": "V", "rad_2_3": "X", "rad_3_4": "V", "rad_0_6": "V"}.items():
        radios[key].set_value(sym)
    expert.button[0].click().run()
    assert not expert.exception, expert.exception

    admin = new_session()
    admin.text_input[0].input("admin_ism")
    admin.text_input[1].input("wrong")
    admin.button[0].click().run()
    assert any("פרטים שגויים" in e.value for e in admin.error)

    admin.text_input[1].input("smoke-pass")
    admin.button[0].click().run()
    admin.run()
    assert not admin.exception, admin.exception
    assert any("הניתוח הושלם" in s.value for s in admin.success)
    assert any("מומחה בדיקה" in str(df.value.to_dict()) for df in admin.dataframe)

    method = next(r for r in admin.radio if r.key == "micmac_method")
    assert len(method.options) == 3
    method.set_value("katz").run()
    assert not admin.exception, admin.exception
    assert len(admin.get("download_button")) == 2


def test_admin_login_blocked_without_password(tmp_path, monkeypatch):
    monkeypatch.setenv("ISM_DB_PATH", str(tmp_path / "x.db"))
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    at = AppTest.from_file(APP, default_timeout=60)
    at.secrets["ISM_DB_PATH"] = str(tmp_path / "x.db")
    at.run()
    assert not at.exception, at.exception
    assert any("כניסת מנהל חסומה" in w.value for w in at.warning)
