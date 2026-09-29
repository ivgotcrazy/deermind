<script setup lang="ts">
import { computed, ref } from 'vue'
import { useEvidenceStore } from '@/stores/evidence'
import { DEMO_NOTE, EVIDENCE_TYPE_LABEL, type Concept } from '@/data/sharedMock'
import StateBadge from '@/components/admin/StateBadge.vue'

const ev = useEvidenceStore()
const selectedId = ref(ev.concepts[0]?.id ?? '')

const selected = computed<Concept | undefined>(() => ev.findConcept(selectedId.value))
const selectedSnapshot = computed(() => ev.snapshotOf(selectedId.value))
const prereqNames = computed(() =>
  (selected.value?.prerequisites ?? []).map((p) => ev.findConcept(p)?.name ?? p).join('、'),
)
const kpEvidence = computed(() => ev.evidencesOf(selectedId.value).slice(-10).reverse())
const kpDecisions = computed(() =>
  ev.decisions.filter((d) => d.kpId === selectedId.value).slice(-4).reverse(),
)

/* 演示：政策评估（候选动作评分 + 选中 + 为什么）——算法见系统设计 */
const policy = computed(() => {
  const sn = selectedSnapshot.value
  if (!sn) return null
  const candidates = [
    { action: 'VERIFY', label: '检验 / 验证', score: 0, why: '验证即时掌握' },
    { action: 'EXPLAIN', label: '讲解', score: 0, why: '补概念缺口' },
    { action: 'REVIEW', label: '间隔复习', score: 0, why: '验证延迟保持' },
    { action: 'STOP', label: '停止 / 减负', score: 0, why: '已无高价值动作' },
  ]
  let selectedAction = 'VERIFY'
  let missing = '—'
  const evs = ev.evidencesOf(sn.conceptId)
  if (sn.status === 'stable') {
    candidates[0].score = 0.2
    candidates[1].score = 0.05
    candidates[2].score = 0.25
    candidates[3].score = 0.95
    selectedAction = 'STOP'
    missing = '证据充分（含迁移/复习/延迟），近期无强反证 → 默认静默'
  } else if (sn.status === 'short') {
    candidates[0].score = 0.82
    candidates[1].score = 0.2
    candidates[2].score = 0.51
    candidates[3].score = 0.42
    selectedAction = 'VERIFY'
    missing = evs.some((e) => e.type === 'migration')
      ? '已含迁移证据，但缺延迟独立检索 → 安排间隔复习'
      : '短期掌握已确认，缺高价值迁移（跨题型）证据 → 验证稳定性'
  } else if (sn.status === 'learning') {
    const hasNeg = sn.lastNegativeAt !== ''
    candidates[0].score = 0.6
    candidates[1].score = hasNeg ? 0.68 : 0.36
    candidates[2].score = 0.3
    candidates[3].score = 0.1
    selectedAction = hasNeg ? 'EXPLAIN' : 'VERIFY'
    missing = evs.some((e) => e.type === 'variant')
      ? '已有部分证据，缺变式/迁移确认'
      : '缺变式（即时迁移）通过证据'
  } else {
    candidates[0].score = 0.1
    candidates[1].score = 0.1
    candidates[2].score = 0.05
    candidates[3].score = 0.3
    selectedAction = 'STOP'
    missing = 'UNKNOWN：无足够证据，默认静默等待反证（错题/求助/检验失败）'
  }
  return { candidates, selectedAction, missing }
})
</script>

