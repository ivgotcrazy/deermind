import { blankMethod, blankStep, blankTask, type DomainData, type Method, type Step, type Route, type Parameter } from './domain';

const step=(key:string,title:string,inputs:string,output:string,detail:string,extra:Partial<Step>={}):Step=>({...blankStep(),key,title,inputs,output,detail,...extra});
const route=(condition:string,action:string,result:string,next='$next'):Route=>({condition,action,result,next});
const stopMath='已知条件不足、子任务未解决或检查发现矛盾且无法修正时，保留已得到的结果并说明缺口，以未解决结束；不能把不完整推导报告为成功。';

// Explicit mock definitions for reviewing authoring; this does not execute methods.
export function addMethodFlows(data:DomainData,key:'junior'|'senior'|'k8s'){
  const parent=data.tasks[0],a=data.methods.find(m=>m.id===parent.methods[0])!,b=data.methods.find(m=>m.id===parent.methods[1])!;
  if(key==='junior')junior(data,a,b);
  if(key==='senior')senior(a,b);
  if(key==='k8s')k8s(a,b);
}

function junior(data:DomainData,a:Method,b:Method){
  const [fn,geo,max,right]=a.kc,domainId=a.domainId;
  const param=(symbol:string,name:string,kind:string,condition:string,role:Parameter['role']='题目已给定'):Parameter=>({symbol,name,kind,condition,role});
  function part(name:string,parameters:Parameter[],criterion:string,methodName:string,description:string,steps:Step[],kc:string[]){
    const t={...blankTask(domainId),version:1,name,summary:description,goal:parameters.filter(p=>p.role!=='题目已给定').map(p=>p.name).join('；'),responsibility:description,
      requirements:[{deliverable:parameters.filter(p=>p.role!=='题目已给定').map(p=>p.symbol+'：'+p.name).join('；'),criterion}],parameters,relations:description,variations:[],exclusions:'仅在各输入约束内使用；条件不足时不补造结论。'};
    const m={...blankMethod(domainId),version:1,name:methodName,description,conditions:parameters.filter(p=>p.role==='题目已给定').map(p=>p.condition).join('；'),
      inputs:parameters.filter(p=>p.role==='题目已给定').map(p=>p.symbol+'：'+p.name).join('；'),output:t.requirements[0].deliverable,steps,kc,ending:{success:criterion,stop:stopMath}};
    t.methods=[m.id];data.tasks.push(t);data.methods.push(m);return {task:t,method:m};
  }
  const maximum=part('求凹二次函数在开区间内的最大值',[
    param('S','凹二次函数','函数／表达式','二次项系数小于0'),param('I','非空有限开区间','区间／集合','I=(u,v)，u<v'),param('M','最值与取等位置，或不取最大值的说明','文本','区分最大值与上确界','需要研究或求解'),
  ],'配方和区间检查一致；有最大值时给出取等点，无最大值时说明不可取的边界。','配方并核对顶点位置','配方得到顶点，再结合开区间判断最大值能否取得。',[
    step('vertex','配方求顶点','S(t) 与 I=(u,v)','顶点横坐标 t₀、顶点值 S(t₀)','将 S 写为 A(t−t₀)²+S(t₀)，A<0。'),
    step('inside','检查顶点是否在区间内','t₀、S(t₀)、I','M：最大值及位置，或无最大值的说明','依据给定区间选择一种情况。',{kind:'choice',routes:[
      route('u<t₀<v','取 t=t₀ 并代回','M={有最大值，S(t₀)，t₀}','$success'),
      route('t₀≤u 或 t₀≥v','利用区间内单调性说明边界不可取','M={无最大值，边界原因}','$success'),
    ],coverage:'两种情况覆盖实数顶点位置，等于端点归入第二种。S 或 I 不明确时停止，不猜测。'}),
  ],[max]);
  const prepare=part('由给定点确定抛物线及动点范围',[
    param('points','A、B、C、D 的坐标','点／图形','A=(0,0)，B=(L,0)，C=(0,h)，D=(d,e)，0<d<L，e>0；P 区域非空'),param('f,I','函数及动点区间','文本','f 经过 A、B、D；I 同时满足所有位置限制','需要研究或求解'),
  ],'函数代入三个给定点成立，I 来自全部位置条件且非空。','待定系数与位置不等式','由三个点确定 f，并联立 P 在 BC 上方及 0<t<L 的条件。',[
    step('function','求函数','A、B、D','f(x)=kx(L−x)，k=e/[d(L−d)]','代入各给定点核对函数。'),
    step('range','求可行区间','f；B、C；0<t<L','I=(h/(kL),L)','联立 f(t)>h−ht/L。输入条件应保证 h<kL²；否则停止并说明区域为空。'),
  ],[fn]);
  const areaParams=[param('f','已确定的抛物线','函数／表达式','f(t)=kt(L−t)，k>0'),param('I','动点允许区间','区间／集合','I=(h/(kL),L) 非空'),param('L,h','两轴定点坐标','文本','L>0，h>0'),param('areaResult','最大面积与点坐标','文本','包含取等点位置检查','需要研究或求解')];
  function area(auxiliary:boolean){return part('研究动点三角形的面积最值'+(auxiliary?'（辅助线）':''),areaParams,
    '面积函数符合几何关系；最大值能够取得，P 坐标满足原条件。',auxiliary?'竖直分割后调用最值方法':'面积加减后调用最值方法',
    auxiliary?'过 P 作竖直线交 BC 于 H，将两个三角形面积相加。':'将 BCP 面积表示为 ABP 与 ACP 面积之和减去 ABC 面积。',[
      step('area','建立面积函数','f、I、L、h','S(t)：BCP 面积函数',auxiliary?'PH=f(t)−(h−ht/L)，S=L×PH/2。':'S=L×f(t)/2+h×t/2−Lh/2。'),
      step('maximum','求限定区间内最值','将 S(t) 传为子方法的 S；将 I 传为子方法的 I','返回 M；有最大值时用其中 t₀ 求 P=(t₀,f(t₀))','调用凹二次函数最值子任务。',{divided:true,taskId:maximum.task.id,solutionId:maximum.method.id}),
      step('area-check','检查取等位置','M、f、I 与原位置条件','areaResult 或无法完成的原因','不能把边界上的上确界当作最大值。',{kind:'check',routes:[
        route('M 有最大值，且取等点满足原位置条件','代入面积和坐标核对','最大面积、P 坐标及依据','$success'),
        route('M 无最大值，或原条件核对失败','记录原因，停止此面积方法','未解决：本任务要求的最大面积尚不能交付','$stop'),
      ],coverage:'信息不足时停止并保留已有 S 和 M；不填造一个取等点。'}),
    ],[geo]);}
  const areaA=area(false),areaB=area(true);
  // The two area solutions address the same subtask, not two different abilities.
  data.tasks.splice(data.tasks.indexOf(areaB.task),1);
  areaA.task.methods.push(areaB.method.id);areaB.task=areaA.task;
  areaA.task.summary='研究指定动点范围内的三角形面积与取等位置。';
  areaA.task.responsibility='建立面积关系，在允许范围内求最大值并核对取等位置。';
  areaA.task.relations='A=(0,0)，B=(L,0)，C=(0,h)；P=(t,f(t))，t∈I，P 位于 BC 上方。研究 BCP 的面积。';
  const angles=part('寻找使三角形为直角三角形的动点',[
    param('f,I','抛物线与允许区间','文本','P=(t,f(t))，t∈I；A=(0,0)，B=(L,0)，P 在 x 轴上方'),param('L','底边长度','数值','L>0'),param('R','全部合格动点','区间／集合','可为空集，但需说明穷尽依据','需要研究或求解'),
  ],'覆盖可能的直角位置；每个候选点均检查原条件，给出全部合格点或空集理由。','勾股关系与逐点筛选','先排除 A、B 为直角，再在 P 处建立勾股关系；对所有候选点逐个核对。',[
    step('candidates','求候选点','f、I、L','候选横坐标集合 C','0<t<L 且 f(t)>0，A、B 处角均为锐角；P 处直角满足 f(t)²=t(L−t)。求所有实数候选值。'),
    step('filter','逐个筛选候选点','候选集合 C、f、I','R：保留的点；排除记录','对 C 中每一个值使用下表，不是只选择一个候选点。',{kind:'cases',routes:[
      route('候选 t∈I，代回直角条件成立且三角形非退化','保留 P=(t,f(t))','加入 R'),
      route('候选不满足上述任一条件','记录不满足的条件并排除','加入排除记录'),
    ],coverage:'每个候选都要归入一类；遍历完 C 后汇总 R，C 为空或 R 为空也须说明求解穷尽依据。',next:'$success'}),
  ],[right]);
  for(const [m,areaPart] of [[a,areaA],[b,areaB]] as const){
    m.kc=[];m.steps=[
      step('prepare','确定函数与动点范围','将题目 A、B、C、D 传入子方法 points','返回 f、I，供步骤2和步骤3共同使用','先确定后续两个研究任务共同使用的条件。',{divided:true,taskId:prepare.task.id,solutionId:prepare.method.id}),
      step('area','研究最大面积','步骤1的 f、I；B 的 L、C 的 h','返回 areaResult：最大面积、取等点与依据','面积子方法中还会继续调用最值子方法。',{divided:true,taskId:areaPart.task.id,solutionId:areaPart.method.id}),
      step('angles','研究直角位置','步骤1的 f、I；B 的 L','返回 R：合格点及逐点排除依据','不使用最大面积时的 P 代替本步骤的全部候选点。',{divided:true,taskId:angles.task.id,solutionId:angles.method.id}),
      step('combine','汇总并核对三项要求','f、I、areaResult、R','完整解答或尚未解决的部分','检查三项任务要求都得到回答；任一子方法停止时保留其原因，不报告整体完成。',{kind:'check',routes:[
        route('三项结果齐全，代入与范围检查均通过','整理推导、取等位置和候选筛选依据','任务完整解答','$success'),
        route('有子任务未解决，或结果检查不一致','保留已完成部分，列明缺口','未解决的原因','$stop'),
      ],coverage:'没有返回值的子任务视为未解决，不能跳过。'}),
    ];m.ending={success:'函数、面积最值及全部直角点三项要求均完成，所有结果满足原题位置与非退化条件。',stop:stopMath};
  }
}

