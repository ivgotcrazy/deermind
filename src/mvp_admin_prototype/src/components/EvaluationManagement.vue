<script setup lang="ts">
import { ref, computed } from 'vue';
import { taskClaims } from '../admin-data';
import type { TaskClaim, ClaimDimensionConfig } from '../types';

type ViewMode = 'list' | 'detail';

const viewMode = ref<ViewMode>('list');
const selectedClaim = ref<TaskClaim | null>(null);
const filterDomain = ref<string>('all');
const filterStatus = ref<string>('all');

const domains = computed(() => [...new Set(taskClaims.map(c => c.domainName))]);

const filteredClaims = computed(() => {
  return taskClaims.filter(c => {
    if (filterDomain.value !== 'all' && c.domainName !== filterDomain.value) return false;
    if (filterStatus.value !== 'all' && c.status !== filterStatus.value) return false;
    return true;
  });
});

function openClaim(claim: TaskClaim) {
  selectedClaim.value = claim;
  viewMode.value = 'detail';
}

function backToList() {
  viewMode.value = 'list';
  selectedClaim.value = null;
}

const statusConfig: Record<string, { label: string; color: string; bg: string }> = {
  active: { label: '已启用', color: '#2d8a5e', bg: '#e8f5ee' },
  draft: { label: '草稿', color: '#8a99a8', bg: '#f0f4f7' },
  archived: { label: '已归档', color: '#b85c3c', bg: '#fdf0ed' },
};

const dimensionConfig: Record<string, { label: string; icon: string }> = {
  independent: { label: '独立完成', icon: '✓' },
  understanding: { label: '理解解释', icon: '💡' },
  transfer: { label: '迁移应用', icon: '🔄' },
  retention: { label: '延迟保持', icon: '⏳' },
};

const enabledDimensions = computed(() => selectedClaim.value?.dimensions.filter(d => d.enabled) || []);
const disabledDimensions = computed(() => selectedClaim.value?.dimensions.filter(d => !d.enabled) || []);
</script>

