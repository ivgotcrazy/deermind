<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import WorkbenchDialog from './WorkbenchDialog.vue';
import { aspects, categories, learningSpaces, taskResult, latestLearning, latestEvaluation, relatedEvents, linkedCells, latestBeliefUpdate, beliefEvidence, type GoalCell, type SpaceTask, type SpaceEvent } from '../model/learning-spaces';

const props=defineProps<{hash:string}>();
const params=computed(()=>new URLSearchParams(props.hash.split('?')[1]||''));
const value=(key:string)=>params.value.get(key)||'';
const space=computed(()=>learningSpaces.find(s=>s.id===value('id')));
const tab=computed(()=>['book','events'].includes(value('tab'))?value('tab'):'goal');
const chapter=computed(()=>space.value?.chapters.find(ch=>ch.id===(value('chapter')||space.value?.tasks[0]?.chapter))||space.value?.chapters[0]);
const listStudent=ref(value('student')),listQuery=ref(value('q')),listBook=ref(value('book')),listTarget=ref(value('target'));
const chapterQuery=ref(''),definition=ref(false),pagePreview=ref(0),eventBack=ref<string[]>([]);
const eventQuery=ref(value('eq')),eventCategory=ref(value('category')),eventActivity=ref(value('activity')),from=ref(value('from')),to=ref(value('to'));
const filterError=ref('');
const listRows=computed(()=>learningSpaces.filter(s=>(s.student+' '+s.account).includes(value('student').trim())&&s.name.includes(value('q').trim())&&(!value('book')||s.book===value('book'))&&(!value('target')||s.target===value('target'))));
const listPages=computed(()=>Math.max(1,Math.ceil(listRows.value.length/2)));
const listPage=computed(()=>clampPage(value('lp'),listPages.value));
const chapters=computed(()=>space.value?.chapters.filter(ch=>ch.name.includes(chapterQuery.value.trim()))||[]);
const tasks=computed(()=>space.value?.tasks.filter(t=>t.chapter===chapter.value?.id)||[]);
const allCells=computed(()=>space.value?.tasks.flatMap(t=>t.methods.flatMap(m=>m.cells.map(c=>({task:t,method:m,cell:c}))))||[]);
const selectedCell=computed(()=>allCells.value.find(x=>x.cell.key===value('cell')));
const focusCell=computed(()=>allCells.value.find(x=>x.cell.key===value('focus')));
const expanded=computed(()=>value('expanded')||tasks.value[0]?.id||'');
const selectedEvent=computed(()=>space.value?.events.find(e=>e.id===value('event')));
const cellBeliefEvent=computed(()=>space.value&&selectedCell.value?latestBeliefUpdate(space.value,selectedCell.value.cell.key):undefined);
const cellBelief=computed(()=>cellBeliefEvent.value?.beliefChanges?.find(c=>c.cell===selectedCell.value?.cell.key));
const cellEvidence=computed(()=>space.value&&selectedCell.value?beliefEvidence(space.value,selectedCell.value.cell.key):[]);
const activeEvidence=computed(()=>cellEvidence.value.filter(row=>!row.replacedBy));
const replacedEvidence=computed(()=>cellEvidence.value.filter(row=>row.replacedBy));
const selectedEvidence=computed(()=>cellEvidence.value.find(row=>row.evidence.id===value('evidence')));
const sourceEvent=computed(()=>selectedEvidence.value?.evidence.sources.includes(value('sourceEvent'))?space.value?.events.find(e=>e.id===value('sourceEvent')):undefined);
const aspectName=(id:string)=>aspects.find(a=>a.id===id)?.name||id;
const probability=(p:number)=>(p*100).toFixed(1)+'%';
const focusedIds=computed(()=>space.value&&focusCell.value?relatedEvents(space.value,focusCell.value.cell.key):null);
const eventRows=computed(()=>[...(space.value?.events||[])].filter(e=>(!focusedIds.value||focusedIds.value.has(e.id))&&(!value('ech')||e.chapter===value('ech'))&&(!value('category')||e.category===value('category'))&&(!value('activity')||e.activity===value('activity'))&&(!value('from')||e.occurredAt.slice(0,10)>=value('from'))&&(!value('to')||e.occurredAt.slice(0,10)<=value('to'))&&(e.id+' '+e.summary+' '+e.type+' '+e.fields.map(f=>f.value).join(' ')).includes(value('eq').trim())).sort((a,b)=>b.sequence-a.sequence));
const eventPages=computed(()=>Math.max(1,Math.ceil(eventRows.value.length/8)));
const eventPage=computed(()=>clampPage(value('ep'),eventPages.value));
const laterEvents=computed(()=>space.value?.events.filter(e=>e.causes.includes(selectedEvent.value?.id||''))||[]);
const currentCells=computed(()=>space.value&&selectedEvent.value?linkedCells(space.value,selectedEvent.value.id):[]);
const activities=computed(()=>[...new Set(space.value?.events.map(e=>e.activity).filter(Boolean))]);
watch(()=>props.hash,()=>{
  listStudent.value=value('student');listQuery.value=value('q');listBook.value=value('book');listTarget.value=value('target');
  eventQuery.value=value('eq');eventCategory.value=value('category');eventActivity.value=value('activity');from.value=value('from');to.value=value('to');
  definition.value=false;pagePreview.value=0;filterError.value='';
});
watch(()=>space.value?.id,()=>{chapterQuery.value='';eventBack.value=[];});
watch(()=>[value('evidence'),value('sourceEvent')],()=>{document.querySelector('.goal-evidence-drawer .dialog-content')?.scrollTo(0,0);},{flush:'post'});
function clampPage(raw:string,max:number){const n=Number(raw);return Number.isInteger(n)&&n>0?Math.min(n,max):1;}
function go(changes:Record<string,string>){const p=new URLSearchParams(params.value);for(const [k,v] of Object.entries(changes)){if(v)p.set(k,v);else p.delete(k);}location.hash='/learning-spaces'+(p.size?'?'+p:'');}
function enter(id:string){go({id,tab:'goal',chapter:'',cell:'',expanded:'',event:'',focus:'',origin:'',ech:'',ep:'',category:'',activity:'',eq:'',from:'',to:'',mark:''});}
function backList(){const p=new URLSearchParams();for(const key of ['student','q','book','target','lp'])if(value(key))p.set(key,value(key));location.hash='/learning-spaces'+(p.size?'?'+p:'');}
function filterList(){go({student:listStudent.value.trim(),q:listQuery.value.trim(),book:listBook.value,target:listTarget.value,lp:''});}
function switchTab(next:string){eventBack.value=[];go({tab:next,cell:'',event:'',evidence:'',sourceEvent:''});}
function selectChapter(id:string){go({chapter:id,expanded:'',cell:''});}
function openCell(t:SpaceTask,c:GoalCell){go({tab:'goal',chapter:t.chapter,expanded:t.id,cell:c.key,event:'',evidence:'',sourceEvent:''});}
function cellLabel(key:string){const row=allCells.value.find(x=>x.cell.key===key);return row?row.method.name+' · '+aspects.find(a=>a.id===row.cell.aspect)?.name:key;}
function requiredAspectNames(cells:GoalCell[]){return cells.filter(c=>c.required).map(c=>aspects.find(a=>a.id===c.aspect)?.name).join('、');}
function openEvidence(id:string){go({evidence:id,sourceEvent:''});}
function backGoal(key:string){const row=allCells.value.find(x=>x.cell.key===key);if(row)openCell(row.task,row.cell);}
function openEvent(id:string){if(selectedEvent.value)eventBack.value.push(selectedEvent.value.id);else eventBack.value=[];go({tab:'events',event:id,cell:''});}
function previousEvent(){const id=eventBack.value.pop();if(id)go({event:id});}
function filterEvents(){if(from.value&&to.value&&from.value>to.value){filterError.value='开始日期不能晚于结束日期。';return;}go({eq:eventQuery.value.trim(),category:eventCategory.value,activity:eventActivity.value,from:from.value,to:to.value,ep:'',event:''});}
function resetEvents(){go({eq:'',category:'',activity:'',from:'',to:'',ech:'',ep:'',event:''});}
function surrounding(e:SpaceEvent){const sorted=[...space.value!.events].sort((a,b)=>b.sequence-a.sequence);go({focus:'',eq:'',category:'',activity:'',from:'',to:'',ech:'',ep:String(Math.floor(sorted.findIndex(x=>x.id===e.id)/8)+1),event:'',mark:e.id});}
function lookup(id:string){return space.value?.events.find(e=>e.id===id);}
function chapterEvents(){go({tab:'events',ech:chapter.value?.id||'',focus:'',origin:'',event:'',eq:'',category:'',activity:'',from:'',to:'',ep:''});}
const badgeClass=(status:string)=>status==='已达标'?'passed':status==='需加强'?'attention':'unknown';
</script>

