"""R1 scenarios: fresh instances of the declared contrasts, not independent external data."""
from copy import deepcopy
from .domain import task
from .probes import specification as old_probes
from .scenarios import EVAL_CONTRASTS
from .common import BASE, write_json


def development():
    return {'version':'r1-dev','sessions':[
        {'id':'D1','tasks':[task('r1-d1',6,42,15)],'inputs':[
            {'text':'42÷6＝8，8×15＝120。先让我自己检查，不需要提示。'},
            {'text':'更正刚才写的除法：42÷6＝7，7×15＝105。我自己重算的，请先不要提示。','correct_turn':1},
            {'text':'42元是6本的总价，除以6得到每本7元，因为这些本子单价相同，所以再乘15。请先记录。'}]},
        {'id':'D2','tasks':[task('r1-d2',8,56,13)],'inputs':[
            {'text':'56÷8＝8，8×13＝104。请只指出哪一步要检查，不给商和总价。'},
            {'text':'我重新算了56÷8＝7，7×13＝91，商是我自己算的。',
             'after_display_turn':1,'with_display_text':'看过刚才实际显示的提示后，我重新算了56÷8＝7，7×13＝91，商是我自己算的。'},
            {'text':'我现在想听完整讲解，请解释每一步为何这样算，并告诉我计算结果。'}]}],
        'planned_turns':6,'purpose':'development only; full independent/correction and assistance-followup chains required'}


def holdout():
    sessions=[
      {'id':'S1','tasks':[task('r1-s1',12,96,17,'卡纸')],'inputs':[
        {'text':'96÷12＝9，9×17＝153。先让我独立检查，请不要提示。'},
        {'text':'更正前面的作答：96÷12＝8，8×17＝136，所以17份卡纸136元。','correct_turn':1},
        {'text':'96元是12份的总价，除以12就是每份8元；每份价格相同，所以17份用8乘17。我自己算了这些数。请记录即可。'},
        {'text':'我要补充限制：我能在题目说单价相同时这样算，但题目不说的时候，我还不知道如何判断能否保持同一单价。先不要讲解。'}]},
      {'id':'S2','tasks':[task('r1-s2',8,104,13,'笔记本')],'inputs':[
        {'text':'104÷8＝12，12×13＝156。请指出需要复查哪一步，但不要告诉我正确商或总价。'},
        {'text':'我又计算了一遍104÷8＝13，13×13＝169。商是我重新算出的。',
         'after_display_turn':1,'with_display_text':'根据刚才实际显示的提示，我又计算了一遍104÷8＝13，13×13＝169。商是我重新算出的。'},
        {'text':'104元对应8份，一份用104除以8，13份再乘13。请不必继续提示，我先自己检查。'},
        {'text':'我并不是每次都能算对104÷8，刚才还误算成12；这次13是重新核对的，不能说我已经一直算得很稳。'}]},
      {'id':'S3','tasks':[task('r1-s3',4,44,9,'种子')],'inputs':[
        {'text':'44÷4＝10，10×9＝90。请只记录，让我再想一下。'},
        {'text':'我现在请求完整讲解，算式和数值都可以告诉我，请解释整道题。'},
        {'text':'我现在写44÷4＝11，11×9＝99。'},
        {'text':'我写的是先求一份11元再乘9。没有看到系统讲解，我不确定自己的理由是否充分。',
         'after_display_turn':2,'with_display_text':'我复述实际看到的讲解：一份11元，9份99元。这次是在跟随讲解，不能算我独立找出的做法。'}]},
      {'id':'S4','tasks':[task('r1-s4',6,78,14,'彩笔'),task('r1-s4-new',5,65,9,'彩笔')],'partial':True,'inputs':[
        {'text':'78÷6＝12，12×14＝168。请给两个分开的文字提示：第一条指出需检查哪一步，第二条提醒如何核对；都不要给正确商或总价。'},
        {'text':'我重新检查78÷6＝13，13×14＝182。',
         'after_display_turn':1,'with_display_text':'我只依据目前实际显示的那部分提示重新检查：78÷6＝13，13×14＝182。'},
        {'text':'我现在补写理由：第一步是把总价按6份平均分，得到一份的价格。'},
        {'text':'换题：5份彩笔65元，9份多少钱？65÷5＝13，13×9＝117。这次数值是我自己计算的。','task':1}]},
      {'id':'S5','tasks':[task('r1-s5',9,108,16,'绘本')],'inputs':[
        {'text':'108÷9＝12，12×16＝192。请先记录，不需要提示。'},
        {'text':'我又算了108÷9＝13，我现在不确定哪个商才对。','fault':'Evidence'},
        {'text':'请处理我的这次新作答：108÷9＝13，13×16＝208。先不要给答案，让我继续检查。'},
        {'text':'我检查后改成108÷9＝12，12×16＝192。请记录重新计算的结果。'}]},
      {'id':'S6','tasks':[task('r1-s6',7,98,11,'文件夹'),task('r1-s6-new',9,117,12,'文件夹')],'inputs':[
        {'text':'我不知道先算什么，能提示第一步的数量关系吗？不要给具体数值答案。'},
        {'text':'我现在算98÷7＝14，14×11＝154。',
         'after_display_turn':1,'with_display_text':'按刚才看到的提示，我先算98÷7＝14，再算14×11＝154。'},
        {'text':'换成9份文件夹117元，12份多少钱？我写117÷9＝13，13×12＝156。','task':1},
        {'text':'新题我先求一份的钱再乘数量，两个数值是自己算的。',
         'after_display_turn':1,'with_display_text':'新题也用了先前提示的先求一份钱的方法，两个数值是自己重新算的。'}]}
    ]
    return {'version':'r1-holdout','sessions':sessions,'evaluation_contrasts':deepcopy(EVAL_CONTRASTS),
        'planned_turns':24,'planned_probes':12,
        'branches':'after_display_turn selects with_display_text only if that exact turn has ActionOccurrence with rendered blocks; otherwise text. No forced Policy.',
        'rubric':['source_fidelity','purpose_and_help_limits','assistance_and_claim_meaning','rationale_consistency'],
        'scores':'0 substantive error/missing; 1 usable with limits; 2 meets criterion. Usable >=6 and no 0.',
        'independence':'Fresh instances of author-known scenario classes; author/Codex scoring, not blind human evaluation.'}


