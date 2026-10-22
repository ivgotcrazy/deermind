<script setup lang="ts">
import { ref, computed } from 'vue';
import { learningSpaceInstances, learningTargets } from '../admin-data';
import { textbooks } from '../data';
import type { LSInstance } from '../types';

type ViewMode = 'list' | 'detail';

const viewMode = ref<ViewMode>('list');
const selectedLS = ref<LSInstance | null>(null);
const filterStatus = ref<string>('all');
const filterTextbook = ref<string>('all');
const filterTarget = ref<string>('all');

const filteredLS = computed(() => {
  return learningSpaceInstances.filter(ls => {
    if (filterStatus.value !== 'all' && ls.status !== filterStatus.value) return false;
    if (filterTextbook.value !== 'all' && ls.textbookId !== filterTextbook.value) return false;
    if (filterTarget.value !== 'all' && ls.targetId !== filterTarget.value) return false;
    return true;
  });
});

function openLS(ls: LSInstance) {
  selectedLS.value = ls;
  viewMode.value = 'detail';
}

function backToList() {
  viewMode.value = 'list';
  selectedLS.value = null;
}

const statusConfig: Record<string, { label: string; color: string; bg: string }> = {
  active: { label: '运行中', color: '#2d8a5e', bg: '#e8f5ee' },
  paused: { label: '已暂停', color: '#c9942a', bg: '#fdf6e3' },
  archived: { label: '已归档', color: '#8a99a8', bg: '#f0f4f7' },
};

const totalActive = computed(() => learningSpaceInstances.filter(l => l.status === 'active').length);
const totalInteractions = computed(() => learningSpaceInstances.reduce((s, l) => s + l.totalInteractions, 0));
const totalEvidence = computed(() => learningSpaceInstances.reduce((s, l) => s + l.totalEvidence, 0));
</script>