<template><section class="wb-page learning-space-workspace">
  <template v-if="!value('id')">
    <header class="page-header"><div><h2>学习空间</h2><p class="page-desc">查看学生选用的课程、目标达成情况和发生过的事件。</p></div><span class="badge">固定 Mock 样例</span></header>
    <form class="panel space-filters" @submit.prevent="filterList">
      <label>学生<input v-model="listStudent" placeholder="姓名或账号" type="search"/></label>
      <label>学习空间<input v-model="listQuery" placeholder="空间名称" type="search"/></label>
      <label>教材<select v-model="listBook" aria-label="教材"><option value="">全部教材</option><option v-for="b in [...new Set(learningSpaces.map(s=>s.book))]" :key="b">{{b}}</option></select></label>
      <label>学习目标<select v-model="listTarget" aria-label="学习目标"><option value="">全部目标</option><option v-for="t in [...new Set(learningSpaces.map(s=>s.target))]" :key="t">{{t}}</option></select></label>
      <div class="filter-actions"><button class="btn primary" type="submit">查询</button><button type="button" class="btn" @click="go({student:'',q:'',book:'',target:'',lp:''})">重置</button></div>
    </form>
    <section class="panel table-scroll"><table class="data-table"><thead><tr><th>学习空间</th><th>学生</th><th>教材</th><th>学习目标</th><th>最近学习</th><th>操作</th></tr></thead><tbody>
      <tr v-for="s in listRows.slice((listPage-1)*2,listPage*2)" :key="s.id"><td><button class="text-link model-name" @click="enter(s.id)">{{s.name}}</button><small>{{s.id}}</small></td><td>{{s.student}}<small>{{s.account}}</small></td><td>{{s.book}}</td><td>{{s.target}}</td><td>{{latestLearning(s)}}</td><td><button class="btn" :aria-label="'进入 '+s.id" @click="enter(s.id)">进入空间</button></td></tr>
    </tbody></table><p v-if="!listRows.length" class="empty">没有符合条件的学习空间。</p></section>
    <div class="pagination"><span>共 {{listRows.length}} 个空间 · {{listPage}} / {{listPages}}</span><button class="btn" :disabled="listPage===1" @click="go({lp:String(listPage-1)})">上一页</button><button class="btn" :disabled="listPage===listPages" @click="go({lp:String(listPage+1)})">下一页</button></div>
    <p class="muted">最近学习按学生消息或作答的发生时间统计，不因后台评价或补录而刷新。这里的样例独立于学生端实际试用记录。</p>
  </template>
  <template v-else-if="space">
    <button class="text-link" @click="backList">← 返回学习空间列表</button>
    <header class="page-header space-heading"><div><h2>{{space.name}}</h2><p class="page-desc">{{space.student}} · {{space.account}} · {{space.id}}</p></div><span class="badge">固定 Mock · 只读观测</span></header>
    <nav class="object-tabs" aria-label="空间内容"><button v-for="t in [{id:'book',name:'教材'},{id:'goal',name:'学习目标'},{id:'events',name:'空间事件'}]" :key="t.id" :class="{active:tab===t.id}" :aria-current="tab===t.id?'page':undefined" @click="switchTab(t.id)">{{t.name}}</button></nav>

    <template v-if="tab==='book'||tab==='goal'">
      <section class="panel adoption-head"><div><h3>{{tab==='book'?space.book:space.target}}</h3><p class="muted">{{tab==='book'?space.bookVersion:space.targetVersion}} · 采用于 {{space.adoptedAt}}</p><p v-if="tab==='goal'">{{space.description}}</p><p v-if="tab==='goal'" class="muted">最近目标评价：{{latestEvaluation(space)}}</p></div><button class="btn" @click="definition=true">{{tab==='book'?'查看采用说明':'查看目标定义'}}</button></section>
      <div class="space-columns"><aside class="panel chapter-panel"><label>查找章节<input v-model="chapterQuery" type="search" placeholder="章节名称"/></label><nav aria-label="教材章节"><button v-for="ch in chapters" :key="ch.id" class="chapter-button" :class="{active:chapter?.id===ch.id}" :aria-current="chapter?.id===ch.id?'page':undefined" @click="selectChapter(ch.id)">{{ch.name}}</button></nav><p v-if="!chapters.length" class="empty">没有匹配章节</p></aside>
        <section class="panel chapter-detail" v-if="chapter"><div class="row-between"><h3>{{chapter.name}}</h3><div class="button-row"><button v-if="tab==='book'" class="text-link" @click="switchTab('goal')">本章目标 →</button><button v-else class="text-link" @click="switchTab('book')">本章教材 →</button><button v-if="tab==='book'" class="text-link" @click="chapterEvents">本章事件 →</button></div></div>
          <template v-if="tab==='book'"><p>{{chapter.content}}</p><div class="student-question"><span class="badge">整理内容示例</span><p>{{chapter.question}}</p><p class="formula">{{chapter.formula}}</p></div><p class="muted">下方为采用的教材原页，可放大核对。上方整理示例不替代原页内容。</p><div class="book-pages"><button v-for="n in chapter.pages" :key="n" class="page-thumb" :aria-label="'第 '+n+' 页 · 放大查看'" @click="pagePreview=n"><img :src="'/materials/bnu6a/page-'+n+'.png'" :alt="'教材第 '+n+' 页缩略图'" loading="lazy"/><span>第 {{n}} 页 · 放大查看</span></button></div></template>
          <template v-else>
            <p v-if="!tasks.length" class="empty">本目标未选用本章任务。教材包含本章，不代表本目标要求评价本章。</p>
            <article v-for="t in tasks" :key="t.id" class="goal-task"><button class="task-toggle" :aria-expanded="expanded===t.id" @click="go({expanded:expanded===t.id?'none':t.id})"><span>{{expanded===t.id?'▾':'▸'}} {{t.name}}<small>{{t.methods.length===1?'指定方法达标':t.mode==='all'?'所选 '+t.methods.length+' 种方法分别达标':'所选方法任一达标'}}</small></span><span class="status-label" :class="badgeClass(taskResult(t))">{{taskResult(t)}}</span></button>
              <div v-if="expanded===t.id"><p class="muted">{{t.id}} · {{t.claim}} · 状态按目标要求判断，点击结果查看依据。</p><div class="table-scroll"><table class="data-table goal-matrix"><thead><tr><th>方法</th><th v-for="a in aspects" :key="a.id">{{a.name}}</th></tr></thead><tbody><tr v-for="m in t.methods" :key="m.id"><td><strong>{{m.name}}</strong><small>{{m.execution}}</small></td><td v-for="c in m.cells" :key="c.key"><button v-if="c.required" class="cell-result" :class="badgeClass(c.status)" :aria-label="m.name+' · '+aspects.find(a=>a.id===c.aspect)?.name+' · '+c.status" @click="openCell(t,c)">{{c.status}}</button><span v-else class="muted">本目标未要求</span><small v-if="c.processing" class="processing-note">{{c.processing}}</small></td></tr></tbody></table></div><p class="muted">{{t.mode==='all'?'各方法分别判断，不能用一种方法的通过代替另一种。':'满足所选方法中任一种的全部要求即可。'}} 尚未发生或不足以判断的表现保留“待确认”。</p></div>
            </article>
          </template>
        </section>
      </div>
    </template>

    <template v-else>
      <div class="row-between"><p class="muted">按记录顺序倒序显示。事件一经记录不再修改或删除；补录、纠正均追加新事件。</p><button v-if="value('origin')" class="btn" @click="backGoal(value('origin'))">返回目标项</button></div>
      <div v-if="focusCell" class="callout row-between"><span>正在追溯：{{cellLabel(focusCell.cell.key)}}<br/><small>包含目标评价及其引用的原始事件；以下筛选只在此范围内生效。</small></span><button class="btn" @click="go({focus:'',ep:''})">查看全部事件</button></div>
      <div v-if="value('ech')" class="callout row-between"><span>章节：{{space.chapters.find(c=>c.id===value('ech'))?.name}}</span><button class="btn" @click="go({ech:'',ep:''})">清除章节筛选</button></div>
      <form class="panel event-filters" @submit.prevent="filterEvents"><label>发生日期从<input v-model="from" type="date"/></label><label>至<input v-model="to" type="date"/></label><label>事件类别<select v-model="eventCategory" aria-label="事件类别"><option value="">全部类别</option><option v-for="c in categories" :key="c">{{c}}</option></select></label><label>活动<select v-model="eventActivity" aria-label="活动"><option value="">全部活动</option><option v-for="a in activities" :key="a">{{a}}</option></select></label><label>查找事件<input v-model="eventQuery" type="search" placeholder="内容、类型或事件编号"/></label><div class="filter-actions"><button class="btn primary" type="submit">查询事件</button><button class="btn" type="button" @click="resetEvents">重置筛选</button></div><p v-if="filterError" role="alert" class="filter-error">{{filterError}}</p></form>
      <section class="panel table-scroll"><table class="data-table event-table"><thead><tr><th>发生时间</th><th>类别 / 类型</th><th>发起方</th><th>事件内容</th><th>活动</th></tr></thead><tbody><tr v-for="e in eventRows.slice((eventPage-1)*8,eventPage*8)" :key="e.id" :data-event="e.id" :class="{'located-event':value('mark')===e.id}"><td class="time-cell">{{e.occurredAt}}<small v-if="e.recordedAt!==e.occurredAt">补录于 {{e.recordedAt}}</small></td><td>{{e.type}}<small>{{e.category}}</small></td><td>{{e.actor==='学生'?space.student:e.actor}}</td><td><button class="text-link model-name" @click="openEvent(e.id)">{{e.summary}}</button><small>{{e.id}}{{value('mark')===e.id?' · 当前定位':''}}</small></td><td>{{e.activity||'空间级'}}</td></tr></tbody></table><p v-if="!eventRows.length" class="empty">没有符合条件的事件。</p></section>
      <div class="pagination"><span>共 {{eventRows.length}} 条 · {{eventPage}} / {{eventPages}}</span><button class="btn" :disabled="eventPage===1" @click="go({ep:String(eventPage-1)})">上一页</button><button class="btn" :disabled="eventPage===eventPages" @click="go({ep:String(eventPage+1)})">下一页</button></div>
      <p v-if="value('event')&&!selectedEvent" class="callout" role="alert">此事件不属于当前学习空间，未打开其他空间的数据。</p>
    </template>

    <WorkbenchDialog v-if="tab==='goal'&&selectedCell" class="space-drawer goal-evidence-drawer" :title="value('sourceEvent')?'来源事件':value('evidence')?'Evidence 详情':'目标项与判断依据'" @close="go({cell:'',evidence:'',sourceEvent:''})">
      <div v-if="value('evidence')" class="button-row evidence-back"><button v-if="value('sourceEvent')" class="text-link" @click="go({sourceEvent:''})">← 返回 Evidence</button><button class="text-link" @click="go({evidence:'',sourceEvent:''})">← 返回目标依据</button></div>
      <template v-if="value('sourceEvent')">
        <template v-if="sourceEvent"><h3>{{sourceEvent.summary}}</h3><p class="muted">{{sourceEvent.id}} · {{sourceEvent.type}}</p><div class="event-times"><span>发生：{{sourceEvent.occurredAt}}</span><span>记录：{{sourceEvent.recordedAt}}</span></div><section class="detail-section"><h4>当时记录 <span class="badge">只读</span></h4><dl class="field-list"><template v-for="f in sourceEvent.fields" :key="f.label"><dt>{{f.label}}</dt><dd>{{f.value}}</dd></template></dl><div v-if="sourceEvent.table" class="table-scroll"><table class="data-table"><caption>{{sourceEvent.table.caption}}</caption><thead><tr><th v-for="c in sourceEvent.table.columns" :key="c">{{c}}</th></tr></thead><tbody><tr v-for="(row,i) in sourceEvent.table.rows" :key="i"><td v-for="(c,j) in row" :key="j">{{c}}</td></tr></tbody></table></div></section></template>
        <p v-else role="alert">未找到属于这条 Evidence 的来源事件。</p>
      </template>
      <template v-else-if="value('evidence')">
        <template v-if="selectedEvidence"><h3>{{cellLabel(selectedCell.cell.key)}}</h3><p class="muted">{{selectedEvidence.evidence.id}} · {{selectedEvidence.evidence.attempt}}</p><p><span class="badge">{{selectedEvidence.evidence.judgment}}</span> <span v-if="selectedEvidence.replacedBy" class="badge warning">已被替代 · 不参与当前判断</span></p>
          <section class="detail-section"><h4>评价依据</h4><p><strong>判据：</strong>{{selectedEvidence.evidence.criterion}}</p><blockquote class="evidence-quote">{{selectedEvidence.evidence.quote}}</blockquote><p><strong>判断理由：</strong>{{selectedEvidence.evidence.reason}}</p><p class="muted">形成时间：{{selectedEvidence.event.recordedAt}}。{{selectedEvidence.evidence.claim}}</p></section>
          <section v-if="selectedEvidence.replacedBy||selectedEvidence.evidence.replaces?.length" class="detail-section"><h4>纠正关系</h4><p v-if="selectedEvidence.replacedBy">此解释已被纠正；保留历史，不重复计入作答。<button class="text-link" @click="openEvidence(selectedEvidence.replacedBy)">查看替代后的 Evidence</button></p><button v-for="id in selectedEvidence.evidence.replaces" :key="id" class="text-link" @click="openEvidence(id)">查看被替代的 Evidence</button></section>
          <section class="detail-section"><h4>来源事件</h4><p class="muted">以下是形成这条 Evidence 所依据的原始记录。</p><ul class="event-links"><li v-for="id in selectedEvidence.evidence.sources" :key="id"><button class="text-link" @click="go({sourceEvent:id})">{{lookup(id)?.summary||id}}</button><small>{{lookup(id)?.type}} · {{lookup(id)?.occurredAt}}</small></li></ul></section>
        </template><p v-else role="alert">未找到属于当前目标项的 Evidence。</p>
      </template>
      <template v-else>
      <h3>{{selectedCell.task.name}}</h3><p>{{cellLabel(selectedCell.cell.key)}}</p><span class="status-label" :class="badgeClass(selectedCell.cell.status)">{{selectedCell.cell.status}}</span><span v-if="selectedCell.cell.processing" class="badge warning">{{selectedCell.cell.processing}}</span>
      <section class="detail-section"><h4>目标要求</h4><p>{{selectedCell.cell.requirement}}</p><p class="muted">{{space.target}} · v1；{{selectedCell.task.claim}}</p></section>
      <section class="detail-section"><h4>当前判断</h4><p>{{selectedCell.cell.reason}}</p><p class="muted">{{selectedCell.cell.updatedAt?'评价时间：'+selectedCell.cell.updatedAt:'尚未形成有效评价'}}。评价失败不会覆盖此前有效结果。</p></section>
      <section class="detail-section belief-basis"><h4>对应的能力判断（Belief）</h4>
        <template v-if="cellBelief&&cellBeliefEvent"><p><strong class="probability">{{probability(cellBelief.after)}}</strong> <span class="muted">{{aspectName(cellBelief.aspect)}} · 本方法的试用概率估计</span></p><p class="muted">最近更新：{{cellBeliefEvent.recordedAt}}。目标还要核对题数、情境、时间和反证，不能只看概率。</p></template>
        <p v-else class="muted">尚无符合本方法、本评价方面的有效证据更新。不将初始概率显示为已掌握。</p>
      </section>
      <section class="detail-section"><h4>Evidence 列表 <span class="badge">{{activeEvidence.length}} 条</span></h4><p class="muted">当前方法、当前评价方面的累计有效依据。点击查看判据与来源事件。</p><div v-if="activeEvidence.length" class="table-scroll"><table class="data-table goal-evidence-list"><thead><tr><th>作答</th><th>Evidence 摘要</th><th>判断</th></tr></thead><tbody><tr v-for="row in activeEvidence" :key="row.evidence.id"><td>{{row.evidence.attempt}}<small>{{row.event.occurredAt}}</small></td><td><button class="text-link" :aria-label="'查看 '+row.evidence.attempt+' Evidence'" @click="openEvidence(row.evidence.id)">{{row.evidence.reason}}</button></td><td>{{row.evidence.judgment}}</td></tr></tbody></table></div><p v-else class="empty">暂无有效 Evidence；未检测、求助或评价失败不作为答错。</p>
        <details v-if="replacedEvidence.length" class="replaced-evidence"><summary>查看已被替代的 Evidence（{{replacedEvidence.length}} 条）</summary><ul class="event-links"><li v-for="row in replacedEvidence" :key="row.evidence.id"><button class="text-link" @click="openEvidence(row.evidence.id)">{{row.evidence.attempt}} · {{row.evidence.judgment}} · 已被替代</button><small>保留历史，不计入当前有效依据。</small></li></ul></details>
      </section>
      </template>
    </WorkbenchDialog>
    <WorkbenchDialog v-if="tab==='events'&&selectedEvent" class="space-drawer" title="事件详情" @close="go({event:''})">
      <button v-if="eventBack.length" class="text-link" @click="previousEvent">← 返回上一条查看记录</button>
      <h3 class="event-title">{{selectedEvent.summary}}</h3><p class="muted">{{selectedEvent.id}} · {{selectedEvent.type}} · {{selectedEvent.actor==='学生'?space.student:selectedEvent.actor}}</p>
      <div class="event-times"><span>发生：{{selectedEvent.occurredAt}}</span><span>记录：{{selectedEvent.recordedAt}}</span></div>
      <section class="detail-section"><h4>当时记录 <span class="badge">只读</span></h4><dl class="field-list"><template v-for="f in selectedEvent.fields" :key="f.label"><dt>{{f.label}}</dt><dd>{{f.value}}</dd></template></dl><div v-if="selectedEvent.table" class="table-scroll event-stimulus"><table class="data-table"><caption>{{selectedEvent.table.caption}}</caption><thead><tr><th v-for="c in selectedEvent.table.columns" :key="c">{{c}}</th></tr></thead><tbody><tr v-for="(row,i) in selectedEvent.table.rows" :key="i"><td v-for="(cell,j) in row" :key="j">{{cell}}</td></tr></tbody></table></div></section>
      <section v-if="selectedEvent.beliefChanges" class="detail-section"><h4>本次概率变化</h4><p class="muted">按方法和评价方面分别更新；更新事件用于留痕，不再作为新的能力证据。</p>
        <div class="table-scroll"><table class="data-table belief-changes"><thead><tr><th>方法 / 方面</th><th>更新前 → 更新后</th><th>依据</th></tr></thead><tbody><tr v-for="c in selectedEvent.beliefChanges" :key="c.claim+c.method+c.aspect"><td>{{aspectName(c.aspect)}}<small>{{c.method}}</small></td><td class="probability">{{probability(c.before)}} → {{probability(c.after)}}<small v-if="c.baseline!==undefined">重算基线：{{probability(c.baseline)}}</small></td><td><button class="text-link" :aria-label="'查看'+aspectName(c.aspect)+'的 Evidence'" @click="openEvent(c.evidenceEvent)">查看 Evidence</button><small v-for="id in c.evidenceIds" :key="id">{{id}}</small></td></tr></tbody></table></div>
        <p v-for="note in [...new Set(selectedEvent.beliefChanges.map(c=>c.note).filter(Boolean))]" :key="note" class="muted">{{note}}</p>
      </section>
      <section v-if="selectedEvent.evidence" class="detail-section"><h4>本次形成的 Evidence</h4><p class="muted">Evaluation 对原始事件的加工结果。同一检测轮用于多个评价方面，仍只算一次作答。</p>
        <article v-for="e in selectedEvent.evidence" :key="e.id" class="evidence-record"><div class="row-between"><strong>{{aspectName(e.aspect)}} · {{e.judgment}}</strong><span class="badge">{{e.attempt}}</span></div><small class="muted">{{e.id}}</small><p>{{e.method}} · {{e.claim}}</p><p><strong>判据：</strong>{{e.criterion}}</p><blockquote>{{e.quote}}</blockquote><p><strong>判断理由：</strong>{{e.reason}}</p><ul class="event-links"><li v-for="id in e.sources" :key="id"><button class="text-link" @click="openEvent(id)">{{lookup(id)?.type}}：{{lookup(id)?.summary}}</button></li></ul></article>
      </section>
      <section v-if="selectedEvent.causes.length" class="detail-section"><h4>引用的前序事件</h4><ul class="event-links"><li v-for="id in selectedEvent.causes" :key="id"><button class="text-link" @click="openEvent(id)">{{lookup(id)?.summary||id}}</button><small>{{id}}</small></li></ul></section>
      <section class="detail-section"><h4>后续关联</h4><p class="muted">由后续事件的引用关系形成，不改写上方的当时记录。</p><ul v-if="laterEvents.length" class="event-links"><li v-for="e in laterEvents" :key="e.id"><button class="text-link" @click="openEvent(e.id)">{{e.summary}}</button><small>{{e.type}} · {{e.recordedAt}}</small></li></ul><p v-else class="muted">暂无后续关联事件。</p></section>
      <section v-if="currentCells.length" class="detail-section"><h4>关联的当前目标项</h4><div class="relation-list"><button v-for="key in currentCells" :key="key" class="text-link" @click="backGoal(key)">{{cellLabel(key)}} → {{allCells.find(x=>x.cell.key===key)?.cell.status}}</button></div><p class="muted">这里进入当前状态；历史事件中的结果仍按发生当时保留。</p></section>
      <div class="button-row"><button class="btn" @click="surrounding(selectedEvent)">查看前后事件</button><button v-if="value('origin')" class="btn" @click="backGoal(value('origin'))">返回目标项</button></div>
    </WorkbenchDialog>
    <WorkbenchDialog v-if="definition" :title="tab==='book'?'教材采用说明':'当前采用的目标定义'" @close="definition=false">
      <p>{{tab==='book'?space.book:space.target}}</p><p class="muted">{{tab==='book'?space.bookVersion:space.targetVersion}} · {{space.adoptedAt}}</p><p v-if="tab==='book'">本页展示该空间采用的教材快照。这里的章节与真实原页用于演示；不是整册覆盖完成的证明，也不随公共教材的后续编辑自动改变。</p><template v-else><p>{{space.description}}</p><article v-for="t in space.tasks" :key="t.id" class="detail-section"><h4>{{t.name}}</h4><p>{{t.claim}} · {{t.mode==='all'?'所选方法分别达标':'所选方法任一达标'}}</p><ul><li v-for="m in t.methods" :key="m.id">{{m.name}}：{{requiredAspectNames(m.cells)}}</li></ul></article></template>
      <p class="muted">此处查看采用版本，不编辑公共定义，也不修改学生的选用结果。</p>
    </WorkbenchDialog>
    <WorkbenchDialog v-if="pagePreview" wide :title="'教材第 '+pagePreview+' 页'" @close="pagePreview=0"><img class="full-book-page" :src="'/materials/bnu6a/page-'+pagePreview+'.png'" :alt="'教材第 '+pagePreview+' 页原件'"/></WorkbenchDialog>
  </template>
  <section v-else class="panel empty"><h2>未找到学习空间</h2><p>当前 mock 中没有此空间，不展示其他学生的数据。</p><button class="btn" @click="backList">返回学习空间列表</button></section>
