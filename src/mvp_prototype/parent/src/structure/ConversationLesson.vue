<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue';
import { chapterOf } from './data';
import { state, uid, touchSession } from './state';
import type { Session, LessonEvent } from './state';
import CardGroups from './CardGroups.vue';
const props=defineProps<{session:Session;scope:string}>();
const emit=defineEmits<{home:[];record:[id:string]}>();
const chapter=computed(()=>chapterOf(props.session.chapter)!);
const fractions=computed(()=>props.session.chapter==='fractions');
const root=ref<HTMLElement>(),newContent=ref(false),review=ref(false),forceScroll=ref(false);
// Old progress is expanded into visible turns, without replacing answers or drafts.
if(!props.session.conversation){
 const events:LessonEvent[]=(props.session.shown||Array.from({length:props.session.segment+1},(_,i)=>i)).map(index=>({id:uid('TURN'),kind:'segment',index}));
 for(const m of state.messages[props.scope]||[])events.push({id:uid('TURN'),kind:'message',value:m.id});
 if(props.session.status==='check'||props.session.submitted||props.session.endedReason.includes('检查'))events.push({id:uid('TURN'),kind:'check-start'});
 if(props.session.status==='ended')events.push({id:uid('TURN'),kind:props.session.endedReason.includes('检查')?'check-end':'ended'});
 if(props.session.postHelpShown)events.push({id:uid('TURN'),kind:'help'});
 props.session.conversation={version:1,events,scenario:'none',prepared:false,practiceDraft:''};
}
const conversation=computed(()=>props.session.conversation!);
const events=computed(()=>conversation.value.events);
const visibleEvents=computed(()=>sessionCheckStart());
function sessionCheckStart(){if(props.session.status!=='check')return events.value;const start=events.value.findIndex(e=>e.kind==='check-start');return start<0?[]:events.value.slice(start);}
const has=(kind:LessonEvent['kind'])=>events.value.some(e=>e.kind===kind);
const message=(id?:string)=>(state.messages[props.scope]||[]).find(m=>m.id===id);
const title=computed(()=>fractions.value?'为什么要除以比较标准？':chapter.value.goal);
function append(kind:LessonEvent['kind'],value?:string,index?:number){events.value.push({id:uid('TURN'),kind,value,index});touchSession(props.session);}
function scrollToLatest(){const main=root.value?.closest('main');if(main){main.scrollTop=main.scrollHeight;newContent.value=false;}}
function acted(){forceScroll.value=true;}
watch(()=>[events.value.length,props.session.status,conversation.value.prepared],async()=>{
 const main=root.value?.closest('main');const nearEnd=!!main&&main.scrollHeight-main.scrollTop-main.clientHeight<160;
 await nextTick();if(forceScroll.value||nearEnd)scrollToLatest();else newContent.value=true;forceScroll.value=false;
});
function scenario(which:'quick'|'support'){
 if(props.session.status!=='learning'||conversation.value.scenario!=='none')return;
 acted();conversation.value.scenario=which;append(which);review.value=false;
}
function show(kind:'groups'|'return'|'practice'){
 if(props.session.status!=='learning'||has(kind))return;acted();append(kind);
}
function nextSegment(){
 if(props.session.status!=='learning')return;const index=props.session.segment+1;
 if(!chapter.value.segments[index])return;acted();props.session.segment=index;(props.session.shown??=[0]).push(index);append('segment',undefined,index);
}
function practiceSubmit(){
 if(props.session.status!=='learning'||conversation.value.practiceAnswer!==undefined||!conversation.value.practiceDraft.trim())return;
 acted();conversation.value.practiceAnswer=conversation.value.practiceDraft;append('practice-answer');
}
function prepare(){if(props.session.status!=='learning')return;acted();conversation.value.prepared=true;}
function startCheck(){
 if(props.session.status!=='learning'||!conversation.value.prepared||has('check-start'))return;
 acted();conversation.value.prepared=false;props.session.status='check';append('check-start');
}
function finish(reason:string,submitted=false,help=false){
 if(props.session.status==='ended')return;
 acted();const wasCheck=props.session.status==='check';props.session.status='ended';props.session.submitted=submitted;props.session.endedReason=reason;conversation.value.prepared=false;
 append(wasCheck?'check-end':'ended');
 if(help){props.session.postHelpShown=true;append('help');}
}
function submit(){if(props.session.status==='check'&&props.session.answer.trim())finish('检查已提交',true);}
</script>

