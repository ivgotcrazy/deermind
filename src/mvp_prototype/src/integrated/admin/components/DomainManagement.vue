<script setup lang="ts">
import { ref, computed } from 'vue';
import { domains } from '../data';
import { domainDetails } from '../admin-data';
import type { Domain, DomainDetail, DomainTask, DomainSolution, DomainKC } from '../types';

type ViewMode = 'list' | 'detail';
type DetailTab = 'tasks' | 'solutions' | 'kcs';

const viewMode = ref<ViewMode>('list');
const selectedDomain = ref<DomainDetail | null>(null);
const activeTab = ref<DetailTab>('tasks');
const selectedItemId = ref<string>('');

function openDomain(domain: Domain) {
  selectedDomain.value = domainDetails[domain.id] || null;
  viewMode.value = 'detail';
  activeTab.value = 'tasks';
  selectedItemId.value = '';
}

function backToList() {
  viewMode.value = 'list';
  selectedDomain.value = null;
  selectedItemId.value = '';
}

const statusConfig: Record<string, { label: string; color: string; bg: string }> = {
  active: { label: '已启用', color: '#2d8a5e', bg: '#e8f5ee' },
  draft: { label: '草稿', color: '#8a99a8', bg: '#f0f4f7' },
};

const taskTypeConfig: Record<string, string> = {
  'problem-solving': '解题',
  'explanation': '解释',
  'modeling': '建模',
  'proof': '证明',
};

const currentTasks = computed(() => selectedDomain.value?.tasks || []);
const currentSolutions = computed(() => selectedDomain.value?.solutions || []);
const currentKCs = computed(() => selectedDomain.value?.kcs || []);

const selectedTask = computed(() => currentTasks.value.find(t => t.id === selectedItemId.value));
const selectedSolution = computed(() => currentSolutions.value.find(s => s.id === selectedItemId.value));
const selectedKC = computed(() => currentKCs.value.find(k => k.id === selectedItemId.value));

function selectItem(id: string) {
  selectedItemId.value = selectedItemId.value === id ? '' : id;
}
</script>

