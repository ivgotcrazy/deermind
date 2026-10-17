"""检查本章节候选的引用、来源覆盖及数学约束；不运行 LLM 或判定教学质量。"""
from fractions import Fraction as F
from pathlib import Path
import ast
import hashlib
import json

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PACKAGE = HERE / 'package.json'
CASES = ROOT / 'src/mvp_foundation/evaluation/fractions-content-cases.json'
REFERENCES = HERE / 'source-references.json'


def evaluate(text):
    def walk(node):
        if isinstance(node, ast.Constant) and type(node.value) is int:
            return F(node.value)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            return -walk(node.operand)
        if isinstance(node, ast.BinOp):
            a, b = walk(node.left), walk(node.right)
            if isinstance(node.op, ast.Add): return a + b
            if isinstance(node.op, ast.Sub): return a - b
            if isinstance(node.op, ast.Mult): return a * b
            if isinstance(node.op, ast.Div): return a / b
        raise ValueError('Unsupported expression node: ' + type(node).__name__)
    return walk(ast.parse(text, mode='eval').body)


def verify():
    p = json.loads(PACKAGE.read_text(encoding='utf-8'))
    c = json.loads(CASES.read_text(encoding='utf-8'))
    groups = ['knowledge_components', 'problem_templates', 'solution_templates', 'claims', 'original_problems']
    objects = [o for group in groups for o in p[group]] + [p['material'], p['target']]
    ids = [o['id'] for o in objects]
    assert len(ids) == len(set(ids)), 'Duplicate object ID'
    lookup = {o['id']+'@'+o['version']: o for o in objects}
    for group in groups:
        for o in p[group]:
            assert o['version'] == '1', o['id']

    def refs(values, expected):
        valid = {o['id']+'@'+o['version'] for o in p[expected]}
        assert set(values) <= valid, (expected, set(values) - valid)

    for t in p['problem_templates']:
        refs(t['solution_refs'], 'solution_templates')
        refs(t['knowledge_refs'], 'knowledge_components')
        assert t['constraints'] and t['responsibility'] and t['variation_axes']
        for s in t['solution_refs']:
            assert t['id']+'@1' in lookup[s]['applies_to'], (t['id'], s)
    for s in p['solution_templates']:
        refs(s['applies_to'], 'problem_templates')
        refs(s['knowledge_refs'], 'knowledge_components')
        refs([r['ref'] for r in s['subproblem_refs']], 'problem_templates')
        assert s['condition'] and s['steps'] and s['output']

    inventory = p['material']['inventory']
    source_keys = {r['key'] for r in inventory}
    assert len(source_keys) == len(inventory)
    assert {page for row in inventory for page in row['pages']} == set(range(49, 57))
    for row in inventory:
        refs(row['template_refs'], 'problem_templates')
        refs(row['knowledge_refs'], 'knowledge_components')
        assert row['status'] and row['location']
    requirements = p['target']['requirements']
    requirements_by_id = {r['id']: r for r in requirements}
    assert len(requirements_by_id) == len(requirements)
    for row in requirements:
        refs(row['template_refs'], 'problem_templates')
        refs(row['knowledge_refs'], 'knowledge_components')
        refs([row['claim_ref']], 'claims')
        assert set(row['source_keys']) <= source_keys
        claim = lookup[row['claim_ref']]
        assert set(row['template_refs']) <= set(claim['problem_refs'])
    for row in p['claims']:
        refs(row.get('problem_refs', []), 'problem_templates')
        refs([row['knowledge_ref']] if 'knowledge_ref' in row else [], 'knowledge_components')
        assert row['supporting'] and row['counterevidence'] and row['insufficient']

    checked = []
    for item in p['original_problems']:
        refs([item['template_ref']], 'problem_templates')
        assert set(item['requirement_ids']) <= requirements_by_id.keys()
        b, name = item['binding'], item['template_ref']
        if name == 'PT-FA-CHAIN@1':
            middle = F(b['a'])*F(b['r'])
            actual = middle*F(b['s'])
            assert middle.denominator == actual.denominator == 1
        elif name == 'PT-FA-COMPARE@1':
            a, other = F(b['a']), F(b['b'])
            assert a > 0 and other > 0
            actual = abs(other-a)/a
            assert abs(other-a)/other == F(item['reference']['reverse_answer'])
        elif name == 'PT-FA-COMBINE@1':
            actual = F(b['a'])*sum(map(F, b['coefficients']))
            assert actual >= 0
            if b['quantity_kind'] == 'discrete': assert actual.denominator == 1
        elif name == 'PT-FA-EXPR@1':
            actual = evaluate(b['expression'])
            if item['id'] == 'ITEM-FA-05':
                assert evaluate('3/4 / (1/2 / (3/8))') == F(item['reference']['changed_expression_answer'])
        elif name == 'PT-FA-TRIPS@1':
            capacity, ratio, trips = F(b['capacity']), F(b['ratio']), F(b['large_trips'])
            mass, small = capacity*trips, capacity*ratio
            q = mass/small
            actual = F(-(-q.numerator//q.denominator))
            assert (actual-1)*small < mass <= actual*small
            assert q == F(item['reference']['quotient'])
        else:
            raise AssertionError(name)
        assert actual == F(item['reference']['answer']), (item['id'], actual)
        checked.append({'id':item['id'], 'answer':str(actual)})

    # 改变参数独立核对两条方法的等价性及运次边界，避免只检查八个固定答案。
    variants = 0
    for a in [F(1, 2), F(6), F(24), F(40)]:
        for r in [F(1, 4), F(2, 3), F(3, 2)]:
            for s in [F(1, 5), F(3, 4)]:
                assert (a*r)*s == a*(r*s)
                assert a+a*r == a*(1+r)
                assert a*r-a*s == a*(r-s)
                variants += 1
    for a, b in [(F(24),F(30)), (F(10),F(6)), (F(7),F(7))]:
        assert (b-a)/a == b/a-1
        assert (a-b)/a == 1-b/a
    for ratio in [F(1,2),F(2,5),F(3,4)]:
        for trips in [1,3,6]:
            q=F(trips)/ratio
            n=-(-q.numerator//q.denominator)
            assert (n-1)*ratio < trips <= n*ratio
    assert (F(10)*F(1,3)).denominator != 1  # CASE-057 的非法离散参数

    case_ids = [case['id'] for case in c['cases']]
    all_cases = []
    for file in (ROOT/'src/mvp_foundation/evaluation').glob('*.json'):
        all_cases += [row['id'] for row in json.loads(file.read_text(encoding='utf-8')).get('cases',[])]
    assert len(all_cases) == len(set(all_cases)), 'Duplicate CASE ID'
    req = (ROOT/'doc/mvp/phase-3-definition/MVP_Requirements_and_Acceptance.md').read_text(encoding='utf-8')
    metrics = (ROOT/'doc/mvp/phase-3-definition/MVP_Validation_Plan.md').read_text(encoding='utf-8')
    for case in c['cases']:
        refs(case['item_refs'], 'original_problems')
        refs(case['claim_refs'], 'claims')
        assert all(ref in req for ref in case['acceptance_refs'])
        assert all(ref in metrics for ref in case['metric_refs'])
        assert case['expected'] and case['forbidden'] and case['reference_status']=='author_reference_pending_review'
    assert c['held_out'] is False and c['independent_review']=='pending'
    assert p['activation']=='not_published_not_adopted'
    assert all(v=='pending' for k,v in p['review'].items() if k!='reviewer')
    probe = next(i for i in p['original_problems'] if i['id']=='ITEM-FA-07')
    scope = next(d for d in p['scope_decisions'] if d['decision_ref']=='DEC-019')
    assert probe['use_policy']['first_batch_required_assessment'] is False
    assert probe['use_policy']['allowed_uses'] == scope['allowed_uses'] == ['optional_practice','transfer_probe']
    assert scope['first_batch_required_assessment'] is False
    assert any(e['decision_ref']=='DEC-019' and e['scope']==scope['scope'] for e in p['target']['assessment_exclusions'])
    governance = (ROOT/'doc/mvp/MVP_Governance.md').read_text(encoding='utf-8')
    assert scope['decision_ref'] in governance and scope['source_ref'] in governance

    # 对照作者独立写下的期望值计算，不从表达式生成同一份“答案”。
    source = json.loads(REFERENCES.read_text(encoding='utf-8'))
    assert source['package_ref'] == p['asset_id']+'@'+p['version']
    assert p['source_reference_asset']['id'] == source['asset_id']
    assert p['source_reference_asset']['version'] == source['version']
    assert (HERE / p['source_reference_asset']['path']).resolve() == REFERENCES.resolve()
    assert source['verification']['held_out'] is False
    assert source['verification']['independent_review'] == 'pending'
    assert source['reviewer'] is None
    source_rows = source['rows']
    assert len(source_rows) == len({r['id'] for r in source_rows}) == 51
    assert {r['source_key'] for r in source_rows} == source_keys
    assert {r['page'] for r in source_rows} == set(range(49,57))
    source_lookup = {r['key']: r for r in inventory}
    figures = {d['id']: d for d in source['diagrams']}
    assert len(figures) == len(source['diagrams']) == 8
    reference_checks = 0
    for row in source_rows:
        assert row['page'] in source_lookup[row['source_key']]['pages'], row['id']
        refs(row['template_refs'], 'problem_templates')
        assert set(row['template_refs']) <= set(source_lookup[row['source_key']]['template_refs'])
        assert row['required'] and row['reasoning'] and row['reference_answer']
        assert row['review_status'] == 'author_checked_pending_independent_review'
        if row['diagram_ref']: assert row['diagram_ref'] in figures
        for check in row['checks']:
            assert evaluate(check['expression']) == F(check['expected']), (row['id'], check)
            reference_checks += 1
    assert {r['diagram_ref'] for r in source_rows if r['diagram_ref']} == set(figures)
    relation_checks = 0
    for figure in figures.values():
        assert figure['role'] == 'answer_reference_only'
        for row in figure['rows']:
            assert F(row['value']) > 0 and isinstance(row['parts'], int) and 1 <= row['parts'] <= 12
            assert row['origin'] in ['given','derived','result']
        for rel in figure['relations']:
            a, b = figure['rows'][rel['from']], figure['rows'][rel['to']]
            assert F(b['value'])/F(a['value']) == F(rel['ratio']), (figure['id'],rel)
            relation_checks += 1
    assert {r['printed_page'] for r in source['source_images']} == set(range(49,57))
    local_images_checked = 0
    for row in source['source_images']:
        assert row['image_index'] == row['printed_page']+3
        assert len(row['sha256']) == 64 and all(c in '0123456789abcdef' for c in row['sha256'])
        image_path = ROOT/'.tmp/textbook-source-20261016'/f"page-{row['image_index']:03d}.png"
        if image_path.exists():
            assert hashlib.sha256(image_path.read_bytes()).hexdigest() == row['sha256']
            local_images_checked += 1
    return {
        'package_sha256':hashlib.sha256(PACKAGE.read_bytes()).hexdigest(),
        'cases_sha256':hashlib.sha256(CASES.read_bytes()).hexdigest(),
        'source_references_sha256':hashlib.sha256(REFERENCES.read_bytes()).hexdigest(),
        'definitions':{g:len(p[g]) for g in groups},
        'source_inventory_groups':len(inventory), 'requirements':len(requirements),
        'reference_integrity':'pass', 'numeric_examples':checked,
        'parameter_combinations_checked':variants, 'transport_boundaries_checked':9,
        'cases':len(case_ids), 'all_development_case_ids_unique':len(all_cases),
        'source_reference_rows':len(source_rows), 'source_numeric_checks':reference_checks,
        'reference_diagrams':len(figures), 'diagram_ratio_checks':relation_checks,
        'local_source_images_hash_checked':local_images_checked,
        'limits':'静态引用、数值与声明边界检查；不是独立语义复核、模型运行或 G4 通过。'
    }


if __name__ == '__main__':
    print(json.dumps(verify(), ensure_ascii=False, indent=2))
