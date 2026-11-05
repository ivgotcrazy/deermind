import { domainData, id, instanceSignature, blankTask, blankMethod, blankKnowledge, blankInstance, type DomainData, type Task } from './domain';
import { addDomainExample } from './domain-example';
import { addMethodFlows } from './method-flow-examples';

export const taskExamples=[
  {key:'primary',name:'小学数学 · 比例增加',description:'原有入门示例：两种解法、子方法与知识汇总。'},
  {key:'junior',name:'初中数学 · 动点综合题',description:'递归分解：综合任务 → 面积研究 → 最值子方法；衔接输入输出。'},
  {key:'senior',name:'高中数学 · 含参数函数',description:'完整分类：研究所有参数情况，汇总根数并检查临界值和端点。'},
  {key:'k8s',name:'K8s · 服务排障',description:'条件选择与复查：修复后再验证，按新证据继续或以未解决停止。'},
] as const;
export type TaskExampleKey=typeof taskExamples[number]['key'];
export function loadTaskExample(key:TaskExampleKey,latest=false){
  const existing=domainData.domains.find(d=>d.exampleKey===key&&(!latest||d.exampleRevision===2));
  if(existing)return existing.id;
  if(key==='primary'){
    const domainId=addDomainExample();domainData.domains.find(d=>d.id===domainId)!.exampleKey=key;return domainId;
  }
  const data=key==='junior'?junior():key==='senior'?senior():k8s();data.domains[0].exampleKey=key;data.domains[0].exampleRevision=2;
  addMethodFlows(data,key);
  if(domainData.domains.some(d=>d.exampleKey===key))data.domains[0].name+=' · 方法流程版';
  domainData.domains.push(...data.domains);domainData.knowledge.push(...data.knowledge);
  domainData.tasks.push(...data.tasks);domainData.methods.push(...data.methods);
  for(const q of data.instances){q.checkedSignature=instanceSignature(q);q.checkedAt=new Date().toLocaleString('zh-CN');domainData.instances.push(q);}
  return data.domains[0].id;
}

// These builders only prepare mock authoring records, not a model or a cluster.
function example(name:string,scope:string){
  const domainId=id('DOM');
  const data:DomainData={domains:[{id:domainId,name,scope,description:'用于检验模板表达的自编 mock；不代表已开放相应课程。',version:1}],tasks:[],methods:[],knowledge:[],instances:[]};
  function knowledge(name:string,description:string,conditions:string,illustration:string){
    const k={...blankKnowledge(domainId),name,description,conditions,example:illustration,version:1};data.knowledge.push(k);return k.id;
  }
  function method(name:string,description:string,conditions:string,inputs:string,output:string,steps:[string,string][],kc:string[]){
    const m={...blankMethod(domainId),name,description,conditions,inputs,output,steps:steps.map(([title,detail])=>({title,detail,divided:false,taskId:'',solutionId:''})),kc,version:1};data.methods.push(m);return m.id;
  }
  function task(fields:Omit<Task,'id'|'domainId'|'version'>){
    const t={...blankTask(domainId),...fields,version:1};data.tasks.push(t);return t;
  }
  function instance(t:Task,question:string,bindings:Record<string,string>,answer:string,solutions:{methodId:string;working:string}[],sourceNote:string){
    data.instances.push({...blankInstance(t),question,bindings,answer,solutions,sourceNote,version:1});
  }
  return {data,knowledge,method,task,instance};
}

