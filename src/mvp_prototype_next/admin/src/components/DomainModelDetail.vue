<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { domainMock, domainKinds, collectKnowledge, type DomainKind, type DomainMethod, type DomainKnowledge } from '../workbench/domain-mock';
import WorkbenchDialog from './WorkbenchDialog.vue';

const props=defineProps<{kind:'solution'|'kc';objectId:string;domainId:string;editing:boolean}>();
const emit=defineEmits<{edit:[];save:[id:string];cancel:[];open:[kind:DomainKind,id:string]}>();
const originalMethod=computed(()=>domainMock.methods.find(m=>m.id===props.objectId&&m.domainId===props.domainId));
const originalKnowledge=computed(()=>domainMock.knowledge.find(k=>k.id===props.objectId&&k.domainId===props.domainId));
const copy=<T,>(value:T):T=>JSON.parse(JSON.stringify(value));
const methodDraft=ref<DomainMethod>(copy(originalMethod.value||{id:'S-'+Date.now(),domainId:props.domainId,name:'',description:'',conditions:'',inputs:[],output:'',steps:[],kc:[]}));
const knowledgeDraft=ref<DomainKnowledge>(copy(originalKnowledge.value||{id:'K-'+Date.now(),domainId:props.domainId,name:'',description:'',prerequisites:[]}));
const method=computed(()=>props.editing?methodDraft.value:originalMethod.value||methodDraft.value);
const knowledge=computed(()=>props.editing?knowledgeDraft.value:originalKnowledge.value||knowledgeDraft.value);
const object=computed(()=>props.kind==='solution'?method.value:knowledge.value);
const info=computed(()=>domainKinds[props.kind]);
const tasks=computed(()=>domainMock.tasks.filter(t=>t.domainId===props.domainId));
const knowledgeOptions=computed(()=>domainMock.knowledge.filter(k=>k.domainId===props.domainId));
const linkedTasks=computed(()=>tasks.value.filter(t=>t.methods.includes(method.value.id)));
const selectedTasks=ref(linkedTasks.value.map(t=>t.id));
const relatedTasks=computed(()=>tasks.value.filter(t=>collectKnowledge(t.methods,props.domainId).rows.some(r=>r.knowledge.id===knowledge.value.id)));
const methodKnowledge=computed(()=>collectKnowledge([method.value.id],props.domainId));
const childOptions=computed(()=>domainMock.methods.filter(m=>m.domainId===props.domainId&&m.id!==method.value.id));
function methodName(id:string){return domainMock.methods.find(m=>m.id===id)?.name||id;}
function childTasks(id:string){return tasks.value.filter(t=>t.methods.includes(id));}
const relatedMethods=computed(()=>domainMock.methods.filter(m=>m.domainId===props.domainId&&m.kc.includes(knowledge.value.id)));
const dependentKnowledge=computed(()=>knowledgeOptions.value.filter(k=>k.prerequisites.includes(knowledge.value.id)));
const message=ref(''),picker=ref<'task'|'kc'|null>(null),query=ref(''),picked=ref<string[]>([]);
const choices=computed(()=>(picker.value==='task'?tasks.value:knowledgeOptions.value.filter(k=>props.kind!=='kc'||k.id!==knowledge.value.id)).filter(o=>(o.name+' '+o.id).includes(query.value.trim())));
watch(()=>props.editing,()=>{if(originalMethod.value)methodDraft.value=copy(originalMethod.value);if(originalKnowledge.value)knowledgeDraft.value=copy(originalKnowledge.value);selectedTasks.value=linkedTasks.value.map(t=>t.id);message.value='';});
function taskName(id:string){return tasks.value.find(t=>t.id===id)?.name||id;}
function knowledgeName(id:string){return knowledgeOptions.value.find(k=>k.id===id)?.name||id;}
function openPicker(kind:'task'|'kc'){picker.value=kind;query.value='';picked.value=[...(kind==='task'?selectedTasks.value:props.kind==='solution'?method.value.kc:knowledge.value.prerequisites)];}
function applyPicker(){if(picker.value==='task')selectedTasks.value=[...picked.value];else if(props.kind==='solution')methodDraft.value.kc=[...picked.value];else knowledgeDraft.value.prerequisites=[...picked.value];picker.value=null;}
function save(){
  if(!object.value.name.trim()){message.value='请填写'+info.value.name+'名称。';return;}
  if(props.kind==='solution'){
    const saved=copy(methodDraft.value),index=domainMock.methods.findIndex(m=>m.id===saved.id);
    if(index<0)domainMock.methods.push(saved);else domainMock.methods[index]=saved;
    tasks.value.forEach(t=>{t.methods=t.methods.filter(id=>id!==saved.id);if(selectedTasks.value.includes(t.id))t.methods.push(saved.id);});
    emit('save',saved.id);
  }else{
    const saved=copy(knowledgeDraft.value),index=domainMock.knowledge.findIndex(k=>k.id===saved.id);
    if(index<0)domainMock.knowledge.push(saved);else domainMock.knowledge[index]=saved;
    emit('save',saved.id);
  }
}
</script>

