<script setup lang="ts">
import { ref, computed } from 'vue';
import { learningTargets } from '../admin-data';
import { textbooks } from '../data';
import type { LearningTarget } from '../types';

type ViewMode = 'list' | 'detail' | 'wizard';
type WizardStep = 1 | 2 | 3;

const viewMode = ref<ViewMode>('list');
const selectedTarget = ref<LearningTarget | null>(null);
const wizardStep = ref<WizardStep>(1);
const filterTextbook = ref<string>('all');

const filteredTargets = computed(() => {
  if (filterTextbook.value === 'all') return learningTargets;
  return learningTargets.filter(t => t.textbookId === filterTextbook.value);
});

function openTarget(target: LearningTarget) {
  selectedTarget.value = target;
  viewMode.value = 'detail';
}

function backToList() {
  viewMode.value = 'list';
  selectedTarget.value = null;
}

function startWizard() {
  wizardStep.value = 1;
  viewMode.value = 'wizard';
}

const statusConfig: Record<string, { label: string; color: string; bg: string }> = {
  draft: { label: '草稿', color: '#8a99a8', bg: '#f0f4f7' },
  published: { label: '已发布', color: '#2d8a5e', bg: '#e8f5ee' },
  archived: { label: '已归档', color: '#b85c3c', bg: '#fdf0ed' },
};

const enabledDimensionCount = computed(() => {
  if (!selectedTarget.value) return 0;
  return selectedTarget.value.claimConfigs.reduce((sum, c) => sum + c.dimensions.filter(d => d.enabled).length, 0);
});

const totalDimensionCount = computed(() => {
  if (!selectedTarget.value) return 0;
  return selectedTarget.value.claimConfigs.reduce((sum, c) => sum + c.dimensions.length, 0);
});
</script>

