<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useStudentChat } from '@/stores/studentChat'
import { agentLineForConcept, childState, type ChildState } from '@/stores/studentSemantics'
import { conceptContents, type MasteryState, type TextbookUnit } from '@/data/sharedMock'
import Icon from '@/components/Icon.vue'

const store = useStudentChat()
const router = useRouter()
const showPicker = ref(false)
const openConcept = ref<string | null>(null)
const reading = ref(false)

const textbook = computed(() => store.ev.textbookOf(store.activeSpaceId))
const activeSpace = computed(() => store.activeSpace)

/* 章节聚合状态（儿童语）：全稳定=已经会了 / 有进行中=正在学 / 否则=暂时不用学 */
function sectionChild(unit: TextbookUnit, si: number): ChildState {
  const ids = unit.sections[si]?.conceptIds ?? []
  const states = ids.map((id) => store.ev.snapshotOf(id)?.status ?? ('unknown' as MasteryState))
  if (states.length && states.every((s) => s === 'stable')) return { text: '已经会了', show: true }
  if (states.some((s) => s === 'learning' || s === 'short')) return { text: '正在学', show: true }
  return { text: '暂时不用学', show: false }
}

function goLearn(name: string) {
  store.send(`讲讲${name}`)
  router.push('/student/home')
}

function toggleConcept(id: string) {
  openConcept.value = openConcept.value === id ? null : id
}

/* 更新当前学习进度（课程位置，非掌握度） */
function updateHere(unitTitle: string, secTitle: string) {
  store.setSpaceProgress(store.activeSpaceId, `${unitTitle} · ${secTitle}`)
}
function pickSection(unitTitle: string, secTitle: string) {
  store.setSpaceProgress(store.activeSpaceId, `${unitTitle} · ${secTitle}`)
  showPicker.value = false
}
</script>

