<script setup lang="ts">
import {computed,ref} from 'vue';
import {students} from '../data';
import type {Student,StudentLS} from '../types';
const emit=defineEmits<{goTrace:[traceId:string]}>();
const search=ref(''),selected=ref<Student>(),space=ref<StudentLS>(),page=ref(1);
const filtered=computed(()=>students.filter(s=>`${s.name} ${s.id}`.includes(search.value)));
const pages=computed(()=>Math.max(1,Math.ceil(filtered.value.length/15)));
const rows=computed(()=>filtered.value.slice((page.value-1)*15,page.value*15));
const dimensions=['独立完成','理解与解释','迁移应用','延迟保持'];
</script>
<template><div class="student-list" style="padding:24px">
 <h2>学生画像</h2><p class="integration-explanation">以下为合成学生目录。能力状态按 Task Claim 的内部方面查看；正式多维推断尚未接入，不用原来的 KC 百分比代替。</p>
 <template v-if="!selected"><input v-model="search" aria-label="查找学生" placeholder="搜索学生或编号" @input="page=1"/><div class="profile-table"><button v-for="student in rows" :key="student.id" @click="selected=student;space=undefined"><b>{{ student.name }}</b><span>{{ student.id }} · {{ student.grade }} · {{ student.learningSpaces.length }} 个空间</span></button></div><div class="profile-pages"><span>{{ filtered.length }} 人 · {{ page }}/{{ pages }}</span><button :disabled="page===1" @click="page--">上一页</button><button :disabled="page>=pages" @click="page++">下一页</button></div></template>
 <template v-else><button @click="selected=undefined;space=undefined">← 学生列表</button><h3>{{ selected.name }} · {{ selected.id }}</h3><div class="profile-tabs"><button v-for="ls in selected.learningSpaces" :key="ls.id" @click="space=ls">{{ ls.name }}</button></div>
 <template v-if="space"><h3>{{ space.name }} · {{ space.textbook }}</h3><div class="profile-claims"><article v-for="belief in space.beliefs" :key="belief.claim"><h4>{{ belief.claim }}</h4><div class="profile-aspects"><div v-for="dimension in dimensions" :key="dimension"><b>{{ dimension }}</b><p>未接入正式判断</p></div></div><p>原示例的整体单值不转换为四方面状态。</p></article></div>
 <section><h3>教学解释线索</h3><p>KC 保留领域与教学作用，不维护 KC 掌握状态。以下为示例关联，需核对具体任务与证据。</p><p v-for="kc in space.weakKCs" :key="kc.kcId">{{ kc.kcId }} · {{ kc.kcName }}</p></section>
 <section><h3>示例活动与轨迹</h3><article v-for="episode in space.episodes" :key="episode.date+episode.title"><p>{{ episode.date }} · {{ episode.title }}</p><button v-for="id in episode.traceIds" :key="id" @click="emit('goTrace',id)">查看 {{ id }}</button></article></section></template>
 <p v-else>选择一个学习空间，查看其任务评价与记录。不同空间分别查看。</p></template>
