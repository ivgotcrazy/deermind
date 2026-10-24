<script setup lang="ts">
import { computed, ref } from 'vue';
import { domainMock, domainTaskTabs, blankDomainTask, collectKnowledge, type DomainTask, type DomainKind } from '../workbench/domain-mock';
import WorkbenchDialog from './WorkbenchDialog.vue';
import TaskInstances from './TaskInstances.vue';
const props=defineProps<{taskId:string;domainId:string;editing:boolean}>();
const emit=defineEmits<{save:[id:string];cancel:[];open:[kind:DomainKind,id:string]}>();
const empty=blankDomainTask(props.domainId);
const task=computed(()=>domainMock.tasks.find(t=>t.id===props.taskId&&t.domainId===props.domainId)||empty);
const copy=(value:DomainTask):DomainTask=>JSON.parse(JSON.stringify(value));
const draft=ref(copy(task.value));
const sections=[{id:'basic',label:'基本定义'},{id:'parameters',label:'对象与参数'},{id:'relations',label:'条件与关系'},{id:'variations',label:'允许的变化'},{id:'exclusions',label:'适用边界'}] as const;
type Section=typeof sections[number]['id'];
const section=ref<Section|null>(props.taskId==='new'?'basic':null),message=ref(''),notice=ref('');
const sectionTitle=computed(()=>sections.find(s=>s.id===section.value)?.label||'');
const tab=computed({get:()=>domainTaskTabs[props.domainId+':'+props.taskId]||'definition',set:(value:string)=>{domainTaskTabs[props.domainId+':'+props.taskId]=value;}});
const tabs=[{id:'definition',label:'任务定义'},{id:'methods',label:'方法'},{id:'knowledge',label:'知识'},{id:'instances',label:'实例'}];
if(!tabs.some(t=>t.id===tab.value)||props.taskId==='new')tab.value='definition';
if(new URLSearchParams(location.hash.split('?')[1]).get('source'))tab.value='instances';
const methods=computed(()=>domainMock.methods.filter(m=>m.domainId===props.domainId&&task.value.methods.includes(m.id)));
const knowledge=computed(()=>collectKnowledge(task.value.methods,props.domainId));
const picker=ref(false),query=ref(''),picked=ref<string[]>([]);
const choices=computed(()=>domainMock.methods.filter(m=>m.domainId===props.domainId&&(m.name+' '+m.description).includes(query.value.trim())));
function edit(value:Section){draft.value=copy(task.value);section.value=value;message.value='';notice.value='';}
function closeEditor(){section.value=null;message.value='';if(props.taskId==='new')emit('cancel');}
function saveSection(){
  if(section.value==='basic'&&!draft.value.name.trim()){message.value='请填写任务名称。';return;}
  if(props.taskId==='new'){domainMock.tasks.push(copy(draft.value));section.value=null;emit('save',draft.value.id);return;}
  if(section.value==='basic')Object.assign(task.value,{name:draft.value.name,summary:draft.value.summary,goal:draft.value.goal,responsibility:draft.value.responsibility,output:draft.value.output});
  else if(section.value==='parameters')task.value.parameters=copy(draft.value).parameters;
  else if(section.value==='relations')task.value.relations=copy(draft.value).relations;
  else if(section.value==='variations')task.value.variations=draft.value.variations;
  else if(section.value==='exclusions')task.value.exclusions=draft.value.exclusions;
  notice.value=sectionTitle.value+'已保存。';section.value=null;
}
function openPicker(){query.value='';picked.value=[...task.value.methods];picker.value=true;notice.value='';}
function saveMethods(){task.value.methods=[...picked.value];picker.value=false;notice.value='方法关联已保存，知识汇总已更新。';}
function unlink(id:string){task.value.methods=task.value.methods.filter(m=>m!==id);notice.value='已解除方法关联，知识汇总已更新。';}
function methodName(id:string){return domainMock.methods.find(m=>m.id===id)?.name||id;}
function switchTab(id:string){tab.value=id;notice.value='';}
function moveTab(event:KeyboardEvent,index:number){const next=event.key==='ArrowRight'?(index+1)%tabs.length:event.key==='ArrowLeft'?(index+tabs.length-1)%tabs.length:-1;if(next<0)return;event.preventDefault();switchTab(tabs[next]!.id);document.getElementById('task-tab-'+tab.value)?.focus();}
</script>