function senior(a:Method,b:Method){
  const monotonic=()=>step('monotonic','讨论所有参数下的单调性','f_a(x)=x³−3ax+b；b>0；a∈R','按 a 分类的单调区间','由 f′=3(x²−a) 分类，不把研究参数 a 当成一个给定数。',{kind:'cases',routes:[
    route('a≤0','证明 f 在 R 严格递增；a=0 只有孤立导数零点','R 上严格递增，无局部极值'),
    route('a>0','用 −√a、√a 分段研究导数符号','两侧递增，中间递减；有两个极值点'),
  ],coverage:'两类不重叠并覆盖所有实数 a；合并完整单调性结论。'});
  a.steps=[monotonic(),
    step('roots','讨论不同实根个数','步骤1的单调性；b>0','α=(b/2)^(2/3)；根数分类表','仅在 a>0 时计算两个极值 b±2a^(3/2)。a≤0 直接使用严格单调性。',{kind:'cases',routes:[
      route('a<α','a≤0 时由单调性判断；0<a<α 时检查两个极值为正','1 个不同实根'),
      route('a=α','极小值为0，重根只按一个不同根计数','2 个不同实根'),
      route('a>α','极大值正、极小值负，三个单调区间各有一个根','3 个不同实根'),
    ],coverage:'α>0；小于、等于、大于三类覆盖 R，不能遗漏临界值。汇总后保留 a>α 作为下一步的必要条件。'}),
    step('location','限制三个根的位置','a>α；b、L；步骤1的单调区间','允许的 a 集合及端点证明','核对极值点位置、f(−L)≤0、f(L)≥0，并证明必要充分性。b<L³/4 时得到 α<a≤(L³−b)/(3L)，否则集合为空。本实例 b=2、L=3，得到 1<a≤25/9。'),
    proofCheck(),
  ];
  b.steps=[monotonic(),
    step('separate','分离参数并研究两侧函数','零点方程；b>0','g(x)=x²/3+b/(3x)，x≠0；正半轴最低值 α','x=0 不可能为根，分离参数合法。分别研究两个半轴。',{kind:'cases',routes:[
      route('x<0','求 g′=(2x³−b)/(3x²)，证明严格递减且值域为 R','每个 a 恒有一个负根'),
      route('x>0','求出 x₀=(b/2)^(1/3)，先减后增','g(x₀)=α=(b/2)^(2/3)'),
    ],coverage:'x=0 已排除；两半轴均需研究并合并结论。'}),
    step('roots','计数所有参数的交点','步骤2两侧图像性质；水平线 y=a','不同实根的完整分类','交点个数对应不同实根，不按重数重复计数。',{kind:'cases',routes:[
      route('a<α','负半轴1交点，正半轴0交点','共1个不同实根'),route('a=α','负半轴1交点，正半轴1交点','共2个不同实根'),route('a>α','负半轴1交点，正半轴2交点','共3个不同实根'),
    ],coverage:'三类覆盖所有 a，全部处理后汇总。'}),
    step('location','限制交点的位置','a>α；g 的单调区间；L','根的位置限制与参数集合','分别限制负根、较大正根和较小正根。须先核对 L 相对 x₀ 的位置，再比较 g(−L)、g(L)。本例 x₀=1<L=3，得到 a≤25/9 与 a≤29/9，结合 a>1 取交集。'),
    proofCheck(),
  ];
  for(const m of [a,b])m.ending={success:'全部 a 的单调性与根数已分类；第三项参数集合已证明必要充分性，并说明重根和区间端点。',stop:stopMath};
}
function proofCheck(){return step('proof-check','核对分类与边界','前面各步骤的分类、参数集合和证明','最终三项结论及核对记录','尤其核对 a=α、重根计数、区间端点；代入几个数值不能代替证明。',{kind:'check',routes:[
  route('分类覆盖完整、端点取舍及必要充分性均已说明','整理完整结论','任务解答','$success'),
  route('分类或证明仍有缺口','明确缺少哪种情况或证明','未解决部分及原因','$stop'),
],coverage:'无法确定证明是否成立时保留疑点，以未解决结束。'});}

