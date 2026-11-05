"""Author-curated fixtures, NOT OCR output. Rebuild the versioned reference pack."""
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[3]
ROOT.joinpath('source').mkdir(parents=True, exist_ok=True)
sources = []
for page in [11, 49, 50, 67, 86, 91, 92, 93]:
    if page in [49, 50, 91, 92, 93]:
        source = REPO / f'doc/mvp/m1/prototype/public/materials/bnu6a/page-{page}.png'
    else:
        source = REPO / f'.tmp/textbook-source-20261102/page-{page + 3:03}.jpg'
    destination = ROOT / 'source' / f'page-{page}{source.suffix}'
    shutil.copyfile(source, destination)
    sources.append(dict(id=f'P{page}', printedPage=page, readerIndex=page+3,
                        file=f'source/{destination.name}', sha256=hashlib.sha256(destination.read_bytes()).hexdigest()))

def n(value): return dict(op='number', value=str(value))
def f(a, b): return dict(op='fraction', args=[n(a), n(b)])
def op(name, *args): return dict(op=name, args=list(args))
def para(text): return dict(type='text', text=text)
def formula(expression, latex): return dict(type='formula', expression=expression, latex=latex)
def ref(page, rect): return dict(page=f'P{page}', rect=rect)
def cell(value=None, state='provided'): return dict(state=state, value=value)
def table(headers, rows, unit='', states=None):
    return dict(type='table', headers=headers, rows=[[cell(v, states or 'provided') for v in row] for row in rows], unit=unit)
def scene(objects, meaning, relations=None):
    return dict(type='scene', coordinates='layout_only', viewBox=[0,0,600,300], objects=objects,
                meaning=meaning, relations=relations or [])
def shape(kind, id, **values): return dict(kind=kind, id=id, **values)

elements=[]; definitions=[]; instances=[]; cases=[]
def element(id, owner, role, origin, content, refs):
    elements.append(dict(id=id, owner=owner, role=role, origin=origin, content=content, sourceRefs=refs))
    return id
def define(id, kind, title, definition, **extra):
    definitions.append(dict(id=id, kind=kind, title=title, definition=definition,
                            origin='author_abstraction', domainId='DOM-MATH', **extra))
def ti(id, template, blocks):
    instances.append(dict(id=id, kind='TaskInstance', templateId=template, contentRefs=blocks))
def si(id, task, template, blocks, origin='textbook'):
    instances.append(dict(id=id, kind='SolutionInstance', templateId=template, taskInstanceId=task,
                          contentRefs=blocks, origin=origin))
def case(id,title,pages,scope,checks,task,solution_ids,notes=None):
    cases.append(dict(id=id,title=title,pages=pages,scope=scope,checks=checks,
                      taskId=task,solutionIds=solution_ids,notes=notes or []))

# C01: expressions are tasks; no answer is present in the selected source region.
define('KC-ORDER','KnowledgeComponent','分数混合运算顺序','分数混合运算遵循括号及同级运算顺序。')
define('ST-ORDER','SolutionTemplate','按运算顺序化简','保持运算树，除以非零数改为乘其倒数，再计算。',kcIds=['KC-ORDER'],subsolutionIds=[])
define('TT-EXPR','TaskTemplate','计算含括号的分数混合运算','给定合法有理数表达式，按规定顺序计算结果；除数不能为零。',solutionIds=['ST-ORDER'])
exprs=[op('divide',op('divide',n(12),f(4,5)),f(3,8)),op('multiply',op('divide',f(3,8),f(1,10)),f(5,7)),op('multiply',f(4,7),op('group',op('divide',f(5,8),f(5,14))))]
blocks=[para('请你试着算一算。')]+[formula(e,l) for e,l in zip(exprs,[r'12\div\frac45\div\frac38',r'\frac38\div\frac1{10}\times\frac57',r'\frac47\times(\frac58\div\frac5{14})'])]
element('E-EXPR','TI-EXPR','question','textbook',blocks,[ref(50,[.08,.44,.72,.09])]);ti('TI-EXPR','TT-EXPR',['E-EXPR'])
element('E-ORDER','KC-ORDER','knowledge','textbook',[para('分数混合运算的顺序与整数混合运算的顺序一样。')],[ref(50,[.39,.53,.38,.08])])
case('C01','公式：除号、分数与括号',[50],'“试一试”第一组的三道计算题及运算顺序说明。',['三个表达式的运算顺序不变','保留分数结构，不把连续除法合并成错误的分母','原题没有答案，题面不补答案'],'TI-EXPR',[],['本轮未生成参考解法；数值检查只用于作者核对，不属于教材原文。'])

