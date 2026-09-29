<script setup lang="ts">
import { computed, ref } from 'vue'
import { useEvidenceStore } from '@/stores/evidence'
import { EVIDENCE_TYPE_LABEL, DEMO_NOTE } from '@/data/sharedMock'
import Icon from '@/components/Icon.vue'

const ev = useEvidenceStore()
const showDetail = ref(false)

const todayEvidence = computed(() => ev.evidence.slice(-6).reverse())
const weakness = computed(() =>
  ev.concepts
    .filter((c) => ev.snapshotOf(c.id)?.status === 'learning')
    .map((c) => c.name),
)
const stableNames = computed(() =>
  ev.concepts.filter((c) => ev.snapshotOf(c.id)?.status === 'stable').map((c) => c.name),
)

const attentionWarning = computed(
  () => ev.attention.todayProactiveActions >= ev.rules.dailyProactiveActionLimit,
)

/* 平静优先：默认"没什么需要操心"，有异常才显著提示 */
const headline = computed(() => {
  if (ev.attention.todayCompleted)
    return { tone: 'ok', text: '今天已收工，不需要你做任何事。' }
  if (attentionWarning.value)
    return { tone: 'warn', text: '今日主动触达已达上限，剩下由孩子主动发起。' }
  if (weakness.value.length)
    return { tone: 'info', text: `有 ${weakness.value.length} 个知识点在巩固中，暂不需要你介入。` }
  return { tone: 'ok', text: '今天没什么需要你操心的。' }
})

const subline = computed(() => {
  const parts: string[] = []
  if (weakness.value.length) parts.push(`${weakness.value.join('、')} 正在巩固`)
  if (stableNames.value.length) parts.push(`${stableNames.value.slice(0, 2).join('、')} 已稳定掌握`)
  if (!parts.length) parts.push('孩子今天还没有学习记录')
  return `${parts.join('；')}。今天用了 ${ev.attention.todayFocusMinutes} 分钟。`
})
</script>

<template>
  <div class="today">
    <h2 class="title">今日 · 8 月 23 日</h2>

    <!-- 平静摘要（首屏） -->
    <section class="calm" :class="headline.tone">
      <div class="calm-head">
        <Icon :name="headline.tone === 'warn' ? 'sparkles' : 'check'" :size="20" />
        <span>{{ headline.text }}</span>
      </div>
      <p class="sub">{{ subline }}</p>
      <button class="btn-ghost small" @click="showDetail = !showDetail">
        {{ showDetail ? '收起详情' : '查看详情' }}
      </button>
    </section>

    <!-- 详情（可展开） -->
    <template v-if="showDetail">
      <div class="stats">
        <div class="stat">
          <Icon name="chart" :size="20" />
          <span class="v">{{ ev.attention.todayFocusMinutes }} 分</span>
          <span class="l">今日专注</span>
        </div>
        <div class="stat">
          <Icon name="check" :size="20" />
          <span class="v">{{ ev.attention.todayProactiveActions }}/{{ ev.rules.dailyProactiveActionLimit }}</span>
          <span class="l">主动动作</span>
        </div>
        <div class="stat">
          <Icon name="calendar" :size="20" />
          <span class="v">{{ ev.attention.todayCompleted ? '已收工' : '进行中' }}</span>
          <span class="l">今日状态</span>
        </div>
      </div>

      <section class="card">
        <div class="sec-title">学习记录（证据账本）</div>
        <ul class="records">
          <li v-for="r in todayEvidence" :key="r.id" class="rec">
            <span class="t">{{ r.time }}</span>
            <span class="tag" :class="r.polarity">
              {{ EVIDENCE_TYPE_LABEL[r.type] }} · {{ r.polarity === 'positive' ? '通过' : '未通过' }}
            </span>
            <div class="txt">{{ r.kpName }}：{{ r.note }}</div>
          </li>
        </ul>
      </section>

      <section v-if="weakness.length" class="card alert">
        <div class="head">
          <Icon name="sparkles" :size="18" />
          <span>待巩固知识点</span>
        </div>
        <p><b v-for="w in weakness" :key="w" class="chip">{{ w }}</b></p>
        <p class="sugg">建议：继续「分数乘分数」的变式/迁移验证（约 8 分钟）</p>
      </section>
    </template>

    <footer class="demo">{{ DEMO_NOTE }}</footer>
  </div>
</template>

<style scoped>
.today {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.title {
  margin: 0;
  font-size: 19px;
}
.calm {
  background: #fff;
  border-radius: 14px;
  padding: 18px 20px;
  box-shadow: var(--shadow-clay);
  border-left: 4px solid var(--color-cta);
}
.calm.warn {
  border-left-color: var(--color-warning);
}
.calm.info {
  border-left-color: var(--color-primary);
}
.calm-head {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 800;
  color: #15803d;
}
.calm.warn .calm-head {
  color: #b45309;
}
.calm.info .calm-head {
  color: var(--color-primary);
}
.sub {
  margin: 8px 0 12px;
  font-size: 13.5px;
  color: #475569;
  line-height: 1.7;
}
.btn-ghost.small {
  border: 1.5px solid var(--color-primary);
  color: var(--color-primary);
  background: transparent;
  border-radius: 8px;
  padding: 6px 14px;
  font-size: 12.5px;
  font-weight: 700;
  cursor: pointer;
}
.stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
}
.stat {
  background: #fff;
  border-radius: 14px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  color: var(--color-primary);
  box-shadow: var(--shadow-clay);
}
.stat .v {
  font-size: 16px;
  font-weight: 800;
  color: var(--color-text);
}
.stat .l {
  font-size: 11px;
  opacity: 0.7;
}
.sec-title {
  font-weight: 800;
  margin-bottom: 10px;
}
.records {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.rec {
  display: flex;
  align-items: baseline;
  gap: 8px;
  flex-wrap: wrap;
  font-size: 13px;
}
.rec .t {
  color: var(--color-primary);
  font-weight: 700;
  font-size: 12px;
}
.rec .txt {
  width: 100%;
  padding-left: 56px;
  opacity: 0.85;
}
.tag {
  font-size: 11px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 999px;
}
.tag.positive {
  background: var(--color-cta-soft);
  color: #15803d;
}
.tag.negative {
  background: var(--color-danger-soft);
  color: #b91c1c;
}
.alert {
  border-top: 4px solid var(--color-warning);
}
.head {
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 800;
  color: #b45309;
  margin-bottom: 6px;
}
.alert p {
  margin: 0 0 6px;
  font-size: 13px;
  line-height: 1.6;
}
.chip {
  display: inline-block;
  margin: 0 4px;
  font-style: normal;
  background: var(--color-warning-soft);
  color: #b45309;
  border-radius: 999px;
  padding: 2px 10px;
  font-size: 12px;
  font-weight: 700;
}
.sugg {
  color: var(--color-primary);
}
.demo {
  font-size: 11px;
  color: #b45309;
  background: var(--color-warning-soft);
  padding: 2px 8px;
  border-radius: 999px;
  align-self: flex-start;
}
</style>