<template>
 <section ref="root" class="conversation-lesson" aria-label="本次学习对话">
  <div class="conversation-heading"><div><p class="eyebrow">{{ chapter.name }} · {{ session.status==='check'?'正在检查':session.status==='ended'?'本次学习已结束':'一起弄清一个问题' }}</p><h1>{{ title }}</h1></div><button class="text" :disabled="session.status==='check'" @click="emit('home')">← 暂离并保留进度</button></div>
  <div class="lesson-context"><details><summary>{{ session.status==='check'?'本次检查范围':'本次问题与学习目标' }}</summary><p>{{ session.status==='check'?chapter.goal:fractions?'甲有 12 张卡片，乙有 9 张。甲比乙多几分之几？为什么要除以 9？':chapter.goal }}</p></details><span class="reference-badge">{{ session.status==='check'?'合成检测题 · 未接入评分':'预写教学 · 未接入模型' }}</span></div>
  <div v-if="fractions&&session.status==='learning'" class="lesson-review"><button class="text" @click="review=!review" :aria-expanded="review">教学情境</button><span>{{ conversation.scenario==='quick'?'理解较快的参考路径':conversation.scenario==='support'?'基础回补的参考路径':'可查看两条预写路径' }}</span><div v-if="review"><p>仅用于评审。下面的学生表达与系统回应都是预写示例，不会成为你的作答或掌握证据。每次活动选择一条；查看另一条请另开一次讲解，已有内容保留。</p><button :disabled="conversation.scenario!=='none'" @click="scenario('quick')">载入理解较快情境</button><button :disabled="conversation.scenario!=='none'" @click="scenario('support')">载入基础回补情境</button></div></div>
  <button v-if="newContent" class="new-content" @click="scrollToLatest">有新内容，查看最新位置 ↓</button>

  <div v-if="session.status==='check'" class="teaching-folded" role="note">正在进行结束检查。此前讲解暂时收起，结束后可回看；先前获得的帮助仍会保留记录。</div>
  <div class="conversation-turns">
   <template v-for="event in visibleEvents" :key="event.id">
    <template v-if="session.status!=='check'||event.kind==='check-start'||event.kind==='message'">
     <article v-if="event.kind==='segment'" class="teaching-turn"><p class="speaker">DeerMind <span>讲解</span></p><template v-if="fractions&&event.index===0"><h2>先看：多出来的 3 张，要和谁比？</h2><p>“甲比乙多几分之几”，问的是多出来的部分占<strong>乙的 9 张</strong>的几分之几。甲多了 12 − 9 = 3 张，所以要用 3 ÷ 9。</p><CardGroups :total="9"/><p>把乙的 9 张看成一整份，多出的 3 张正好占三分之一。比较标准是 9，所以用它作除数。</p></template><template v-else><h2>{{ chapter.segments[event.index||0]?.title }}</h2><p>{{ chapter.segments[event.index||0]?.body }}</p><div class="formula">{{ chapter.segments[event.index||0]?.formula }}</div></template></article>
     <template v-else-if="event.kind==='quick'"><article class="student-turn fixture-turn"><p class="speaker">示例学生 <span>预写情境，不是你的作答</span></p><p>明白了。如果问乙比甲少，就应该用 3÷12，因为这次和甲比。</p></article><article class="teaching-turn"><p class="speaker">DeerMind <span>预写回应</span></p><p>这句话把比较方向和标准量联系起来了。我们可以跳过重复讲解，试着换一个数量关系检查一下。</p><p class="muted small">这段反馈只对应上面的示例表达，没有评价本轮真实输入。</p></article></template>
     <template v-else-if="event.kind==='support'"><article class="student-turn fixture-turn"><p class="speaker">示例学生 <span>预写情境，不是你的作答</span></p><p>我知道是 3 张和 9 张比，但 3÷9 为什么是三分之一？</p></article><article class="teaching-turn"><p class="speaker">DeerMind <span>预写回应</span></p><h2>先把“三张占九张多少”讲清楚</h2><p>九张可以分成三个同样大的组，每组三张。三张正好是一组，所以占整体的三分之一。3/9 和 1/3 描述的是同样的一部分。</p><CardGroups :total="9"/><p>这只是在处理当前疑点，还不能据此判断整个分数基础。</p></article></template>
     <article v-else-if="event.kind==='groups'" class="teaching-turn"><p class="speaker">DeerMind <span>图示说明</span></p><h2>同样的 3 张，放进 12 张里呢？</h2><CardGroups :total="12"/><p>整体变成 12 张，三张占其中四组中的一组，所以是四分之一。</p></article>
     <article v-else-if="event.kind==='return'" class="teaching-turn"><p class="speaker">DeerMind <span>回到原题</span></p><h2>相差量没变，比较标准变了</h2><div class="comparison-lines"><p>甲比乙多：以乙的 9 张为标准，3 ÷ 9 = 1/3。</p><p>乙比甲少：以甲的 12 张为标准，3 ÷ 12 = 1/4。</p></div><p>先说清“和谁比”，再决定把谁作为一整份。可以继续追问，也可以试着做题。</p></article>
     <article v-else-if="event.kind==='practice'" class="teaching-turn embedded-task"><p class="speaker">一起练一练 <span>讲解中的练习，可求助</span></p><h2>换一个比较方向</h2><p>甲有 12 张卡片，乙有 9 张。乙比甲少几分之几？请说明比较标准。</p><template v-if="conversation.practiceAnswer===undefined&&session.status==='learning'"><label class="field">练习作答<textarea v-model="conversation.practiceDraft" rows="3" placeholder="写下算式和理由…"/></label><button class="primary" :disabled="!conversation.practiceDraft.trim()" @click="practiceSubmit">提交练习</button></template><p v-else-if="conversation.practiceAnswer===undefined" class="muted">未提交{{ conversation.practiceDraft?'，草稿已保留':'' }}，不记为错误。</p></article>
     <template v-else-if="event.kind==='practice-answer'"><article class="student-turn"><p class="speaker">你的练习作答 <span>实际输入</span></p><p class="preserve-text">{{ conversation.practiceAnswer }}</p></article><article class="teaching-turn"><p class="speaker">已收到 <span>尚未判定</span></p><p>作答已保留，当前没有运行评分。刚才的讲解背景一并保留，不能据此宣布独立掌握。</p></article></template>
     <article v-else-if="event.kind==='message'&&message(event.value)" class="student-turn"><p class="speaker">你 <span>{{ message(event.value)?.at }} · 尚未处理</span></p><p class="preserve-text">{{ message(event.value)?.text }}</p><img v-if="message(event.value)?.attachment" class="request-image" :src="message(event.value)?.attachment?.data" :alt="message(event.value)?.attachment?.name"/><small>已保存。这版没有理解请求或生成回答；不会用预写教学冒充对这条输入的回应。</small></article>
     <article v-else-if="event.kind==='check-start'" class="teaching-turn embedded-task check-turn"><p class="speaker">结束检查 <span>{{ session.status==='check'?'进行中':'已结束' }} · 1 道题</span></p><h2>用自己的话解释</h2><p>{{ chapter.question }}</p><template v-if="session.status==='check'"><label class="field">你的作答<textarea v-model="session.answer" rows="4" aria-label="检查作答" placeholder="写下算式和理由…"/></label><div class="action-bar"><button class="primary" :disabled="!session.answer.trim()" @click="submit">提交本次检查</button><button @click="finish('请求讲解，先结束检查',false,true)">需要讲解，结束检查</button><button class="text" @click="finish('主动结束检查')">结束，保留已有内容</button></div><p class="muted small">此稿用文字走查；手写和语音待接入。提交后不会自动生成评分。</p></template><template v-else><p class="muted small">{{ session.submitted?'实际提交':'未提交草稿' }}</p><blockquote v-if="session.answer">{{ session.answer }}</blockquote><p v-else>没有提交作答，不记为错误。</p></template></article>
     <article v-else-if="event.kind==='check-end'||event.kind==='ended'" class="teaching-turn lesson-summary"><p class="speaker">本次小结</p><h2>{{ session.endedReason||'本次学习已结束' }}</h2><p>{{ session.submitted?'已提交 1 次检查作答，尚未判定。':'没有提交本次检查作答。' }}{{ conversation.practiceAnswer!==undefined?'另有一份讲解中练习作答，尚未判定。':'' }}</p><p>本次围绕“{{ title }}”展开；{{ conversation.scenario==='support'?'另外查看了三张占九张的图示解释。':conversation.scenario==='quick'?'查看了理解较快的预写情境。':'已展示的讲解和实际输入保留在这段对话里。' }}</p><p class="muted small">阅读、预写示例和未判定作答都不会直接更新学习状态。可以回看本次内容，结束的检查不能重新提交。</p></article>
     <article v-else-if="event.kind==='help'" class="teaching-turn"><p class="speaker">DeerMind <span>检查结束后展示的预写帮助</span></p><h2>一起看这道检查题</h2><p>{{ chapter.reference }}</p><p class="muted small">帮助是在检查结束后展示的；未提交草稿保留，后续帮助不会改写先前表现。</p></article>
    </template>
   </template>
  </div>

  <section v-if="session.status==='learning'&&conversation.prepared" class="teaching-turn embedded-task check-preparation" aria-label="检查安排"><p class="speaker">检查安排</p><h2>检查这次理解了什么</h2><p>{{ chapter.goal }} · 1 道合成题 · 参考 3 分钟</p><p>开始后先收起讲解，提交后统一反馈；实质求助会先结束检查。刚才的帮助仍有记录，本次不能单独证明持久掌握。</p><div class="action-bar"><button class="primary" @click="startCheck">开始检查</button><button @click="conversation.prepared=false">继续交流，暂不检查</button></div></section>
  <div v-if="session.status==='learning'&&!conversation.prepared" class="conversation-actions"><p class="muted small">可以随时在下方追问，也可以选择：</p><div class="action-bar"><template v-if="fractions"><button v-if="!has('groups')&&conversation.scenario!=='quick'" @click="show('groups')">看看 12 张的图示</button><button v-if="has('groups')&&!has('return')" @click="show('return')">回到原题</button><button v-if="!has('practice')&&conversation.scenario!=='quick'" @click="show('practice')">一起练一练</button></template><button v-else-if="session.segment<chapter.segments.length-1" @click="nextSegment">继续下一段 →</button><button class="primary" @click="prepare">检查一下这次理解</button><button class="text" @click="finish('学生结束讲解')">这次先到这里</button></div></div>
  <div v-if="session.status==='ended'" class="conversation-actions"><div class="action-bar"><button class="primary" @click="emit('home')">回到首页</button><button @click="emit('record',session.id)">查看这次记录</button></div></div>
 </section>
</template>
