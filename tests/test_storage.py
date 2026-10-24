import storage


def test_settings_roundtrip(tmp_path):
    db = str(tmp_path / "t.db")
    storage.init_db(db)
    storage.save_settings({'FACTORS': ['עייפות', 'מצב כבישים'], 'TOPIC': 'בטיחות'}, db)
    storage.save_settings({'TOPIC': 'בטיחות בדרכים'}, db)
    assert storage.load_settings(db) == {'FACTORS': ['עייפות', 'מצב כבישים'], 'TOPIC': 'בטיחות בדרכים'}


def test_experts_roundtrip_and_justifications(tmp_path):
    db = str(tmp_path / "t.db")
    storage.init_db(db)
    storage.save_expert('Exp_1', 'דנה', 'אגף תנועה', {'A': {'B': 'V'}},
                        justifications=[{'pair': ('A', 'B'), 'expert': 'דנה', 'symbol': 'V', 'text': 'נימוק'}], db_path=db)
    storage.save_expert('Synth_1', 'סוכן', 'AI', {'A': {'B': 'O'}}, citations=[{'href': 'x'}], db_path=db)

    data, justs, cites = storage.load_experts(db)
    assert list(data) == ['Exp_1', 'Synth_1']
    assert data['Exp_1']['responses'] == {'A': {'B': 'V'}}
    assert justs == {('A', 'B'): [{'expert': 'דנה', 'symbol': 'V', 'text': 'נימוק'}]}
    assert cites == {'Synth_1': [{'href': 'x'}]}


def test_delete_by_prefix_also_drops_their_justifications(tmp_path):
    db = str(tmp_path / "t.db")
    storage.init_db(db)
    storage.save_expert('Exp_1', 'a', '', {}, db_path=db)
    storage.save_expert('Synth_1', 'b', '', {},
                        justifications=[{'pair': ('A', 'B'), 'expert': 'b', 'symbol': 'O', 'text': 't'}], db_path=db)
    storage.delete_experts(prefix='Synth_', db_path=db)
    data, justs, _ = storage.load_experts(db)
    assert list(data) == ['Exp_1'] and justs == {}
    storage.delete_experts(db_path=db)
    assert storage.load_experts(db)[0] == {}