<template>
  <div class="target-management">
    <!-- 列表视图 -->
    <template v-if="viewMode === 'list'">
      <div class="page-header">
        <div>
          <h2>目标管理</h2>
          <p class="page-desc">管理预设的 Learning Target，在教材边界内遴选 Task/Solution 并裁剪 Claim 维度</p>
        </div>
        <button class="primary-btn" @click="startWizard">+ 新建目标</button>
      </div>

      <div class="stats-row">
        <div class="stat-card">
          <span class="stat-label">目标总数</span>
          <span class="stat-value">{{ learningTargets.length }}</span>
        </div>
        <div class="stat-card">
          <span class="stat-label">已发布</span>
          <span class="stat-value">{{ learningTargets.filter(t => t.status === 'published').length }}</span>
        </div>
        <div class="stat-card">
          <span class="stat-label">草稿</span>
          <span class="stat-value">{{ learningTargets.filter(t => t.status === 'draft').length }}</span>
        </div>
        <div class="stat-card">
          <span class="stat-label">关联教材</span>
          <span class="stat-value">{{ new Set(learningTargets.map(t => t.textbookId)).size }}</span>
        </div>
      </div>

      <!-- 筛选 -->
      <div class="filter-bar">
        <div class="filter-item">
          <label>教材</label>
          <select v-model="filterTextbook" class="filter-select">
            <option value="all">全部教材</option>
            <option v-for="tb in textbooks" :key="tb.id" :value="tb.id">{{ tb.name }}</option>
          </select>
        </div>
        <span class="filter-result">共 {{ filteredTargets.length }} 个目标</span>
      </div>

      <!-- Target 卡片列表 -->
      <div class="target-grid">
        <div
          v-for="target in filteredTargets"
          :key="target.id"
          class="target-card"
          @click="openTarget(target)"
        >
          <div class="target-header">
            <span class="mono target-id">{{ target.id }}</span>
            <span class="status-tag" :style="{ color: statusConfig[target.status].color, background: statusConfig[target.status].bg }">
              {{ statusConfig[target.status].label }}
            </span>
          </div>
          <h3 class="target-name">{{ target.name }}</h3>
          <p class="target-desc">{{ target.description }}</p>
          <div class="target-meta">
            <span class="meta-item">📚 {{ target.textbookName }}</span>
            <span class="meta-item">🏛️ {{ target.domainName }}</span>
          </div>
          <div class="target-stats">
            <div class="target-stat">
              <span class="stat-num">{{ target.taskCount }}</span>
              <span class="stat-label">遴选 Task</span>
            </div>
            <div class="target-stat">
              <span class="stat-num">{{ target.claimCount }}</span>
              <span class="stat-label">激活 Claim</span>
            </div>
            <div class="target-stat">
              <span class="stat-num">{{ target.chapterCoverage }}</span>
              <span class="stat-label">覆盖章节</span>
            </div>
            <div class="target-stat">
              <span class="stat-num">v{{ target.version }}</span>
              <span class="stat-label">版本</span>
            </div>
          </div>
        </div>
      </div>
    </template>

    <!-- 详情视图 -->
    <template v-else-if="viewMode === 'detail' && selectedTarget">
      <div class="detail-header">
        <button class="back-btn" @click="backToList">← 返回列表</button>
        <div class="detail-title">
          <h2>{{ selectedTarget.name }}</h2>
          <span class="status-tag" :style="{ color: statusConfig[selectedTarget.status].color, background: statusConfig[selectedTarget.status].bg }">
            {{ statusConfig[selectedTarget.status].label }}
          </span>
          <span class="version-tag">v{{ selectedTarget.version }}</span>
        </div>
        <div class="detail-actions">
          <button class="secondary-btn" v-if="selectedTarget.status === 'draft'">发布</button>
          <button class="secondary-btn">编辑</button>
          <button class="secondary-btn">新建版本</button>
        </div>
      </div>

      <div class="detail-desc">{{ selectedTarget.description }}</div>

      <div class="detail-meta-row">
        <div class="meta-card">
          <label>关联教材</label>
          <span>{{ selectedTarget.textbookName }}</span>
        </div>
        <div class="meta-card">
          <label>所属 Domain</label>
          <span>{{ selectedTarget.domainName }}</span>
        </div>
        <div class="meta-card">
          <label>创建时间</label>
          <span>{{ selectedTarget.createdAt }}</span>
        </div>
        <div class="meta-card" v-if="selectedTarget.publishedAt">
          <label>发布时间</label>
          <span>{{ selectedTarget.publishedAt }}</span>
        </div>
      </div>

      <!-- 遴选的 Task -->
      <div class="section-card">
        <h3 class="section-title">遴选的 Task <span class="section-count">{{ selectedTarget.taskCount }} 个</span></h3>
        <table class="data-table">
          <thead>
            <tr>
              <th>Task ID</th>
              <th>Task 名称</th>
              <th>所属章节</th>
              <th>状态</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="task in selectedTarget.selectedTasks" :key="task.taskId">
              <td class="mono">{{ task.taskId }}</td>
              <td class="font-medium">{{ task.taskName }}</td>
              <td>{{ task.chapterRef }}</td>
              <td>
                <span class="status-tag" :style="{ color: '#2d8a5e', background: '#e8f5ee' }">已遴选</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Claim 维度裁剪 -->
      <div class="section-card">
        <h3 class="section-title">
          Claim 维度裁剪
          <span class="section-count">{{ enabledDimensionCount }}/{{ totalDimensionCount }} 维度启用</span>
        </h3>
        <div class="claim-config-list">
          <div v-for="config in selectedTarget.claimConfigs" :key="config.claimId" class="claim-config-item">
            <div class="claim-config-header">
              <span class="mono">{{ config.claimId }}</span>
              <span class="claim-name">{{ config.claimName }}</span>
              <span class="mono task-ref">→ {{ config.taskId }}</span>
            </div>
            <div class="dimension-tags">
              <span
                v-for="dim in config.dimensions"
                :key="dim.dimension"
                class="dim-tag"
                :class="{ disabled: !dim.enabled }"
              >
                {{ dim.label }}
              </span>
            </div>
            <div v-if="config.trimReason" class="trim-reason">
              裁剪说明: {{ config.trimReason }}
            </div>
          </div>
        </div>
      </div>
    </template>

    <!-- 创建向导 -->
    <template v-else-if="viewMode === 'wizard'">
      <div class="wizard-container">
        <div class="wizard-header">
          <button class="back-btn" @click="backToList">← 取消</button>
          <h2>新建学习目标</h2>
        </div>

        <!-- 步骤指示器 -->
        <div class="wizard-steps">
          <div class="step" :class="{ active: wizardStep === 1, done: wizardStep > 1 }">
            <span class="step-num">1</span>
            <span class="step-label">基本信息</span>
          </div>
          <div class="step-line" :class="{ active: wizardStep > 1 }"></div>
          <div class="step" :class="{ active: wizardStep === 2, done: wizardStep > 2 }">
            <span class="step-num">2</span>
            <span class="step-label">遴选 Task</span>
          </div>
          <div class="step-line" :class="{ active: wizardStep > 2 }"></div>
          <div class="step" :class="{ active: wizardStep === 3 }">
            <span class="step-num">3</span>
            <span class="step-label">Claim 维度裁剪</span>
          </div>
        </div>

        <div class="wizard-content">
          <!-- 步骤1: 基本信息 -->
          <div v-if="wizardStep === 1" class="wizard-step">
            <div class="form-group">
              <label>目标名称 *</label>
              <input type="text" class="form-input" placeholder="如：北师大六下数学·基础目标">
            </div>
            <div class="form-group">
              <label>目标描述</label>
              <textarea class="form-textarea" placeholder="描述该目标的范围、深度和适用学生..."></textarea>
            </div>
            <div class="form-row">
              <div class="form-group">
                <label>关联教材 *</label>
                <select class="form-input">
                  <option value="">请选择教材</option>
                  <option v-for="tb in textbooks" :key="tb.id" :value="tb.id">{{ tb.name }}</option>
                </select>
              </div>
              <div class="form-group">
                <label>所属 Domain</label>
                <input type="text" class="form-input" value="数学" disabled>
              </div>
            </div>
          </div>

          <!-- 步骤2: 遴选 Task -->
          <div v-if="wizardStep === 2" class="wizard-step">
            <p class="wizard-hint">在教材关联的 Domain Task 池中，勾选本目标包含的 Task</p>
            <div class="task-select-list">
              <label v-for="i in 6" :key="i" class="task-select-item">
                <input type="checkbox" checked>
                <span class="mono">T-00{{ i }}</span>
                <span class="task-name">示例 Task {{ i }}</span>
                <span class="task-chapter">第二单元</span>
              </label>
            </div>
          </div>

          <!-- 步骤3: Claim 维度裁剪 -->
          <div v-if="wizardStep === 3" class="wizard-step">
            <p class="wizard-hint">系统根据遴选的 Task 自动带出关联的 Claim，可对每个 Claim 裁剪评价维度</p>
            <div class="claim-config-list">
              <div v-for="i in 3" :key="i" class="claim-config-item">
                <div class="claim-config-header">
                  <span class="mono">CL-00{{ i }}</span>
                  <span class="claim-name">示例 Claim {{ i }}</span>
                </div>
                <div class="dimension-toggles">
                  <label v-for="dim in ['独立完成', '理解解释', '迁移应用', '延迟保持']" :key="dim" class="dim-toggle">
                    <input type="checkbox" :checked="dim !== '迁移应用'">
                    <span>{{ dim }}</span>
                  </label>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="wizard-footer">
          <button class="secondary-btn" v-if="wizardStep > 1" @click="wizardStep = (wizardStep - 1) as WizardStep">上一步</button>
          <button class="secondary-btn" @click="backToList">取消</button>
          <button class="primary-btn" v-if="wizardStep < 3" @click="wizardStep = (wizardStep + 1) as WizardStep">下一步</button>
          <button class="primary-btn" v-else @click="backToList">保存为草稿</button>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.target-management { height: 100%; overflow-y: auto; padding: 24px; }