<template>
  <div class="learn">
    <header class="page-head">
      <h1>学习</h1>
      <p class="desc">{{ textbook?.name }}</p>
    </header>

    <!-- 当前进度（课程位置）+ 更新 -->
    <section class="progress-card">
      <div class="pc-head">
        <span class="pc-label">当前学到</span>
        <button class="ghost small" @click="showPicker = true"><Icon name="check" :size="14" /> 更新进度</button>
      </div>
      <div class="pc-value">{{ activeSpace?.progress }}</div>
      <p class="pc-note">进度是"课本到哪了"，掌握是"你会不会"——两个不一样（还没有发现需要处理的问题 ≠ 不会）。</p>
    </section>

    <!-- 课程树 -->
    <div class="units">
      <section v-for="unit in textbook?.units ?? []" :key="unit.id" class="unit">
        <h2 class="unit-title">{{ unit.title }}</h2>

        <div v-if="!unit.sections.length" class="unit-empty">这一部分还没开始学</div>

        <div v-else class="sections">
          <div v-for="(sec, si) in unit.sections" :key="sec.id" class="section">
            <div class="sec-head">
              <span class="sec-title">{{ sec.title }}</span>
              <span class="sec-state" :class="{ on: sectionChild(unit, si).show }">
                {{ sectionChild(unit, si).text }}
              </span>
            </div>
            <div class="concepts">
              <button
                v-for="cid in sec.conceptIds"
                :key="cid"
                class="concept"
                @click="toggleConcept(cid)"
              >
                <span class="c-name">{{ store.ev.findConcept(cid)?.name }}</span>
                <!-- UNKNOWN 不展示掌握状态（儿童语义层 show=false） -->
                <span
                  v-if="childState(store.ev.snapshotOf(cid)?.status).show"
                  class="c-state"
                  :class="childState(store.ev.snapshotOf(cid)?.status).text === '正在学' ? 'learning' : 'stable'"
                >
                  {{ childState(store.ev.snapshotOf(cid)?.status).text }}
                </span>
                <Icon name="play" :size="14" class="go" />
              </button>

              <!-- 知识点详情（教材内容 + 小鹿的话 + 操作） -->
              <div v-for="cid in sec.conceptIds" :key="`d-${cid}`">
                <div v-if="openConcept === cid" class="concept-detail">
                  <div class="cd-head">
                    <span class="cd-name">{{ store.ev.findConcept(cid)?.name }}</span>
                    <span class="cd-ref">{{ conceptContents[cid]?.textbookRef }}</span>
                  </div>
                  <div class="sec">小鹿说</div>
                  <p class="full agent">
                    {{ agentLineForConcept(store.ev.findConcept(cid)?.name ?? '', store.ev.snapshotOf(cid)?.status) }}
                  </p>
                  <div class="sec">教材内容</div>
                  <p class="full">{{ conceptContents[cid]?.summary }}</p>
                  <div class="keypoints">
                    <span v-for="kp in conceptContents[cid]?.keyPoints" :key="kp" class="kp-chip">{{ kp }}</span>
                  </div>
                  <div class="cd-actions">
                    <button class="ghost" :class="{ playing: reading }" @click="reading = !reading">
                      <Icon :name="reading ? 'volumeOff' : 'speaker'" :size="15" />
                      {{ reading ? '朗读中…' : '朗读' }}
                    </button>
                    <button class="ghost" @click="goLearn(store.ev.findConcept(cid)?.name ?? '')">
                      让小鹿讲讲 <Icon name="speaker" :size="15" />
                    </button>
                    <button class="primary" @click="updateHere(unit.title, sec.title)">更新进度到这里</button>
                  </div>
                </div>
              </div>

              <div v-if="!sec.conceptIds.length" class="concept-empty">尚未映射知识点</div>
            </div>
          </div>
        </div>
      </section>
    </div>

    <!-- 更新进度选择器 -->
    <div v-if="showPicker" class="mask" @click.self="showPicker = false">
      <div class="picker">
        <div class="picker-head">更新我的学习进度 <button class="close" @click="showPicker = false">✕</button></div>
        <p class="picker-note">选到你现在学到的位置，小鹿记住这里（只记录课程位置，不影响掌握判断）。</p>
        <div
          v-for="unit in textbook?.units ?? []"
          :key="unit.id"
          class="picker-unit"
        >
          <div class="pu-title">{{ unit.title }}</div>
          <div v-if="!unit.sections.length" class="pu-empty">暂无内容</div>
          <button
            v-for="sec in unit.sections"
            :key="sec.id"
            class="pu-sec"
            @click="pickSection(unit.title, sec.title)"
          >
            {{ sec.title }}
          </button>
        </div>
      </div>
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
.progress-card {
  background: var(--color-white);
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-clay);
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.pc-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.pc-label {
  font-size: 12px;
  font-weight: 800;
  color: var(--color-secondary);
}
.pc-value {
  font-family: var(--font-head);
  font-size: 16px;
  font-weight: 700;
}
.pc-note {
  margin: 0;
  font-size: 12px;
  opacity: 0.7;
}
.ghost.small {
  border: 0;
  background: var(--color-primary-soft);
  color: var(--color-primary);
  font-weight: 700;
  font-size: 12.5px;
  padding: 6px 12px;
  border-radius: 12px;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 4px;
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
  background: #f1f5f9;
  color: #94a3b8;
}
.sec-state.on {
  background: var(--color-primary-soft);
  color: var(--color-primary);
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
.c-state {
  font-size: 11px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 999px;
}
.c-state.learning {
  background: var(--color-warning-soft);
  color: #b45309;
}
.c-state.stable {
  background: var(--color-cta-soft);
  color: #15803d;
}
.concept .go {
  color: var(--color-primary);
  opacity: 0.6;
}
.concept:hover .go {
  opacity: 1;
}
.concept-detail {
  background: #fff;
  border: 2px solid var(--color-primary-soft);
  border-radius: 12px;
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.cd-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
}
.cd-name {
  font-weight: 800;
  font-size: 14px;
}
.cd-ref {
  font-size: 11px;
  color: var(--color-secondary);
}
.sec {
  font-size: 12px;
  font-weight: 800;
  color: var(--color-secondary);
  margin-top: 4px;
}
.full {
  margin: 0;
  font-size: 13px;
  line-height: 1.7;
  background: var(--color-primary-soft);
  border-radius: 12px;
  padding: 9px 12px;
}
.full.agent {
  background: var(--color-warning-soft);
  color: #7c4a03;
}
.keypoints {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
.kp-chip {
  font-size: 11.5px;
  font-weight: 700;
  padding: 3px 9px;
  border-radius: 999px;
  background: var(--color-cta-soft);
  color: #15803d;
}
.cd-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 2px;
}
.ghost,
.primary {
  border: 0;
  cursor: pointer;
  font-family: var(--font-body);
  font-weight: 700;
  font-size: 12.5px;
  padding: 8px 13px;
  border-radius: 12px;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.ghost {
  background: var(--color-primary-soft);
  color: var(--color-primary);
}
.ghost.playing {
  background: var(--color-cta-soft);
  color: var(--color-cta);
}
.primary {
  background: var(--color-cta);
  color: #fff;
}
.mask {
  position: fixed;
  inset: 0;
  background: rgba(49, 46, 129, 0.35);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 60;
}
.picker {
  width: min(420px, 90vw);
  max-height: 70vh;
  overflow-y: auto;
  background: #fff;
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-clay);
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.picker-head {
  font-family: var(--font-head);
  font-weight: 700;
  font-size: 15px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.close {
  border: 0;
  background: transparent;
  font-size: 16px;
  cursor: pointer;
  color: var(--color-text);
}
.picker-note {
  margin: 0;
  font-size: 12px;
  opacity: 0.75;
}
.picker-unit {
  border-top: 1px dashed var(--color-line);
  padding-top: 8px;
}
.pu-title {
  font-size: 13px;
  font-weight: 800;
  margin-bottom: 6px;
}
.pu-empty {
  font-size: 12px;
  color: #94a3b8;
}
.pu-sec {
  display: block;
  width: 100%;
  text-align: left;
  border: 0;
  background: var(--color-primary-soft);
  border-radius: 10px;
  padding: 8px 12px;
  margin-bottom: 6px;
  cursor: pointer;
  font-family: var(--font-body);
  font-size: 13px;
  font-weight: 700;
  color: var(--color-text);
}
</style>
