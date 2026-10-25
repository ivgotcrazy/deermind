<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue';
import { useRoute } from 'vue-router';
import { chapterOf } from './data';
import { state, orderedSessions, scriptedPreview, classroomIsCurrent } from './state';
import type { Session } from './state';
import { chapterCounts, chapterFeedback, displayRequirementState, hasReference } from './home';
import { statusCatalog, chapterPath } from './statusCatalog';
import type { StatusChapter } from './statusCatalog';
import SavedRequest from './SavedRequest.vue';
import ClassroomProgress from './ClassroomProgress.vue';
import './learning-status.css';

const props=defineProps<{space:string;scope:string}>();
const emit=defineEmits<{navigate:[page:string,query?:Record<string,string>];begin:[chapter:string];resume:[session:Session]}>();
const route=useRoute();
const q=(key:string)=>String(route.query[key]||'');
const catalog=computed(()=>statusCatalog(state.home.catalogScale));
const selectedChapter=computed(()=>q('chapter'));
const selected=computed(()=>catalog.value.find(c=>c.id===selectedChapter.value));
const view=computed(()=>selectedChapter.value?'detail':'directory');
const sessions=computed(()=>orderedSessions(state.sessions.filter(s=>s.learner==='S0001'&&s.space===props.space)));
const available=computed(()=>props.space==='school');
const reference=computed(()=>hasReference('S0001',props.space));
const counts=(chapter:string)=>chapterCounts(chapter,'S0001',props.space);
const root=ref<HTMLElement>();
const search=ref(q('q'));
watch(()=>q('q'),value=>{search.value=value;});
const books=computed(()=>[...new Set(catalog.value.map(c=>c.book))]);
const units=computed(()=>[...new Set(catalog.value.filter(c=>c.book===q('book')).map(c=>c.unit).filter(Boolean))]);
const hasActivity=(id:string)=>sessions.value.some(s=>s.chapter===id);
const filtered=computed(()=>catalog.value.filter(c=>{
 const term=q('q').trim().toLocaleLowerCase();
 return (!term||`${c.name} ${chapterPath(c)}`.toLocaleLowerCase().includes(term))&&
 (!q('book')||q('book')===c.book)&&(!q('unit')||q('unit')===c.unit)&&
 (!q('state')||q('state')==='attention'&&reference.value&&c.reference&&counts(c.id)[1]>0||
 q('state')==='unknown'&&(!reference.value||!c.reference)||q('state')==='activity'&&hasActivity(c.id));
}));
const pages=computed(()=>Math.max(1,Math.ceil(filtered.value.length/12)));
const page=computed(()=>Math.min(pages.value,Math.max(1,Math.floor(Number(q('p'))||1))));
const rows=computed(()=>filtered.value.slice((page.value-1)*12,page.value*12));
function navigate(page:string,query:Record<string,string>={}){emit('navigate',page,query);}
function directoryQuery():Record<string,string>{return Object.fromEntries(['view','q','book','unit','state','p'].map(k=>[k,q(k)]).filter(([,v])=>!!v));}
function directory(changes:Record<string,string>={}){const query:Record<string,string>={...directoryQuery(),view:'directory',...changes};navigate('status',Object.fromEntries(Object.entries(query).filter(([,v])=>!!v)));}
function filter(key:string,value:string){directory({[key]:value,p:'1',...(key==='book'?{unit:''}:{})});}
function openChapter(id:string){navigate('status',{...directoryQuery(),view:'directory',chapter:id});}
function backToList(){if(q('from')==='home')navigate('home');else directory();}
function canBegin(id:string){return !!chapterOf(id)&&(scriptedPreview||id==='fractions');}
function statusSummary(c:StatusChapter){return reference.value&&c.reference?`已达标 ${counts(c.id)[0]} · 需加强 ${counts(c.id)[1]} · 待确认 ${counts(c.id)[2]}`:c.reference?'尚无学习评价':'内容准备中 · 尚无学习评价';}
// Navigate with a visible context and a predictable keyboard focus, without losing list scroll.
watch(()=>route.fullPath,async(to,from)=>{
 if(!to.startsWith('/status'))return;
 const previousQuery=new URLSearchParams(from.split('?')[1]||'');
 const previous=previousQuery.get('chapter');
 const previousView=previous?'detail':'directory';
 // Filter changes leave focus on the search/filter control; result count is announced separately.
 if(from.startsWith('/status')&&previousView===view.value&&previous=== (selectedChapter.value||null))return;
 await nextTick();
 const row=previous&&!selectedChapter.value?root.value?.querySelector<HTMLElement>(`[data-chapter="${CSS.escape(previous)}"]`):undefined;
 const target=row||root.value?.querySelector<HTMLElement>('h1');
 target?.focus({preventScroll:true});
 if(row){const bounds=row.getBoundingClientRect(),main=row.closest('main')?.getBoundingClientRect();if(main&&(bounds.top<main.top||bounds.bottom>main.bottom))row.scrollIntoView({block:'nearest'});}
});
</script>

