<script setup lang="ts">
import { computed, ref } from 'vue'
import { useStudentChat } from '@/stores/studentChat'
import { EVIDENCE_TYPE_LABEL } from '@/data/sharedMock'
import Icon from '@/components/Icon.vue'
import ChatMessage from '@/components/student/ChatMessage.vue'

const store = useStudentChat()
const tab = ref<'record' | 'me' | 'chat'>('record')

/* ---------------- 每日学习记录（结构化总结，非聊天复制） ---------------- */
const todayEvidence = computed(() =>
  store.ev.evidence.filter((e) => e.time.includes('今天') || /^\d{2}:\d{2}$/.test(e.time)),
)
const todayConcepts = computed(() => [...new Set(todayEvidence.value.map((e) => e.kpName))])
const todayCounts = computed(() => {
  const c: Record<string, number> = {}
  todayEvidence.value.forEach((e) => {
    const k = EVIDENCE_TYPE_LABEL[e.type]
    c[k] = (c[k] || 0) + 1
  })
  return Object.entries(c)
})
const todayTransitions = computed(() =>
  store.ev.decisions.filter(
    (d) => (d.time.includes('今天') || /^\d{2}:\d{2}$/.test(d.time)) && d.fromState !== d.toState,
  ),
)
const stopReason = computed(() => {
  const d = [...store.ev.decisions].reverse().find((x) => x.toState === 'stable')
  return d?.reason
})

/* ---------------- 我的学习（定性，不展示数值/掌握条） ---------------- */
const me = computed(() => {
  const stable = store.ev.concepts.filter((c) => store.ev.snapshotOf(c.id)?.status === 'stable').map((c) => c.name)
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

const chatGroups = computed(() => [{ day: '今天 · 8月23日', messages: store.messages }])
</script>

<template>
  <div class="record">
    <header class="page-head">
      <h1>记录</h1>
      <p class="desc">最近在这里做了什么，以及你变成了什么样。</p>
    </header>

    <div class="tabs">
      <button class="tab" :class="{ on: tab === 'record' }" @click="tab = 'record'">每日记录</button>
      <button class="tab" :class="{ on: tab === 'me' }" @click="tab = 'me'">我的学习</button>
      <button class="tab" :class="{ on: tab === 'chat' }" @click="tab = 'chat'">完整对话</button>
    </div>

    <!-- 每日记录 -->
    <section v-if="tab === 'record'" class="panel">
      <h2 class="panel-title">今天 · 8月23日</h2>

      <div class="sec">今天学了什么</div>
      <div class="chips">
        <span v-for="c in todayConcepts" :key="c" class="chip">{{ c }}</span>
        <span v-if="!todayConcepts.length" class="muted">还没有学习记录</span>
      </div>

      <div class="sec">完成了什么</div>
      <ul class="done">
        <li v-for="[k, n] in todayCounts" :key="k">{{ n }} 次{{ k }}</li>
        <li v-if="!todayCounts.length" class="muted">—</li>
      </ul>

      <div class="sec">掌握变化</div>
      <ul class="trans">
        <li v-for="d in todayTransitions" :key="d.id">
          「{{ d.kpName }}」{{ d.fromState === 'unknown' ? '未接触' : d.fromState === 'learning' ? '学习中' : d.fromState === 'short' ? '短期' : '稳定' }}
          → {{ d.toState === 'stable' ? '稳定掌握' : d.toState === 'short' ? '短期掌握' : d.toState === 'learning' ? '学习中' : '未接触' }}
        </li>
        <li v-if="!todayTransitions.length" class="muted">今天暂无掌握状态变化</li>
      </ul>

      <div v-if="store.ev.attention.todayCompleted && stopReason" class="stop-card">
        <div class="sec">小鹿为什么让你停下来</div>
        <p>{{ stopReason }}</p>
      </div>

      <div class="sec">今天用了多久</div>
      <p class="minutes">{{ store.ev.attention.todayFocusMinutes }} 分钟</p>

      <button class="ghost" @click="tab = 'chat'">查看今天的完整对话 <Icon name="chat" :size="15" /></button>
    </section>

    <!-- 我的学习（定性） -->
    <section v-if="tab === 'me'" class="panel">
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
        <div class="stat"><span class="v">{{ me.stableCount }}</span><span class="l">已稳定掌握</span></div>
      </div>

      <p class="hint">这里只告诉你"会什么、在学什么、最近做得怎么样"，不给你打分。</p>
    </section>

    <!-- 完整对话（按自然日） -->
    <section v-if="tab === 'chat'" class="panel chat-panel">
      <div v-for="g in chatGroups" :key="g.day" class="day-group">
        <div class="day-label">{{ g.day }}</div>
        <div class="messages">
          <ChatMessage v-for="m in g.messages" :key="m.id" :msg="m" />
        </div>
        <div v-if="!g.messages.length" class="muted">今天还没有对话</div>
      </div>
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
  gap: 10px;
}
.panel-title {
  margin: 0;
  font-family: var(--font-head);
  font-size: 15px;
  font-weight: 700;
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
.chat-panel {
  gap: 12px;
}
.day-group {
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
.messages {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
</style>
