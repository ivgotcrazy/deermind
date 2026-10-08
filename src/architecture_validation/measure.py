"""Single frozen B4 campaign: 24 planned turns and 12 probes, no cherry-picked retries."""
import argparse
import json
from pathlib import Path
import time
from playwright.sync_api import sync_playwright
from .common import BASE, Rejected, now, write_json
from .contracts import WIRE, validate
from .harness import Server
from .model import RealModel, Budget
from .protocols import RULES, review_system


def load(name):return json.loads((BASE/name).read_text(encoding='utf-8'))


def packet(rows,turn,input_spec):
    selected=[r for r in rows if r['turn_id']==turn['id']]
    kinds=('Observation','Evidence','Belief','Decision','ActionOccurrence','ActivityTransitionOccurred','EvaluationCompletion','RuntimeFailure','AttemptFailure','StageTiming','TurnTiming')
    return {'turn':turn,'input':input_spec,'records':[{'id':r['id'],'kind':r['kind'],'revision':r['revision'],'body':r['body']} for r in selected if r['kind'] in kinds],
        'failed_reviews':[r['body'] for r in selected if r['kind']=='Validation' and r['body']['verdict']!='PASS']}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run',default='b4-primary-v1');parser.add_argument('--start-session',default='S1');a=parser.parse_args()
    path=BASE/'runs'/a.run
    if path.exists():raise SystemExit('Refusing to overwrite B4 evidence')
    frozen=load('fixtures/holdout-v1.json');all_cases=frozen['sessions'];start_index=next(i for i,c in enumerate(all_cases) if c['id']==a.start_session);frozen['sessions']=all_cases[start_index:]
    report={'created':now(),'status':'RUNNING','start_session':a.start_session,'sessions':[],'probes':[],'active_segments':[],'network_pause':None}
    dest=BASE/'reports'/f'{a.run}.json';packets=[];stopped=False
    phase_start=time.monotonic();budget_before=load('reports/api-budget-v1.json')['active_b4_seconds']
    with Server(path,'real','B4') as srv,sync_playwright() as pw:
        browser=pw.chromium.launch()
        for case in frozen['sessions']:
            sid=case['id'];tasks=[]
            # Register the exact frozen proposal; do not regenerate or rename its text.
            for proposal in case['tasks']:
                tasks.append(srv.request('/admin/canonical',proposal,True)['id'])
            page=srv.page(browser,sid,tasks[0],{'maxBlocks':1} if case.get('partial') else None)
            session={'id':sid,'turns':[],'browser':{},'coverage_notes':[]};report['sessions'].append(session)
            for n,item in enumerate(case['inputs'],1):
                label=f'{sid}.{n}';q=tasks[item.get('task',0)]
                body=case['tasks'][item.get('task',0)]['body'];page.locator('#task').evaluate('(node,text)=>node.textContent=text',body['statement'])
                if item.get('fault'):srv.request('/admin/test/fault',{'purpose':item['fault']},True)
                correction=None
                if item.get('correct_turn'):
                    prior=session['turns'][item['correct_turn']-1]['id']
                    observations=[r for r in srv.records(sid,'Observation') if r['turn_id']==prior]
                    if observations:correction=observations[-1]['id']
                    else:session['coverage_notes'].append(label+': correction target unavailable because preceding Observation did not commit')
                before=time.perf_counter();turn=srv.submit(sid,item['text'],q,str(n),correction)
                result=srv.settled(sid,turn['id'],900);result.update(label=label,wall_seconds=time.perf_counter()-before,injected_fault=item.get('fault'))
                if item.get('fault'):srv.request('/admin/test/fault',{'purpose':None},True)
                session['turns'].append(result)
                rows=srv.records(sid);packets.append(packet(rows,result,item))
                write_json(path/'review-packets.json',packets);write_json(dest,report)
                print({'unit':label,'status':result['status'],'error':result['error'],'seconds':round(result['wall_seconds'],2)},flush=True)
                if result['status']=='WAITING_EFFECT':
                    # Controlled browser is stopped and confirms only actually rendered blocks.
                    page.evaluate('window.stopChannel()');session['coverage_notes'].append(label+': required controlled channel reconciliation')
                if 'Transport' in result['error']:
                    report['network_pause']={'unit':label,'reason':result['error']};stopped=True;break
                if 'BudgetExhausted' in result['error'] or time.monotonic()-phase_start+budget_before>=5400:
                    stopped=True;report['stop_reason']=result['error'] or 'ExecutionTimeBudgetExhausted';break
            session['browser']={'text':page.locator('#conversation').inner_text(),'rendered':page.evaluate('window.buildTest.rendered')}
            page.screenshot(path=str(path/(sid+'.png')),full_page=True);page.close();write_json(dest,report)
            if stopped:break
        srv.export();browser.close()
    elapsed=time.monotonic()-phase_start;report['active_segments'].append({'kind':'sessions','seconds':elapsed})
    budget=Budget(BASE/'reports/api-budget-v1.json');budget.data['active_b4_seconds']=max(budget.data['active_b4_seconds'],budget_before+elapsed);budget.save()
    if not stopped:
        phase_start=time.monotonic();model=RealModel('B4',path/'model-calls')
        for probe in load('fixtures/probes-v1.json'):
            result={'id':probe['id'],'purpose':probe['purpose'],'expected':probe['expected'],'criterion':probe['criterion']}
            try:
                output,record=model.complete(review_system(probe['purpose']),probe['context']|{'candidate':probe['candidate'],'candidate_id':probe['id']},WIRE['Review'],'Probe:'+probe['purpose'],'probe')
                validate(WIRE['Review'],output)
                complete=len(output['checks'])==len(RULES[probe['purpose']]) and {c['rule_id'] for c in output['checks']}==set(RULES[probe['purpose']])
                passed=output['verdict']=='PASS' and complete and all(c['verdict']=='PASS' for c in output['checks'])
                result.update(output=output,attempt_id=record['attempt_id'],review_complete=complete,accepted=passed,
                    matched=(passed if probe['expected']=='PASS' else output['verdict'] in ('FAIL','UNRESOLVED') and complete),status='COMPLETED')
            except Rejected as exc:result.update(status='FAILED',failure=str(exc),matched=False)
            report['probes'].append(result);write_json(dest,report);print({'unit':probe['id'],'status':result['status'],'matched':result['matched']},flush=True)
            if 'Transport' in result.get('failure','') or 'BudgetExhausted' in result.get('failure',''):stopped=True;break
        model.budget.refresh_active();model.budget.save();report['active_segments'].append({'kind':'probes','seconds':time.monotonic()-phase_start})
    report.update(status='STOPPED' if stopped else 'COMPLETED',completed=now(),planned_turns=24,planned_probes=12,budget=load('reports/api-budget-v1.json'))
    write_json(dest,report)


if __name__=='__main__':main()
