"""Fixed R3 regression inputs and fresh instances, frozen before model calls."""
from copy import deepcopy
import hashlib
import json
from .common import BASE,ROOT,write_json
from .domain import task
from .protocols import review_rule_ids
from .revalidate import prepare_probe
from .scenarios import EVAL_CONTRASTS


def bind_checks(schema,purpose,context):
    schema=deepcopy(schema);checks=schema['properties']['checks']
    item=deepcopy(checks['prefixItems'][0] if 'prefixItems' in checks else checks['items'])
    items=[]
    for name in review_rule_ids(purpose,[c['id'] for c in context.get('claims',[])]):
        child=deepcopy(item);child['properties']['rule_id']={'const':name};items.append(child)
    if not items:raise ValueError('No review scope')
    schema['properties']['checks']={'type':'array','prefixItems':items,'items':False,'minItems':len(items),'maxItems':len(items)}
    return schema


def replay(label,purpose,role,expected,criterion):
    sid=label.split('.')[0];root=BASE/'runs/g2-r2/v2'/sid
    packets=json.loads((root/'review-packets.json').read_text(encoding='utf-8'))
    tid=next(p['turn']['id'] for p in packets if p['turn']['label']==label)
    rows=json.loads((root/'records.json').read_text(encoding='utf-8'))
    rec=next(r['body']['model_record'] for r in rows if r['kind']=='ReasoningExecution' and r['turn_id']==tid and r['body']['purpose']==purpose and r['body']['role']==role)
    context=json.loads(rec['messages'][1]['content']);schema=rec['schema']
    if role=='review':schema=bind_checks(schema,purpose,context)
    source=root/'model-calls'/(rec['attempt_id']+'.json')
    return {'purpose':purpose,'role':role,'expected':expected,'criterion':criterion,'source':source.relative_to(ROOT).as_posix(),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'context':context,'schema':schema}


def specification():
    entries=[
      ('S3.1','Evidence','review','FAIL','Wrong arithmetic and no relation explanation are not counterevidence to unit meaning.'),
      ('S4.1','Evidence','review','FAIL','Same missing-versus-negative distinction in a second original failure.'),
      ('S3.2','Belief','review','FAIL','Do not retain the mistaken unit-relation negative merely because it was committed.'),
      ('S6.3','Evidence','review','FAIL','Prior method help remains relevant after changing numbers/tasks.'),
      ('S6.4','Belief','review','FAIL','Explicit reuse of earlier method cannot support no-help whole-task independence.'),
      ('S1.1','Evidence','review','PASS','Arithmetic counterevidence and absent relation explanation remain distinct.'),
      ('S1.2','Evidence','review','PASS','Unassisted corrected calculation supports limited calculation Claims.'),
      ('S2.2','Evidence','review','PASS','Actual location-only help limits whole-task independence but preserves calculating the quotient.'),
      ('S6.2','Evidence','review','PASS','Method was supplied, quotient was not; Claim responsibilities differ.'),
      ('S5.3','Belief','review','PASS','Mixed arithmetic evidence with legitimate UNKNOWN for relation meaning.'),
    ]
    replays=[replay(*entry) for entry in entries]
    probes=json.loads((BASE/'fixtures/probes-r1.json').read_text(encoding='utf-8'))
    for pid in ('RP05','RP06'):
        p=next(p for p in probes if p['id']==pid);ctx,schema,_=prepare_probe(p)
        replays.append({'purpose':'Policy','role':'review','expected':'PASS' if pid=='RP05' else 'FAIL','criterion':'Policy rationale diagnostic; not independently a G2 readiness veto','context':ctx,'schema':schema,'source':'fixtures/probes-r1.json:'+pid})
    for args in [
      ('S3.1','Evidence','generation','AUTHOR_REVIEW','Unit relation NonInformative, division negative; no ability overclaim.'),
      ('S3.2','Belief','generation','AUTHOR_REVIEW','Reject the historical false unit counterevidence in the inference; do not silently retain a negative direction.'),
      ('S6.3','Evidence','generation','AUTHOR_REVIEW','Retain prior method influence on no-help task Claim; numeric computation can still support its own Claim.'),
      ('S6.4','Belief','generation','AUTHOR_REVIEW','Do not propagate old task-independence support that excluded prior method solely due to task change.')]:
        replays.append(replay(*args))
    for i,r in enumerate(replays,1):r['id']=f'R{i:02}'
    old=json.loads((BASE/'fixtures/holdout-r1.json').read_text(encoding='utf-8'))
    live=deepcopy([old['sessions'][2],old['sessions'][5]])
    for s in live:s['id']='D'+s['id'][1:]
    live += [
      {'id':'N1','tasks':[task('r3-negative',6,42,15)],'inputs':[{'text':'42元是6份的总价，我把42元当成每份的价格，所以42×15＝630。请先只记录。'}],'acceptance':'Explicit total-versus-unit confusion provides genuine counterevidence to unit meaning, unlike mere omission.'},
      {'id':'N2','tasks':[task('r3-positive',6,42,15)],'inputs':[{'text':'42元按6份平均分，一份7元，所以15份是7×15＝105。我先独立核对，不要提示。'}],'acceptance':'Equal division into six shares explains unit meaning; limited support rather than mechanically UNKNOWN.'}]
    return {'version':'evaluation-repair-r3','replays':replays,'live':live,'formal':formal(),
        'readiness':'R01-R10 actual PASS/FAIL matches; all four new generations meet their specific meaning constraints; ten live turns completed and usable with no persistence of either root error. R11/R12 Policy diagnostics disclosed separately. Author assessment required; no keyword scorer.'}