</div></template>
<style scoped>
.student-profile { padding: 20px 24px; height: 100%; overflow-y: auto; }
.page-header { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 16px; }
.page-header h2 { margin: 0; font-size: 18px; color: #1a3a2e; }
.header-sub { font-size: 12px; color: #8a99a8; }

/* 系统统计 */
.sys-stats { display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; margin-bottom: 16px; }
.sys-stat { background: white; border: 1px solid #e1e8ed; border-radius: 10px; padding: 14px; display: flex; flex-direction: column; gap: 4px; }
.ss-label { font-size: 11px; color: #8a99a8; }
.ss-value { font-size: 24px; font-weight: 700; color: #1a3a2e; }
.ss-value.warn { color: #b85c3c; }

/* 筛选 */
.filter-bar { display: flex; gap: 10px; margin-bottom: 16px; flex-wrap: wrap; }
.filter-select { padding: 7px 12px; border: 1px solid #d0d7de; border-radius: 6px; font-size: 13px; font-family: inherit; background: white; }
.filter-search { flex: 1; min-width: 160px; padding: 7px 12px; border: 1px solid #d0d7de; border-radius: 6px; font-size: 13px; font-family: inherit; }
.filter-search:focus { outline: none; border-color: #2d6a4f; }

/* 学生表格 */
.student-table { background: white; border: 1px solid #e1e8ed; border-radius: 10px; overflow: hidden; }
.table-header { display: flex; padding: 12px 16px; background: #f7f9fa; border-bottom: 1px solid #e1e8ed; font-size: 12px; font-weight: 600; color: #5a6b7a; }
.table-row { display: flex; padding: 12px 16px; border-bottom: 1px solid #f5f7fa; cursor: pointer; align-items: center; font-size: 13px; transition: background 0.1s; }
.table-row:hover { background: #f5f9f7; }
.col-name { width: 120px; flex-shrink: 0; display: flex; align-items: center; gap: 8px; font-weight: 500; }
.row-avatar { width: 28px; height: 28px; border-radius: 50%; background: linear-gradient(135deg, #2d6a4f, #40916c); color: white; display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 600; flex-shrink: 0; }
.col-grade { width: 70px; flex-shrink: 0; color: #5a6b7a; }
.col-ls { width: 180px; flex-shrink: 0; display: flex; flex-direction: column; gap: 2px; }
.ls-count { font-size: 11px; color: #4a6fa5; font-weight: 600; }
.ls-primary { font-size: 11px; color: #8a99a8; }
.col-num { width: 90px; flex-shrink: 0; text-align: center; }
.col-num.sortable { cursor: pointer; user-select: none; }
.col-num.sortable:hover { color: #2d6a4f; }
.col-time { width: 110px; flex-shrink: 0; color: #8a99a8; font-size: 12px; }
.col-time.sortable { cursor: pointer; }
.col-action { width: 80px; flex-shrink: 0; text-align: right; }
.mastery-inline { font-weight: 600; }
.warn { color: #b85c3c !important; font-weight: 600; }
.mono { font-family: Consolas, Monaco, monospace; }
.detail-btn { background: none; border: none; color: #2d6a4f; font-size: 12px; cursor: pointer; font-family: inherit; font-weight: 500; }
.detail-btn:hover { text-decoration: underline; }
.pagination { padding: 12px 0; font-size: 12px; color: #8a99a8; }

/* 详情头部 */
.detail-header { display: flex; align-items: center; gap: 16px; margin-bottom: 16px; }
.back-btn { background: none; border: 1px solid #d0d7de; color: #5a6b7a; padding: 6px 14px; border-radius: 6px; font-size: 13px; cursor: pointer; font-family: inherit; flex-shrink: 0; }
.back-btn:hover { background: #f0f4f7; }
.detail-title { display: flex; align-items: center; gap: 12px; flex: 1; }
.detail-title h2 { margin: 0; font-size: 18px; color: #1a3a2e; }
.detail-sub { font-size: 12px; color: #8a99a8; }
.student-avatar { width: 40px; height: 40px; border-radius: 50%; background: linear-gradient(135deg, #2d6a4f, #40916c); color: white; display: flex; align-items: center; justify-content: center; font-size: 16px; font-weight: 600; flex-shrink: 0; }
.student-avatar.large { width: 48px; height: 48px; font-size: 20px; }
.ls-icon { font-size: 24px; flex-shrink: 0; }
.ls-icon-large { font-size: 32px; flex-shrink: 0; }
.ls-status-tag { padding: 4px 10px; border-radius: 6px; font-size: 11px; font-weight: 600; flex-shrink: 0; }
.ls-status-tag.large { padding: 6px 14px; font-size: 13px; }
.ls-status-tag.active { background: #e8f5ee; color: #1b4332; }
.ls-status-tag.paused { background: #f0f4f7; color: #8a99a8; }

/* 概览 */
.overview-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; margin-bottom: 16px; }
.ov-card { background: white; border: 1px solid #e1e8ed; border-radius: 10px; padding: 14px; display: flex; flex-direction: column; gap: 4px; }
.ov-card.primary { border-left: 3px solid #2d6a4f; }
.ov-label { font-size: 11px; color: #8a99a8; }
.ov-value { font-size: 22px; font-weight: 700; color: #1a3a2e; line-height: 1.2; }
.ov-value.warn { color: #b85c3c; }
.ov-sub { font-size: 11px; color: #5a7a6a; }

.section-title { margin: 20px 0 12px 0; font-size: 14px; color: #1a3a2e; }

/* LS卡片 */
.ls-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 14px; }
.ls-card { background: white; border: 1px solid #e1e8ed; border-radius: 12px; padding: 16px; cursor: pointer; transition: all 0.2s; }
.ls-card:hover { border-color: #2d6a4f; box-shadow: 0 4px 12px rgba(45,106,79,0.1); transform: translateY(-2px); }
.ls-card.paused { opacity: 0.7; }
.ls-card-header { display: flex; align-items: center; gap: 10px; margin-bottom: 14px; }
.ls-info h4 { margin: 0; font-size: 14px; color: #1a3a2e; }
.ls-meta { font-size: 11px; color: #8a99a8; }
.ls-card-header .ls-status-tag { margin-left: auto; }
.ls-card-stats { display: flex; justify-content: space-around; padding: 10px 0; border-top: 1px solid #f0f4f7; border-bottom: 1px solid #f0f4f7; margin-bottom: 10px; }
.ls-stat { text-align: center; }
.ls-stat-value { display: block; font-size: 18px; font-weight: 700; color: #1a3a2e; }
.ls-stat-value.warn { color: #b85c3c; }
.ls-stat-label { font-size: 10px; color: #8a99a8; }
.ls-card-footer { display: flex; justify-content: space-between; align-items: center; }
.ls-beliefs { display: flex; gap: 4px; flex-wrap: wrap; }
.ls-belief-tag { font-size: 10px; background: #f0f4f7; color: #5a6b7a; padding: 2px 6px; border-radius: 3px; }
.ls-view { font-size: 12px; color: #2d6a4f; font-weight: 600; flex-shrink: 0; }

/* Tab */
.tab-bar { display: flex; gap: 4px; margin-bottom: 16px; border-bottom: 2px solid #e1e8ed; }
.tab { padding: 8px 20px; background: none; border: none; border-bottom: 2px solid transparent; font-size: 14px; color: #5a6b7a; cursor: pointer; font-family: inherit; margin-bottom: -2px; }
.tab.active { color: #1b4332; font-weight: 600; border-bottom-color: #2d6a4f; }

.content-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.panel { background: white; border: 1px solid #e1e8ed; border-radius: 10px; padding: 16px; }
.panel.wide { grid-column: 1 / -1; }
.panel h3 { margin: 0 0 14px 0; font-size: 14px; color: #1a3a2e; }
.empty-small { text-align: center; padding: 30px; color: #8a99a8; font-size: 13px; }

/* 学习状态 */
.belief-detail { margin-bottom: 16px; }
.belief-detail:last-child { margin-bottom: 0; }
.belief-detail-header { display: flex; justify-content: space-between; margin-bottom: 6px; }
.bd-name { font-size: 13px; font-weight: 500; color: #2c3e50; }
.bd-change { font-size: 12px; color: #b85c3c; font-weight: 600; }
.bd-change.up { color: #2d8a5e; }
.bd-bar { height: 8px; background: #f0f4f7; border-radius: 4px; overflow: hidden; margin-bottom: 4px; }
.bd-fill { height: 100%; border-radius: 4px; }
.bd-range { display: flex; justify-content: space-between; font-size: 11px; color: #8a99a8; }
.weak-list { display: flex; flex-direction: column; gap: 10px; }
.weak-item { display: flex; align-items: center; gap: 10px; padding: 8px; background: #fafbfc; border-radius: 6px; }
.weak-info { display: flex; flex-direction: column; gap: 2px; width: 120px; flex-shrink: 0; }
.weak-id { font-size: 10px; color: #8a99a8; }
.weak-name { font-size: 12px; color: #2c3e50; font-weight: 500; }
.weak-mastery { flex: 1; display: flex; align-items: center; gap: 8px; }
.wm-bar { flex: 1; height: 6px; background: #f0f4f7; border-radius: 3px; overflow: hidden; }
.wm-fill { height: 100%; border-radius: 3px; }
.wm-value { width: 32px; text-align: right; font-size: 12px; font-weight: 600; }
.weak-evidence { font-size: 11px; color: #8a99a8; width: 60px; text-align: right; flex-shrink: 0; }
.trend-chart { padding: 10px 0; }
.trend-bars { display: flex; justify-content: space-around; align-items: flex-end; height: 140px; gap: 8px; }
.trend-col { display: flex; flex-direction: column; align-items: center; gap: 4px; flex: 1; }
.trend-bar-wrap { height: 80px; display: flex; align-items: flex-end; width: 100%; justify-content: center; }
.trend-bar { width: 32px; background: linear-gradient(180deg, #52b788, #2d6a4f); border-radius: 4px 4px 0 0; min-height: 4px; }
.trend-value { font-size: 11px; font-weight: 600; color: #2c3e50; }
.trend-date { font-size: 10px; color: #8a99a8; }

/* 交互统计 */
.action-dist { display: flex; flex-direction: column; gap: 12px; }
.action-row { display: flex; align-items: center; gap: 10px; }
.action-label { width: 40px; font-size: 13px; color: #3a4a5a; flex-shrink: 0; }
.action-bar { flex: 1; height: 16px; background: #f0f4f7; border-radius: 4px; overflow: hidden; }
.action-fill { height: 100%; border-radius: 4px; min-width: 2px; }
.action-count { width: 30px; text-align: right; font-weight: 600; color: #2c3e50; font-size: 13px; }
.quality-list { display: flex; flex-direction: column; gap: 14px; }
.quality-item { display: flex; flex-direction: column; gap: 2px; padding-bottom: 12px; border-bottom: 1px solid #f0f4f7; }
.quality-item:last-child { border-bottom: none; padding-bottom: 0; }
.q-label { font-size: 12px; color: #8a99a8; }
.q-value { font-size: 20px; font-weight: 700; color: #1a3a2e; }
.q-value.warn { color: #b85c3c; }
.q-desc { font-size: 11px; color: #a0aab8; }

/* 学习轨迹 */
.timeline-panel { background: white; border: 1px solid #e1e8ed; border-radius: 10px; padding: 16px; }
.timeline { position: relative; padding-left: 8px; }
.timeline-item { position: relative; padding-bottom: 20px; padding-left: 24px; }
.timeline-item:last-child { padding-bottom: 0; }
.tl-dot { position: absolute; left: 0; top: 4px; width: 12px; height: 12px; border-radius: 50%; background: #2d6a4f; border: 2px solid white; box-shadow: 0 0 0 2px #2d6a4f; z-index: 1; }
.tl-dot.practice { background: #4a6fa5; box-shadow: 0 0 0 2px #4a6fa5; }
.tl-dot.qa { background: #c9942a; box-shadow: 0 0 0 2px #c9942a; }
.tl-dot.review { background: #8a99a8; box-shadow: 0 0 0 2px #8a99a8; }
.tl-line { position: absolute; left: 5px; top: 18px; width: 2px; height: calc(100% - 10px); background: #e1e8ed; }
.tl-content { background: #fafbfc; border-radius: 8px; padding: 12px 14px; }
.tl-header { display: flex; align-items: center; gap: 10px; margin-bottom: 6px; }
.tl-date { font-size: 12px; color: #8a99a8; font-weight: 500; }
.tl-type { font-size: 10px; padding: 2px 8px; border-radius: 8px; font-weight: 600; }
.tl-type.lecture { background: #e8f5ee; color: #1b4332; }
.tl-type.practice { background: #e8f0f8; color: #2a4a6a; }
.tl-type.qa { background: #fef5e0; color: #6a5a1a; }
.tl-type.review { background: #f0f4f7; color: #5a6b7a; }
.tl-mastery { font-size: 11px; color: #2d8a5e; font-weight: 600; margin-left: auto; }
.tl-title { font-size: 13px; color: #2c3e50; font-weight: 500; display: block; margin-bottom: 8px; }
.tl-traces { display: flex; gap: 6px; flex-wrap: wrap; }
.tl-trace-btn { background: none; border: 1px solid #d0d7de; color: #2d6a4f; padding: 3px 10px; border-radius: 4px; font-size: 11px; cursor: pointer; font-family: inherit; }
.tl-trace-btn:hover { background: #e8f5ee; border-color: #2d6a4f; }

@media (max-width: 1200px) {
  .sys-stats, .overview-grid { grid-template-columns: repeat(3, 1fr); }
  .content-grid { grid-template-columns: 1fr; }
}
</style>

<style scoped>
.integration-explanation{margin:16px 0;color:#718579;line-height:1.8}.profile-table{display:grid;gap:10px;margin:20px 0}.profile-table>button{display:flex;justify-content:space-between;padding:16px;text-align:left;background:white;border:1px solid #dde6e1;border-radius:8px;cursor:pointer}.profile-tabs,.profile-pages{display:flex;gap:12px;align-items:center;margin:16px 0}.profile-claims article{border:1px solid #e1e8ed;border-radius:8px;padding:18px;margin:16px 0;background:white}.profile-aspects{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:16px 0}.profile-aspects p{margin-top:10px;color:#8a99a8}.profile-claims+section{margin:24px 0}.student-list h3{margin:18px 0}.student-list button,.student-list input{font:inherit;padding:8px;border:1px solid #d3ddd6;border-radius:6px;background:white}.student-list button{cursor:pointer}.student-list button:disabled{opacity:.5}
</style>
