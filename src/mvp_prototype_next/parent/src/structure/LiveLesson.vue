<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue';
import { state, touchSession } from './state';
import type { Session } from './state';
import { liveRequest, LiveRequestError } from './live';
import type { LiveSession, LiveCommand } from './live';
const props=defineProps<{session:Session;integrated?:boolean}>();
const emit=defineEmits<{home:[]}>();
const data=ref<LiveSession>(),error=ref(''),sending=ref(false),scroll=ref<HTMLElement>(),newContent=ref(false);
const draftKey=`real:${props.session.id}`;
const draft=computed({get:()=>state.drafts[draftKey]||'',set:(v:string)=>{state.drafts[draftKey]=v;}});
const busy=computed(()=>sending.value||!!data.value?.pending);
const checking=computed(()=>data.value?.phase==='check');
const currentQuestion=computed(()=>data.value?.turns.flatMap(t=>t.blocks||[]).find(b=>b.type==='question'&&b.id===data.value?.check));
const suggestions=computed(()=>data.value?.turns.filter(t=>t.role==='assistant').at(-1)?.suggestions||[]);
const elapsed=ref(0);
let disposed=false,timer:ReturnType<typeof setTimeout>|undefined,clock:ReturnType<typeof setInterval>|undefined;
let uncertain:LiveCommand|undefined;
const uncertainKey=`real-request:${props.session.id}`;
try { if(state.drafts[uncertainKey]) uncertain=JSON.parse(state.drafts[uncertainKey]!); } catch {}
const uncertainRequest=ref(!!uncertain);
function remember(command?:LiveCommand){uncertain=command;uncertainRequest.value=!!command;if(command)state.drafts[uncertainKey]=JSON.stringify(command);else delete state.drafts[uncertainKey];}
function answerDraft(id:string){return state.drafts[`${draftKey}:${id}`]||'';}
function setAnswer(id:string,value:string){state.drafts[`${draftKey}:${id}`]=value;}
function latest(){if(scroll.value){scroll.value.scrollTop=scroll.value.scrollHeight;newContent.value=false;}}
async function accept(value:LiveSession,force=false){
  if(disposed)return;
  if(data.value&&Date.parse(value.updatedAt)<Date.parse(data.value.updatedAt))return;
  const nearEnd=!scroll.value||scroll.value.scrollHeight-scroll.value.scrollTop-scroll.value.clientHeight<140;
  const changed=data.value?.turns.length!==value.turns.length||data.value?.phase!==value.phase;
  data.value=value; props.session.status=value.phase==='ended'?'ended':value.phase==='check'?'check':'learning';
  props.session.endedReason=value.phase==='ended'?'真实对话已暂停':'';
  props.session.realTurns=value.turns.length;
  props.session.updatedAt=Date.parse(value.updatedAt);
  if(changed){await nextTick();if(nearEnd||force)latest();else newContent.value=true;}
}
async function refresh(){clearTimeout(timer);try{await accept(await liveRequest<LiveSession>(`sessions/${props.session.id}`));}catch(e){error.value=(e as Error).message;}finally{if(!disposed)timer=setTimeout(refresh,data.value?.pending?800:4000);}}
async function perform(command:LiveCommand){
  sending.value=true;error.value='';remember(command);
  try {
    await accept(await liveRequest<LiveSession>(`sessions/${props.session.id}/commands`,command),true);
    remember();
    if(['message','help','answer'].includes(command.kind)&&draft.value.trim()===command.text?.trim())draft.value='';
    touchSession(props.session);
  }catch(e){if(e instanceof LiveRequestError&&e.status<500){remember();error.value=e.message;}else error.value=`${(e as Error).message} 若请求已经送达，重发同一请求不会重复调用模型。`;}
  finally{sending.value=false;}
}
async function act(kind:string,text?:string,questionId?:string){if(sending.value)return;await perform({requestId:crypto.randomUUID(),kind,...(text?{text}:{}),...(questionId?{questionId}:{})});}
async function send(){if(!draft.value.trim()||busy.value||uncertainRequest.value)return;await act(checking.value?'answer':'message',draft.value,data.value?.check||undefined);}
function keydown(e:KeyboardEvent){if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();void send();}}
onMounted(()=>{void (async()=>{await refresh();if(props.integrated&&uncertain&&!disposed)await perform(uncertain);})();clock=setInterval(()=>{elapsed.value=data.value?.pending?Math.max(0,Math.floor((Date.now()-Date.parse(data.value.pending.startedAt))/1000)):0;},1000);});
onUnmounted(()=>{disposed=true;clearTimeout(timer);clearInterval(clock);});
</script>

