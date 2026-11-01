<script setup lang="ts">
import { computed, nextTick, onMounted, onBeforeUnmount, ref, watch } from 'vue';
import InputComposer from './InputComposer.vue';
import type { StudentCourse } from '../student-pages';
import { append, currentActivity, sendConversation, finishActivity, beginCheck, helpDuringCheck, confirmSwitch, sampleAnswer, type Conversation } from '../conversation';
const props=defineProps<{conversation:Conversation;course:StudentCourse;collapsed:boolean}>();
const emit=defineEmits<{toggleCollapse:[]}>();
const history=ref(false),query=ref(''),from=ref(''),until=ref(''),kind=ref('全部'),chapter=ref(''),filters=ref(false),focused=ref(''),limit=ref(40),resultLimit=ref(30);
const viewport=ref<HTMLElement|null>(null);
const atLatest=ref(true);let sizeObserver:ResizeObserver|undefined;
function trackScroll(){if(viewport.value&&!history.value)atLatest.value=viewport.value.scrollHeight-viewport.value.clientHeight-viewport.value.scrollTop<24;}
const c=computed(()=>props.conversation),active=computed(()=>currentActivity(c.value));
const reference=computed(()=>c.value.messages.find(m=>m.id===c.value.referenceId));
const quotedActivity=computed(()=>c.value.activities.find(a=>a.id===reference.value?.activityId));
const visibleMessages=computed(()=>c.value.messages.slice(-limit.value));
const lastOffer=computed(()=>c.value.messages.filter(m=>m.action==='offer').slice(-1)[0]?.id);
const results=computed(()=>c.value.messages.filter(m=>{
  const a=c.value.activities.find(a=>a.id===m.activityId);
  return m.role!=='event'&&(!query.value||`${m.text} ${a?.title||''}`.toLowerCase().includes(query.value.toLowerCase()))&&(!from.value||m.at.slice(0,10)>=from.value)&&(!until.value||m.at.slice(0,10)<=until.value)&&(!chapter.value||a?.chapters.includes(chapter.value))&&(kind.value==='全部'||(a?.kind||'一般交流')===kind.value);
}).slice().reverse());
watch([query,from,until,kind,chapter],()=>resultLimit.value=30);
async function latest(){history.value=false;focused.value='';atLatest.value=true;await nextTick();if(viewport.value)viewport.value.scrollTop=viewport.value.scrollHeight;}
async function locate(id:string){
  history.value=false;focused.value=id;limit.value=Math.max(limit.value,c.value.messages.length-c.value.messages.findIndex(m=>m.id===id));
  await nextTick();viewport.value?.querySelector<HTMLElement>('[data-message-id="'+id+'"]')?.scrollIntoView({block:'center'});
}
async function quote(id:string){c.value.referenceId=id;await latest();}
function send(text:string){
  if((history.value||focused.value)&&active.value?.kind==='检测'&&!reference.value){
    append(c.value,'user',text,active.value.id);append(c.value,'assistant','当前仍在检测。这条交流未作为答案提交；作答请在下方使用“提交答案”，需要讲解可点“求助并结束检测”。',active.value.id);c.value.draft='';
  }else sendConversation(c.value,text,props.course);
  void latest();
}
function end(){finishActivity(c.value);void latest();}
function startCheck(){beginCheck(c.value);void latest();}
function help(){helpDuringCheck(c.value);void latest();}
function acceptSwitch(){confirmSwitch(c.value);void latest();}
function cancelSwitch(){const r=c.value.pending;if(r){if(!c.value.draft)c.value.draft=r.text;c.value.referenceId=r.reference||'';}c.value.pending=undefined;}
function clearSearch(){query.value='';from.value='';until.value='';kind.value='全部';chapter.value='';}
watch(()=>c.value.messages.length,()=>{if(!history.value&&!focused.value&&atLatest.value)void latest();});
watch(()=>props.collapsed,v=>{if(!v&&!history.value&&!focused.value)void latest();});
watch(viewport,element=>{sizeObserver?.disconnect();if(element){sizeObserver=new ResizeObserver(()=>{if(atLatest.value&&!history.value&&!focused.value)element.scrollTop=element.scrollHeight;});sizeObserver.observe(element);}});
onMounted(()=>void latest());onBeforeUnmount(()=>sizeObserver?.disconnect());
defineExpose({locate,latest,send});
</script>