<template><div class="task-workspace">
  <header class="page-header"><div><span class="object-type">TaskTemplate</span><h2>{{task.name||'新建任务模板'}}</h2><p class="page-desc">{{task.summary}}</p></div></header>
  <div class="task-tabs" role="tablist" aria-label="任务模板内容"><button v-for="(item,index) in tabs" :id="'task-tab-'+item.id" :key="item.id" role="tab" :aria-selected="tab===item.id" :aria-controls="'task-panel-'+item.id" :tabindex="tab===item.id?0:-1" :class="{active:tab===item.id}" @click="switchTab(item.id)" @keydown="moveTab($event,index)">{{item.label}}</button></div>
  <p v-if="notice" class="saved-note" role="status">{{notice}}</p>
  <div :id="'task-panel-'+tab" role="tabpanel" :aria-labelledby="'task-tab-'+tab">
    <template v-if="tab==='definition'">
      <section v-for="item in sections" :key="item.id" class="panel definition-section" :data-section="item.id">
        <header class="section-heading"><h3>{{item.label}}</h3><button class="text-link" :aria-label="'编辑'+item.label" @click="edit(item.id)">编辑</button></header>
        <template v-if="item.id==='basic'"><h4>任务目标</h4><p>{{task.goal||'尚未填写'}}</p><div class="field-pair"><div><h4>学习者承担的工作</h4><p class="multiline">{{task.responsibility||'尚未填写'}}</p></div><div><h4>输出要求</h4><p class="multiline">{{task.output||'尚未填写'}}</p></div></div></template>
        <template v-else-if="item.id==='parameters'"><div class="table-scroll"><table class="data-table"><thead><tr><th>符号</th><th>含义</th><th>类型</th><th>角色</th><th>单位与条件</th></tr></thead><tbody><tr v-for="(parameter,index) in task.parameters" :key="index"><td class="mono">{{parameter.symbol}}</td><td>{{parameter.name}}</td><td>{{parameter.type}}</td><td>{{parameter.role}}</td><td>{{parameter.condition}}</td></tr></tbody></table></div><p v-if="!task.parameters.length" class="muted">尚未填写参数。</p></template>
        <template v-else-if="item.id==='relations'"><div v-for="(relation,index) in task.relations" :key="index" class="relation-read"><strong>{{relation.meaning}}</strong><div class="formula">{{relation.expression}}</div><p class="muted">题面提供：{{relation.given||'尚未说明'}}</p></div><p v-if="!task.relations.length" class="muted">尚未填写条件与关系。</p></template>
        <p v-else class="multiline">{{(item.id==='variations'?task.variations:task.exclusions)||'尚未说明'}}</p>
      </section>
    </template>
    <template v-else-if="tab==='methods'">
      <div class="section-heading"><p class="muted">直接关联 {{methods.length}} 种方法；点击名称查看步骤、子方法与知识依据。</p><button class="btn primary" @click="openPicker">关联方法</button></div>
      <section class="table-card"><table class="data-table methods-table"><thead><tr><th>方法名称</th><th>思路摘要</th><th>适用条件</th><th>操作</th></tr></thead><tbody><tr v-for="method in methods" :key="method.id"><td><button class="text-link model-name" @click="emit('open','solution',method.id)">{{method.name}}</button><small>{{method.id}}</small></td><td>{{method.description}}</td><td>{{method.conditions||'尚未填写'}}</td><td><button class="text-link" :aria-label="'解除关联：'+method.name" @click="unlink(method.id)">解除关联</button></td></tr></tbody></table><p v-if="!methods.length" class="empty">尚未关联方法。补充方法后才能汇总此任务的知识。</p></section>
    </template>
    <template v-else-if="tab==='knowledge'">
      <div class="section-heading"><p class="muted">由 {{methods.length}} 种方法递归汇总，共 {{knowledge.rows.length}} 项知识（已去重）。</p></div>
      <p v-if="knowledge.issues.length" class="callout amber">方法或知识依据尚未完整，以下为已知部分。{{knowledge.issues.join(' ')}}</p>
      <section class="table-card"><table class="data-table knowledge-table"><thead><tr><th>知识名称</th><th>知识说明</th><th>关联方法与来源</th></tr></thead><tbody><tr v-for="row in knowledge.rows" :key="row.knowledge.id"><td><button class="text-link model-name" @click="emit('open','kc',row.knowledge.id)">{{row.knowledge.name}}</button><small>{{row.knowledge.id}}</small></td><td>{{row.knowledge.description}}</td><td><div v-for="source in row.sources" :key="source.methodId" class="knowledge-source"><button class="text-link" @click="emit('open','solution',source.methodId)">{{methodName(source.methodId)}}</button><small>{{source.direct&&source.indirect?'直接依赖、经子方法':source.direct?'直接依赖':'经子方法汇总'}}</small></div></td></tr></tbody></table><p v-if="!knowledge.rows.length" class="empty">{{methods.length?'关联方法尚未提供可汇总的知识依据。':'尚未关联方法，没有可汇总的知识。'}}</p></section>
    </template>
    <TaskInstances v-else :task="task"/>
  </div>

  <WorkbenchDialog v-if="section" :title="props.taskId==='new'?'新建任务模板':'编辑'+sectionTitle" wide @close="closeEditor"><form @submit.prevent="saveSection"><p v-if="message" class="callout danger" role="alert">{{message}}</p>
    <template v-if="section==='basic'"><label>任务名称<input v-model="draft.name" placeholder="例如：已知原量和增加比例，求增加后的量"/></label><label>任务说明<textarea v-model="draft.summary" rows="2"/></label><label>所求目标<input v-model="draft.goal"/></label><div class="field-pair"><label>学习者承担的工作<textarea v-model="draft.responsibility" rows="4"/></label><label>输出要求<textarea v-model="draft.output" rows="4"/></label></div></template>
    <template v-else-if="section==='parameters'"><div class="section-heading"><p class="muted">区分已知条件、中间量与最终输出。</p><button type="button" class="btn" @click="draft.parameters.push({symbol:'',name:'',type:'数量',role:'已知量',condition:''})">添加参数</button></div><div class="table-scroll"><table class="parameter-table"><thead><tr><th>符号</th><th>含义</th><th>类型</th><th>角色</th><th>单位与条件</th><th></th></tr></thead><tbody><tr v-for="(p,index) in draft.parameters" :key="index"><td><input v-model="p.symbol" :aria-label="'参数'+(index+1)+'符号'"/></td><td><input v-model="p.name" :aria-label="'参数'+(index+1)+'含义'"/></td><td><input v-model="p.type" :aria-label="'参数'+(index+1)+'类型'"/></td><td><select v-model="p.role" :aria-label="'参数'+(index+1)+'角色'"><option v-for="role in ['已知量','已知对象','待推导中间量','最终输出']" :key="role">{{role}}</option></select></td><td><input v-model="p.condition" :aria-label="'参数'+(index+1)+'条件'"/></td><td><button type="button" class="text-link" :aria-label="'移除参数'+(index+1)" @click="draft.parameters.splice(index,1)">移除</button></td></tr></tbody></table></div></template>
    <template v-else-if="section==='relations'"><div class="section-heading"><p class="muted">分别说明关系及题面提供的信息。</p><button type="button" class="btn" @click="draft.relations.push({meaning:'',expression:'',given:''})">添加关系</button></div><div v-for="(r,index) in draft.relations" :key="index" class="relation-edit-block"><div class="row-between"><strong>关系 {{index+1}}</strong><button type="button" class="text-link" :aria-label="'移除关系'+(index+1)" @click="draft.relations.splice(index,1)">移除</button></div><label>关系含义<input v-model="r.meaning" :aria-label="'关系'+(index+1)+'含义'"/></label><label>关系表达<input v-model="r.expression" :aria-label="'关系'+(index+1)+'表达'"/></label><label>题面如何提供信息<input v-model="r.given" :aria-label="'关系'+(index+1)+'题面信息'"/></label></div></template>
    <label v-else-if="section==='variations'">允许的变化<textarea v-model="draft.variations" rows="7" placeholder="哪些内容改变后仍属于同一任务"/></label>
    <label v-else>适用边界<textarea v-model="draft.exclusions" rows="7" placeholder="适用的限制，以及不属于本任务的情况"/></label>
    <div class="dialog-footer button-row"><button type="button" class="btn" @click="closeEditor">取消</button><button class="btn primary" type="submit">{{props.taskId==='new'?'创建任务模板':'保存'+sectionTitle}}</button></div>
  </form></WorkbenchDialog>
  <WorkbenchDialog v-if="picker" title="关联方法" @close="picker=false"><label>搜索方法<input v-model="query" type="search" placeholder="按名称或思路搜索"/></label><div class="picker-list"><label v-for="m in choices" :key="m.id" class="picker-choice"><input v-model="picked" type="checkbox" :value="m.id"/><span><strong>{{m.name}}</strong><small>{{m.description}}</small></span></label><p v-if="!choices.length" class="muted">没有匹配的方法，可先在方法模板分区新建。</p></div><div class="dialog-footer button-row"><button class="btn" @click="picker=false">取消</button><button class="btn primary" @click="saveMethods">保存关联</button></div></WorkbenchDialog>