<template><div class="domain-detail">
  <header class="page-header detail-heading"><div><span class="object-type">{{info.english}}</span><h2>{{object.name||'新建'+info.name}}</h2><p v-if="!editing" class="page-desc">{{object.description}}</p></div><div class="detail-actions"><template v-if="editing"><button class="btn" @click="emit('cancel')">取消</button><button class="btn primary" @click="save">保存</button></template><button v-else class="btn primary" @click="emit('edit')">编辑{{info.name}}</button></div></header>
  <p v-if="message" class="callout danger" role="alert">{{message}}</p>
  <section v-if="editing" class="panel"><h3>基本定义</h3><label>{{info.name}}名称<input v-model="object.name" :placeholder="kind==='solution'?'例如：先求增加量，再求总量':'例如：分数的参照量'"/></label><label>定义说明<textarea v-model="object.description" :placeholder="kind==='solution'?'说明方法的主要思路':'说明这项知识是什么，以及适用条件'"/></label><label v-if="kind==='solution'">适用条件<textarea v-model="method.conditions"/></label></section>

  <template v-if="kind==='solution'">
    <section class="panel"><div class="row-between"><h3>适用任务</h3><button v-if="editing" class="btn" @click="openPicker('task')">选择任务</button></div><p class="muted">这些任务将此方法列为可用解法。</p><p v-if="!editing">适用条件：{{method.conditions||'尚未填写'}}</p><div class="relation-rows"><div v-for="id in (editing?selectedTasks:linkedTasks.map(t=>t.id))" :key="id"><span v-if="editing">{{taskName(id)}}</span><button v-else class="text-link" @click="emit('open','task',id)">{{taskName(id)}} →</button><button v-if="editing" class="text-link" :aria-label="'移除任务：'+taskName(id)" @click="selectedTasks=selectedTasks.filter(t=>t!==id)">移除</button></div></div><p v-if="!(editing?selectedTasks:linkedTasks).length" class="muted">尚未关联任务。</p></section>
    <section class="panel"><div class="row-between"><h3>输入与输出</h3><button v-if="editing" class="btn" @click="method.inputs.push(['',''])">＋ 添加输入</button></div><template v-if="editing"><div v-for="(input,index) in method.inputs" :key="index" class="input-row"><label>输入含义<input v-model="input[0]" :aria-label="'输入'+(index+1)+'含义'" placeholder="原量"/></label><label>参数或表达<input v-model="input[1]" :aria-label="'输入'+(index+1)+'表达'" placeholder="q"/></label><button class="text-link" :aria-label="'移除输入'+(index+1)" @click="method.inputs.splice(index,1)">移除</button></div><label>输出<input v-model="method.output" placeholder="例如：最终量 → t"/></label></template><template v-else><dl class="field-list"><template v-for="([label,value],index) in method.inputs" :key="index"><dt>{{label}}</dt><dd class="mono">{{value}}</dd></template><dt>输出</dt><dd>{{method.output||'尚未填写'}}</dd></dl></template></section>
    <section class="panel"><div class="row-between"><h3>求解步骤与子方法</h3><button v-if="editing" class="btn" @click="method.steps.push({title:'',detail:'',decomposed:false,solutionId:''})">＋ 添加步骤</button></div><p class="muted">直接处理的步骤使用本方法的知识依据；需要分解的步骤明确引用子 Solution。</p>
      <ol class="solution-steps"><li v-for="(step,index) in method.steps" :key="index"><template v-if="editing"><div class="row-between"><strong>步骤 {{index+1}}</strong><button class="text-link" :aria-label="'移除步骤'+(index+1)" @click="method.steps.splice(index,1)">移除</button></div><label>步骤名称<input v-model="step.title" :aria-label="'步骤'+(index+1)+'名称'"/></label><label>处理与参数传递<textarea v-model="step.detail" :aria-label="'步骤'+(index+1)+'说明'" placeholder="说明输入、处理关系和输出"/></label><label class="check-label"><input v-model="step.decomposed" type="checkbox" :aria-label="'步骤'+(index+1)+'分解为子方法'" @change="!step.decomposed&&(step.solutionId='')"/>分解为子方法</label><label v-if="step.decomposed">引用子方法<select v-model="step.solutionId" :aria-label="'步骤'+(index+1)+'子方法'"><option value="">尚未指定</option><option v-for="m in childOptions" :key="m.id" :value="m.id">{{m.name}}</option></select></label></template><template v-else><strong>{{step.title}}</strong><p class="multiline">{{step.detail}}</p><template v-if="step.solutionId"><button class="subtask text-link" @click="emit('open','solution',step.solutionId)">子方法：{{methodName(step.solutionId)}} →</button><p class="muted">对应子任务：<template v-for="(t,i) in childTasks(step.solutionId)" :key="t.id"><span v-if="i">、</span><button class="text-link" @click="emit('open','task',t.id)">{{t.name}}</button></template><span v-if="!childTasks(step.solutionId).length">尚未关联</span></p></template><p v-else-if="step.decomposed" class="callout amber">子方法尚未指定，知识汇总未完整。</p></template></li></ol><p v-if="!method.steps.length" class="muted">尚未添加求解步骤。</p>
    </section>
    <section class="panel"><div class="row-between"><h3>直接依赖的知识</h3><button v-if="editing" class="btn" @click="openPicker('kc')">关联知识</button></div><div class="relation-rows"><div v-for="id in method.kc" :key="id"><span v-if="editing">{{knowledgeName(id)}}</span><button v-else class="text-link" @click="emit('open','kc',id)">{{knowledgeName(id)}} →</button><button v-if="editing" class="text-link" :aria-label="'移除知识：'+knowledgeName(id)" @click="method.kc=method.kc.filter(k=>k!==id)">移除</button></div></div><p v-if="!method.kc.length" class="muted">尚未关联知识成分。</p></section>
    <section v-if="!editing" class="panel"><h3>方法知识汇总</h3><p class="muted">直接依赖与子方法知识合并，共 {{methodKnowledge.rows.length}} 项（已去重）。</p><p v-if="methodKnowledge.issues.length" class="callout amber">{{methodKnowledge.issues.join(' ')}}</p><table class="data-table"><thead><tr><th>知识成分</th><th>来源</th></tr></thead><tbody><tr v-for="row in methodKnowledge.rows" :key="row.knowledge.id"><td><button class="text-link" @click="emit('open','kc',row.knowledge.id)">{{row.knowledge.name}}</button></td><td>{{row.sources[0]?.direct?(row.sources[0]?.indirect?'直接依赖、经子方法':'直接依赖'):'经子方法汇总'}}</td></tr></tbody></table><p v-if="!methodKnowledge.rows.length" class="muted">暂无可汇总的知识依据。</p></section>

  </template>

  <template v-else>
    <section class="panel"><div class="row-between"><h3>先修知识</h3><button v-if="editing" class="btn" @click="openPicker('kc')">选择先修知识</button></div><p class="muted">理解或运用本项知识之前，需要哪些知识作为基础。</p><div class="relation-rows"><div v-for="id in knowledge.prerequisites" :key="id"><span v-if="editing">{{knowledgeName(id)}}</span><button v-else class="text-link" @click="emit('open','kc',id)">{{knowledgeName(id)}} →</button><button v-if="editing" class="text-link" :aria-label="'移除先修：'+knowledgeName(id)" @click="knowledge.prerequisites=knowledge.prerequisites.filter(k=>k!==id)">移除</button></div></div><p v-if="!knowledge.prerequisites.length" class="muted">未设置先修知识。</p></section>
    <section v-if="!editing" class="panel"><h3>哪些对象依赖这项知识</h3><h4>相关任务（经方法汇总）</h4><div class="relation-rows"><div v-for="t in relatedTasks" :key="t.id"><button class="text-link" @click="emit('open','task',t.id)">{{t.name}} →</button></div></div><p v-if="!relatedTasks.length" class="muted">暂无任务通过方法关联到此知识。</p><h4>直接引用的方法</h4><div class="relation-rows"><div v-for="m in relatedMethods" :key="m.id"><button class="text-link" @click="emit('open','solution',m.id)">{{m.name}} →</button></div></div><p v-if="!relatedMethods.length" class="muted">暂无方法引用。</p><h4>以此为先修的知识</h4><div class="relation-rows"><div v-for="k in dependentKnowledge" :key="k.id"><button class="text-link" @click="emit('open','kc',k.id)">{{k.name}} →</button></div></div><p v-if="!dependentKnowledge.length" class="muted">暂无其他知识引用。</p></section>
  </template>
  <div v-if="editing" class="edit-footer"><button class="btn" @click="emit('cancel')">取消</button><button class="btn primary" @click="save">保存</button></div>
  <WorkbenchDialog v-if="picker" :title="picker==='task'?'选择适用任务':kind==='kc'?'选择先修知识':'关联知识成分'" @close="picker=null"><label>搜索<input v-model="query" placeholder="按名称或编号搜索"/></label><div class="picker-list"><label v-for="choice in choices" :key="choice.id" class="picker-choice"><input v-model="picked" type="checkbox" :value="choice.id"/><span>{{choice.name}}<small>{{choice.id}}</small></span></label><p v-if="!choices.length" class="muted">没有匹配项，请调整搜索或先在对应分区新建。</p></div><div class="dialog-footer button-row"><button class="btn" @click="picker=null">取消</button><button class="btn primary" @click="applyPicker">确认选择</button></div></WorkbenchDialog>
