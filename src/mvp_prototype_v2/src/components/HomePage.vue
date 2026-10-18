<script setup lang="ts">
import { computed } from 'vue';
import { learningOverview, textbookData } from '../data';

const emit = defineEmits<{
  continueLearning: [];
  startAction: [text: string];
}>();

const stats = computed(() => [
  { label: '今日学习', value: '32分钟', icon: '⏱️' },
  { label: '本周学习', value: '145分钟', icon: '📅' },
  { label: '错题存量', value: '6道', icon: '📝' },
  { label: '连续学习', value: '5天', icon: '🔥' },
  { label: '综合掌握', value: learningOverview.mastery + '%', icon: '📊' },
]);

const currentChapter = computed(() => {
  for (const unit of textbookData.units) {
    const ch = unit.chapters.find(c => c.id === textbookData.currentChapterId);
    if (ch) return ch;
  }
  return null;
});
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

    <!-- 主要行动区 -->
    <div class="action-zone">
      <div class="primary-action" @click="emit('continueLearning')">
        <div class="pa-icon">▶️</div>
        <div class="pa-content">
          <span class="pa-tag">继续学习</span>
          <span class="pa-title">比例的应用</span>
          <span class="pa-desc">上次停在第2段 · 比较标准量</span>
        </div>
        <span class="pa-arrow">→</span>
      </div>

      <div class="secondary-actions">
        <div class="sa-card" @click="emit('startAction', '复习分数加法')">
          <span class="sa-icon">🔄</span>
          <div>
            <span class="sa-title">系统推荐：复习分数加法</span>
            <span class="sa-desc">3天未接触，建议巩固</span>
          </div>
        </div>
        <div class="sa-card" @click="emit('startAction', '测一下比例的应用掌握得怎么样')">
          <span class="sa-icon">📋</span>
          <div>
            <span class="sa-title">邀请检测：比例的应用</span>
            <span class="sa-desc">已学过但证据不足，建议自测</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 状态概览 -->
    <div class="stats-grid">
      <div v-for="s in stats" :key="s.label" class="stat-card">
        <span class="stat-icon">{{ s.icon }}</span>
        <span class="stat-value">{{ s.value }}</span>
        <span class="stat-label">{{ s.label }}</span>
      </div>
    </div>

    <!-- 学习足迹 -->
    <div class="section">
      <h3>近7天学习足迹</h3>
      <div class="trend-bars">
        <div v-for="p in learningOverview.trend" :key="p.date" class="trend-col">
          <div class="trend-bar-wrap">
            <div class="trend-bar" :style="{ height: p.mastery + '%' }"></div>
          </div>
          <span class="trend-value">{{ p.mastery }}</span>
          <span class="trend-date">{{ p.date }}</span>
        </div>
      </div>
    </div>

    <!-- 薄弱点提示 -->
    <div class="section" v-if="learningOverview.weakPoints.length > 0">
      <h3>需要关注</h3>
      <div class="weak-list">
        <div v-for="w in learningOverview.weakPoints" :key="w.name" class="weak-item">
          <div class="weak-info">
            <span class="weak-name">{{ w.name }}</span>
            <span class="weak-reason">{{ w.reason }}</span>
          </div>
          <span class="weak-mastery">{{ w.mastery }}%</span>
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

.action-zone { margin-bottom: 20px; }
.primary-action {
  display: flex; align-items: center; gap: 16px;
  background: linear-gradient(135deg, #1b4332, #2d6a4f);
  color: white; padding: 20px 24px; border-radius: 12px;
  cursor: pointer; transition: transform 0.2s; margin-bottom: 12px;
}
.primary-action:hover { transform: translateY(-2px); }
.pa-icon { font-size: 28px; }
.pa-content { flex: 1; display: flex; flex-direction: column; gap: 2px; }
.pa-tag { font-size: 11px; opacity: 0.8; }
.pa-title { font-size: 18px; font-weight: 700; }
.pa-desc { font-size: 12px; opacity: 0.7; }
.pa-arrow { font-size: 20px; opacity: 0.8; }

.secondary-actions { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.sa-card {
  display: flex; align-items: center; gap: 12px;
  background: white; border: 1px solid #e1e8ed; border-radius: 10px;
  padding: 14px 16px; cursor: pointer; transition: all 0.2s;
}
.sa-card:hover { border-color: #2d6a4f; box-shadow: 0 2px 8px rgba(45,106,79,0.1); }
.sa-icon { font-size: 20px; }
.sa-card > div { display: flex; flex-direction: column; gap: 2px; }
.sa-title { font-size: 13px; font-weight: 600; color: #2c3e50; }
.sa-desc { font-size: 11px; color: #8a99a8; }

.stats-grid {
  display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; margin-bottom: 20px;
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
