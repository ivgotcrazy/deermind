<script setup lang="ts">
import { ref, computed, watch } from 'vue';
import { spaceOverviews, learningSpaces } from '../data';
import type { SpaceId, SpaceOverview, SpaceObjectItem, LearningSpace } from '../types';

const emit = defineEmits<{ goDetail: [objectId: string] }>();

const currentSpaceId = ref<SpaceId>('domain');
const currentObjectType = ref('');
const selectedLsId = ref<string>('all'); // 'all' = 全局聚合

const currentSpace = computed((): SpaceOverview => {
  return spaceOverviews.find(s => s.spaceId === currentSpaceId.value)!;
});

const isGlobalSpace = computed(() => currentSpace.value.isGlobal);

// 按学生分组的 Learning Space 列表（用于选择器的分组显示）
const lsByStudent = computed(() => {
  const map = new Map<string, LearningSpace[]>();
  for (const ls of learningSpaces) {
    if (!map.has(ls.studentName)) map.set(ls.studentName, []);
    map.get(ls.studentName)!.push(ls);
  }
  return Array.from(map.entries());
});

const selectedLs = computed(() => {
  if (selectedLsId.value === 'all') return null;
  return learningSpaces.find(ls => ls.id === selectedLsId.value) || null;
});

// 当前对象列表（按 LS 过滤）
const currentObjects = computed((): SpaceObjectItem[] => {
  if (!currentObjectType.value) return [];
  const all = currentSpace.value.objects[currentObjectType.value] || [];
  if (selectedLsId.value === 'all' || isGlobalSpace.value) return all;
  return all.filter(o => o.lsId === selectedLsId.value);
});

// 当前对象类型的计数（按 LS 过滤后）
const filteredTypeCounts = computed(() => {
  const result: Record<string, number> = {};
  for (const ot of currentSpace.value.objectTypes) {
    const all = currentSpace.value.objects[ot.id] || [];
    if (selectedLsId.value === 'all' || isGlobalSpace.value) {
      result[ot.id] = all.length;
    } else {
      result[ot.id] = all.filter(o => o.lsId === selectedLsId.value).length;
    }
  }
  return result;
});

function lsLabel(lsId?: string): string {
  if (!lsId) return '';
  const ls = learningSpaces.find(l => l.id === lsId);
  if (!ls) return lsId;
  return `${ls.studentName} · ${ls.subject}·${ls.textbook}${ls.grade}`;
}

function selectSpace(spaceId: SpaceId) {
  currentSpaceId.value = spaceId;
  selectedLsId.value = 'all'; // 切换 Space 时重置为全局聚合
  const firstType = currentSpace.value.objectTypes[0];
  currentObjectType.value = firstType ? firstType.id : '';
}

// 初始化
selectSpace('domain');

const spaceNav = [
  { id: 'domain' as SpaceId, label: 'Domain Space', icon: '📐', desc: '领域知识体系' },
  { id: 'learning' as SpaceId, label: 'Learning Space', icon: '📚', desc: '学生学习空间' },
  { id: 'evaluation' as SpaceId, label: 'Evaluation Space', icon: '📊', desc: '证据与信念评估' },
  { id: 'interaction' as SpaceId, label: 'Interaction Space', icon: '💬', desc: '观察与教学决策' },
  { id: 'reasoning' as SpaceId, label: 'AI Reasoning', icon: '🧠', desc: '推理运行时' },
  { id: 'evolution' as SpaceId, label: 'Evolution Space', icon: '🌱', desc: '系统演化（MVP后）' },
];

const statusColor: Record<string, string> = {
  active: '#2d8a5e', committed: '#2d8a5e', passed: '#2d8a5e', approved: '#2d8a5e',
  draft: '#8a99a8', experimental: '#8a99a8',
  rejected: '#b85c3c', failed: '#b85c3c', skipped: '#9aaab8',
  executed: '#4a6fa5', completed: '#4a6fa5',
};
</script>