<template><section class="live-workspace" aria-label="真实模型学习对话">
  <header class="live-heading"><div><h1>DeerMind</h1><p>校内数学 · 分数的应用{{ checking?' · 正在检查':'' }}</p></div><div class="live-actions"><button v-if="!checking" @click="emit('home')">返回首页</button><button v-if="data?.phase!=='ended'" :disabled="busy||uncertainRequest" @click="act('end')">这次先到这里</button></div></header>
  <div ref="scroll" class="live-scroll" @scroll="()=>{if(scroll&&scroll.scrollHeight-scroll.scrollTop-scroll.clientHeight<80)newContent=false;}">
    <div v-if="!data&&!error" class="empty">正在恢复对话…</div>
    <section v-if="data&&!data.turns.length" class="live-welcome"><h2>你想先弄懂什么？</h2><p>可以直接说困惑，也可以输入一道题。我们一边讨论，一边试着解决。</p><div class="live-actions"><button :disabled="busy||uncertainRequest" @click="act('message','甲有12张卡片，乙有9张。为什么甲比乙多几分之几要除以9？')">为什么要除以比较的标准量？</button><button :disabled="busy||uncertainRequest" @click="act('message','我想学懂分数的应用，请先帮我确定一个合适的开始点。')">帮我找个开始点</button></div></section>
    <article v-if="checking&&currentQuestion?.type==='question'" class="live-turn assistant" aria-label="正在检查"><div class="live-speaker">DeerMind</div><div class="live-body"><span class="tag">即时检查 · 1 题</span><h2>先自己试一试</h2><p class="live-prose">{{ currentQuestion.prompt }}</p><p class="muted small">此前讲解暂时收起。直接在下方写答案和理由；提交后结束这道检查，再给反馈。需要帮助可以结束检查后求助。</p></div></article>
    <template v-else><article v-for="turn in data?.turns" :key="turn.id" class="live-turn" :class="turn.role"><div class="live-speaker">{{ turn.role==='user'?'你':'DeerMind' }}<small v-if="turn.metrics">{{ (turn.metrics.ms/1000).toFixed(1) }} 秒</small></div><div class="live-body"><p v-if="turn.role==='user'" class="live-prose">{{ turn.displayText||turn.text }}</p><template v-for="(block,index) in turn.blocks" :key="index">
      <p v-if="block.type==='text'" class="live-prose">{{ block.text }}</p>
      <div v-else-if="block.type==='formula'" class="live-formula">{{ block.text }}</div>
      <figure v-else-if="block.type==='bars'" class="live-bars" :aria-label="block.caption"><figcaption>{{ block.caption }}</figcaption><div v-for="row in block.rows" :key="row.label" class="live-bar-row"><span>{{ row.label }}</span><div><i :style="{width:`${100*row.value/Math.max(...block.rows.map(r=>r.value))}%`}"/></div><b>{{ row.value }}</b></div></figure>
      <section v-else-if="block.type==='question'" class="live-question" :aria-label="block.mode==='check'?'检查安排':'随堂练习'"><span class="tag">{{ block.mode==='check'?'即时检查':'随堂练习' }}</span><p class="live-prose">{{ block.prompt }}</p>
        <template v-if="block.state==='offered'&&data?.phase!=='ended'"><template v-if="block.mode==='practice'"><label class="field">写下答案或思路<textarea :value="answerDraft(block.id)" @input="setAnswer(block.id,($event.target as HTMLTextAreaElement).value)" rows="3" aria-label="练习答案"/></label><button class="primary" :disabled="busy||!answerDraft(block.id).trim()||uncertainRequest" @click="act('answer',answerDraft(block.id),block.id)">提交这道练习</button></template><template v-else><p class="muted small">开始后暂时收起前面的讲解。你可以提交答案，或随时求助并结束检查。</p><button class="primary" :disabled="busy||uncertainRequest" @click="act('start_check',undefined,block.id)">开始这道检查</button></template></template>
        <p v-else class="muted small">{{ block.state==='answered'?'已提交，原作答保留在对话中':block.state==='helped'?'已结束检查并求助，未记为错误':block.state==='skipped'?'已跳过，未作答':data?.phase==='ended'?'对话已暂停，可继续后作答':'' }}</p>
      </section>
    </template></div></article></template>
    <div v-if="data?.pending" class="live-wait" role="status">DeerMind 正在准备回复<span v-if="elapsed"> · {{ elapsed }} 秒</span>…<button @click="act('cancel')" :disabled="sending">停止生成</button></div>
    <div v-if="data?.error" role="alert" class="live-error"><p>{{ data.error.message }}</p><button v-if="data.error.retryable" :disabled="busy||uncertainRequest" @click="act('retry')">重试这次回复</button></div>
    <div v-if="error||uncertainRequest" role="alert" class="live-error"><p>{{ error||'上次请求的送达状态需要确认。' }}</p><button v-if="uncertainRequest" :disabled="sending" @click="uncertain&&perform(uncertain)">确认或重发同一请求</button><button v-else @click="refresh">重新连接</button></div>
    <section v-if="data?.phase==='ended'" class="live-summary"><h2>这次交流已保存</h2><p>可以回来接着聊。模型对本次作答的反馈不代表已形成长期掌握。</p><button class="primary" :disabled="busy||uncertainRequest" @click="act('resume')">继续这次交流</button><button @click="emit('home')">回到首页</button></section>
  </div>
  <button v-if="newContent" class="live-latest" @click="latest">有新回复 · 回到最新</button>
  <footer v-if="data?.phase!=='ended'" class="live-composer"><div v-if="data?.turns.length&&!checking" class="live-suggestions"><button v-for="suggestion in suggestions" :key="suggestion" :disabled="busy||uncertainRequest" @click="act('message',suggestion)">{{ suggestion }}</button><button :disabled="busy||uncertainRequest" @click="act('practice_request')">出一道练习</button><button :disabled="busy||uncertainRequest" @click="act('check_request')">检查这次理解</button></div><form @submit.prevent="send"><textarea v-model="draft" rows="2" :aria-label="checking?'检查答案':'向真实 DeerMind 提问'" :placeholder="checking?'写下答案，也说说你是怎么想的…':'哪里不明白？随时追问，也可以说“换一种讲法”…'" @keydown="keydown"/><button class="primary" type="submit" :disabled="busy||!draft.trim()||uncertainRequest||!data">{{ checking?'提交并结束检查':'发送' }}</button></form><div class="live-composer-note"><small>Enter 发送 · Shift + Enter 换行{{ checking?'':' · 回复完成后再继续下一轮' }}</small><button v-if="checking" class="text" :disabled="busy||uncertainRequest" @click="act('help',draft)">求助并结束检查</button></div></footer>