<template>
  <div class="kpage">
    <div class="page-head">
      <h1>知识点详情 · Concept Decision Inspector</h1>
      <p class="desc">为什么系统这么判断？当前状态 → 证据 → 政策候选 → 决策（{{ DEMO_NOTE }}）</p>
    </div>

    <div class="grid">
      <!-- 知识点列表 -->
      <section class="panel">
        <div class="panel-title">知识点（{{ ev.concepts.length }}）</div>
        <table class="tbl">
          <thead>
            <tr>
              <th>名称</th>
              <th>状态</th>
              <th class="num">估计</th>
              <th class="num">置信</th>
              <th class="num">稳定</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="c in ev.concepts"
              :key="c.id"
              :class="{ on: selectedId === c.id }"
              @click="selectedId = c.id"
            >
              <td class="kp-name">{{ c.name }}</td>
              <td><StateBadge :state="ev.snapshotOf(c.id)?.status ?? 'unknown'" /></td>
              <td class="num">{{ ev.snapshotOf(c.id)?.estimate ?? 0 }}</td>
              <td class="num">{{ ((ev.snapshotOf(c.id)?.confidence ?? 0) * 100).toFixed(0) }}%</td>
              <td class="num">{{ ((ev.snapshotOf(c.id)?.stability ?? 0) * 100).toFixed(0) }}%</td>
            </tr>
          </tbody>
        </table>
      </section>

      <!-- 决策检查器 -->
      <section v-if="selected && selectedSnapshot && policy" class="panel detail">
        <div class="d-head">
          <span class="d-name">{{ selected.name }}</span>
          <StateBadge :state="selectedSnapshot.status" />
        </div>
        <div class="d-meta">
          领域：{{ selected.domain }} · {{ selected.important ? '重要' : '一般' }} · 前置：{{ prereqNames || '无' }} · 追踪：{{ ev.isTracked(selected.id) ? '是' : '否（UNKNOWN 静默）' }}
        </div>

        <!-- ① 当前掌握 -->
        <div class="sec">Current Mastery</div>
        <div class="d-nums">
          <div class="d-num"><span class="l">估计掌握</span><span class="v">{{ selectedSnapshot.estimate }}</span></div>
          <div class="d-num"><span class="l">置信度</span><span class="v">{{ (selectedSnapshot.confidence * 100).toFixed(0) }}%</span></div>
          <div class="d-num"><span class="l">稳定度</span><span class="v">{{ (selectedSnapshot.stability * 100).toFixed(0) }}%</span></div>
        </div>
        <div class="d-meta">
          证据 {{ selectedSnapshot.evidenceCount }} 条 · 最近正向 {{ selectedSnapshot.lastPositiveAt || '—' }} · 最近负向 {{ selectedSnapshot.lastNegativeAt || '—' }} · 下次复习 {{ selectedSnapshot.nextReviewAt }}
        </div>

        <!-- ② 证据时间线 -->
        <div class="sec">Evidence Timeline（{{ kpEvidence.length }}）</div>
        <ul class="tl">
          <li v-for="e in kpEvidence" :key="e.id" class="tl-item">
            <span class="t">{{ e.time }}</span>
            <div class="tl-body">
              <span class="etype" :class="e.polarity">{{ EVIDENCE_TYPE_LABEL[e.type] }} · {{ e.polarity === 'positive' ? '通过' : '未通过' }}</span>
              <span class="w">信息值 {{ e.informationValue.toFixed(2) }}</span>
              <div class="note">{{ e.note }}（{{ e.source }}）</div>
            </div>
          </li>
          <li v-if="!kpEvidence.length" class="muted">暂无证据（UNKNOWN，静默）</li>
        </ul>

        <!-- ③ 政策评估 -->
        <div class="sec">Policy Evaluation（候选动作 · 演示评分）</div>
        <ul class="pol">
          <li
            v-for="cd in policy.candidates"
            :key="cd.action"
            class="pol-item"
            :class="{ sel: cd.action === policy.selectedAction }"
          >
            <span class="pol-act">{{ cd.action }} <em>{{ cd.label }}</em></span>
            <div class="pol-bar">
              <div class="pol-fill" :style="{ width: cd.score * 100 + '%' }"></div>
            </div>
            <span class="pol-score">{{ cd.score.toFixed(2) }}</span>
          </li>
        </ul>
        <div class="why">
          <span class="why-tag">为什么 → {{ policy.selectedAction }}</span>
          <p>{{ policy.missing }}</p>
        </div>

        <!-- ④ 决策理由 -->
        <div class="sec">Decision Reason（可解释性）</div>
        <ul class="tl">
          <li v-for="d in kpDecisions" :key="d.id" class="tl-item">
            <span class="t">{{ d.time }}</span>
            <div class="tl-body">
              <div class="dr-action">{{ d.action }}</div>
              <div class="dr-reason">{{ d.reason }}</div>
            </div>
          </li>
          <li v-if="!kpDecisions.length" class="muted">暂无决策</li>
        </ul>
      </section>
    </div>
  </div>
</template>

