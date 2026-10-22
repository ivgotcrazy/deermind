<script setup lang="ts">
import { computed, ref, nextTick, watch } from 'vue';
import type { useConversation } from '../useConversation';
import ChatMessageComp from './ChatMessage.vue';
import InputComposer from './InputComposer.vue';
const props=defineProps<{conversation:ReturnType<typeof useConversation>;collapsed:boolean;opening:boolean;hasSession:boolean}>();
const input=defineModel<string>({default:''});
const emit=defineEmits<{send:[text:string];toggleCollapse:[];history:[]}>();
const {data,busy,ready,checking,error,uncertain,sending}=props.conversation;
const scrollContainer=ref<HTMLElement>(),newContent=ref(false);
const disabled=computed(()=>props.opening||busy.value||!!uncertain.value||props.hasSession&&!ready.value);
const question=computed(()=>data.value?.turns.flatMap(t=>t.blocks||[]).find(b=>b.type==='question'&&b.id===data.value?.check));
const actions=computed(()=>data.value?.turns.filter(t=>t.role==='assistant').at(-1)?.suggestions||[]);
async function latest(){await nextTick();if(scrollContainer.value){scrollContainer.value.scrollTop=scrollContainer.value.scrollHeight;newContent.value=false;}}
watch(()=>[data.value?.turns.length,data.value?.phase],async()=>{const el=scrollContainer.value,near=!el||el.scrollHeight-el.scrollTop-el.clientHeight<140;await nextTick();if(near)void latest();else newContent.value=true;});
watch(()=>props.collapsed,v=>{if(!v)void latest();});
async function action(kind:string,text?:string,id?:string){if(kind==='help')text=input.value;if(!data.value){emit('send',kind==='check_request'?'请出一道分数应用的即时检查题。':'请出一道分数应用的练习题。');return;}await props.conversation.act(kind,text,id);}
</script>
<template><div class="chat-workspace" :class="{collapsed}">
 <div v-if="!collapsed" class="chat-header"><div class="mode-indicator" :class="checking?'problem':'lecture'"><span class="mode-icon">{{ checking?'✏️':'🦌' }}</span><span class="mode-text">{{ checking?'即时检查':data?'DeerMind · 分数的应用':'DeerMind' }}</span><span class="mode-note">{{ checking?'先独立试一试':data?'真实对话':'随时提问' }}</span></div></div>
 <div v-if="!collapsed" class="messages-container" ref="scrollContainer" @scroll="()=>{if(scrollContainer&&scrollContainer.scrollHeight-scrollContainer.scrollTop-scrollContainer.clientHeight<80)newContent=false;}"><div class="messages-inner">
 <div v-if="!data?.turns.length" class="welcome"><h2>你想先弄懂什么？</h2><p>直接说出你的问题，右侧的页面会留在这里。</p></div>
 <div v-if="checking&&question?.type==='question'" class="active-question" aria-label="正在检查"><span class="question-tag">即时检查 · 1 题</span><h3>先自己试一试</h3><p>{{ question.prompt }}</p><small>在下方写下答案和理由。需要帮助可以先结束检查。</small></div>
 <template v-else><ChatMessageComp v-for="msg in data?.turns" :key="msg.id" :message="msg" :disabled="disabled" :ended="data?.phase==='ended'" :answer="conversation.answer" @draft="conversation.setAnswer" @act="action"/></template>
 <div v-if="busy" class="typing-indicator" role="status"><div class="avatar">🦌</div><div class="typing-bubble"><span/><span/><span/></div><span class="wait-label">正在准备回复…</span></div>
 </div></div>
 <div class="delivery-status"><span v-if="busy && collapsed">DeerMind 正在准备回复…</span><button v-if="data?.pending" :disabled="sending" @click="action('cancel')">停止生成</button><button v-if="newContent&&!collapsed" @click="latest">有新回复 · 回到最新</button>
 <div v-if="data?.error" role="alert"><p>{{ data.error.message }}</p><button v-if="data.error.retryable" :disabled="disabled" @click="action('retry')">重试这次回复</button></div><div v-if="error||uncertain" role="alert"><p>{{ error||'上次请求的送达状态需要确认。' }}</p><button v-if="uncertain" :disabled="sending" @click="conversation.perform(uncertain)">确认或重发同一请求</button><button v-else @click="conversation.refresh">重新连接</button></div>
 </div>
 <div v-if="data?.phase==='ended'" class="saved-summary"><h3>这次交流已保存</h3><button :disabled="disabled" @click="action('resume')">继续这次交流</button><button @click="emit('history')">对话历史</button></div>
 <div v-else class="composer-wrapper"><InputComposer v-model="input" :context-actions="actions" :disabled="disabled" :collapsed="collapsed" :checking="checking" @send="emit('send',$event)" @toggle-collapse="emit('toggleCollapse')" @history="emit('history')" @action="action"/></div>
