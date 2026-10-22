<script setup lang="ts">
import { computed } from 'vue';
import { catalogForSpace, useView } from '../workspace';
import { classroomIsCurrent } from '../../../structure/state';
const props = defineProps<{space:string}>();
const emit = defineEmits<{startAction:[text:string,chapter:string]}>();
const view = useView(`textbook:${props.space}`, {search:'', expanded:['六年级上册'] as string[]});
const catalog = computed(()=>catalogForSpace(props.space));
const groups = computed(()=>[...new Set(catalog.value.map(c=>c.book))].map(book=>({id:book,name:book,chapters:catalog.value.filter(c=>c.book===book&&`${c.name} ${c.order} ${c.unit}`.includes(view.search))})).filter(g=>g.chapters.length));
function toggle(id:string){view.expanded=view.expanded.includes(id)?view.expanded.filter(x=>x!==id):[...view.expanded,id];}
</script>
<template><div class="textbook-page">
 <div class="page-header"><div><h2>教材</h2><span class="header-sub">{{ space==='school'?'北师大版 · 六年级上册 · 数学':'校外数学 · 教材待准备' }}</span></div><div class="header-stats"><div class="hs-card"><span class="hs-value">{{ catalog.length }}</span><span class="hs-label">已收录条目</span></div></div></div>
 <p class="data-caption">目前仅“分数的应用”接通真实教学；其他条目用于目录展示。</p><input v-model="view.search" class="catalog-search" aria-label="查找教材章节" placeholder="查找章节或单元"/>
 <div class="unit-list"><div v-for="unit in groups" :key="unit.id" class="unit-block"><button class="unit-header" @click="toggle(unit.id)" :aria-expanded="view.expanded.includes(unit.id)"><span class="unit-toggle">{{ view.expanded.includes(unit.id)?'▼':'▶' }}</span><span class="unit-name">{{ unit.name }}</span><span class="unit-count">{{ unit.chapters.length }} 节</span></button>
 <div v-if="view.expanded.includes(unit.id)||view.search" class="chapter-list"><div v-for="ch in unit.chapters.slice(0,view.search?100:20)" :key="ch.id" class="chapter-row"><div class="ch-info"><div class="ch-title-row"><span class="ch-name">{{ ch.name }}</span><span v-if="classroomIsCurrent('S0001',space,ch.id)" class="ch-tag taught">课堂正在学</span></div><span class="ch-desc">{{ ch.order }} · {{ ch.requirements[0] || '内容准备中' }}</span></div><div class="ch-right"><button class="ch-action learn" :disabled="ch.id!=='fractions'" @click="emit('startAction',`给我讲一下${ch.name}，先从一个关键问题开始。`,ch.id)">{{ ch.id==='fractions'?'开始讲解':'准备中' }}</button></div></div><p v-if="!view.search&&unit.chapters.length>20" class="data-caption">先显示前 20 节，可通过搜索定位其他章节。</p></div>
 </div></div><p v-if="!groups.length" class="data-caption">{{ catalog.length?'没有符合条件的章节。':'本空间还没有教材。' }}</p>
</div></template>

<style scoped>
.textbook-page { padding: 20px 24px; height: 100%; overflow-y: auto; }