<template>
  <section class="continuous-chat" :class="{collapsed}">
    <header v-if="!collapsed" class="conversation-header">
      <div><strong>{{active?active.kind+'：'+active.title:'DeerMind'}}</strong><span class="prototype-note">持续对话 · 示例内容</span></div>
      <div class="header-actions"><button v-if="active" @click="end">{{active.kind==='检测'?'结束检测':'本次先到这里'}}</button><button :aria-pressed="history" @click="history=!history;focused=''">{{history?'返回对话':'历史'}}</button></div>
    </header>
    <div v-if="!collapsed && history" class="history-search">
      <div class="search-row"><input v-model="query" aria-label="搜索对话历史" placeholder="搜索说过的话、题目或章节"><button @click="filters=!filters">筛选</button></div>
      <div v-if="filters" class="history-filters">
        <label>开始日期<input v-model="from" type="date"></label><label>结束日期<input v-model="until" type="date"></label>
        <label>活动类型<select aria-label="历史活动类型" v-model="kind"><option>全部</option><option>讲解</option><option>检测</option><option>答疑</option><option>一般交流</option></select></label>
        <label>章节<select aria-label="历史章节" v-model="chapter"><option value="">全部章节</option><option v-for="ch in course.chapters" :key="ch.id" :value="ch.id">{{ch.name}}</option></select></label>
        <button @click="clearSearch">清除条件</button>
      </div>
      <p>仅查找 {{course.title}} · {{results.length}} 条交流</p>
    </div>
    <div v-if="!collapsed" ref="viewport" class="conversation-scroll" @scroll="trackScroll">
      <div v-if="history" class="history-results">
        <p v-if="from&&until&&from>until" role="alert">开始日期应早于或等于结束日期。</p>
        <p v-else-if="!results.length" class="empty">没有找到符合条件的交流。可以换个词，或清除筛选。</p>
        <button v-for="m in results.slice(0,resultLimit)" :key="m.id" class="history-result" :data-result-id="m.id" @click="locate(m.id)">
          <span class="message-meta">{{m.at}} · {{c.activities.find(a=>a.id===m.activityId)?.kind||'一般交流'}} · {{m.role==='user'?'你':'DeerMind'}}</span>
          <strong>{{c.activities.find(a=>a.id===m.activityId)?.title||'日常交流'}}</strong><span class="result-excerpt">{{m.text}}</span>
        </button>
        <button v-if="results.length>resultLimit" @click="resultLimit+=30">查看更多结果</button>
      </div>
      <div v-else class="conversation-messages">
        <button v-if="limit<c.messages.length" class="older" @click="limit+=40">查看更早的交流</button>
        <p v-if="!c.messages.length" class="empty">你可以直接提问，也可以从右侧选择内容。这些交流只保留在当前学习空间。</p>
        <template v-for="(m,i) in visibleMessages" :key="m.id">
          <div v-if="i===0 || visibleMessages[i-1]?.at.slice(0,10)!==m.at.slice(0,10)" class="date-divider">{{m.at.slice(0,10)}}</div>
          <article :data-message-id="m.id" :class="['conversation-message',m.role,{focused:focused===m.id}]">
            <template v-if="m.role==='event'"><span>{{m.text}}</span></template>
            <template v-else>
              <div class="message-meta">{{m.role==='user'?'你':'DeerMind'}} · {{m.at.slice(11)}}</div>
              <button v-if="m.reference" class="message-reference" @click="locate(m.reference)">引用：{{c.messages.find(x=>x.id===m.reference)?.text.slice(0,70)}}</button>
              <p class="message-text">{{m.text}}</p>
              <div v-if="m.action==='offer' && c.offer && lastOffer===m.id" class="check-actions"><button class="primary" @click="startCheck">开始检测</button><button @click="c.offer=undefined">暂不开始</button></div>
              <div v-if="m.action==='question' && active?.id===m.activityId && !focused && !c.referenceId" class="check-actions"><span>第 1／1 题 · 请在下方提交答案和理由</span><button @click="help">求助并结束检测</button></div>
              <button class="quote-action" @click="quote(m.id)">接着聊</button>
            </template>
          </article>
        </template>
      </div>
    </div>
    <div v-if="!collapsed && (focused||history||!atLatest)" class="history-location"><span>{{history?'正在查找历史，当前活动未改变':'正在回看历史，当前活动未改变'}}</span><button v-if="focused" @click="history=true">返回查找</button><button @click="latest">回到最新</button></div>
    <div v-if="c.pending" class="switch-confirm" role="dialog" aria-label="切换学习内容">
      <strong>结束当前检测，再开始其他内容？</strong><p>保留已提交的作答，未提交不计错。要转到：{{c.pending.title}}</p><div><button class="primary" @click="acceptSwitch">结束检测并切换</button><button @click="cancelSwitch">继续检测</button></div>
    </div>
    <div class="conversation-composer">
      <div v-if="collapsed && active" class="collapsed-activity">{{active.kind==='检测'?'检测中 · 第1／1题':active.kind+'：'+active.title}}</div>
      <div v-if="reference" class="composer-reference"><div><strong>接着聊：{{reference.at.slice(0,10)}} · {{quotedActivity?.title||'历史交流'}}</strong><p>{{reference.text}}</p></div><button aria-label="取消引用" @click="c.referenceId=''">×</button></div>
      <p v-if="history||focused" class="sending-location">输入将发送到最新位置；讨论历史内容，请先点“接着聊”。</p>
      <details v-if="!collapsed" class="mock-examples"><summary>试用示例</summary><div>
        <template v-if="active?.kind==='检测'&&!reference"><button @click="c.draft=sampleAnswer">填入示例作答</button><button @click="help">请求讲解</button></template>
        <template v-else-if="reference"><button v-if="quotedActivity?.status!=='已结束' && quotedActivity?.kind!=='检测'" @click="c.draft='继续上次进度'">继续上次进度</button><button @click="c.draft='为什么还要加上原来的量？'">追问这段内容</button></template>
        <template v-else><button v-for="text in (course.chapters.length?['为什么增加四分之一还要加原量？','先讲圆柱的表面积','出一道题检测一下','换个例子','今天先到这里']:['你好'])" :key="text" @click="c.draft=text">{{text}}</button></template>
      </div><p>按钮只填入示例文本，由你发送；未编写的回答会保留为待处理，不冒充真实模型判断。</p></details>
      <InputComposer :model-value="c.draft" @update:model-value="c.draft=$event" :context-actions="[]" :collapsed="collapsed" :disabled="!!c.pending"
        :send-label="active?.kind==='检测'&&!reference&&!history&&!focused?'提交答案':'发送'" :input-context="active?.kind==='检测'&&!reference&&!history&&!focused?'答案和理由':undefined"
        @send="send" @toggle-collapse="emit('toggleCollapse')"/>
    </div>
  </section>
