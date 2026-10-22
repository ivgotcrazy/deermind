<script setup lang="ts">
import { ref,computed } from 'vue';
import { state, mode, annotate, invalidateEvidence, act } from '../workbench/store';
const props=defineProps<{subject:string;evidence?:string}>();const text=ref('');
const notes=computed(()=>state.annotations.filter(n=>n.subject===props.subject&&n.mode===mode.value));
const legacy=computed(()=>state.issues.filter(i=>i.origin===props.subject&&i.dataMode===mode.value));
function save(){annotate(props.subject,text.value);text.value='';}
</script>
<template><section class="panel"><h3>核对记录</h3><div class="list-row" v-for="n in notes" :key="n.id"><p>{{n.text}}</p><small>{{n.at}}</small></div><div v-for="i in legacy" :key="i.id" class="list-row"><p>{{i.finding}} {{i.conclusion||i.purpose}}</p><small>历史记录 {{i.id}}</small></div><label>核对意见<textarea v-model="text" placeholder="记录观察到的问题、判断依据或后续建议"/></label><div class="button-row"><button class="btn" @click="act(save)">保存意见</button><button v-if="evidence && !state.invalidated[evidence]" class="btn danger-btn" @click="act(()=>{invalidateEvidence(evidence!,text,subject);text=''})">停止使用此依据及依赖结果</button></div><p v-if="evidence" class="muted">停止使用须填写依据；保留原记录并标记待重新推断，不手填新的能力判断。</p></section></template>