.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px; }
.page-header h2 { margin: 0; font-size: 18px; color: #1a3a2e; }
.header-sub { font-size: 12px; color: #8a99a8; }
.header-stats { display: flex; gap: 12px; }
.hs-card {
  background: white; border: 1px solid #e1e8ed; border-radius: 8px;
  padding: 8px 14px; text-align: center; min-width: 60px;
}
.hs-value { display: block; font-size: 16px; font-weight: 700; color: #1a3a2e; }
.hs-label { font-size: 10px; color: #8a99a8; }

.legend { display: flex; gap: 16px; margin-bottom: 16px; flex-wrap: wrap; }
.legend-item { display: flex; align-items: center; gap: 6px; font-size: 12px; color: #5a6b7a; }
.lg-dot { width: 10px; height: 10px; border-radius: 50%; }
.lg-tag {
  display: inline-flex; align-items: center; justify-content: center;
  width: 18px; height: 18px; border-radius: 4px; font-size: 10px; font-weight: 700;
}
.lg-tag.taught { background: #e8f0fe; color: #2a5a9a; }

.unit-block { margin-bottom: 8px; }
.unit-header {
  display: flex; align-items: center; gap: 8px; padding: 10px 14px;
  background: #f7f9fa; border: 1px solid #e1e8ed; border-radius: 8px;
  cursor: pointer; font-weight: 600; color: #2c3e50; font-size: 14px;
}
.unit-toggle { font-size: 10px; color: #8a99a8; width: 12px; }
.unit-name { flex: 1; }
.unit-count { font-size: 11px; color: #8a99a8; font-weight: 400; }

.chapter-list { margin-top: 4px; display: flex; flex-direction: column; gap: 6px; }
.chapter-row {
  display: flex; justify-content: space-between; align-items: center; gap: 16px;
  background: white; border: 1px solid #e1e8ed; border-radius: 8px; padding: 12px 16px;
}
.ch-info { flex: 1; min-width: 0; }
.ch-title-row { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; flex-wrap: wrap; }
.ch-name { font-size: 14px; font-weight: 600; color: #2c3e50; }
.ch-tag {
  font-size: 10px; padding: 2px 6px; border-radius: 4px; font-weight: 600;
}
.ch-tag.taught { background: #e8f0fe; color: #2a5a9a; }
.ch-tag.not-taught { background: #f0f4f7; color: #8a99a8; }
.ch-anomaly { font-size: 11px; color: #c9942a; background: #fef9e8; padding: 2px 8px; border-radius: 4px; }
.ch-desc { font-size: 11px; color: #8a99a8; display: block; margin-bottom: 6px; }
.ch-meta { display: flex; gap: 16px; flex-wrap: wrap; }
.ch-evidence { font-size: 11px; color: #5a6b7a; }
.ch-topics { font-size: 11px; color: #5a6b7a; }
.ch-weak-tag {
  background: #fef5f0; color: #b85c3c; padding: 1px 6px; border-radius: 3px;
  margin-left: 4px; font-size: 10px;
}

.ch-right { display: flex; align-items: center; gap: 16px; flex-shrink: 0; }
.ch-mastery { display: flex; flex-direction: column; align-items: flex-end; gap: 4px; width: 100px; }
.cm-value { font-size: 18px; font-weight: 700; }
.cm-bar { width: 100%; height: 5px; background: #f0f4f7; border-radius: 3px; overflow: hidden; }
.cm-fill { height: 100%; border-radius: 3px; }
.ch-action {
  padding: 6px 14px; border-radius: 6px; font-size: 12px; font-weight: 600;
  cursor: pointer; font-family: inherit; border: none; white-space: nowrap;
}
.ch-action.test { background: #fef5e0; color: #8a6a1a; }
.ch-action.test:hover { background: #fde9b8; }
.ch-action.learn { background: #fef5f0; color: #8a3a1a; }
.ch-action.learn:hover { background: #fce0d0; }
.ch-action.practice { background: #e8f0fe; color: #2a5a9a; }
.ch-action.practice:hover { background: #d0e0fc; }
.ch-action.review { background: #e8f5ee; color: #1b4332; }
.ch-action.review:hover { background: #d0ecd8; }
.ch-no-action { color: #c0c8d0; font-size: 14px; width: 70px; text-align: center; }

.textbook-page{container-type:inline-size}.unit-header{width:100%;border:0;text-align:left;font-family:inherit}.chapter-row{min-width:0}.ch-info{min-width:0}.ch-name,.ch-desc{overflow-wrap:anywhere}.ch-right{flex-shrink:0}.data-caption{font-size:11px;color:#809084;line-height:1.7;margin-bottom:14px}.catalog-search{width:100%;padding:9px 12px;border:1px solid #d7e3db;border-radius:7px;font-family:inherit;margin-bottom:16px}
@container(max-width:520px){.chapter-row{align-items:flex-start;gap:10px}.ch-title-row{flex-wrap:wrap}.ch-action{padding:6px 9px;font-size:11px}.header-stats{gap:12px}.page-header{gap:12px}}

</style>
