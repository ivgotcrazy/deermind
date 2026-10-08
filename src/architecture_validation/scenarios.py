"""Predeclared held-out learner inputs and review rubrics, never sent as answer keys."""
from .domain import task


SESSIONS=[
 {'id':'S1','tasks':[task('s1',8,56,13,'支笔')],'inputs':[
  {'text':'56÷8＝6，6×13＝78。请先让我独立完成，不用提示。'},
  {'text':'更正刚才的计算：56÷8＝7，7×13＝91，所以13支笔91元。','correct_turn':1},
  {'text':'56元对应8支笔，除以8得到每支7元，再乘13得到13支的钱。我自己重新算了除法和乘法。'},
  {'text':'我要补充：我会按这个顺序计算，但还不能解释为什么不同数量时单价一定不变。请暂时不要讲解。'}],
  'acceptance':'原始错误与更正均留存；已失效错误 Evidence 不进入新 Belief；计算证据与单位关系解释分别评价，不能一次成功宣称普遍掌握。'},
 {'id':'S2','tasks':[task('s2',9,72,14,'本练习册')],'inputs':[
  {'text':'72÷9＝9，9×14＝126。请只告诉我哪一步需要检查，不要说正确的商或总价。'},
  {'text':'我重新计算了除法：72÷9＝8，8×14＝112。我自己算出了商。'},
  {'text':'请先不要继续提示。72元是9本的钱，一本的钱应由72除以9得到，之后乘14。'},
  {'text':'我发现自己有时仍会把72÷9算成9，需要检查；这次写8是重新算过的。'}],
  'acceptance':'实际定位帮助限制独立整题 Claim；未给商时仍可支持定位提示条件下的除法 Claim；自报波动应限制能力推断。'},
 {'id':'S3','tasks':[task('s3',5,45,12,'袋种子')],'inputs':[
  {'text':'我写45÷5＝8，8×12＝96。先记录就行，让我再想想。'},
  {'text':'我改变主意了，请完整讲解这道题，告诉我每一步怎么计算。'},
  {'text':'现在我写45÷5＝9，9×12＝108。'},
  {'text':'我能跟着刚才讲解复述：先算一袋9元，再乘12。这个做法和计算是你刚才告诉我的。'}],
  'acceptance':'讲解请求本身不等于已展示；真实 Control 后才能完整讲解；复述及答案正确不证明独立完成或独立算商。'},
 {'id':'S4','tasks':[task('s4',7,63,11,'盒彩笔')],'partial':True,'inputs':[
  {'text':'63÷7＝8，8×11＝88。请用两条分开的提示帮我检查，但不要给正确的商或总价。'},
  {'text':'我只根据目前显示的提示，重算63÷7＝9，9×11＝99。'},
  {'text':'我想说明：第一步是在算一盒的价钱；这段解释是我现在自己写的。'},
  {'text':'接着换一道同类题：4盒彩笔28元，10盒多少钱？我算28÷4＝7，7×10＝70。','task':1}],
  'extra_task':task('s4-new',4,28,10,'盒彩笔'),
  'acceptance':'仅第一实际渲染块作为帮助；不把未显示块纳入经历；新题保留历史帮助并判断其相关性，不自动视为独立。'},
 {'id':'S5','tasks':[task('s5',6,54,16,'本绘本')],'inputs':[
  {'text':'54÷6＝9，9×16＝144。先不需要提示。'},
  {'text':'我又算成54÷6＝8了，我不确定。','fault':'Evidence'},
  {'text':'刚才那次处理没完成。请重新根据我现在写的54÷6＝8、8×16＝128作判断，不用直接给答案。'},
  {'text':'我自己核对后更正为54÷6＝9，9×16＝144。请记录这次更正。'}],
  'acceptance':'预定 Evaluation 故障单列，不能伪造 Policy 或成功 UNKNOWN；后续真实重新评价可恢复并处理反向材料。'},
 {'id':'S6','tasks':[task('s6',3,24,17,'个文件夹')],'inputs':[
  {'text':'我不知道该先除还是乘。请只提示怎么开始，不要直接给数值答案。'},
  {'text':'我按目前的提示先算24÷3＝8，再算8×17＝136。'},
  {'text':'换一道同类题：8个文件夹40元，15个多少钱？我写40÷8＝5，5×15＝75。','task':1},
  {'text':'新题我也是按刚才的先求单价再乘数量的方法做的；数值是自己计算的。'}],
  'extra_task':task('s6-new',8,40,15,'个文件夹'),
  'acceptance':'新题与先前方法提示的关联必须解释；整题独立 Claim 与自行计算 Claim 分开。'}
]
for s in SESSIONS:
    if 'extra_task' in s:s['tasks'].append(s.pop('extra_task'))

EVAL_CONTRASTS={
 'EVAL-01':{'turns':['S1.2','S1.3','S2.2'],'claims':['claim-task','claim-unit','claim-division'],
  'required':'同次表现的整题、关系解释、允许定位提示下自行除法有不同依据与范围；不以一次成功断言掌握。'},
 'EVAL-02':{'turns':['S2.1','S2.2','S3.2','S3.3','S4.1','S4.2','S4.4','S6.3','S6.4'],
  'required':'请求/意图与已发生展示有别；部分展示只认实际块；换题不清除相关帮助；不同 Claim 帮助责任不同。'},
 'EVAL-03':{'turns':['S1.1','S1.2','S1.4','S2.2','S2.4'],
  'required':'更正后旧 Evidence 已失效且不被引用；正反或限制材料改变依据、解释或明确保持理由，不能只加 revision。'},
 'EVAL-04':{'turns':['S1.3','S3.2','S5.2','S5.3'],
  'required':'有信息表现、只有请求的不足与执行失败分开；故障后新轮真实评价，不用旧 Belief 冒充本轮完成。'}
}


def specification():
    return {'version':'v1','sessions':SESSIONS,'evaluation_contrasts':EVAL_CONTRASTS,
        'rubric':['source_fidelity','purpose_and_help_limits','assistance_and_claim_meaning','rationale_consistency'],
        'scores':'Each 0 substantive error/missing, 1 usable with limits, 2 meets criterion. Usable >=6 and no 0.',
        'planned_turns':24,'planned_probes':12,'branches':'Only specified fault, correction target binding, task change, first-block client rendering. No forced Policy action; no action means uncovered if needed.',
        'independence':'Author/Codex review; same-provider reviewer is fallible, not independent human validation.'}
