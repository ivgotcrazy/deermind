<script setup lang="ts">
import { computed, ref } from 'vue';
import { parentState, parentScope, visibleThreads, sendParentMessage, removeParentThread, activeParent } from '../parentState';
const props=defineProps<{space:string;name:string}>();
const scope=computed(()=>parentScope(props.space));
const draft=computed({get:()=>parentState.drafts[scope.value]||'',set:(v:string)=>parentState.drafts[scope.value]=v});
const threads=computed(()=>visibleThreads(props.space));
const historyOpen=ref(false),notice=ref('');
function send(){if(!draft.value.trim())return;sendParentMessage(props.space);notice.value='已保存到你的私人咨询；尚未连接模型，没有生成回复，也没有改变学生记录或安排任务。';}
function remove(id:string){if(!confirm('删除这整段私人咨询？本端不可恢复，内部暂保留；孩子资料和独立提交的事项不变。'))return;removeParentThread(props.space,id);notice.value='这段咨询已从家长端删除，本端不可恢复。';}
function newThread(){delete parentState.active[scope.value];notice.value='下次发送将新开一段咨询。未发送草稿仍保留。';}
function enter(e:KeyboardEvent){if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();send();}}
</script>
<template><section class="f-inline-composer" aria-label="家长私人咨询">
 <div class="f-content-heading"><label for="parent-question">咨询孩子的学习情况</label><button @click="historyOpen=!historyOpen" :aria-expanded="historyOpen">{{ historyOpen?'收起历史':'对话历史' }}</button></div>
 <form @submit.prevent="send"><textarea id="parent-question" v-model="draft" rows="2" placeholder="说说你观察到的情况，或想了解的支持方式…" @keydown="enter"/><button type="submit" class="f-primary" :disabled="!draft.trim()">发送</button></form>
 <p class="f-muted">{{ activeParent?.name }} · {{ name }} · 私人咨询，不向孩子或其他家长共享。</p><p v-if="notice" role="status">{{ notice }}</p>
 <div v-if="historyOpen" class="f-parent-history"><button @click="newThread">另开一段咨询</button><p v-if="!threads.length">当前空间还没有可查看的咨询。</p><article v-for="t in threads" :key="t.id"><p v-for="(entry,i) in t.entries" :key="i">{{ entry.text }}</p><p class="f-muted">原型未连接模型，只有你的实际输入，没有生成咨询回复。</p><button @click="parentState.active[scope]=t.id">继续这段咨询</button><button @click="remove(t.id)">删除整段咨询</button></article></div>
</section></template>
