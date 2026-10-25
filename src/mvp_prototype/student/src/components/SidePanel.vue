<script setup lang="ts">
import { ref, computed } from 'vue';
import RadarChart from './RadarChart.vue';
import TrendChart from './TrendChart.vue';
import { learningOverview, textbookData, wrongQuestions, errorCategories } from '../data';
import type { Chapter } from '../types';

const emit = defineEmits<{
  selectChapter: [chapterId: string, chapterName: string];
  selectTopic: [topicName: string];
  retryQuestion: [questionId: number];
}>();

type TabType = 'overview' | 'textbook' | 'wrong';
const activeTab = ref<TabType>('overview');
const expandedUnits = ref<Set<string>>(new Set(['unit4']));
const selectedChapter = ref<Chapter | null>(null);
const errorFilter = ref<string>('all');

function toggleUnit(unitId: string) {
  if (expandedUnits.value.has(unitId)) expandedUnits.value.delete(unitId);
  else expandedUnits.value.add(unitId);
}

function selectChapter(chapter: Chapter) {
  selectedChapter.value = chapter;
  emit('selectChapter', chapter.id, chapter.name);
}

function statusColor(mastery: number): string {
  if (mastery >= 80) return '#2d8a5e';
  if (mastery >= 60) return '#c9942a';
  if (mastery > 0) return '#b85c3c';
  return '#9aaab8';
}

const filteredWrongQuestions = computed(() => {
  if (errorFilter.value === 'all') return wrongQuestions;
  return wrongQuestions.filter(q => q.errorType === errorFilter.value);
});

const masteredCount = computed(() => wrongQuestions.filter(q => q.mastered).length);
</script>