function k8s(a:Method,b:Method){
  a.steps=[
    step('observe','读取现象与配置','namespace、service、workload、client；允许的读取与检查范围','最新配置、预期 Pod 标签、就绪后端、原地址响应','确认原访问地址与命名空间。记录观察时间；不预设只有一处故障。'),
    step('selector','判断后端选择关系','最新 selector、Pod 标签与 EndpointSlice','选择关系判断及证据','只有证实不匹配才修改；没有端点本身还不足以证明选择器错误。',{kind:'choice',routes:[
      route('selector 与预期 Pod 标签不匹配，已取得对应证据','确定最小修改内容','已证实的 selector 差异','fix-selector'),
      route('selector 匹配且预期后端已出现','保留检查结果','选择关系正常','port'),
      route('标签或后端状态不足以判定，或出现范围外问题','记录缺少的观察或范围外现象','未解决原因','$stop'),
    ],coverage:'以最新观察判断；信息矛盾归入第三类，不猜测修复。'}),
    step('fix-selector','修正选择器','已证实的 selector 差异；允许修改的 Service','修改记录，等待复查','只改 selector，保留原资源与访问地址；修改后立即复查原路径。',{next:'verify'}),
    step('port','判断转发端口','最新 targetPort、应用实际监听及协议','端口判断及证据','实际监听由检查取得，不能只依据 containerPort 声明。',{kind:'choice',routes:[
      route('转发端口与实际服务端口不符，证据充分','确定最小修正内容','已证实的端口差异','fix-port'),
      route('转发与实际监听相符','保留端口检查结果','端口关系正常','verify'),
      route('缺少实际监听证据或超出允许范围','说明缺少的信息','未解决原因','$stop'),
    ],coverage:'条件无法判定时停止，不扩大读取和修改范围。'}),
    step('fix-port','修正转发端口','已证实的端口差异','修改记录，等待复查','只改指定 Service 的 targetPort，然后复查原地址。',{next:'verify'}),
    step('verify','复查原访问路径','最新配置、后端、原地址响应；已检查与已修正记录','成功结论，或新的检查依据，或未解决原因','每次修正后重新检查。只在有新依据或尚未核对的必要信息时继续，避免重复做同样的修复。',{kind:'check',routes:[
      route('原地址返回预期响应，三个预期就绪后端齐全，改动在范围内','保存验证记录','任务完成','$success'),
      route('尚未完成，且新观察支持重新核对选择关系','记录新的选择关系疑点','新证据及检查目标','selector'),
      route('尚未完成，选择关系已正常，端口尚未核对或有新的端口证据','记录剩余疑点','端口排查依据','port'),
      route('尚未完成且没有新依据，或信息不足、问题超出范围','保留修复与复查记录并说明原因','未解决，不继续重复修改','$stop'),
    ],coverage:'分支按上表互斥含义使用；无法归类或证据冲突时停止。检查和修复失败也记录为未解决，不视为服务恢复。'}),
  ];
  b.steps=[
    step('backend','核对后端事实','指定应用及允许的检查范围','实际标签、就绪状态、监听端口及检查证据','确认实际后端服务情况，不仅看资源声明；读取与检查失败则保留原因并停止。'),
    step('compare','对照 Service 配置','后端事实；selector、targetPort','已证实的差异集合','根据观察决定是否修改，可一次修正两处已证实的差异。',{kind:'choice',routes:[
      route('至少一处差异已证实，修改在允许范围内','确定 selector 和／或 targetPort 的最小修改','待修改内容','repair'),
      route('没有差异且信息齐全','保留核对结果','没有需要修改的配置','verify'),
      route('信息不全、证据冲突或范围外问题','记录原因','未解决','$stop'),
    ],coverage:'不把暂时没有观察到差异解释为系统已恢复；无差异也必须验证原路径。'}),
    step('repair','修正已证实的差异','最小修改内容','修改记录','可同时修改 selector 和 targetPort；不触碰其他资源。'),
    step('verify','验证结果并决定是否继续','原地址响应、三个后端、改动及历史检查记录','验证结论或未解决记录','验证原客户端路径。',{kind:'check',routes:[
      route('全部完成要求满足','整理证据','成功完成','$success'),
      route('仍失败，但出现新的范围内观察','带着新观察重新核对','下一轮检查输入','backend'),
      route('仍失败且没有新依据，或信息不足、超出范围','记录停止原因','未解决','$stop'),
    ],coverage:'仅有新观察才返回步骤1；信息不明时停止，不无限重试。'}),
  ];
  for(const m of [a,b])m.ending={success:'指定客户端经原地址返回 HTTP 200 和 web-ok，三个预期就绪 Pod 均成为后端；原因有依据，且只改了允许字段。',stop:'证据不足、检查或修复无法完成、超出本方法范围，或重复验证仍失败且无新依据时停止；记录已有发现和未解决原因，不报告恢复。'};
}
