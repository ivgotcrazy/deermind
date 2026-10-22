<script setup lang="ts">
import { computed, watch } from 'vue';
import { catalogForSpace, useView, sessionsForSpace } from '../workspace';
import { chapterCounts, displayRequirementState } from '../../../structure/home';
import { classroomIsCurrent, type Session } from '../../../structure/state';
const props = defineProps<{space:string}>();
const emit = defineEmits<{startAction:[text:string,chapter:string];resume:[session:Session]}>();
const view = useView(`status:${props.space}`,{search:'',p:1,selected:''});
const catalog = computed(()=>catalogForSpace(props.space));
const filtered = computed(()=>catalog.value.filter(c=>`${c.name} ${c.book} ${c.order}`.includes(view.search)));
const pages = computed(()=>Math.max(1,Math.ceil(filtered.value.length/8)));
const rows = computed(()=>filtered.value.slice((view.p-1)*8,view.p*8));
const selected = computed(()=>catalog.value.find(c=>c.id===view.selected));
const records = computed(()=>sessionsForSpace(props.space).filter(s=>s.real).slice(0,8));
watch(()=>view.search,()=>view.p=1);
watch(pages,()=>view.p=Math.min(view.p,pages.value));
</script>
<template><div class="learning-status-page">
 <div class="page-header"><h2>学习情况</h2><span class="data-caption">章节要求 · 预写展示参考</span></div>
 <div v-if="!catalog.length" class="empty">本空间教材尚未准备，暂无学习情况。</div>
 <template v-else>
 <div v-if="selected" class="section"><button class="back-link" @click="view.selected=''">← 返回章节概览</button><h3>{{ selected.name }}</h3><p class="data-caption">下列状态为预写参考，不根据真实对话自动更新。</p><ul class="requirement-list"><li v-for="(r,i) in selected.requirements" :key="r"><span>{{ r }}</span><span>{{ displayRequirementState('S0001',i,space) }}</span></li></ul><p v-if="!selected.requirements.length">本章尚未准备学习要求。</p><button class="action-btn" :disabled="selected.id!=='fractions'" @click="emit('startAction','我想弄懂分数的应用，请讲一个关键问题。',selected.id)">{{ selected.id==='fractions'?'请帮我讲讲':'教学内容准备中' }}</button></div>
 <div v-else class="section"><div class="section-header"><h3>章节学习概览</h3><input v-model="view.search" aria-label="查找章节" placeholder="查找章节、分册或单元"/></div><p class="data-caption">查看具体学习要求的已达标、需加强和待确认项数，不折算为掌握率。</p><div class="chapter-grid"><button v-for="chapter in rows" :key="chapter.id" class="chapter-card" @click="view.selected=chapter.id"><div class="cc-header"><span class="cc-name">{{ chapter.name }}</span><span v-if="classroomIsCurrent('S0001',space,chapter.id)" class="classroom-tag">课堂正在学</span></div><div v-if="chapter.reference" class="count-row"><span v-for="(n,i) in chapterCounts(chapter.id)" :key="i"><b>{{ n }}</b> {{ ['已达标','需加强','待确认'][i] }}</span></div><p v-else class="data-caption">尚无评价依据</p><span class="cc-unit">{{ chapter.book }} · {{ chapter.order }}</span></button></div><div class="pagination"><span>{{ filtered.length }} 章 · 第 {{ view.p }}/{{ pages }} 页</span><button :disabled="view.p<=1" @click="view.p--">上一页</button><button :disabled="view.p>=pages" @click="view.p++">下一页</button></div></div>
 </template>
 <div class="section"><div class="section-header"><h3>实际学习记录</h3><span class="data-caption">最近 8 次</span></div><div class="timeline"><div v-for="(r,i) in records" :key="r.id" class="timeline-item"><div class="tl-dot" style="background:#2d6a4f"/><div v-if="i<records.length-1" class="tl-line"/><div class="tl-content"><div class="tl-header"><span class="tl-date">{{ r.date }}</span><span class="tl-type">真实交流</span></div><span class="tl-title">分数的应用</span><span class="tl-detail">{{ r.realTurns||0 }} 条交流记录 · 尚未形成正式学习评价</span><button class="back-link" @click="emit('resume',r)">回看或继续 →</button></div></div></div><p v-if="!records.length" class="data-caption">还没有实际学习记录。</p></div>
</div></template>

<style scoped>
.learning-status-page { padding: 20px 24px; height: 100%; overflow-y: auto; }

