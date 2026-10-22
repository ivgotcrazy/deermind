<script setup lang="ts">
import { ref } from 'vue';
import { state, submitMessage } from '../../../structure/state';
const props = defineProps<{scope:string;disabled?:boolean}>();
const input = defineModel<string>({default:''});
const emit = defineEmits<{send:[text:string];expand:[];history:[]}>();
const isExpanded=ref(false),fileInput=ref<HTMLInputElement>(),notice=ref('');
function send(){if(props.disabled)return;if(state.attachments[props.scope]){submitMessage(props.scope);notice.value='图片与说明已保存，可到错题本的待处理输入查看；尚未识别或判错。';return;}if(input.value.trim())emit('send',input.value);}
function key(e:KeyboardEvent){if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();send();}}
function attach(event:Event){const el=event.target as HTMLInputElement,file=el.files?.[0];el.value='';if(!file)return;if(!['image/png','image/jpeg','image/webp'].includes(file.type)||file.size>2*1024*1024){notice.value='请选择不超过 2 MB 的 JPG、PNG 或 WebP 图片。';return;}const scope=props.scope,reader=new FileReader();reader.onload=()=>state.attachments[scope]={name:file.name,data:String(reader.result)};reader.onerror=()=>notice.value='图片读取失败，请重试。';reader.readAsDataURL(file);}
</script>
<template><div class="bottom-bar-host"><p v-if="notice" class="input-notice" role="status">{{ notice }}</p><div v-if="state.attachments[scope]" class="attachment"><img :src="state.attachments[scope]!.data" alt="待录入题目"/><span>{{ state.attachments[scope]!.name }} · 仅本地保存，尚不支持读图</span><button @click="delete state.attachments[scope]">移除</button></div><div class="bottom-input-bar" :class="{expanded:isExpanded}"><button class="expand-btn" @click="emit('expand')" aria-label="展开聊天" title="展开聊天">💬</button><button class="expand-btn" @click="fileInput?.click()" :disabled="disabled" aria-label="拍照或上传题目">＋</button><div class="input-wrapper"><input v-model="input" @focus="isExpanded=true" @keydown="key" placeholder="有问题？直接问 DeerMind..." aria-label="向 DeerMind 提问" class="bar-input"/><button class="quick-hint" @click="emit('history')" aria-label="查看对话历史">⋯</button></div><button class="send-btn" :disabled="disabled||(!input.trim()&&!state.attachments[scope])" @click="send">{{ state.attachments[scope]?'保存题目输入':'发送' }}</button><input ref="fileInput" hidden type="file" accept="image/png,image/jpeg,image/webp" @change="attach"/></div></div></template>

<style scoped>
.bottom-input-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 20px;
  background: linear-gradient(135deg, #1a3a2e 0%, #244c40 100%);
  border-top: 1px solid #2d5a4a;
  flex-shrink: 0;
  box-shadow: 0 -2px 10px rgba(0,0,0,0.1);
}

.expand-btn {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: rgba(255,255,255,0.15);
  border: none;
  font-size: 16px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: background 0.15s;
}

.expand-btn:hover {
  background: rgba(255,255,255,0.25);
}

.input-wrapper {
  flex: 1;
  position: relative;
  display: flex;
  align-items: center;
}

.bar-input {
  width: 100%;
  background: rgba(255,255,255,0.12);
  border: 1px solid rgba(255,255,255,0.2);
  border-radius: 20px;
  padding: 9px 36px 9px 16px;
  font-size: 13px;
  color: #e8f0ec;
  font-family: inherit;
  transition: all 0.2s;
}

.bar-input::placeholder {
  color: rgba(232,240,236,0.5);
}

.bar-input:focus {
  outline: none;
  background: rgba(255,255,255,0.18);
  border-color: rgba(255,255,255,0.35);
}

.quick-hint {
  position: absolute;
  right: 8px;
  background: none;
  border: none;
  color: rgba(232,240,236,0.5);
  font-size: 18px;
  cursor: pointer;
  padding: 2px 6px;
  line-height: 1;
}

.quick-hint:hover {
  color: #e8f0ec;
}

.send-btn {
  background: #40916c;
  color: white;
  border: none;
  padding: 8px 18px;
  border-radius: 20px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  font-family: inherit;
  transition: all 0.15s;
  flex-shrink: 0;
}

.send-btn:hover:not(:disabled) {
  background: #52b788;
}

.send-btn:disabled {
  background: rgba(255,255,255,0.15);
  color: rgba(255,255,255,0.4);
  cursor: not-allowed;
}

@media (max-width: 700px) {
  .bottom-input-bar {
    padding: 8px 12px;
    gap: 8px;
  }
  .send-btn {
    padding: 7px 14px;
    font-size: 12px;
  }
}

.bottom-bar-host{flex-shrink:0;background:white}.bottom-input-bar{position:static!important;width:100%;transform:none!important;margin:0!important}.input-wrapper{min-width:0}.bar-input{min-width:0}.input-notice{font-size:12px;padding:8px 24px;color:#6b7f70}.attachment{display:flex;gap:10px;align-items:center;padding:8px 24px;font-size:12px}.attachment img{max-width:60px;max-height:50px}.attachment button{border:0;background:none;color:#2d6a4f}

</style>
