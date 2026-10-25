// UI review fixtures only. These are not definitions or model execution records.
export interface MockParameter { symbol:string; name:string; type:string; role:string; condition:string }
export interface MockRelation { meaning:string; expression:string; given:string }
export interface MockMethod { id:string; name:string; description:string; inputs:[string,string][]; output:string; steps:{title:string; detail:string; children?:string[]}[]; kc:string[] }
export interface MockCase { label:string; text:string; verdict:string; bindings:[string,string][]; reasons:string[] }
export interface MockTask {
  id:string; label:string; name:string; summary:string; goal:string; responsibility:string; output:string;
  parameters:MockParameter[]; relations:MockRelation[]; variations:string; exclusions:string;
  methods:string[]; availableMethods:string[];
  question:string; answer:string; working:string[]; checks:string[]; cases:MockCase[];
}
export const mockKnowledge = [
  {id:'K-REF',name:'分数的参照量',description:'辨认一个分数是相对于哪个量而言。'},
  {id:'K-PART',name:'求一个量的几分之几',description:'根据基准量和比例确定对应数量。'},
  {id:'K-GROW',name:'增加后的倍数关系',description:'增加原量的 r 后，最终量为原量的 1+r 倍。'},
  {id:'K-HEIGHT',name:'三角形的底与对应高',description:'从顶点到所选底边所在直线的垂直距离。'},
  {id:'K-TRI',name:'三角形面积',description:'三角形面积等于底与对应高乘积的一半。'},
  {id:'K-RECT',name:'长方形面积',description:'长方形面积等于长乘宽。'},
  {id:'K-AREA',name:'面积的可加性与区域差',description:'内含且不重叠的区域，可通过分割求和或整体相减求面积。'},
];
export const mockMethods:MockMethod[] = [
  {id:'S1-A',name:'先求增加量，再求总量',description:'把增加的部分单独求出，再与原量相加。',inputs:[['原量','q'],['增加比例','r']],output:'最终量 → t',steps:[
    {title:'求增加量',detail:'引用子任务：求给定量的几分之几；输入 q、r，输出 Δ。',children:['子任务 T0：求给定量的几分之几','方法 S0：使用分数乘法，Δ = q × r']},
    {title:'合并原量与增加量',detail:'t = q + Δ。'}],kc:['K-PART']},
  {id:'S1-B',name:'先求最终量对应的倍数',description:'把原量看作 1，先确定最终量对应的倍数。',inputs:[['原量','q'],['增加比例','r']],output:'最终量 → t',steps:[{title:'确定倍数',detail:'最终量是原量的 1+r 倍。'},{title:'求最终量',detail:'t = q × (1+r)。'}],kc:['K-GROW']},
  {id:'S2-A',name:'底乘对应高，再除以二',description:'先确认底高配对，再使用面积关系。',inputs:[['底长','b'],['对应高','h']],output:'面积 → S',steps:[{title:'确认对应关系',detail:'确认高垂直于所选底边所在直线。'},{title:'求面积',detail:'S = b × h ÷ 2。'}],kc:['K-HEIGHT','K-TRI']},
  {id:'S3-A',name:'整体面积减去花坛面积',description:'先求扩建后的尺寸，再用花园面积减去花坛面积。',inputs:[['花园长、宽','L、W'],['原底长、增加比例','q、r'],['保持不变的高','h']],output:'剩余面积 → A',steps:[
    {title:'求扩建后的底长',detail:'引用 T1：q、r → b。',children:['选择 S1-A：先求增加量，再求总量','继续引用 T0：q、r → Δ','合并得到 b = q + Δ']},
    {title:'求花坛面积',detail:'引用 T2：上一步的 b 与本任务的 h → 花坛面积。'},
    {title:'求花园面积',detail:'使用长方形面积规则：L × W。'},
    {title:'求剩余面积',detail:'花园面积 − 花坛面积 → A。'}],kc:['K-RECT','K-AREA','K-TRI','K-PART']},
  {id:'S3-B',name:'分割剩余区域，再求和',description:'将剩余区域划分为两个矩形和一个三角形。',inputs:[['花园长、宽','L、W'],['原底长、增加比例','q、r'],['保持不变的高','h']],output:'剩余面积 → A',steps:[{title:'确定新底长',detail:'引用 T1，求出 b。'},{title:'分割剩余区域',detail:'分为 (L−b)×W、b×(W−h) 两个矩形及底 b、高 h 的三角形；省略零面积区域。'},{title:'各部分求和',detail:'A = (L−b)×W + b×(W−h) + b×h÷2。'}],kc:['K-RECT','K-TRI','K-AREA']},
];
export const mockTasks:MockTask[] = [
  {id:'fraction',label:'分数应用',name:'已知原量和增加比例，求增加后的量',summary:'在一次增加的情境中，根据原量和相对原量的增加比例，求最终数量。',goal:'求增加后的数量 t',responsibility:'识别增加比例以原量为基准\n从情境中建立数量关系\n计算最终数量',output:'给出最终数量及适用单位。若要求列式，应在具体题目中说明。',parameters:[
    {symbol:'q',name:'增加前的原量',type:'数量',role:'已知量',condition:'q > 0'},
    {symbol:'r',name:'相对原量的增加比例',type:'比例',role:'已知量',condition:'无量纲，正有理数'},
    {symbol:'t',name:'增加后的量',type:'数量',role:'最终输出',condition:'与 q 同类型、同单位'}],relations:[{meaning:'增加量占原量的比例为 r',expression:'(t − q) / q = r',given:'用文字说明比例及参照量，不直接给出计算式。'}],variations:'数值：在符合情境的范围内变化\n情境：水量、长度、图书数量等\n呈现：文字或示意图',exclusions:'不包括连续多次增减\n不包括已知最终量反求原量\n直接给出计算式时，未承担同样的关系建模工作',methods:['S1-A'],availableMethods:['S1-A','S1-B'],question:'水箱原有80升水，又加入了原有水量的四分之一。现在有多少升水？',answer:'100 升',working:['增加量：80 × 1/4 = 20（升）','最终量：80 + 20 = 100（升）'],checks:['原量和最终量均使用升，比例无量纲。','增加比例的参照量明确为原有水量。','题面没有提前给出需要学生建立的算式。'],cases:[
    {label:'符合模板',text:'班级原有40本图书，又购买了原有数量的十分之三。现在有多少本？',verdict:'符合模板',bindings:[['q','40 本'],['r','3/10'],['t','待求的最终图书数量']],reasons:['参照量是原有40本图书。','已知原量与增加比例，所求为最终量。','结果为52本，满足图书数量的整数条件。']},
    {label:'不符合模板',text:'班级现在有52本图书，比原来增加了十分之三。原来有多少本？',verdict:'不符合模板',bindings:[['已知','最终量52本、增加比例3/10'],['未知','原量']],reasons:['已知与未知的位置改变。','这道题是反求原量，不能直接按当前模板归类。']},
    {label:'信息不足',text:'水箱原有80升水，后来又加入了一些水。现在有多少升水？',verdict:'增加量尚未给出',bindings:[['q','80 升'],['r','尚不能确定']],reasons:['未给出增加量或增加比例，不能确定最终数量。','需要补充条件，不能自行给 r 赋值。']}]},
  {id:'geometry',label:'几何面积',name:'已知三角形的底与对应高，求面积',summary:'从文字或图形中识别一组底与对应高，计算三角形面积。',goal:'求三角形面积 S',responsibility:'识别底与对应高\n选择面积关系\n计算并使用正确面积单位',output:'给出面积数值与平方单位。',parameters:[
    {symbol:'ABC',name:'非退化三角形',type:'几何对象',role:'已知对象',condition:'底边为 AB，顶点为 C'},
    {symbol:'H',name:'C 到直线 AB 的垂足',type:'几何对象',role:'已知对象',condition:'可以位于底边或其延长线上'},
    {symbol:'b',name:'底边 AB 的长度',type:'长度',role:'已知量',condition:'b > 0'},
    {symbol:'h',name:'对应高 CH 的长度',type:'长度',role:'已知量',condition:'h > 0，与 b 单位一致'},
    {symbol:'S',name:'三角形面积',type:'面积',role:'最终输出',condition:'使用对应的平方单位'}],relations:[{meaning:'垂足位于底边所在直线',expression:'H ∈ 直线 AB',given:'文字说明或图形标注。'},{meaning:'CH 是 AB 对应的高',expression:'CH ⟂ AB',given:'明确的垂直条件或直角标记，不凭图形外观猜测。'}],variations:'数值：正的底长与对应高\n图形：旋转、内部高或外部高\n呈现：文字、图示；记录具体变化',exclusions:'不包括先求未知高度的额外步骤\n不把另一条斜边直接当作高\n本例不包含单位换算',methods:['S2-A'],availableMethods:['S2-A'],question:'如图，三角形ABC的底AB长12厘米，对应高CH长7厘米，求三角形面积。',answer:'42 平方厘米',working:['确认 CH 垂直于 AB。','三角形面积：12 × 7 ÷ 2 = 42（平方厘米）'],checks:['底与高对应，垂直关系明确。','长度单位一致。','图中未提前给出面积或计算式。'],cases:[
    {label:'符合模板',text:'三角形ABC的底AB长10厘米，C到直线AB的垂直距离为4厘米，求面积。',verdict:'符合模板',bindings:[['b','10 厘米'],['h','4 厘米'],['S','待求的三角形面积']],reasons:['垂直距离明确构成对应高。','即使垂足位于延长线上，也符合模板。','参考面积为20平方厘米。']},
    {label:'不符合模板',text:'三角形的底长10厘米，面积为20平方厘米，求这条底对应的高。',verdict:'不符合模板',bindings:[['已知','底与面积'],['未知','对应高']],reasons:['本题求高，当前模板求面积。','共享面积关系不等于同一任务。']},
    {label:'信息不足',text:'三角形一条底边长10厘米，另一条边长4厘米，求面积。',verdict:'对应高尚未确认',bindings:[['b','10 厘米'],['h','尚不能确定']],reasons:['另一条边不一定是对应高。','缺少垂直关系，不能把4厘米直接绑定为 h。']}]},
  {id:'composite',label:'递归综合任务',name:'花坛扩建后，求长方形花园的剩余面积',summary:'花坛的一条直角边按比例增加，另一条保持不变；求花园去掉花坛后的面积。',goal:'求剩余区域面积 A',responsibility:'确定扩建后的花坛尺寸\n组织分数关系与面积关系\n求花园扣除花坛后的面积',output:'给出剩余面积和单位；保留所选方法的必要中间结果。',parameters:[
    {symbol:'L',name:'长方形花园的长',type:'长度',role:'已知量',condition:'L > 0'},
    {symbol:'W',name:'长方形花园的宽',type:'长度',role:'已知量',condition:'W > 0'},
    {symbol:'q',name:'花坛原底长',type:'长度',role:'已知量',condition:'q > 0'},
    {symbol:'r',name:'底长相对原长的增加比例',type:'比例',role:'已知量',condition:'r > 0'},
    {symbol:'h',name:'保持不变的另一条直角边',type:'长度',role:'已知量',condition:'0 < h ≤ W'},
    {symbol:'b',name:'扩建后的底长',type:'长度',role:'待推导中间量',condition:'0 < b ≤ L'},
    {symbol:'A',name:'剩余区域面积',type:'面积',role:'最终输出',condition:'使用对应的平方单位'}],relations:[{meaning:'底长按原长的比例增加',expression:'(b − q) / q = r',given:'说明原底长与增加比例，不直接提供 b。'},{meaning:'花坛内含于花园，直角边沿相邻边',expression:'花坛 ⊆ 花园；两直角边分别沿长、宽方向',given:'文字或图形明确区域位置与方向。'}],variations:'花园与花坛的合法尺寸\n比例、角落位置及图形旋转\n情境名称和文字／图示呈现',exclusions:'扩建后花坛不能超出花园\n不包括多块区域重叠\n花园本身不同时扩建',methods:['S3-A'],availableMethods:['S3-A','S3-B'],question:'长方形花园长20米、宽12米。角落的直角三角形花坛两直角边沿花园相邻边，其中一条原长8米，增加原长的四分之一，另一条保持6米。其余区域铺草坪，求草坪面积。',answer:'210 平方米',working:['T1：新底长 = 8 × (1 + 1/4) = 10（米）','T2：花坛面积 = 10 × 6 ÷ 2 = 30（平方米）','花园面积 = 20 × 12 = 240（平方米）','剩余面积 = 240 − 30 = 210（平方米）'],checks:['扩建后底长10米不超过花园长20米，高6米不超过宽12米。','三角形两条直角边沿花园相邻边，区域完全内含。','T2 的底长来自 T1 输出，而非题目直接给定。'],cases:[
    {label:'符合模板',text:'长方形广场长30米、宽16米，角落的直角三角形绿地两直角边沿广场相邻边。一条原长10米，增加原长的五分之一，另一条保持8米。求其余铺砖区域面积。',verdict:'符合模板',bindings:[['L、W','30米、16米'],['q、r、h','10米、1/5、8米'],['b','需推导为12米'],['A','待求的剩余面积']],reasons:['尺寸变化、区域关系与目标均对应。','新底长12米、高8米均未越界。','参考结果为432平方米。']},
    {label:'不符合模板',text:'广场面积480平方米，绿地面积48平方米，求其余区域面积。',verdict:'仅对应局部计算',bindings:[['已知','两个区域的面积'],['未知','面积差']],reasons:['只需相减，未承担尺寸推导及面积建模。','不能因最后一步相同而认定完成了整个综合任务。']},
    {label:'信息不足',text:'长方形花园长20米、宽12米，内部三角形花坛一边长8米，扩大四分之一，另一边长6米。求剩余面积。',verdict:'几何条件不完整',bindings:[['L、W','20米、12米'],['底高关系','未确认']],reasons:['两条边是否垂直，以及扩建方向均未明确。','可以保留候选，不能补造条件宣布归类成功。']}]},
];
