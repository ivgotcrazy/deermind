"""Explicit author corrections for this fixed run, based on visual source inspection.
This is NOT an automatic correction algorithm and does NOT improve raw extraction scores.
"""
import copy
from datetime import datetime,timezone
from pipeline import ROOT,read,save,digest,content_errors

RUN='20261105T024756Z'
review_start='2026-11-05T02:48:42+00:00'
cases=read(ROOT/'cases.json');reference=read(ROOT.parent/'reference.json')
def n(v):return {'op':'number','value':str(v)}
def frac(a,b):return {'op':'fraction','args':[n(a),n(b)]}
def op(name,*args):return {'op':name,'args':list(args)}
def txt(s):return {'type':'text','text':s}
def part(region,blocks):return {'regionIndex':region,'blocks':blocks}
def changes(before,after,path=''):
    if before==after:return []
    if isinstance(before,dict) and isinstance(after,dict) and before.keys()==after.keys():return [x for k in before for x in changes(before[k],after[k],path+'/'+k)]
    if isinstance(before,list) and isinstance(after,list) and len(before)==len(after):return [x for i,(a,b) in enumerate(zip(before,after)) for x in changes(a,b,path+'/'+str(i))]
    return [dict(path=path,before=before,after=after)]

for case in cases:
    cid=case['id'];folder=ROOT/'runs'/RUN/cid;original=read(folder/'extract-output.json');data=copy.deepcopy(original);task=data['tasks'][0]
    if cid=='C02':
        task['question'].append(part(1,[txt('请列式解决问题。'),{'type':'table','headers':['答句'],'rows':[[{'state':'response_blank','value':None}]],'unit':''}]))
        task['solutions']=[
          {'content':[part(1,[txt('先求摄影小组有多少人，再……'),{'type':'worked_example','expressions':[op('multiply',op('multiply',n(12),frac(1,3)),frac(3,4)),n(3)],'assertedCorrect':True},txt('结果单位：人。')])]},
          {'content':[part(1,[txt('先求航模小组的人数是气象小组的几分之几。'),{'type':'worked_example','expressions':[op('multiply',n(12),op('group',op('multiply',frac(1,3),frac(3,4)))),op('multiply',n(12),frac(1,4)),n(3)],'assertedCorrect':True},txt('结果单位：人。')])]}
        ]
        task['teachingAids']=[part(1,[txt('你能看懂笑笑的方法吗？')])]
        data['uncertainties']=['原图约分笔迹未逐笔结构化；左列演算按首式与结果规范化展示，未伪造约分过程。','插画人物外观不是题目条件；保留文字给定的人数和比例。']
        judgment='needs_substantial_correction';notes=['把两个原有方法分成两个解法对象。','修复三元乘法及把“人”作为公式节点的非法结构；单位改为文本。','把待填答句放回题面，独立提示从解法移出。','依原图规范化运算展示；约分标注仍是已知缺口。']
    elif cid=='C03':
        b=task['question'][1]['blocks'][0]
        b['expressions'][0]=op('divide',op('multiply',frac(7,8),frac(3,4)),frac(1,3))
        b['expressions'][1]=op('multiply',op('multiply',frac(7,8),frac(3,4)),frac(1,3))
        judgment='core_content_correct_normalization_needed';notes=['原始输出的除号、各数值、三行及错误结果均保留正确。','原 AST 右结合与原式数值等价，但改成从左到右结合以保留教材运算次序；没有改变错误演算。','约分笔迹未逐笔表达，仍保留此缺口。']
    elif cid=='C05':
        charts=copy.deepcopy(next(e for e in reference['elements'] if e['id']=='E-CHARTS')['content'][1:])
        for b in charts:
            b.pop('derivedFrom',None);b.pop('conversion',None)
        task['question'][0]['blocks'].extend(charts)
        data['uncertainties']=['模型漏掉全部三个图表；作者依据本轮原图重新核对首轮人工参考中的系列、数值、单位及刻度后补入。','精确 RGB 并非教学语义；重绘用固定近似颜色并保留类别对应。']
        judgment='critical_content_missing';notes=['原始输出没有任何 chart 块，不能因 JSON 合格判定提取完成。','三个统计图均为作者补齐，不计为本轮 LLM 提取成功。','题目提问和三条提示无需改动；已分开放置。']
    else:
        judgment='selected_content_accepted';notes=['核对原图：六种形状、顺序、六个可见点、剪图要求均有表达。','点只声明视觉上接近中间；尺寸与多边形规则性由示意布局决定，不作为新的题目已知关系。','附页图1未提供，不据此宣称完整动手活动可以替代。']
    assert not content_errors(case,data),content_errors(case,data)
    diff=changes(original,data);save(folder/'reviewed-content.json',data)
    save(folder/'content-review.json',dict(reviewer='Codex author source comparison; not independent human',decision='accept_for_mapping',rawJudgment=judgment,originalHash=digest(original),reviewedContentHash=digest(data),reviewWindowStart=review_start,reviewWindowEnd=datetime.now(timezone.utc).isoformat(),timingScope='Shared content inspection/edit window across four cases; includes author analysis and correction-script writing. Do not sum per-case times or use as end-user editing time.',notes=notes,changes=diff))
    print(cid,judgment,'changed_paths',len(diff))
