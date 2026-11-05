"""Check this authored reference's structure and arithmetic, not LLM semantics."""

from copy import deepcopy
from fractions import Fraction
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASPECTS = {'independent', 'explanation', 'transfer', 'retention'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def index(objects):
    refs = [f"{obj['id']}@{obj['version']}" for obj in objects]
    require(len(refs) == len(set(refs)), 'duplicate object reference')
    return dict(zip(refs, objects))


def validate(package, cases):
    tasks = index(package['task_templates'])
    solutions = index(package['solution_templates'])
    knowledge = index(package['knowledge_components'])
    claims = index(package['claims'])
    questions = index(package['questions'])
    targets = index([package['learning_target'], *package['target_variants']])
    domain = package['domain']['id'] + '@' + package['domain']['version']
    for obj in [*tasks.values(), *solutions.values(), *knowledge.values()]:
        require(obj['domain_ref'] == domain, 'wrong domain')
    for obj in knowledge.values():
        require(not obj['personal_state'], 'KC personal state is forbidden')
        require(set(obj['prerequisite_refs']) <= knowledge.keys(), 'missing KC prerequisite')
    for task_ref, obj in tasks.items():
        require(not any(k in obj for k in ['kc_refs', 'direct_kc_refs', 'knowledge_refs']), 'direct Task-KC link')
        require(bool(obj['solution_refs']), 'task has no method')
        for solution_ref in obj['solution_refs']:
            require(solution_ref in solutions, 'missing method')
            require(solutions[solution_ref]['task_ref'] == task_ref, 'method task mismatch')

    def kc_union(solution_ref, visiting=()):
        require(solution_ref not in visiting, 'recursive solution cycle')
        require(solution_ref in solutions, 'missing child method')
        solution = solutions[solution_ref]
        refs = set(solution['direct_kc_refs'])
        require(refs <= knowledge.keys(), 'missing direct KC')
        for child in solution['children']:
            require(child['task_ref'] in tasks, 'missing child task')
            require(child['solution_ref'] in tasks[child['task_ref']]['solution_refs'], 'unbound child method')
            require(set(child['inputs']) == set(solutions[child['solution_ref']]['inputs']), 'child inputs mismatch')
            refs |= kc_union(child['solution_ref'], (*visiting, solution_ref))
        return refs

    unions = {r: set().union(*(kc_union(s) for s in t['solution_refs'])) for r, t in tasks.items()}
    require(set().union(*unions.values()) == knowledge.keys(), 'KC has no task/method path')
    for obj in claims.values():
        require(isinstance(obj['task_ref'], str) and obj['task_ref'] in tasks, 'Claim must bind one task version')
        require(obj['type'] == 'TaskProficiencyClaim', 'non-Task Claim')
        require(set(obj['aspects']) == ASPECTS, 'missing default aspect')
        require(set(obj['conditions']['solution_refs']) <= set(tasks[obj['task_ref']]['solution_refs']), 'Claim methods mismatch')
    for obj in targets.values():
        require(obj['claim_ref'] in claims, 'target Claim missing')
        require({r['aspect'] for r in obj['requirements']} <= ASPECTS, 'invalid target aspect')
        require(set(obj['allowed_solution_refs']) <= set(claims[obj['claim_ref']]['conditions']['solution_refs']), 'target methods mismatch')
        require(not obj['ready_for_formal_assessment'], 'reference must not be activated')
    for page in package['source_pages']:
        require(hashlib.sha256((HERE / page['file']).read_bytes()).hexdigest() == page['sha256'], 'source hash mismatch')
    for question in questions.values():
        require(question['task_ref'] in tasks, 'question task missing')
        p = question['parameters']
        a, r = Fraction(p['a']), Fraction(p['r'])
        require(a > 0 and 0 < r < 1, 'invalid increase parameters')
        if p['quantity_kind'] == 'discrete':
            require(a.denominator == 1 and (a*r).denominator == 1, 'invalid discrete quantity')
        require(Fraction(question['reference']['answer']) == a*(1+r) == a+a*r, 'answer mismatch')
        require(question['reference']['unit'] == p['unit'], 'unit mismatch')
        require(not question['formal_use'], 'reference question activated')
        require(set(question['reference']['allowed_solution_refs']) <= set(tasks[question['task_ref']]['solution_refs']), 'question methods mismatch')
    seen = set()
    for case in cases['cases']:
        require(case['id'] not in seen, 'duplicate case')
        seen.add(case['id'])
        require(case['package_ref'] == package['asset_id']+'@'+package['version'], 'case package mismatch')
        require(case['input']['question_ref'] in questions, 'case question missing')
        require(case['preconditions']['claim_ref'] in claims, 'case Claim missing')
        require(case['preconditions']['target_ref'] in targets, 'case target missing')
        expected = case['expected']
        changed = set(expected['belief_aspect_effects'])
        unchanged = set(expected['unchanged_aspects'])
        require(not changed & unchanged and changed | unchanged == ASPECTS, 'aspect effect partition')
        require(case['execution'] == {'status': 'not_run', 'actual': None}, 'authored reference claims runtime result')
    return {r: sorted(k) for r, k in unions.items()}


def main():
    package = json.loads((HERE/'package.json').read_text(encoding='utf-8'))
    cases = json.loads((HERE/'cases.json').read_text(encoding='utf-8'))
    unions = validate(package, cases)
    mutations = [
        ('direct Task-KC link', lambda p: p['task_templates'][0].update(kc_refs=['KC-M1-BASE@1'])),
        ('missing method', lambda p: p['task_templates'][0]['solution_refs'].append('MISSING@1')),
        ('recursive solution cycle', lambda p: p['solution_templates'][2]['children'].append(
            {'task_ref':'TT-M1-INCREASE@1','solution_ref':'ST-M1-PARTS@1',
             'inputs':{'a':'a','r':'r','unit':'unit'},'output_binding':'cycle'})),
        ('Claim must bind one task version', lambda p: p['claims'][0].update(task_ref=['TT-M1-INCREASE@1','TT-M1-SCALE@1'])),
        ('missing default aspect', lambda p: p['claims'][0]['aspects'].pop('retention')),
        ('answer mismatch', lambda p: p['questions'][0]['reference'].update(answer='2')),
        ('invalid discrete quantity', lambda p: p['questions'][2]['parameters'].update(a='3')),
    ]
    for expected_error, mutate in mutations:
        invalid = deepcopy(package)
        mutate(invalid)
        try:
            validate(invalid, cases)
        except ValueError as error:
            require(str(error) == expected_error, f'wrong rejection for {expected_error}: {error}')
        else:
            raise ValueError(f'accepted invalid fixture: {expected_error}')
    print(json.dumps(dict(
        asset_check='passed', negative_checks=len(mutations), question_arithmetic_checks=len(package['questions']),
        reference_cases=len(cases['cases']), source_hash_checks=len(package['source_pages']),
        derived_task_kc=unions, semantic_run='not_run', runtime_run='not_run',
        limitation='Only reference structure, source hashes, and arithmetic were checked.'), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