<template>
  <div class="domain-management">
    <!-- 列表视图 -->
    <template v-if="viewMode === 'list'">
      <div class="page-header">
        <div>
          <h2>领域管理</h2>
          <p class="page-desc">管理 Domain Space 中的领域知识结构，包括 Task、Solution、KC</p>
        </div>
        <button class="primary-btn" disabled title="只读示例；该操作尚未接通">+ 新建领域</button>
      </div>

      <div class="stats-row">
        <div class="stat-card">
          <span class="stat-label">领域总数</span>
          <span class="stat-value">{{ domains.length }}</span>
        </div>
        <div class="stat-card">
          <span class="stat-label">已启用</span>
          <span class="stat-value">{{ domains.filter(d => d.status === 'active').length }}</span>
        </div>
        <div class="stat-card">
          <span class="stat-label">关联教材</span>
          <span class="stat-value">{{ domains.reduce((s, d) => s + d.textbookCount, 0) }}</span>
        </div>
        <div class="stat-card">
          <span class="stat-label">覆盖学生</span>
          <span class="stat-value">{{ domains.reduce((s, d) => s + d.studentCount, 0) }}</span>
        </div>
      </div>

      <div class="table-card">
        <table class="data-table">
          <thead>
            <tr>
              <th>领域ID</th>
              <th>名称</th>
              <th>学科</th>
              <th>KC 数量</th>
              <th>关联教材</th>
              <th>学生数</th>
              <th>状态</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="d in domains" :key="d.id" @click="openDomain(d)" class="clickable-row">
              <td class="mono">{{ d.id }}</td>
              <td class="font-medium">{{ d.name }}</td>
              <td>{{ d.subject }}</td>
              <td>{{ d.kcCount }}</td>
              <td>{{ d.textbookCount }}</td>
              <td>{{ d.studentCount }}</td>
              <td>
                <span class="status-tag" :style="{ color: statusConfig[d.status].color, background: statusConfig[d.status].bg }">
                  {{ statusConfig[d.status].label }}
                </span>
              </td>
              <td><button class="link-btn" disabled title="只读示例；该操作尚未接通">管理</button></td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>

    <!-- 详情视图 -->
    <template v-else-if="selectedDomain">
      <div class="detail-header">
        <button class="back-btn" @click="backToList">← 返回列表</button>
        <div class="detail-title">
          <h2>{{ selectedDomain.name }}</h2>
          <span class="status-tag" :style="{ color: statusConfig[selectedDomain.status].color, background: statusConfig[selectedDomain.status].bg }">
            {{ statusConfig[selectedDomain.status].label }}
          </span>
        </div>
        <div class="detail-meta">
          <span>{{ selectedDomain.subject }} · {{ selectedDomain.gradeRange }}</span>
          <span>{{ selectedDomain.tasks.length }} 个 Task · {{ selectedDomain.solutions.length }} 个 Solution · {{ selectedDomain.kcs.length }} 个 KC</span>
        </div>
      </div>

      <div class="detail-desc">{{ selectedDomain.description }}</div>

      <!-- Tab 切换 -->
      <div class="tab-bar">
        <button class="tab" :class="{ active: activeTab === 'tasks' }" @click="activeTab = 'tasks'; selectedItemId = ''">
          Task <span class="tab-count">{{ selectedDomain.tasks.length }}</span>
        </button>
        <button class="tab" :class="{ active: activeTab === 'solutions' }" @click="activeTab = 'solutions'; selectedItemId = ''">
          Solution <span class="tab-count">{{ selectedDomain.solutions.length }}</span>
        </button>
        <button class="tab" :class="{ active: activeTab === 'kcs' }" @click="activeTab = 'kcs'; selectedItemId = ''">
          KC <span class="tab-count">{{ selectedDomain.kcs.length }}</span>
        </button>
        <button class="tab-add" disabled title="只读示例；该操作尚未接通">+ 新建</button>
      </div>

      <!-- Task 列表 -->
      <div v-if="activeTab === 'tasks'" class="detail-content">
        <div class="item-list">
          <div
            v-for="task in currentTasks"
            :key="task.id"
            class="item-card"
            :class="{ expanded: selectedItemId === task.id }"
            @click="selectItem(task.id)"
          >
            <div class="item-header">
              <div class="item-title">
                <span class="mono item-id">{{ task.id }}</span>
                <span class="item-name">{{ task.name }}</span>
                <span class="type-tag">{{ taskTypeConfig[task.taskType] || task.taskType }}</span>
              </div>
              <span class="status-tag" :style="{ color: statusConfig[task.status].color, background: statusConfig[task.status].bg }">
                {{ statusConfig[task.status].label }}
              </span>
            </div>
            <div class="item-summary">{{ task.description }}</div>
            <div class="item-meta">
              <span>关联 KC: {{ task.kcRefs.join(', ') }}</span>
              <span>关联 Solution: {{ task.solutionRefs.join(', ') }}</span>
              <span>{{ task.createdAt }}</span>
            </div>
            <div v-if="selectedItemId === task.id" class="item-detail-panel">
              <div class="detail-grid">
                <div class="detail-field"><label>参数范围</label><span>{{ task.parameterRange }}</span></div>
                <div class="detail-field"><label>情境</label><span>{{ task.context }}</span></div>
                <div class="detail-field"><label>表征</label><span>{{ task.representation }}</span></div>
                <div class="detail-field"><label>排除范围</label><span>{{ task.exclusionScope }}</span></div>
              </div>
              <div class="detail-actions">
                <button class="secondary-btn" disabled title="只读示例；该操作尚未接通">编辑</button>
                <button class="secondary-btn" disabled title="只读示例；该操作尚未接通">查看关联 Claim</button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Solution 列表 -->
      <div v-if="activeTab === 'solutions'" class="detail-content">
        <div class="item-list">
          <div
            v-for="sol in currentSolutions"
            :key="sol.id"
            class="item-card"
            :class="{ expanded: selectedItemId === sol.id }"
            @click="selectItem(sol.id)"
          >
            <div class="item-header">
              <div class="item-title">
                <span class="mono item-id">{{ sol.id }}</span>
                <span class="item-name">{{ sol.name }}</span>
              </div>
              <span class="status-tag" :style="{ color: statusConfig[sol.status].color, background: statusConfig[sol.status].bg }">
                {{ statusConfig[sol.status].label }}
              </span>
            </div>
            <div class="item-summary">{{ sol.description }}</div>
            <div class="item-meta">
              <span>方法: {{ sol.method }}</span>
              <span>关联 Task: {{ sol.taskRefs.join(', ') }}</span>
            </div>
            <div v-if="selectedItemId === sol.id" class="item-detail-panel">
              <div class="detail-grid">
                <div class="detail-field"><label>适用条件</label><span>{{ sol.applicableConditions }}</span></div>
                <div class="detail-field"><label>子任务依赖</label><span>{{ sol.subtaskDependencies.length > 0 ? sol.subtaskDependencies.join(', ') : '无' }}</span></div>
              </div>
              <div class="detail-actions">
                <button class="secondary-btn" disabled title="只读示例；该操作尚未接通">编辑</button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- KC 列表 -->
      <div v-if="activeTab === 'kcs'" class="detail-content">
        <div class="item-list">
          <div
            v-for="kc in currentKCs"
            :key="kc.id"
            class="item-card"
            :class="{ expanded: selectedItemId === kc.id }"
            @click="selectItem(kc.id)"
          >
            <div class="item-header">
              <div class="item-title">
                <span class="mono item-id">{{ kc.id }}</span>
                <span class="item-name">{{ kc.name }}</span>
              </div>
              <span class="status-tag" :style="{ color: statusConfig[kc.status].color, background: statusConfig[kc.status].bg }">
                {{ statusConfig[kc.status].label }}
              </span>
            </div>
            <div class="item-summary">{{ kc.description }}</div>
            <div class="item-meta">
              <span>前置 KC: {{ kc.prerequisites.length > 0 ? kc.prerequisites.join(', ') : '无' }}</span>
              <span>关联 KC: {{ kc.relatedKCs.join(', ') }}</span>
              <span>{{ kc.taskCount }} 个 Task</span>
            </div>
            <div v-if="selectedItemId === kc.id" class="item-detail-panel">
              <div class="detail-actions">
                <button class="secondary-btn" disabled title="只读示例；该操作尚未接通">编辑</button>
                <button class="secondary-btn" disabled title="只读示例；该操作尚未接通">查看知识图谱</button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.domain-management { height: 100%; overflow-y: auto; padding: 24px; }
