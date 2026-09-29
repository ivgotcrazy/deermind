<script setup lang="ts">
import { computed, ref } from 'vue'
import { useStudentChat } from '@/stores/studentChat'
import { transitionChild, dayKey } from '@/stores/studentSemantics'
import { EVIDENCE_TYPE_LABEL } from '@/data/sharedMock'
import Icon from '@/components/Icon.vue'
import ChatMessage from '@/components/student/ChatMessage.vue'

const store = useStudentChat()
const tab = ref<'timeline' | 'me'>('timeline')
const openDay = ref<string | null>(null)

const todayKey = dayKey(new Date().toISOString())

/* 学习时间线：按 occurredAt 时间戳分组（领域层），非 UI 文本 */
const timeline = computed(() => {
  const days = new Map<string, string>()
  store.ev.evidence.forEach((e) => days.set(dayKey(e.occurredAt), ''))
  store.ev.decisions.forEach((d) => days.set(dayKey(d.occurredAt), ''))
  store.messages.forEach((m) => days.set(dayKey(m.ts), ''))
  return [...days.keys()]
    .sort()
    .reverse()
    .map((key) => {
      const evs = store.ev.evidence.filter((e) => dayKey(e.occurredAt) === key)
      const decs = store.ev.decisions.filter((d) => dayKey(d.occurredAt) === key)
      const msgs = store.messages.filter((m) => dayKey(m.ts) === key)
      const concepts = [...new Set(evs.map((e) => e.kpName))]
      const counts: Record<string, number> = {}
      evs.forEach((e) => {
        const k = EVIDENCE_TYPE_LABEL[e.type]
        counts[k] = (counts[k] || 0) + 1
      })
      const transitions = decs.filter((d) => d.fromState !== d.toState)
      const stop = [...decs].reverse().find((d) => d.toState === 'stable')?.reason
      return {
        key,
        isToday: key === todayKey,
        concepts,
        counts: Object.entries(counts),
        transitions,
        stop,
        msgs,
      }
    })
})

/* 我的学习（成长视图，定性） */
const me = computed(() => {
  const stable = store.ev.concepts
    .filter((c) => store.ev.snapshotOf(c.id)?.status === 'stable')
    .map((c) => c.name)
  const growing = store.ev.concepts
    .filter((c) => {
      const s = store.ev.snapshotOf(c.id)?.status
      return s === 'learning' || s === 'short'
    })
    .map((c) => c.name)
  const solved = store.ev.evidence.filter((e) => e.polarity === 'positive').length
  return {
    active: store.activeKpName,
    stable,
    growing,
    minutes: store.ev.attention.todayFocusMinutes,
    solved,
    stableCount: stable.length,
  }
})

/* 最近的成长：掌握状态发生了真实变化（领域层 decisions），用儿童语言描述 */
const recentGrowth = computed(() =>
  store.ev.decisions
    .filter((d) => d.fromState !== d.toState)
    .slice(-3)
    .reverse()
    .map((d) => `「${d.kpName}」${transitionChild(d.fromState, d.toState)}`),
)

function toggleDay(key: string) {
  openDay.value = openDay.value === key ? null : key
}
</script>

<template>
  <div class="record">
    <header class="page-head">
      <h1>记录</h1>
      <p class="desc">最近在这里做了什么，以及你变成了什么样。</p>
    </header>

    <div class="tabs">
      <button class="tab" :class="{ on: tab === 'timeline' }" @click="tab = 'timeline'">学习时间线</button>
      <button class="tab" :class="{ on: tab === 'me' }" @click="tab = 'me'">我的学习</button>
    </div>

    <!-- 学习时间线（按自然日） -->
    <section v-if="tab === 'timeline'" class="panel">
      <div v-for="d in timeline" :key="d.key" class="day">
        <div class="day-label">{{ d.isToday ? '今天' : d.key.slice(5).replace('-', '月') + '日' }}</div>

        <div class="day-body">
          <div class="sec">学了什么</div>
          <div class="chips">
            <span v-for="c in d.concepts" :key="c" class="chip">{{ c }}</span>
            <span v-if="!d.concepts.length" class="muted">今天还没有学习记录</span>
          </div>

          <div class="sec">完成了什么</div>
          <ul class="done">
            <li v-for="[k, n] in d.counts" :key="k">{{ n }} 次{{ k }}</li>
            <li v-if="!d.counts.length" class="muted">—</li>
          </ul>

          <div class="sec">掌握变化</div>
          <ul class="trans">
            <li v-for="t in d.transitions" :key="t.id">
              「{{ t.kpName }}」{{ transitionChild(t.fromState, t.toState) }}
            </li>
            <li v-if="!d.transitions.length" class="muted">这天没有掌握状态变化</li>
          </ul>

          <div v-if="d.stop" class="stop-card">
            <div class="sec">小鹿为什么让你停下来</div>
            <p>{{ d.stop }}</p>
          </div>

          <div v-if="d.isToday" class="sec">今天用了多久</div>
          <p v-if="d.isToday" class="minutes">{{ store.ev.attention.todayFocusMinutes }} 分钟</p>

          <button v-if="d.msgs.length" class="ghost" @click="toggleDay(d.key)">
            {{ openDay === d.key ? '收起完整对话' : `查看今天的完整对话（${d.msgs.length}）` }}
            <Icon :name="openDay === d.key ? 'close' : 'chat'" :size="15" />
          </button>

          <div v-if="openDay === d.key && d.msgs.length" class="chat-block">
            <ChatMessage v-for="m in d.msgs" :key="m.id" :msg="m" />
          </div>
        </div>
      </div>

      <div v-if="!timeline.length" class="muted">还没有学习记录</div>
    </section>

    <!-- 我的学习（成长视图） -->
    <section v-if="tab === 'me'" class="panel">
      <div class="me-block">
        <div class="sec">最近的成长</div>
        <ul class="growth">
          <li v-for="g in recentGrowth" :key="g">{{ g }}</li>
          <li v-if="!recentGrowth.length" class="muted">还没有成长记录</li>
        </ul>
      </div>

      <div class="me-block">
        <div class="sec">最近在学</div>
        <p class="me-big">{{ me.active }}</p>
      </div>

      <div class="me-block">
        <div class="sec">我比较拿手</div>
        <div class="chips">
          <span v-for="c in me.stable" :key="c" class="chip ok">{{ c }}</span>
          <span v-if="!me.stable.length" class="muted">还在积累中</span>
        </div>
      </div>

      <div class="me-block">
        <div class="sec">正在变强</div>
        <div class="chips">
          <span v-for="c in me.growing" :key="c" class="chip grow">{{ c }}</span>
          <span v-if="!me.growing.length" class="muted">暂时没有进行中的</span>
        </div>
      </div>

      <div class="me-stats">
        <div class="stat"><span class="v">{{ me.minutes }}</span><span class="l">今天学了（分钟）</span></div>
        <div class="stat"><span class="v">{{ me.solved }}</span><span class="l">解决过的问题</span></div>
        <div class="stat"><span class="v">{{ me.stableCount }}</span><span class="l">已经会了的</span></div>
      </div>

      <p class="hint">这里只告诉你"会什么、在学什么、最近做得怎么样"，不给你打分。</p>
    </section>
  </div>
