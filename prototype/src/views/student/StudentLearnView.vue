<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useStudentChat } from '@/stores/studentChat'
import type { MasteryState, TextbookUnit } from '@/data/sharedMock'
import StateBadge from '@/components/admin/StateBadge.vue'
import Icon from '@/components/Icon.vue'

const store = useStudentChat()
const router = useRouter()

const textbook = computed(() => store.ev.textbookOf(store.activeSpaceId))
const activeSpace = computed(() => store.activeSpace)

/* 章节聚合状态：全稳定=已掌握 / 有学习中或短期=进行中 / 否则未接触 */
function sectionState(unit: TextbookUnit, sectionIndex: number) {
  const ids = unit.sections[sectionIndex]?.conceptIds ?? []
  const states = ids.map((id) => store.ev.snapshotOf(id)?.status ?? ('unknown' as MasteryState))
  if (states.length && states.every((s) => s === 'stable')) return 'stable'
  if (states.some((s) => s === 'learning' || s === 'short')) return 'learning'
  return 'unknown'
}

function goLearn(name: string) {
  store.send(`讲讲${name}`)
  router.push('/student/home')
}
</script>

<template>
  <div class="learn">
    <header class="page-head">
      <h1>学习</h1>
      <p class="desc">{{ textbook?.name }} · 学到 {{ activeSpace?.progress }}</p>
      <p class="note">进度是"课本到哪了"，掌握是"你会不会"——两个不一样（未发生反证≠不会）。</p>
    </header>

    <div class="units">
      <section v-for="unit in textbook?.units ?? []" :key="unit.id" class="unit">
        <h2 class="unit-title">{{ unit.title }}</h2>

        <div v-if="!unit.sections.length" class="unit-empty">这一部分还没开始学</div>

        <div v-else class="sections">
          <div v-for="(sec, si) in unit.sections" :key="sec.id" class="section">
            <div class="sec-head">
              <span class="sec-title">{{ sec.title }}</span>
              <span class="sec-state" :class="sectionState(unit, si)">
                {{ sectionState(unit, si) === 'stable' ? '已掌握' : sectionState(unit, si) === 'learning' ? '进行中' : '未开始' }}
              </span>
            </div>
            <div class="concepts">
              <button
                v-for="cid in sec.conceptIds"
                :key="cid"
                class="concept"
                @click="goLearn(store.ev.findConcept(cid)?.name ?? '')"
              >
                <span class="c-name">{{ store.ev.findConcept(cid)?.name }}</span>
                <StateBadge :state="store.ev.snapshotOf(cid)?.status ?? 'unknown'" />
                <Icon name="play" :size="14" class="go" />
              </button>
              <div v-if="!sec.conceptIds.length" class="concept-empty">尚未映射知识点</div>
            </div>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.learn {
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
  opacity: 0.8;
  font-weight: 700;
}
.page-head .note {
  margin: 4px 0 0;
  font-size: 12px;
  opacity: 0.7;
}
.units {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.unit {
  background: var(--color-white);
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-clay);
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.unit-title {
  margin: 0;
  font-family: var(--font-head);
  font-size: 15px;
  font-weight: 700;
}
.unit-empty,
.concept-empty {
  font-size: 12.5px;
  color: #94a3b8;
  padding: 6px 0;
}
.sections {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.section {
  border-left: 3px solid var(--color-primary-soft);
  padding-left: 12px;
}
.sec-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 6px;
}
.sec-title {
  font-size: 13.5px;
  font-weight: 700;
}
.sec-state {
  font-size: 11px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 999px;
}
.sec-state.stable {
  background: var(--color-cta-soft);
  color: #15803d;
}
.sec-state.learning {
  background: var(--color-warning-soft);
  color: #b45309;
}
.sec-state.unknown {
  background: #f1f5f9;
  color: #94a3b8;
}
.concepts {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.concept {
  display: flex;
  align-items: center;
  gap: 8px;
  border: 0;
  background: var(--color-primary-soft);
  border-radius: 12px;
  padding: 8px 12px;
  cursor: pointer;
  font-family: var(--font-body);
  text-align: left;
}
.concept .c-name {
  font-size: 13.5px;
  font-weight: 700;
  color: var(--color-text);
  flex: 1;
}
.concept .go {
  color: var(--color-primary);
  opacity: 0.6;
}
.concept:hover .go {
  opacity: 1;
}
</style>