function junior(){
  const e=example('初中数学 · 综合示例','二次函数、动点、面积最值与直角条件');
  const functions=e.knowledge('由点的坐标确定二次函数','用点在曲线上的条件确定函数，再代入各点核对。','条件足以唯一确定二次函数，二次项系数非零。','过(0,0)、(4,0)、(1,3)，得到 y=−x²+4x。');
  const geometry=e.knowledge('坐标与三角形面积关系','将同底、同高和面积加减转换为坐标关系。','明确点的位置及非退化条件。','P 在 BC 上方时，S_BCP=S_ABP+S_ACP−S_ABC。');
  const maximum=e.knowledge('二次函数在指定区间的最值','通过配方或对称轴比较允许区间内的函数值。','先确定定义域，核对顶点与端点是否可取。','面积函数顶点必须位于动点的可行区间。');
  const right=e.knowledge('勾股定理及其逆定理','用三边平方关系检验直角条件，排除不符合位置的解。','三角形非退化，需确认可能的斜边。','算出候选点后仍需检查是否位于指定曲线段。');
  const a=e.method('面积加减与二次函数最值','由三个三角形的面积加减建立面积函数。','A 为原点，B、C 分别在两轴正半轴；P 位于 BC 上方且横坐标介于 A、B 之间。','给定点 A、B、C、D。','函数、最大面积与位置、满足直角条件的全部点。',[
    ['确定函数与动点范围','由 A、B、D 确定 f；设 P=(t,f(t))，将位置条件联立确定 t 的范围。'],
    ['求最大面积','S_BCP=S_ABP+S_ACP−S_ABC。代入坐标、配方求最值，并检查取等位置。'],
    ['检验直角条件','根据位置确定可能的直角顶点，用勾股关系求候选点，再筛选范围与非退化条件。'],
  ],[functions,geometry,maximum,right]);
  const b=e.method('竖直辅助线分割面积','过 P 作竖直线交 BC 于 H，通过 PH 与水平跨度计算面积。','H 在线段 BC 上且 P 在 H 上方。','给定点与抛物线条件。','与面积加减法相同的三项交付结果。',[
    ['确定函数与范围','由给定点求 f，确定 P=(t,f(t)) 的可行范围。'],
    ['构造辅助线','H=(t,y_BC(t))，PH=f(t)−y_BC(t)；两个三角形面积之和等于水平跨度乘 PH 的一半。'],
    ['求最值与直角位置','研究面积二次函数；直角问题另用勾股关系求候选点并检查范围。'],
  ],[functions,geometry,maximum,right]);
  const t=e.task({name:'二次函数与动点几何综合',summary:'由给定点确定曲线，研究面积最值与直角位置。',goal:'完成函数确定、面积最值与直角条件三项研究。',responsibility:'建立关系、推导结果、检查定义域并排除越界候选解。',requirements:[
    {deliverable:'抛物线解析式及推导',criterion:'由给定条件唯一确定，代入各给定点成立，二次项系数非零。'},
    {deliverable:'最大面积及对应动点坐标',criterion:'说明动点范围，给出最大值及取等点，验证取等点满足全部位置条件。'},
    {deliverable:'使三角形 ABP 为直角三角形的全部动点',criterion:'覆盖可能的直角位置，筛除越界与退化解；不存在时给出理由。'},
  ],parameters:[
    {symbol:'A',name:'坐标原点',kind:'点／图形',role:'题目已给定',condition:'A=(0,0)。'},
    {symbol:'B',name:'x 轴上的定点',kind:'点／图形',role:'题目已给定',condition:'B=(L,0)，L>0。'},
    {symbol:'C',name:'y 轴上的定点',kind:'点／图形',role:'题目已给定',condition:'C=(0,h)，h>0。'},
    {symbol:'D',name:'抛物线上第三个给定点',kind:'点／图形',role:'题目已给定',condition:'D=(d,e)，0<d<L，e>0。'},
    {symbol:'f',name:'待确定的二次函数',kind:'函数／表达式',role:'需要研究或求解',condition:'曲线经过 A、B、D。'},
    {symbol:'P',name:'动点',kind:'点／图形',role:'需要研究或求解',condition:'P=(t,f(t))，0<t<L，且位于 BC 上方。'},
    {symbol:'t',name:'动点横坐标',kind:'数值',role:'需要研究或求解',condition:'在允许的曲线段内变化，出题时不能固定为一个位置。'},
    {symbol:'S',name:'三角形 BCP 的面积',kind:'数值',role:'需要研究或求解',condition:'由 P 决定，研究整个可行区间上的最值。'},
  ],relations:'A、B、D 在同一条二次函数曲线上，C 位于 y 轴正半轴。P 同时满足曲线条件、0<t<L 及位于 BC 上方。面积最值研究 BCP，直角条件研究 ABP。',variations:[
    {target:'B、C、D 的坐标',range:'保留坐标轴位置及 0<d<L、e>0，改变 L、h、d、e。',constraint:'三点唯一确定二次函数，动点区域非空。若写为 f(x)=kx(L−x)，需 0<h<kL²。'},
    {target:'数值难度',range:'优先使用可手算的整数或有理数坐标。',constraint:'重新检查最大值是否取得、直角点是否存在，不沿用原答案。'},
  ],exclusions:'不包含圆锥曲线、空间几何或多个独立运动点。反例：本实例只把 C 改为(0,20)，动点区域会消失；把“面积最大”改为“周长最小”会改变任务要求。',methods:[a,b]});
  e.instance(t,'抛物线经过 A(0,0)、B(4,0)、D(1,3)，另有 C(0,3)。P 在抛物线上，满足 0<x_P<4 且位于直线 BC 上方。\n1. 求抛物线解析式。\n2. 求三角形 BCP 面积的最大值及此时 P 的坐标。\n3. 判断是否存在符合条件的 P，使三角形 ABP 为直角三角形；若存在，求全部坐标。',
    {A:'(0,0)',B:'(4,0)',C:'(0,3)',D:'(1,3)'},
    'f(x)=−x²+4x；3/4<t<4。最大面积169/32，P=(19/8,247/64)。直角条件的唯一合格点为(2+√3,1)。需给出推导和筛选理由。',[
      {methodId:a,working:'设 f(x)=kx(x−4)，代入 D 得 k=−1。BC: y=3−3x/4；联立 f(t)>3−3t/4 与0<t<4，得3/4<t<4。\nS_BCP=2f(t)+3t/2−6=−2(t−19/8)²+169/32。取等位置在范围内，f(19/8)=247/64。\nA、B 处角均为锐角，检验 P 处直角。令 u=t(4−t)>0，勾股关系给出 u²=u，所以 u=1、t=2±√3。排除越界的2−√3，保留(2+√3,1)。'},
      {methodId:b,working:'函数与范围为 f(x)=−x²+4x、3/4<t<4。过 P 作竖直线交 BC 于 H，PH=f(t)−(3−3t/4)。\nS_BCP=(t+4−t)PH/2=2PH=−2t²+19t/2−6。配方得最大值169/32，P=(19/8,247/64)。\n直角条件另行使用勾股关系，得到两个候选点，排除 t=2−√3，最终保留(2+√3,1)。'},
    ],'人工构造的初中综合题，非教材原题；数值已核算，归类及可用状态为 mock。');
  return e.data;
}

