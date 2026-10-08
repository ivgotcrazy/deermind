"""Build exit: known-error containment, NOT semantic quality or autonomous repair.

Only existing Store/Engine owner paths are used. No model API, maintenance service,
or production semantic override is introduced by these mechanical fixtures.
"""
from copy import deepcopy
import hashlib
import sqlite3

import pytest

from architecture_validation.common import BASE, Rejected, write_json
from architecture_validation.domain import task
from architecture_validation.runtime import Engine
from architecture_validation.store import Store
from architecture_validation.testing import ScriptedModel


class KnownErrorFixture(ScriptedModel):
    """An explicitly authored wrong interpretation, followed by authored repair."""
    def __init__(self):
        super().__init__(policy='Hint')
        self.repaired = False

    def complete(self, system, context, schema, purpose, category='base'):
        output, record = super().complete(system, context, schema, purpose, category)
        if purpose == 'Evidence' and not self.repaired:
            for item in output['items']:
                item.update(relation='Contradicts', interpretation='故意注入的错误评价夹具；不代表模型判断')
        return output, record


@pytest.fixture
def case(tmp_path, request):
    store = Store(tmp_path / 'runtime.sqlite')
    store.bootstrap()
    task_id = store.canonical(task('exit-mechanism', 6, 42, 15, '练习本'))
    store.start_session('s')
    model = KnownErrorFixture()
    engine = Engine(store, model, test_mode=True)
    yield store, engine, model, task_id
    write_json(BASE / 'reports/build-exit-v1/mechanisms' / (request.node.name + '.json'), {
        'scope': 'Fixed-response mechanism check; no model accuracy claim',
        'api_calls': 0, 'scripted_calls': model.calls, 'records': store.rows(),
    })
    store.db.close()


def begin(case, key='initial'):
    store, engine, _, task_id = case
    turn = store.enqueue('s', key, '机制夹具作答', task_id)
    assert store.claim_turn(engine.worker_epoch)['id'] == turn['id']
    return turn['id']


def evaluated(case):
    store, engine, _, _ = case
    turn = begin(case)
    observation = engine.step(turn, 'Observation')[0][0]
    evidence = engine.step(turn, 'Evidence', observation)[0]
    beliefs, unchanged, context = engine.step(turn, 'Belief', observation)
    completion = engine.evaluation_completion(turn, evidence, beliefs, unchanged, context, observation)
    return turn, observation, evidence, beliefs, completion


def unchanged_history(store, before):
    assert all(store.get(rid) == row for rid, row in before.items())


def test_known_error_owner_replacement_and_pending_effect(case):
    store, engine, model, _ = case
    turn, observation, evidence, beliefs, completion = evaluated(case)
    decision = engine.step(turn, 'Policy', observation, completion)[0][0]
    intent = store.create_intent(decision)
    before = {r['id']: deepcopy(r) for r in store.rows()}
    target = evidence[0]
    affected = store.invalidate(target, 'admin')
    assert set(beliefs + [completion, decision, intent]) <= set(affected)
    assert store.current(observation)
    assert all(store.current(rid) for rid in evidence[1:])
    with pytest.raises(Rejected, match='NoCurrentValidState'):
        store.head(store.get(target)['obj'])
    with pytest.raises(Rejected, match='RequiredEvaluationUnavailable'):
        engine.context(turn, 'Policy', observation, completion)
    assert store.dispatch('s', store.session('s')['epoch']) is None
    assert store.intent(intent)['status'] == 'NOT_OCCURRED'
    call_start = len(model.calls)
    model.repaired = True
    replacements = engine.step(turn, 'Evidence', observation)[0]
    new_beliefs, unchanged, context = engine.step(turn, 'Belief', observation)
    new_completion = engine.evaluation_completion(turn, replacements, new_beliefs, unchanged, context, observation)
    assert model.calls[call_start:] == ['Evidence', 'Review:Evidence', 'Belief', 'Review:Belief']
    assert all(store.get(rid)['owner'] == 'Evaluation' for rid in replacements + new_beliefs)
    replacement = next(store.get(rid) for rid in replacements if store.get(rid)['obj'] == store.get(target)['obj'])
    assert replacement['revision'] == store.get(target)['revision'] + 1
    assert replacement['body']['relation'] == 'NonInformative'
    assert not set(evidence + beliefs) & set(store.get(context)['body']['control']['refs'])
    assert all(store.current(rid) for rid in replacements + new_beliefs + [new_completion])
    assert all(not store.current(rid) for rid in evidence + beliefs + [completion])
    assert len(store.rows('Event', 's')) == 1
    assert len(store.rows('Decision', 's')) == len(store.rows('ActionIntent', 's')) == 1
    assert not store.rows('ActionOccurrence', 's')
    unchanged_history(store, before)
    store.finish(turn)


@pytest.mark.parametrize('failure', ['generation', 'validation'])
def test_failed_replacement_never_restores_known_error(case, failure):
    store, engine, model, _ = case
    turn, observation, evidence, beliefs, completion = evaluated(case)
    before = {r['id']: deepcopy(r) for r in store.rows()}
    store.invalidate(evidence[0], 'admin')
    if failure == 'generation':
        model.fail_next = 'Evidence'
    else:
        model.review_verdict = 'FAIL'
    with pytest.raises(Rejected):
        engine.step(turn, 'Evidence', observation)
    assert len(store.rows('Evidence', 's')) == 3
    assert len(store.rows('Belief', 's')) == 3
    assert not store.rows('Belief', 's', current=True)
    assert not store.current(evidence[0]) and not store.current(completion)
    with pytest.raises(Rejected, match='RequiredEvaluationUnavailable'):
        engine.context(turn, 'Policy', observation, completion)
    assert not store.rows('Decision', 's') and not store.rows('ActionIntent', 's')
    store.recover()
    assert not store.current(evidence[0])
    assert all(not store.current(rid) for rid in beliefs)
    unchanged_history(store, before)