# C02: one task, two source solutions; methods are separately abstracted.
define('KC-FRACTION','KnowledgeComponent','一个量的几分之几','确定作为整体的量，再按比例求其部分；多层关系需要辨明每层整体。')
define('KC-ASSOC','KnowledgeComponent','乘法结合律','连乘可以改变结合次序而不改变乘积。')
define('ST-TWO','SolutionTemplate','逐层求部分量','先求中间量，再求最终量。',kcIds=['KC-FRACTION'],subsolutionIds=[])
define('ST-COMBINE','SolutionTemplate','合并两层比例','先相乘得到相对原量的比例，再乘原量。',kcIds=['KC-FRACTION','KC-ASSOC'],subsolutionIds=[])
define('TT-CHAIN','TaskTemplate','已知两层比例求最终量','给定原量及连续两层比例，求最后一层数量；人数任务须满足整数条件。',solutionIds=['ST-TWO','ST-COMBINE'])
element('E-GIVEN','TI-CHAIN','question','textbook',[para('气象小组有12人。摄影小组人数是气象小组的1/3，航模小组人数是摄影小组的3/4。航模小组有多少人？说明思路。')],[ref(49,[.12,.22,.80,.32])]);ti('TI-CHAIN','TT-CHAIN',['E-GIVEN'])
for suffix,method,parts in [('A','ST-TWO',[para('先求摄影小组人数，再求航模小组人数。'),formula(op('multiply',op('multiply',n(12),f(1,3)),f(3,4)),r'12\times\frac13\times\frac34'),formula(op('equal',op('multiply',n(4),f(3,4)),n(3)),r'4\times\frac34=3')]),('B','ST-COMBINE',[para('先求航模小组人数占气象小组的几分之几。'),formula(op('multiply',n(12),op('group',op('multiply',f(1,3),f(3,4)))),r'12\times(\frac13\times\frac34)'),formula(op('equal',op('multiply',n(12),f(1,4)),n(3)),r'12\times\frac14=3')])]:
    element('E-SOL-'+suffix,'SI-CHAIN-'+suffix,'solution','textbook',parts,[ref(50,[.07,.09,.85,.18])]);si('SI-CHAIN-'+suffix,'TI-CHAIN',method,['E-SOL-'+suffix])
element('E-BLANK','TI-CHAIN','question','textbook',[table(['答句'],[[None]],states='response_blank')],[ref(50,[.10,.31,.36,.045])]);next(i for i in instances if i['id']=='TI-CHAIN')['contentRefs'].append('E-BLANK')
case('C02','跨页例题：同一道题，两种解法',[49,50],'第49页条件与首问、第50页两列解法和答句空白。',['三个已知条件来自原题，不按插画人物计数','两列解法分别关联同一道题','题面不显示4人、3人或解法','保留完整答句待填写的性质'],'TI-CHAIN',['SI-CHAIN-A','SI-CHAIN-B'],['求解运算与方法顺序保留；红色约分笔迹尚未逐笔建模，是本轮已知表达缺口。','未覆盖第49页下方圆点图和线段图；本例不代表整页转换通过。'])