function senior(){
  const e=example('高中数学 · 综合示例','含参数三次函数、不同实根数量与根的位置');
  const derivative=e.knowledge('导数符号与函数单调性','由导数符号确定增减区间，检查临界参数引起的分支变化。','函数在讨论区间可导；导数为零不单独意味着极值。','a≤0 与 a>0 时，x³−3ax+b 的单调结构不同。');
  const roots=e.knowledge('连续函数零点与单调区间','结合连续性、端点和极值的符号及单调性判断零点数量。','分别证明存在与唯一；重根只按一个不同实根计数。','极小值为零时可能只有两个不同实根。');
  const boundary=e.knowledge('参数分类与根的位置约束','将临界参数、根所在区间及必要充分性共同纳入参数范围。','关注端点取舍，不能只检验数值样本。','有三个实根不代表三个根都在指定区间。');
  const a=e.method('导数、极值与端点符号','按单调结构分类，再用极值和端点判断根。','f_a(x)=x³−3ax+b，b>0，目标区间[−L,L]，L>0。','固定 b、L，研究所有实数 a。','单调区间、不同实根分类、全部满足位置条件的 a。',[
    ['讨论单调性','f′=3(x²−a)。a≤0 时严格递增；a>0 时用 ±√a 分隔增减区间。'],
    ['计数不同实根','计算极值 b±2a^(3/2)，处理与零相等的临界情形，给出完整分类。'],
    ['限制根的位置','在三个不同实根前提下，核对端点符号、极值点位置及端点取等，证明必要性和充分性。'],
  ],[derivative,roots,boundary]);
  const b=e.method('分离参数与水平线交点','利用原函数导数完成单调性，再将零点方程改写为水平线与 g(x) 的交点。','b>0 保证 x=0 不是根；分离参数后保留 x≠0。','固定 b、L，研究 a 与 g(x)=(x³+b)/(3x) 的交点。','与极值法相同的三项交付结果。',[
    ['原函数单调性','由 f′=3(x²−a) 按 a≤0、a>0 分类。'],
    ['分离参数','零点满足 a=g(x)=(x³+b)/(3x)。研究 g 在负半轴和正半轴的单调性及极值。'],
    ['计数与区间限制','将交点数转为不同实根数；再对交点位置、端点逐一检查。'],
  ],[derivative,roots,boundary]);
  const t=e.task({name:'含参数三次函数的零点与位置研究',summary:'讨论完整参数范围，区分重根与不同实根。',goal:'确定单调性、根的数量及全部根位于指定区间时的参数条件。',responsibility:'完整分类，说明临界值及端点，证明必要性与充分性。',requirements:[
    {deliverable:'随参数变化的单调区间',criterion:'覆盖所有实数 a，处理临界值，区间表达完整。'},
    {deliverable:'不同实根个数的分类',criterion:'给出完整参数分段；重根只计一次。'},
    {deliverable:'三个不同实根均在指定区间内的 a 的范围',criterion:'同时检查根的数量和位置；说明端点取舍并证明必要充分性，无解时给出空集及理由。'},
  ],parameters:[
    {symbol:'b',name:'常数项',kind:'数值',role:'题目已给定',condition:'b>0，在每道实例中固定。'},
    {symbol:'L',name:'目标区间半长',kind:'数值',role:'题目已给定',condition:'L>0，在每道实例中固定，区间为[−L,L]。'},
    {symbol:'f',name:'含参数函数族',kind:'函数／表达式',role:'题目已给定',condition:'固定结构 f_a(x)=x³−3ax+b，不是任意三次多项式。'},
    {symbol:'a',name:'待讨论参数',kind:'数值',role:'需要研究或求解',condition:'遍历实数，不得在出题时固定为某个具体数。'},
    {symbol:'x',name:'函数自变量',kind:'数值',role:'需要研究或求解',condition:'x∈R，研究所有可能零点。'},
    {symbol:'Z',name:'不同实根集合',kind:'区间／集合',role:'需要研究或求解',condition:'Z={x∈R:f_a(x)=0}；第三项要求|Z|=3且Z⊆[−L,L]。'},
  ],relations:'f_a(x)=x³−3ax+b，a∈R，b、L 在实例中固定。不同实根不按重数重复计数。第三项要求恰有三个不同实根且全部位于[−L,L]。',variations:[
    {target:'常数项 b 与区间半长 L',range:'正数，优先使用适合手算的值。',constraint:'重新计算临界参数和端点条件。若要求第三项解集非空，需 b<L³/4；否则允许空集作为结果。'},
    {target:'给定信息的表示',range:'函数式与文字说明，或等价符号说明。',constraint:'保留 a 的全范围讨论责任，不能以 a=2 的固定函数替代。'},
  ],exclusions:'不包含任意高次函数或复根计数。反例：只研究 a=2 已丢失参数分类责任；按重数计根会改变临界答案。',methods:[a,b]});
  e.instance(t,'设 f_a(x)=x³−3ax+2，a∈R。\n1. 讨论函数单调性。\n2. 讨论方程 f_a(x)=0 的不同实根个数。\n3. 求使方程具有三个不同实根，且三个根均位于[−3,3]内的 a 的范围。',
    {b:'2',L:'3',f:'f_a(x)=x³−3ax+2'},
    'a≤0：R 上严格递增。a>0：在(−∞,−√a)、(√a,+∞)递增，在(−√a,√a)递减。\n不同实根：a<1 时1个；a=1 时2个；a>1 时3个。\n第三项：1<a≤25/9；需解释重根与端点。',[
      {methodId:a,working:'f′=3(x²−a) 给出单调区间。a>0 时极大值2+2a^(3/2)>0，极小值2−2a^(3/2)在 a=1 变号。a=1 时 f=(x−1)²(x+2)，只有两个不同实根。\na>1 时恰有一负两正三个不同实根。所有根在[−3,3]内必有 f(−3)=9a−25≤0，故a≤25/9。反之，1<a≤25/9 时 √a<3，f(−3)≤0、f(−√a)>0、f(√a)<0、f(3)=29−9a>0，三个单调区间各有一根且均在界内。'},
      {methodId:b,working:'原函数单调性由 f′=3(x²−a)得到。零点方程写为 a=g(x)=x²/3+2/(3x)，x≠0；g′=2(x³−1)/(3x²)。\n负半轴上 g 严格递减且值域为 R，恒有一负根；正半轴上 g 在x=1取最小值1，故分别有0、1、2个正根。\na>1 时，负根≥−3 等价于 a≤g(−3)=25/9；较大正根≤3 等价于 a≤g(3)=29/9；较小正根在(0,1)。交集为1<a≤25/9。'},
    ],'人工构造的高中综合题，非考试真题；公式与边界已核算，可用状态为 mock。');
  return e.data;
}