<template>
  <div class="ls-management">
    <!-- 列表视图 -->
    <template v-if="viewMode === 'list'">
      <div class="page-header">
        <div>
          <h2>学习空间管理</h2>
          <p class="page-desc">管理学生创建的 Learning Space 实例，查看激活的 Domain/Evaluation 子集和运行状态</p>
        </div>
      </div>

      <div class="stats-row">
        <div class="stat-card">
          <span class="stat-label">空间总数</span>
          <span class="stat-value">{{ learningSpaceInstances.length }}</span>
        </div>
        <div class="stat-card">
          <span class="stat-label">运行中</span>
          <span class="stat-value">{{ totalActive }}</span>
        </div>
        <div class="stat-card">
          <span class="stat-label">总交互次数</span>
          <span class="stat-value">{{ totalInteractions }}</span>
        </div>
        <div class="stat-card">
          <span class="stat-label">总证据数</span>
          <span class="stat-value">{{ totalEvidence }}</span>
        </div>
      </div>

      <!-- 筛选 -->
      <div class="filter-bar">
        <div class="filter-item">
          <label>状态</label>
          <select v-model="filterStatus" class="filter-select">
            <option value="all">全部状态</option>
            <option value="active">运行中</option>
            <option value="paused">已暂停</option>
            <option value="archived">已归档</option>
          </select>
        </div>
        <div class="filter-item">
          <label>教材</label>
          <select v-model="filterTextbook" class="filter-select">
            <option value="all">全部教材</option>
            <option v-for="tb in textbooks" :key="tb.id" :value="tb.id">{{ tb.name }}</option>
          </select>
        </div>
        <div class="filter-item">
          <label>目标</label>
          <select v-model="filterTarget" class="filter-select">
            <option value="all">全部目标</option>
            <option v-for="t in learningTargets" :key="t.id" :value="t.id">{{ t.name }}</option>
          </select>
        </div>
        <span class="filter-result">共 {{ filteredLS.length }} 个空间</span>
      </div>

      <!-- 列表 -->
      <div class="table-card">
        <table class="data-table">
          <thead>
            <tr>
              <th>空间ID</th>
              <th>空间名称</th>
              <th>学生</th>
              <th>教材</th>
              <th>目标</th>
              <th>交互次数</th>
              <th>证据数</th>
              <th>状态</th>
              <th>最后活跃</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="ls in filteredLS" :key="ls.id" class="clickable-row" @click="openLS(ls)">
              <td class="mono">{{ ls.id }}</td>
              <td class="font-medium">{{ ls.name }}</td>
              <td>{{ ls.studentName }}</td>
              <td>{{ ls.textbookName }}</td>
              <td>{{ ls.targetName }}</td>
              <td>{{ ls.totalInteractions }}</td>
              <td>{{ ls.totalEvidence }}</td>
              <td>
                <span class="status-tag" :style="{ color: statusConfig[ls.status].color, background: statusConfig[ls.status].bg }">
                  {{ statusConfig[ls.status].label }}
                </span>
              </td>
              <td>{{ ls.lastActive }}</td>
              <td><button class="link-btn" disabled title="只读示例；该操作尚未接通">详情</button></td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>

    <!-- 详情视图 -->
    <template v-else-if="selectedLS">
      <div class="detail-header">
        <button class="back-btn" @click="backToList">← 返回列表</button>
        <div class="detail-title">
          <h2>{{ selectedLS.name }}</h2>
          <span class="status-tag" :style="{ color: statusConfig[selectedLS.status].color, background: statusConfig[selectedLS.status].bg }">
            {{ statusConfig[selectedLS.status].label }}
          </span>
        </div>
        <div class="detail-actions">
          <button class="secondary-btn" v-if="selectedLS.status === 'active'" disabled title="只读示例；该操作尚未接通">暂停</button>
          <button class="secondary-btn" v-else disabled title="只读示例；该操作尚未接通">恢复</button>
          <button class="secondary-btn" disabled title="只读示例；该操作尚未接通">迁移目标</button>
          <button class="secondary-btn" disabled title="只读示例；该操作尚未接通">导出数据</button>
        </div>
      </div>

      <!-- 基本信息 -->
      <div class="detail-meta-row">
        <div class="meta-card">
          <label>所属学生</label>
          <span>{{ selectedLS.studentName }} ({{ selectedLS.studentId }})</span>
        </div>
        <div class="meta-card">
          <label>年级</label>
          <span>{{ selectedLS.grade }}</span>
        </div>
        <div class="meta-card">
          <label>关联教材</label>
          <span>{{ selectedLS.textbookName }}</span>
        </div>
        <div class="meta-card">
          <label>选择目标</label>
          <span>{{ selectedLS.targetName }}</span>
        </div>
        <div class="meta-card">
          <label>所属 Domain</label>
          <span>{{ selectedLS.domainName }}</span>
        </div>
        <div class="meta-card">
          <label>创建时间</label>
          <span>{{ selectedLS.createdAt }}</span>
        </div>
        <div class="meta-card">
          <label>最后活跃</label>
          <span>{{ selectedLS.lastActive }}</span>
        </div>
        <div class="meta-card">
          <label>空间ID</label>
          <span class="mono">{{ selectedLS.id }}</span>
        </div>
      </div>

      <!-- 运行统计 -->
      <div class="stats-row">
        <div class="stat-card">
          <span class="stat-label">总交互次数</span>
          <span class="stat-value">{{ selectedLS.totalInteractions }}</span>
        </div>
        <div class="stat-card">
          <span class="stat-label">总证据数</span>
          <span class="stat-value">{{ selectedLS.totalEvidence }}</span>
        </div>
        <div class="stat-card" v-for="dist in selectedLS.claimStatusDist" :key="dist.status">
          <span class="stat-label">{{ dist.status }}</span>
          <span class="stat-value">{{ dist.count }}</span>
        </div>
      </div>

      <!-- 激活的 Domain 子集 -->
      <div class="section-card">
        <h3 class="section-title">
          激活的 Domain 子集
          <span class="section-count">{{ selectedLS.activatedDomain.taskCount }} Task · {{ selectedLS.activatedDomain.solutionCount }} Solution · {{ selectedLS.activatedDomain.kcCount }} KC</span>
        </h3>
        <table class="data-table">
          <thead>
            <tr>
              <th>Task ID</th>
              <th>Task 名称</th>
              <th>所属章节</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="task in selectedLS.activatedDomain.tasks" :key="task.id">
              <td class="mono">{{ task.id }}</td>
              <td class="font-medium">{{ task.name }}</td>
              <td>{{ task.chapter }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- 激活的 Evaluation 子集 -->
      <div class="section-card">
        <h3 class="section-title">
          激活的 Evaluation 子集
          <span class="section-count">{{ selectedLS.activatedEvaluation.claimCount }} Claim · {{ selectedLS.activatedEvaluation.dimensionCount }} 维度</span>
        </h3>
        <div class="claim-activation-list">
          <div v-for="claim in selectedLS.activatedEvaluation.claims" :key="claim.id" class="claim-activation-item">
            <div class="claim-activation-header">
              <span class="mono">{{ claim.id }}</span>
              <span class="claim-name">{{ claim.name }}</span>
            </div>
            <div class="dimension-tags">
              <span v-for="dim in claim.dimensions" :key="dim" class="dim-tag">{{ dim }}</span>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.ls-management { height: 100%; overflow-y: auto; padding: 24px; }
.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px; }
.page-header h2 { margin: 0 0 4px 0; font-size: 20px; color: #1a2a3a; }
.page-desc { margin: 0; font-size: 13px; color: #8a99a8; }
.stats-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 16px; }
.stat-card { background: #fff; border-radius: 8px; padding: 16px; border: 1px solid #e8ecf0; }
.stat-label { display: block; font-size: 12px; color: #8a99a8; margin-bottom: 6px; }
.stat-value { font-size: 24px; font-weight: 600; color: #1a2a3a; }
.filter-bar { display: flex; align-items: center; gap: 16px; background: #fff; padding: 12px 16px; border-radius: 8px; border: 1px solid #e8ecf0; margin-bottom: 16px; }
.filter-item { display: flex; align-items: center; gap: 8px; }
.filter-item label { font-size: 13px; color: #5a6b7a; }
.filter-select { padding: 6px 10px; border: 1px solid #d0d8e0; border-radius: 6px; font-size: 13px; font-family: inherit; background: #fff; }
.filter-result { margin-left: auto; font-size: 13px; color: #8a99a8; }
.table-card { background: #fff; border-radius: 8px; border: 1px solid #e8ecf0; overflow: hidden; }
.data-table { width: 100%; border-collapse: collapse; }
.data-table th { text-align: left; padding: 12px 16px; font-size: 12px; color: #8a99a8; font-weight: 600; background: #f8fafc; border-bottom: 1px solid #e8ecf0; }
.data-table td { padding: 12px 16px; font-size: 13px; color: #3a4a5a; border-bottom: 1px solid #f0f4f7; }
.clickable-row { cursor: pointer; transition: background 0.15s; }
.clickable-row:hover { background: #f8fafc; }
.mono { font-family: 'SF Mono', 'Consolas', monospace; font-size: 12px; color: #5a6b7a; }
.font-medium { font-weight: 500; }
.status-tag { font-size: 11px; padding: 3px 8px; border-radius: 4px; font-weight: 500; }
.link-btn { background: none; border: none; color: #2d6a4f; cursor: pointer; font-size: 13px; font-family: inherit; padding: 0; }
.link-btn:hover { text-decoration: underline; }
.detail-header { margin-bottom: 16px; }
.back-btn { background: none; border: none; color: #5a6b7a; cursor: pointer; font-size: 13px; font-family: inherit; padding: 0; margin-bottom: 12px; }
.back-btn:hover { color: #2d6a4f; }
.detail-title { display: flex; align-items: center; gap: 12px; margin-bottom: 8px; }
.detail-title h2 { margin: 0; font-size: 20px; color: #1a2a3a; }
.detail-actions { display: flex; gap: 8px; margin-top: 8px; }
.secondary-btn { background: #fff; border: 1px solid #d0d8e0; padding: 6px 14px; border-radius: 6px; font-size: 13px; color: #5a6b7a; cursor: pointer; font-family: inherit; }
.secondary-btn:hover { border-color: #2d6a4f; color: #2d6a4f; }
.detail-meta-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 16px; }
.meta-card { background: #fff; border: 1px solid #e8ecf0; border-radius: 8px; padding: 12px 16px; }
.meta-card label { display: block; font-size: 11px; color: #8a99a8; margin-bottom: 4px; }
.meta-card span { font-size: 13px; color: #3a4a5a; font-weight: 500; }
.section-card { background: #fff; border: 1px solid #e8ecf0; border-radius: 8px; padding: 20px; margin-bottom: 16px; }
.section-title { font-size: 15px; font-weight: 600; color: #1a2a3a; margin: 0 0 16px 0; display: flex; align-items: center; gap: 8px; }
.section-count { font-size: 12px; font-weight: 400; color: #8a99a8; background: #f0f4f7; padding: 2px 8px; border-radius: 10px; }
.claim-activation-list { display: flex; flex-direction: column; gap: 10px; }
.claim-activation-item { border: 1px solid #e8ecf0; border-radius: 8px; padding: 12px 16px; }
.claim-activation-header { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }
.claim-name { font-size: 14px; font-weight: 500; color: #1a2a3a; }
.dimension-tags { display: flex; gap: 6px; flex-wrap: wrap; }
.dim-tag { font-size: 11px; padding: 3px 8px; border-radius: 4px; background: #e8f5ee; color: #2d8a5e; font-weight: 500; }
</style>
