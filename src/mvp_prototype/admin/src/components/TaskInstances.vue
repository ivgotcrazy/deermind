<script setup lang="ts">
const location=window.location;
import { computed, ref, watch } from 'vue';
import { type DomainTask, domainMock } from '../workbench/domain-mock';
import { taskInstances, generatedInstance } from '../workbench/domain-instances';
import { flow } from '../workbench/learning-flow';
import { copy, changeFlow, saveQuestion, fractionQuestion, type Question } from '../../../shared/learning-flow';
import { route, go } from '../workbench/navigation';
import WorkbenchDialog from './WorkbenchDialog.vue';
const props=defineProps<{task:DomainTask}>();
changeFlow(s=>{for(const q of taskInstances)if(!s.questions.some(x=>x.id===q.id))s.questions.push({...copy(q),version:1,source:'教材导入',methods:domainMock.tasks.find(t=>t.id===q.taskId)?.methods||[]});});
const query=ref(''),source=ref(''),page=ref(1),dialog=ref<'view'|'edit'|'generate'|null>(null),draft=ref<Question|null>(null),tab=ref('content');
const extraCandidates=ref<Question[]>([]);
const notice=ref(''),error=ref(''),outcome=ref('pass'),report=ref(''),count=ref(1),request=ref('增加分率为四分之一，使用新的数值'),parent=ref('');
const rows=computed(()=>flow.questions.filter(q=>q.taskId===props.task.id&&q.domainId===props.task.domainId&&(!source.value||q.source===source.value)&&(q.id+' '+q.question+' '+q.source).includes(query.value.trim())));
const sources=computed(()=>[...new Set(flow.questions.filter(q=>q.taskId===props.task.id&&q.domainId===props.task.domainId).map(q=>q.source))]);
const uses=computed(()=>flow.uses.filter(u=>u.question.id===draft.value?.id).slice().reverse());
watch([query,source],()=>page.value=1);
watch(()=>route.source,id=>{const q=flow.questions.find(q=>q.id===id&&q.taskId===props.task.id);if(q)open(q,'view');},{immediate:true});
watch(draft,()=>{report.value='';error.value='';},{deep:true});
function open(q:Question,mode:'view'|'edit'){extraCandidates.value=[];draft.value=copy(q);dialog.value=mode;tab.value='content';outcome.value='pass';report.value='';error.value='';}
function create(origin:string){count.value=1;open({id:'',taskId:props.task.id,domainId:props.task.domainId,version:1,question:'',parameters:'',answer:'',explanation:'',source:origin,sourceNote:'',methods:[...props.task.methods]},'edit');}
function generate(from?:Question){parent.value=from?.id||'';count.value=1;request.value='增加分率为四分之一，使用新的数值';error.value='';dialog.value='generate';}
function generated(){
  if(!Number.isInteger(count.value)||count.value<1||count.value>10){error.value='本次请输入 1–10 道题。';return;}
  const sample=generatedInstance(props.task.id,props.task.domainId);
  if(props.task.id!=='fraction'&&!sample){error.value='此模板尚无 mock 生成样例，可以新建或导入。';return;}
  if(props.task.id!=='fraction'&&count.value>1){error.value='这个模板目前只提供单题 mock 样例，请生成 1 题。';return;}
  const first=props.task.id==='fraction'?fractionQuestion(120,'后台生成'):{...sample!,version:1};
  open({...first,id:'',taskId:props.task.id,domainId:props.task.domainId,methods:[...props.task.methods],source:'后台生成',parentId:parent.value||undefined,sourceNote:'固定 mock 候选；本次生成要求：'+request.value},'edit');
  extraCandidates.value=Array.from({length:count.value-1},(_,i)=>({...fractionQuestion(140+i*20,'后台生成'),id:'',parentId:parent.value||undefined,sourceNote:draft.value!.sourceNote}));
}
async function importFile(event:Event){const file=(event.target as HTMLInputElement).files?.[0];if(!file||!draft.value)return;try{draft.value.question=await file.text();draft.value.sourceNote=file.name;}catch{error.value='读取失败，可直接粘贴题目。';}}
function save(){
  if(!draft.value)return;
  if(!draft.value.question.trim()||!draft.value.answer.trim()||!draft.value.explanation.trim()){error.value='请补齐题目、参考答案和解题过程。';return;}
  if(outcome.value!=='pass'){report.value=outcome.value==='mismatch'?'模板归类未通过：不能保存为当前模板实例。':outcome.value==='answer'?'参考解答未通过检查。':outcome.value==='invalid'?'题目条件不成立。':'题目条件尚不明确，暂不保存为可用题目。';return;}
  try{const candidates=[copy(draft.value),...copy(extraCandidates.value)],n=candidates.length;
    for(const q of candidates)saveQuestion(q);
    notice.value=`已保存 ${n} 道可用题目；题意、模板归类和参考解答按 mock 场景检查通过。`;dialog.value=null;query.value='';source.value='';page.value=1;
  }catch(e){error.value='未保存：'+(e as Error).message;}
}
function usage(q:Question){return flow.uses.filter(u=>u.question.id===q.id).length;}
function showUses(q:Question){open(q,'view');tab.value='uses';}
function methodName(id:string){return domainMock.methods.find(m=>m.id===id)?.name||id;}
</script>
<template><div class="task-instances">
  <div class="instance-tools"><label>搜索实例<input v-model="query" type="search" placeholder="题目或编号"/></label><label>来源<select aria-label="来源" v-model="source"><option value="">全部来源</option><option v-for="s in sources" :key="s">{{s}}</option></select></label><div class="button-row"><button class="btn" @click="create('管理员编写')">新建题目</button><button class="btn" @click="create('教材导入')">导入题目</button><button class="btn primary" @click="generate()">生成题目</button></div></div>
  <p v-if="notice" class="saved-note" role="status">{{notice}}</p>
  <section class="table-card table-scroll"><table class="data-table instance-table"><thead><tr><th>题目</th><th>关键参数</th><th>来源</th><th>使用记录</th><th>操作</th></tr></thead><tbody><tr v-for="q in rows.slice((page-1)*10,page*10)" :key="q.id"><td><button class="text-link question-link" @click="open(q,'view')">{{q.question}}</button><small>{{q.id}} · v{{q.version}}</small></td><td class="multiline">{{q.parameters||'未填写'}}</td><td>{{q.source}}</td><td><button class="text-link" @click="showUses(q)">{{usage(q)}} 次展示</button></td><td><button class="text-link" :aria-label="'编辑实例 '+q.id" @click="open(q,'edit')">编辑</button></td></tr></tbody></table><p v-if="!rows.length" class="empty">暂无匹配题目，可新建、导入或生成。</p></section>
  <div v-if="rows.length>10" class="pagination"><button class="btn" :disabled="page===1" @click="page--">上一页</button><span>{{page}} / {{Math.ceil(rows.length/10)}}</span><button class="btn" :disabled="page*10>=rows.length" @click="page++">下一页</button></div>
  <WorkbenchDialog v-if="dialog==='generate'" title="生成题目" @close="dialog=null"><p>所属任务：{{task.name}}</p><p v-if="parent">基于题目 {{parent}} 生成变式。</p><label>生成数量<input v-model.number="count" type="number" min="1" max="10"/></label><label>补充要求（可选）<textarea v-model="request" rows="3"/></label><p class="muted">使用当前模板的条件与允许变化。本轮为固定 mock 生成，不调用模型理解补充要求。</p><p v-if="error" role="alert" class="callout amber">{{error}}</p><button class="btn primary" @click="generated">生成候选题</button></WorkbenchDialog>
  <WorkbenchDialog v-else-if="dialog&&draft" :title="dialog==='view'?'题目详情':draft.id?'编辑题目':'准备题目'" wide @close="dialog=null">
    <p class="muted">{{task.name}} · {{draft.id||'候选题'}}{{draft.id?' · v'+draft.version:''}}</p>
    <template v-if="dialog==='view'">
      <div class="tabs" role="tablist" aria-label="题目详情"><button v-for="(label,key) in {content:'题目与解答',source:'来源与检查',uses:'使用记录'}" :key="key" role="tab" :aria-selected="tab===key" :class="{active:tab===key}" @click="tab=key">{{label}}</button></div>
      <template v-if="tab==='content'"><p class="instance-question">{{draft.question}}</p>
      <svg v-if="draft.figure==='triangle'" class="example-figure" viewBox="0 0 320 200" role="img" aria-label="三角形示意图：底12厘米，对应高7厘米"><polygon points="35,150 275,150 115,30" fill="#ecf5ef" stroke="#3f7258" stroke-width="2"/><path d="M115 30V150 M115 138H127V150" fill="none" stroke="#547b9b" stroke-width="1.5" stroke-dasharray="4 3"/><g fill="#314e41" font-size="13"><text x="20" y="169">A</text><text x="277" y="169">B</text><text x="108" y="21">C</text><text x="108" y="169">H</text><text x="142" y="190">12 厘米</text><text x="125" y="93">7 厘米</text></g></svg><svg v-else-if="draft.figure==='garden'" class="example-figure" viewBox="0 0 340 215" role="img" aria-label="长方形花园和角落的三角形花坛示意图"><rect x="45" y="35" width="250" height="150" fill="#eef6ee" stroke="#3f7258" stroke-width="2"/><polygon points="45,35 170,35 45,110" fill="#eacfa4" stroke="#a68555" stroke-width="1.5"/><g fill="#314e41" font-size="12"><text x="143" y="205">20 米</text><text x="300" y="116">12米</text><text x="12" y="84">6米</text><text x="70" y="23">原8米，增加1/4</text><text x="68" y="64">花坛</text><text x="178" y="137">草坪</text></g></svg>
      <svg v-if="draft.figure==='length'" class="example-figure" viewBox="0 0 400 100" role="img" :aria-label="'原长'+draft.quantity+'米，新增部分为原长四分之一'"><rect x="20" y="25" width="280" height="30" fill="#bed8ca"/><rect x="300" y="25" width="70" height="30" fill="#efce8c"/><text x="80" y="80">原长 {{draft.quantity}} 米</text><text x="305" y="18">增加 1/4</text></svg>
      <dl class="field-list"><dt>参数对应</dt><dd>{{draft.parameters}}</dd><dt>参考答案</dt><dd>{{draft.answer}}</dd><dt>解题过程</dt><dd>{{draft.explanation}}</dd><dt>适用方法</dt><dd><button v-for="id in draft.methods||task.methods" :key="id" class="text-link owner-link" @click="go('domain',{domain:task.domainId,filter:'solution',id,returnTo:location.hash})">{{methodName(id)}} ↗</button></dd></dl><div class="button-row"><button class="btn" @click="generate(draft)">生成变式</button><button class="btn primary" @click="dialog='edit'">编辑题目</button></div></template>
      <dl v-else-if="tab==='source'" class="field-list"><dt>来源</dt><dd>{{draft.source}} · {{draft.sourceNote}}</dd><dt>来源题</dt><dd>{{draft.parentId||'无'}}</dd><dt>变化</dt><dd>{{draft.variation||'未声明变化；不能自动认定迁移'}}</dd><dt>保存检查</dt><dd>题意、模板归类、参考解答：mock 通过。{{draft.checkedAt}}</dd></dl>
      <template v-else><p class="muted">按实际展示计次；生成但未展示不计次。例题不等于学生作答。</p><div class="table-scroll"><table class="data-table use-table"><thead><tr><th>时间 / 空间</th><th>用途</th><th>作答情况</th><th></th></tr></thead><tbody><tr v-for="u in uses" :key="u.id"><td>{{u.at}}<small>学生 A · {{flow.spaces.find(s=>s.id===u.spaceId)?.name}}</small></td><td>{{u.purpose}}<small>v{{u.question.version}}</small></td><td>{{u.purpose==='讲解'?'未要求作答':u.answer?u.result:'未提交'}}<small>{{u.answer}}</small></td><td><button class="text-link" @click="go('activity',{id:u.activityId,returnTo:location.hash})">查看过程 →</button></td></tr></tbody></table></div><p v-if="!uses.length" class="empty">尚无使用记录。</p></template>
    </template>
    <form v-else @submit.prevent="save"><label v-if="draft.source==='教材导入'&&!draft.id">文本文件<input type="file" accept=".txt,text/plain" @change="importFile"/></label><label>题目内容<textarea v-model="draft.question" rows="4"/></label><div class="field-pair"><label>参数对应<textarea v-model="draft.parameters" rows="3"/></label><label>参考答案<textarea v-model="draft.answer" rows="3"/></label></div><label>解题过程<textarea v-model="draft.explanation" rows="3"/></label><label>来源说明<input v-model="draft.sourceNote"/></label>
      <section v-if="extraCandidates.length" class="batch-preview"><h3>另 {{extraCandidates.length}} 道候选题</h3><article v-for="(q,i) in extraCandidates" :key="i"><strong>第 {{i+2}} 题 · {{q.question}}</strong><p>{{q.parameters}}</p><p>参考答案：{{q.answer}}</p><p>{{q.explanation}}</p></article><p class="muted">以上题目与当前题目一起检查并保存；保存后可逐题编辑。</p></section>
      <details class="mock-controls"><summary>Mock 检查场景</summary><label>模拟检查结果<select aria-label="模拟检查结果" v-model="outcome"><option value="pass">检查通过</option><option value="mismatch">不匹配当前模板</option><option value="invalid">题目条件不成立</option><option value="answer">参考答案错误</option><option value="uncertain">信息不足</option></select></label></details>
      <p v-if="error||report" role="alert" class="callout amber">{{error||report}} 输入已保留。</p><p class="muted">已使用题目的修改保存为新版，旧作答仍保留原题。所有检查结果均为 mock。</p><div class="dialog-footer button-row"><button type="button" class="btn" @click="dialog=null">取消</button><button class="btn primary" type="submit">检查并保存</button></div>
    </form>
  </WorkbenchDialog>
</div></template>
<style scoped>
.batch-preview article{border-top:1px solid #e3ebe6;padding:12px 0}.batch-preview p{white-space:pre-line}
.instance-tools{display:flex;gap:14px;align-items:end;flex-wrap:wrap;margin-bottom:16px}.instance-tools label{margin:0;flex:1}.instance-tools .button-row{margin:0}.instance-table th:first-child{width:40%}.question-link{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;text-align:left;line-height:1.7}.multiline,.instance-question{white-space:pre-wrap}.instance-question{font-size:16px;line-height:1.8;margin:20px 0}.field-pair{display:grid;grid-template-columns:1fr 1fr;gap:16px}.table-scroll{overflow:auto}.instance-table{min-width:660px}.use-table{min-width:570px}.example-figure{display:block;max-width:400px;margin:16px auto}.mock-controls{margin:16px 0;padding:12px;background:#f5f7f6}.saved-note{color:#2d6a4f}.owner-link{margin-right:12px}
</style>