function k8s(){
  const e=example('K8s · 排障示例','Service 选择器与转发端口故障的定位、修复和验证');
  const selectors=e.knowledge('Service 选择器与 Pod 标签','带 selector 的 Service 通过标签匹配确定后端，控制器维护对应 EndpointSlice。','同命名空间、带 selector 的普通 Service；不涉及手工端点。','selector 不匹配时预期 Pod 不会成为后端。');
  const ports=e.knowledge('Service 端口与实际监听端口','port 是访问端口，targetPort 应对应后端应用实际服务端口。','检查协议及实际监听；声明 containerPort 不能证明应用正在监听。','Service port=80 可转发到应用8080端口。');
  const evidence=e.knowledge('分层排障与修复验证','根据观察区分故障层次，修改后复查原路径，避免用绕过方案冒充恢复。','环境与操作范围明确，命令成功不等于服务恢复。','修正 selector 后仍失败，应依据证据继续检查端口。');
  const a=e.method('从客户端沿 Service 路径排查','从失败现象向后端逐层检查，修改后沿原路径复查。','DNS、基础网络及应用正常，故障限 selector 或 targetPort，可能同时存在。','指定环境与访问失败现象，通过检查逐步获取信息。','原因与证据、范围内的修复、服务恢复验证记录。',[
    ['确认现象与环境','核对命名空间、原地址和 Service，读取配置及 EndpointSlice，不预设只有一处错误。'],
    ['检查选择关系','未选中预期 Pod 时对照 selector 与实际标签；证实后修正。选择正确则进入转发检查。'],
    ['检查转发并复查','对照 targetPort 与实际监听端口，修正已证实差异后复查原路径。仍失败时依据新证据继续在本例范围内检查。'],
    ['结束条件','原地址响应符合要求、就绪后端齐全、改动未越权时结束。证据不足或超出边界时说明未解决原因并停止，不报告成功。'],
  ],[selectors,ports,evidence]);
  const b=e.method('从应用后端反向核对 Service','先确认预期 Pod 标签、就绪状态和实际端口，再与 Service 对照。','已知目标应用及允许检查的资源，只能修改指定 Service。','应用与客户端标识，逐步取得的 Pod 和 Service 事实。','与正向排查一致的原因、修复和验证结果。',[
    ['确认后端','检查预期 Pod 是否就绪并直接验证服务，获取标签与实际监听端口，不仅查看 containerPort 声明。'],
    ['对照并修正','将 selector、targetPort 与后端事实对照，可一次修改已证实的两处差异。'],
    ['验证和停止','复查 EndpointSlice 与原地址。满足完成要求才结束；证据不足或超出范围时说明未解决状态，不扩大改动。'],
  ],[selectors,ports,evidence]);
  const t=e.task({name:'诊断并修复 Service 访问异常',summary:'调查配置与运行状态，修复后验证原访问路径。',goal:'在指定权限与故障范围内恢复访问，并解释原因。',responsibility:'自行调查，区分现象和原因，只修改允许对象，保留依据并验证结果。',requirements:[
    {deliverable:'故障原因与定位依据',criterion:'有配置及运行观察支持；组合故障分别解释影响，不以猜测代替检查。'},
    {deliverable:'指定 Service 的配置修复',criterion:'仅改 selector、targetPort；保留 Service、访问地址、应用与副本，不通过删除或换地址绕过。'},
    {deliverable:'恢复结果及验证记录',criterion:'指定客户端经原地址获得 HTTP 200 和预期正文，三个预期就绪 Pod 均成为后端，未修改范围外资源。命令成功本身不算完成。'},
  ],parameters:[
    {symbol:'namespace',name:'练习命名空间',kind:'配置／资源',role:'题目已给定',condition:'固定在一次练习的隔离环境内。'},
    {symbol:'service',name:'待修复的 Service',kind:'配置／资源',role:'题目已给定',condition:'带 selector 的 ClusterIP Service，名称与访问地址固定。'},
    {symbol:'workload',name:'预期应用',kind:'配置／资源',role:'题目已给定',condition:'三个预期 Pod；应用本身、DNS 与基础网络正常。'},
    {symbol:'client',name:'验证客户端及预期响应',kind:'配置／资源',role:'题目已给定',condition:'经原地址验证，不能以直连 Pod 代替最终验收。'},
    {symbol:'observations',name:'标签、后端和实际监听信息',kind:'状态／观测',role:'需要通过调查获取',condition:'通过允许的资源读取和检查获取；不在题面提前告知差异及根因。'},
    {symbol:'cause',name:'故障原因',kind:'文本',role:'需要研究或求解',condition:'范围限 selector、targetPort 的单项或组合错误，结论需要证据。'},
  ],relations:'selector 应匹配预期 Pod 标签，targetPort 应对应应用实际服务端口，后端须就绪。可读取指定命名空间资源并执行规定的客户端检查，仅可修改指定 Service 的 selector 和 targetPort；原地址与应用保持不变。',variations:[
    {target:'资源名称、标签及端口',range:'合法名称、标签和端口值。',constraint:'保持路径明确、应用可用、权限一致，各引用需相互匹配。'},
    {target:'故障组合',range:'selector 错误、targetPort 错误，或两者同时发生。',constraint:'后台保留设置及核验依据，题面不泄露根因。组合故障不保证与单故障同难度。'},
  ],exclusions:'不包含 DNS、NetworkPolicy、CNI、应用代码或节点故障。反例：必须改应用代码才能恢复，超出此模板；换地址绕过故障不算完成。本原型仅展示静态 mock，不创建集群、执行命令或测量恢复。',methods:[a,b]});
  e.instance(t,'命名空间 lab 内有 web 应用及三个副本。客户端 client 通过 http://web.lab.svc.cluster.local 访问失败。\n请定位原因、修复并提供验证记录。DNS、基础网络与应用本身正常。可读取 lab 内资源，并从 client 检查连通性；仅可修改 Service web 的 selector 和 targetPort。\n保持原应用、副本与访问地址。完成后原地址应返回 HTTP 200 和正文 web-ok，三个预期就绪 Pod 均应成为服务后端。',
    {namespace:'lab',service:'web；ClusterIP；http://web.lab.svc.cluster.local',workload:'Deployment web；三个副本',client:'Pod client；预期 HTTP 200、正文 web-ok'},
    '后台模拟设置（不展示给学习者）：三个 Pod 标签 app=web，实际监听8080且就绪；Service selector 为 app=frontend，port=80，targetPort=8000。\n预期修复：selector 改为 app=web，targetPort 改为8080。验证就绪后端、原地址响应及改动范围。本例未连接集群，参考答案不能替代真实执行证据。',[
      {methodId:a,working:'模拟走查：未选中预期 Pod，比较标签确认 app=frontend 与 app=web 不匹配。修正 selector 后出现三个后端，但原地址仍失败。\n继续检查实际服务监听8080，而 Service 转发至8000；修正 targetPort。核对三个就绪后端，由 client 经原地址获得预期响应，并检查未改其他资源。以上为预设结果，未执行真实命令。'},
      {methodId:b,working:'模拟走查：先确认三个 Pod 的实际标签 app=web、监听8080且就绪；读取 Service 后同时发现两处差异。\n一次修正两处已证实的错误，检查后端与原客户端路径。允许不同检查顺序；仅提交修复建议不能声称已恢复服务。'},
    ],'人工构造练习，依据 Kubernetes Debug Services：https://kubernetes.io/docs/tasks/debug/debug-application/debug-service/ 。静态 mock，未部署执行。');
  return e.data;
}
