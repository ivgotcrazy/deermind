<script setup lang="ts">
import { computed, ref } from 'vue';
import { domainData, blankMethod, readMethod, saveEntity, collectKnowledge, type Kind, type Method } from '../../model/domain';
const props=defineProps<{domainId:string;objectId:string;initial?:Method}>();
const emit=defineEmits<{saved:[id:string];open:[kind:Kind,id:string];back:[]}>();
const empty=blankMethod(props.domainId);
const method=computed(()=>readMethod(domainData.methods.find(m=>m.id===props.objectId&&m.domainId===props.domainId)||props.initial||empty));
const editing=ref(props.objectId==='new'),draft=ref(readMethod(method.value)),error=ref('');
const tasks=computed(()=>domainData.tasks.filter(t=>t.domainId===props.domainId));
const linked=computed(()=>tasks.value.filter(t=>t.methods.includes(method.value.id)));
const selectedTasks=ref(linked.value.map(t=>t.id));
const knowledge=computed(()=>domainData.knowledge.filter(k=>k.domainId===props.domainId));
const collected=computed(()=>collectKnowledge([method.value.id],props.domainId));
const examples=computed(()=>domainData.instances.filter(q=>q.domainId===props.domainId&&q.solutions.some(s=>s.methodId===method.value.id)));
const taskQuery=ref(''),kcQuery=ref('');
const taskChoices=computed(()=>tasks.value.filter(t=>t.name.includes(taskQuery.value)));
const kcChoices=computed(()=>knowledge.value.filter(k=>k.name.includes(kcQuery.value)));
function edit(){draft.value=readMethod(method.value);selectedTasks.value=linked.value.map(t=>t.id);editing.value=true;error.value='';}
function cancel(){editing.value=false;if(props.objectId==='new')emit('back');}
function save(){
  if(!draft.value.name.trim()){error.value='请填写方法名称。';return;}
  const next=saveEntity(domainData.methods,draft.value);
  for(const t of tasks.value){const wanted=selectedTasks.value.includes(t.id),has=t.methods.includes(next.id);if(wanted!==has)saveEntity(domainData.tasks,{...t,methods:wanted?[...t.methods,next.id]:t.methods.filter(x=>x!==next.id)});}
  editing.value=false;emit('saved',next.id);
}
</script>
<template><div>
  <header class="page-header"><div><span class="object-type">Solution <span v-if="method.version">· {{method.id}} · v{{method.version}}</span></span><h2>{{method.name||'新建方法'}}</h2><p class="page-desc">描述学生怎样完成任务、为什么这样做；教学策略在交互活动中管理。</p></div><div class="button-row"><button class="btn" @click="emit('back')">返回方法列表</button><button v-if="!editing" class="btn primary" @click="edit">编辑方法</button></div></header>
  <p v-if="error" class="callout danger" role="alert">{{error}}</p>
  <form v-if="editing" @submit.prevent="save">
    <section class="panel"><h3>方法定义</h3><label>方法名称<input v-model="draft.name" required/></label><label>方法思路与依据<textarea v-model="draft.description" rows="3"/></label><label>适用条件<textarea v-model="draft.conditions" rows="3"/></label><label>关键过程<textarea v-model="draft.procedure" rows="9" placeholder="说明怎样完成任务；需要时写明分类、复查和停止条件，不必创建子任务调用图。"/></label><div class="edit-pair"><label>所需信息（可选）<textarea v-model="draft.inputs" rows="2"/></label><label>得到的结果（可选）<textarea v-model="draft.output" rows="2"/></label></div></section>
    <section class="panel"><h3>适用任务</h3><label>查找任务<input v-model="taskQuery" type="search"/></label><div class="picker-list"><label v-for="t in taskChoices" :key="t.id" class="check-line"><input v-model="selectedTasks" type="checkbox" :value="t.id"/>{{t.name}}</label></div><p v-if="!tasks.length" class="muted">可以先保存方法，再创建任务并关联。</p></section>
    <section class="panel"><h3>知识依据</h3><p class="muted">选择此方法实际涉及的所有 KC，可关联多项。先导任务的知识不会自动加入。</p><label>查找知识<input v-model="kcQuery" type="search"/></label><div class="picker-list"><label v-for="k in kcChoices" :key="k.id" class="check-line"><input v-model="draft.kc" type="checkbox" :value="k.id"/>{{k.name}}</label></div><p v-if="!knowledge.length" class="muted">还没有知识成分，可先保存，之后补齐。</p></section>
    <footer class="editor-footer"><button type="button" class="btn" @click="cancel">取消</button><button class="btn primary">保存方法</button></footer>
  </form>
  <template v-else>
    <div v-if="collected.issues.length" class="callout amber" role="status"><strong>方法待核对</strong><ul><li v-for="issue in collected.issues" :key="issue">{{issue}}</li></ul></div>
    <section class="panel"><h3>方法定义</h3><dl class="field-list"><dt>思路与依据</dt><dd class="multiline">{{method.description||'尚未填写'}}</dd><dt>适用条件</dt><dd class="multiline">{{method.conditions||'尚未填写'}}</dd><template v-if="method.inputs"><dt>所需信息</dt><dd>{{method.inputs}}</dd></template><template v-if="method.output"><dt>得到的结果</dt><dd>{{method.output}}</dd></template></dl></section>
    <section class="panel"><h3>关键过程</h3><p class="multiline">{{method.procedure||'尚未填写'}}</p><details v-if="method.ending?.success||method.ending?.stop"><summary>已有完成与停止说明</summary><p>{{method.ending?.success}}</p><p>{{method.ending?.stop}}</p></details></section>
    <section class="panel"><h3>适用任务</h3><div class="relation-list"><button v-for="t in linked" :key="t.id" class="text-link" @click="emit('open','task',t.id)">{{t.name}} →</button></div><p v-if="!linked.length" class="muted">尚未关联任务。</p></section>
    <section class="panel"><h3>知识依据</h3><table v-if="collected.rows.length" class="data-table"><thead><tr><th>知识成分</th><th>定义</th></tr></thead><tbody><tr v-for="row in collected.rows" :key="row.knowledge.id"><td><button class="text-link" @click="emit('open','kc',row.knowledge.id)">{{row.knowledge.name}}</button></td><td>{{row.knowledge.description}}</td></tr></tbody></table><p v-else class="muted">尚未关联知识。</p></section>
    <section v-if="examples.length" class="panel"><h3>题目中的参考解法</h3><p class="muted">具体解法随题目保存；参考内容不代表学生实际采用了这个方法。</p><details v-for="q in examples" :key="q.id"><summary>{{q.question}}</summary><article v-for="s in q.solutions.filter(s=>s.methodId===method.id)" :key="s.id||s.working"><p class="multiline">{{s.working}}</p><small>{{s.origin||'来源待确认'}} · {{s.sourceNote||q.sourceNote}}</small></article><button class="text-link" @click="emit('open','task',q.taskId)">查看所属任务 →</button></details></section>
  </template>
</div></template>