.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px; }
.page-header h2 { margin: 0 0 4px 0; font-size: 20px; color: #1a2a3a; }
.page-desc { margin: 0; font-size: 13px; color: #8a99a8; }
.primary-btn { background: #2d6a4f; color: #fff; border: none; padding: 8px 16px; border-radius: 6px; font-size: 13px; cursor: pointer; font-family: inherit; }
.primary-btn:hover { background: #1b4332; }
.stats-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 20px; }
.stat-card { background: #fff; border-radius: 8px; padding: 16px; border: 1px solid #e8ecf0; }
.stat-label { display: block; font-size: 12px; color: #8a99a8; margin-bottom: 6px; }
.stat-value { font-size: 24px; font-weight: 600; color: #1a2a3a; }
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
.detail-meta { display: flex; gap: 20px; font-size: 13px; color: #8a99a8; }
.detail-desc { background: #f8fafc; border-radius: 8px; padding: 12px 16px; font-size: 13px; color: #5a6b7a; margin-bottom: 16px; border-left: 3px solid #2d6a4f; }
.tab-bar { display: flex; gap: 0; border-bottom: 2px solid #e8ecf0; margin-bottom: 16px; }
.tab { background: none; border: none; padding: 10px 16px; font-size: 13px; color: #8a99a8; cursor: pointer; font-family: inherit; border-bottom: 2px solid transparent; margin-bottom: -2px; display: flex; align-items: center; gap: 6px; }
.tab:hover { color: #3a4a5a; }
.tab.active { color: #2d6a4f; border-bottom-color: #2d6a4f; font-weight: 500; }
.tab-count { font-size: 11px; background: #e8ecf0; padding: 1px 6px; border-radius: 8px; }
.tab.active .tab-count { background: #d8f3e3; color: #2d6a4f; }
.tab-add { margin-left: auto; background: none; border: 1px solid #d0d8e0; padding: 6px 12px; border-radius: 6px; font-size: 12px; color: #5a6b7a; cursor: pointer; font-family: inherit; align-self: center; }
.tab-add:hover { border-color: #2d6a4f; color: #2d6a4f; }
.detail-content { display: flex; gap: 0; }
.item-list { flex: 1; }
.item-card { background: #fff; border: 1px solid #e8ecf0; border-radius: 8px; padding: 14px 16px; margin-bottom: 10px; cursor: pointer; transition: all 0.15s; }
.item-card:hover { border-color: #c0d0c8; }
.item-card.expanded { border-color: #2d6a4f; box-shadow: 0 2px 8px rgba(45,106,79,0.1); }
.item-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
.item-title { display: flex; align-items: center; gap: 10px; }
.item-id { font-size: 11px; }
.item-name { font-size: 14px; font-weight: 500; color: #1a2a3a; }
.type-tag { font-size: 11px; background: #eef2f7; color: #5a6b7a; padding: 2px 6px; border-radius: 4px; }
.item-summary { font-size: 13px; color: #5a6b7a; margin-bottom: 8px; }
.item-meta { display: flex; gap: 16px; font-size: 12px; color: #8a99a8; flex-wrap: wrap; }
.item-detail-panel { margin-top: 12px; padding-top: 12px; border-top: 1px solid #f0f4f7; }
.detail-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 12px; }
.detail-field label { display: block; font-size: 11px; color: #8a99a8; margin-bottom: 4px; font-weight: 500; }
.detail-field span { font-size: 13px; color: #3a4a5a; }
.detail-actions { display: flex; gap: 8px; }
.secondary-btn { background: #fff; border: 1px solid #d0d8e0; padding: 6px 12px; border-radius: 6px; font-size: 12px; color: #5a6b7a; cursor: pointer; font-family: inherit; }
.secondary-btn:hover { border-color: #2d6a4f; color: #2d6a4f; }
</style>
