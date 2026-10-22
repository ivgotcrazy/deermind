<script setup lang="ts">
import { ref, computed } from 'vue';
import { domains, textbooks } from '../data';
import type { Textbook } from '../types';

type ViewMode = 'list' | 'detail';
const viewMode = ref<ViewMode>('list');
const selectedTextbook = ref<Textbook | null>(null);
const activeTab = ref<'domains' | 'textbooks'>('textbooks');
const expandedUnits = ref<Set<string>>(new Set());

function openTextbook(tb: Textbook) {
  selectedTextbook.value = tb;
  viewMode.value = 'detail';
  expandedUnits.value = new Set(tb.units.map(u => u.id));
}

function backToList() {
  viewMode.value = 'list';
  selectedTextbook.value = null;
}

function toggleUnit(unitId: string) {
  if (expandedUnits.value.has(unitId)) {
    expandedUnits.value.delete(unitId);
  } else {
    expandedUnits.value.add(unitId);
  }
}

const statusConfig: Record<string, { label: string; color: string; bg: string }> = {
  active: { label: '已启用', color: '#2d8a5e', bg: '#e8f5ee' },
  draft: { label: '草稿', color: '#8a99a8', bg: '#f0f4f7' },
  archived: { label: '已归档', color: '#b85c3c', bg: '#fdf0ed' },
};

const totalChapters = computed(() => textbooks.reduce((s, t) => s + t.totalChapters, 0));
const totalMappedKc = computed(() => textbooks.reduce((s, t) => s + t.mappedKcCount, 0));
</script>