.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.page-header h2 { margin: 0; font-size: 18px; color: #1a3a2e; }
.header-stats { display: flex; gap: 16px; }
.hs-item { display: flex; align-items: center; gap: 6px; font-size: 13px; color: #5a6b7a; }
.hs-dot { width: 8px; height: 8px; border-radius: 50%; }

.section { margin-bottom: 24px; }
.section h3 { margin: 0 0 12px 0; font-size: 14px; color: #1a3a2e; }
.section-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.section-header h3 { margin: 0; }

.chapter-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 10px; }
.chapter-card {
  background: white; border: 1px solid #e1e8ed; border-radius: 8px; padding: 12px;
}
.cc-header { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 6px; }
.cc-name { font-size: 13px; font-weight: 600; color: #2c3e50; }
.cc-mastery { font-size: 14px; font-weight: 700; }
.cc-bar { height: 6px; background: #f0f4f7; border-radius: 3px; overflow: hidden; margin-bottom: 4px; }
.cc-fill { height: 100%; border-radius: 3px; }
.cc-unit { font-size: 10px; color: #8a99a8; }

.weak-list { display: flex; flex-direction: column; gap: 10px; }
.weak-item {
  display: flex; justify-content: space-between; align-items: flex-start;
  background: #fef5f0; border: 1px solid #f0d0c0; border-radius: 8px; padding: 12px 14px;
}
.weak-info { display: flex; flex-direction: column; gap: 4px; flex: 1; }
.weak-name { font-size: 13px; font-weight: 600; color: #8a3a1a; }
.weak-reason { font-size: 11px; color: #a06a5a; }
.weak-suggestion { font-size: 11px; color: #5a7a6a; margin-top: 2px; }
.weak-mastery { font-size: 18px; font-weight: 700; color: #b85c3c; margin-left: 12px; }

.filter-tabs { display: flex; gap: 4px; }
.filter-tab {
  padding: 4px 12px; border: 1px solid #d0d7de; background: white;
  border-radius: 4px; font-size: 12px; cursor: pointer; font-family: inherit; color: #5a6b7a;
}
.filter-tab.active { background: #2d6a4f; color: white; border-color: #2d6a4f; }

.timeline { position: relative; padding-left: 8px; }
.timeline-item { position: relative; padding-bottom: 16px; padding-left: 24px; }
.timeline-item:last-child { padding-bottom: 0; }
.tl-dot { position: absolute; left: 0; top: 4px; width: 10px; height: 10px; border-radius: 50%; z-index: 1; }
.tl-line { position: absolute; left: 4px; top: 18px; width: 2px; height: calc(100% - 10px); background: #e1e8ed; }
.tl-content { background: white; border: 1px solid #e1e8ed; border-radius: 8px; padding: 10px 14px; }
.tl-header { display: flex; align-items: center; gap: 10px; margin-bottom: 4px; }
.tl-date { font-size: 11px; color: #8a99a8; }
.tl-type { font-size: 10px; padding: 2px 8px; border-radius: 8px; font-weight: 600; }
.tl-mastery { font-size: 11px; color: #2d8a5e; font-weight: 600; margin-left: auto; }
.tl-title { font-size: 13px; font-weight: 600; color: #2c3e50; display: block; margin-bottom: 2px; }
.tl-detail { font-size: 11px; color: #8a99a8; }

.learning-status-page{container-type:inline-size}.chapter-card{text-align:left;font-family:inherit;cursor:pointer}.chapter-grid{grid-template-columns:repeat(auto-fit,minmax(min(100%,230px),1fr))}.count-row{display:flex;flex-wrap:wrap;gap:10px;font-size:11px;margin:12px 0;color:#6b7a8a}.count-row b{font-size:16px;color:#2d6a4f}.data-caption{font-size:11px;color:#7e8f85;line-height:1.7;margin-bottom:10px}.requirement-list{list-style:none}.requirement-list li{display:flex;justify-content:space-between;gap:16px;border-bottom:1px solid #edf2ef;padding:12px 0;font-size:13px}.requirement-list li span:last-child{flex-shrink:0;color:#76887c}.back-link{background:none;border:0;color:#2d6a4f;font-size:12px;cursor:pointer;margin:10px 0}.action-btn{margin-top:16px;background:#2d6a4f;color:white;border:0;border-radius:6px;padding:8px 14px}.section-header{flex-wrap:wrap;gap:8px}.section-header input{min-width:0;max-width:100%;font-size:12px;border:1px solid #d7e3db;padding:7px 10px;border-radius:6px}.pagination{display:flex;align-items:center;justify-content:flex-end;gap:8px;font-size:11px;margin-top:16px}.pagination button{padding:5px 8px;background:white;border:1px solid #d7e3db;border-radius:5px}.classroom-tag{color:#2d6a4f;font-size:10px;background:#e8f5ee;padding:3px 5px;white-space:nowrap}.empty{padding:24px;color:#809084}
@container(max-width:520px){.chapter-grid{grid-template-columns:1fr}.page-header{flex-wrap:wrap;gap:8px}}

</style>
