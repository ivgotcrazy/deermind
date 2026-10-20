<script setup lang="ts">
import { computed } from 'vue';
import { learningOverview, textbookData } from '../data';
import type { ClaimStatus } from '../types';

const emit = defineEmits<{
  continueLearning: [];
  startAction: [text: string];
}>();

const stats = computed(() => [
  { label: '今日学习', value: '32分钟', icon: '⏱️' },
  { label: '本周学习', value: '145分钟', icon: '📅' },
  { label: '错题存量', value: '6道', icon: '📝' },
  { label: '连续学习', value: '5天', icon: '🔥' },
]);

const currentChapter = computed(() => {
  for (const unit of textbookData.units) {
    const ch = unit.chapters.find(c => c.id === textbookData.currentChapterId);
    if (ch) return ch;
  }
  return null;
});

const statusConfig: Record<ClaimStatus, { label: string; icon: string; color: string; bg: string }> = {
  mastered:     { label: '已达标',   icon: '✓',  color: '#2d6a4f', bg: '#e8f5ee' },
  developing:   { label: '发展中',   icon: '◐',  color: '#c47a2a', bg: '#fdf3e6' },
  insufficient: { label: '证据不足', icon: '?',  color: '#6b7a8a', bg: '#f0f3f6' },
  conflict:     { label: '证据冲突', icon: '⚠',  color: '#b85c3c', bg: '#fdf0eb' },
};

const ta = computed(() => learningOverview.targetAssessment);
const overallConfig = computed(() => statusConfig[ta.value.overallStatus]);
</script>

<template>
  <div class="home-page">
    <!-- 顶部：当前学习空间 + 课堂进度 -->
    <div class="space-header">
      <div class="space-info">
        <span class="space-icon">🔢</span>
        <div>
          <h2>数学 · 北师大版六年级下册</h2>
          <span class="space-sub">当前学习空间</span>
        </div>
      </div>
      <div class="classroom-progress">
        <span class="cp-label">学校正在学</span>
        <span class="cp-chapter">第四单元 · 比例的应用</span>
        <button class="cp-update">更新</button>
      </div>
    </div>

    <!-- 学习统计（第一行） -->
    <div class="stats-card">
      <div class="stats-header">
        <span class="stats-title-icon">📊</span>
        <span class="stats-header-title">学习统计</span>
        <span class="stats-updated">今日</span>
      </div>
      <div class="stats-grid">
        <div v-for="s in stats" :key="s.label" class="stat-card">
          <span class="stat-icon">{{ s.icon }}</span>
          <span class="stat-value">{{ s.value }}</span>
          <span class="stat-label">{{ s.label }}</span>
        </div>
      </div>
    </div>

    <!-- 当前学习目标评估（第二行） -->
    <div class="target-assessment-card">
      <div class="ta-header">
        <span class="ta-title-icon">🎯</span>
        <span class="ta-header-title">当前学习目标评估</span>
        <span class="ta-updated">{{ ta.lastUpdated }} 更新</span>
      </div>

      <div class="ta-main">
        <div class="ta-target-row">
          <span class="ta-target-name">{{ ta.targetName }}</span>
          <span class="ta-status-badge" :style="{ color: overallConfig.color, background: overallConfig.bg }">
            {{ overallConfig.icon }} {{ overallConfig.label }}
          </span>
        </div>
        <div class="ta-meta">基于 {{ ta.claimCount }} 个 Task Claim · Evaluation Space v1.4</div>
      </div>

      <div class="ta-evidence-row">
        <span class="ta-evidence-label">证据基础</span>
        <span class="ta-evidence-positive">{{ ta.evidence.positive }} 正向</span>
        <span class="ta-evidence-divider">·</span>
        <span class="ta-evidence-negative">{{ ta.evidence.negative }} 反向</span>
        <span class="ta-evidence-divider">·</span>
        <span class="ta-evidence-pending">{{ ta.evidence.pending }} 项待取证</span>
        <span v-if="ta.evidence.conflict" class="ta-evidence-conflict">· 存在冲突</span>
      </div>

      <div class="ta-dimensions">
        <div v-for="d in ta.dimensions" :key="d.dimension" class="ta-dim-item">
          <div class="ta-dim-top">
            <span class="ta-dim-icon" :style="{ color: statusConfig[d.status].color, background: statusConfig[d.status].bg }">
              {{ statusConfig[d.status].icon }}
            </span>
            <span class="ta-dim-label">{{ d.label }}</span>
          </div>
          <div class="ta-dim-bottom">
            <span class="ta-dim-status" :style="{ color: statusConfig[d.status].color }">
              {{ statusConfig[d.status].label }}
            </span>
            <span class="ta-dim-evidence">{{ d.evidenceCount }} 条证据</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 待完成任务（第三行） -->
    <div class="task-card">
      <div class="task-header">
        <span class="task-title-icon">📋</span>
        <span class="task-header-title">待完成任务</span>
        <span class="task-count">3 项</span>
      </div>

      <div class="task-list">
        <!-- 继续学习（主要任务） -->
        <div class="task-item task-primary" @click="emit('continueLearning')">
          <div class="task-icon">▶️</div>
          <div class="task-content">
            <div class="task-top">
              <span class="task-tag">继续学习</span>
              <span class="task-priority">优先</span>
            </div>
            <span class="task-title">比例的应用</span>
            <span class="task-desc">上次停在第2段 · 比较标准量</span>
          </div>
          <span class="task-arrow">→</span>
        </div>

        <!-- 系统推荐 -->
        <div class="task-item" @click="emit('startAction', '复习分数加法')">
          <div class="task-icon">🔄</div>
          <div class="task-content">
            <div class="task-top">
              <span class="task-tag">系统推荐</span>
            </div>
            <span class="task-title">复习分数加法</span>
            <span class="task-desc">3天未接触，建议巩固</span>
          </div>
          <span class="task-arrow">→</span>
        </div>

        <!-- 邀请检测 -->
        <div class="task-item" @click="emit('startAction', '测一下比例的应用掌握得怎么样')">
          <div class="task-icon">📝</div>
          <div class="task-content">
            <div class="task-top">
              <span class="task-tag">邀请检测</span>
            </div>
            <span class="task-title">比例的应用自测</span>
            <span class="task-desc">已学过但证据不足，建议自测获取证据</span>
          </div>
          <span class="task-arrow">→</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.home-page { padding: 20px 24px; height: 100%; overflow-y: auto; }