<style scoped>
.kpage {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.page-head h1 {
  margin: 0;
  font-size: 20px;
}
.page-head .desc {
  margin: 4px 0 0;
  font-size: 12.5px;
  color: #64748b;
}
.grid {
  display: grid;
  grid-template-columns: minmax(340px, 0.8fr) 1.2fr;
  gap: 12px;
  align-items: start;
}
@media (max-width: 900px) {
  .grid {
    grid-template-columns: 1fr;
  }
}
.panel {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 14px 16px;
}
.panel-title {
  font-size: 13px;
  font-weight: 700;
  color: #334155;
  margin-bottom: 10px;
}
.tbl {
  width: 100%;
  border-collapse: collapse;
}
.tbl th {
  font-size: 12px;
  font-weight: 600;
  color: #64748b;
  text-align: left;
  padding: 6px 8px;
  border-bottom: 1px solid #e2e8f0;
}
.tbl th.num,
.tbl td.num {
  text-align: right;
}
.tbl td {
  font-size: 13px;
  padding: 8px;
  border-bottom: 1px solid #f1f5f9;
  cursor: pointer;
  font-variant-numeric: tabular-nums;
}
.tbl tr:hover td {
  background: #f8fafc;
}
.tbl tr.on td {
  background: #eef2ff;
}
.kp-name {
  font-weight: 600;
}
.detail {
  position: sticky;
  top: 0;
}
.d-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.d-name {
  font-size: 17px;
  font-weight: 800;
}
.d-meta {
  font-size: 12.5px;
  color: #64748b;
  margin-top: 4px;
  line-height: 1.6;
}
.d-nums {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  margin: 10px 0;
}
.d-num {
  background: #f8fafc;
  border-radius: 8px;
  padding: 10px;
  text-align: center;
}
.d-num .l {
  display: block;
  font-size: 11px;
  color: #64748b;
}
.d-num .v {
  font-size: 20px;
  font-weight: 800;
  font-variant-numeric: tabular-nums;
}
.sec {
  font-size: 13px;
  font-weight: 700;
  color: #334155;
  margin: 14px 0 8px;
  border-top: 1px solid #eef2ff;
  padding-top: 12px;
}
.tl {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.tl-item {
  display: flex;
  gap: 10px;
}
.tl-item .t {
  font-size: 12px;
  font-weight: 700;
  color: var(--color-primary);
  flex-shrink: 0;
  padding-top: 2px;
}
.tl-body {
  flex: 1;
  border-left: 2px solid #eef2ff;
  padding-left: 10px;
}
.etype {
  font-size: 11px;
  font-weight: 700;
  padding: 1px 8px;
  border-radius: 999px;
}
.etype.positive {
  background: #dcfce7;
  color: #15803d;
}
.etype.negative {
  background: #fee2e2;
  color: #b91c1c;
}
.w {
  font-size: 11px;
  color: #94a3b8;
  margin-left: 6px;
}
.note {
  font-size: 12.5px;
  color: #475569;
  margin-top: 2px;
}
.pol {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.pol-item {
  display: flex;
  align-items: center;
  gap: 10px;
}
.pol-act {
  width: 110px;
  font-size: 12.5px;
  font-weight: 700;
  flex-shrink: 0;
}
.pol-act em {
  font-style: normal;
  font-weight: 400;
  color: #64748b;
  font-size: 11px;
  margin-left: 4px;
}
.pol-bar {
  flex: 1;
  height: 10px;
  background: #f1f5f9;
  border-radius: 999px;
  overflow: hidden;
}
.pol-fill {
  height: 100%;
  border-radius: 999px;
  background: #cbd5e1;
}
.pol-item.sel .pol-fill {
  background: var(--color-primary);
}
.pol-item.sel {
  background: #eef2ff;
  border-radius: 6px;
  padding: 3px 6px;
  margin-left: -6px;
}
.pol-score {
  width: 42px;
  text-align: right;
  font-size: 12px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}
.why {
  margin-top: 8px;
  background: #eef2ff;
  border-radius: 8px;
  padding: 10px 12px;
}
.why-tag {
  font-size: 12px;
  font-weight: 800;
  color: var(--color-primary);
}
.why p {
  margin: 4px 0 0;
  font-size: 12.5px;
  color: #475569;
  line-height: 1.6;
}
.dr-action {
  font-size: 13px;
  font-weight: 600;
}
.dr-reason {
  font-size: 12px;
  color: #64748b;
  margin-top: 2px;
}
.muted {
  font-size: 12.5px;
  color: #94a3b8;
}
</style>