</template>

<style scoped>
.record {
  height: 100%;
  overflow-y: auto;
  padding: 12px 16px 24px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-width: 760px;
  margin: 0 auto;
  width: 100%;
}
.page-head h1 {
  margin: 0;
  font-size: 19px;
  font-family: var(--font-head);
}
.page-head .desc {
  margin: 4px 0 0;
  font-size: 12.5px;
  opacity: 0.75;
}
.tabs {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.tab {
  border: 0;
  cursor: pointer;
  font-family: var(--font-body);
  font-size: 13px;
  font-weight: 700;
  padding: 7px 14px;
  border-radius: 999px;
  background: var(--color-primary-soft);
  color: var(--color-primary);
}
.tab.on {
  background: var(--color-primary);
  color: #fff;
}
.panel {
  background: var(--color-white);
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-clay);
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.day {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.day-label {
  font-size: 12px;
  font-weight: 800;
  color: var(--color-secondary);
  text-align: center;
  background: var(--color-primary-soft);
  border-radius: 999px;
  align-self: center;
  padding: 3px 12px;
}
.day-body {
  border-left: 2px solid var(--color-primary-soft);
  padding-left: 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.sec {
  font-size: 12px;
  font-weight: 800;
  color: var(--color-secondary);
  margin-top: 4px;
}
.chips {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
.chip {
  font-size: 12.5px;
  font-weight: 700;
  padding: 4px 10px;
  border-radius: 999px;
  background: var(--color-primary-soft);
  color: var(--color-primary);
}
.chip.ok {
  background: var(--color-cta-soft);
  color: #15803d;
}
.chip.grow {
  background: var(--color-warning-soft);
  color: #b45309;
}
.done,
.trans {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 5px;
  font-size: 13px;
}
.muted {
  font-size: 12.5px;
  color: #94a3b8;
}
.stop-card {
  background: var(--color-cta-soft);
  border-radius: 12px;
  padding: 10px 12px;
}
.stop-card p {
  margin: 4px 0 0;
  font-size: 13px;
  line-height: 1.6;
  color: #475569;
}
.minutes {
  margin: 0;
  font-size: 15px;
  font-weight: 800;
}
.ghost {
  border: 0;
  cursor: pointer;
  font-family: var(--font-body);
  font-weight: 700;
  font-size: 13px;
  padding: 8px 14px;
  border-radius: 12px;
  background: var(--color-primary-soft);
  color: var(--color-primary);
  display: inline-flex;
  align-items: center;
  gap: 5px;
  align-self: flex-start;
}
.chat-block {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-top: 4px;
}
.me-big {
  margin: 0;
  font-family: var(--font-head);
  font-size: 18px;
  font-weight: 700;
  color: var(--color-primary);
}
.me-block {
  display: flex;
  flex-direction: column;
  gap: 6px;
  border-bottom: 1px dashed var(--color-line);
  padding-bottom: 10px;
}
.growth {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.growth li {
  background: var(--color-cta-soft);
  border-radius: 12px;
  padding: 8px 10px;
  font-size: 13px;
  color: var(--color-cta);
  font-weight: 700;
  animation: growth-in 0.3s ease-out;
}
@keyframes growth-in {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
.me-stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  margin-top: 4px;
}
.stat {
  background: var(--color-primary-soft);
  border-radius: 14px;
  padding: 12px;
  text-align: center;
}
.stat .v {
  display: block;
  font-size: 20px;
  font-weight: 800;
  color: var(--color-text);
}
.stat .l {
  font-size: 11px;
  opacity: 0.75;
}
.hint {
  margin: 0;
  font-size: 12px;
  color: #94a3b8;
}
</style>
