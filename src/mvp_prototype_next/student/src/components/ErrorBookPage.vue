<script setup lang="ts">
import { ref, computed } from 'vue';
import { wrongQuestions } from '../data';
import type { WrongQuestion } from '../types';

const emit = defineEmits<{
  startAction: [text: string];
}>();

// 筛选
const filterType = ref('all');
const filterSource = ref('all');
const filterStatus = ref('all');

// 扩展错题数据：添加来源、掌握状态、证据历史
interface ExtendedError extends WrongQuestion {
  source: 'practice' | 'test' | 'upload';
  masteryStatus: 'pending' | 'explained' | 'corrected' | 'mastered' | 'repeated';
  evidenceHistory: { date: string; action: string; result: string }[];
}

const extendedErrors: ExtendedError[] = [
  { ...wrongQuestions[0], source: 'practice', masteryStatus: 'explained',
    evidenceHistory: [
      { date: '10-15', action: '练习答错', result: '标准量搞反' },
      { date: '10-16', action: 'DeerMind讲解', result: '已讲解比较标准量' },
    ]},
  { ...wrongQuestions[1], source: 'test', masteryStatus: 'pending',
    evidenceHistory: [
      { date: '10-16', action: '自测答错', result: '先涨后降标准量混淆' },
    ]},
  { ...wrongQuestions[2], source: 'practice', masteryStatus: 'mastered',
    evidenceHistory: [
      { date: '10-14', action: '练习答错', result: '计算错误' },
      { date: '10-15', action: '订正正确', result: '重做正确' },
      { date: '10-17', action: '迁移检测', result: '同类题正确' },
    ]},
  { ...wrongQuestions[3], source: 'upload', masteryStatus: 'corrected',
    evidenceHistory: [
      { date: '10-13', action: '上传错题', result: '审题错误' },
      { date: '10-14', action: '订正正确', result: '重做正确' },
    ]},
  { ...wrongQuestions[4], source: 'test', masteryStatus: 'repeated',
    evidenceHistory: [
      { date: '10-12', action: '自测答错', result: '公式记错' },
      { date: '10-14', action: '练习答错', result: '再次出错' },
      { date: '10-16', action: 'DeerMind讲解', result: '已讲解体积公式' },
    ]},
  { ...wrongQuestions[5], source: 'practice', masteryStatus: 'pending',
    evidenceHistory: [
      { date: '10-16', action: '练习答错', result: '计算错误' },
    ]},
];

const sourceLabels: Record<string, string> = { practice: '练习', test: '自测', upload: '上传' };
const sourceColors: Record<string, string> = { practice: '#4a6fa5', test: '#c9942a', upload: '#8a7ad4' };
const statusLabels: Record<string, string> = {
  pending: '待处理', explained: '已讲解', corrected: '订正正确', mastered: '已掌握', repeated: '反复错',
};
const statusColors: Record<string, string> = {
  pending: '#b85c3c', explained: '#c9942a', corrected: '#4a90d9', mastered: '#2d8a5e', repeated: '#d44a4a',
};

const filteredErrors = computed(() => {
  return extendedErrors.filter(e => {
    if (filterType.value !== 'all' && e.errorType !== filterType.value) return false;
    if (filterSource.value !== 'all' && e.source !== filterSource.value) return false;
    if (filterStatus.value !== 'all' && e.masteryStatus !== filterStatus.value) return false;
    return true;
  });
});

// 统计
const stats = computed(() => ({
  total: extendedErrors.length,
  pending: extendedErrors.filter(e => e.masteryStatus === 'pending' || e.masteryStatus === 'explained').length,
  mastered: extendedErrors.filter(e => e.masteryStatus === 'mastered').length,
  repeated: extendedErrors.filter(e => e.masteryStatus === 'repeated').length,
}));

const errorTypes = ['概念误解', '计算错误', '审题错误', '方法不会'];

function handleDetect(err: ExtendedError) {
  emit('startAction', `针对错题"${err.topic}"进行检测，包括原题重做和迁移能力检测`);
}