<template>
  <div class="resource-management">
    <!-- 列表视图 -->
    <template v-if="viewMode === 'list'">
      <div class="page-header">
        <h2>资源管理</h2>
        <button class="import-btn" disabled title="只读示例；该操作尚未接通">+ 导入教材</button>
      </div>

      <!-- Tab 切换 -->
      <div class="tab-bar">
        <button class="tab" :class="{ active: activeTab === 'textbooks' }" @click="activeTab = 'textbooks'">
          教材管理 <span class="tab-count">{{ textbooks.length }}</span>
        </button>
        <button class="tab" :class="{ active: activeTab === 'domains' }" @click="activeTab = 'domains'">
          领域管理 <span class="tab-count">{{ domains.length }}</span>
        </button>
      </div>

      <!-- 教材管理 -->
      <template v-if="activeTab === 'textbooks'">
        <div class="stats-row">
          <div class="stat-card">
            <span class="stat-label">教材总数</span>
            <span class="stat-value">{{ textbooks.length }}</span>
          </div>
          <div class="stat-card">
            <span class="stat-label">总章节数</span>
            <span class="stat-value">{{ totalChapters }}</span>
          </div>
          <div class="stat-card">
            <span class="stat-label">已映射KC</span>
            <span class="stat-value">{{ totalMappedKc }}</span>
          </div>
          <div class="stat-card">
            <span class="stat-label">启用中</span>
            <span class="stat-value">{{ textbooks.filter(t => t.status === 'active').length }}</span>
          </div>
        </div>

        <div class="textbook-grid">
          <div v-for="tb in textbooks" :key="tb.id" class="textbook-card" @click="openTextbook(tb)">
            <div class="tb-header">
              <div class="tb-icon">📖</div>
              <div class="tb-title-group">
                <h3 class="tb-name">{{ tb.name }}</h3>
                <span class="tb-sub">{{ tb.publisher }} · {{ tb.grade }}</span>
              </div>
              <span class="tb-status" :style="{ color: statusConfig[tb.status].color, background: statusConfig[tb.status].bg }">
                {{ statusConfig[tb.status].label }}
              </span>
            </div>
            <div class="tb-meta">
              <div class="meta-item">
                <span class="meta-label">领域</span>
                <span class="meta-value">{{ tb.domain }}</span>
              </div>
              <div class="meta-item">
                <span class="meta-label">章节</span>
                <span class="meta-value">{{ tb.totalChapters }}</span>
              </div>
              <div class="meta-item">
                <span class="meta-label">映射KC</span>
                <span class="meta-value">{{ tb.mappedKcCount }}</span>
              </div>
              <div class="meta-item">
                <span class="meta-label">未映射</span>
                <span class="meta-value" :class="{ warn: tb.unmappedChapters > 0 }">{{ tb.unmappedChapters }}</span>
              </div>
            </div>
            <div class="tb-progress">
              <div class="progress-track">
                <div class="progress-fill" :style="{ width: (tb.mappedKcCount / Math.max(tb.totalChapters * 8, 1) * 100) + '%' }"></div>
              </div>
              <span class="progress-text">KC映射完成度 {{ Math.round(tb.mappedKcCount / Math.max(tb.totalChapters * 8, 1) * 100) }}%</span>
            </div>
            <div class="tb-footer">
              <span class="import-date">导入于 {{ tb.importedAt }}</span>
              <span class="view-link">查看详情 →</span>
            </div>
          </div>
        </div>
      </template>

      <!-- 领域管理 -->
      <template v-else>
        <div class="domain-list">
          <div v-for="d in domains" :key="d.id" class="domain-card">
            <div class="domain-header">
              <div class="domain-icon">{{ d.subject === '数学' ? '🔢' : d.subject === '语文' ? '📝' : '🔤' }}</div>
              <div>
                <h3>{{ d.name }}</h3>
                <span class="domain-sub">{{ d.subject }}领域</span>
              </div>
              <span class="domain-status" :class="{ active: d.status === 'active' }">{{ d.status === 'active' ? '已启用' : '规划中' }}</span>
            </div>
            <div class="domain-stats">
              <div class="domain-stat">
                <span class="ds-value">{{ d.kcCount }}</span>
                <span class="ds-label">KC数量</span>
              </div>
              <div class="domain-stat">
                <span class="ds-value">{{ d.textbookCount }}</span>
                <span class="ds-label">关联教材</span>
              </div>
              <div class="domain-stat">
                <span class="ds-value">{{ d.studentCount }}</span>
                <span class="ds-label">使用学生</span>
              </div>
            </div>
            <div class="domain-actions">
              <button class="action-btn" disabled title="只读示例；该操作尚未接通">管理KC</button>
              <button class="action-btn" disabled title="只读示例；该操作尚未接通">查看教材</button>
            </div>
          </div>
        </div>
      </template>
    </template>

    <!-- 教材详情视图 -->
    <template v-else-if="selectedTextbook">
      <div class="detail-header">
        <button class="back-btn" @click="backToList">← 返回列表</button>
        <div class="detail-title">
          <h2>{{ selectedTextbook.name }}</h2>
          <span class="detail-sub">{{ selectedTextbook.publisher }} · {{ selectedTextbook.grade }} · {{ selectedTextbook.version }}</span>
        </div>
        <span class="detail-status" :style="{ color: statusConfig[selectedTextbook.status].color, background: statusConfig[selectedTextbook.status].bg }">
          {{ statusConfig[selectedTextbook.status].label }}
        </span>
      </div>

      <div class="detail-stats">
        <div class="ds-card">
          <span class="ds-label">总章节</span>
          <span class="ds-value">{{ selectedTextbook.totalChapters }}</span>
        </div>
        <div class="ds-card">
          <span class="ds-label">已映射KC</span>
          <span class="ds-value">{{ selectedTextbook.mappedKcCount }}</span>
        </div>
        <div class="ds-card">
          <span class="ds-label">未映射章节</span>
          <span class="ds-value" :class="{ warn: selectedTextbook.unmappedChapters > 0 }">{{ selectedTextbook.unmappedChapters }}</span>
        </div>
        <div class="ds-card">
          <span class="ds-label">导入时间</span>
          <span class="ds-value small">{{ selectedTextbook.importedAt }}</span>
        </div>
      </div>

      <div class="chapter-tree">
        <h3>章节结构与 KC 映射</h3>
        <div v-for="unit in selectedTextbook.units" :key="unit.id" class="unit-block">
          <div class="unit-header" @click="toggleUnit(unit.id)">
            <span class="unit-toggle">{{ expandedUnits.has(unit.id) ? '▼' : '▶' }}</span>
            <span class="unit-name">{{ unit.name }}</span>
            <span class="unit-count">{{ unit.chapters.length }} 章</span>
          </div>
          <div v-if="expandedUnits.has(unit.id)" class="chapter-list">
            <div v-for="ch in unit.chapters" :key="ch.id" class="chapter-row">
              <span class="chapter-name">{{ ch.name }}</span>
              <div class="kc-tags">
                <span v-for="kc in ch.kcRefs" :key="kc" class="kc-tag">{{ kc }}</span>
                <span v-if="ch.kcRefs.length === 0" class="kc-tag missing">未映射</span>
              </div>
              <div class="chapter-mastery" v-if="ch.mastery !== undefined">
                <div class="mastery-track">
                  <div class="mastery-fill" :style="{ width: ch.mastery + '%', background: ch.mastery >= 60 ? '#2d8a5e' : ch.mastery >= 40 ? '#c9942a' : '#b85c3c' }"></div>
                </div>
                <span class="mastery-text">{{ ch.mastery }}%</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.resource-management { padding: 20px 24px; height: 100%; overflow-y: auto; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.page-header h2 { margin: 0; font-size: 18px; color: #1a3a2e; }
.import-btn { background: #2d6a4f; color: white; border: none; padding: 8px 16px; border-radius: 6px; font-size: 13px; cursor: pointer; font-family: inherit; }
.import-btn:hover { background: #245440; }

.tab-bar { display: flex; gap: 4px; margin-bottom: 16px; border-bottom: 2px solid #e1e8ed; }
.tab { padding: 8px 20px; background: none; border: none; border-bottom: 2px solid transparent; font-size: 14px; color: #5a6b7a; cursor: pointer; font-family: inherit; margin-bottom: -2px; display: flex; align-items: center; gap: 8px; }
.tab.active { color: #1b4332; font-weight: 600; border-bottom-color: #2d6a4f; }
.tab-count { background: #f0f4f7; padding: 1px 8px; border-radius: 8px; font-size: 11px; }
.tab.active .tab-count { background: #e8f5ee; color: #1b4332; }

.stats-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 16px; }
.stat-card { background: white; border: 1px solid #e1e8ed; border-radius: 10px; padding: 14px 16px; }
.stat-label { display: block; font-size: 12px; color: #8a99a8; margin-bottom: 6px; }
.stat-value { display: block; font-size: 24px; font-weight: 700; color: #1a3a2e; }

.textbook-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 16px; }
.textbook-card { background: white; border: 1px solid #e1e8ed; border-radius: 12px; padding: 18px; cursor: pointer; transition: all 0.2s; }
.textbook-card:hover { border-color: #2d6a4f; box-shadow: 0 4px 12px rgba(45, 106, 79, 0.1); transform: translateY(-2px); }
.tb-header { display: flex; align-items: flex-start; gap: 12px; margin-bottom: 14px; }
.tb-icon { font-size: 28px; flex-shrink: 0; }
.tb-title-group { flex: 1; min-width: 0; }
.tb-name { margin: 0 0 2px 0; font-size: 15px; color: #1a3a2e; }
.tb-sub { font-size: 11px; color: #8a99a8; }
.tb-status { padding: 3px 10px; border-radius: 10px; font-size: 11px; font-weight: 600; flex-shrink: 0; }
.tb-meta { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin-bottom: 12px; }
.meta-item { display: flex; flex-direction: column; gap: 2px; }
.meta-label { font-size: 10px; color: #8a99a8; }
.meta-value { font-size: 13px; font-weight: 600; color: #2c3e50; }
.meta-value.warn { color: #b85c3c; }
.tb-progress { margin-bottom: 12px; }
.progress-track { height: 6px; background: #f0f4f7; border-radius: 3px; overflow: hidden; margin-bottom: 4px; }
.progress-fill { height: 100%; background: linear-gradient(90deg, #2d6a4f, #52b788); border-radius: 3px; }
.progress-text { font-size: 11px; color: #5a6b7a; }
.tb-footer { display: flex; justify-content: space-between; align-items: center; padding-top: 10px; border-top: 1px solid #f0f4f7; }
.import-date { font-size: 11px; color: #8a99a8; }
.view-link { font-size: 12px; color: #2d6a4f; font-weight: 600; }

/* 领域管理 */
.domain-list { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 16px; }
.domain-card { background: white; border: 1px solid #e1e8ed; border-radius: 12px; padding: 18px; }
.domain-header { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; }
.domain-icon { font-size: 32px; }
.domain-header h3 { margin: 0; font-size: 16px; color: #1a3a2e; }
.domain-sub { font-size: 12px; color: #8a99a8; }
.domain-status { margin-left: auto; padding: 3px 10px; border-radius: 10px; font-size: 11px; background: #f0f4f7; color: #8a99a8; }
.domain-status.active { background: #e8f5ee; color: #2d8a5e; }
.domain-stats { display: flex; gap: 16px; margin-bottom: 14px; }
.domain-stat { display: flex; flex-direction: column; align-items: center; flex: 1; }
.ds-value { font-size: 20px; font-weight: 700; color: #1a3a2e; }
.ds-label { font-size: 11px; color: #8a99a8; }
.domain-actions { display: flex; gap: 8px; }
.action-btn { flex: 1; background: none; border: 1px solid #d0d7de; color: #5a6b7a; padding: 6px 12px; border-radius: 6px; font-size: 12px; cursor: pointer; font-family: inherit; }
.action-btn:hover { background: #f0f4f7; }

/* 详情视图 */
.detail-header { display: flex; align-items: center; gap: 16px; margin-bottom: 20px; }
.back-btn { background: none; border: 1px solid #d0d7de; color: #5a6b7a; padding: 6px 14px; border-radius: 6px; font-size: 13px; cursor: pointer; font-family: inherit; flex-shrink: 0; }
.back-btn:hover { background: #f0f4f7; }
.detail-title { flex: 1; }
.detail-title h2 { margin: 0 0 2px 0; font-size: 18px; color: #1a3a2e; }
.detail-sub { font-size: 12px; color: #8a99a8; }
.detail-status { padding: 4px 12px; border-radius: 10px; font-size: 12px; font-weight: 600; flex-shrink: 0; }
.detail-stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 20px; }
.ds-card { background: white; border: 1px solid #e1e8ed; border-radius: 10px; padding: 14px 16px; }
.ds-card .ds-label { display: block; font-size: 12px; color: #8a99a8; margin-bottom: 6px; }
.ds-card .ds-value { display: block; font-size: 22px; font-weight: 700; color: #1a3a2e; }
.ds-card .ds-value.small { font-size: 14px; }
.ds-card .ds-value.warn { color: #b85c3c; }

.chapter-tree { background: white; border: 1px solid #e1e8ed; border-radius: 12px; padding: 18px; }
.chapter-tree h3 { margin: 0 0 14px 0; font-size: 15px; color: #1a3a2e; }
.unit-block { margin-bottom: 8px; }
.unit-header { display: flex; align-items: center; gap: 8px; padding: 10px 12px; background: #f7f9fa; border-radius: 6px; cursor: pointer; font-size: 14px; font-weight: 600; color: #2c3e50; }
.unit-toggle { font-size: 10px; color: #8a99a8; width: 14px; }
.unit-name { flex: 1; }
.unit-count { font-size: 11px; color: #8a99a8; font-weight: 400; }
.chapter-list { padding: 8px 0 8px 30px; }
.chapter-row { display: flex; align-items: center; gap: 12px; padding: 8px 12px; border-bottom: 1px solid #f5f7fa; font-size: 13px; }
.chapter-row:last-child { border-bottom: none; }
.chapter-name { width: 160px; flex-shrink: 0; color: #3a4a5a; }
.kc-tags { flex: 1; display: flex; flex-wrap: wrap; gap: 4px; }
.kc-tag { background: #e8f5ee; color: #1b4332; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-family: Consolas, monospace; }
.kc-tag.missing { background: #fdf0ed; color: #b85c3c; }
.chapter-mastery { display: flex; align-items: center; gap: 8px; width: 140px; flex-shrink: 0; }
.mastery-track { flex: 1; height: 6px; background: #f0f4f7; border-radius: 3px; overflow: hidden; }
.mastery-fill { height: 100%; border-radius: 3px; }
.mastery-text { font-size: 11px; color: #5a6b7a; width: 32px; text-align: right; font-variant-numeric: tabular-nums; }
</style>
