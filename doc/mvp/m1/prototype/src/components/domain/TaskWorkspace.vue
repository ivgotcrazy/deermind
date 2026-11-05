<script setup lang="ts">
import { computed, ref } from 'vue';
import { domainData, clone, blankTask, saveEntity, taskIssues, collectKnowledge, parameterKinds, parameterRoles, type Kind, type Task } from '../../model/domain';
import WorkbenchDialog from '../WorkbenchDialog.vue';
import TaskInstances from './TaskInstances.vue';
const props=defineProps<{domainId:string;objectId:string;tab:string;initial?:Task}>();
const emit=defineEmits<{saved:[id:string];open:[kind:Kind,id:string,tab?:string];back:[]}>();
const empty=blankTask(props.domainId);
const task=computed(()=>domainData.tasks.find(t=>t.id===props.objectId&&t.domainId===props.domainId)||props.initial||empty);
const sections=[{id:'basic',name:'任务与完成要求'},{id:'parameters',name:'对象与变量'},{id:'relations',name:'条件与关系'},{id:'variations',name:'允许的变化'},{id:'exclusions',name:'适用边界'}] as const;
type Section=typeof sections[number]['id'];
const editing=ref<Section|''>(props.objectId==='new'?'basic':''), draft=ref(clone(task.value));
const picker=ref(false),picked=ref<string[]>([]),query=ref(''),error=ref('');
const tabs={definition:'任务定义',methods:'方法',knowledge:'知识',instances:'实例'};
const active=computed(()=>props.tab in tabs?props.tab:'definition');
const methods=computed(()=>domainData.methods.filter(m=>m.domainId===props.domainId&&task.value.methods.includes(m.id)));
const knowledge=computed(()=>collectKnowledge(task.value.methods,props.domainId));
const issues=computed(()=>taskIssues(task.value));
const choices=computed(()=>domainData.methods.filter(m=>m.domainId===props.domainId&&(m.name+' '+m.id).includes(query.value.trim())));
function edit(s:Section){draft.value=clone(task.value);editing.value=s;error.value='';}
function cancel(){editing.value='';if(props.objectId==='new')emit('back');}
function save(){
  if(!draft.value.name.trim()){error.value='请填写任务名称。';return;}
  saveEntity(domainData.tasks,draft.value);editing.value='';emit('saved',draft.value.id);
}
function chooseMethods(){picked.value=[...task.value.methods];query.value='';picker.value=true;}
function saveMethods(){saveEntity(domainData.tasks,{...task.value,methods:[...picked.value]});picker.value=false;emit('saved',task.value.id);}
</script>
<template><div>
  <header class="page-header"><div><span class="object-type">TaskTemplate <span v-if="task.version">· {{task.id}} · v{{task.version}}</span></span><h2>{{task.name||'新建任务模板'}}</h2><p class="page-desc">{{task.summary}}</p></div><button class="btn" @click="emit('back')">返回任务列表</button></header>
  <template v-if="objectId!=='new'">
    <details v-if="issues.length" class="preparation"><summary>任务尚有 {{issues.length}} 项待补齐</summary><ul><li v-for="issue in issues" :key="issue">{{issue}}</li></ul></details>
    <nav class="object-tabs" aria-label="任务内容"><button v-for="(name,key) in tabs" :key="key" :class="{active:active===key}" :aria-current="active===key?'page':undefined" @click="emit('open','task',task.id,key)">{{name}}</button></nav>
    <template v-if="active==='definition'">
      <section v-for="s in sections" :key="s.id" class="panel"><header class="row-between"><h3>{{s.name}}</h3><button class="text-link" :aria-label="'编辑'+s.name" @click="edit(s.id)">编辑</button></header>
        <template v-if="s.id==='basic'"><dl class="field-list"><dt>任务目标</dt><dd>{{task.goal||'尚未填写'}}</dd><dt>学习者承担的工作</dt><dd>{{task.responsibility||'尚未填写'}}</dd></dl><h4>完成要求</h4><p class="muted">说明这一次任务要交付什么、怎样算完成；不表示学生已长期掌握。</p><table v-if="task.requirements.length" class="data-table" aria-label="完成要求"><thead><tr><th>交付内容</th><th>怎样算完成</th></tr></thead><tbody><tr v-for="(r,index) in task.requirements" :key="index"><td class="multiline">{{index+1}}. {{r.deliverable||'尚未填写'}}</td><td class="multiline">{{r.criterion||'待补充完成条件'}}</td></tr></tbody></table><p v-else class="muted">尚未添加完成要求。</p></template>
        <template v-else-if="s.id==='parameters'"><p class="muted">区分题目已经给出的内容、需要研究的变量，以及需要调查才能获取的信息。</p><table v-if="task.parameters.length" class="data-table" aria-label="对象与变量"><thead><tr><th>标识</th><th>名称</th><th>内容类型</th><th>用途</th><th>取值与约束</th></tr></thead><tbody><tr v-for="(p,index) in task.parameters" :key="index"><td>{{p.symbol}}</td><td>{{p.name}}</td><td>{{p.kind||'待标注'}}</td><td>{{p.role}}</td><td class="multiline">{{p.condition}}</td></tr></tbody></table><p v-else class="muted">尚未定义对象与变量。</p></template>
        <template v-else-if="s.id==='variations'"><p class="muted">只在声明的范围内变题；变化后的题目仍需检查。未设置时不主动生成变式。</p><table v-if="task.variations.length" class="data-table" aria-label="允许的变化"><thead><tr><th>什么可以变</th><th>允许怎样变</th><th>必须满足的条件</th></tr></thead><tbody><tr v-for="(v,index) in task.variations" :key="index"><td>{{v.target}}</td><td class="multiline">{{v.range}}</td><td class="multiline">{{v.constraint||'待补充变化条件'}}</td></tr></tbody></table><p v-else class="muted">未开放变化，按已定义的任务条件准备实例。</p></template>
        <template v-else><p class="muted">{{s.id==='relations'?'写明必须成立的事实及对象之间的关系；求解步骤在方法中维护。':'说明不包含的任务、排除情况及容易混淆的反例。'}}</p><p class="multiline">{{(s.id==='relations'?task.relations:task.exclusions)||'尚未填写'}}</p></template>
      </section>
    </template>
    <template v-else-if="active==='methods'"><div class="object-toolbar"><p class="muted">只展示直接方法，子方法在方法详情中查看。</p><button class="btn primary" @click="chooseMethods">关联方法</button></div><section class="panel"><table v-if="methods.length" class="data-table"><thead><tr><th>方法</th><th>思路</th><th>适用条件</th></tr></thead><tbody><tr v-for="m in methods" :key="m.id"><td><button class="text-link model-name" @click="emit('open','solution',m.id)">{{m.name}}</button></td><td>{{m.description}}</td><td>{{m.conditions}}</td></tr></tbody></table><div v-else class="empty"><p>尚未关联方法。</p><button class="btn" @click="emit('open','solution','new')">新建方法模板</button></div></section></template>
    <template v-else-if="active==='knowledge'"><p class="muted">由所选方法及子方法递归汇总并去重，不能在这里直接添加知识。</p><p v-if="knowledge.issues.length" class="callout amber">{{knowledge.issues.join('；')}}</p><section class="panel"><table v-if="knowledge.rows.length" class="data-table"><thead><tr><th>知识成分</th><th>知识定义</th><th>引用路径</th></tr></thead><tbody><tr v-for="row in knowledge.rows" :key="row.knowledge.id"><td><button class="text-link model-name" @click="emit('open','kc',row.knowledge.id)">{{row.knowledge.name}}</button></td><td>{{row.knowledge.description}}</td><td><div v-for="(path,index) in row.paths" :key="index" class="reference-path"><template v-for="(key,n) in path" :key="n"><span v-if="n"> → </span><button class="text-link" @click="emit('open','solution',key)">{{domainData.methods.find(m=>m.id===key)?.name}}</button></template></div></td></tr></tbody></table><p v-else class="empty">没有可汇总的知识。请在方法中补齐知识依据。</p></section></template>
    <TaskInstances v-else :task="task" @open="(kind,key)=>emit('open',kind,key)"/>
  </template>
  <WorkbenchDialog v-if="editing" :title="objectId==='new'?'新建任务模板':'编辑'+sections.find(s=>s.id===editing)?.name" wide @close="cancel"><form @submit.prevent="save"><p v-if="error" class="callout danger" role="alert">{{error}}</p>
    <template v-if="editing==='basic'"><label>任务名称<input v-model="draft.name" required/></label><label>任务说明<textarea v-model="draft.summary" rows="2"/></label><label>任务目标<input v-model="draft.goal"/></label><label>学习者承担的工作<textarea v-model="draft.responsibility" rows="3"/></label><h4>完成要求</h4><p class="muted">逐项说明要交付什么，以及怎样才算完成。这里不填写某一道题的答案。</p><div v-for="(r,index) in draft.requirements" :key="index" class="entry-editor"><div class="row-between"><strong>要求 {{index+1}}</strong><button type="button" class="text-link" @click="draft.requirements.splice(index,1)">移除要求 {{index+1}}</button></div><label>交付内容<textarea v-model="r.deliverable" :aria-label="'要求'+(index+1)+'交付内容'" rows="2"/></label><label>怎样算完成<textarea v-model="r.criterion" :aria-label="'要求'+(index+1)+'完成条件'" rows="2"/></label></div><button type="button" class="btn" @click="draft.requirements.push({deliverable:'',criterion:''})">添加完成要求</button></template>
    <template v-else-if="editing==='parameters'"><p class="muted">题目已给定的内容在实例中填写；需要讨论或调查的内容，保留给学习者处理。</p><div v-for="(p,index) in draft.parameters" :key="index" class="entry-editor"><div class="row-between"><strong>对象／变量 {{index+1}}</strong><button type="button" class="text-link" @click="draft.parameters.splice(index,1)">移除对象 {{index+1}}</button></div><div class="edit-pair"><label>标识<input v-model="p.symbol" :aria-label="'对象'+(index+1)+'标识'" placeholder="如 a、P、service"/></label><label>名称<input v-model="p.name" :aria-label="'对象'+(index+1)+'名称'"/></label></div><div class="edit-pair"><label>内容类型<select v-model="p.kind" :aria-label="'对象'+(index+1)+'类型'"><option value="">请选择</option><option v-for="kind in parameterKinds" :key="kind">{{kind}}</option></select></label><label>用途<select v-model="p.role" :aria-label="'对象'+(index+1)+'用途'"><option v-for="role in parameterRoles" :key="role">{{role}}</option></select></label></div><label>取值与约束<textarea v-model="p.condition" :aria-label="'对象'+(index+1)+'约束'" rows="2"/></label></div><button type="button" class="btn" @click="draft.parameters.push({symbol:'',name:'',kind:'',role:'题目已给定',condition:''})">添加对象或变量</button></template>
    <label v-else-if="editing==='relations'">条件与关系<textarea v-model="draft.relations" rows="6" placeholder="说明已知、未知之间的关系及题面给出的信息"/></label>
    <template v-else-if="editing==='variations'"><p class="muted">填写可以改变的内容、允许范围及联合约束。不开放变式时可以留空。</p><div v-for="(v,index) in draft.variations" :key="index" class="entry-editor"><div class="row-between"><strong>变化 {{index+1}}</strong><button type="button" class="text-link" @click="draft.variations.splice(index,1)">移除变化 {{index+1}}</button></div><label>什么可以变<input v-model="v.target" :aria-label="'变化'+(index+1)+'对象'"/></label><label>允许怎样变<textarea v-model="v.range" :aria-label="'变化'+(index+1)+'范围'" rows="2"/></label><label>必须满足的条件<textarea v-model="v.constraint" :aria-label="'变化'+(index+1)+'条件'" rows="2"/></label></div><button type="button" class="btn" @click="draft.variations.push({target:'',range:'',constraint:''})">添加变化</button></template>
    <label v-else>适用边界<textarea v-model="draft.exclusions" rows="6"/></label>
    <footer class="dialog-footer"><button type="button" class="btn" @click="cancel">取消</button><button class="btn primary">{{objectId==='new'?'创建任务模板':'保存修改'}}</button></footer>
  </form></WorkbenchDialog>
  <WorkbenchDialog v-if="picker" title="关联方法" @close="picker=false"><label>搜索方法<input v-model="query" type="search"/></label><div class="picker-list"><label v-for="m in choices" :key="m.id" class="check-line"><input v-model="picked" type="checkbox" :value="m.id"/>{{m.name}}</label><p v-if="!choices.length" class="muted">没有匹配的方法，请先在方法模板中创建。</p></div><p class="muted">取消勾选会解除关联，不删除方法；受影响实例需要重新检查。</p><footer class="dialog-footer"><button class="btn" @click="picker=false">取消</button><button class="btn primary" @click="saveMethods">保存关联</button></footer></WorkbenchDialog>
</div></template>