# C03: erroneous work remains erroneous in the task, never silently corrected.
define('KC-RECIP','KnowledgeComponent','除以非零数等于乘其倒数','除数必须非零；改乘法时需要取倒数。')
define('ST-ERROR','SolutionTemplate','逐步核查运算变换','逐步比对表达式，定位首个不等价的变换并解释。',kcIds=['KC-RECIP'],subsolutionIds=[])
define('TT-ERROR','TaskTemplate','辨析分数除法的错误演算','给出他人演算，判断是否等价并说明理由。',solutionIds=['ST-ERROR'])
wrong=[op('divide',op('multiply',f(7,8),f(3,4)),f(1,3)),op('multiply',op('multiply',f(7,8),f(3,4)),f(1,3)),f(7,32)]
element('E-WRONG','TI-ERROR','question','textbook',[para('下面这道题算得对吗？说明理由。'),dict(type='worked_example',expressions=wrong,assertedCorrect=False)],[ref(50,[.195,.70,.18,.11])]);ti('TI-ERROR','TT-ERROR',['E-WRONG'])
element('E-RECIP','KC-RECIP','knowledge','textbook',[para('除以一个不为零的数，等于乘这个数的倒数。')],[ref(50,[.14,.81,.36,.09])])
case('C03','错例：错误内容也是原题的一部分',[50],'底部绿色板书中的第一列；约分笔迹暂不逐笔复刻。',['保留7/32这个错误结果','三行属于被评价的演算，不是标准解答','提取时不改写原题'],'TI-ERROR',[],['本例识别首项为7/8；后续真实LLM必须从原图读取，不能看到本参考值。'])

# C04: source data and blanks are different content states.
define('KC-DATA','KnowledgeComponent','数据的类别与单位','读数须结合列标题、统计范围、单位与来源；重叠类别不可直接相加。')
define('ST-TABLE','SolutionTemplate','按标题和单位读表','对应行列查找数据，保留单位并区分类别范围。',kcIds=['KC-DATA'],subsolutionIds=[])
define('TT-TABLE','TaskTemplate','整理并解读人口统计资料','区分调查方案、观测数据和结论，按年龄及普查批次整理。',solutionIds=['ST-TABLE'])
counts=[['第五次',129977870,88274022],['第六次',177648705,118831709],['第七次',264018766,190635280]]
element('E-PLAN','TI-DATA','question','textbook',[para('讨论研究方案并填写表格。'),table(['收集什么样的数据','数据从哪里获取','怎样分析数据得出结论'],[[None,None,None]],states='response_blank')],[ref(91,[.13,.52,.80,.14])])
element('E-COUNTS','TI-DATA','question','textbook',[para('教材提供的三次人口普查老龄人数资料：'),table(['普查批次','60岁及以上人数','65岁及以上人数'],counts,'人')],[ref(91,[.17,.78,.28,.11])]);ti('TI-DATA','TT-TABLE',['E-PLAN','E-COUNTS'])
case('C04','表格：数据与待填写内容',[91],'研究方案空表及左下老龄人数表；不含右下年龄占比整表。',['三格为空是作答要求，不是OCR失败','65岁及以上不能变成以下','人数用整数保存，单位为人'],'TI-DATA',[],['实际题组还有开放探究要求；本例只验表格及所选内容，不据此认定整个调查任务已完整建模。'])

# C05: plot encodings, overlapping cohorts, and original rounded values.
define('KC-CHART','KnowledgeComponent','统计图的表达','条形图比较数量，折线图呈现变化，扇形图表达互斥部分在整体中的占比。')
define('ST-READ-CHART','SolutionTemplate','结合图例与坐标读图','先确定系列、范围及单位，再读数和比较，不将包含关系当作互斥部分。',kcIds=['KC-CHART','KC-DATA'],subsolutionIds=[])
define('TT-CHART','TaskTemplate','解读同一资料的不同统计图','根据图形及图例说明数量、变化或构成；解释不能超出数据范围。',solutionIds=['ST-READ-CHART'])
chart_common=dict(categories=['第五次','第六次','第七次'],unit='亿人',precision=2,axis=dict(min=0,max=3,step=.5),labels=True,
                  series=[dict(name='60岁及以上',values=[1.30,1.78,2.64],color='#4f81bd'),dict(name='65岁及以上',values=[.88,1.19,1.91],color='#e28036')],
                  cohortRelation='second_subset_of_first',stacked=False,derivedFrom='E-COUNTS',conversion='人数 / 100000000；四舍五入至两位小数')