</template>

<style scoped>
.continuous-chat{width:100%;min-width:0}
.conversation-composer :deep(.input-composer){padding-top:30px}
.continuous-chat{display:flex;flex-direction:column;height:100%;min-height:0;color:#234b42;background:#f7f9fa;font-size:14px}.continuous-chat button,.continuous-chat input,.continuous-chat select{font:inherit}.continuous-chat button{cursor:pointer;border:1px solid #cfdfd7;background:white;color:#28664f;border-radius:6px;padding:7px 10px}.continuous-chat button:hover{background:#eef6f1}.continuous-chat button.primary{background:#2d6a4f;color:white}.conversation-header{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:13px 20px;background:#edf6f1;border-bottom:1px solid #dce8e1}.conversation-header strong{display:block}.prototype-note{font-size:11px;color:#74877f;display:block;margin-top:4px}.header-actions{display:flex;gap:8px;flex-shrink:0}.conversation-scroll{flex:1;min-height:0;overflow-y:auto;scroll-behavior:auto}.conversation-messages{max-width:860px;margin:auto;padding:16px 24px 26px}.date-divider{text-align:center;color:#82928c;font-size:12px;margin:18px 0}.conversation-message{margin:14px 0;max-width:94%;padding:14px;border-radius:10px;background:white;border:1px solid #e0eae4;overflow-wrap:anywhere}.conversation-message.user{margin-left:auto;background:#eaf4ee}.conversation-message.event{border:0;background:transparent;max-width:none;text-align:center;color:#71857b;font-size:12px;padding:4px}.conversation-message.focused{outline:2px solid #94b7a3;background:#fffce9}.message-meta{font-size:12px;color:#7b8983}.message-text{white-space:pre-wrap;line-height:1.8;margin:8px 0}.continuous-chat .quote-action{border:0;background:transparent;color:#597a6b;font-size:12px;padding:3px 0}.message-reference{text-align:left;font-size:12px!important;border-left:3px solid #9dbfac!important}.check-actions{display:flex;align-items:center;gap:9px;flex-wrap:wrap;margin:12px 0}.check-actions span{font-size:12px}.history-search{padding:16px 20px 8px;background:white;border-bottom:1px solid #dce8e1}.search-row{display:flex;gap:8px}.history-search input,.history-search select{min-width:0;border:1px solid #cbdcd2;padding:8px;border-radius:6px;background:white;color:#355a49}.search-row input{flex:1}.history-search p{font-size:12px;color:#7b8983}.history-filters{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:12px}.history-filters label{display:flex;flex-direction:column;gap:5px;font-size:12px}.history-results{padding:12px 20px}.continuous-chat .history-result{display:block;width:100%;padding:15px;text-align:left;margin-bottom:10px}.history-result strong{display:block;margin:8px 0}.result-excerpt{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;line-height:1.7;color:#516f61}.history-location{display:flex;gap:10px;align-items:center;padding:9px 16px;background:#fffbe9;font-size:12px;flex-wrap:wrap}.history-location span{flex:1}.conversation-composer{flex-shrink:0;background:white}.composer-reference{display:flex;gap:10px;padding:10px 20px;background:#edf4ef;font-size:12px}.composer-reference>div{flex:1;min-width:0}.composer-reference p{margin:4px 0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.sending-location,.collapsed-activity{padding:8px 20px;margin:0;color:#6b776d;font-size:12px;background:#fffbe9}.mock-examples{padding:7px 20px;font-size:11px;color:#7c8a83;border-top:1px solid #edf1ee}.mock-examples summary{cursor:pointer}.mock-examples>div{display:flex;gap:6px;flex-wrap:wrap;margin:8px 0}.mock-examples button{font-size:11px}.mock-examples p{margin:7px 0}.switch-confirm{margin:10px 18px;padding:16px;border:1px solid #dec992;border-radius:8px;background:#fffbef}.switch-confirm>div{display:flex;gap:8px}.empty{color:#7b8983;padding:30px 12px;line-height:1.8}.older{display:block;margin:auto}.collapsed{height:auto}.collapsed .conversation-composer{width:100%}@media(max-width:1100px){.conversation-header{padding:10px 14px;flex-wrap:wrap}.header-actions{margin-left:auto}.conversation-messages{padding:12px}.header-actions button{font-size:12px}.history-search{padding:12px}.history-filters{grid-template-columns:1fr}}
</style>
