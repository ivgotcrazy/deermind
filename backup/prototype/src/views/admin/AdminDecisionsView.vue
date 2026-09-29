<script setup lang="ts">
import { computed, ref } from 'vue'
import { useEvidenceStore } from '@/stores/evidence'
import { DEMO_NOTE } from '@/data/sharedMock'
import StateBadge from '@/components/admin/StateBadge.vue'

const ev = useEvidenceStore()
const filter = ref('all')

const kpNames = computed(() => ev.concepts.map((c) => c.name))

const rows = computed(() =>
  ev.decisions
    .filter((d) => filter.value === 'all' || d.kpName === filter.value)
    .slice()
    .reverse(),
)
</script>

<template>
  <div class="dpage">
    <div class="page-head">
      <h1>决策理由</h1>
      <p class="desc">政策引擎输入 → 动作 → 理由（可解释性审计，{{ DEMO_NOTE }}）</p>
    </div>

    <div class="toolbar">
      <label class="f">
        知识点
        <select v-model="filter">
          <option value="all">全部</option>
          <option v-for="n in kpNames" :key="n" :value="n">{{ n }}</option>
        </select>
      </label>
      <span class="count">共 {{ rows.length }} 条</span>
    </div>

    <section class="panel">
      <table class="tbl">
        <thead>
          <tr>
            <th>时间</th>
            <th>知识点</th>
            <th>触发证据</th>
            <th>输出动作</th>
            <th>状态变化</th>
            <th>决策理由</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="d in rows" :key="d.id">
            <td class="nowrap">{{ d.time }}</td>
            <td class="nowrap kp">{{ d.kpName }}</td>
            <td class="trig">{{ d.trigger }}</td>
            <td class="act">{{ d.action }}</td>
            <td class="nowrap">
              <span class="move"><StateBadge :state="d.fromState" /> → <StateBadge :state="d.toState" /></span>
            </td>
            <td class="reason">{{ d.reason }}</td>
          </tr>
          <tr v-if="!rows.length">
            <td colspan="6" class="muted">暂无决策记录</td>
          </tr>
        </tbody>
      </table>
    </section>
  </div>
</template>

<style scoped>
.dpage {
  display: flex;
  flex-direction: column;
  gap: 14px;
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
.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
}
.f {
  font-size: 12.5px;
  color: #475569;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.f select {
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 6px 8px;
  font-size: 13px;
  background: #fff;
  color: #334155;
}
.count {
  font-size: 12px;
  color: #94a3b8;
}
.panel {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 8px 12px;
  overflow-x: auto;
}
.tbl {
  width: 100%;
  border-collapse: collapse;
  min-width: 900px;
}
.tbl th {
  font-size: 12px;
  font-weight: 600;
  color: #64748b;
  text-align: left;
  padding: 8px;
  border-bottom: 1px solid #e2e8f0;
  white-space: nowrap;
}
.tbl td {
  font-size: 12.5px;
  padding: 10px 8px;
  border-bottom: 1px solid #f1f5f9;
  vertical-align: top;
  line-height: 1.5;
}
.tbl tr:hover td {
  background: #f8fafc;
}
.nowrap {
  white-space: nowrap;
}
.kp {
  font-weight: 700;
}
.trig,
.act {
  color: #475569;
  max-width: 220px;
}
.reason {
  color: #64748b;
  max-width: 260px;
}
.move {
  display: inline-flex;
  align-items: center;
  gap: 2px;
}
.muted {
  color: #94a3b8;
  text-align: center;
  padding: 16px;
}
</style>
