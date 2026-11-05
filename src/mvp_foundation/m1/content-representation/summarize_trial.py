"""Read immutable answers for inspection; never repair model output or fill from reference."""
import json
from collections import Counter
from pathlib import Path
from jsonschema import Draft202012Validator

ROOT=Path(__file__).resolve().parent
RUNS=['20261104T233715Z','20261104T233824Z']
schema=json.loads(ROOT.joinpath('extraction-schema.json').read_text(encoding='utf-8'))
block_validator=Draft202012Validator({'$defs':schema['$defs'],'$ref':'#/$defs/block'})
notes={
 'C01':['三道算式的运算符、分数和括号与参考核对一致；未编造答案。','根 taskId=T-C01，但只创建 TI-C01-1/2/3，不能据此入库。试验规定每例一个主任务，对三小题而言也偏生硬，应将题组组织与题目本身分开。'],
 'C02':['主问题的三个条件及两种解法读出，关联同一道任务的意图明确。','超出所选范围，提取了整页其他题；额外演算出现非法公式节点。还将教材提示放入题面引用，并新建与现有模板重复的候选。'],
 'C03':['保留了错误结果7/32，但把原式中的除以1/3写成乘以1/3，导致错误发生的位置失真。','乘法节点提供三个参数而格式规定二元运算；这同时存在内容错误和格式错误，不能只修格式就判通过。'],
 'C04':['六个人数及行列对应一致，三个待填格正确保留为空。','数据表被归为教学辅助、未进入题目的内容引用；题面反而引用了讨论提示。另有主任务编号不一致。'],
 'C05':['两组数量、四个比例、类别、图名、刻度及包含关系与参考核对一致，可从返回数据重绘三图。','任务编号不一致，题面引用了教学提示；与现有 TaskTemplate 重复新建。颜色为近似值，单位仅写“亿”，缺“人”。'],
 'C06':['识别出六种形状，但 scene 未包含中心点，正方形绘成12×18长方形，六边形部分坐标超出画布。','把所提供领域目录中的作者说明复制成“教材原文”；说明提取阶段不应同时输入包含解释的领域目录。该原因是基于原样输出的判断，尚未通过拆分实验验证。','任务和 owner 引用不一致，且超范围提取了整页其他内容。'],
 'C07':['文字包含方向角和距离，但结构只记录若干点和说明，没有可重绘的方向轴、射线与角弧；读懂意思不等于完成图形提取。','元素 owner 指向自身，任务引用失效；还提取了范围外内容。'],
 'C08':['返回文本中能看到四个视图及圆锥顶视中心点；但 JSON 存在语法错误，不能作为合格结构化输出。','额外抽取下方手电实验；将领域目录的概括写为教材原文；未保留顶部两个立体对象的结构。']
}
attempts=[]; latest={}
for run in RUNS:
    summary=json.loads((ROOT/'runs'/run/'summary.json').read_text(encoding='utf-8'))
    for record in summary['records']:
        row=dict(record,run=run);attempts.append(row)
        if row.get('httpStatus')==200:latest[row['caseId']]=row
cases=[]
for cid,row in sorted(latest.items()):
    folder=ROOT/'runs'/row['run']/cid
    data=json.loads((folder/'extracted.json').read_text(encoding='utf-8')) if (folder/'extracted.json').exists() else None
    preview=[]
    if data:
        for e in data.get('elements',[]):
            blocks=[]
            for b in e.get('content',[]):
                problems=[error.message for error in block_validator.iter_errors(b)]
                blocks.append(dict(value=b,renderable=not problems,errors=problems))
            preview.append(dict(id=e.get('id'),owner=e.get('owner'),role=e.get('role'),origin=e.get('origin'),blocks=blocks))
    cases.append(dict(row,review=notes[cid],preview=preview,answerPath=f"runs/{row['run']}/{cid}/answer.txt",raw=(folder/'answer.txt').read_text(encoding='utf-8')))
totals=dict(attempts=len(attempts),http200=sum(a.get('httpStatus')==200 for a in attempts),transportErrors=sum(a['status']=='transport_error' for a in attempts),statuses=dict(Counter(c['status'] for c in cases)),promptTokens=sum(c.get('usage',{}).get('prompt_tokens',0) for c in cases),completionTokens=sum(c.get('usage',{}).get('completion_tokens',0) for c in cases))
result=dict(status='author_review_complete_not_import_approved',totals=totals,attempts=attempts,cases=cases,notes=['One explicit retry of the two transport failures; no prompt or schema changes; no further calls','Local socksio setup failure before any API request is logged separately','Block previews preserve returned data and do not repair failed references','Review is by the author, not independent expert validation'])
ROOT.joinpath('results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(totals))
