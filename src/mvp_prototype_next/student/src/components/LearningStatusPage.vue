<script setup lang="ts">
import { ref, computed } from 'vue';
import { textbookData, learningOverview } from '../data';
import type { Chapter } from '../types';

const recordFilter = ref('all');

// 按章节组织的掌握概览
const chapterMastery = computed(() => {
  const list: { chapter: Chapter; unit: string }[] = [];
  for (const unit of textbookData.units) {
    for (const ch of unit.chapters) {
      if (ch.mastery > 0) list.push({ chapter: ch, unit: unit.name });
    }
  }
  return list.sort((a, b) => a.chapter.mastery - b.chapter.mastery);
});

const masteredCount = computed(() => chapterMastery.value.filter(c => c.chapter.mastery >= 80).length);
const developingCount = computed(() => chapterMastery.value.filter(c => c.chapter.mastery >= 60 && c.chapter.mastery < 80).length);
const weakCount = computed(() => chapterMastery.value.filter(c => c.chapter.mastery < 60).length);

// 学习记录
interface LearningRecord {
  date: string; type: 'lecture' | 'practice' | 'test' | 'error';
  title: string; detail: string; masteryChange?: string;
}
const allRecords: LearningRecord[] = [
  { date: '10-18 14:30', type: 'lecture', title: '讲解：比例的应用', detail: '比较标准量 · 第2段', masteryChange: '62→65%' },
  { date: '10-18 14:15', type: 'practice', title: '练习：分数加法', detail: '3/5 正确', masteryChange: '60→62%' },
  { date: '10-17 19:20', type: 'test', title: '自测：第三单元 圆柱与圆锥', detail: '完成度 80% · 5题', masteryChange: '68→70%' },
  { date: '10-17 19:00', type: 'lecture', title: '讲解：圆锥的体积', detail: '体积公式推导', masteryChange: '65→68%' },
  { date: '10-16 20:10', type: 'error', title: '错题：比较标准量', detail: '甲比乙多1/3，乙比甲少几分之几', masteryChange: '—' },
  { date: '10-16 20:00', type: 'practice', title: '练习：连续变化问题', detail: '2/4 正确', masteryChange: '58→60%' },
  { date: '10-15 18:30', type: 'lecture', title: '讲解：分数乘法', detail: '连续变化问题', masteryChange: '55→58%' },
  { date: '10-15 18:15', type: 'error', title: '错题：连续变化问题', detail: '先涨1/10再降1/10', masteryChange: '—' },
];

const filteredRecords = computed(() => {
  if (recordFilter.value === 'all') return allRecords;
  return allRecords.filter(r => r.type === recordFilter.value);
});

const typeLabels: Record<string, string> = {
  lecture: '讲解', practice: '练习', test: '自测', error: '错题',
};
const typeColors: Record<string, string> = {
  lecture: '#2d6a4f', practice: '#4a6fa5', test: '#c9942a', error: '#b85c3c',
};

function masteryColor(v: number): string {
  if (v >= 80) return '#2d8a5e';
  if (v >= 60) return '#c9942a';
  return '#b85c3c';
}
</script>

<template>
  <div class="learning-status-page">
    <!-- 顶部统计 -->
    <div class="page-header">
      <h2>学习情况</h2>
      <div class="header-stats">
        <span class="hs-item"><span class="hs-dot" style="background:#2d8a5e"></span>已掌握 {{ masteredCount }}</span>
        <span class="hs-item"><span class="hs-dot" style="background:#c9942a"></span>发展中 {{ developingCount }}</span>
        <span class="hs-item"><span class="hs-dot" style="background:#b85c3c"></span>需加强 {{ weakCount }}</span>
      </div>
    </div>

    <!-- 章节掌握概览 -->
    <div class="section">
      <h3>章节掌握概览</h3>
      <div class="chapter-grid">
        <div v-for="item in chapterMastery" :key="item.chapter.id" class="chapter-card">
          <div class="cc-header">
            <span class="cc-name">{{ item.chapter.name }}</span>
            <span class="cc-mastery" :style="{color: masteryColor(item.chapter.mastery)}">{{ item.chapter.mastery }}%</span>
          </div>
          <div class="cc-bar"><div class="cc-fill" :style="{width: item.chapter.mastery + '%', background: masteryColor(item.chapter.mastery)}"></div></div>
          <span class="cc-unit">{{ item.unit }}</span>
        </div>
      </div>
    </div>

    <!-- 薄弱知识点 -->
    <div class="section">
      <h3>薄弱知识点</h3>
      <div class="weak-list">
        <div v-for="w in learningOverview.weakPoints" :key="w.name" class="weak-item">
          <div class="weak-info">
            <span class="weak-name">{{ w.name }}</span>
            <span class="weak-reason">{{ w.reason }}</span>
            <span class="weak-suggestion">💡 {{ w.suggestion }}</span>
          </div>
          <span class="weak-mastery">{{ w.mastery }}%</span>
        </div>
      </div>
    </div>

    <!-- 学习记录 -->
    <div class="section">
      <div class="section-header">
        <h3>学习记录</h3>
        <div class="filter-tabs">
          <button v-for="f in ['all','lecture','practice','test','error']" :key="f"
            class="filter-tab" :class="{active: recordFilter === f}"
            @click="recordFilter = f">
            {{ f === 'all' ? '全部' : typeLabels[f] }}
          </button>
        </div>
      </div>
      <div class="timeline">
        <div v-for="(r, i) in filteredRecords" :key="i" class="timeline-item">
          <div class="tl-dot" :style="{background: typeColors[r.type]}"></div>
          <div v-if="i < filteredRecords.length - 1" class="tl-line"></div>
          <div class="tl-content">
            <div class="tl-header">
              <span class="tl-date">{{ r.date }}</span>
              <span class="tl-type" :style="{background: typeColors[r.type] + '22', color: typeColors[r.type]}">{{ typeLabels[r.type] }}</span>
              <span v-if="r.masteryChange" class="tl-mastery">{{ r.masteryChange }}</span>
            </div>
            <span class="tl-title">{{ r.title }}</span>
            <span class="tl-detail">{{ r.detail }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

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
</style>
