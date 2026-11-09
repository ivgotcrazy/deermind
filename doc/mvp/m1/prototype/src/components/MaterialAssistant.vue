<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue';
import type { MaterialFlow } from '../model/material-flow';
import { assistantState, sendToAssistant, acceptCandidate, type AssistantMessage } from '../model/material-assistant';
import { storageError } from '../model/imports';
import { clone, id } from '../model/domain';
const props=defineProps<{flow:MaterialFlow}>();
const emit=defineEmits<{preview:[id:string];adopted:[]}>();
const state=computed(()=>assistantState(props.flow)),list=ref<HTMLElement|null>(null),input=ref<HTMLTextAreaElement|null>(null),error=ref('');
const labels={pending:'待核对',adopted:'已采用',discarded:'未采用',superseded:'已由后续候选替代'};
watch(()=>state.value.messages.length,async()=>{await nextTick();if(list.value)list.value.scrollTop=list.value.scrollHeight;});
watch(()=>state.value.reference,async()=>{await nextTick();input.value?.focus();});
function send(){if(storageError.value)return;error.value='';sendToAssistant(props.flow,state.value.input);const last=state.value.messages.at(-1);if(last?.candidate)emit('preview',last.id);}
function adopt(m:AssistantMessage){if(storageError.value)return;error.value=acceptCandidate(props.flow,m);if(!error.value)emit('adopted');}
function retry(m:AssistantMessage){state.value.reference=m.reference?clone(m.reference):null;sendToAssistant(props.flow,m.retry||'',true);const last=state.value.messages.at(-1);if(last?.candidate)emit('preview',last.id);}
function attach(event:Event){
  const field=event.target as HTMLInputElement,files=Array.from(field.files||[]);field.value='';
  if(storageError.value||!files.length)return;
  if(files.some(f=>!(/\.pdf$/i.test(f.name)||f.type.startsWith('image/')))){error.value='请选择PDF或扫描图片。';return;}
  error.value='';state.value.messages.push({id:id('MSG'),role:'user',text:'补充材料：'+files.map(f=>f.name).join('、'),reference:state.value.reference?clone(state.value.reference):undefined});
  state.value.messages.push({id:id('MSG'),role:'assistant',text:'已记录补充材料的文件名（mock）。此原型未上传或识别文件，不能据此宣称附页已经解析；已有内容保持不变。'});
}
function continueCorrection(m:AssistantMessage){state.value.reference=m.reference?clone(m.reference):null;state.value.input='';input.value?.focus();}
</script>
<template>
  <aside v-if="!state.collapsed" class="panel material-assistant" aria-label="教材助手">
    <header class="row-between"><div><h3>教材助手</h3><small class="muted">持续对话 · Mock，未接入真实 Agent</small></div><button class="btn" @click="state.collapsed=true">收起助手</button></header>
    <div ref="list" class="assistant-messages" aria-label="教材助手对话">
      <article v-for="m in state.messages" :key="m.id" :class="['assistant-message',m.role]">
        <small>{{m.role==='user'?'你':'教材助手'}}</small><p v-if="m.reference" class="message-reference">引用：{{m.reference.title}}</p><p class="message-text">{{m.text}}</p>
        <div v-if="m.candidate" class="candidate-card" :data-candidate="m.id">
          <strong>修正结果</strong><span class="badge">{{labels[m.candidate.status]}}</span>
          <p>{{m.candidate.before.length}} 项原内容 → {{m.candidate.after.length}} 项候选</p>
          <ul><li v-for="e in m.candidate.after" :key="e.id">{{e.title}}</li></ul>
          <div class="button-row"><button class="btn" @click="emit('preview',m.id)">查看结果</button><template v-if="m.candidate.status==='pending'"><button class="btn primary" :disabled="!!storageError" @click="adopt(m)">采用结果</button><button class="btn" :disabled="!!storageError" @click="m.candidate.status='discarded'">不采用</button><button class="text-link" @click="continueCorrection(m)">继续修正</button></template></div>
          <small v-if="m.candidate.status==='adopted'" class="muted">只更新解析内容，尚未自动写入领域或章节关联。</small>
        </div>
        <button v-if="m.retry" class="btn" :disabled="!!storageError" @click="retry(m)">重试</button>
      </article>
    </div>
    <form class="assistant-composer" @submit.prevent="send">
      <div v-if="state.reference" class="composer-reference"><span>已引用：{{state.reference.title}}</span><button type="button" aria-label="移除对话引用" @click="state.reference=null">×</button></div>
      <p v-else class="muted">在右侧引用内容，或直接说明要核对什么。</p>
      <label class="sr-only" for="material-assistant-input">给教材助手的消息</label><textarea id="material-assistant-input" ref="input" v-model="state.input" rows="3" placeholder="例如：这里是两种解法，请分别提取。" @keydown.ctrl.enter.prevent="send"/>
      <p v-if="error||storageError" class="callout danger" role="alert">{{error||storageError}}</p>
      <footer class="row-between"><label class="btn attachment-control">补充材料<input type="file" accept=".pdf,image/*" multiple :disabled="!!storageError" @change="attach"/></label><button class="btn primary" :disabled="!state.input.trim()||!!storageError">发送</button></footer>
    </form>
  </aside>
</template>
<style scoped>
.material-assistant{padding:18px;display:flex;flex-direction:column;height:calc(100vh - 225px);min-height:520px;max-height:900px;position:sticky;top:12px;min-width:0}.material-assistant h3{margin:0 0 5px}.material-assistant header{gap:10px;padding-bottom:14px;border-bottom:1px solid #e0e8e3}.material-assistant header .btn{white-space:nowrap;padding:7px 9px}.assistant-messages{flex:1;overflow:auto;min-height:100px;padding:14px 2px;overscroll-behavior:contain}.assistant-message{padding:12px;background:#f5f8f6;border-radius:8px;margin-bottom:14px;overflow-wrap:anywhere}.assistant-message.user{background:#eaf3ee}.assistant-message>small{color:#60796a}.message-text{white-space:pre-wrap;line-height:1.75;margin:8px 0}.message-reference{font-size:12px;color:#52705e;border-left:2px solid #98b3a4;padding-left:8px}.candidate-card{background:white;border:1px solid #dce7df;border-radius:6px;padding:12px;margin-top:10px}.candidate-card .badge{margin-left:8px}.candidate-card ul{padding-left:18px}.candidate-card .button-row{display:flex;gap:8px;flex-wrap:wrap}.candidate-card small{display:block;margin-top:10px}.assistant-composer{border-top:1px solid #e0e8e3;padding-top:12px}.assistant-composer textarea{width:100%;box-sizing:border-box;resize:vertical}.assistant-composer footer{margin-top:8px}.composer-reference{display:flex;align-items:center;justify-content:space-between;gap:8px;background:#edf5ef;padding:8px;font-size:12px;margin-bottom:8px}.composer-reference button{border:0;background:none;font-size:20px;cursor:pointer}.attachment-control{position:relative;overflow:hidden;cursor:pointer;margin:0}.attachment-control input{position:absolute;inset:0;opacity:0;cursor:pointer;width:100%;height:100%}.sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0)}@media(max-width:800px){.material-assistant{position:static;height:480px;min-height:0}}
</style>
