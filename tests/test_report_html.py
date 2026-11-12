import json
import re

import pandas as pd

from ism_core import transitive_closure, classify_micmac, build_analysis_results
from report_html import collect_report_data, build_html_report

FACTORS = ['תרבות', 'אכיפה', 'עייפות', 'הסחות']


def _analysis():
    irm = pd.DataFrame(0, index=FACTORS, columns=FACTORS)
    for f in FACTORS:
        irm.loc[f, f] = 1
    for a, b in [('אכיפה', 'תרבות'), ('תרבות', 'עייפות'), ('תרבות', 'הסחות')]:
        irm.loc[a, b] = 1
    frm = transitive_closure(irm)
    return build_analysis_results(irm, frm, classify_micmac(frm.sum(axis=1), frm.sum(axis=0)))


def _data(**kw):
    experts = {
        'e1': {'name': 'מומחה א', 'role': 'תנועה', 'responses': {'תרבות': {'אכיפה': 'A'}}},
        'Synth_1': {'name': 'סוכן', 'role': 'AI', 'responses': {}},
    }
    return collect_report_data(FACTORS, experts, _analysis(), topic='בטיחות </script> בדרכים', **kw)


def _embedded(html):
    m = re.search(r'<script id="report-data" type="application/json">(.*?)</script>', html, re.S)
    return json.loads(m.group(1))


def test_report_data_structure():
    d = _data()
    assert d['factors'] == FACTORS
    assert set(d['micmac']) == {'classic', 'classic_mid', 'godet', 'katz'}
    assert d['levels'][-1] == ['אכיפה']  # השורש בתחתית ההיררכיה
    drivers = [r['f'] for r in d['micmac']['classic']['rows'] if r['cls'] == 'driving']
    assert 'אכיפה' in drivers
    types = {e['name']: e['type'] for e in d['experts']}
    assert types == {'מומחה א': 'human', 'סוכן': 'ai'}
    assert sum(d['experts'][0]['counts'].values()) == 6  # 4 גורמים = 6 זוגות
    assert d['experts'][0]['counts']['A'] == 1


def test_conflicts_parsed_from_ai_log():
    log = [{'זוג גורמים': 'תרבות ↔ עייפות', 'הצבעות': "{'V': 2, 'O': 2}", 'הכרעת AI': 'V', 'נימוק ה-AI': 'נימוק'}]
    justs = {('תרבות', 'עייפות'): [{'expert': 'מומחה א', 'symbol': 'V', 'text': 'כי'}]}
    c = _data(ai_log=log, justifications=justs)['conflicts'][0]
    assert c['pair'] == ['תרבות', 'עייפות']
    assert c['votes'] == {'V': 2, 'O': 2}
    assert c['justs'][0]['text'] == 'כי'


def test_html_is_self_contained_and_round_trips():
    html = build_html_report(_data())
    assert html.startswith('<!doctype html>') and 'dir="rtl"' in html
    assert not re.search(r'<(script|link)[^>]+(src|href)="https?:', html)  # עובד בלי אינטרנט
    assert _embedded(html)['topic'] == 'בטיחות </script> בדרכים'  # טקסט חופשי לא סוגר את תגית הנתונים
    assert '&lt;/script&gt;' in html.split('<style>')[0]  # כותרת הדף מוברחת
