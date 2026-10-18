<script setup lang="ts">
import { ref, computed } from 'vue';
import { textbookData } from '../data';
import type { Chapter } from '../types';

const emit = defineEmits<{
  startAction: [text: string];
}>();

// 模拟学校进度：哪些章节学校已经教过
const taughtChapterIds = new Set([
  'c1-1', 'c1-2', 'c2-1', 'c2-2', 'c2-3', 'c2-4',
  'c3-1', 'c3-2', 'c3-3', 'c3-4', 'c3-5',
  'c4-1', 'c4-2', 'c4-3',
]);

// 模拟证据数量
const evidenceCount: Record<string, number> = {
  'c1-1': 12, 'c1-2': 8, 'c2-1': 10, 'c2-2': 6, 'c2-3': 5, 'c2-4': 4,
  'c3-1': 8, 'c3-2': 6, 'c3-3': 5, 'c3-4': 4, 'c3-5': 3,
  'c4-1': 6, 'c4-2': 4, 'c4-3': 8, 'c4-4': 0, 'c5-1': 2,
};

const expandedUnits = ref<Set<string>>(new Set(['unit4']));

function toggleUnit(unitId: string) {
  if (expandedUnits.value.has(unitId)) expandedUnits.value.delete(unitId);
  else expandedUnits.value.add(unitId);
}

interface ChapterStatus {
  taught: boolean;
  hasEvidence: boolean;
  masteryLevel: 'mastered' | 'developing' | 'weak' | 'unknown';
  action: { label: string; type: string } | null;
  anomaly: boolean;
}

function getChapterStatus(ch: Chapter): ChapterStatus {
  const taught = taughtChapterIds.has(ch.id);
  const evidence = evidenceCount[ch.id] || 0;
  const hasEvidence = evidence > 0;
  const mastery = ch.mastery;

  let masteryLevel: ChapterStatus['masteryLevel'] = 'unknown';
  if (hasEvidence) {
    if (mastery >= 80) masteryLevel = 'mastered';
    else if (mastery >= 60) masteryLevel = 'developing';
    else masteryLevel = 'weak';
  }

  let action: ChapterStatus['action'] = null;
  if (taught && !hasEvidence) action = { label: '开始自测', type: 'test' };
  else if (taught && masteryLevel === 'weak') action = { label: '继续学习', type: 'learn' };
  else if (taught && masteryLevel === 'developing') action = { label: '巩固练习', type: 'practice' };
  else if (taught && masteryLevel === 'mastered') action = { label: '复习', type: 'review' };

  const anomaly = !taught && hasEvidence;

  return { taught, hasEvidence, masteryLevel, action, anomaly };
}

function handleAction(ch: Chapter) {
  const status = getChapterStatus(ch);
  if (!status.action) return;
  const map: Record<string, string> = {
    test: `测一下${ch.name}掌握得怎么样`,
    learn: `给我讲一下${ch.name}`,
    practice: `给我出几道${ch.name}的练习题`,
    review: `复习一下${ch.name}`,
  };
  emit('startAction', map[status.action.type] || ch.name);
}

// 顶部统计
const stats = computed(() => {
  let taught = 0, total = 0, mastered = 0, noEvidence = 0;
  for (const unit of textbookData.units) {
    for (const ch of unit.chapters) {
      total++;
      if (taughtChapterIds.has(ch.id)) taught++;
      if ((evidenceCount[ch.id] || 0) > 0 && ch.mastery >= 80) mastered++;
      if (taughtChapterIds.has(ch.id) && (evidenceCount[ch.id] || 0) === 0) noEvidence++;
    }
  }
  return { total, taught, mastered, noEvidence };
});

function masteryColor(v: number): string {
  if (v >= 80) return '#2d8a5e';
  if (v >= 60) return '#c9942a';
  return '#b85c3c';
}
</script>

