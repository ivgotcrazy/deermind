<script setup lang="ts">
import { computed, ref } from 'vue';
import { domainData, clone, blankKnowledge, saveEntity, knowledgeIssues, collectKnowledge, type Kind, type Knowledge } from '../../model/domain';
import ContentVisuals from '../ContentVisuals.vue';
import ContentVisualEditor from '../ContentVisualEditor.vue';
import type { ContentVisual } from '../../model/content-visuals';
const props=defineProps<{domainId:string;objectId:string;initial?:Knowledge}>();
const emit=defineEmits<{saved:[id:string];open:[kind:Kind,id:string];back:[]}>();
const visualEditor=ref<{value?:ContentVisual}|null>(null);
function saveVisual(value:ContentVisual){const list=draft.value.visuals??=[],i=list.findIndex(v=>v.id===value.id);if(i<0)list.push(value);else list[i]=value;visualEditor.value=null;}
const empty=blankKnowledge(props.domainId);
const knowledge=computed(()=>domainData.knowledge.find(k=>k.id===props.objectId&&k.domainId===props.domainId)||props.initial||empty);
const draft=ref(clone(knowledge.value)),editing=ref(props.objectId==='new');
const methods=computed(()=>domainData.methods.filter(m=>m.domainId===props.domainId&&m.kc.includes(knowledge.value.id)));
const tasks=computed(()=>domainData.tasks.filter(t=>t.domainId===props.domainId&&collectKnowledge(t.methods,props.domainId).rows.some(r=>r.knowledge.id===knowledge.value.id)));
function edit(){draft.value=clone(knowledge.value);editing.value=true;}
function cancel(){editing.value=false;if(props.objectId==='new')emit('back');}
function save(){if(!draft.value.name.trim())return;saveEntity(domainData.knowledge,draft.value);editing.value=false;emit('saved',draft.value.id);}
</script>
<template><div>
  <header class="page-header"><div><span class="object-type">KnowledgeComponent <span v-if="knowledge.version">· {{knowledge.id}} · v{{knowledge.version}}</span></span><h2>{{knowledge.name||'新建知识成分'}}</h2><p class="page-desc">定义知识及其适用条件；这里不维护学生的掌握状态。</p></div><div class="button-row"><button class="btn" @click="emit('back')">返回知识列表</button><button v-if="!editing" class="btn primary" @click="edit">编辑知识</button></div></header>
  <form v-if="editing" @submit.prevent="save"><section class="panel"><h3>知识定义</h3><label>知识名称<input v-model="draft.name" required/></label><label>定义与含义<textarea v-model="draft.description" rows="4"/></label><label>适用条件<textarea v-model="draft.conditions" rows="3"/></label><label>示例与边界说明<textarea v-model="draft.example" rows="3"/></label><h3>知识图表</h3><ContentVisuals :items="draft.visuals" editing metadata @edit="value=>visualEditor={value}" @remove="key=>draft.visuals=draft.visuals?.filter(v=>v.id!==key)"/><button type="button" class="btn" @click="visualEditor={}">添加知识图表</button></section>
    <footer class="editor-footer"><span class="muted">未完成定义可先保存；保存后显示缺口。</span><button type="button" class="btn" @click="cancel">取消</button><button class="btn primary">保存知识</button></footer></form>
  <template v-else><div v-if="knowledgeIssues(knowledge).length" class="callout amber" role="status"><strong>知识定义待补齐</strong><ul><li v-for="issue in knowledgeIssues(knowledge)" :key="issue">{{issue}}</li></ul></div><section class="panel"><h3>知识定义</h3><dl class="field-list"><dt>定义与含义</dt><dd>{{knowledge.description||'尚未填写'}}</dd><dt>适用条件</dt><dd>{{knowledge.conditions||'尚未填写'}}</dd><dt>示例与边界</dt><dd>{{knowledge.example||'尚未填写'}}</dd></dl><ContentVisuals :items="knowledge.visuals" metadata/></section>
    <section class="panel"><h3>引用这项知识的方法</h3><table v-if="methods.length" class="data-table"><thead><tr><th>方法</th><th>思路</th></tr></thead><tbody><tr v-for="m in methods" :key="m.id"><td><button class="text-link" @click="emit('open','solution',m.id)">{{m.name}}</button></td><td>{{m.description}}</td></tr></tbody></table><p v-else class="muted">尚未被方法引用，可继续补齐方法关联。</p></section>
    <section class="panel"><h3>通过方法涉及这项知识的任务</h3><p class="muted">引用知识不等于直接检验它。正式使用前，需核对至少一个任务的责任及方法能明确检验此知识；先导关系在任务中维护。</p><div class="relation-list"><button v-for="t in tasks" :key="t.id" class="text-link" @click="emit('open','task',t.id)">{{t.name}} →</button></div><p v-if="!tasks.length" class="muted">暂无关联任务；此列表由方法关系计算。</p></section>
  </template>
<ContentVisualEditor v-if="visualEditor" :value="visualEditor.value" @save="saveVisual" @close="visualEditor=null"/>
</div></template>
