<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import type { ImportDraft } from '../model/imports';
import { domainData, domainStorageError, clone, collectKnowledge, type Kind, type Task, type Method, type Knowledge, type Instance } from '../model/domain';
import { proposalSlots, canPropose, generatedSolution, saveExtractedInstances, objectKinds, objectRows, findObject, objectName, isReviewed, confirmSemantic, candidate, saveCandidate, mappingIssues, mappingReady, mappingSignature, saveMapping, type ObjectKind, type SemanticEntry, type ExtractedSolution } from '../model/material-integration';
import { recordBookChange } from '../model/textbook';
import WorkbenchDialog from './WorkbenchDialog.vue';
import TaskWorkspace from './domain/TaskWorkspace.vue';
import MethodWorkspace from './domain/MethodWorkspace.vue';
import KnowledgeWorkspace from './domain/KnowledgeWorkspace.vue';
import TaskInstances from './domain/TaskInstances.vue';
import ExtractedMaterial from './ExtractedMaterial.vue';

const props=defineProps<{draft:ImportDraft;mode:'semantic'|'fusion'|'application'}>();
const emit=defineEmits<{source:[entry:SemanticEntry];stage:[value:'semantic'|'fusion'|'application']}>();
const integration=computed(()=>props.draft.integration!),book=computed(()=>props.draft.book);
const entry=computed(()=>integration.value.entries.find(e=>e.id===integration.value.selected)||integration.value.entries[0]);
const chapters=computed(()=>book.value.units.flatMap(u=>u.chapters));
const chapterName=(id:string)=>chapters.value.find(c=>c.id===id)?.name||'';
const methodNames=(ids:string[],separator=' → ')=>ids.map(id=>domainData.methods.find(m=>m.id===id)?.name||id).join(separator);
const error=ref(''),notice=ref(''),query=ref('');
const picker=ref<{slot:string;kind:ObjectKind}|null>(null),picked=ref('');
const editor=ref<{kind:ObjectKind;id:string;slot:string;initial?:Task|Method|Knowledge|Instance;tab:string}|null>(null);
watch(()=>props.mode,()=>{editor.value=null;error.value='';notice.value='';});
const options=computed(()=>picker.value?objectRows(picker.value.kind).filter(o=>o.domainId===book.value.domainId&&(objectName(o)+' '+o.id).includes(query.value)):[]);
const preview=computed(()=>picker.value?findObject(picker.value.kind,picked.value,book.value.domainId):undefined);
const availableSlots=computed(()=>proposalSlots(entry.value));
const selectedTask=computed(()=>domainData.tasks.find(t=>t.id===entry.value.bindings.task?.id&&t.domainId===book.value.domainId));
const methods=computed(()=>domainData.methods.filter(m=>m.domainId===book.value.domainId&&selectedTask.value?.methods.includes(m.id)));
const kc=computed(()=>collectKnowledge(entry.value.selectedMethods,book.value.domainId));
const applicationEditor=ref(false),goal=ref(''),claim=ref(''),teaching=ref(''),requirements=ref('');
const config=ref<{goal:string;claim:string;teaching:string;requirements:string}|null>(null);
const outcome=ref('pass');
const generator=ref(false),generatingMethod=ref(''),generated=ref<ExtractedSolution|null>(null),generationError=ref(''),generationOutcome=ref('pass');
function select(id:string){integration.value.selected=id;editor.value=null;error.value='';notice.value='';config.value=null;}
function extractedChanged(sourceChanged:boolean){if(sourceChanged)entry.value.reviewed='';entry.value.mapped='';config.value=null;notice.value='提取内容已保存。来源内容改变后需重新核对，已保存的公共对象不会自动改写。';recordBookChange(book.value,'修改教材提取：'+entry.value.title);}
function confirm(){error.value=confirmSemantic(book.value,entry.value).join('；');if(!error.value)notice.value='本项语义内容已核对，可以进入模板匹配。';}
function choose(slot:string,kind:ObjectKind){picker.value={slot,kind};picked.value=entry.value.bindings[slot]?.id||'';query.value='';error.value='';}
function useExisting(){
  if(!preview.value||!picker.value)return;
  const {slot}=picker.value;entry.value.bindings[slot]={id:preview.value.id,mode:'reuse'};entry.value.mapped='';
  if(slot==='task')entry.value.selectedMethods=entry.value.selectedMethods.filter(id=>(preview.value as Task).methods.includes(id));
  picker.value=null;notice.value='已选择复用对象，公共定义未改写。请继续核对方法、题目与章节映射。';
}
function openObject(kind:Kind,id:string,tab='definition'){editor.value={kind,id,slot:'',tab};}
function openSlot(slot:string,kind:ObjectKind){const id=entry.value.bindings[slot]?.id;if(id)editor.value={kind,id,slot,tab:'definition'};}
function createSlot(slot:string,kind:ObjectKind){
  if(kind==='instance'&&!selectedTask.value){error.value='请先关联任务模板，再准备具体题目。';return;}
  editor.value={kind,id:'new',slot,tab:'definition',initial:candidate(book.value,entry.value,slot)};error.value='';
}
function savedObject(id:string){
  if(editor.value?.slot){entry.value.bindings[editor.value.slot]={id,mode:editor.value.initial?'new':'reuse'};entry.value.mapped='';}
  editor.value=null;notice.value='对象已保存到当前领域。教材映射尚需核对并保存。';
}
const editorTask=computed(()=>editor.value?.initial&&editor.value.kind==='instance'?domainData.tasks.find(t=>t.id===(editor.value!.initial as Instance).taskId):editor.value?.kind==='instance'?domainData.tasks.find(t=>t.id===(findObject('instance',editor.value!.id,book.value.domainId) as Instance)?.taskId):undefined);
function createMissing(){
  if(!isReviewed(book.value,entry.value)){error.value='请先核对本项语义内容。';return;}
  if(outcome.value!=='pass'){error.value='模拟检查未通过：候选归类或解答需要修正，本次未新建对象。';return;}
  try{
    for(const s of proposalSlots(entry.value))if(!findObject(s.kind,entry.value.bindings[s.key]?.id,book.value.domainId))saveCandidate(book.value,entry.value,s.key);
    entry.value.selectedMethods=[...(selectedTask.value?.methods||[])];
    notice.value='缺少的模板和知识已补齐；没有自动生成解法或保存题目实例。已有对象未覆盖。';error.value='';
  }catch(e){error.value='部分定义已保存；题目仍待检查：'+String(e);}
}
function saveInstances(checked:boolean){if(checked&&outcome.value!=='pass'){error.value='模拟归类或解答检查未通过，未保存为可用实例。';return;}error.value=saveExtractedInstances(book.value,entry.value,checked).join('；');if(!error.value)notice.value=checked?'题目与具体解法已保存（mock），来源分别保留。':'题目实例草稿已保存；缺少解法或检查时仍不可用于教学、检测。';}
function openGenerator(){generator.value=true;generatingMethod.value=methods.value[0]?.id||'';generated.value=null;generationError.value='';generationOutcome.value='pass';}
function generate(){try{generated.value=generatedSolution(book.value,entry.value,generatingMethod.value);generationError.value='';}catch(err){generated.value=null;generationError.value=String(err);}}
function adoptGenerated(){
  if(!generated.value)return;
  if(generationOutcome.value!=='pass'){generationError.value='模拟检查不通过，候选未采用，也未写入教材原有解法。';return;}
  if(!generated.value.working.trim()||!generated.value.result.trim()){generationError.value='请补齐具体步骤与结果。';return;}
  const list=entry.value.solutionInstances!;
  if(!list.some(s=>s.origin==='系统生成'&&s.key===generated.value!.key&&s.working===generated.value!.working))list.push(clone(generated.value));
  entry.value.mapped='';generator.value=false;notice.value='已采用系统生成的参考解法（mock），教材原有解法保持原样。请重新检查并保存实例。';
}
function save(){error.value=saveMapping(book.value,entry.value).join('；');if(!error.value)notice.value='本项教材映射已保存。其他内容的缺口仍单独保留。';}
function prepareApplication(){
  const previous=integration.value.applications.find(a=>a.entryId===entry.value.id);
  goal.value=previous?.goal||'';claim.value=previous?.claim||'';teaching.value=previous?.teaching||'';requirements.value=previous?.requirements||'';applicationEditor.value=true;
}
function sampleConfig(){goal.value='演示目标：'+(selectedTask.value?.goal||entry.value.title);claim.value='当前 Task 的 Task Claim（四方面，mock）';teaching.value='分段讲解 → 提问与练习 → 检测反馈（mock）';requirements.value='独立求解：无当题提示完成当前任务。理解与解释：说明所用方法与知识依据。迁移：在新条件下完成相应任务。持久：另行安排延迟检测。本配置仅演示关联方式，具体门槛待课程准备时确认。';}
function configure(){
  if(!goal.value.trim()||!claim.value||!teaching.value||!requirements.value.trim()){error.value='请补齐目标、Task Claim、要求说明和教学配置。';return;}
  config.value={goal:goal.value,claim:claim.value,teaching:teaching.value,requirements:requirements.value};applicationEditor.value=false;error.value='';
}
function apply(){
  if(!mappingReady(book.value,entry.value)){error.value='本项模型映射尚未就绪，请回到模板匹配处理。';return;}
  if(!config.value){error.value='请先准备本项教学与评价的演示配置。';return;}
  integration.value.applications=integration.value.applications.filter(a=>a.entryId!==entry.value.id);
  integration.value.applications.push({entryId:entry.value.id,at:new Date().toLocaleString('zh-CN'),signature:mappingSignature(book.value,entry.value),...config.value});
  recordBookChange(book.value,'模拟应用本项内容：'+entry.value.title);notice.value='本项已模拟应用；其余内容仍待准备。没有生成学生状态，也没有连接真实教学服务。';error.value='';
}
const applied=computed(()=>integration.value.applications.find(a=>a.entryId===entry.value.id));
const appliedCurrent=computed(()=>applied.value?.signature===mappingSignature(book.value,entry.value)&&mappingReady(book.value,entry.value));
function rowState(e:SemanticEntry){return !isReviewed(book.value,e)?'提取待核对':e.knowledgeOnly?(e.knowledgeItems?.every(k=>findObject('kc',e.bindings[k.key]?.id,book.value.domainId))?'KC 已归入领域':'KC 待匹配'):mappingReady(book.value,e)?'映射就绪':'模板／实例待准备';}
</script>
<template><section class="integration-workspace">
  <p v-if="error" class="callout danger" role="alert">{{error}}</p><p v-if="notice" class="saved-note" role="status">{{notice}}</p>
  <p v-if="domainStorageError" class="callout danger" role="alert">{{domainStorageError}}</p><p v-if="integration.notice" class="callout">{{integration.notice}} <button class="text-link" @click="integration.notice=''">知道了</button></p>
  <div v-if="entry" class="integration-layout">
    <aside class="panel integration-tree"><h3>章节与内容</h3><section v-for="ch in chapters" :key="ch.id"><h4>{{ch.name}}</h4><button v-for="e in integration.entries.filter(e=>e.chapterId===ch.id)" :key="e.id" class="integration-entry" :class="{active:e.id===entry.id}" @click="select(e.id)"><strong>{{e.title}}</strong><small>{{rowState(e)}}</small></button></section></aside>
    <div class="integration-main">
      <header class="panel row-between"><div><h3>{{entry.title}}</h3><p class="muted">{{chapterName(entry.chapterId)}} · 原书 {{entry.pages.join('、')}} 页</p></div><button class="btn" @click="emit('source',entry)">查看原页并核对</button></header>
      <template v-if="editor">
        <div class="callout"><button class="text-link" @click="editor=null">← 返回本项融合</button><p>领域：{{domainData.domains.find(d=>d.id===book.domainId)?.name}}。这里使用领域管理的同一套编辑页面；保存后保留教材上下文。已有对象是公共定义。</p></div>
        <TaskWorkspace v-if="editor.kind==='task'" :key="editor.id+editor.slot" :domain-id="book.domainId" :object-id="editor.id" :tab="editor.tab" :initial="editor.initial as Task|undefined" @saved="savedObject" @open="openObject" @back="editor=null"/>
        <MethodWorkspace v-else-if="editor.kind==='solution'" :key="editor.id+editor.slot" :domain-id="book.domainId" :object-id="editor.id" :initial="editor.initial as Method|undefined" @saved="savedObject" @open="openObject" @back="editor=null"/>
        <KnowledgeWorkspace v-else-if="editor.kind==='kc'" :key="editor.id+editor.slot" :domain-id="book.domainId" :object-id="editor.id" :initial="editor.initial as Knowledge|undefined" @saved="savedObject" @open="openObject" @back="editor=null"/>
        <TaskInstances v-else-if="editorTask" :key="editor.id+editor.slot" :task="editorTask" :initial="(editor.initial||findObject('instance',editor.id,book.domainId)) as Instance" @saved="savedObject" @open="openObject"/>
      </template>
      <template v-else-if="mode==='semantic'">
        <ExtractedMaterial :book="book" :entry="entry" @changed="extractedChanged"/>
        <footer class="row-between"><span class="badge">{{isReviewed(book,entry)?'本项提取已核对':'本项提取待核对'}}</span><div class="button-row"><button class="btn" @click="confirm">确认本项提取结果</button><button class="btn primary" :disabled="!isReviewed(book,entry)" @click="emit('stage','fusion')">匹配或补建模板</button></div></footer>
      </template>
      <template v-else-if="mode==='fusion'">
        <p v-if="!isReviewed(book,entry)" class="callout amber">本项内容尚未核对或已经变化。<button class="text-link" @click="emit('stage','semantic')">返回内容提取</button></p>
        <section class="panel"><div class="row-between"><h3>匹配或补建领域定义</h3><button v-if="canPropose(entry)" class="btn" :disabled="!isReviewed(book,entry)||!!domainStorageError" @click="createMissing">补齐缺少的模板与知识（mock）</button></div><p class="muted">本步根据已提取的具体内容，匹配已有定义或提出新定义。模板建议为 mock；创建模板不会凭空增加教材中的解法。</p>
          <p v-if="!canPropose(entry)" class="callout">此内容尚未预写完整建模候选。可以选择当前领域的对象；缺少的定义从领域管理手动补充，不能把整章标成已完成。</p>
          <div class="table-scroll"><table class="data-table fusion-table" aria-label="领域对象匹配"><thead><tr><th>具体内容／模板建议</th><th>领域对象／处理方式</th><th>操作</th></tr></thead><tbody><tr v-for="s in availableSlots" :key="s.key"><td><template v-if="s.kind==='task'">TaskInstance → TaskTemplate<small>{{entry.taskInstance?.id}}</small></template><template v-else-if="s.kind==='solution'">SolutionTemplate<small v-for="si in (entry.solutionInstances||[]).filter(x=>x.key===s.key)" :key="si.id">{{si.origin}} · {{si.id}}</small><small v-if="!(entry.solutionInstances||[]).some(x=>x.key===s.key)">系统建议的方法；尚未生成具体解法</small></template><template v-else>KC<small>{{entry.knowledgeItems?.some(k=>k.key===s.key)?'来自知识提取':'方法建模所需的补充知识'}}</small></template><small>{{s.name}}</small></td><td>{{objectName(findObject(s.kind,entry.bindings[s.key]?.id,book.domainId))}}<small v-if="entry.bindings[s.key]">{{entry.bindings[s.key].mode==='reuse'?'复用已有':'本次新增'}} · {{entry.bindings[s.key].id}}</small></td><td><div class="button-row"><button class="text-link" :aria-label="'选择已有 '+s.key" @click="choose(s.key,s.kind)">选择已有</button><button v-if="entry.bindings[s.key]" class="text-link" :aria-label="'查看对象 '+s.key" @click="openSlot(s.key,s.kind)">查看／编辑</button><button class="text-link" :aria-label="'新建对象 '+s.key" @click="createSlot(s.key,s.kind)">{{entry.bindings[s.key]?'另建候选':'新建候选'}}</button></div></td></tr></tbody></table></div>
          <details class="mock-tools"><summary>模拟候选检查</summary><label>候选检查结果<select aria-label="候选检查结果" v-model="outcome"><option value="pass">归类与解答通过（演示）</option><option value="fail">归类或解答不通过</option></select></label></details>
        </section>
        <section v-if="entry.taskInstance" class="panel"><div class="row-between"><h3>保存题目与具体解法</h3><button class="btn" :disabled="!selectedTask||!methods.length||!isReviewed(book,entry)" @click="openGenerator">补充参考解法（mock）</button></div>
          <p>TaskInstance：{{entry.taskInstance.id}}。当前有 {{entry.solutionInstances?.length||0}} 份 SolutionInstance。</p>
          <table v-if="entry.solutionInstances?.length" class="data-table" aria-label="实例与模板归属"><thead><tr><th>具体解法</th><th>来源</th><th>所用方法模板</th><th>结果</th></tr></thead><tbody><tr v-for="si in entry.solutionInstances" :key="si.id"><td>{{si.name}}<small>{{si.id}}</small></td><td>{{si.origin}}<small>{{si.sourceNote}}</small></td><td>{{objectName(findObject('solution',entry.bindings[si.key]?.id,book.domainId))}}</td><td>{{si.result}}</td></tr></tbody></table>
          <p v-else class="callout">只有题目，没有参考解法。可先保存题目草稿；需要用于教学或检测时，再补充并检查具体解法。</p>
          <div class="button-row"><button class="btn" :disabled="!selectedTask||!isReviewed(book,entry)" @click="saveInstances(false)">保存实例草稿</button><button class="btn primary" :disabled="!selectedTask||!isReviewed(book,entry)" @click="saveInstances(true)">检查并保存实例（mock）</button><button v-if="entry.bindings.question" class="text-link" @click="openSlot('question','instance')">查看已保存题目</button></div>
          <p class="muted">实例检查与模板匹配完成后，才可保存章节映射。生成解法不新增题目，也不改变题目来源。</p>
        </section>
        <p v-else class="callout">本项是纯知识说明。匹配或补建 KC 即可归入领域；课程使用仍需通过 Task 与 Solution 组织。</p>
        <section v-if="entry.taskInstance" class="panel"><h3>本教材采用的方法</h3><p class="muted">只选择本教材适用的方法；取消选择不会删除领域中的方法，也不会改写 Task 的全部方法集合。</p><label v-for="m in methods" :key="m.id" class="check-line"><input v-model="entry.selectedMethods" type="checkbox" :value="m.id" @change="entry.mapped=''"/>{{m.name}}<button class="text-link" @click="openObject('solution',m.id)">查看</button></label><p v-if="!methods.length" class="muted">先关联任务，或在任务定义中补齐适用方法。</p></section>
        <section v-if="entry.taskInstance" class="panel"><h3>由所选方法涉及的知识</h3><table v-if="kc.rows.length" class="data-table" aria-label="本教材汇总知识"><thead><tr><th>KC</th><th>来源方法路径</th></tr></thead><tbody><tr v-for="r in kc.rows" :key="r.knowledge.id"><td>{{r.knowledge.name}}</td><td><div v-for="(p,i) in r.paths" :key="i">{{methodNames(p)}}</div></td></tr></tbody></table><p v-else class="muted">尚未选择可汇总的方法。章节和 Task 均不直接关联 KC。</p></section>
        <footer class="row-between"><span class="muted">保存映射后仍需检查课程目标与教学条件。</span><div class="button-row"><button v-if="entry.taskInstance" class="btn" @click="save">保存本项映射</button><button class="btn primary" @click="emit('stage','application')">检查并应用</button></div></footer>
      </template>
      <template v-else>
        <section class="panel"><h3>章节内容准备情况</h3><table class="data-table" aria-label="章节映射清单"><thead><tr><th>内容</th><th>Task／本教材方法</th><th>准备情况</th></tr></thead><tbody><tr v-for="e in integration.entries.filter(e=>e.chapterId===entry.chapterId)" :key="e.id"><td><button class="text-link" @click="select(e.id)">{{e.title}}</button></td><td>{{objectName(findObject('task',e.bindings.task?.id,book.domainId))}}<small>{{methodNames(e.selectedMethods,'；')}}</small></td><td>{{rowState(e)}}</td></tr></tbody></table><p class="muted">本次只应用所选内容“{{entry.title}}”。其余内容和全册的准备要求保持不变。</p></section>
        <section class="panel"><h3>本项应用检查</h3><ul v-if="!mappingReady(book,entry)" class="callout amber"><li v-for="msg in mappingIssues(book,entry)" :key="msg">{{msg}}</li><li v-if="!mappingIssues(book,entry).length">映射尚未保存，或定义已有变化，请重新核对保存。</li></ul><p v-else class="saved-note">语义核对、Task、所选方法、KC 和题目引用已就绪。</p>
          <table class="data-table"><thead><tr><th>必要准备</th><th>当前选择</th></tr></thead><tbody><tr><td>学习目标及要求</td><td>{{config?.goal||applied?.goal||'尚未配置'}}</td></tr><tr><td>绑定当前 Task 的 Task Claim</td><td>{{config?.claim||applied?.claim||'尚未配置'}}</td></tr><tr><td>DeerMind 教学配置</td><td>{{config?.teaching||applied?.teaching||'尚未配置'}}</td></tr></tbody></table>
          <div class="button-row"><button class="btn" @click="prepareApplication">准备应用条件（mock）</button><button class="btn primary" :disabled="!mappingReady(book,entry)||!config" @click="apply">模拟应用本项内容</button></div>
          <p class="muted">此处演示目标、Claim 与教学配置的关联及缺项阻断。演示标准不是正式课程门槛；真实服务接入与课程验证仍需后续完成。</p>
        </section>
        <section v-if="applied" class="panel"><h3>{{appliedCurrent?'本项已模拟应用':'已有应用记录，当前修改尚未应用'}}</h3><p>教材：{{book.name}}；章节：{{chapterName(entry.chapterId)}}；可用内容：{{entry.title}}。</p><p>学生可选用该教材，并在这项内容范围内请求讲解、提问和测验；其他内容仍显示待准备。</p><p class="muted">这是学生可用范围的预览，不是已部署的学生端。应用不产生 Evidence 或 Belief。</p><p class="muted">{{applied.at}} · 保留目标与所用内容的应用记录。</p></section>
      </template>
    </div>
  </div><p v-else class="empty">没有可整理的内容，请返回检查原件。</p>
  <WorkbenchDialog v-if="generator" title="生成参考解法（mock）" wide @close="generator=false">
    <p>对应 TaskInstance：{{entry.taskInstance?.id}} · {{entry.title}}</p><p class="callout">这是系统补充的具体解法。题目原文、教材原有解法及其来源均保留。</p>
    <p v-if="generationError" class="callout danger" role="alert">{{generationError}}</p>
    <label>采用的方法模板<select aria-label="采用的方法模板" v-model="generatingMethod" @change="generated=null"><option v-for="m in methods" :key="m.id" :value="m.id">{{m.name}}</option></select></label><button class="btn" @click="generate">生成解法候选</button>
    <template v-if="generated"><p><span class="badge warning">系统生成</span> · {{generated.id}}</p><p class="muted">{{generated.sourceNote}}</p><label>生成的求解过程<textarea v-model="generated.working" rows="6"/></label><label>生成的结果<input v-model="generated.result"/></label><label>模拟解法检查<select aria-label="模拟解法检查" v-model="generationOutcome"><option value="pass">通过</option><option value="fail">不通过</option></select></label></template>
    <footer class="dialog-footer"><button class="btn" @click="generator=false">取消</button><button class="btn primary" :disabled="!generated" @click="adoptGenerated">检查并采用（mock）</button></footer>
  </WorkbenchDialog>
  <WorkbenchDialog v-if="picker" :title="'选择已有'+objectKinds[picker.kind]" wide @close="picker=null"><p class="muted">仅列出当前领域对象。请核对定义、适用范围与本教材内容；选择不会改写对象。</p><label>查找对象<input v-model="query"/></label><label>已有对象<select aria-label="已有对象" v-model="picked"><option value="">请选择</option><option v-for="o in options" :key="o.id" :value="o.id">{{objectName(o)}} · {{o.id}}</option></select></label><dl v-if="preview" class="field-list"><dt>名称／题目</dt><dd>{{objectName(preview)}}</dd><template v-if="'description' in preview"><dt>定义／思路</dt><dd>{{preview.description}}</dd><dt>适用条件</dt><dd>{{preview.conditions}}</dd></template><template v-if="'goal' in preview"><dt>任务目标</dt><dd>{{preview.goal}}</dd><dt>条件与关系</dt><dd>{{preview.relations}}</dd><dt>边界</dt><dd>{{preview.exclusions}}</dd></template><template v-if="'answer' in preview"><dt>参考答案</dt><dd>{{preview.answer}}</dd><dt>来源</dt><dd>{{preview.sourceNote}}</dd></template></dl><p v-if="!options.length" class="empty">当前领域没有匹配列表项，可以返回新建。</p><div class="dialog-footer"><button class="btn" @click="picker=null">取消</button><button class="btn primary" :disabled="!preview" @click="useExisting">复用所选对象</button></div></WorkbenchDialog>
  <WorkbenchDialog v-if="applicationEditor" title="准备应用条件（mock）" wide @close="applicationEditor=false"><p class="muted">仅为本项内容演示关联方式，不创建学生判断。当前 Task：{{selectedTask?.name||'尚未关联'}}。</p><button class="btn" @click="sampleConfig">载入演示配置</button><label>学习目标<input v-model="goal"/></label><label>Task Claim<select v-model="claim"><option value="">请选择</option><option>当前 Task 的 Task Claim（四方面，mock）</option></select></label><label>学习要求与标准说明<textarea v-model="requirements" rows="4"/></label><label>教学配置<select v-model="teaching"><option value="">请选择</option><option>分段讲解 → 提问与练习 → 检测反馈（mock）</option></select></label><div class="dialog-footer"><button class="btn" @click="applicationEditor=false">取消</button><button class="btn primary" @click="configure">采用演示配置</button></div></WorkbenchDialog>