<template>
  <div class="textbook-page">
    <!-- 顶部 -->
    <div class="page-header">
      <div>
        <h2>教材</h2>
        <span class="header-sub">北师大版 · 六年级下册 · 数学</span>
      </div>
      <div class="header-stats">
        <div class="hs-card"><span class="hs-value">{{ stats.taught }}/{{ stats.total }}</span><span class="hs-label">已学章节</span></div>
        <div class="hs-card"><span class="hs-value" style="color:#2d8a5e">{{ stats.mastered }}</span><span class="hs-label">已掌握</span></div>
        <div class="hs-card"><span class="hs-value" style="color:#c9942a">{{ stats.noEvidence }}</span><span class="hs-label">待自测</span></div>
      </div>
    </div>

    <!-- 图例 -->
    <div class="legend">
      <span class="legend-item"><span class="lg-dot" style="background:#2d8a5e"></span>已掌握</span>
      <span class="legend-item"><span class="lg-dot" style="background:#c9942a"></span>发展中</span>
      <span class="legend-item"><span class="lg-dot" style="background:#b85c3c"></span>需加强</span>
      <span class="legend-item"><span class="lg-dot" style="background:#a0aab8"></span>无证据</span>
      <span class="legend-item"><span class="lg-tag taught">校</span>学校已教</span>
    </div>

    <!-- 章节列表 -->
    <div class="unit-list">
      <div v-for="unit in textbookData.units" :key="unit.id" class="unit-block">
        <div class="unit-header" @click="toggleUnit(unit.id)">
          <span class="unit-toggle">{{ expandedUnits.has(unit.id) ? '▼' : '▶' }}</span>
          <span class="unit-name">{{ unit.name }}</span>
          <span class="unit-count">{{ unit.chapters.length }}节</span>
        </div>

        <div v-if="expandedUnits.has(unit.id)" class="chapter-list">
          <div v-for="ch in unit.chapters" :key="ch.id" class="chapter-row">
            <!-- 左侧：章节信息 -->
            <div class="ch-info">
              <div class="ch-title-row">
                <span class="ch-name">{{ ch.name }}</span>
                <span v-if="getChapterStatus(ch).taught" class="ch-tag taught">学校已学</span>
                <span v-else class="ch-tag not-taught">未学</span>
                <span v-if="getChapterStatus(ch).anomaly" class="ch-anomaly">⚠️ 是不是忘记更新课堂进展了？</span>
              </div>
              <span class="ch-desc">{{ ch.description }}</span>
              <div class="ch-meta">
                <span class="ch-evidence">📊 {{ getChapterStatus(ch).hasEvidence ? (evidenceCount[ch.id] || 0) + '条证据' : '暂无证据' }}</span>
                <span v-if="ch.topics.length > 0" class="ch-topics">
                  薄弱点：
                  <span v-for="t in ch.topics.filter(t => t.mastery < 60).slice(0,2)" :key="t.name" class="ch-weak-tag">{{ t.name }}</span>
                  <span v-if="ch.topics.filter(t => t.mastery < 60).length === 0" style="color:#8a99a8">无</span>
                </span>
              </div>
            </div>

            <!-- 右侧：掌握度 + 行动按钮 -->
            <div class="ch-right">
              <div class="ch-mastery">
                <span class="cm-value" :style="{color: getChapterStatus(ch).hasEvidence ? masteryColor(ch.mastery) : '#a0aab8'}">
                  {{ getChapterStatus(ch).hasEvidence ? ch.mastery + '%' : '—' }}
                </span>
                <div class="cm-bar">
                  <div v-if="getChapterStatus(ch).hasEvidence" class="cm-fill" :style="{width: ch.mastery + '%', background: masteryColor(ch.mastery)}"></div>
                </div>
              </div>
              <button v-if="getChapterStatus(ch).action"
                class="ch-action" :class="getChapterStatus(ch).action?.type"
                @click="handleAction(ch)">
                {{ getChapterStatus(ch).action?.label }}
              </button>
              <span v-else class="ch-no-action">—</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

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
</style>