<template>
  <div class="space-browser">
    <!-- 左侧 Space 导航 -->
    <aside class="space-nav">
      <h3 class="nav-title">观测空间</h3>
      <button
        v-for="nav in spaceNav"
        :key="nav.id"
        class="space-nav-item"
        :class="{ active: currentSpaceId === nav.id }"
        @click="selectSpace(nav.id)"
      >
        <span class="nav-icon">{{ nav.icon }}</span>
        <div class="nav-text">
          <span class="nav-label">{{ nav.label }}</span>
          <span class="nav-desc">{{ nav.desc }}</span>
        </div>
      </button>
    </aside>

    <!-- 右侧 Space 详情 -->
    <div class="space-content">
      <!-- Space 标题 + 范围选择器 -->
      <div class="space-header">
        <div>
          <h2>{{ currentSpace.spaceName }}</h2>
          <p class="space-desc">{{ currentSpace.description }}</p>
        </div>
        <!-- 非全局 Space 显示 Learning Space 范围选择器 -->
        <div v-if="!isGlobalSpace" class="ls-selector">
          <span class="ls-label">观测范围</span>
          <select v-model="selectedLsId" class="ls-select">
            <option value="all">全部 Learning Space（聚合）</option>
            <optgroup v-for="[student, lsList] in lsByStudent" :key="student" :label="student">
              <option v-for="ls in lsList" :key="ls.id" :value="ls.id">
                {{ ls.subject }}·{{ ls.textbook }}{{ ls.grade }}
                <template v-if="ls.status === 'paused'">（已暂停）</template>
              </option>
            </optgroup>
          </select>
        </div>
        <div v-else class="global-badge">
          <span class="global-icon">🌐</span> 全局共享空间
        </div>
      </div>

      <!-- 选中 LS 时显示该 LS 概览 -->
      <div v-if="selectedLs" class="ls-info-bar">
        <div class="ls-info-item">
          <span class="ls-info-label">学生</span>
          <span class="ls-info-value">{{ selectedLs.studentName }}</span>
        </div>
        <div class="ls-info-item">
          <span class="ls-info-label">学科·教材</span>
          <span class="ls-info-value">{{ selectedLs.subject }}·{{ selectedLs.textbook }}{{ selectedLs.grade }}</span>
        </div>
        <div class="ls-info-item">
          <span class="ls-info-label">交互次数</span>
          <span class="ls-info-value">{{ selectedLs.totalInteractions }}</span>
        </div>
        <div class="ls-info-item">
          <span class="ls-info-label">平均掌握度</span>
          <span class="ls-info-value">{{ selectedLs.avgMastery }}%</span>
        </div>
        <div class="ls-info-item">
          <span class="ls-info-label">最后活跃</span>
          <span class="ls-info-value">{{ selectedLs.lastActive }}</span>
        </div>
        <div class="ls-info-item">
          <span class="ls-status-tag" :class="selectedLs.status">{{ selectedLs.status === 'active' ? '活跃' : selectedLs.status === 'paused' ? '已暂停' : '已归档' }}</span>
        </div>
      </div>

      <!-- 概览指标 -->
      <div class="metric-row">
        <div v-for="m in currentSpace.metrics" :key="m.label" class="metric-card">
          <span class="metric-label">{{ m.label }}</span>
          <span class="metric-value">{{ m.value }}</span>
          <span class="metric-sub" v-if="m.sub">{{ m.sub }}</span>
        </div>
      </div>

      <!-- 分布图 -->
      <div class="dist-row">
        <div v-for="dist in currentSpace.distributions" :key="dist.title" class="dist-card">
          <h4>{{ dist.title }}</h4>
          <div class="dist-bars">
            <div v-for="item in dist.items" :key="item.label" class="dist-bar-item">
              <span class="dist-label">{{ item.label }}</span>
              <div class="dist-track">
                <div class="dist-fill" :style="{ width: (item.count / Math.max(...dist.items.map(i => i.count)) * 100) + '%', background: item.color }"></div>
              </div>
              <span class="dist-count">{{ item.count }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 对象类型 Tab -->
      <div class="object-tabs">
        <button
          v-for="ot in currentSpace.objectTypes"
          :key="ot.id"
          class="object-tab"
          :class="{ active: currentObjectType === ot.id }"
          @click="currentObjectType = ot.id"
        >
          {{ ot.label }}
          <span class="tab-count">{{ filteredTypeCounts[ot.id] !== undefined ? filteredTypeCounts[ot.id] : ot.count }}</span>
        </button>
      </div>

      <!-- 对象列表 -->
      <div class="object-table" v-if="currentObjects.length > 0">
        <div class="table-header">
          <span class="col-id">ID</span>
          <span class="col-name">名称</span>
          <span class="col-type">类型</span>
          <span class="col-metrics">关键指标</span>
          <span class="col-ls" v-if="!isGlobalSpace && selectedLsId === 'all'">归属 LS</span>
          <span class="col-status">状态</span>
          <span class="col-time">更新</span>
        </div>
        <div
          v-for="obj in currentObjects"
          :key="obj.id"
          class="table-row"
          @click="emit('goDetail', obj.id)"
        >
          <span class="col-id mono">{{ obj.id }}</span>
          <span class="col-name">{{ obj.name }}</span>
          <span class="col-type">{{ obj.type }}</span>
          <span class="col-metrics">
            <span v-for="(m, i) in obj.metrics" :key="i" class="metric-pill">
              {{ m.label }}: <strong>{{ m.value }}</strong>
            </span>
          </span>
          <span class="col-ls" v-if="!isGlobalSpace && selectedLsId === 'all'">
            <span class="ls-tag" v-if="obj.lsId">{{ lsLabel(obj.lsId) }}</span>
            <span class="ls-tag global" v-else>全局</span>
          </span>
          <span class="col-status">
            <span class="status-dot" :style="{ background: statusColor[obj.status] || '#8a99a8' }"></span>
            {{ obj.status }}
          </span>
          <span class="col-time">{{ obj.updatedAt }}</span>
        </div>
      </div>

      <!-- 空状态 -->
      <div class="empty-state" v-else>
        <span class="empty-icon">📋</span>
        <p>该类型暂无数据</p>
        <p class="empty-hint" v-if="currentSpaceId === 'evolution'">Evolution Space 将在 MVP 之后启用</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.space-browser { display: flex; height: 100%; overflow: hidden; }

/* 左侧导航 */
.space-nav {
  width: 220px; flex-shrink: 0; background: white; border-right: 1px solid #e1e8ed;
  padding: 16px 12px; overflow-y: auto;
}
.nav-title { margin: 0 0 12px 0; font-size: 12px; color: #8a99a8; text-transform: uppercase; font-weight: 600; padding: 0 8px; }
.space-nav-item {
  display: flex; align-items: flex-start; gap: 10px; width: 100%;
  padding: 10px; background: none; border: none; border-radius: 8px;
  cursor: pointer; font-family: inherit; text-align: left; margin-bottom: 4px;
  transition: background 0.15s;
}
.space-nav-item:hover { background: #f5f9f7; }
.space-nav-item.active { background: #e8f5ee; border-left: 3px solid #2d6a4f; padding-left: 7px; }
.nav-icon { font-size: 18px; flex-shrink: 0; margin-top: 1px; }
.nav-text { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.nav-label { font-size: 13px; font-weight: 600; color: #2c3e50; }
.space-nav-item.active .nav-label { color: #1b4332; }
.nav-desc { font-size: 11px; color: #8a99a8; }

/* 右侧内容 */
.space-content { flex: 1; overflow-y: auto; padding: 20px 24px; }
.space-header { margin-bottom: 16px; display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; }
.space-header h2 { margin: 0 0 4px 0; font-size: 20px; color: #1a3a2e; }
.space-desc { margin: 0; font-size: 13px; color: #6a7a8a; }

/* LS 范围选择器 */
.ls-selector { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }
.ls-label { font-size: 12px; color: #8a99a8; white-space: nowrap; }
.ls-select { padding: 7px 12px; border: 1px solid #d0d7de; border-radius: 6px; font-size: 13px; font-family: inherit; background: white; min-width: 240px; cursor: pointer; }
.ls-select:focus { outline: none; border-color: #2d6a4f; }
.global-badge { display: flex; align-items: center; gap: 6px; padding: 6px 12px; background: #f0f4f7; border-radius: 6px; font-size: 12px; color: #5a6b7a; flex-shrink: 0; }
.global-icon { font-size: 14px; }

/* LS 信息栏 */
.ls-info-bar { display: flex; gap: 20px; padding: 12px 16px; background: #e8f5ee; border: 1px solid #b8dfc8; border-radius: 8px; margin-bottom: 16px; flex-wrap: wrap; }
.ls-info-item { display: flex; flex-direction: column; gap: 2px; }
.ls-info-label { font-size: 10px; color: #5a7a6a; text-transform: uppercase; }
.ls-info-value { font-size: 13px; font-weight: 600; color: #1a3a2e; }
.ls-status-tag { padding: 3px 10px; border-radius: 10px; font-size: 11px; font-weight: 600; align-self: center; }
.ls-status-tag.active { background: #2d8a5e; color: white; }
.ls-status-tag.paused { background: #c9942a; color: white; }
.ls-status-tag.archived { background: #8a99a8; color: white; }

/* 指标行 */
.metric-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 16px; }
.metric-card { background: white; border: 1px solid #e1e8ed; border-radius: 10px; padding: 14px 16px; }
.metric-label { display: block; font-size: 11px; color: #8a99a8; margin-bottom: 6px; }
.metric-value { display: block; font-size: 24px; font-weight: 700; color: #1a3a2e; }
.metric-sub { display: block; font-size: 11px; color: #5a7a6a; margin-top: 2px; }

/* 分布图 */
.dist-row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 20px; }
.dist-card { background: white; border: 1px solid #e1e8ed; border-radius: 10px; padding: 14px 16px; }
.dist-card h4 { margin: 0 0 12px 0; font-size: 13px; color: #1a3a2e; }
.dist-bars { display: flex; flex-direction: column; gap: 8px; }
.dist-bar-item { display: flex; align-items: center; gap: 8px; font-size: 12px; }
.dist-label { width: 100px; flex-shrink: 0; color: #5a6b7a; font-size: 11px; }
.dist-track { flex: 1; height: 14px; background: #f0f4f7; border-radius: 3px; overflow: hidden; }
.dist-fill { height: 100%; border-radius: 3px; min-width: 2px; }
.dist-count { width: 30px; text-align: right; font-weight: 600; color: #2c3e50; font-variant-numeric: tabular-nums; }

/* 对象 Tab */
.object-tabs { display: flex; gap: 4px; margin-bottom: 12px; border-bottom: 2px solid #e1e8ed; }
.object-tab {
  padding: 8px 16px; background: none; border: none; border-bottom: 2px solid transparent;
  font-size: 13px; color: #5a6b7a; cursor: pointer; font-family: inherit;
  margin-bottom: -2px; transition: all 0.15s; display: flex; align-items: center; gap: 6px;
}
.object-tab:hover { color: #2c3e50; }
.object-tab.active { color: #1b4332; font-weight: 600; border-bottom-color: #2d6a4f; }
.tab-count { background: #f0f4f7; padding: 1px 7px; border-radius: 8px; font-size: 11px; font-weight: 500; }
.object-tab.active .tab-count { background: #e8f5ee; color: #1b4332; }

/* 对象表格 */
.object-table { background: white; border: 1px solid #e1e8ed; border-radius: 10px; overflow: hidden; }
.table-header { display: flex; padding: 10px 16px; background: #f7f9fa; border-bottom: 1px solid #e1e8ed; font-size: 11px; font-weight: 600; color: #5a6b7a; }
.table-row { display: flex; padding: 12px 16px; border-bottom: 1px solid #f5f7fa; cursor: pointer; align-items: center; font-size: 13px; transition: background 0.1s; }
.table-row:hover { background: #f5f9f7; }
.col-id { width: 90px; flex-shrink: 0; font-size: 11px; color: #5a6b7a; }
.col-name { width: 180px; flex-shrink: 0; font-weight: 500; color: #2c3e50; }
.col-type { width: 100px; flex-shrink: 0; color: #5a6b7a; font-size: 12px; }
.col-metrics { flex: 1; display: flex; flex-wrap: wrap; gap: 6px; min-width: 0; }
.metric-pill { background: #f0f4f7; padding: 2px 8px; border-radius: 4px; font-size: 11px; color: #5a6b7a; white-space: nowrap; }
.metric-pill strong { color: #1a3a2e; font-weight: 600; }
.col-status { width: 90px; flex-shrink: 0; display: flex; align-items: center; gap: 6px; font-size: 12px; color: #3a4a5a; text-transform: capitalize; }
.status-dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }
.col-time { width: 60px; flex-shrink: 0; color: #8a99a8; font-size: 12px; text-align: right; }
.col-ls { width: 180px; flex-shrink: 0; }
.ls-tag { font-size: 11px; color: #4a6fa5; background: #e8f0f8; padding: 2px 8px; border-radius: 4px; white-space: nowrap; }
.ls-tag.global { color: #8a99a8; background: #f0f4f7; }
.mono { font-family: Consolas, Monaco, monospace; }

/* 空状态 */
.empty-state { text-align: center; padding: 60px 20px; color: #8a99a8; background: white; border: 1px dashed #d0d7de; border-radius: 10px; }
.empty-icon { font-size: 40px; display: block; margin-bottom: 12px; }
.empty-state p { margin: 4px 0; }
.empty-hint { font-size: 12px; color: #a0aab8; }

@media (max-width: 1200px) {
  .metric-row { grid-template-columns: repeat(2, 1fr); }
  .dist-row { grid-template-columns: 1fr; }
}
</style>