</section></template>

<style scoped>
.evidence-back{margin-bottom:20px}.evidence-quote{margin:12px 0;padding:12px 16px;border-left:3px solid #9bbfa9;background:#f6f9f7;line-height:1.7}.goal-evidence-list td{vertical-align:top}.goal-evidence-list th:first-child{width:130px}.goal-evidence-list th:last-child{width:60px}.replaced-evidence{margin-top:18px;color:#617583}.replaced-evidence summary{cursor:pointer}
.belief-basis .btn{margin-top:8px}.probability{font-variant-numeric:tabular-nums;white-space:nowrap}.belief-basis strong.probability{font-size:24px;color:#31543f}.belief-changes small{overflow-wrap:anywhere}.belief-changes th:nth-child(2){min-width:150px}.evidence-record{padding:16px;margin:14px 0;background:#f6f9f7;border:1px solid #e0e9e3;border-radius:8px}.evidence-record>small{display:block;margin-top:8px;overflow-wrap:anywhere}.evidence-record blockquote{margin:12px 0;padding:10px 14px;border-left:3px solid #9bbfa9;background:white;line-height:1.7}
.located-event{background:#edf7ef;outline:1px solid #9bbfa9;outline-offset:-1px}
.event-stimulus{margin-top:18px}.event-stimulus caption{text-align:left;margin-bottom:8px;font-size:12px;color:#74847b}
.space-heading{margin-top:12px;margin-bottom:14px}.space-filters{display:grid;grid-template-columns:1fr 1fr 1.3fr 1.3fr;gap:14px}.space-filters label,.event-filters label{margin:0}.filter-actions{display:flex;gap:8px;align-items:end;justify-content:flex-end;grid-column:1/-1}.space-columns{display:grid;grid-template-columns:215px minmax(0,1fr);gap:18px;align-items:start}.chapter-panel{padding:16px;position:sticky;top:12px}.chapter-panel label{margin-top:0}.chapter-button{width:100%;padding:13px 10px;border:0;border-left:3px solid transparent;border-radius:5px;background:none;color:#405a4c;text-align:left;line-height:1.6;margin:4px 0}.chapter-button.active{background:#eaf4ee;border-color:#2d6a4f;color:#24583f}.chapter-detail{min-height:320px}.chapter-detail .row-between h3{margin:0}.adoption-head{display:flex;justify-content:space-between;align-items:start;gap:20px}.adoption-head p{margin:6px 0}.adoption-head .btn{flex-shrink:0}.goal-task{border-top:1px solid #e3ebe6;margin-top:18px}.task-toggle{display:flex;justify-content:space-between;gap:18px;align-items:center;width:100%;border:0;background:none;text-align:left;padding:18px 0;color:#244837;font-weight:600}.task-toggle small{display:block;font-weight:400;color:#72877a;margin-top:6px}.status-label{display:inline-block;white-space:nowrap;padding:4px 10px;border-radius:5px;font-size:13px;font-weight:500}.passed{color:#256343;background:#edf7ef}.attention{color:#8a4d1c;background:#fff3e5}.unknown{color:#617583;background:#edf2f5}.goal-matrix{min-width:640px}.goal-matrix td{vertical-align:top}.goal-matrix th:first-child{width:30%}.cell-result{border:1px solid transparent;border-radius:5px;white-space:nowrap;padding:5px 9px;font-size:13px}.cell-result:hover{border-color:currentColor}.processing-note{color:#926325!important;max-width:100px}.event-filters{display:grid;grid-template-columns:1fr 1fr 1.1fr 1.2fr 1.4fr;gap:14px}.event-table{min-width:760px}.event-table td{vertical-align:top}.time-cell{width:160px;font-variant-numeric:tabular-nums}.event-table th:nth-child(4){width:35%}.filter-error{grid-column:1/-1;margin:0;color:#963f26}.book-pages{display:flex;gap:18px;flex-wrap:wrap;margin-top:20px}.page-thumb{background:#f7faf8;border:1px solid #d9e4dd;border-radius:6px;padding:8px;max-width:180px;color:#31543f}.page-thumb img{width:100%;height:210px;object-fit:contain;display:block;margin-bottom:8px}.full-book-page{width:100%;height:auto}.formula{font-family:Georgia,serif;font-size:21px}.space-drawer{margin:0 0 0 auto;width:min(700px,96vw);height:100dvh;max-height:100dvh;border-radius:12px 0 0 12px}.space-drawer :deep(.dialog-content){padding:24px}.detail-section{padding:18px 0;border-bottom:1px solid #e3ebe6}.detail-section h4{margin:0 0 12px;font-size:14px;color:#31543f}.detail-section p{margin:8px 0}.detail-section .field-list{grid-template-columns:100px minmax(0,1fr);gap:13px}.event-links{list-style:none;margin:0;padding:0}.event-links li{margin:12px 0}.event-links small{display:block;color:#7b8c81;font-size:11px;margin-top:2px}.event-title{margin-top:18px}.event-times{display:flex;flex-wrap:wrap;gap:8px 18px;font-size:12px;color:#74847b}
@media(max-width:1100px){.space-filters,.event-filters{grid-template-columns:repeat(2,minmax(0,1fr))}.space-columns{grid-template-columns:175px minmax(0,1fr)}.goal-matrix{min-width:540px}}
@media(max-width:760px){.space-columns{grid-template-columns:1fr}.chapter-panel{position:static}.chapter-panel nav{display:flex;flex-wrap:wrap}.chapter-button{width:auto}.adoption-head{flex-wrap:wrap}.space-filters,.event-filters{grid-template-columns:1fr}}
</style>
