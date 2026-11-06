<script setup lang="ts">
import { ref, watch } from 'vue';
import WorkbenchDialog from './WorkbenchDialog.vue';
import { clone } from '../model/domain';
import { aspectRule, evaluationData, methodName, saveDefinition, type AspectRule, type Claim } from '../model/evaluation';

const props=defineProps<{claim:Claim;methodId:string;blocked:boolean}>();
const emit=defineEmits<{saved:[message:string]}>();
const draft=ref<AspectRule>();
const error=ref('');
watch(()=>[props.claim.id,props.methodId],()=>{draft.value=undefined;});
function edit(aspectId:string){
  draft.value=clone(aspectRule(props.claim,props.methodId,aspectId));
  error.value='';
}
function save(){
  if(!draft.value||props.blocked||draft.value.methodId!==props.methodId)return;
  if(!draft.value.judgment.trim()||!draft.value.condition.trim()){
    error.value='请填写判断要求和需要的证据。';return;
  }
  const next=clone(props.claim);
  const rule=draft.value;
  next.rules=next.rules.filter(r=>r.methodId!==rule.methodId||r.aspectId!==rule.aspectId);
  next.rules.push(clone(rule));
  if(saveDefinition(evaluationData.claims,next,'修改「'+methodName(rule.methodId)+'」的评价方面规则')){
    draft.value=undefined;
    emit('saved','评价规则已保存。');
  }
}
</script>

<template>
  <section class="panel table-scroll" aria-label="四方面评价规则">
    <h3>四方面评价规则</h3>
    <table class="data-table aspect-rules">
      <thead><tr><th>评价方面</th><th>判断要求</th><th>需要的证据</th><th>操作</th></tr></thead>
      <tbody><tr v-for="a in claim.aspects.filter(a=>a.enabled)" :key="a.id" :data-aspect="a.id">
        <td><strong>{{a.name}}</strong></td>
        <td>{{aspectRule(claim,methodId,a.id).judgment||'待填写'}}</td>
        <td>{{aspectRule(claim,methodId,a.id).condition||'待填写'}}</td>
        <td><button class="btn" :disabled="blocked" :aria-label="'编辑'+a.name+'规则'" @click="edit(a.id)">编辑</button></td>
      </tr></tbody>
    </table>
  </section>
  <WorkbenchDialog v-if="draft" title="编辑评价规则" @close="draft=undefined">
    <strong>{{methodName(draft.methodId)}} · {{claim.aspects.find(a=>a.id===draft!.aspectId)?.name}}</strong>
    <p v-if="error" role="alert" class="callout danger">{{error}}</p>
    <label>判断要求<textarea v-model="draft.judgment" rows="3" :placeholder="draft.aspectId==='explanation'?'填写学生需要解释的关键关系或原理':'填写该方面要判断的表现'"/></label>
    <label>需要的证据<textarea v-model="draft.condition" rows="3"/></label>
    <footer class="dialog-footer"><button class="btn" @click="draft=undefined">取消</button><button class="btn primary" :disabled="blocked" @click="save">保存评价规则</button></footer>
  </WorkbenchDialog>
</template>
<style scoped>
.aspect-rules td{vertical-align:top;white-space:pre-wrap}.aspect-rules th:first-child{width:13%}.aspect-rules th:nth-child(2){width:40%}.aspect-rules th:nth-child(3){width:40%}
</style>