</section></template>

<style scoped>
.live-workspace{display:flex;flex-direction:column;min-height:0;height:100%;position:relative}.live-heading{display:flex;align-items:center;justify-content:space-between;gap:16px;flex-shrink:0;border-bottom:1px solid #e0e6ed;padding:16px 24px}.live-heading h1{font-size:21px;margin:0 0 3px}.live-heading p{font-size:11px;margin:0;color:#69788c}.live-dot{display:inline-block;width:6px;height:6px;background:#388a71;border-radius:50%;margin-right:4px}.live-actions{display:flex;gap:10px;flex-wrap:wrap}.live-actions button{font-size:12px}.live-scroll{flex:1;min-height:0;overflow:auto;overscroll-behavior:contain;padding:20px 28px 30px;scrollbar-gutter:stable}.live-disclosure{font-size:11px;color:#778294;margin:0 0 26px}.live-welcome{padding:25px 0 30px}.live-welcome h2{font-size:24px}.live-welcome p{color:#63748a}.live-turn{display:flex;gap:24px;margin:0 0 28px}.live-speaker{width:72px;flex-shrink:0;font-size:12px;color:#60728c;padding-top:5px}.live-speaker small{font-size:10px;margin-top:5px;color:#96a0b0}.live-body{flex:1;min-width:0}.live-turn.user .live-body{background:#edf2f8;padding:14px 18px;border-radius:10px}.live-prose{white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.9;margin-bottom:14px}.live-prose:last-child{margin-bottom:0}.live-formula{white-space:pre-wrap;overflow-wrap:anywhere;font-size:19px;padding:16px 20px;background:#f0f4fa;border-left:3px solid #9aaecf;border-radius:4px;margin:14px 0}.live-bars{margin:20px 0;padding:18px;border:1px solid #dce4f0;border-radius:8px;background:#fff}.live-bars figcaption{font-size:12px;margin-bottom:15px;color:#60728c}.live-bar-row{display:flex;gap:12px;align-items:center;font-size:12px;margin:10px 0}.live-bar-row>span{width:90px;overflow-wrap:anywhere}.live-bar-row>div{flex:1;min-width:0}.live-bar-row i{display:block;height:20px;background:#7999be;border-radius:3px}.live-bar-row b{min-width:30px;font-weight:500}.live-question,.live-check{background:#fff;border:1px solid #ccd9ea;padding:20px;border-radius:10px;margin:18px 0}.live-question>.tag,.live-check>.tag{display:inline-block;margin-bottom:14px}.live-check{max-width:760px;margin:12px auto}.live-composer{flex-shrink:0;padding:12px 24px 16px;background:#fff;border-top:1px solid #dce4ed}.live-composer form{display:flex;align-items:flex-end;gap:12px}.live-composer textarea{flex:1;min-width:0;max-height:160px;resize:vertical;background:#f8fafd}.live-composer small{font-size:10px;margin-top:6px;color:#8b97a6}.live-suggestions{display:flex;gap:8px;flex-wrap:wrap;max-height:82px;overflow:auto;margin-bottom:10px}.live-suggestions button{font-size:11px;padding:5px 10px}.live-wait{display:flex;align-items:center;gap:15px;font-size:13px;color:#546d91;margin:18px 0}.live-wait button{font-size:12px}.live-error{padding:16px;border:1px solid #e7cfb1;background:#fff9f0;border-radius:7px;margin:15px 0;font-size:13px}.live-summary{padding:20px;background:#edf4f3;border-radius:8px;margin:20px 0}.live-summary button{margin-right:10px}.live-latest{position:absolute;right:30px;bottom:170px;background:#e7effb;font-size:12px;box-shadow:0 2px 10px #39476822}
.live-composer-note{display:flex;align-items:center;justify-content:space-between;gap:12px}.live-composer-note button{font-size:12px}.live-turn[aria-label="正在检查"] .tag{display:inline-block;margin-bottom:14px}.live-heading h1{font-size:21px;letter-spacing:-.6px}
@media(max-width:700px){.live-heading{padding:12px 14px;align-items:flex-start}.live-heading h1{font-size:18px}.live-heading .live-actions{gap:5px;max-width:180px;justify-content:flex-end}.live-heading button{padding:6px 9px;font-size:11px}.live-scroll{padding:16px 14px}.live-turn{gap:9px}.live-speaker{width:51px;font-size:10px}.live-body{font-size:14px}.live-composer{padding:10px 14px}.live-question{padding:14px}.live-bar-row>span{width:60px}.live-formula{font-size:16px;padding:12px}.live-suggestions{max-height:64px}.live-composer form>button{max-width:100px;font-size:12px}.live-composer-note small{font-size:9px}}
</style>