.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px; }
.page-header h2 { margin: 0 0 4px 0; font-size: 20px; color: #1a2a3a; }
.page-desc { margin: 0; font-size: 13px; color: #8a99a8; }
.primary-btn { background: #2d6a4f; color: #fff; border: none; padding: 8px 16px; border-radius: 6px; font-size: 13px; cursor: pointer; font-family: inherit; }
.primary-btn:hover { background: #1b4332; }
.stats-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 16px; }
.stat-card { background: #fff; border-radius: 8px; padding: 16px; border: 1px solid #e8ecf0; }
.stat-label { display: block; font-size: 12px; color: #8a99a8; margin-bottom: 6px; }
.stat-value { font-size: 24px; font-weight: 600; color: #1a2a3a; }
.filter-bar { display: flex; align-items: center; gap: 16px; background: #fff; padding: 12px 16px; border-radius: 8px; border: 1px solid #e8ecf0; margin-bottom: 16px; }
.filter-item { display: flex; align-items: center; gap: 8px; }
.filter-item label { font-size: 13px; color: #5a6b7a; }
.filter-select { padding: 6px 10px; border: 1px solid #d0d8e0; border-radius: 6px; font-size: 13px; font-family: inherit; background: #fff; }
.filter-result { margin-left: auto; font-size: 13px; color: #8a99a8; }
.target-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; }
.target-card { background: #fff; border: 1px solid #e8ecf0; border-radius: 8px; padding: 20px; cursor: pointer; transition: all 0.15s; }
.target-card:hover { border-color: #2d6a4f; box-shadow: 0 2px 8px rgba(45,106,79,0.08); }
.target-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.target-id { font-size: 11px; }
.target-name { margin: 0 0 8px 0; font-size: 16px; font-weight: 600; color: #1a2a3a; }
.target-desc { margin: 0 0 12px 0; font-size: 13px; color: #5a6b7a; line-height: 1.5; min-height: 40px; }
.target-meta { display: flex; gap: 12px; margin-bottom: 14px; font-size: 12px; color: #8a99a8; }
.meta-item { display: flex; align-items: center; gap: 4px; }
.target-stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; padding-top: 14px; border-top: 1px solid #f0f4f7; }
.target-stat { text-align: center; }
.target-stat .stat-num { display: block; font-size: 18px; font-weight: 600; color: #2d6a4f; }
.target-stat .stat-label { display: block; font-size: 11px; color: #8a99a8; margin-top: 2px; }
.mono { font-family: 'SF Mono', 'Consolas', monospace; font-size: 12px; color: #5a6b7a; }
.status-tag { font-size: 11px; padding: 3px 8px; border-radius: 4px; font-weight: 500; }
.detail-header { margin-bottom: 16px; }
.back-btn { background: none; border: none; color: #5a6b7a; cursor: pointer; font-size: 13px; font-family: inherit; padding: 0; margin-bottom: 12px; }
.back-btn:hover { color: #2d6a4f; }
.detail-title { display: flex; align-items: center; gap: 12px; margin-bottom: 8px; }
.detail-title h2 { margin: 0; font-size: 20px; color: #1a2a3a; }
.version-tag { font-size: 12px; background: #eef2f7; color: #5a6b7a; padding: 2px 8px; border-radius: 4px; }
.detail-actions { display: flex; gap: 8px; margin-top: 8px; }
.secondary-btn { background: #fff; border: 1px solid #d0d8e0; padding: 6px 14px; border-radius: 6px; font-size: 13px; color: #5a6b7a; cursor: pointer; font-family: inherit; }
.secondary-btn:hover { border-color: #2d6a4f; color: #2d6a4f; }
.detail-desc { background: #f8fafc; border-radius: 8px; padding: 12px 16px; font-size: 13px; color: #5a6b7a; margin-bottom: 16px; border-left: 3px solid #2d6a4f; }
.detail-meta-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 16px; }
.meta-card { background: #fff; border: 1px solid #e8ecf0; border-radius: 8px; padding: 12px 16px; }
.meta-card label { display: block; font-size: 11px; color: #8a99a8; margin-bottom: 4px; }
.meta-card span { font-size: 13px; color: #3a4a5a; font-weight: 500; }
.section-card { background: #fff; border: 1px solid #e8ecf0; border-radius: 8px; padding: 20px; margin-bottom: 16px; }
.section-title { font-size: 15px; font-weight: 600; color: #1a2a3a; margin: 0 0 16px 0; display: flex; align-items: center; gap: 8px; }
.section-count { font-size: 12px; font-weight: 400; color: #8a99a8; background: #f0f4f7; padding: 2px 8px; border-radius: 10px; }
.data-table { width: 100%; border-collapse: collapse; }
.data-table th { text-align: left; padding: 10px 12px; font-size: 12px; color: #8a99a8; font-weight: 600; background: #f8fafc; border-bottom: 1px solid #e8ecf0; }
.data-table td { padding: 10px 12px; font-size: 13px; color: #3a4a5a; border-bottom: 1px solid #f0f4f7; }
.font-medium { font-weight: 500; }
.claim-config-list { display: flex; flex-direction: column; gap: 12px; }
.claim-config-item { border: 1px solid #e8ecf0; border-radius: 8px; padding: 14px 16px; }
.claim-config-header { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
.claim-name { font-size: 14px; font-weight: 500; color: #1a2a3a; }
.task-ref { font-size: 11px; color: #8a99a8; margin-left: auto; }
.dimension-tags { display: flex; gap: 6px; flex-wrap: wrap; }
.dim-tag { font-size: 11px; padding: 3px 8px; border-radius: 4px; background: #e8f5ee; color: #2d8a5e; font-weight: 500; }
.dim-tag.disabled { background: #f0f4f7; color: #b0b8c0; text-decoration: line-through; }
.trim-reason { margin-top: 8px; font-size: 12px; color: #8a6d3b; background: #fcf8e3; padding: 6px 10px; border-radius: 4px; }
/* 向导样式 */
.wizard-container { max-width: 800px; margin: 0 auto; }
.wizard-header { margin-bottom: 24px; }
.wizard-header h2 { margin: 8px 0 0 0; font-size: 20px; color: #1a2a3a; }
.wizard-steps { display: flex; align-items: center; justify-content: center; margin-bottom: 32px; }
.step { display: flex; flex-direction: column; align-items: center; gap: 6px; }
.step-num { width: 32px; height: 32px; border-radius: 50%; background: #e8ecf0; color: #8a99a8; display: flex; align-items: center; justify-content: center; font-size: 14px; font-weight: 600; }
.step.active .step-num { background: #2d6a4f; color: #fff; }
.step.done .step-num { background: #40916c; color: #fff; }
.step-label { font-size: 12px; color: #8a99a8; }
.step.active .step-label { color: #2d6a4f; font-weight: 500; }
.step-line { width: 80px; height: 2px; background: #e8ecf0; margin: 0 12px; margin-bottom: 22px; }
.step-line.active { background: #40916c; }
.wizard-content { background: #fff; border: 1px solid #e8ecf0; border-radius: 8px; padding: 24px; margin-bottom: 20px; min-height: 300px; }
.wizard-hint { font-size: 13px; color: #5a6b7a; margin: 0 0 16px 0; background: #f0f7f4; padding: 10px 14px; border-radius: 6px; border-left: 3px solid #2d6a4f; }
.form-group { margin-bottom: 16px; }
.form-group label { display: block; font-size: 13px; color: #5a6b7a; margin-bottom: 6px; font-weight: 500; }
.form-input { width: 100%; padding: 8px 12px; border: 1px solid #d0d8e0; border-radius: 6px; font-size: 13px; font-family: inherit; box-sizing: border-box; }
.form-textarea { width: 100%; padding: 8px 12px; border: 1px solid #d0d8e0; border-radius: 6px; font-size: 13px; font-family: inherit; min-height: 80px; box-sizing: border-box; resize: vertical; }
.form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.task-select-list { display: flex; flex-direction: column; gap: 8px; }
.task-select-item { display: flex; align-items: center; gap: 12px; padding: 10px 14px; border: 1px solid #e8ecf0; border-radius: 6px; cursor: pointer; }
.task-select-item:hover { border-color: #2d6a4f; }
.task-select-item .task-name { font-size: 13px; color: #3a4a5a; flex: 1; }
.task-select-item .task-chapter { font-size: 12px; color: #8a99a8; }
.dimension-toggles { display: flex; gap: 16px; flex-wrap: wrap; }
.dim-toggle { display: flex; align-items: center; gap: 6px; font-size: 13px; color: #5a6b7a; cursor: pointer; }
.wizard-footer { display: flex; justify-content: flex-end; gap: 8px; }
</style>