</div></template>

<style scoped>
.task-workspace{padding-bottom:24px}.object-type{font-size:12px;color:#788d80}.page-header h2{font-size:23px;margin-top:4px}.task-tabs{display:flex;gap:28px;border-bottom:1px solid #dbe5df;margin-bottom:22px}.task-tabs button{padding:10px 2px 13px;border:0;border-bottom:3px solid transparent;background:none;color:#6b7e72;font-size:14px}.task-tabs button.active{color:#286246;font-weight:600;border-bottom-color:#2d6a4f}.section-heading{display:flex;align-items:center;justify-content:space-between;gap:20px;margin-bottom:14px}.section-heading h3,.section-heading p{margin:0}.section-heading>.btn{flex-shrink:0}.definition-section h4{font-size:12px;color:#78897d;margin:12px 0 5px}.field-pair{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:22px}.multiline{white-space:pre-line;font-size:14px;line-height:1.9}.relation-read{padding:14px 0;border-top:1px solid #edf1ee;font-size:14px}.formula{padding:10px 14px;background:#f3f7f4;font-family:Consolas,monospace;margin:10px 0;border-radius:5px}.table-scroll{overflow:auto}.model-name{font-size:14px;font-weight:600}.methods-table th:first-child{width:25%}.methods-table th:nth-child(2){width:32%}.methods-table th:last-child{width:90px}.knowledge-table th:first-child{width:23%}.knowledge-table th:nth-child(2){width:34%}.knowledge-source+.knowledge-source{margin-top:12px}.knowledge-source small{margin-top:2px}.saved-note{font-size:13px;color:#2d6a4f;margin:0 0 14px}.parameter-table{width:100%;min-width:740px;font-size:12px;border-collapse:collapse}.parameter-table th{text-align:left;font-weight:500;color:#73887a;padding:8px 5px}.parameter-table td{padding:5px}.parameter-table input,.parameter-table select{font-size:12px;padding:7px;margin:0}.parameter-table th:first-child{width:65px}.parameter-table th:nth-child(3){width:85px}.parameter-table th:nth-child(4){width:132px}.parameter-table th:last-child{width:42px}.relation-edit-block{border:1px solid #e1e8e3;border-radius:8px;margin:16px 0;padding:16px}.picker-list{max-height:360px;overflow:auto}.picker-choice{display:flex;gap:8px;align-items:flex-start;border:1px solid #e3ebe5;border-radius:6px;padding:12px;cursor:pointer}.picker-choice input{margin-top:4px}.picker-choice small{display:block;color:#7a8c80;margin-top:4px}@media(max-width:950px){.field-pair{grid-template-columns:1fr;gap:4px}.section-heading{gap:12px}.methods-table th:first-child{width:27%}.methods-table th:nth-child(2){width:28%}}
</style>