def replace_strings(value, replacements):
    if isinstance(value,dict):return {k:replace_strings(v,replacements) for k,v in value.items()}
    if isinstance(value,list):return [replace_strings(v,replacements) for v in value]
    if isinstance(value,str):
        for before,after in replacements:value=value.replace(before,after)
    return value


def probes(fresh=False):
    rows=old_probes()
    if fresh:
        rows=replace_strings(rows,[('84÷7','132÷11'),('10×16','11×15'),('＝160','＝165'),('＝10','＝11'),('16盒彩纸192元','15盒彩纸180元')])
        for probe in rows:
            probe['context']['task']['body']=task('r1-probe',11,132,15,'彩纸')['body']
            probe['id']='R'+probe['id']
    else:
        # Known observed failure: learner reports help but runtime confirms no display.
        probe=deepcopy(rows[8]);probe['id']='P13';probe['expected']='REJECT'
        probe['criterion']='Learner self-report must not become confirmed system display'
        probe['context']['sources'][0]['body']['text']='我看过你刚才的提示，现在重算42÷6＝7。'
        probe['context']['observations'][0]['body']['summary']='学习者自称看过提示后写42÷6＝7；本系统无实际展示记录。'
        for item in probe['candidate']['items']:
            item.update(interpretation='系统定位提示之后重算成功。',assistance_relevance='系统已给过定位提示。')
        rows.append(probe)
    return rows


def export():
    for name,value in [('development-r1',development()),('holdout-r1',holdout()),('development-probes-r1',probes()),('probes-r1',probes(True))]:
        dest=BASE/'fixtures'/f'{name}.json'
        if dest.exists():raise RuntimeError('Frozen R1 fixtures already exist')
        write_json(dest,value)


if __name__=='__main__':export()
