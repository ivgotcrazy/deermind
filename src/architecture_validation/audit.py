"""Verify frozen source archives, immutable record hashes, exact refs and API accounting."""
import hashlib
import argparse
import json
import sqlite3
import zipfile
from pathlib import Path
from .common import BASE,ROOT,digest,now,write_json


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--write-report');args=parser.parse_args()
    errors=[];counts={};archives={}
    for stem,archive in [(f'preflight-freeze-v{i}',f'preflight-source-v{i}') for i in range(1,5)]+[(f'b4-freeze-v{i}',f'b4-source-v{i}') for i in (1,2)]:
        manifest=read(BASE/'reports'/f'{stem}.json')
        with zipfile.ZipFile(BASE/'reports'/f'{archive}.zip') as z:
            for name,expected in manifest['source_sha256'].items():
                data=z.read(name)
                if hashlib.sha256(data).hexdigest()!=expected:errors.append('FrozenSourceMismatch:'+name)
                archives[(name,expected)]=True
        counts[stem]=len(manifest['source_sha256'])
    contracts=read(BASE/'reports/contracts-freeze-v1.json')
    # The initial schema freeze may be satisfied by current bytes or preserved source.
    hashes=contracts.get('source_sha256',contracts.get('sha256',{}))
    for name,expected in hashes.items():
        p=ROOT/name if name.startswith('src/') else BASE/name
        archive_name=p.relative_to(ROOT).as_posix()
        if not(p.exists() and hashlib.sha256(p.read_bytes()).hexdigest()==expected) and (archive_name,expected) not in archives:errors.append('ContractFreezeUnpreserved:'+name)
    run_results={}
    for run in ('b2-real-01','b2-real-02','b2-real-03','b2-real-04','b4-primary-v1','b4-continuation-v2'):
        rows=read(BASE/'runs'/run/'records.json');exact={};refs=0
        for row in rows:
            ident=row['obj'].split(':',2)[2] if row['version'] else row['obj'] if row['revision'] else row['id']
            exact[(row['kind'],ident,row['version'],row['revision'])]=row['hash']
            if digest(row['body'])!=row['hash']:errors.append('RecordHashMismatch:'+row['id'])
            owners={'Observation':'Interaction','Evidence':'Evaluation','Belief':'Evaluation','Decision':'Interaction'}
            if row['kind'] in owners and row['owner']!=owners[row['kind']]:errors.append('WrongOwner:'+row['id'])
        def visit(value):
            nonlocal refs
            if isinstance(value,dict):
                if set(value)=={'kind','id','version','revision','content_hash'}:
                    refs+=1;key=(value['kind'],value['id'],value['version'],value['revision'])
                    if exact.get(key)!=value['content_hash']:errors.append('ExactReferenceMismatch:'+repr(key))
                for v in value.values():visit(v)
            elif isinstance(value,list):
                for v in value:visit(v)
        for row in rows:visit(row['body'])
        db=BASE/'runs'/run/'runtime.sqlite'
        with sqlite3.connect(db.as_uri()+'?mode=ro',uri=True) as connection:
            check=connection.execute('PRAGMA quick_check').fetchone()[0]
            if check!='ok':errors.append('SQLiteCheckFailed:'+run)
        run_results[run]={'record_hashes_checked':len(rows),'exact_references_checked':refs,'sqlite_quick_check':check}
    b4v1=read(BASE/'reports/b4-freeze-v1.json');b4v2=read(BASE/'reports/b4-freeze-v2.json')
    for name in ('src/architecture_validation/protocols.py','src/architecture_validation/fixtures/holdout-v1.json','src/architecture_validation/fixtures/probes-v1.json'):
        if b4v1['source_sha256'][name]!=b4v2['source_sha256'][name]:errors.append('MeasuredSemanticConfigurationChanged:'+name)
    metrics=read(BASE/'reports/metrics-v1.json');budget=read(BASE/'reports/api-budget-v1.json')
    if budget['total_attempts']!=sum(budget['counts'].values()) or budget['total_attempts']!=len(budget['reservations']):errors.append('BudgetAccountingMismatch')
    if metrics['captured_http_response_records']+len(metrics['missing_attempt_records'])!=budget['total_attempts']:errors.append('UndisclosedAttemptGap')
    if budget['total_attempts']>340 or budget['estimated_cny']>50 or budget['input_tokens']>2000000 or budget['output_tokens']>500000:errors.append('ResourceLimitExceeded')
    result={'created':now(),'status':'PASS_WITH_DISCLOSED_LOCAL_PRE_HTTP_RESERVATION_GAP' if not errors else 'FAIL','errors':errors,'frozen_source_counts':counts,'contract_sources_checked':len(hashes),
      'run_integrity':run_results,'missing_attempt_records':metrics['missing_attempt_records'],'semantic_configuration_unchanged_between_measured_versions':True,'budgets_within_limits':True}
    if args.write_report:
        target=Path(args.write_report)
        if target.exists():raise SystemExit('Refusing to overwrite an integrity report')
        write_json(target,result)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if errors:raise SystemExit(1)


if __name__=='__main__':main()