def test_quarantine_persists_and_next_turn_uses_fresh_basis(case):
    store, engine, model, _ = case
    turn, observation, evidence, beliefs, completion = evaluated(case)
    decision = engine.step(turn, 'Policy', observation, completion)[0][0]
    intent = store.create_intent(decision)
    dispatch = store.dispatch('s', store.session('s')['epoch'])
    store.acknowledge('s', dispatch['dispatch_id'], dispatch['epoch'], dispatch['payload_hash'],
                      [b['block_id'] for b in dispatch['payload']['blocks']])
    store.finish(turn)
    before = {r['id']: deepcopy(r) for r in store.rows()}
    with pytest.raises(Rejected, match='Unauthorized'):
        store.invalidate(evidence[0], 'learner')
    assert store.current(evidence[0])
    store.invalidate(evidence[0], 'admin')
    assert store.intent(intent)['status'] == 'OCCURRED'
    assert store.current(store.rows('ActionOccurrence', 's')[0]['id'])
    # Reopen the persisted store without changing any historical input or result.
    store.db.close()
    store.db = Store(store.path).db
    model.repaired = True
    model.policy = 'NoIntervention'
    engine.worker_epoch = store.recover()
    assert not store.current(evidence[0]) and not store.rows('Belief', 's', current=True)
    assert store.head(store.get(evidence[0])['obj'], required=False) is None
    next_turn = begin(case, 'new-user-input')
    engine.process(next_turn)
    assert store.turn(next_turn)['status'] == 'COMPLETED'
    context = next(r for r in store.rows('Context', 's') if r['turn_id'] == next_turn and r['body']['control']['purpose'] == 'Belief')
    assert evidence[0] not in context['body']['control']['refs']
    assert not set(beliefs) & set(context['body']['control']['refs'])
    assert len(store.rows('Belief', 's', current=True)) == 3
    assert not store.current(evidence[0])  # No replacement of this historical target was claimed.
    assert len(store.rows('ActionOccurrence', 's')) == len(store.rows('ActionIntent', 's')) == 1
    unchanged_history(store, before)


@pytest.mark.parametrize('sid,targets', [
    ('S3', ['evidence_d9d2dda9f0cc411baa9b6e21449b778a']),
    ('S6', ['evidence_8a3e580d24b74032baf57a7e8457bfec', 'evidence_c1a3f35efaad42e990c2c157b8960b47']),
])
def test_existing_error_records_can_be_quarantined_without_rewriting_history(tmp_path, sid, targets):
    source = BASE / 'runs/g2-r2/v2' / sid / 'runtime.sqlite'
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    destination = tmp_path / 'copy.sqlite'
    with sqlite3.connect(source.resolve().as_uri() + '?mode=ro', uri=True) as src:
        with sqlite3.connect(destination) as dst:
            src.backup(dst)
    store = Store(destination)
    try:
        before = {r['id']: deepcopy(r) for r in store.rows()}
        old_beliefs = [r['id'] for r in store.rows('Belief', sid, current=True)]
        assert old_beliefs
        affected = store.invalidate(targets[0], 'admin')
        if len(targets) > 1:
            assert targets[1] not in affected and store.current(targets[1])
            affected += store.invalidate(targets[1], 'admin')
        assert all(not store.current(rid) for rid in targets)
        affected_beliefs = [rid for rid in old_beliefs if rid in affected]
        unaffected_beliefs = [rid for rid in old_beliefs if rid not in affected]
        assert affected_beliefs
        assert all(not store.current(rid) for rid in affected_beliefs)
        assert all(store.current(rid) for rid in unaffected_beliefs)
        assert {r['id'] for r in store.rows('Belief', sid, current=True)} == set(unaffected_beliefs)
        for row in store.rows('Belief', sid, current=True):
            assert all(store.current(store.resolve(ref)['id']) for ref in row['body']['evidence_basis'])
        assert len(store.rows('Event', sid)) == sum(r['kind'] == 'Event' and r['sid'] == sid for r in before.values())
        assert len(store.rows()) == len(before) + len(targets)
        unchanged_history(store, before)
        write_json(BASE / 'reports/build-exit-v1/mechanisms' / (sid + '-actual-error-quarantine.json'), {
            'scope': 'Read-only R2 source copied; manual exact targets, no error detection or semantic recomputation',
            'source': source.relative_to(BASE.parents[1]).as_posix(), 'source_sha256': source_hash,
            'targets': targets, 'affected': sorted(set(affected)), 'prior_current_beliefs': old_beliefs,
            'old_records_unchanged': len(before), 'api_calls': 0, 'new_actions': 0,
            'affected_beliefs': affected_beliefs, 'remaining_current_beliefs': unaffected_beliefs,
        })
    finally:
        store.db.close()
    assert hashlib.sha256(source.read_bytes()).hexdigest() == source_hash
