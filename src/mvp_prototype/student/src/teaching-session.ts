import { reactive, computed, watch } from 'vue';

// Authored interaction fixtures, not a semantic judge or a teaching engine.
export const scenarios = { foundation:'基础含义不清楚', explanation:'会算但解释不清', transfer:'已理解，检验图示迁移' };
export type Scenario = keyof typeof scenarios;
type Step = 'entry'|'basic'|'original'|'contrast'|'practice'|'choice'|'offer'|'testing'|'feedback'|'summary';
type Visual = 'dots'|'contrast'|'garden';
interface Message { id:number; role:'user'|'assistant'; text:string; visual?:Visual }
interface Attempt { item:string; purpose:'练习'|'检测'; answer:string; result:string; help:string; basis:string }
interface Session { version:1; scenario:Scenario; step:Step; messages:Message[]; draft:string; notice:string;
  attempts:Attempt[]; trace:{stage:string;strategy:string;reason:string}[]; checks:number; prepared:boolean;
  preparationError:boolean; uncertainty:boolean; explanationSupported:boolean; transferSupported:boolean;
  activeTest:string; testFinished:boolean; lastResult:string; page:string; visible:boolean; collapsed:boolean; }

export const original='气象小组有 12 人，摄影小组的人数是气象小组的 1/3，航模小组的人数是摄影小组的 3/4。航模小组有多少人？';
export const samples = {
  basicGood:'18 ÷ 3 = 6。把18平均分成3份，取其中1份。',
  basicWrong:'三分之一就是3个人。',
  originalGood:'摄影有4人，第二个分数对应这4人，所以4 × 3/4 = 3人。',
  originalWrong:'航模是12人的四分之三，所以有9人。',
  contrastGood:'A是摄影的四分之三，4 × 3/4 = 3；B是气象的四分之三，12 × 3/4 = 9。',
  contrastWrong:'都是四分之三，应该一样。',
  practiceGood:'24 × 1/3 = 8，8 × 3/4 = 6。第二个分数对应折纸组的8人。',
  textGood:'30 × 2/5 = 12，12 × 1/2 = 6。后一半对应科普书的12本。',
  textWrong:'30 × 1/2 = 15本。后一半对应所有图书。',
  graphGood:'40 × 3/5 = 24，24 × 1/2 = 12平方米。一半对应花区，不是整块苗圃。',
  graphWrong:'40 × 1/2 = 20平方米。一半对应整个苗圃。',
  graphBare:'12',
};
export function createTeachingSession(scenario:Scenario, page='textbook') {
  const key='deermind-teaching-preview-v1-'+scenario;
  if(!['home','status','textbook','errorbook'].includes(page))page='textbook';
  const initial:Session={version:1,scenario,step:'entry',messages:[],draft:'',notice:'',attempts:[],trace:[],checks:0,
    prepared:false,preparationError:false,uncertainty:false,explanationSupported:false,transferSupported:false,
    activeTest:'',testFinished:false,lastResult:'',page,visible:true,collapsed:false};
  let saved:Session|undefined;
  try{const value=JSON.parse(sessionStorage.getItem(key)||'null');if(value?.version===1&&value.scenario===scenario)saved=value;}catch{/* Preview can start without browser storage. */}
  const state=reactive<Session>(saved||JSON.parse(JSON.stringify(initial)));
  const storageError=reactive({message:''});
  watch(state,()=>{try{sessionStorage.setItem(key,JSON.stringify(state));storageError.message='';}catch{storageError.message='此浏览器未能保存演示进度，刷新后可能丢失。';}},{deep:true,flush:'sync'});
  function say(text:string,visual?:Visual,role:'user'|'assistant'='assistant'){state.messages.push({id:state.messages.length+1,role,text,visual});}
  function select(step:Step,stage:string,strategy:string,reason:string){state.step=step;state.trace.push({stage,strategy,reason});}
  function foundation(){say('这里的 1/3 表示分法，不是人数。把12人平均分成3组，取其中1组，就是4人。', 'dots');select('basic','讲解与互动 → 练习与反馈','基础回补','先回应分数含义的具体疑问，再检查单层关系。');say('换个数试试：18人的 1/3 是多少人？请说说你怎么分。');}
  function contrast(){say('两句话只有一个参照对象不同，结果也会不同。请比较 A 和 B，说明各是“谁的”四分之三。','contrast');select('contrast','讲解与互动','对比辨析','需要分清第二层分数的参照量；不因结果正确就推断理解充分。');}
  function explainContrast(){say('A 的四分之三以摄影组4人为整体，得到3人；B 以气象组12人为整体，得到9人。关键是分数前面的“谁”，不是看到分数就连乘。');select('choice','讲解与互动','直接解释','学生请求直接讲解，立即回应，不强迫猜答案。');}
  function practice(){select('practice','练习与反馈','逐步撤去帮助','用未讲过的文字题观察能否说明两层关系。');say('手工社团有24人，折纸组占社团的 1/3，纸花组占折纸组的 3/4。纸花组有多少人？请写下答案和理由。');}
  function entry(){
    say(original);
    if(scenario==='foundation'){say('三分之一是3个人吗？',undefined,'user');foundation();}
    if(scenario==='explanation'){say('12 × 1/3 × 3/4 = 3。看到两个分数就乘起来。',undefined,'user');say('3人这个结果是对的。你这句话还没说明两个分数各对应谁，我们比较两种说法。');contrast();}
    if(scenario==='transfer'){say('文字题我会了，想试试图里的关系。',undefined,'user');say('之前的文字题中，你已经说明了两层分数各对应谁。我们可以跳过重复讲解，换一张图看看。');offer();}
  }
  function record(item:string,purpose:Attempt['purpose'],answer:string,result:string,help:string,basis:string){state.attempts.push({item,purpose,answer,result,help,basis});}
  const waiting=computed(()=>['basic','original','contrast','practice','testing'].includes(state.step));
  const label=computed(()=>state.step==='testing'?'检测中':state.step==='summary'?'本次已结束':state.step==='offer'?'准备检测':waiting.value?'练习与互动':'章节讲解');
  const inputContext=computed(()=>state.step==='summary'?'本次已结束，记录已保留':state.step==='testing'?'正在回答第 1 题 · 提交后结束本次检测':waiting.value?'回答上面的问题，也可以点击“直接讲解”':'继续追问，或选择下一步');
  const presets=computed(()=>(({basic:[samples.basicGood,samples.basicWrong],original:[samples.originalGood,samples.originalWrong],contrast:[samples.contrastGood,samples.contrastWrong],practice:[samples.practiceGood,'24 × 3/4 = 18人。'],testing:scenario==='transfer'?[samples.graphGood,samples.graphWrong,samples.graphBare]:[samples.textGood,samples.textWrong]} as Partial<Record<Step,string[]>>)[state.step]||[]));
  function offer(){state.prepared=false;state.preparationError=false;select('offer','阶段检测','按目标准备新题','先确定检测目的，再检查、保存题目，最后由学生同意开始。');say(scenario==='transfer'?'可以做1道图示题，看看你能否从图中找出两层关系。':'可以做1道新的文字题，看看你能否自己说明两层关系。');}
  function prepare(fail=false){if(state.step!=='offer')return;state.preparationError=fail;state.prepared=!fail;if(!fail)state.trace.push({stage:'阶段检测',strategy:'题目准备',reason:'固定候选 v1：题意、解答、方法与模板匹配检查通过，先保存，再等待开始。'});}
  function start(){if(state.step!=='offer'||!state.prepared)return;state.draft='';state.testFinished=false;state.lastResult='';state.checks++;state.activeTest=scenario==='transfer'?'CHAIN-DIAGRAM@1':'CHAIN-TEXT@1';select('testing','阶段检测','变式检测','学生明确开始；题目已准备，未展示答案或中间量。');say(scenario==='transfer'?'整块苗圃40平方米，分成面积相等的5列。左侧3列是花区，花区的上半部种月季。月季有多少平方米？请说明理由。':'图书角有30本书，科普书占全部的 2/5，动物书占科普书的 1/2。动物书有多少本？请说明理由。',scenario==='transfer'?'garden':undefined);}
  function submit(text:string){
    if(!text.trim()||state.step==='summary')return;
    const value=text.trim();state.draft='';state.notice='';say(value,undefined,'user');
    if(!presets.value.includes(value)){
      if(waiting.value)record(state.step==='testing'?state.activeTest:state.step,state.step==='testing'?'检测':'练习',value,'未预设判定','按当前对话保留','此自由输入没有编写响应，不做关键词判定。');
      if(state.step==='testing'){state.testFinished=true;select('feedback','阶段检测 → 收束','保留未决','检测已提交，但该自由输入没有 mock 判定。');state.lastResult='这份作答已保留，目前没有对应的演示判定。';}
      state.notice='这是固定情境演示，这段输入尚未编写响应；已保留，不据此判对错或更新能力。可在“演示工具”填入预设回答，或直接讲解、结束。';return;
    }
    if(state.step==='testing'){
      state.testFinished=true;
      const correct=value===(scenario==='transfer'?samples.graphGood:samples.textGood),bare=value===samples.graphBare;
      record(state.activeTest,'检测',value,correct?'正确且理由充分':bare?'数值正确，解释待确认':'参照量错误','本题未求助；上文和右侧仍可见，不能保证独立条件','固定案例匹配；提交后整场1题检测结束，才展示反馈。');
      if(correct){if(scenario==='transfer')state.transferSupported=true;else state.explanationSupported=true;}
      state.lastResult=correct?(scenario==='transfer'?'12平方米，结果和理由都对。这次能从这张图找到两层关系。':'6本，结果和理由都对。这次能说明两层分数各对应谁。'):bare?'12平方米这个数值正确。你还没有说明理由，因此理解与解释仍待确认。':scenario==='transfer'?'这里的一半是花区的一半。你用了整块苗圃40平方米，所以得到20；正确结果是12平方米。':'这里的一半对应科普书12本，不能直接取全部30本的一半；动物书有6本。';
      select('feedback','阶段检测 → 反馈','按实际表现反馈','先结束检测再解释；个人判断与目标达成分开，限定这次材料。');say('本次检测已结束。'+state.lastResult);return;
    }
    const step=state.step;
    const good=[samples.basicGood,samples.originalGood,samples.contrastGood,samples.practiceGood].includes(value);
    record(step,'练习',value,good?'本次回答符合预设要求':'需继续讲解','刚接受相关讲解，属于受助后的练习','不将练习成功当作独立或持久掌握。');
    if(step==='basic'){
      if(good){say('对，3表示平均分成3份，6才是每份的人数。回到原题：摄影是4人，航模是“谁的”四分之三？');select('original','讲解与互动','回到原问题','单层练习通过，仅说明局部表现，不完成两层任务的评价。');}
      else{say('3是份数。也可以想成把18人平均装进3个袋子，每袋6人；取1袋就是6人。不急着再做一道相同的题。');select('choice','讲解与互动','更换表示','再次混淆时换一种解释，允许回到原题或结束，不无限刷同题。');}
    }else if(step==='original'){
      if(good){say('对，第二次以摄影的4人为整体。也可以算 12 × (1/3 × 3/4)，理由同样是两层包含关系。');select('choice','练习与反馈','确认局部理解','受助后的原题成功不冒充新题检测。');}else contrast();
    }else if(step==='contrast'){
      if(good){say('你说明了 A 和 B 的区别。接下来可以用一道新的两层关系题练习。');select('choice','讲解与互动','对比辨析','能区分两种说法；辨析材料不作为完整任务的独立通过。');}
      else{say('我们换成分组来看，先弄清第一层，再回来比较。');foundation();}
    }else if(step==='practice'){
      say(good?'6人，计算和两层参照量都说清楚了。这是刚刚讲解后的练习。':'18人是社团总人数的四分之三。题目问的是折纸组的四分之三，先求出折纸组8人，再求6人。');select('choice','练习与反馈','反馈与选择','练习即时反馈；是否继续检测由学生决定。');
    }
  }
  function help(){
    if(state.step==='testing'){
      record(state.activeTest,'检测','','未提交／未检测','求助先结束检测；草稿单独保留：'+(state.draft||'无'),'未提交不计错；随后讲解不改写原始记录。');state.testFinished=true;state.lastResult='本次检测因求助结束，未提交题目没有判错。';say(state.lastResult);select('feedback','阶段检测 → 讲解与互动','对比辨析','先结束整场检测，保留草稿，再提供实质帮助。');
      say(scenario==='transfer'?'左侧3列是花区：40 × 3/5 = 24平方米；月季是这24平方米的一半，所以是12平方米。':'先求科普书：30 × 2/5 = 12本；动物书是这12本的一半，所以是6本。');return;
    }
    if(state.step==='feedback'){say(scenario==='transfer'?'图里先取整块的3/5得到花区24平方米，再取花区的一半得到12平方米。可以先算两步，也可以合并两个比例。原检测记录保持不变。':'30本书中科普书有12本，再取科普书的一半是6本。原检测作答保留。');return;}
    if(state.step==='basic'){say('18平均分成3份，每份6人。原题的摄影组同样先把12人平均分3份，得到4人。');}
    else if(state.step==='contrast'){explainContrast();return;}
    else say('先求摄影组 12 × 1/3 = 4，再求航模组 4 × 3/4 = 3。也可以先合并两个比例，再乘12，两种方法都要说明参照对象。');
    select('choice','讲解与互动','直接解释','明确求助即解释，不把听过讲解记作掌握。');
  }
  function unclear(){if(state.step!=='testing')return;state.uncertainty=true;say('可以点击“放大图示”查看。这里没有给出新的解题提示；如果仍看不清，可以结束这次检测，不计作答错误。');}
  function defective(){if(state.step!=='testing')return;record(state.activeTest,'检测','','材料待核对','未继续判定学生能力','演示工具注入：确认有缺失的区域标注。');state.testFinished=true;state.lastResult='这道题的区域标注需要核对，本次不判断你的能力。';say(state.lastResult);select('feedback','阶段检测 → 收束','材料未决','真实材料疑点与学生答错分开。');}
  function finish(){
    if(state.step==='summary')return;
    if(state.step==='testing'){record(state.activeTest,'检测','','未提交／未检测','主动结束；保留草稿：'+(state.draft||'无'),'未提交不计错。');state.testFinished=true;state.lastResult='本次检测提前结束，未提交题目没有判错。';}
    select('summary','收束','总结实际路径','只总结真实经历的练习和检测，不补写未做的题。');say('今天先到这里。'+(state.lastResult||'本次进行了讲解和练习，没有新的检测结论。'));
  }
  function reset(){Object.assign(state,JSON.parse(JSON.stringify(initial)),{messages:[],attempts:[],trace:[],draft:'',step:'entry'});entry();}
  if(!saved)entry();
  const summary=computed(()=>[
    {name:'理解与解释',judgment:state.explanationSupported?'本次新文字题能说明两层参照量':scenario==='transfer'?'既有文字题表现仍保留：能说明两层参照量':'当前只有局部或受助表现，还需新的完整证据',target:state.explanationSupported||scenario==='transfer'?'文字解释要求已有局部支持':'待确认'},
    {name:'图示迁移',judgment:state.transferSupported?'本次嵌套区域图能解释正确':state.attempts.some(a=>a.answer===samples.graphWrong)?'这次把花区的一半误当成全图的一半':'尚无充分的新图示证据',target:state.transferSupported?'本类图示要求已有局部支持':state.attempts.some(a=>a.answer===samples.graphWrong)?'需加强':'待确认'},
    {name:'独立',judgment:'本次不保证独立条件；上文和右侧内容仍可见',target:'本次不新增结论'},
    {name:'持久',judgment:'本次没有间隔后的检测',target:'本次不新增结论'},
  ]);
  return {state,storageError,waiting,label,inputContext,presets,summary,submit,offer,prepare,start,help,unclear,defective,practice,finish,reset};
}
export type TeachingSession=ReturnType<typeof createTeachingSession>;
