"""One reserved finite run. Per-case author review gates all subsequent calls."""
import argparse
from dataclasses import replace
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import time

from foundation.cases import EvidenceRecorder
from foundation.exit_campaign import CONFIG, ROOT, read, run_schedule
from foundation.llm import DeepSeekAdapter, load_config
from prepare_spike_exit import PACK, RUN, hashed, preflight, write


def verify():
    plan = read(CONFIG.relative_to(ROOT).as_posix())
    preflight(plan)
    frozen = json.loads((PACK / 'manifest.json').read_text(encoding='utf-8'))
    if frozen['status'] != 'OFFLINE_READY':
        raise ValueError('ExitPackageNotReady')
    for p, h in frozen['source_sha256'].items():
        if hashed(ROOT / p) != h:
            raise ValueError('ExitFrozenSourceMismatch:' + p)
    for p, h in frozen['artifact_sha256'].items():
        if hashed(PACK / p) != h:
            raise ValueError('ExitFrozenArtifactMismatch:' + p)
    if hashed(CONFIG) != frozen['configuration_sha256']:
        raise ValueError('ExitConfigurationMismatch')
    return plan, frozen


def await_author_review(directory, spec, row, records, deadline):
    """The author inspects retained raw output; matching hashes prevent stale review reuse."""
    path = directory / 'reviews' / (spec['id'] + '.json')
    record_hash = sha256(json.dumps(records, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()
    write(directory / 'review-request.json', {'case_id': spec['id'], 'case': spec, 'row': row,
        'records_sha256': record_hash, 'decision_file': path.relative_to(directory).as_posix(),
        'required_decision': 'ACCEPT or REJECT, author note and exact records hash',
        'deadline_remaining_seconds': max(0, deadline - time.monotonic()),
        'review_independence': 'Same-session author; not independent blind review'})
    print(json.dumps({'event': 'AUTHOR_REVIEW_REQUIRED', 'case_id': spec['id'],
                     'records_sha256': record_hash}, ensure_ascii=False), flush=True)
    while time.monotonic() < deadline:
        if path.exists():
            review = json.loads(path.read_text(encoding='utf-8'))
            if (review.get('case_id') != spec['id'] or review.get('records_sha256') != record_hash
                    or review.get('decision') not in ('ACCEPT', 'REJECT')
                    or not isinstance(review.get('note'), str) or not review['note'].strip()):
                return False
            return review['decision'] == 'ACCEPT'
        time.sleep(0.25)
    return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='store_true')
    args = parser.parse_args()
    plan, frozen = verify()
    loaded = load_config(ROOT)
    if not loaded.api_key or loaded.model != plan['model']['model']:
        raise ValueError('ExitConfiguredModelOrKeyMismatch')
    model = replace(loaded, base_url=plan['model']['provider_endpoint'], max_calls=375,
                    max_output_tokens=4096, timeout_seconds=60)
    if not args.run:
        print(json.dumps({'status': 'READY_NOT_STARTED', 'already_reserved': RUN.exists(),
            'model': model.public(), 'executions': 66, 'derived_boundaries': 4, 'max_calls': 375,
            'wall_time_seconds': 3600, 'semantic_support_claimed': False}, ensure_ascii=False))
        return 0
    RUN.mkdir(parents=True, exist_ok=False)
    (RUN / 'cases').mkdir()
    (RUN / 'reviews').mkdir()
    started = datetime.now(timezone.utc).isoformat()
    clock_start = time.monotonic()
    write(RUN / 'manifest.json', {'started_at': started, 'source_sha256': frozen['source_sha256'],
        'preparation_manifest_sha256': hashed(PACK / 'manifest.json'), 'public_model_config': model.public(),
        'authorization': 'User continue under finite exit checklist and budget', 'attempt': 1,
        'retries': 0, 'replacement_cases': 0, 'automatic_followup_campaign': False})
    state = {'case': None}

    class RecordedAdapter(DeepSeekAdapter):
        def complete(self, messages, purpose, *, output_contract=None):
            print(json.dumps({'event': 'call_start', 'case': state['case'], 'call': self.calls + 1,
                              'purpose': purpose}, ensure_ascii=False), flush=True)
            try:
                return super().complete(messages, purpose, output_contract=output_contract)
            finally:
                write(RUN / 'adapter-records.json', self.records)
                print(json.dumps({'event': 'call_end', 'call': self.calls,
                    'status': self.records[-1]['status'] if self.records else 'NOT_STARTED'}), flush=True)

    adapter = RecordedAdapter(model)
    def before(spec):
        verify()
        state['case'] = spec['id']
        # Only the nine mechanism gaps preserve the original output-token configuration.
        adapter.config = replace(model, max_output_tokens=2048 if spec['group'] in ('E2', 'F2', 'X1', 'X2') else 4096)
        print(json.dumps({'event': 'case_start', 'case': spec['id']}, ensure_ascii=False), flush=True)
    try:
        result = run_schedule(plan, adapter, lambda id: EvidenceRecorder(RUN / 'cases' / (id + '.jsonl')),
            before_case=before, content_review=lambda spec, row, records: await_author_review(
                RUN, spec, row, records, clock_start + 3600))
    except Exception as exc:
        # Preserve partial records and never implicitly resume a reserved directory.
        result = {'rows': [{'id': s['id'], 'execution': 'INTERRUPTED_REVIEW_RAW_EVIDENCE'
            if (RUN / 'cases' / (s['id'] + '.jsonl')).exists() else 'NOT_RUN'} for s in plan['schedule']],
            'boundaries': [{'variant': b, 'coverage': 'NOT_RUN'} for b in plan['boundaries']],
            'stop_reason': 'UnexpectedRunnerFailure:' + type(exc).__name__}
    write(RUN / 'adapter-records.json', adapter.records)
    write(RUN / 'results.json', result)
    summary = {'status': 'CLOSED_STOPPED' if result['stop_reason'] else 'CLOSED_PENDING_EXIT_ASSESSMENT',
        'started_at': started, 'completed_at': datetime.now(timezone.utc).isoformat(),
        'elapsed_seconds': round(time.monotonic() - clock_start, 3), 'actual_model_calls': adapter.calls,
        'max_calls': 375, 'wall_time_seconds': 3600, 'stop_reason': result['stop_reason'],
        'completed_cases': sum(r['execution'] == 'COMPLETED' for r in result['rows']),
        'failed_cases': sum(r['execution'] == 'FAILED' for r in result['rows']),
        'not_run_cases': sum(r['execution'] == 'NOT_RUN' for r in result['rows']),
        'not_run_boundaries': sum(r['coverage'] == 'NOT_RUN' for r in result['boundaries']),
        'semantic_support_claimed': False, 'original_full_cases_completed': 9,
        'original_A2': 'DENIED', 'gate_E': 'OPEN', 'gate_F': 'OPEN',
        'retries': 0, 'replacement_cases': 0, 'automatic_followup_campaign': False}
    write(RUN / 'summary.json', summary)
    write(RUN / 'artifact-sha256.json', {p.relative_to(RUN).as_posix(): hashed(p)
        for p in sorted(RUN.rglob('*')) if p.is_file()})
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    return 1 if result['stop_reason'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
