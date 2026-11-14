<script setup lang="ts">
import { computed, ref } from 'vue';
import { domainData, clone, prerequisiteIssues, saveEntity, type Task, type TaskPrerequisite } from '../../model/domain';
import WorkbenchDialog from '../WorkbenchDialog.vue';
const props=defineProps<{task:Task}>();
const emit=defineEmits<{open:[id:string]}>();
const editing=ref(false),draft=ref<TaskPrerequisite[]>([]),selected=ref(''),error=ref('');
const choices=computed(()=>domainData.tasks.filter(t=>t.domainId===props.task.domainId&&t.id!==props.task.id&&!draft.value.some(d=>d.taskId===t.id)));
const methods=computed(()=>domainData.methods.filter(m=>props.task.methods.includes(m.id)&&m.domainId===props.task.domainId));
const name=(id:string)=>domainData.tasks.find(t=>t.id===id)?.name||id;
function edit(){draft.value=clone(props.task.prerequisites||[]);selected.value='';error.value='';editing.value=true;}
function add(){if(selected.value){draft.value.push({taskId:selected.value,reason:'',methodIds:[]});selected.value='';}}
function save(){const next={...props.task,prerequisites:draft.value};error.value=prerequisiteIssues(next).join('；');if(error.value)return;saveEntity(domainData.tasks,next);editing.value=false;}
</script>
<template><section class="panel"><header class="row-between"><h3>先导任务</h3><button class="text-link" @click="edit">编辑先导任务</button></header><p class="muted">用于发现需要回补的基础；不锁定学习入口，不传播掌握概率。</p><table v-if="task.prerequisites?.length" class="data-table" aria-label="先导任务"><thead><tr><th>先导任务</th><th>理由</th><th>适用方法</th></tr></thead><tbody><tr v-for="d in task.prerequisites" :key="d.taskId"><td><button class="text-link" @click="emit('open',d.taskId)">{{name(d.taskId)}}</button></td><td>{{d.reason}}</td><td>{{d.methodIds.length?d.methodIds.map(id=>methods.find(m=>m.id===id)?.name||id).join('、'):'全部方法'}}</td></tr></tbody></table><p v-else class="muted">尚未设置先导任务；旧知识先修和方法调用不会自动转换为先导关系。</p></section>
<WorkbenchDialog v-if="editing" title="编辑先导任务" wide @close="editing=false"><p v-if="error" class="callout danger" role="alert">{{error}}</p><div class="button-row"><label>选择任务<select v-model="selected" aria-label="选择任务"><option value="">请选择</option><option v-for="t in choices" :key="t.id" :value="t.id">{{t.name}}</option></select></label><button class="btn" :disabled="!selected" @click="add">添加先导任务</button></div><article v-for="(d,i) in draft" :key="d.taskId" class="entry-editor"><header class="row-between"><strong>{{name(d.taskId)}}</strong><button class="btn" @click="draft.splice(i,1)">移除</button></header><label>先导理由<textarea v-model="d.reason" rows="2"/></label><p>适用方法：不指定时适用于全部方法</p><label v-for="m in methods" :key="m.id" class="check-line"><input v-model="d.methodIds" type="checkbox" :value="m.id"/>{{m.name}}</label></article><footer class="dialog-footer"><button class="btn" @click="editing=false">取消</button><button class="btn primary" @click="save">保存先导关系</button></footer></WorkbenchDialog>
</template>
