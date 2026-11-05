<script setup lang="ts">
import { ref } from 'vue';
import { clone, id } from '../model/domain';
import { visualIssues, type ContentVisual } from '../model/content-visuals';
import WorkbenchDialog from './WorkbenchDialog.vue';
const props=defineProps<{value?:ContentVisual;owner?:string;owners?:{id:string;name:string}[];taskOwner?:string}>();
const emit=defineEmits<{save:[value:ContentVisual,owner:string];close:[]}>();
const draft=ref<ContentVisual>(props.value?clone(props.value):{id:id('FIG'),title:'',kind:'relation',description:'',origin:'人工整理',sourceNote:'',nodes:['',''],links:['']});
const selectedOwner=ref(props.owner||''),error=ref(''),taskConfirmed=ref(false);
function changeKind(){if(draft.value.kind==='table')draft.value.table??={headers:['',''],rows:[['','']]};if(draft.value.kind==='relation'){draft.value.nodes??=['',''];draft.value.links??=[''];}}
function save(){
  const issues=visualIssues([draft.value]);
  if(props.owners&&!props.owners.some(o=>o.id===selectedOwner.value))issues.push('请选择这份图表所属的内容');
  if(props.taskOwner&&selectedOwner.value===props.taskOwner&&!taskConfirmed.value)issues.push('请确认图表属于原题给定内容，或学生需要处理的题面，不含额外解题提示');
  if(issues.length){error.value=issues.join('；');return;}emit('save',clone(draft.value),selectedOwner.value);
}
</script>
<template><WorkbenchDialog title="编辑图表" wide @close="emit('close')"><p v-if="error" class="callout danger" role="alert">{{error}}</p>
  <label v-if="owners">所属内容<select aria-label="所属内容" v-model="selectedOwner" @change="taskConfirmed=false"><option value="">请选择</option><option v-for="o in owners" :key="o.id" :value="o.id">{{o.name}}</option></select></label>
  <p v-if="taskOwner&&selectedOwner===taskOwner" class="callout amber">题面会在作答前展示。辅助线、解题步骤和额外分析图应放入解法或教学辅助展示。</p>
  <label>图表名称<input v-model="draft.title"/></label><label>表达的内容<textarea v-model="draft.description" rows="3"/></label>
  <label>表达形式<select aria-label="表达形式" v-model="draft.kind" @change="changeKind"><option value="relation">关系图</option><option value="table">表格</option><option value="description">图形说明（待补绘）</option></select></label>
  <template v-if="draft.kind==='relation'"><div class="edit-pair"><label v-for="(_,i) in draft.nodes" :key="i">对象 {{i+1}}<input v-model="draft.nodes![i]"/></label><label v-for="(_,i) in draft.links" :key="'link'+i">连接 {{i+1}}<input v-model="draft.links![i]"/></label></div><div class="button-row"><button type="button" class="btn" @click="draft.nodes!.push('');draft.links!.push('')">添加对象</button><button type="button" class="btn" :disabled="draft.nodes!.length<=2" @click="draft.nodes!.pop();draft.links!.pop()">移除末个对象</button></div></template>
  <div v-if="draft.kind==='table'&&draft.table" class="table-scroll"><table class="data-table"><thead><tr><th v-for="(_,i) in draft.table.headers" :key="i"><input v-model="draft.table.headers[i]" :aria-label="'图表表头 '+(i+1)"/></th></tr></thead><tbody><tr v-for="(row,i) in draft.table.rows" :key="i"><td v-for="(_,j) in row" :key="j"><input v-model="row[j]" :aria-label="'图表数据 '+(i+1)+' '+(j+1)"/></td></tr></tbody></table><div class="button-row"><button type="button" class="btn" @click="draft.table.rows.push(draft.table.headers.map(()=>''))">添加行</button><button type="button" class="btn" @click="draft.table.headers.push('');draft.table.rows.forEach(r=>r.push(''))">添加列</button><button type="button" class="btn" :disabled="draft.table.rows.length<=1" @click="draft.table.rows.pop()">移除末行</button><button type="button" class="btn" :disabled="draft.table.headers.length<=1" @click="draft.table.headers.pop();draft.table.rows.forEach(r=>r.pop())">移除末列</button></div></div>
  <div class="edit-pair"><label>图表来源<select aria-label="图表来源" v-model="draft.origin"><option>教材提取</option><option>系统生成</option><option>人工整理</option><option>来源待确认</option></select></label><label>来源说明<input v-model="draft.sourceNote"/></label></div>
  <label v-if="taskOwner&&selectedOwner===taskOwner" class="check-line"><input v-model="taskConfirmed" type="checkbox"/>已核对：这是题面内容，没有额外解题提示</label>
  <footer class="dialog-footer"><button type="button" class="btn" @click="emit('close')">取消</button><button type="button" class="btn primary" @click="save">保存图表</button></footer>
</WorkbenchDialog></template>
