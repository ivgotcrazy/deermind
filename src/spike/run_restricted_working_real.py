"""One reserved real attempt against the immutable working integration package."""
import argparse
from dataclasses import replace
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import time

from foundation.cases import EvidenceRecorder
from foundation.llm import DeepSeekAdapter, load_config
from foundation.working_campaign import run_batch
from preflight_restricted_working import CONFIG, preflight

ROOT = Path(__file__).resolve().parents[2]
PACK = ROOT / 'src/spike/review-packages/restricted-working-v1'
RUN = ROOT / 'src/spike/runs/restricted-working-real-v1'


def write(path, value):
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))


def hashed(path):
    return sha256(path.read_bytes()).hexdigest()


def verify():
    ready = preflight()
    frozen = json.loads((PACK / 'manifest.json').read_text(encoding='utf-8'))
    for name, expected in frozen['source_sha256'].items():
        if hashed(ROOT / name) != expected:
            raise ValueError('FrozenSourceMismatch:' + name)
    for name, expected in frozen['artifact_sha256'].items():
        if hashed(PACK / name) != expected:
            raise ValueError('FrozenArtifactMismatch:' + name)
    if ready['configuration_sha256'] != frozen['configuration_sha256']:
        raise ValueError('FrozenConfigurationMismatch')
    ledger = json.loads((ROOT / 'src/spike/reports/validation-progress-v1.json').read_text(encoding='utf-8'))
    for name, expected in ledger['evidence_sha256'].items():
        if hashed(ROOT / name) != expected:
            raise ValueError('LedgerEvidenceMismatch:' + name)
    return ready, frozen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='store_true')
    args = parser.parse_args()
    ready, frozen = verify()
    config = json.loads(CONFIG.read_text(encoding='utf-8'))
    loaded = load_config(ROOT)
    if not loaded.api_key or loaded.model != config['model']['model']:
        raise ValueError('ConfiguredModelOrKeyMismatch')
    model = replace(loaded, base_url=config['model']['provider_endpoint'],
                    max_calls=config['budget']['max_calls'],
                    max_output_tokens=config['model']['max_output_tokens'],
                    timeout_seconds=config['model']['timeout_seconds'])
    if not args.run:
        print(json.dumps({'status':'READY_NOT_STARTED', 'model':model.public(),
                          'plan':ready, 'run_directory_exists':RUN.exists()}, ensure_ascii=False))
        return 0
    RUN.mkdir(parents=True, exist_ok=False)
    (RUN / 'cases').mkdir()
    started = datetime.now(timezone.utc).isoformat()
    write(RUN / 'manifest.json', {'started_at':started, 'configuration_sha256':hashed(CONFIG),
        'integration_manifest_sha256':hashed(PACK / 'manifest.json'),
        'source_sha256':frozen['source_sha256'],
        'runner_sha256':hashed(Path(__file__)), 'public_model_config':model.public(),
        'authorization':'User continue after fixed real execution plan',
        'attempt':1, 'retries':0, 'replacement_cases':0})
    state = {'case':None}

    class RecordedAdapter(DeepSeekAdapter):
        def complete(self, messages, purpose, *, output_contract=None):
            print(json.dumps({'event':'call_start', 'case':state['case'],
                              'call':self.calls+1, 'purpose':purpose}, ensure_ascii=False), flush=True)
            try:
                return super().complete(messages, purpose, output_contract=output_contract)
            finally:
                write(RUN / 'adapter-records.json', self.records)
                print(json.dumps({'event':'call_end', 'call':self.calls,
                    'status':self.records[-1]['status'] if self.records else 'NOT_STARTED'},
                    ensure_ascii=False), flush=True)

    adapter = RecordedAdapter(model)

    def before_case(spec):
        verify()
        state['case'] = spec['id']
        print(json.dumps({'event':'case_start', 'id':spec['id']}, ensure_ascii=False), flush=True)

    clock_start = time.monotonic()
    unexpected = None
    try:
        result = run_batch(config, adapter,
            lambda identity:EvidenceRecorder(RUN / 'cases' / (identity+'.jsonl')),
            before_case=before_case)
    except Exception as exc:
        # Do not echo arbitrary provider or environment exception strings.
        unexpected = type(exc).__name__
        specs = config['fixed_review_controls'] + config['normal_cases']
        result = {'rows':[{'id':s['id'], 'execution':'INTERRUPTED_REVIEW_RAW_EVIDENCE'
            if (RUN/'cases'/(s['id']+'.jsonl')).exists() else 'NOT_RUN'} for s in specs],
            'stop_reason':'UnexpectedRunnerFailure:'+unexpected,
            'calls':adapter.calls, 'content_review_required':True, 'semantic_support_claimed':False}
    write(RUN / 'adapter-records.json', adapter.records)
    write(RUN / 'results.json', result)
    summary = {'status':'STOPPED' if result['stop_reason'] else 'COMPLETED_CONTENT_REVIEW_REQUIRED',
        'started_at':started, 'completed_at':datetime.now(timezone.utc).isoformat(),
        'elapsed_seconds':round(time.monotonic()-clock_start, 3),
        'actual_calls':adapter.calls, 'planned_calls':config['budget']['planned_calls'],
        'max_calls':config['budget']['max_calls'], 'wall_time_seconds':config['budget']['wall_time_seconds'],
        'stop_reason':result['stop_reason'],
        'completed_cases':sum(r['execution']=='COMPLETED' for r in result['rows']),
        'failed_cases':sum(r['execution']=='FAILED' for r in result['rows']),
        'not_run_cases':sum(r['execution']=='NOT_RUN' for r in result['rows']),
        'content_review_required':True, 'semantic_support_claimed':False,
        'original_full_cases_completed':9, 'original_A2':'DENIED', 'gate_E':'OPEN', 'gate_F':'OPEN',
        'retries':0, 'replacement_cases':0, 'unexpected_failure_type':unexpected}
    write(RUN / 'summary.json', summary)
    write(RUN / 'artifact-sha256.json', {p.relative_to(RUN).as_posix():hashed(p)
        for p in sorted(RUN.rglob('*')) if p.is_file()})
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    return 1 if result['stop_reason'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
