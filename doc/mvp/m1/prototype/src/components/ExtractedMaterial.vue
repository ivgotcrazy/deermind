<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { clone, id } from '../model/domain';
import { objectName, findObject, type SemanticEntry, type ExtractedKC, type ExtractedSolution } from '../model/material-integration';
import type { MockTextbook } from '../model/textbook';
import ContentVisuals from './ContentVisuals.vue';
import ContentVisualEditor from './ContentVisualEditor.vue';
import type { ContentVisual } from '../model/content-visuals';
import WorkbenchDialog from './WorkbenchDialog.vue';
const props=defineProps<{book:MockTextbook;entry:SemanticEntry}>();
const emit=defineEmits<{changed:[sourceChanged:boolean]}>();
const preview=ref(false),visualEditor=ref<{value?:ContentVisual;owner:string}|null>(null);
const tab=ref('task'),taskEditor=ref<SemanticEntry|null>(null),knowledgeEditor=ref<ExtractedKC|null>(null),solutionEditor=ref<ExtractedSolution|null>(null),error=ref('');
watch(()=>props.entry.id,()=>{tab.value=props.entry.knowledgeOnly?'kc':'task';error.value='';},{immediate:true});
const knowledge=computed(()=>props.entry.knowledgeItems||[]),solutions=computed(()=>props.entry.solutionInstances||[]);
const textbookCount=computed(()=>solutions.value.filter(s=>s.origin==='教材原有').length);
function editTask(){taskEditor.value=clone(props.entry);error.value='';}
function saveTask(){
  const value=taskEditor.value!;if(!value.conditions.trim()||!value.question.trim()){error.value='请补齐题目的条件与作答要求。';return;}
  const {title,conditions,question,answer,taskInstance}=value;
  Object.assign(props.entry,{title,conditions,question,answer,taskInstance});
  taskEditor.value=null;emit('changed',true);
}
function editKnowledge(value?:ExtractedKC){knowledgeEditor.value=value?clone(value):{id:id('KC-C'),key:id('kc'),name:'',meaning:'',sourceNote:'教材第'+props.entry.pages.join('、')+'页；请补充具体出处。'};error.value='';}
function saveKnowledge(){const value=knowledgeEditor.value!;if(!value.name.trim()||!value.meaning.trim()||!value.sourceNote.trim()){error.value='请填写知识名称、含义和出处。';return;}const i=knowledge.value.findIndex(x=>x.id===value.id);if(i<0)props.entry.knowledgeItems!.push(value);else props.entry.knowledgeItems![i]=value;knowledgeEditor.value=null;emit('changed',true);}
function editSolution(value?:ExtractedSolution){solutionEditor.value=value?clone(value):{id:id('SI'),taskInstanceId:props.entry.taskInstance!.id,key:id('method'),name:'',working:'',result:'',origin:'教材原有',sourceNote:'教材第'+props.entry.pages.join('、')+'页；请补充具体出处。'};error.value='';}
function saveSolution(){
  const value=solutionEditor.value!;if(!value.name.trim()||!value.working.trim()||!value.result.trim()||!value.sourceNote.trim()||value.origin==='来源待确认'){error.value='请填写名称、具体步骤、结果，并核对来源。';return;}
  const i=solutions.value.findIndex(x=>x.id===value.id),wasSource=i>=0&&solutions.value[i].origin!=='系统生成';
  if(i<0)props.entry.solutionInstances!.push(value);else props.entry.solutionInstances![i]=value;
  solutionEditor.value=null;emit('changed',wasSource||value.origin!=='系统生成');
}
const owners=computed(()=>[
  ...(props.entry.taskInstance?[{id:'task',name:'TaskInstance · 原题题面'}]:[]),
  ...(props.entry.solutionInstances||[]).map(s=>({id:s.id,name:'SolutionInstance · '+s.name})),
  ...(props.entry.knowledgeItems||[]).map(k=>({id:k.id,name:'KC · '+k.name})),
  {id:'teaching',name:'教学辅助展示 · 不进入原题'},
]);
function visuals(owner:string):ContentVisual[]{
  if(owner==='task')return props.entry.taskInstance!.visuals??=[];
  if(owner==='teaching')return props.entry.teachingVisuals??=[];
  if(owner==='pending')return props.entry.pendingVisuals??=[];
  const object=props.entry.solutionInstances?.find(s=>s.id===owner)||props.entry.knowledgeItems?.find(k=>k.id===owner);
  return object?object.visuals??=[]:[];
}
function removeVisual(owner:string,key:string){const list=visuals(owner),i=list.findIndex(v=>v.id===key);if(i>=0)list.splice(i,1);emit('changed',owner!=='teaching');}
function saveVisual(value:ContentVisual,owner:string){
  const previous=visualEditor.value!;
  if(previous.value){const list=visuals(previous.owner),i=list.findIndex(v=>v.id===previous.value!.id);if(i>=0)list.splice(i,1);}
  visuals(owner).push(value);visualEditor.value=null;emit('changed',owner!=='teaching'||previous.owner!=='teaching');
}
function templateName(s:ExtractedSolution){return objectName(findObject('solution',props.entry.bindings[s.key]?.id,props.book.domainId));}
</script>
<template><section class="extracted-material">
  <section class="panel"><h3>教材提取结果</h3><p class="muted">先核对教材实际包含的知识、题目和具体解法。模板在下一步匹配或补建；当前内容可在空领域中保留。</p>
    <nav class="object-tabs" aria-label="提取对象类型"><button :class="{active:tab==='kc'}" @click="tab='kc'">知识 KC（{{knowledge.length}}）</button><button :class="{active:tab==='task'}" @click="tab='task'">题目 TaskInstance（{{entry.taskInstance?1:0}}）</button><button :class="{active:tab==='solution'}" @click="tab='solution'">解法 SolutionInstance（{{solutions.length}}）</button></nav>
    <template v-if="tab==='kc'"><div class="row-between"><h3>知识候选</h3><button class="btn" @click="editKnowledge()">补充漏识别知识</button></div>
      <table v-if="knowledge.length" class="data-table" aria-label="提取的KC"><thead><tr><th>名称与含义</th><th>出处与提取说明</th><th>操作</th></tr></thead><tbody><tr v-for="k in knowledge" :key="k.id"><td><strong>{{k.name}}</strong><p>{{k.meaning}}</p><small>{{k.id}}</small><details class="owned-visuals"><summary>知识图表（{{k.visuals?.length||0}}）</summary><ContentVisuals :items="k.visuals" editing metadata @edit="value=>visualEditor={value,owner:k.id}" @remove="key=>removeVisual(k.id,key)"/><button class="btn" :aria-label="'添加知识图表 '+k.name" @click="visualEditor={owner:k.id}">添加知识图表</button></details></td><td>{{k.sourceNote}}</td><td><button class="text-link" :aria-label="'编辑提取知识 '+k.key" @click="editKnowledge(k)">核对／编辑</button></td></tr></tbody></table><p v-else class="empty">本项尚未提取独立知识表述。解题需要的知识可在后续方法建模时补齐。</p><p class="muted">出处用于追溯；课程所需 KC 仍通过 Task → Solution 汇总。</p>
    </template>
    <template v-else-if="tab==='task'">
      <template v-if="entry.taskInstance"><div class="row-between"><h3>{{entry.taskInstance.kind}}</h3><button class="btn" @click="editTask">编辑题目提取</button></div><p class="object-type">{{entry.taskInstance.id}}</p><dl class="field-list"><dt>已知条件／背景</dt><dd>{{entry.conditions||'尚待提取'}}</dd><dt>作答要求</dt><dd>{{entry.question||'尚待提取'}}</dd><dt>教材给出的答案</dt><dd>{{entry.answer||'未提供／尚未提取。题目可以先保留，不自动编造解法。'}}</dd><dt>TaskTemplate</dt><dd>{{objectName(findObject('task',entry.bindings.task?.id,book.domainId))}}</dd></dl><section aria-label="题面内容"><div class="row-between"><h3>题面图表</h3><div class="button-row"><button class="btn" @click="visualEditor={owner:'task'}">添加题面图表</button><button class="btn" @click="preview=true">预览原题</button></div></div><p class="muted">只包含题目给定的条件和作答对象；额外的分析图、辅助线与求解过程放入解法或教学展示。</p><ContentVisuals :items="entry.taskInstance.visuals" editing metadata @edit="value=>visualEditor={value,owner:'task'}" @remove="key=>removeVisual('task',key)"/><p v-if="entry.taskInstance.visuals?.some(v=>v.kind==='description')" class="callout amber">题面必要图形尚待补绘。统计图的数据、单位和图例仍需核对补齐。当前不能把图形说明当作完整题面使用。</p><p v-if="!entry.taskInstance.visuals?.length" class="muted">本题暂无单独的题面图表。</p></section><p class="muted">题面与参考解法分别保存；教材只给出答案时，也不能当成已有完整解法。</p></template>
      <p v-else class="empty">这是一条知识说明，没有题目实例。无需虚构题目才能提取 KC。</p>
    </template>
    <template v-else><div class="row-between"><h3>本题的具体解法</h3><button v-if="entry.taskInstance" class="btn" @click="editSolution()">补充漏识别教材解法</button></div><p class="muted">教材原有 {{textbookCount}} 份；系统生成 {{solutions.filter(s=>s.origin==='系统生成').length}} 份；来源待确认 {{solutions.filter(s=>s.origin==='来源待确认').length}} 份。</p>
      <table v-if="solutions.length" class="data-table" aria-label="提取的SolutionInstance"><thead><tr><th>解法实例</th><th>来源</th><th>SolutionTemplate</th><th>操作</th></tr></thead><tbody><tr v-for="s in solutions" :key="s.id" :data-solution-id="s.id"><td>{{s.name}}<small>{{s.id}}</small><details class="owned-visuals"><summary>解法图表（{{s.visuals?.length||0}}）</summary><ContentVisuals :items="s.visuals" editing metadata @edit="value=>visualEditor={value,owner:s.id}" @remove="key=>removeVisual(s.id,key)"/><button class="btn" :aria-label="'添加解法图表 '+s.name" @click="visualEditor={owner:s.id}">添加解法图表</button></details></td><td><span class="badge" :class="{warning:s.origin!=='教材原有'}">{{s.origin}}</span><small>{{s.sourceNote}}</small></td><td>{{templateName(s)}}</td><td><button class="text-link" :aria-label="'核对解法 '+s.id" @click="editSolution(s)">查看／核对</button></td></tr></tbody></table>
      <p v-else class="empty">当前内容没有提取到解法。需要参考解法时，先在下一步选择适用模板，再单独生成并检查。</p>
    </template>
  </section>
  <details class="panel teaching-visuals"><summary>教学辅助展示（{{entry.teachingVisuals?.length||0}}）</summary><p class="muted">这些内容供讲解时按需使用，不属于原题、教材原有解法或知识定义，也不自动出现在学生作答前。</p><ContentVisuals :items="entry.teachingVisuals" editing metadata @edit="value=>visualEditor={value,owner:'teaching'}" @remove="key=>removeVisual('teaching',key)"/><button class="btn" @click="visualEditor={owner:'teaching'}">添加教学辅助图</button></details>
  <section v-if="entry.pendingVisuals?.length" class="callout amber"><h3>旧稿图表待核对归属</h3><p>原内容仍保留。请编辑图表选择所属内容；未确认前不进入原题。</p><ContentVisuals :items="entry.pendingVisuals" editing metadata @edit="value=>visualEditor={value,owner:'pending'}" @remove="key=>removeVisual('pending',key)"/></section>
  <WorkbenchDialog v-if="preview&&entry.taskInstance" title="学生看到的原题" wide @close="preview=false"><section data-testid="extracted-task-preview"><p class="multiline">{{entry.conditions}}</p><p class="multiline">{{entry.question}}</p><ContentVisuals :items="entry.taskInstance.visuals"/></section><footer class="dialog-footer"><button class="btn" @click="preview=false">关闭预览</button></footer></WorkbenchDialog>
  <WorkbenchDialog v-if="taskEditor" title="核对题目实例" wide @close="taskEditor=null"><p v-if="error" role="alert" class="callout danger">{{error}}</p><label>内容标题<input v-model="taskEditor.title"/></label><label>已知条件／背景<textarea v-model="taskEditor.conditions" rows="3"/></label><label>问题与作答要求<textarea v-model="taskEditor.question" rows="3"/></label><label>教材给出的答案<textarea v-model="taskEditor.answer" rows="2" placeholder="教材没有给出时留空"/></label><div v-if="taskEditor.taskInstance" class="edit-pair"><label v-for="(_,key) in taskEditor.taskInstance.parameters" :key="key">本题参数 {{key}}<input v-model="taskEditor.taskInstance.parameters[key]"/></label></div><footer class="dialog-footer"><button class="btn" @click="taskEditor=null">取消</button><button class="btn primary" @click="saveTask">保存题目提取</button></footer>
  </WorkbenchDialog>
  <WorkbenchDialog v-if="knowledgeEditor" title="核对 KC 候选" wide @close="knowledgeEditor=null"><p v-if="error" role="alert" class="callout danger">{{error}}</p><label>知识名称<input v-model="knowledgeEditor.name"/></label><label>知识含义<textarea v-model="knowledgeEditor.meaning" rows="4"/></label><label>出处与提取说明<textarea v-model="knowledgeEditor.sourceNote" rows="2"/></label><ContentVisuals :items="knowledgeEditor.visuals" metadata/><footer class="dialog-footer"><button class="btn" @click="knowledgeEditor=null">取消</button><button class="btn primary" @click="saveKnowledge">保存知识提取</button></footer></WorkbenchDialog>
  <WorkbenchDialog v-if="solutionEditor" title="核对解法实例" wide @close="solutionEditor=null"><p v-if="error" role="alert" class="callout danger">{{error}}</p><p class="object-type">SolutionInstance · {{solutionEditor.id}}</p><p>对应题目：{{entry.title}} · {{solutionEditor.taskInstanceId}}</p><p>方法模板：{{templateName(solutionEditor)}}</p><p>来源：<strong>{{solutionEditor.origin}}</strong></p><label v-if="solutions.find(s=>s.id===solutionEditor!.id)?.origin==='来源待确认'">核实后的来源<select v-model="solutionEditor.origin" aria-label="核实后的来源"><option>来源待确认</option><option>教材原有</option><option>系统生成</option></select></label><label>解法名称<input v-model="solutionEditor.name"/></label><label>本题具体求解过程<textarea v-model="solutionEditor.working" rows="6"/></label><label>结果<textarea v-model="solutionEditor.result" rows="2"/></label><label>来源说明<textarea v-model="solutionEditor.sourceNote" rows="2"/></label><ContentVisuals :items="solutionEditor.visuals" metadata/><footer class="dialog-footer"><button class="btn" @click="solutionEditor=null">取消</button><button class="btn primary" @click="saveSolution">保存解法核对</button></footer></WorkbenchDialog>
<ContentVisualEditor v-if="visualEditor" :value="visualEditor.value" :owner="visualEditor.owner" :owners="owners" task-owner="task" @save="saveVisual" @close="visualEditor=null"/>
</section></template>
<style scoped>.object-tabs{gap:12px;flex-wrap:wrap}.object-tabs button{font-size:13px}.data-table td{overflow-wrap:anywhere}.owned-visuals{margin-top:12px}.owned-visuals summary,.teaching-visuals summary{cursor:pointer;color:#2d6a4f;padding:8px 0}.teaching-visuals{margin-top:20px}</style>