<template>
  <div class="evaluation-management">
    <!-- 列表视图 -->
    <template v-if="viewMode === 'list'">
      <div class="page-header">
        <div>
          <h2>评估模型管理</h2>
          <p class="page-desc">管理 Evaluation Space 中的 TaskClaim 能力命题，配置四维评估和证据映射规则</p>
        </div>
        <button class="primary-btn">+ 新建 Claim</button>
      </div>

      <div class="stats-row">
        <div class="stat-card">
          <span class="stat-label">Claim 总数</span>
          <span class="stat-value">{{ taskClaims.length }}</span>
        </div>
        <div class="stat-card">
          <span class="stat-label">已启用</span>
          <span class="stat-value">{{ taskClaims.filter(c => c.status === 'active').length }}</span>
        </div>
        <div class="stat-card">
          <span class="stat-label">草稿</span>
          <span class="stat-value">{{ taskClaims.filter(c => c.status === 'draft').length }}</span>
        </div>
        <div class="stat-card">
          <span class="stat-label">关联 Task</span>
          <span class="stat-value">{{ taskClaims.length }}</span>
        </div>
      </div>

      <!-- 筛选栏 -->
      <div class="filter-bar">
        <div class="filter-item">
          <label>领域</label>
          <select v-model="filterDomain" class="filter-select">
            <option value="all">全部领域</option>
            <option v-for="d in domains" :key="d" :value="d">{{ d }}</option>
          </select>
        </div>
        <div class="filter-item">
          <label>状态</label>
          <select v-model="filterStatus" class="filter-select">
            <option value="all">全部状态</option>
            <option value="active">已启用</option>
            <option value="draft">草稿</option>
            <option value="archived">已归档</option>
          </select>
        </div>
        <span class="filter-result">共 {{ filteredClaims.length }} 条</span>
      </div>

      <!-- Claim 列表 -->
      <div class="claim-list">
        <div
          v-for="claim in filteredClaims"
          :key="claim.id"
          class="claim-card"
          @click="openClaim(claim)"
        >
          <div class="claim-header">
            <div class="claim-title">
              <span class="mono claim-id">{{ claim.id }}</span>
              <span class="claim-name">{{ claim.name }}</span>
              <span class="status-tag" :style="{ color: statusConfig[claim.status].color, background: statusConfig[claim.status].bg }">
                {{ statusConfig[claim.status].label }}
              </span>
            </div>
            <span class="claim-version">v{{ claim.version }}</span>
          </div>
          <div class="claim-desc">{{ claim.description }}</div>
          <div class="claim-meta">
            <span class="meta-item">🏛️ {{ claim.domainName }}</span>
            <span class="meta-item">📋 关联 Task: {{ claim.taskName }} ({{ claim.taskId }})</span>
            <span class="meta-item">📐 {{ claim.dimensions.filter(d => d.enabled).length }}/4 维度启用</span>
            <span class="meta-item">🔗 {{ claim.evidenceRules.length }} 条证据规则</span>
          </div>
          <div class="claim-dimensions">
            <span
              v-for="dim in claim.dimensions"
              :key="dim.dimension"
              class="dim-badge"
              :class="{ disabled: !dim.enabled }"
              :title="dim.enabled ? dim.criteria : '未启用'"
            >
              {{ dimensionConfig[dim.dimension]?.icon }} {{ dimensionConfig[dim.dimension]?.label }}
            </span>
          </div>
        </div>
      </div>
    </template>

    <!-- 详情视图 -->
    <template v-else-if="selectedClaim">
      <div class="detail-header">
        <button class="back-btn" @click="backToList">← 返回列表</button>
        <div class="detail-title">
          <h2>{{ selectedClaim.name }}</h2>
          <span class="status-tag" :style="{ color: statusConfig[selectedClaim.status].color, background: statusConfig[selectedClaim.status].bg }">
            {{ statusConfig[selectedClaim.status].label }}
          </span>
          <span class="version-tag">v{{ selectedClaim.version }}</span>
        </div>
        <div class="detail-actions">
          <button class="secondary-btn">编辑</button>
          <button class="secondary-btn">新建版本</button>
        </div>
      </div>

      <!-- 基本信息 -->
      <div class="section-card">
        <h3 class="section-title">基本信息</h3>
        <div class="info-grid">
          <div class="info-field"><label>Claim ID</label><span class="mono">{{ selectedClaim.id }}</span></div>
          <div class="info-field"><label>所属领域</label><span>{{ selectedClaim.domainName }}</span></div>
          <div class="info-field"><label>关联 Task</label><span>{{ selectedClaim.taskName }} ({{ selectedClaim.taskId }})</span></div>
          <div class="info-field"><label>最后更新</label><span>{{ selectedClaim.updatedAt }}</span></div>
        </div>
        <div class="info-full">
          <label>描述</label>
          <p>{{ selectedClaim.description }}</p>
        </div>
        <div class="info-grid">
          <div class="info-field"><label>TaskScope</label><span>{{ selectedClaim.taskScope }}</span></div>
          <div class="info-field"><label>认知责任</label><span>{{ selectedClaim.responsibility }}</span></div>
          <div class="info-field"><label>方法要求</label><span>{{ selectedClaim.methodRequirement }}</span></div>
          <div class="info-field"><label>适用条件</label><span>{{ selectedClaim.conditions }}</span></div>
          <div class="info-field"><label>支持边界</label><span>{{ selectedClaim.supportBoundary }}</span></div>
          <div class="info-field"><label>质量要求</label><span>{{ selectedClaim.qualityRequirement }}</span></div>
        </div>
      </div>

      <!-- 四维配置 -->
      <div class="section-card">
        <h3 class="section-title">四维评估配置</h3>
        <div class="dimension-list">
          <div
            v-for="dim in selectedClaim.dimensions"
            :key="dim.dimension"
            class="dimension-card"
            :class="{ disabled: !dim.enabled }"
          >
            <div class="dim-header">
              <span class="dim-icon">{{ dimensionConfig[dim.dimension]?.icon }}</span>
              <span class="dim-label">{{ dimensionConfig[dim.dimension]?.label }}</span>
              <span class="dim-status" :class="{ on: dim.enabled, off: !dim.enabled }">
                {{ dim.enabled ? '已启用' : '未启用' }}
              </span>
            </div>
            <div class="dim-detail">
              <div class="dim-row"><label>评价细则</label><span>{{ dim.criteria }}</span></div>
              <div class="dim-row"><label>证据要求</label><span>{{ dim.evidenceRequirement }}</span></div>
            </div>
          </div>
        </div>
      </div>

      <!-- 证据映射规则 -->
      <div class="section-card">
        <h3 class="section-title">证据映射规则 <span class="section-count">{{ selectedClaim.evidenceRules.length }} 条</span></h3>
        <table class="rule-table">
          <thead>
            <tr>
              <th>规则ID</th>
              <th>维度</th>
              <th>观测类型</th>
              <th>极性</th>
              <th>条件</th>
              <th>说明</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="rule in selectedClaim.evidenceRules" :key="rule.id">
              <td class="mono">{{ rule.id }}</td>
              <td>{{ dimensionConfig[rule.dimension]?.label }}</td>
              <td><code>{{ rule.observationType }}</code></td>
              <td>
                <span class="polarity-tag" :class="rule.polarity">
                  {{ rule.polarity === 'positive' ? '正向' : rule.polarity === 'negative' ? '反向' : '非信息性' }}
                </span>
              </td>
              <td>{{ rule.condition }}</td>
              <td>{{ rule.description }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </div>
</template>

<style scoped>
.evaluation-management { height: 100%; overflow-y: auto; padding: 24px; }
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
.claim-list { display: flex; flex-direction: column; gap: 10px; }
.claim-card { background: #fff; border: 1px solid #e8ecf0; border-radius: 8px; padding: 16px; cursor: pointer; transition: all 0.15s; }
.claim-card:hover { border-color: #2d6a4f; box-shadow: 0 2px 8px rgba(45,106,79,0.08); }
.claim-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.claim-title { display: flex; align-items: center; gap: 10px; }
.claim-id { font-size: 11px; }
.claim-name { font-size: 15px; font-weight: 500; color: #1a2a3a; }
.claim-version { font-size: 12px; color: #8a99a8; }
.claim-desc { font-size: 13px; color: #5a6b7a; margin-bottom: 10px; }
.claim-meta { display: flex; gap: 16px; font-size: 12px; color: #8a99a8; margin-bottom: 10px; flex-wrap: wrap; }
.meta-item { display: flex; align-items: center; gap: 4px; }
.claim-dimensions { display: flex; gap: 6px; }
.dim-badge { font-size: 11px; padding: 3px 8px; border-radius: 4px; background: #e8f5ee; color: #2d8a5e; font-weight: 500; }
.dim-badge.disabled { background: #f0f4f7; color: #b0b8c0; }
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
.section-card { background: #fff; border: 1px solid #e8ecf0; border-radius: 8px; padding: 20px; margin-bottom: 16px; }
.section-title { font-size: 15px; font-weight: 600; color: #1a2a3a; margin: 0 0 16px 0; display: flex; align-items: center; gap: 8px; }
.section-count { font-size: 12px; font-weight: 400; color: #8a99a8; background: #f0f4f7; padding: 2px 8px; border-radius: 10px; }
.info-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px 24px; margin-bottom: 12px; }
.info-field label { display: block; font-size: 11px; color: #8a99a8; margin-bottom: 4px; font-weight: 500; }
.info-field span { font-size: 13px; color: #3a4a5a; }
.info-full { margin-bottom: 12px; }
.info-full label { display: block; font-size: 11px; color: #8a99a8; margin-bottom: 4px; font-weight: 500; }
.info-full p { margin: 0; font-size: 13px; color: #3a4a5a; line-height: 1.6; }
.dimension-list { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.dimension-card { border: 1px solid #e8ecf0; border-radius: 8px; padding: 14px; }
.dimension-card.disabled { opacity: 0.5; background: #fafbfc; }
.dim-header { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; }
.dim-icon { font-size: 16px; }
.dim-label { font-size: 14px; font-weight: 500; color: #1a2a3a; flex: 1; }
.dim-status { font-size: 11px; padding: 2px 8px; border-radius: 4px; font-weight: 500; }
.dim-status.on { background: #e8f5ee; color: #2d8a5e; }
.dim-status.off { background: #f0f4f7; color: #8a99a8; }
.dim-detail { display: flex; flex-direction: column; gap: 6px; }
.dim-row { display: flex; gap: 8px; font-size: 12px; }
.dim-row label { color: #8a99a8; min-width: 60px; flex-shrink: 0; }
.dim-row span { color: #5a6b7a; }
.rule-table { width: 100%; border-collapse: collapse; }
.rule-table th { text-align: left; padding: 10px 12px; font-size: 12px; color: #8a99a8; font-weight: 600; background: #f8fafc; border-bottom: 1px solid #e8ecf0; }
.rule-table td { padding: 10px 12px; font-size: 13px; color: #3a4a5a; border-bottom: 1px solid #f0f4f7; }
.rule-table code { background: #f0f4f7; padding: 2px 6px; border-radius: 4px; font-size: 12px; color: #5a6b7a; }
.polarity-tag { font-size: 11px; padding: 2px 8px; border-radius: 4px; font-weight: 500; }
.polarity-tag.positive { background: #e8f5ee; color: #2d8a5e; }
.polarity-tag.negative { background: #fdf0ed; color: #b85c3c; }
.polarity-tag.non-informative { background: #f0f4f7; color: #8a99a8; }
</style>
