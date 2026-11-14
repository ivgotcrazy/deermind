import { domainData, id, instanceSignature, type Task, type Method, type Knowledge, type Instance } from './domain';

export function addDomainExample(){
  const domainId=id('DOM'), taskId=id('TT'), partId=id('TT'), a=id('ST'), b=id('ST'), partMethod=id('ST');
  const ref=id('KC'), fraction=id('KC'), growth=id('KC');
  domainData.domains.push({id:domainId,name:'小学数学 · 示例',scope:'比例增加及其基础任务',description:'人工编写的 mock，供查看对象关系；不是已完成全册建模。',version:1});
  const knowledge:Knowledge[]=[
    {id:ref,domainId,version:1,name:'分率的参照整体',description:'分率表示一个量相对于所指整体的比例。',conditions:'使用分率前须明确对应的整体。',example:'增加原长的四分之一，整体为原长。',prerequisites:[]},
    {id:fraction,domainId,version:1,name:'求一个量的几分之几',description:'基准量乘分率，得到对应部分的量。',conditions:'基准量与分率已知；分率对应的整体明确。',example:'40 × 1/4 = 10。',prerequisites:[ref]},
    {id:growth,domainId,version:1,name:'原量、增加量与新量的关系',description:'新量等于原量加增加量；增加分率为 r 时，新量是原量的 1+r 倍。',conditions:'增加比例以原量为基准，原量与增加量单位一致。',example:'40 + 40 × 1/4 = 40 × (1+1/4)。',prerequisites:[ref]},
  ];
  domainData.knowledge.push(...knowledge);
  const parameters:Task['parameters']=[{symbol:'V',name:'原量',kind:'数值',role:'题目已给定',condition:'V > 0，数量及单位明确'},{symbol:'r',name:'增加比例',kind:'数值',role:'题目已给定',condition:'r > 0，以原量为基准，无量纲'},{symbol:'W',name:'新量',kind:'数值',role:'需要研究或求解',condition:'与 V 同单位；离散数量应满足整量要求'}];
  domainData.tasks.push({id:taskId,domainId,version:1,name:'已知原量和增加比例，求新量',summary:'识别参照量，求出增加后的数量。',goal:'求新量 W',responsibility:'识别增加比例对应的原量；选择方法并求出新量；说明数量关系。',requirements:[{deliverable:'新量、单位及数量关系说明',criterion:'结果满足题设关系，单位正确，并说明增加比例以原量为参照。'}],parameters,relations:'增加量 / 原量 = r；新量 = 原量 + 增加量。题面给出原量与增加比例。',variations:[{target:'原量与增加比例',range:'正数量、正有理数分率',constraint:'单位一致；离散数量应满足整量要求。'},{target:'情境与表达',range:'文字或表格提供已知条件',constraint:'保留原量及增加比例的参照关系；实例记录所用表达，不能视为等价能力证据。'}],exclusions:'不包括反求原量、减少量、连续多次增减；离散数量不取非整量。',methods:[a,b]});
  domainData.tasks.push({id:partId,domainId,version:1,name:'求一个量的几分之几',summary:'给定基准量与分率，求对应数量。',goal:'求对应数量 Δ',responsibility:'识别基准量，并计算对应部分。',requirements:[{deliverable:'对应数量及单位',criterion:'明确基准量，结果满足对应数量与基准量的比例关系。'}],parameters:[{symbol:'V',name:'基准量',kind:'数值',role:'题目已给定',condition:'正数量'},{symbol:'r',name:'分率',kind:'数值',role:'题目已给定',condition:'正有理数'},{symbol:'Δ',name:'对应数量',kind:'数值',role:'需要研究或求解',condition:'与 V 同单位'}],relations:'Δ / V = r。',variations:[{target:'基准量与分率',range:'正数量、正有理数分率',constraint:'分率对应的整体明确，单位一致。'}],exclusions:'本任务只求对应部分，不直接求增加后的总量。',methods:[partMethod]});
  const methods:Method[]=[
    {id:partMethod,domainId,version:1,name:'使用分数乘法求对应数量',description:'基准量乘分率。',conditions:'基准量和所对应分率已知。',inputs:'V：基准量；r：分率',output:'Δ：对应数量',steps:[{title:'计算对应数量',detail:'输入 V、r，计算 Δ = V × r，输出 Δ。',divided:false,taskId:'',solutionId:''}],kc:[ref,fraction]},
    {id:a,domainId,version:1,name:'先求增加量，再加原量',description:'将增加量计算出来，再与原量相加。',conditions:'增加比例以原量为基准，单位一致。',inputs:'V：原量；r：增加比例',output:'W：新量',steps:[{title:'求增加量',detail:'把 V、r 传给子方法，得到增加量 Δ。',divided:true,taskId:partId,solutionId:partMethod},{title:'求新量',detail:'输入 V、Δ，输出 W = V + Δ。',divided:false,taskId:'',solutionId:''}],kc:[growth]},
    {id:b,domainId,version:1,name:'按原量的 1+r 倍计算',description:'先确定新量相对于原量的倍数。',conditions:'增加分率的整体是原量。',inputs:'V：原量；r：增加比例',output:'W：新量',steps:[{title:'计算新量',detail:'先确定新量是原量的 1+r 倍，再计算 W = V × (1+r)。',divided:false,taskId:'',solutionId:''}],kc:[ref,fraction,growth]},
  ];
  const stepIO:Record<string,[string,string][]>={
    [partMethod]:[['V：基准量；r：分率','Δ=V×r，返回对应数量']],
    [a]:[['将原量 V、比例 r 传给子方法同名参数','返回 Δ，供步骤2使用'],['原量 V、步骤1返回的 Δ','W=V+Δ，新量与单位']],
    [b]:[['V：原量；r：增加比例','W=V×(1+r)，新量与单位']],
  };
  for(const m of methods){
    m.steps.forEach((s,i)=>Object.assign(s,{key:'step-'+(i+1),kind:'process',inputs:stepIO[m.id][i][0],output:stepIO[m.id][i][1],next:'$next',routes:[],coverage:''}));
    m.ending={success:m.id===partMethod?'明确比例参照量；乘法结果与单位正确，得到对应数量。':'新量满足原量、增加比例与新量的关系；单位正确，能说明计算依据。',stop:'缺少原量或比例、参照整体不明确、单位不相容或子方法未解决时停止并保留原因。'};
  }
  // This newly authored fixture supplies complete direct KC links; saved user records are not rewritten.
  methods[1].kc=[ref,fraction,growth];
  methods[0].procedure='明确基准量与分率，计算对应数量 Δ=V×r，核对单位。';
  methods[1].procedure='明确原量和增加比例；计算增加量 Δ=V×r；加回原量 W=V+Δ；检查最终量及单位。';
  methods[2].procedure='把原量作为1份，确定新量为1+r份；计算 W=V×(1+r)，说明比例的参照量并检查结果。';
  domainData.tasks.find(t=>t.id===taskId)!.prerequisites=[{taskId:partId,reason:'先求增加量的方法需要识别整体并求对应部分。',methodIds:[a]}];
  domainData.methods.push(...methods);
  const q:Instance={id:id('TI'),domainId,taskId,version:1,question:'一根绳原长40米，增加原长的四分之一后，共长多少米？请说明数量关系。',bindings:{V:'40 米',r:'1/4'},table:null,answer:'50米；增加的四分之一以原长40米为整体。',solutions:[{methodId:a,working:'40 × 1/4 = 10（米），40 + 10 = 50（米）。'},{methodId:b,working:'40 × (1 + 1/4) = 50（米）。'}],source:'人工编写',sourceNote:'M1 自编示例，非教材原题；检查为固定 mock。',checkedSignature:'',checkedAt:new Date().toLocaleString('zh-CN')};
  q.checkedSignature=instanceSignature(q);domainData.instances.push(q);
  return domainId;
}
