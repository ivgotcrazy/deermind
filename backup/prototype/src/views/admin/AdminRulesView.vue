<script setup lang="ts">
import { computed } from 'vue'
import { useEvidenceStore } from '@/stores/evidence'
import { DEMO_NOTE, seedRules } from '@/data/sharedMock'
import Icon from '@/components/Icon.vue'

const ev = useEvidenceStore()

const intervalsText = computed({
  get: () => ev.rules.reviewIntervals.join(', '),
  set: (v: string) => {
    ev.rules.reviewIntervals = v
      .split(/[,，\s]+/)
      .map(Number)
      .filter((n) => !Number.isNaN(n))
  },
})

function save() {
  alert('原型演示：规则已保存（生产环境由系统设计定义校验与生效机制）')
}
function resetDefaults() {
  ev.rules = JSON.parse(JSON.stringify(seedRules))
}
</script>

<template>
  <div class="rpage">
    <div class="page-head">
      <h1>规则配置</h1>
      <p class="desc">Attention Budget 与估计器阈值（MVP 默认值见 PRD §8.3；公式见《系统设计.md》）</p>
    </div>

    <section class="panel">
      <div class="panel-title">Attention Budget（注意力预算）</div>
      <div class="form">
        <label class="row">
          <span class="k">每日主动动作上限</span>
          <input v-model.number="ev.rules.dailyProactiveActionLimit" type="number" min="0" />
        </label>
        <label class="row">
          <span class="k">单知识点主动提醒上限</span>
          <input v-model.number="ev.rules.conceptProactiveReminderLimit" type="number" min="0" />
        </label>
        <div class="row pair">
          <span class="k">静默时段</span>
          <div class="pair-inputs">
            <input v-model="ev.rules.quietHoursStart" type="time" />
            <span>—</span>
            <input v-model="ev.rules.quietHoursEnd" type="time" />
          </div>
        </div>
      </div>
    </section>

    <section class="panel">
      <div class="panel-title">估计器阈值（演示）</div>
      <div class="form">
        <label class="row">
          <span class="k">间隔复习天数（逗号分隔）</span>
          <input v-model="intervalsText" type="text" />
        </label>
        <label class="row">
          <span class="k">SHORT→STABLE 迁移题数</span>
          <input v-model.number="ev.rules.migrationVariantCount" type="number" min="1" />
        </label>
        <label class="row switch">
          <span class="k">稳定掌握后停止该知识点</span>
          <input v-model="ev.rules.stopAfterStable" type="checkbox" />
        </label>
      </div>
    </section>

    <div class="actions">
      <button class="btn btn-primary" @click="save"><Icon name="check" :size="16" /> 保存配置</button>
      <button class="btn btn-ghost" @click="resetDefaults">恢复默认值</button>
    </div>

    <footer class="foot">{{ DEMO_NOTE }} · 规则校验与生效机制见《系统设计.md》</footer>
  </div>
</template>

<style scoped>
.rpage {
  display: flex;
  flex-direction: column;
  gap: 14px;
  max-width: 680px;
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
  margin-bottom: 12px;
}
.form {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}
.row .k {
  font-size: 13px;
  color: #475569;
  font-weight: 600;
}
.row input[type='number'],
.row input[type='text'],
.row input[type='time'] {
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 7px 10px;
  font-size: 13px;
  width: 160px;
  background: #fff;
  color: #334155;
}
.row.pair {
  align-items: center;
}
.pair-inputs {
  display: flex;
  align-items: center;
  gap: 8px;
}
.row.switch input[type='checkbox'] {
  width: 18px;
  height: 18px;
  accent-color: var(--color-primary);
}
.actions {
  display: flex;
  gap: 10px;
}
.btn-ghost {
  border: 1.5px solid var(--color-primary);
  color: var(--color-primary);
  background: #fff;
}
.foot {
  font-size: 11.5px;
  color: #94a3b8;
}
</style>