<template>
 <div ref="root" class="learning-status" :class="`status-view-${view}`">
  <nav v-if="view==='detail'" class="status-breadcrumb" aria-label="学习情况位置">
   <button class="text" @click="navigate('home')">首页</button><span aria-hidden="true">/</span>
   <button class="text" @click="directory()">学习情况</button><span aria-hidden="true">/</span><span aria-current="page">章节详情</span>
  </nav>
  <div class="home-heading"><div><h1 tabindex="-1">{{ view==='directory'?'学习情况':selected?.name||'找不到这个章节' }}</h1><p>{{ selected&&view==='detail'?chapterPath(selected):available?'按教材查找章节，了解具体表现与判断依据。':'校外数学 · 教材待准备' }}</p></div></div>
  <ClassroomProgress v-if="available" learner="S0001" :space="space" :catalog="catalog"/>
  <SavedRequest :scope="scope" :available="available" @materials="navigate('materials')"/>
  <section v-if="!available" class="status-summary" aria-label="学习情况摘要"><h2>本空间暂无学习情况</h2><p>教材和评价依据尚未就绪，校内记录不会合并到这里。没有记录，不代表不会。</p></section>
  <template v-else>
   <section v-if="view==='directory'" aria-label="章节查找">
    <form class="catalog-search" role="search" @submit.prevent="filter('q',search.trim())"><label for="chapter-search">查找章节</label><div><input id="chapter-search" v-model="search" type="search" placeholder="输入章节名称或目录路径"/><button type="submit">搜索</button></div></form>
    <div class="catalog-filters">
     <label v-if="books.length>1">分册<select aria-label="分册" :value="q('book')" @change="filter('book',($event.target as HTMLSelectElement).value)"><option value="">全部分册</option><option v-for="book in books" :key="book">{{ book }}</option></select></label>
     <label v-if="units.length">单元<select aria-label="单元" :value="q('unit')" @change="filter('unit',($event.target as HTMLSelectElement).value)"><option value="">全部单元</option><option v-for="unit in units" :key="unit">{{ unit }}</option></select></label>
     <label>查看范围<select aria-label="查看范围" :value="q('state')" @change="filter('state',($event.target as HTMLSelectElement).value)"><option value="">全部章节</option><option value="attention">有需加强项</option><option value="unknown">尚无学习评价</option><option value="activity">本轮有学习活动</option></select></label>
     <button v-if="q('q')||q('book')||q('unit')||q('state')" class="text" @click="navigate('status',{view:'directory'})">清除筛选</button>
    </div>
    <p v-if="pages>1||q('q')||q('book')||q('unit')||q('state')" class="catalog-results" role="status">共 {{ filtered.length }} 章<span v-if="filtered.length"> · 当前 {{ (page-1)*12+1 }}–{{ Math.min(page*12,filtered.length) }} 章</span><span v-if="q('q')"> · 搜索“{{ q('q') }}”</span></p>
    <div v-if="rows.length" class="catalog-list">
     <button v-for="c in rows" :key="c.id" class="catalog-row" :data-chapter="c.id" @click="openChapter(c.id)">
      <span class="catalog-name"><small>{{ chapterPath(c) }}</small><strong>{{ c.name }}</strong><span v-if="classroomIsCurrent('S0001',space,c.id)" class="classroom-marker">课堂正在学</span></span><span class="catalog-state"><span>{{ statusSummary(c) }}</span><small v-if="reference&&c.reference">{{ c.requirements.length }} 项要求 · 预写参考</small><small v-else-if="hasActivity(c.id)">已有本轮学习活动，尚未评价</small></span><span aria-hidden="true">›</span>
     </button>
    </div>
    <div v-else class="empty"><h2>没有找到符合条件的章节</h2><p>可以更换名称，或清除筛选查看已收录的目录。</p><button @click="navigate('status',{view:'directory'})">查看全部章节</button></div>
    <nav v-if="pages>1" class="catalog-pagination" aria-label="章节分页"><span>第 {{ page }} / {{ pages }} 页</span><button :disabled="page===1" @click="directory({p:String(page-1)})">上一页</button><button :disabled="page===pages" @click="directory({p:String(page+1)})">下一页</button></nav>
    <p class="muted catalog-intro">按教材顺序排列；章节中的数字是学习要求项数，不是掌握百分比。</p>
   </section>

   <section v-else-if="selected" class="chapter-detail-page" :aria-label="`${selected.name}学习详情`">
    <p v-if="classroomIsCurrent('S0001',space,selected.id)" class="classroom-marker">课堂正在学</p>
    <template v-if="selected.reference">
     <section class="chapter-assessment"><div class="section-title"><h2>这一章学得怎样</h2><span v-if="reference" class="reference-badge">预写反馈</span></div>
      <dl v-if="reference" class="chapter-feedback"><dt>已经表现出</dt><dd>{{ chapterFeedback[selected.id]?.strength }}</dd><dt>还需弄清楚</dt><dd>{{ chapterFeedback[selected.id]?.attention }}</dd><dt>还不了解</dt><dd>{{ chapterFeedback[selected.id]?.unknown }}</dd></dl>
      <p v-else>还没有足够记录形成评价，暂不能确定哪些已会、哪些需要帮助。没有记录不表示不会。</p>
     </section>
     <section class="chapter-next"><h2>下一步可以做什么？</h2><p>{{ reference?chapterFeedback[selected.id]?.next:'可以从自己的疑问开始，也可以先选择本章内容学习。' }}</p><p v-if="reference" class="muted small">依据预写反馈提出，本轮新作答尚未参与判断。</p><div class="home-actions"><button :disabled="!canBegin(selected.id)" @click="emit('begin',selected.id)">{{ canBegin(selected.id)?'请求本章讲解':'本章教学内容准备中' }}</button><button class="text" @click="navigate('records',{chapter:selected.id})">查看本章记录 →</button></div></section>
     <div class="chapter-measurements"><section><h2>最近有什么变化？</h2><p>暂无可比较的学习评价，还不能判断进步或退步。</p><p class="muted small">完成讲解或提交作答，不直接等于已经掌握。</p></section><section :aria-label="`${selected.name}实际学习记录`"><h2>近期的实际表现</h2><p>尚无可用于统计的已判定独立作答，暂不显示正确率。</p><p class="muted small">本轮本章有 {{ sessions.filter(s=>s.chapter===selected?.id).length }} 次活动（含进行中）；活动次数不是题数，预写历史不计入这里。</p></section></div>
     <details class="feedback-requirements"><summary>查看 {{ selected.requirements.length }} 项学习要求及状态</summary><p class="muted small">当前沿用交互参考清单，尚未发布为正式评价标准；项数不代表掌握百分比。</p><div class="counts" aria-label="本章要求项数"><b v-for="(n,i) in counts(selected.id)" :key="i">{{ n }}<small>{{ ['已达标','需加强','待确认'][i] }}</small></b></div><div v-for="(r,i) in selected.requirements" :key="r" class="status-requirement"><strong>{{ r }}</strong><span class="tag">{{ displayRequirementState('S0001',i,space) }}</span><p class="muted small">{{ displayRequirementState('S0001',i,space)==='待确认'?'当前资料不足以作出稳定判断。':'这项预写状态的完整判断依据尚未准备。' }}</p></div></details>
    </template>
    <div v-else class="empty"><h2>内容准备中</h2><p>这是目录规模走查用的合成章节，没有学习要求、教学内容或评价。不能据此判断你是否学过或会不会。</p></div>
    <button class="text detail-back" @click="backToList">{{ q('from')==='home'?'← 返回首页':'← 返回章节目录' }}</button>
   </section>
   <section v-else class="empty"><p>这个章节不在当前空间的可用目录中。其他章节及原有学习记录不受影响。</p><button @click="backToList">{{ q('from')==='home'?'返回首页':'返回章节目录' }}</button></section>
  </template>
 </div>
</template>