const expandedId = ref<number | null>(null);
function toggleExpand(id: number) {
  expandedId.value = expandedId.value === id ? null : id;
}
</script>

<template>
  <div class="error-book-page">
    <!-- 顶部 -->
    <div class="page-header">
      <div>
        <h2>错题本</h2>
        <span class="header-sub">共 {{ stats.total }} 道错题</span>
      </div>
      <div class="header-stats">
        <div class="hs-card"><span class="hs-value" style="color:#c9942a">{{ stats.pending }}</span><span class="hs-label">待处理</span></div>
        <div class="hs-card"><span class="hs-value" style="color:#2d8a5e">{{ stats.mastered }}</span><span class="hs-label">已掌握</span></div>
        <div class="hs-card"><span class="hs-value" style="color:#d44a4a">{{ stats.repeated }}</span><span class="hs-label">反复错</span></div>
      </div>
    </div>

    <!-- 筛选栏 -->
    <div class="filter-bar">
      <div class="filter-select-group">
        <label class="fs-label">错误类型</label>
        <select class="fs-select" v-model="filterType">
          <option value="all">全部</option>
          <option v-for="t in errorTypes" :key="t" :value="t">{{ t }}</option>
        </select>
      </div>
      <div class="filter-select-group">
        <label class="fs-label">来源</label>
        <select class="fs-select" v-model="filterSource">
          <option value="all">全部</option>
          <option v-for="(label, key) in sourceLabels" :key="key" :value="key">{{ label }}</option>
        </select>
      </div>
      <div class="filter-select-group">
        <label class="fs-label">状态</label>
        <select class="fs-select" v-model="filterStatus">
          <option value="all">全部</option>
          <option v-for="(label, key) in statusLabels" :key="key" :value="key">{{ label }}</option>
        </select>
      </div>
      <span class="filter-result">共 {{ filteredErrors.length }} 道</span>
    </div>

    <!-- 错题列表 -->
    <div class="error-list">
      <div v-for="err in filteredErrors" :key="err.id" class="error-card">
        <div class="ec-header" @click="toggleExpand(err.id)">
          <div class="ec-tags">
            <span class="ec-source" :style="{background: sourceColors[err.source] + '22', color: sourceColors[err.source]}">{{ sourceLabels[err.source] }}</span>
            <span class="ec-type">{{ err.errorType }}</span>
            <span class="ec-status" :style="{background: statusColors[err.masteryStatus] + '22', color: statusColors[err.masteryStatus]}">{{ statusLabels[err.masteryStatus] }}</span>
          </div>
          <span class="ec-date">{{ err.date }}</span>
          <span class="ec-expand">{{ expandedId === err.id ? '▲' : '▼' }}</span>
        </div>

        <div class="ec-body">
          <div class="ec-topic">{{ err.topic }}</div>
          <div class="ec-text">{{ err.text }}</div>
          <div class="ec-knowledge">
            <span>相关知识点：</span>
            <span v-for="k in err.relatedKnowledge" :key="k" class="ec-kc-tag">{{ k }}</span>
          </div>
        </div>

        <div class="ec-footer">
          <span class="ec-retry">重做 {{ err.retryCount }} 次</span>
          <button class="ec-detect-btn" @click.stop="handleDetect(err)">错题检测 →</button>
        </div>

        <!-- 展开：证据历史 -->
        <div v-if="expandedId === err.id" class="ec-history">
          <div class="ech-title">证据历史</div>
          <div class="ech-timeline">
            <div v-for="(h, i) in err.evidenceHistory" :key="i" class="ech-item">
              <span class="ech-date">{{ h.date }}</span>
              <span class="ech-action">{{ h.action }}</span>
              <span class="ech-result">{{ h.result }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-if="filteredErrors.length === 0" class="empty">
      <span>没有符合条件的错题</span>
    </div>
  </div>
</template>

<style scoped>
.error-book-page { padding: 20px 24px; height: 100%; overflow-y: auto; }

.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px; }
.page-header h2 { margin: 0; font-size: 18px; color: #1a3a2e; }
.header-sub { font-size: 12px; color: #8a99a8; }
.header-stats { display: flex; gap: 12px; }
.hs-card {
  background: white; border: 1px solid #e1e8ed; border-radius: 8px;
  padding: 8px 14px; text-align: center; min-width: 60px;
}
.hs-value { display: block; font-size: 16px; font-weight: 700; }
.hs-label { font-size: 10px; color: #8a99a8; }

.filter-bar {
  display: flex; align-items: center; gap: 16px;
  margin-bottom: 16px; padding: 10px 14px;
  background: white; border: 1px solid #e1e8ed; border-radius: 8px;
}
.filter-select-group { display: flex; align-items: center; gap: 6px; }
.fs-label { font-size: 12px; color: #5a6b7a; font-weight: 500; }
.fs-select {
  padding: 5px 10px; border: 1px solid #d0d7de; background: white;
  border-radius: 6px; font-size: 12px; cursor: pointer; font-family: inherit;
  color: #2c3e50; min-width: 90px;
}
.fs-select:focus { outline: none; border-color: #2d6a4f; }
.filter-result { margin-left: auto; font-size: 12px; color: #8a99a8; }

.error-list { display: flex; flex-direction: column; gap: 10px; }
.error-card {
  background: white; border: 1px solid #e1e8ed; border-radius: 10px; overflow: hidden;
}
.ec-header {
  display: flex; align-items: center; gap: 10px; padding: 10px 14px;
  background: #f7f9fa; border-bottom: 1px solid #f0f4f7; cursor: pointer;
}
.ec-tags { display: flex; gap: 6px; flex: 1; }
.ec-source, .ec-type, .ec-status {
  font-size: 10px; padding: 2px 8px; border-radius: 4px; font-weight: 600;
}
.ec-type { background: #f0f4f7; color: #5a6b7a; }
.ec-date { font-size: 11px; color: #8a99a8; }
.ec-expand { font-size: 10px; color: #8a99a8; }

.ec-body { padding: 12px 14px; }
.ec-topic { font-size: 14px; font-weight: 600; color: #2c3e50; margin-bottom: 6px; }
.ec-text { font-size: 13px; color: #3a4a5a; margin-bottom: 8px; line-height: 1.5; }
.ec-knowledge { font-size: 11px; color: #8a99a8; display: flex; align-items: center; gap: 4px; flex-wrap: wrap; }
.ec-kc-tag { background: #f0f4f7; color: #5a6b7a; padding: 1px 6px; border-radius: 3px; font-size: 10px; }

.ec-footer {
  display: flex; justify-content: space-between; align-items: center;
  padding: 8px 14px; border-top: 1px solid #f0f4f7; background: #fafbfc;
}
.ec-retry { font-size: 11px; color: #8a99a8; }
.ec-detect-btn {
  background: #2d6a4f; color: white; border: none; padding: 6px 14px;
  border-radius: 6px; font-size: 12px; font-weight: 600; cursor: pointer; font-family: inherit;
}
.ec-detect-btn:hover { background: #1b4332; }

.ec-history { padding: 12px 14px; border-top: 1px solid #f0f4f7; background: #fafbfc; }
.ech-title { font-size: 12px; font-weight: 600; color: #5a6b7a; margin-bottom: 8px; }
.ech-timeline { display: flex; flex-direction: column; gap: 6px; }
.ech-item { display: flex; gap: 10px; font-size: 12px; }
.ech-date { color: #8a99a8; width: 50px; flex-shrink: 0; }
.ech-action { color: #2c3e50; font-weight: 500; width: 80px; flex-shrink: 0; }
.ech-result { color: #5a6b7a; flex: 1; }

.empty { text-align: center; padding: 40px; color: #8a99a8; font-size: 14px; }
</style>
