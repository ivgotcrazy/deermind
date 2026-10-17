<script setup lang="ts">
import { ref, watch } from 'vue';
import { state, submitMessage } from './state';
const props=defineProps<{scope:string;context:string;parent?:boolean;home?:boolean;inline?:boolean;checking?:boolean}>();
const open=ref(false),notice=ref(''),fileInput=ref<HTMLInputElement>();
watch(()=>props.scope,()=>{open.value=false;notice.value='';});
function send(){if(!state.drafts[props.scope]?.trim()&&!state.attachments[props.scope])return;submitMessage(props.scope);notice.value='输入已保存在这个上下文。此输入入口尚未理解或执行请求；章节对话可使用真实模型。';}
function enter(e:KeyboardEvent){if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();send();}}
function attach(event:Event){
 const input=event.target as HTMLInputElement,file=input.files?.[0];input.value='';if(!file)return;
 if(!['image/jpeg','image/png','image/webp'].includes(file.type)||file.size>2*1024*1024){notice.value='请选择不超过 2 MB 的 JPG、PNG 或 WebP 图片。';return;}
 const scope=props.scope,reader=new FileReader();
 reader.onload=()=>{state.attachments[scope]={name:file.name,data:String(reader.result)};if(props.scope===scope)notice.value='图片仅在本地预览与保存，尚未识别题目。';};
 reader.onerror=()=>{if(props.scope===scope)notice.value='图片读取失败，请重新选择。';};reader.readAsDataURL(file);
}
</script>
<template>
 <section class="composer" :class="{'home-composer':home}" aria-label="随时输入">
  <div class="composer-label"><span>{{ checking?'检查进行中 · 请在题目内填写并提交作答':home?'有自己的问题？直接告诉我':inline?'继续这次交流':context }}</span><button v-if="!inline" class="text" @click="open=!open" :aria-expanded="open">{{ open?'收起历史':'对话历史' }}</button><small v-else>消息直接出现在上方</small></div>
  <div v-if="state.attachments[scope]" class="attachment-preview"><img :src="state.attachments[scope]!.data" :alt="state.attachments[scope]!.name"/><span>{{ state.attachments[scope]!.name }}</span><button class="text" @click="delete state.attachments[scope]">移除图片</button></div>
  <form @submit.prevent="send"><textarea v-model="state.drafts[scope]" rows="1" :aria-label="parent?'家长咨询输入':'向 DeerMind 提问'" :placeholder="checking?'补充说明只保存；需要解题帮助请点题目中的求助按钮':parent?'想了解什么？可以就当前情况询问…':home?'这道题卡住了，或这个知识点没弄明白…':'说说哪里没想明白，或你想做什么…'" @keydown="enter"/><button class="primary send" :disabled="!state.drafts[scope]?.trim()&&!state.attachments[scope]" aria-label="发送">↑</button></form>
  <div v-if="home" class="composer-tools"><button class="text" @click="fileInput?.click()"><svg viewBox="0 0 20 20" aria-hidden="true"><path d="M3 5h3l1-2h6l1 2h3v12H3z"/><circle cx="10" cy="10" r="3"/></svg>带一道题</button><input ref="fileInput" class="visually-hidden" type="file" accept="image/jpeg,image/png,image/webp" capture="environment" aria-label="选择题目图片" @change="attach"/><span class="muted small">文字或图片 · 本地保存，尚未接入语音</span></div>
  <p v-if="notice" role="status" class="muted small">{{ notice }}</p>
  <div v-if="open&&!inline" class="message-history"><p v-if="!state.messages[scope]?.length" class="muted">这个上下文还没有对话。</p><article v-for="m in state.messages[scope]" :key="m.id"><small>{{ m.at }} · 我的输入</small><p>{{ m.text }}</p><img v-if="m.attachment" :src="m.attachment.data" :alt="m.attachment.name" class="request-image"/></article></div>
 </section>
</template>
