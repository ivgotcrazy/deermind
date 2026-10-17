"""校验评测材料的编号、合同引用与合成权限输入；不执行权限或语义评测。"""
from pathlib import Path
import hashlib
import json
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def verify():
    req = (ROOT/'doc/mvp/phase-3-definition/MVP_Requirements_and_Acceptance.md').read_text(encoding='utf-8')
    val = (ROOT/'doc/mvp/phase-3-definition/MVP_Validation_Plan.md').read_text(encoding='utf-8')
    known_ac = set(re.findall(r'\bAC-\d{3}\b', req))
    known_met = set(re.findall(r'\bMET-\d{3}\b', val))
    seen_cases, seen_assets, counts = set(), set(), {}
    for path in sorted(HERE.glob('*.json')):
        asset = json.loads(path.read_text(encoding='utf-8'))
        assert asset['asset_id'] not in seen_assets, path
        seen_assets.add(asset['asset_id'])
        assert asset['held_out'] is False and asset['independent_review'] == 'pending', path
        assert asset['baseline'] == 'G3-20261015-01'
        for case in asset['cases']:
            assert re.fullmatch(r'CASE-\d{3}', case['id']) and case['id'] not in seen_cases, case['id']
            seen_cases.add(case['id'])
            assert case['acceptance_refs'] and set(case['acceptance_refs']) <= known_ac, case['id']
            assert set(case.get('metric_refs', [])) <= known_met, case['id']
            assert case['title'] and case['precondition'], case['id']
            if 'expected' in case:
                assert case['expected'], case['id']
        counts[path.name] = len(asset['cases'])

    path = HERE/'authority-cases.json'
    asset = json.loads(path.read_text(encoding='utf-8'))
    assert 'AUTH-001' in (ROOT/asset['authority_document']).read_text(encoding='utf-8')
    fixture = asset['fixture']
    assert fixture['all_synthetic'] is True
    assert fixture['default_conditions']['external_adapter'] == 'fake_no_network'
    accounts = {a['account']: a for a in fixture['identities']}
    assert len(accounts) == len(fixture['identities'])
    learners = {a['learner'] for a in fixture['identities'] if a['role']=='student'}
    spaces = {s['id']: s for s in fixture['spaces']}
    assert len(spaces) == len(fixture['spaces'])
    assert all(s['learner'] in learners for s in spaces.values())
    relations = fixture['relations']
    assert len({r['id'] for r in relations}) == len(relations)
    for rel in relations:
        assert accounts[rel['parent']]['role'] == 'parent' and rel['learner'] in learners
    records = {r['id']: r for r in fixture['records']}
    assert len(records) == len(fixture['records'])
    assert all(r['space'] in spaces for r in records.values())
    help_records = {h['id']:h for h in fixture['help_records']}
    assert all(h['record'] in records for h in help_records.values())
    for c in fixture['consultations']:
        assert accounts[c['owner']]['role'] == 'parent' and c['space'] in spaces
        assert any(r['parent']==c['owner'] and r['learner']==spaces[c['space']]['learner'] for r in relations)
    for issue in fixture['cases']:
        assert set(issue.get('allowed_records', [])) <= records.keys()
        assert set(issue.get('allowed_dependencies', [])) <= help_records.keys()
    assert asset['execution_status'] == 'not_run_against_server'
    for case in asset['cases']:
        assert case['allowed'] and case['denied'] and case['evidence_required'] and case['actions'], case['id']
        assert case['authority_refs'] == ['AUTH-001']
        assert case['execution_status'] == 'not_run_against_server'
        assert case['reference_status'] == 'author_contract_reference_pending_review'
    return {'assets':len(seen_assets),'unique_case_ids':len(seen_cases),'cases_by_asset':counts,
            'authority_asset_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'authority_contract_references':'pass','synthetic_fixture_references':'pass',
            'limits':'仅编号、引用和合成输入检查；未执行后端授权、模型判断或正式质量评测。'}


if __name__ == '__main__':
    print(json.dumps(verify(), ensure_ascii=False, indent=2))