</section></template>
<style scoped>
.integration-layout{display:grid;grid-template-columns:220px minmax(0,1fr);gap:18px;align-items:start}.integration-tree{position:sticky;top:10px;max-height:80vh;overflow:auto;padding:16px}.integration-tree h4{font-size:12px;color:#738578;margin-top:24px}.integration-entry{display:block;width:100%;border:0;border-left:3px solid transparent;background:none;text-align:left;padding:12px 9px;color:#405a4c;border-radius:4px}.integration-entry.active{background:#edf5ef;border-color:#2d6a4f}.integration-entry strong{font-size:13px;font-weight:500}.integration-entry small{display:block;color:#829186;font-size:11px;margin-top:4px}.integration-main{min-width:0}.fusion-table .button-row{flex-wrap:wrap;min-width:130px}.semantic-ratio{display:flex;flex-wrap:wrap;align-items:center;justify-content:center;gap:12px;margin:24px 0}.semantic-ratio>div{padding:14px;border:1px solid #bad1c2;background:#f4f9f6;border-radius:6px;min-width:110px;text-align:center}.semantic-ratio strong,.semantic-ratio div span{display:block}.semantic-ratio div span{font-size:12px;color:#75887c}.semantic-ratio figcaption{flex-basis:100%;font-size:12px;color:#75887c;text-align:center}.ratio-arrow{color:#2d6a4f} @media(max-width:1150px){.integration-layout{grid-template-columns:180px minmax(0,1fr);gap:12px}.integration-tree{padding:12px}.integration-main .field-list{grid-template-columns:95px minmax(0,1fr)}}
</style>