charts=[dict(type='chart',chartType=kind,title='第五～七次人口普查中老年人口数量'+('统计图' if kind=='bar' else '变化情况'),**chart_common) for kind in ['bar','line']]
charts.append(dict(type='chart',chartType='pie',title='第七次人口普查年龄分布图',categories=['0～14岁','15～59岁','60～64岁','65岁及以上'],unit='%',precision=2,labels=True,
                   series=[dict(name='第七次人口普查',values=[17.95,63.35,5.20,13.50],color='#4f81bd')],
                   colors=['#4f81bd','#e28036','#a5a5a5','#ffc000'],cohortRelation='disjoint_parts',stacked=False))
element('E-CHARTS','TI-CHARTS','question','textbook',[para('从这些统计图中能获得哪些信息？'),*charts],[ref(93,[.13,.23,.80,.57])]);ti('TI-CHARTS','TT-CHART',['E-CHARTS'])
element('E-CHART-TIPS','SI-CHARTS','solution','textbook',[para('条形图便于比较数量；折线图便于观察变化；扇形图便于观察年龄构成。')],[ref(93,[.07,.82,.84,.09])]);si('SI-CHARTS','TI-CHARTS','ST-READ-CHART',['E-CHART-TIPS'])
case('C05','统计图：并列柱、折线与扇形',[93,91],'第93页三个图形及下方提示，引用第91页原始人数。',['柱图不能堆叠','60+包含65+，两组人数不能相加','图上保留两位小数及亿人单位','扇形四组互斥且合计100%','教学提示不进入原题'],'TI-CHARTS',['SI-CHARTS'])

# C06: geometry values are layout choices, not givens in the exercise.
define('KC-CIRCLE','KnowledgeComponent','圆与其他平面图形的区别','圆周到圆心距离相等；此知识定义是作者据教材活动抽象，不能冒充逐字提取。')
define('ST-SHAPE','SolutionTemplate','比较形状与中心距离','观察或操作图形，检验中心到边界的距离是否一致。',kcIds=['KC-CIRCLE'],subsolutionIds=[])
define('TT-SHAPE','TaskTemplate','比较圆与其他图形','比较指定圆、椭圆及多边形，提出区分依据；未给长度不得编造测量值。',solutionIds=['ST-SHAPE'])
shapes=[shape('circle','circle',cx=55,cy=120,r=35),shape('ellipse','ellipse',cx=150,cy=120,rx=40,ry=28),shape('polygon','triangle',points=[[250,80],[210,155],[290,155]]),shape('polygon','square',points=[[320,85],[390,85],[390,155],[320,155]]),shape('polygon','pentagon',points=[[450,80],[488,108],[474,155],[426,155],[412,108]]),shape('polygon','hexagon',points=[[535,85],[570,85],[590,120],[570,155],[535,155],[515,120]])]
for x in [55,150,250,355,450,552]: shapes.append(shape('point',f'center{x}',x=x,y=120,label=''))
element('E-SHAPES','TI-SHAPES','question','textbook',[para('观察圆、椭圆、三角形、正方形、五边形和六边形，说明圆与其他图形的不同。'),scene(shapes,'六种图形及各自内部的标记点。绘制尺寸只用于布局，不是题目给定长度。')],[ref(11,[.13,.61,.72,.09])]);ti('TI-SHAPES','TT-SHAPE',['E-SHAPES'])
case('C06','几何：对象结构与绘图布局分开',[11],'六种图形与中央标记点；按语义重述观察要求。',['六种图形均可从结构重绘','布局数值不能成为题目已知长度','不把图形的样子当成新增数学条件'],'TI-SHAPES',[],['原活动还要求使用附页剪图操作；本例只验证图形表达，不声称已经替代完整动手活动。'])