</div></template>

<style scoped>
.object-type{font-size:12px;color:#718578}.detail-heading h2{font-size:23px;margin:4px 0}.detail-heading>div:first-child{min-width:0}.detail-actions{display:flex;gap:8px;flex-shrink:0;padding-top:18px}.detail-heading{align-items:flex-start}.detail-heading .page-desc{max-width:800px}.relation-rows>div{display:flex;justify-content:space-between;gap:18px;padding:12px 0;border-bottom:1px solid #edf1ee;font-size:14px}.relation-rows>div:last-child{border-bottom:0}.relation-rows .text-link{font-size:14px}.input-row{display:grid;grid-template-columns:1fr 1fr auto;gap:18px;align-items:end}.input-row>.text-link{margin-bottom:16px}.solution-steps{list-style:none;counter-reset:step;padding:0}.solution-steps>li{counter-increment:step;position:relative;margin-top:18px;padding:0 0 18px 42px;border-bottom:1px solid #e6ede8;font-size:14px}.solution-steps>li:before{content:counter(step);position:absolute;left:0;top:0;width:26px;height:26px;border-radius:50%;background:#eaf2ed;color:#37664b;text-align:center;line-height:26px;font-size:13px}.solution-steps>li:last-child{border:0;padding-bottom:0}.multiline{white-space:pre-wrap}.subtask{display:inline-block;background:#f2f7f4;border:1px solid #dfe9e3;border-radius:6px;padding:8px 12px;margin-top:6px}.edit-footer{display:flex;justify-content:flex-end;gap:10px;padding:14px 0}.picker-list{max-height:360px;overflow:auto}.picker-choice{display:flex;gap:8px;align-items:flex-start;border:1px solid #e3ebe5;border-radius:6px;padding:12px;cursor:pointer}.picker-choice input{margin-top:4px}.picker-choice small{display:block;color:#7a8c80;margin-top:3px}@media(max-width:900px){.detail-heading{flex-wrap:wrap}.detail-actions{padding-top:0}.input-row{grid-template-columns:1fr 1fr auto;gap:10px}}
</style>