</div></template>

<style scoped>
.chat-workspace {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #f7f9fa;
  width: 100%;
  min-width: 0;
}

.chat-header {
  flex-shrink: 0;
  border-bottom: 1px solid #e1e8ed;
}
.mode-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 20px;
  font-size: 12px;
}
.mode-indicator.lecture { background: #e8f5ee; color: #1b4332; }
.mode-indicator.problem { background: #fef3e2; color: #8a5a1a; }
.mode-indicator.error-check { background: #fde8e8; color: #8a2a2a; }
.mode-indicator.review { background: #e8f0fe; color: #1e3a8a; }
.mode-indicator.qa { background: #e8f0f8; color: #1e3a5f; }
.mode-indicator.idle { background: #f0f4f7; color: #5a6b7a; }
.mode-icon { font-size: 14px; }
.mode-text { font-weight: 600; flex-shrink: 0; }
.mode-steps { display: flex; align-items: center; gap: 4px; margin-left: auto; font-size: 11px; }
.mode-steps span { padding: 2px 8px; border-radius: 8px; background: rgba(255,255,255,0.5); color: #7a8a9a; }
.mode-steps span.active { background: #2d6a4f; color: white; font-weight: 600; }
.mode-steps .sep { background: transparent; padding: 0; color: #9aab9a; }

.messages-container {
  flex: 1;
  overflow-y: auto;
  scroll-behavior: smooth;
  min-height: 0;
}
.messages-inner {
  max-width: 860px;
  margin: 0 auto;
  padding: 24px 20px 16px;
}
.typing-indicator { display: flex; gap: 12px; margin-bottom: 24px; align-items: flex-start; }
.typing-indicator .avatar { width: 36px; height: 36px; border-radius: 50%; background: #2d5a4a; display: flex; align-items: center; justify-content: center; font-size: 13px; flex-shrink: 0; }
.typing-bubble { background: #fff; border-radius: 12px; padding: 14px 18px; display: flex; gap: 5px; align-items: center; box-shadow: 0 1px 3px rgba(0,0,0,0.06); }
.typing-bubble span { width: 7px; height: 7px; background: #a0b0a8; border-radius: 50%; animation: bounce 1.2s infinite; }
.typing-bubble span:nth-child(2) { animation-delay: 0.15s; }
.typing-bubble span:nth-child(3) { animation-delay: 0.3s; }
@keyframes bounce { 0%, 60%, 100% { transform: translateY(0); opacity: 0.5; } 30% { transform: translateY(-5px); opacity: 1; } }

.composer-wrapper {
  width: 100%;
  flex-shrink: 0;
}

@media (max-width: 700px) {
  .messages-inner { padding: 16px 12px; }
  .mode-indicator { padding: 6px 12px; flex-wrap: wrap; gap: 6px; }
  .mode-steps { margin-left: 0; width: 100%; }
}

.chat-workspace{min-height:0}.mode-note{margin-left:auto;font-size:10px}.mode-text{flex-shrink:1;overflow-wrap:anywhere}.welcome{padding:16px 0;color:#3a5645;line-height:1.9}.welcome h2{font-size:21px}.welcome p{font-size:13px;color:#7a8b80}.messages-inner{padding:24px 22px}.active-question{padding:20px;background:white;border:1px solid #cfe0d5;border-radius:10px;line-height:1.9}.active-question h3{font-size:18px;margin:8px 0}.active-question small{color:#809084}.question-tag{font-size:11px;color:#2d6a4f}.wait-label{font-size:12px;color:#809084;align-self:center}.delivery-status{font-size:12px;color:#7a6a41;padding:0 18px;flex-shrink:0;max-height:140px;overflow:auto}.delivery-status>div{padding:10px 0}.delivery-status button,.saved-summary button{border:1px solid #d4e4dc;background:white;border-radius:6px;color:#2d6a4f;padding:5px 10px;cursor:pointer;margin:5px}.saved-summary{padding:16px 20px;background:#edf5ef;font-size:13px;flex-shrink:0}.saved-summary h3{margin-bottom:10px}

</style>
