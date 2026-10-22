<script setup lang="ts">
import { computed } from 'vue';
import type { Span } from '../types';

const props = defineProps<{ span: Span | null }>();

const statusLabel: Record<string, string> = {
  success: '成功',
  failed: '失败',
  partial: '部分成功',
  skipped: '跳过',
  running: '运行中',
};

const statusColor: Record<string, string> = {
  success: '#2d8a5e',
  failed: '#b85c3c',
  partial: '#c9942a',
  skipped: '#9aaab8',
  running: '#4a6fa5',
};

function formatTime(ms: number): string {
  if (ms < 1000) return `${ms.toFixed(0)}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}

function copyText(text: string | undefined) {
  if (text) navigator.clipboard.writeText(text);
}
</script>

<template>
  <div class="span-detail" v-if="span">
    <div class="detail-header">
      <h4>{{ span.label }}</h4>
      <span class="status-badge" :style="{ background: statusColor[span.status] + '20', color: statusColor[span.status] }">
        {{ statusLabel[span.status] }}
      </span>
    </div>

    <div class="detail-meta">
      <div class="meta-item"><span class="meta-label">类型</span><span class="meta-value">{{ span.type }}</span></div>
      <div class="meta-item"><span class="meta-label">Span ID</span><span class="meta-value mono">{{ span.spanId }}</span></div>
      <div class="meta-item"><span class="meta-label">开始</span><span class="meta-value mono">+{{ formatTime(span.startTime) }}</span></div>
      <div class="meta-item"><span class="meta-label">耗时</span><span class="meta-value mono">{{ span.duration > 0 ? formatTime(span.duration) : '—' }}</span></div>
    </div>

    <!-- LLM 调用详情 -->
    <template v-if="span.type === 'llm.invoke'">
      <div class="detail-section">
        <h5>调用信息</h5>
        <div class="meta-grid">
          <div class="meta-item"><span class="meta-label">模型</span><span class="meta-value">{{ span.detail.model }}</span></div>
          <div class="meta-item"><span class="meta-label">温度</span><span class="meta-value">{{ span.detail.temperature }}</span></div>
          <div class="meta-item"><span class="meta-label">输入Token</span><span class="meta-value">{{ span.detail.inputTokens }}</span></div>
          <div class="meta-item"><span class="meta-label">输出Token</span><span class="meta-value">{{ span.detail.outputTokens }}</span></div>
        </div>
      </div>
      <div class="detail-section">
        <h5>Prompt <button class="copy-btn" @click="copyText(span.detail.prompt)">复制</button></h5>
        <pre class="code-block">{{ span.detail.prompt }}</pre>
      </div>
      <div class="detail-section">
        <h5>Response <button class="copy-btn" @click="copyText(span.detail.response)">复制</button></h5>
        <pre class="code-block">{{ span.detail.response }}</pre>
      </div>
    </template>

    <!-- Observation 生成 -->
    <template v-else-if="span.type === 'observation.generate'">
      <div class="detail-section">
        <h5>Candidate 信息</h5>
        <div class="meta-grid">
          <div class="meta-item"><span class="meta-label">Candidate ID</span><span class="meta-value mono">{{ span.detail.candidateId }}</span></div>
          <div class="meta-item"><span class="meta-label">类型</span><span class="meta-value">{{ span.detail.candidateType }}</span></div>
        </div>
      </div>
      <div class="detail-section" v-if="span.detail.candidateJson">
        <h5>Candidate 完整内容</h5>
        <pre class="code-block json">{{ span.detail.candidateJson }}</pre>
      </div>
    </template>

    <!-- Observation 验证 -->
    <template v-else-if="span.type === 'observation.validate'">
      <div class="detail-section">
        <h5>规则检查结果</h5>
        <div v-for="rule in span.detail.validationRules" :key="rule.ruleId" class="rule-item" :class="{ fail: !rule.passed }">
          <span class="rule-icon">{{ rule.passed ? '✓' : '✗' }}</span>
          <div class="rule-content">
            <span class="rule-name">{{ rule.ruleId }} {{ rule.ruleName }}</span>
            <span class="rule-detail">{{ rule.detail }}</span>
          </div>
        </div>
      </div>
      <div class="detail-section rejection" v-if="span.detail.rejectionReason">
        <h5>拒绝原因</h5>
        <p class="rejection-text">{{ span.detail.rejectionReason }}</p>
      </div>
    </template>

    <!-- Observation Commit -->
    <template v-else-if="span.type === 'observation.commit'">
      <div class="detail-section">
        <h5>Commit 决策</h5>
        <div class="meta-grid">
          <div class="meta-item"><span class="meta-label">Authority</span><span class="meta-value">{{ span.detail.commitAuthority }}</span></div>
          <div class="meta-item"><span class="meta-label">Standing</span><span class="meta-value" :style="{color: statusColor[span.status]}">{{ span.detail.standing }}</span></div>
        </div>
      </div>
    </template>

    <!-- Policy 决策 -->
    <template v-else-if="span.type === 'policy.evaluate'">
      <div class="detail-section">
        <h5>输入 Observation</h5>
        <div class="tag-list">
          <span v-for="ref in span.detail.inputObservationRefs" :key="ref" class="tag">{{ ref }}</span>
        </div>
      </div>
      <div class="detail-section">
        <h5>候选 Action 评分</h5>
        <div v-for="act in span.detail.candidateActions" :key="act.actionId" class="action-item" :class="{ selected: act.selected }">
          <div class="action-header">
            <span class="action-name">{{ act.label }}</span>
            <span class="action-score">{{ act.score.toFixed(2) }}</span>
            <span v-if="act.selected" class="selected-badge">已选择</span>
          </div>
          <p class="action-reason" v-if="act.reason">{{ act.reason }}</p>
        </div>
      </div>
      <div class="detail-section" v-if="span.detail.decisionBasis">
        <h5>决策依据</h5>
        <p class="basis-text">{{ span.detail.decisionBasis }}</p>
      </div>
    </template>

    <!-- Action 执行 -->
    <template v-else-if="span.type === 'action.execute'">
      <div class="detail-section">
        <h5>Action 信息</h5>
        <div class="meta-grid">
          <div class="meta-item"><span class="meta-label">类型</span><span class="meta-value">{{ span.detail.actionType }}</span></div>
          <div class="meta-item"><span class="meta-label">结果</span><span class="meta-value">{{ span.detail.actionResult }}</span></div>
        </div>
      </div>
      <div class="detail-section" v-if="span.detail.actionPayload">
        <h5>Payload</h5>
        <pre class="code-block json">{{ span.detail.actionPayload }}</pre>
      </div>
    </template>

    <!-- Evidence 解释 -->
    <template v-else-if="span.type === 'evidence.interpret'">
      <div class="detail-section">
        <h5>Evidence 信息</h5>
        <div class="meta-grid">
          <div class="meta-item"><span class="meta-label">Claim</span><span class="meta-value mono">{{ span.detail.claimId }}</span></div>
          <div class="meta-item"><span class="meta-label">关联 Observation</span><span class="meta-value mono">{{ span.detail.observationRef }}</span></div>
          <div class="meta-item"><span class="meta-label">证据强度</span><span class="meta-value">{{ span.detail.evidenceStrength }}</span></div>
        </div>
      </div>
      <div class="detail-section" v-if="span.detail.interpretation">
        <h5>解释</h5>
        <p class="basis-text">{{ span.detail.interpretation }}</p>
      </div>
    </template>

    <!-- Belief 更新 -->
    <template v-else-if="span.type === 'belief.infer'">
      <div class="detail-section">
        <h5>Belief 更新</h5>
        <div class="meta-grid">
          <div class="meta-item"><span class="meta-label">Claim</span><span class="meta-value mono">{{ span.detail.claimId }}</span></div>
          <div class="meta-item"><span class="meta-label">算法</span><span class="meta-value">{{ span.detail.algorithm }}</span></div>
          <div class="meta-item"><span class="meta-label">先验</span><span class="meta-value">{{ (span.detail.priorBelief! * 100).toFixed(0) }}%</span></div>
          <div class="meta-item"><span class="meta-label">后验</span><span class="meta-value">{{ (span.detail.posteriorBelief! * 100).toFixed(0) }}%</span></div>
          <div class="meta-item"><span class="meta-label">变化</span><span class="meta-value" :style="{color: span.detail.beliefChange! < 0 ? '#b85c3c' : '#2d8a5e'}">
            {{ span.detail.beliefChange! >= 0 ? '+' : '' }}{{ (span.detail.beliefChange! * 100).toFixed(1) }}%
          </span></div>
        </div>
      </div>
      <div class="detail-section" v-if="span.detail.evidenceRefs?.length">
        <h5>使用的 Evidence</h5>
        <div class="tag-list">
          <span v-for="ref in span.detail.evidenceRefs" :key="ref" class="tag">{{ ref }}</span>
        </div>
      </div>
    </template>

    <!-- Turn start/end -->
    <template v-else>
      <div class="detail-section" v-if="span.detail.actionResult">
        <h5>结果</h5>
        <p class="basis-text">{{ span.detail.actionResult }}</p>
      </div>
      <div class="detail-section" v-if="span.detail.actionPayload">
        <h5>内容</h5>
        <p class="basis-text">{{ span.detail.actionPayload }}</p>
      </div>
    </template>
  </div>

  <div class="span-detail empty" v-else>
    <p>点击左侧瀑布图中的 Span 查看详情</p>
  </div>
</template>

<style scoped>
.span-detail { height: 100%; overflow-y: auto; padding: 16px; }
.span-detail.empty { display: flex; align-items: center; justify-content: center; color: #8a99a8; font-size: 13px; }
.detail-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; padding-bottom: 10px; border-bottom: 1px solid #e1e8ed; }
.detail-header h4 { margin: 0; font-size: 14px; color: #1a3a2e; }
.status-badge { padding: 3px 10px; border-radius: 10px; font-size: 11px; font-weight: 600; }
.detail-meta { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 16px; }
.meta-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.meta-item { display: flex; flex-direction: column; gap: 2px; }
.meta-label { font-size: 10px; color: #8a99a8; text-transform: uppercase; }
.meta-value { font-size: 12px; color: #2c3e50; }
.meta-value.mono { font-family: Consolas, Monaco, monospace; font-size: 11px; }
.detail-section { margin-bottom: 16px; }
.detail-section h5 { margin: 0 0 8px 0; font-size: 12px; color: #5a6b7a; font-weight: 600; display: flex; align-items: center; gap: 8px; }
.copy-btn { background: none; border: 1px solid #d0d7de; color: #5a6b7a; padding: 1px 8px; border-radius: 4px; font-size: 10px; cursor: pointer; font-family: inherit; }
.copy-btn:hover { background: #f0f4f7; }
.code-block { background: #1e293b; color: #e2e8f0; padding: 12px; border-radius: 6px; font-size: 11px; line-height: 1.6; overflow-x: auto; margin: 0; white-space: pre-wrap; word-break: break-all; max-height: 300px; overflow-y: auto; }
.code-block.json { color: #a5d6a7; }
.rule-item { display: flex; gap: 8px; padding: 8px; border-radius: 6px; margin-bottom: 6px; background: #f5f9f7; }
.rule-item.fail { background: #fdf0ed; }
.rule-icon { font-weight: 700; color: #2d8a5e; flex-shrink: 0; width: 16px; }
.rule-item.fail .rule-icon { color: #b85c3c; }
.rule-content { display: flex; flex-direction: column; gap: 2px; }
.rule-name { font-size: 12px; font-weight: 600; color: #2c3e50; }
.rule-detail { font-size: 11px; color: #6a7a8a; }
.detail-section.rejection { background: #fdf0ed; border-radius: 8px; padding: 12px; }
.detail-section.rejection h5 { color: #b85c3c; }
.rejection-text { margin: 0; font-size: 12px; line-height: 1.7; color: #7a3a2a; }
.tag-list { display: flex; flex-wrap: wrap; gap: 6px; }
.tag { background: #e8f0f8; color: #3a5a7a; padding: 3px 8px; border-radius: 4px; font-size: 11px; font-family: Consolas, Monaco, monospace; }
.action-item { padding: 10px; border-radius: 8px; margin-bottom: 8px; border: 1px solid #e1e8ed; }
.action-item.selected { border-color: #2d6a4f; background: #f0f7f3; }
.action-header { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
.action-name { font-size: 12px; font-weight: 600; color: #2c3e50; flex: 1; }
.action-score { font-size: 13px; font-weight: 700; color: #2d6a4f; font-variant-numeric: tabular-nums; }
.selected-badge { background: #2d6a4f; color: white; padding: 2px 8px; border-radius: 8px; font-size: 10px; font-weight: 600; }
.action-reason { margin: 0; font-size: 11px; color: #6a7a8a; line-height: 1.5; }
.basis-text { margin: 0; font-size: 12px; line-height: 1.7; color: #3a4a5a; background: #f7f9fa; padding: 10px; border-radius: 6px; }
</style>