# C07: bearing has a reference axis, direction and angle, not an absolute screen angle.
define('KC-POS','KnowledgeComponent','方向与距离确定位置','给定参照点后，方向角与距离共同限定平面中的位置。')
define('ST-POS','SolutionTemplate','比较位置描述的约束范围','分别考察仅方向、仅距离、方向和距离齐全时的可能位置。',kcIds=['KC-POS'],subsolutionIds=[])
define('TT-POS','TaskTemplate','判断位置描述是否充分','判断相对同一参照点的描述能否唯一定位，说明缺少的信息。',solutionIds=['ST-POS'])
element('E-POS','TI-POS','question','textbook',[para('哪条信息能准确确定象群的位置？想一想，画一画。'),para('①象群在指挥部的东北方向。'),para('②象群距离指挥部6000米。'),para('③象群在指挥部的北边再往东30°方向上，距离6000米。')],[ref(67,[.13,.52,.79,.13])]);ti('TI-POS','TT-POS',['E-POS'])
element('E-BEARING','SI-POS','solution','textbook',[para('第三条同时提供了方向角和距离。下图表达第三条信息。'),dict(type='bearing',reference='指挥部',target='象群',referenceAxis='north',turn='east',angleDegrees=30,distance=6000,unit='米',screenDistance=150)],[ref(67,[.56,.71,.31,.17])]);si('SI-POS','TI-POS','ST-POS',['E-BEARING'])
case('C07','方向：北偏东与距离',[67],'三张描述卡片，以及第三种描述的教学示意图。',['30°以北为起始方向向东转','6000米是实际距离；150是绘图长度','题面不提前出现第三条正确的反馈'],'TI-POS',['SI-POS'],['原页另外两幅不充分定位示意图未包含，本轮不声称整页重建。'])

# C08: source supplies top/front views; side view is not silently filled in.
define('KC-VIEW','KnowledgeComponent','观察方向与物体视图','物体与观察方向共同决定看到的轮廓；这里限定直立圆柱和圆锥。')
define('ST-VIEW','SolutionTemplate','固定物体姿态比较视图','分别从上方、正面和侧面观察，区分三维物体与二维轮廓。',kcIds=['KC-VIEW'],subsolutionIds=[])
define('TT-VIEW','TaskTemplate','观察直立圆柱与圆锥','描述从不同方向看到的形状；不从一幅轮廓反推出唯一三维物体。',solutionIds=['ST-VIEW'])
element('E-SOLIDS','TI-VIEW','question','textbook',[para('从上面、正面和侧面观察直立的圆柱和圆锥，看到的分别是什么形状？'),dict(type='solids',items=[dict(id='cylinder',shape='cylinder',orientation='upright'),dict(id='cone',shape='cone',orientation='upright')],dimensionsRole='layout_only')],[ref(86,[.10,.20,.77,.20])]);ti('TI-VIEW','TT-VIEW',['E-SOLIDS'])
element('E-VIEWS','SI-VIEW','solution','textbook',[dict(type='views',items=[dict(solid='cylinder',direction='top',outline='circle',centerDot=False),dict(solid='cone',direction='top',outline='circle',centerDot=True),dict(solid='cylinder',direction='front',outline='rectangle',centerDot=False),dict(solid='cone',direction='front',outline='triangle',centerDot=False)]),para('所选教材答案框只画了上面和正面；这里不把侧面答案当成已提取内容。')],[ref(86,[.285,.405,.36,.14])]);si('SI-VIEW','TI-VIEW','ST-VIEW',['E-VIEWS'])
case('C08','立体：物体、视图与未提供的答案',[86],'顶部圆柱圆锥及观察问题、中间四幅已画出的视图。',['物体姿态为直立，尺寸只是绘图参数','圆锥上视图保留中心点','仅提取上面和正面四个视图，不编造侧面来源'],'TI-VIEW',['SI-VIEW'],['不含下半页手电照射实验；本轮不是完整光照模拟。'])

pack=dict(schemaVersion='0.1',id='M1-CONTENT-REFERENCE-20261105',status='author_reference_not_llm_output',
          sourceUrl='https://www.100875.com.cn/show/eBookAndTeacher.html?resId=7965194976af40f5b9abc4b3f89522fe&bookId=120170718181616016000&firstNum=120170718181616016000&contributeId=9276',
          sources=sources,definitions=definitions,instances=instances,elements=elements,cases=cases)
ROOT.joinpath('reference.json').write_text(json.dumps(pack,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(f'Reference: {len(cases)} cases, {len(elements)} content elements, {len(definitions)} candidate definitions; no LLM calls.')