.space-header {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 20px;
}
.space-info { display: flex; align-items: center; gap: 12px; }
.space-icon { font-size: 32px; }
.space-info h2 { margin: 0; font-size: 18px; color: #1a3a2e; }
.space-sub { font-size: 12px; color: #8a99a8; }
.classroom-progress {
  display: flex; align-items: center; gap: 10px;
  background: #f0f7f4; border: 1px solid #c8e0d4;
  padding: 8px 14px; border-radius: 8px;
}
.cp-label { font-size: 12px; color: #5a7a6a; }
.cp-chapter { font-size: 13px; font-weight: 600; color: #1b4332; }
.cp-update {
  background: none; border: 1px solid #2d6a4f; color: #2d6a4f;
  padding: 3px 10px; border-radius: 4px; font-size: 12px; cursor: pointer;
}
.cp-update:hover { background: #2d6a4f; color: white; }

/* ===== 待完成任务卡片 ===== */
.task-card {
  background: white; border: 1px solid #d4e4dc; border-radius: 12px;
  padding: 18px 20px; margin-bottom: 20px;
  box-shadow: 0 1px 4px rgba(45,106,79,0.06);
}
.task-header {
  display: flex; align-items: center; gap: 8px;
  margin-bottom: 14px; padding-bottom: 12px;
  border-bottom: 1px solid #eef3f0;
}
.task-title-icon { font-size: 18px; }
.task-header-title { font-size: 14px; font-weight: 700; color: #1a3a2e; flex: 1; }
.task-count { font-size: 11px; color: #8a99a8; background: #f0f4f2; padding: 2px 8px; border-radius: 10px; }

.task-list { display: flex; flex-direction: column; gap: 10px; }
.task-item {
  display: flex; align-items: center; gap: 14px;
  background: #fafcfb; border: 1px solid #e8ede9; border-radius: 10px;
  padding: 14px 16px; cursor: pointer; transition: all 0.2s;
}
.task-item:hover { border-color: #2d6a4f; background: #f0f7f3; box-shadow: 0 2px 8px rgba(45,106,79,0.08); }
.task-item.task-primary {
  background: linear-gradient(135deg, #f0f7f3, #e8f5ee);
  border-color: #b8d8c4;
}
.task-item.task-primary:hover { background: linear-gradient(135deg, #e8f5ee, #d4edda); }
.task-icon { font-size: 22px; flex-shrink: 0; }
.task-content { flex: 1; display: flex; flex-direction: column; gap: 3px; min-width: 0; }
.task-top { display: flex; align-items: center; gap: 8px; }
.task-tag { font-size: 11px; font-weight: 600; color: #5a7a6a; background: #e0f0e8; padding: 2px 8px; border-radius: 4px; }
.task-priority { font-size: 10px; font-weight: 600; color: #b85c3c; background: #fdf0eb; padding: 2px 6px; border-radius: 4px; }
.task-title { font-size: 15px; font-weight: 700; color: #1a3a2e; }
.task-desc { font-size: 12px; color: #8a99a8; }
.task-arrow { font-size: 18px; color: #8a99a8; flex-shrink: 0; }
.task-item:hover .task-arrow { color: #2d6a4f; }

/* ===== 当前学习目标评估卡片 ===== */
.target-assessment-card {
  background: white; border: 1px solid #d4e4dc; border-radius: 12px;
  padding: 18px 20px; margin-bottom: 20px;
  box-shadow: 0 1px 4px rgba(45,106,79,0.06);
}
.ta-header {
  display: flex; align-items: center; gap: 8px;
  margin-bottom: 14px; padding-bottom: 12px;
  border-bottom: 1px solid #eef3f0;
}
.ta-title-icon { font-size: 18px; }
.ta-header-title { font-size: 14px; font-weight: 700; color: #1a3a2e; flex: 1; }
.ta-updated { font-size: 11px; color: #8a99a8; }

.ta-main { margin-bottom: 12px; }
.ta-target-row {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 4px;
}
.ta-target-name { font-size: 17px; font-weight: 700; color: #1a3a2e; }
.ta-status-badge {
  font-size: 12px; font-weight: 600;
  padding: 3px 10px; border-radius: 12px;
}
.ta-meta { font-size: 11px; color: #8a99a8; }

.ta-evidence-row {
  display: flex; align-items: center; gap: 6px;
  background: #f7faf8; border-radius: 8px;
  padding: 8px 12px; margin-bottom: 14px;
  font-size: 12px;
}
.ta-evidence-label { color: #5a7a6a; font-weight: 600; margin-right: 4px; }
.ta-evidence-positive { color: #2d6a4f; font-weight: 600; }
.ta-evidence-negative { color: #b85c3c; font-weight: 600; }
.ta-evidence-pending { color: #8a6a2a; font-weight: 600; }
.ta-evidence-conflict { color: #c0392b; font-weight: 700; }
.ta-evidence-divider { color: #c0c8d0; }

.ta-dimensions {
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px;
}
.ta-dim-item {
  background: #fafcfb; border: 1px solid #e8ede9; border-radius: 8px;
  padding: 10px 12px;
}
.ta-dim-top {
  display: flex; align-items: center; gap: 6px;
  margin-bottom: 6px;
}
.ta-dim-icon {
  width: 22px; height: 22px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 12px; font-weight: 700;
}
.ta-dim-label { font-size: 12px; font-weight: 600; color: #2c3e50; }
.ta-dim-bottom {
  display: flex; flex-direction: column; gap: 1px;
  padding-left: 28px;
}
.ta-dim-status { font-size: 11px; font-weight: 600; }
.ta-dim-evidence { font-size: 10px; color: #8a99a8; }

/* ===== 学习统计卡片 ===== */
.stats-card {
  background: white; border: 1px solid #d4e4dc; border-radius: 12px;
  padding: 18px 20px; margin-bottom: 20px;
  box-shadow: 0 1px 4px rgba(45,106,79,0.06);
}
.stats-header {
  display: flex; align-items: center; gap: 8px;
  margin-bottom: 14px; padding-bottom: 12px;
  border-bottom: 1px solid #eef3f0;
}
.stats-title-icon { font-size: 18px; }
.stats-header-title { font-size: 14px; font-weight: 700; color: #1a3a2e; flex: 1; }
.stats-updated { font-size: 11px; color: #8a99a8; background: #f0f4f2; padding: 2px 8px; border-radius: 10px; }

.stats-grid {
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px;
}
.stat-card {
  background: white; border: 1px solid #e1e8ed; border-radius: 10px;
  padding: 14px; display: flex; flex-direction: column; align-items: center; gap: 4px;
}
.stat-icon { font-size: 18px; }
.stat-value { font-size: 18px; font-weight: 700; color: #1a3a2e; }
.stat-label { font-size: 11px; color: #8a99a8; }

.section { margin-bottom: 20px; }
.section h3 { margin: 0 0 12px 0; font-size: 14px; color: #1a3a2e; }

.trend-bars {
  display: flex; justify-content: space-around; align-items: flex-end;
  height: 120px; background: white; border: 1px solid #e1e8ed;
  border-radius: 10px; padding: 16px;
}
.trend-col { display: flex; flex-direction: column; align-items: center; gap: 4px; flex: 1; }
.trend-bar-wrap { height: 60px; display: flex; align-items: flex-end; }
.trend-bar { width: 24px; background: linear-gradient(180deg, #52b788, #2d6a4f); border-radius: 4px 4px 0 0; min-height: 4px; }
.trend-value { font-size: 11px; font-weight: 600; color: #2c3e50; }
.trend-date { font-size: 10px; color: #8a99a8; }

.weak-list { display: flex; flex-direction: column; gap: 8px; }
.weak-item {
  display: flex; justify-content: space-between; align-items: center;
  background: #fef5f0; border: 1px solid #f0d0c0; border-radius: 8px;
  padding: 12px 14px;
}
.weak-info { display: flex; flex-direction: column; gap: 2px; }
.weak-name { font-size: 13px; font-weight: 600; color: #8a3a1a; }
.weak-reason { font-size: 11px; color: #a06a5a; }
.weak-mastery { font-size: 16px; font-weight: 700; color: #b85c3c; }

@media (max-width: 900px) {
  .stats-grid { grid-template-columns: repeat(3, 1fr); }
  .secondary-actions { grid-template-columns: 1fr; }
}
</style>