<template>
  <aside class="side-panel">
    <!-- 标签页 -->
    <div class="tabs">
      <button class="tab" :class="{ active: activeTab === 'overview' }" @click="activeTab = 'overview'">📊 学习总览</button>
      <button class="tab" :class="{ active: activeTab === 'textbook' }" @click="activeTab = 'textbook'">📚 教材</button>
      <button class="tab" :class="{ active: activeTab === 'wrong' }" @click="activeTab = 'wrong'">📝 错题本</button>
    </div>

    <div class="panel-content">
      <!-- ========== 学习总览 ========== -->
      <div v-if="activeTab === 'overview'" class="tab-content">
        <!-- 当前目标评估 -->
        <div class="card mastery-card">
          <div class="card-header">
            <h3>当前目标评估</h3>
            <span class="chapter-tag">{{ learningOverview.targetAssessment.targetName }}</span>
          </div>
          <div class="mastery-display">
            <span class="mastery-number" :style="{ color: statusColor(70) }">{{ learningOverview.targetAssessment.overallStatus === 'mastered' ? '已达标' : learningOverview.targetAssessment.overallStatus === 'developing' ? '发展中' : learningOverview.targetAssessment.overallStatus === 'conflict' ? '冲突' : '证据不足' }}</span>
          </div>
          <div class="ta-evidence-mini">
            <span>{{ learningOverview.targetAssessment.evidence.positive }} 正向</span>
            <span>·</span>
            <span>{{ learningOverview.targetAssessment.evidence.negative }} 反向</span>
            <span>·</span>
            <span>{{ learningOverview.targetAssessment.evidence.pending }} 待取证</span>
          </div>
          <TrendChart :data="learningOverview.trend" :width="300" :height="100" />
          <p class="trend-caption">最近 7 天学习活动趋势</p>
        </div>

        <!-- 能力雷达图 -->
        <div class="card">
          <h3>能力结构</h3>
          <RadarChart :abilities="learningOverview.abilities" :size="220" />
        </div>

        <!-- 薄弱点聚焦 -->
        <div class="card">
          <h3>薄弱点聚焦</h3>
          <div v-for="wp in learningOverview.weakPoints" :key="wp.name" class="weak-point" @click="emit('selectTopic', wp.name)">
            <div class="wp-header">
              <span class="wp-name">{{ wp.name }}</span>
              <span class="wp-mastery" :style="{ color: statusColor(wp.mastery) }">{{ wp.mastery }}%</span>
            </div>
            <p class="wp-reason">{{ wp.reason }}</p>
            <p class="wp-suggestion">💡 {{ wp.suggestion }}</p>
          </div>
        </div>

        <!-- 学习节奏 -->
        <div class="card">
          <h3>本周学习节奏</h3>
          <div class="rhythm-grid">
            <div class="rhythm-item">
              <span class="rhythm-value">{{ learningOverview.rhythm.weekMinutes }}</span>
              <span class="rhythm-label">学习分钟</span>
            </div>
            <div class="rhythm-item">
              <span class="rhythm-value">{{ learningOverview.rhythm.exercisesDone }}</span>
              <span class="rhythm-label">完成练习</span>
            </div>
            <div class="rhythm-item">
              <span class="rhythm-value">{{ learningOverview.rhythm.correctRate }}%</span>
              <span class="rhythm-label">正确率</span>
            </div>
            <div class="rhythm-item">
              <span class="rhythm-value">{{ learningOverview.rhythm.streak }}</span>
              <span class="rhythm-label">连续天数</span>
            </div>
          </div>
        </div>

        <!-- 下一步建议 -->
        <div class="card suggestion-card">
          <h3>建议下一步</h3>
          <div v-for="(s, i) in learningOverview.suggestions" :key="i" class="next-suggestion" :class="{ high: s.priority === 'high' }">
            <span class="priority-tag" :class="s.priority">{{ s.priority === 'high' ? '优先' : '可选' }}</span>
            <p class="s-action">{{ s.action }}</p>
            <p class="s-reason">{{ s.reason }}</p>
          </div>
        </div>
      </div>

      <!-- ========== 教材目录 ========== -->
      <div v-else-if="activeTab === 'textbook'" class="tab-content">
        <div class="textbook-header">
          <span class="grade">{{ textbookData.grade }}</span>
          <span class="subject">{{ textbookData.subject }}</span>
        </div>

        <!-- 章节详情 -->
        <div v-if="selectedChapter" class="chapter-detail">
          <div class="detail-header">
            <h4>{{ selectedChapter.name }}</h4>
            <button class="close-detail" @click="selectedChapter = null">×</button>
          </div>
          <p class="detail-desc">{{ selectedChapter.description }}</p>
          <div class="detail-mastery">
            <span>掌握度</span>
            <div class="detail-bar"><div class="detail-fill" :style="{ width: selectedChapter.mastery + '%', background: statusColor(selectedChapter.mastery) }"></div></div>
            <span :style="{ color: statusColor(selectedChapter.mastery) }">{{ selectedChapter.mastery }}%</span>
          </div>
          <div v-if="selectedChapter.prerequisites.length > 0" class="detail-prereq">
            <span class="prereq-label">前置知识：</span>
            <span class="prereq-text">{{ selectedChapter.prerequisites.join('、') }}</span>
          </div>
          <div v-if="selectedChapter.topics.length > 0" class="detail-topics">
            <h5>知识点明细</h5>
            <div v-for="t in selectedChapter.topics" :key="t.name" class="detail-topic" @click="emit('selectTopic', t.name)">
              <span class="dt-name">{{ t.name }}</span>
              <span class="dt-status" :style="{ color: statusColor(t.mastery) }">{{ t.status }}</span>
              <span class="dt-percent">{{ t.mastery }}%</span>
            </div>
          </div>
          <button class="detail-action" @click="emit('selectChapter', selectedChapter.id, selectedChapter.name)">
            🎯 开始学习这一章
          </button>
        </div>

        <!-- 单元列表 -->
        <div v-for="unit in textbookData.units" :key="unit.id" class="unit-block">
          <div class="unit-header" @click="toggleUnit(unit.id)">
            <span class="unit-toggle">{{ expandedUnits.has(unit.id) ? '▼' : '▶' }}</span>
            <span class="unit-name">{{ unit.name }}</span>
            <span class="unit-count">{{ unit.chapters.length }}章</span>
          </div>
          <div v-if="expandedUnits.has(unit.id)" class="chapter-list">
            <div v-for="chapter in unit.chapters" :key="chapter.id"
              class="chapter-item"
              :class="{ current: chapter.id === textbookData.currentChapterId, selected: selectedChapter?.id === chapter.id }"
              @click="selectChapter(chapter)">
              <div class="chapter-left">
                <span class="chapter-name">{{ chapter.name }}</span>
                <span v-if="chapter.id === textbookData.currentChapterId" class="current-badge">当前</span>
              </div>
              <div class="chapter-right">
                <div class="chapter-mini-bar">
                  <div class="chapter-mini-fill" :style="{ width: chapter.mastery + '%', background: statusColor(chapter.mastery) }"></div>
                </div>
                <span class="chapter-status" :style="{ color: statusColor(chapter.mastery) }">{{ chapter.status }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- ========== 错题本 ========== -->
      <div v-else-if="activeTab === 'wrong'" class="tab-content">
        <!-- 统计概览 -->
        <div class="card">
          <div class="wrong-stats">
            <div class="ws-item">
              <span class="ws-number">{{ wrongQuestions.length }}</span>
              <span class="ws-label">总错题</span>
            </div>
            <div class="ws-item">
              <span class="ws-number">{{ masteredCount }}</span>
              <span class="ws-label">已掌握</span>
            </div>
            <div class="ws-item">
              <span class="ws-number">{{ wrongQuestions.length - masteredCount }}</span>
              <span class="ws-label">待攻克</span>
            </div>
          </div>
          <!-- 错误类型分布 -->
          <div class="error-distribution">
            <div v-for="cat in errorCategories" :key="cat.type" class="error-bar-row">
              <span class="error-type-label">{{ cat.type }}</span>
              <div class="error-bar-track">
                <div class="error-bar-fill" :style="{ width: (cat.count / wrongQuestions.length * 100) + '%', background: cat.color }"></div>
              </div>
              <span class="error-count">{{ cat.count }}</span>
            </div>
          </div>
        </div>

        <!-- 筛选 -->
        <div class="filter-row">
          <button class="filter-btn" :class="{ active: errorFilter === 'all' }" @click="errorFilter = 'all'">全部</button>
          <button v-for="cat in errorCategories" :key="cat.type" class="filter-btn" :class="{ active: errorFilter === cat.type }" @click="errorFilter = cat.type">{{ cat.type }}</button>
        </div>

        <!-- 错题列表 -->
        <div v-for="q in filteredWrongQuestions" :key="q.id" class="wrong-card" :class="{ mastered: q.mastered }">
          <div class="wrong-meta">
            <span class="wrong-topic">{{ q.topic }}</span>
            <span class="wrong-type" :style="{ background: errorCategories.find(c => c.type === q.errorType)?.color }">{{ q.errorType }}</span>
            <span class="wrong-date">{{ q.date }}</span>
          </div>
          <p class="wrong-text">{{ q.text }}</p>
          <div class="wrong-related">
            <span class="related-label">相关知识点：</span>
            <span v-for="k in q.relatedKnowledge" :key="k" class="related-tag" @click="emit('selectTopic', k)">{{ k }}</span>
          </div>
          <div class="wrong-footer">
            <span class="retry-count">已重做 {{ q.retryCount }} 次</span>
            <span v-if="q.mastered" class="mastered-badge">✓ 已掌握</span>
            <button v-else class="retry-btn" @click="emit('retryQuestion', q.id)">再做一次</button>
          </div>
        </div>

        <div v-if="filteredWrongQuestions.length === 0" class="empty-state">
          <span class="empty-icon">🎉</span>
          <p>该类型暂无错题</p>
        </div>
      </div>
    </div>
  </aside>
</template>

<style scoped>
.side-panel { width: 380px; min-width: 380px; background: #fff; border-left: 1px solid #e1e8ed; display: flex; flex-direction: column; height: 100%; overflow: hidden; }
.tabs { display: flex; border-bottom: 1px solid #e1e8ed; background: #f7f9fa; flex-shrink: 0; }
.tab { flex: 1; padding: 12px 6px; border: none; background: transparent; font-size: 12px; color: #6a7a8a; cursor: pointer; font-family: inherit; border-bottom: 2px solid transparent; transition: all 0.15s; }
.tab:hover { color: #2c3e50; background: #eef2f5; }
.tab.active { color: #1b4332; font-weight: 600; border-bottom-color: #2d6a4f; background: #fff; }
.panel-content { flex: 1; overflow-y: auto; }
.tab-content { padding: 16px; }

/* 通用卡片 */
.card { background: #fafbfc; border: 1px solid #e8edf0; border-radius: 10px; padding: 16px; margin-bottom: 16px; }
.card h3 { margin: 0 0 12px 0; font-size: 14px; color: #1a3a2e; font-weight: 600; }
.card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.card-header h3 { margin: 0; }
.chapter-tag { font-size: 11px; color: #5a7a6a; background: #e0f0e8; padding: 2px 8px; border-radius: 4px; }

/* 掌握度卡片 */
.mastery-display { text-align: center; margin-bottom: 8px; }
.mastery-number { font-size: 32px; font-weight: 700; line-height: 1.2; }
.ta-evidence-mini { text-align: center; font-size: 11px; color: #6a7a8a; margin-bottom: 10px; display: flex; justify-content: center; gap: 6px; }
.trend-caption { text-align: center; font-size: 11px; color: #8a99a8; margin: 4px 0 0 0; }

/* 薄弱点 */
.weak-point { background: #fff; border-radius: 8px; padding: 12px; margin-bottom: 10px; cursor: pointer; border: 1px solid #f0e8e0; transition: border-color 0.15s; }
.weak-point:hover { border-color: #d4a06a; }
.weak-point:last-child { margin-bottom: 0; }
.wp-header { display: flex; justify-content: space-between; margin-bottom: 6px; }
.wp-name { font-size: 13px; font-weight: 600; color: #2c3e50; }
.wp-mastery { font-size: 13px; font-weight: 700; }
.wp-reason { font-size: 12px; color: #6a5a4a; margin: 0 0 6px 0; line-height: 1.5; }
.wp-suggestion { font-size: 12px; color: #2d6a4f; margin: 0; line-height: 1.5; }

/* 学习节奏 */
.rhythm-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.rhythm-item { text-align: center; padding: 10px; background: #fff; border-radius: 8px; }
.rhythm-value { display: block; font-size: 24px; font-weight: 700; color: #2d6a4f; }
.rhythm-label { font-size: 11px; color: #8a99a8; }

/* 下一步建议 */
.suggestion-card { background: linear-gradient(135deg, #f0f7f3 0%, #e8f5ee 100%); border-color: #c8e6d4; }
.next-suggestion { background: #fff; border-radius: 8px; padding: 12px; margin-bottom: 10px; position: relative; }
.next-suggestion:last-child { margin-bottom: 0; }
.next-suggestion.high { border-left: 3px solid #d4726a; }
.priority-tag { display: inline-block; font-size: 10px; padding: 2px 8px; border-radius: 4px; font-weight: 600; margin-bottom: 6px; }
.priority-tag.high { background: #fde8e8; color: #b84a4a; }
.priority-tag.medium { background: #fef5e0; color: #9a7a2a; }
.s-action { font-size: 13px; font-weight: 600; color: #2c3e50; margin: 0 0 4px 0; }
.s-reason { font-size: 12px; color: #6a7a8a; margin: 0; line-height: 1.5; }

/* 教材目录 */
.textbook-header { display: flex; justify-content: space-between; margin-bottom: 16px; padding-bottom: 12px; border-bottom: 1px solid #e1e8ed; }
.grade { font-size: 14px; font-weight: 600; color: #1a3a2e; }
.subject { font-size: 12px; color: #6a7a8a; }

/* 章节详情 */
.chapter-detail { background: #f0f7f3; border-radius: 10px; padding: 14px; margin-bottom: 16px; border: 1px solid #c8e6d4; }
.detail-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.detail-header h4 { margin: 0; font-size: 14px; color: #1b4332; }
.close-detail { background: none; border: none; font-size: 18px; cursor: pointer; color: #6a8a7a; padding: 0 4px; }
.detail-desc { font-size: 12px; color: #4a6a5a; margin: 0 0 10px 0; line-height: 1.6; }
.detail-mastery { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; font-size: 12px; color: #5a7a6a; }
.detail-bar { flex: 1; height: 6px; background: #d4e8dc; border-radius: 3px; overflow: hidden; }
.detail-fill { height: 100%; border-radius: 3px; }
.detail-prereq { font-size: 11px; margin-bottom: 10px; }
.prereq-label { color: #8a99a8; }
.prereq-text { color: #5a7a6a; }
.detail-topics h5 { font-size: 12px; color: #1b4332; margin: 0 0 8px 0; }
.detail-topic { display: flex; align-items: center; gap: 8px; padding: 6px 8px; background: #fff; border-radius: 6px; margin-bottom: 4px; cursor: pointer; font-size: 12px; }
.detail-topic:hover { background: #e8f5ee; }
.dt-name { flex: 1; color: #2c3e50; }
.dt-status { font-size: 11px; font-weight: 500; }
.dt-percent { color: #8a99a8; width: 30px; text-align: right; }
.detail-action { width: 100%; margin-top: 10px; background: #2d6a4f; color: white; border: none; padding: 10px; border-radius: 8px; font-size: 13px; cursor: pointer; font-weight: 500; font-family: inherit; }
.detail-action:hover { background: #245440; }

/* 单元列表 */
.unit-block { margin-bottom: 4px; }
.unit-header { display: flex; align-items: center; gap: 6px; padding: 10px 8px; cursor: pointer; border-radius: 6px; transition: background 0.15s; }
.unit-header:hover { background: #f0f4f7; }
.unit-toggle { font-size: 10px; color: #8a99a8; width: 12px; }
.unit-name { font-size: 13px; font-weight: 600; color: #2c3e50; flex: 1; }
.unit-count { font-size: 11px; color: #8a99a8; }
.chapter-list { margin-left: 18px; border-left: 2px solid #e8edf0; padding-left: 8px; }
.chapter-item { display: flex; justify-content: space-between; align-items: center; padding: 8px; border-radius: 6px; cursor: pointer; transition: background 0.15s; }
.chapter-item:hover { background: #f0f4f7; }
.chapter-item.current { background: #e8f5ee; border-left: 3px solid #2d6a4f; padding-left: 5px; }
.chapter-item.selected { background: #d4edda; }
.chapter-left { display: flex; align-items: center; gap: 6px; min-width: 0; }
.chapter-name { font-size: 12px; color: #3a4a5a; }
.chapter-item.current .chapter-name { color: #1b4332; font-weight: 600; }
.current-badge { font-size: 9px; background: #2d6a4f; color: white; padding: 1px 5px; border-radius: 3px; }
.chapter-right { display: flex; align-items: center; gap: 6px; flex-shrink: 0; }
.chapter-mini-bar { width: 40px; height: 4px; background: #e8edf0; border-radius: 2px; overflow: hidden; }
.chapter-mini-fill { height: 100%; border-radius: 2px; }
.chapter-status { font-size: 10px; font-weight: 500; width: 36px; text-align: right; }

/* 错题本 */
.wrong-stats { display: flex; justify-content: space-around; margin-bottom: 16px; }
.ws-item { text-align: center; }
.ws-number { display: block; font-size: 28px; font-weight: 700; color: #2d6a4f; }
.ws-label { font-size: 11px; color: #8a99a8; }
.error-distribution { margin-top: 12px; }
.error-bar-row { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; font-size: 11px; }
.error-type-label { width: 56px; color: #5a6b7a; flex-shrink: 0; }
.error-bar-track { flex: 1; height: 8px; background: #eef2f5; border-radius: 4px; overflow: hidden; }
.error-bar-fill { height: 100%; border-radius: 4px; }
.error-count { width: 16px; text-align: right; color: #5a6b7a; font-weight: 600; }

.filter-row { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 14px; }
.filter-btn { background: #f0f4f7; border: 1px solid #d4dde4; color: #5a6b7a; padding: 4px 10px; border-radius: 12px; font-size: 11px; cursor: pointer; font-family: inherit; transition: all 0.15s; }
.filter-btn:hover { background: #e0f0e8; border-color: #40916c; color: #1b4332; }
.filter-btn.active { background: #2d6a4f; color: white; border-color: #2d6a4f; }

.wrong-card { background: #fff; border: 1px solid #f0e0d0; border-radius: 10px; padding: 14px; margin-bottom: 12px; }
.wrong-card.mastered { border-color: #d4e8dc; opacity: 0.75; }
.wrong-meta { display: flex; align-items: center; gap: 6px; margin-bottom: 8px; flex-wrap: wrap; }
.wrong-topic { font-size: 10px; background: #f5e0d0; color: #8a5a2a; padding: 2px 8px; border-radius: 4px; font-weight: 500; }
.wrong-type { font-size: 10px; color: white; padding: 2px 8px; border-radius: 4px; font-weight: 500; }
.wrong-date { font-size: 10px; color: #9a8a7a; margin-left: auto; }
.wrong-text { font-size: 13px; color: #2c3e50; line-height: 1.6; margin: 0 0 10px 0; }
.wrong-related { margin-bottom: 10px; font-size: 11px; }
.related-label { color: #8a99a8; }
.related-tag { display: inline-block; background: #e8f0f8; color: #3a5a7a; padding: 1px 6px; border-radius: 4px; margin-right: 4px; cursor: pointer; }
.related-tag:hover { background: #d0e0f0; }
.wrong-footer { display: flex; align-items: center; gap: 10px; }
.retry-count { font-size: 11px; color: #8a99a8; }
.mastered-badge { font-size: 11px; color: #2d8a5e; font-weight: 600; }
.retry-btn { margin-left: auto; background: #2d6a4f; color: white; border: none; padding: 5px 14px; border-radius: 6px; font-size: 12px; cursor: pointer; font-family: inherit; }
.retry-btn:hover { background: #245440; }

.empty-state { text-align: center; padding: 40px 20px; color: #8a99a8; }
.empty-icon { font-size: 36px; display: block; margin-bottom: 12px; }

@media (max-width: 1100px) {
  .side-panel { width: 340px; min-width: 340px; }
}
</style>