def formal():
    def case(sid,args,inputs,extra=None,partial=False):
        tasks=[task('r3-'+sid.lower(),*args)]
        if extra:tasks.append(task('r3-'+sid.lower()+'-new',*extra))
        return {'id':sid,'tasks':tasks,'inputs':inputs,'partial':partial}
    sessions=[
      case('S1',(7,112,12,'卡纸'),[
        {'text':'112÷7＝17，17×12＝204。请先让我独立检查，不要提示。'},
        {'text':'更正前面的作答：112÷7＝16，16×12＝192，所以12份卡纸192元。','correct_turn':1},
        {'text':'112元是7份的总价，按7份平均分就是每份16元；每份价格相同，所以12份用16乘12。我自己算了，请记录即可。'},
        {'text':'补充限制：只有知道单价相同时我才会这样算；题目没说时，我还不知道怎么判断单价是否不变。先不要讲解。'}]),
      case('S2',(5,90,9,'笔记本'),[
        {'text':'90÷5＝17，17×9＝153。请指出需要复查哪一步，不要告诉我正确商或总价。'},
        {'text':'我重新算90÷5＝18，18×9＝162，商是我重新算出的。','after_display_turn':1,'with_display_text':'根据刚才实际显示的提示，我重算90÷5＝18，18×9＝162，商是我重新算出的。'},
        {'text':'90元对应5份，一份的钱用90除以5，再乘9。请不必继续提示，我先自己检查。'},
        {'text':'我不是每次都能算对90÷5，刚才还误算成17；18是重新核对的，不能说已经一直算得稳。'}]),
      case('S3',(6,78,8,'种子'),[
        {'text':'78÷6＝12，12×8＝96。请只记录，让我再想一下。'},
        {'text':'我现在请求完整讲解，算式和数值都可以告诉我，请解释整道题。'},
        {'text':'我现在写78÷6＝13，13×8＝104。'},
        {'text':'我写的是每份13元再乘8。没看到系统讲解，我不确定理由是否充分。','after_display_turn':2,'with_display_text':'我复述实际看到的讲解：一份13元，8份104元。这次是跟随讲解，不是我独立找出的做法。'}]),
      case('S4',(8,96,15,'彩笔'),[
        {'text':'96÷8＝11，11×15＝165。请给两个分开的文字提示：第一条指出需检查哪一步，第二条提醒如何核对；都不要给正确商或总价。'},
        {'text':'我重新检查96÷8＝12，12×15＝180。','after_display_turn':1,'with_display_text':'我只依据目前实际显示的那部分提示重算：96÷8＝12，12×15＝180。'},
        {'text':'我补写理由：第一步是把总价按8份平均分，得到一份的价格。'},
        {'text':'换题：7份彩笔77元，13份多少钱？77÷7＝11，11×13＝143。这次数值是我自己算的。','task':1}],extra=(7,77,13,'彩笔'),partial=True),
      case('S5',(11,88,17,'绘本'),[
        {'text':'88÷11＝8，8×17＝136。请先记录，不需要提示。'},
        {'text':'我又算了88÷11＝9，我现在不确定哪个商才对。','fault':'Evidence'},
        {'text':'请处理我的新作答：88÷11＝9，9×17＝153。先不要给答案，让我继续检查。'},
        {'text':'检查后改为88÷11＝8，8×17＝136。请记录重新计算的结果。'}]),
      case('S6',(9,135,7,'文件夹'),[
        {'text':'我不知道先算什么，能提示第一步的数量关系吗？不要给具体数值答案。'},
        {'text':'我现在算135÷9＝15，再算15×7＝105。','after_display_turn':1,'with_display_text':'按刚才实际看到的提示，我先算135÷9＝15，再算15×7＝105。'},
        {'text':'换成6份文件夹84元，11份多少钱？我写84÷6＝14，14×11＝154。','task':1},
        {'text':'新题我先求一份的钱再乘数量，两个数值自己算的。','after_display_turn':1,'with_display_text':'新题也用了先前提示的先求一份钱的方法，两个数值是自己重新算的。'}],extra=(6,84,11,'文件夹'))]
    return {'sessions':sessions,'evaluation_contrasts':deepcopy(EVAL_CONTRASTS),'planned_turns':24,'planned_probes':12,'independence':'Fresh numeric instances of author-known scenario families; no claim of independent blinded evaluation.'}


if __name__=='__main__':
    dest=BASE/'fixtures/evaluation-repair-r3.json'
    if dest.exists():raise SystemExit('Refusing to replace frozen input preparation')
    write_json(dest,specification())
