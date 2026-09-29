<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useStudentChat } from '@/stores/studentChat'
import { childState, ERROR_STATUS_CHILD, agentLineForWrongbook } from '@/stores/studentSemantics'
import { ERROR_SOURCE_LABEL, type ErrorStatus } from '@/data/sharedMock'
import Icon from '@/components/Icon.vue'

const store = useStudentChat()
const router = useRouter()

type Filter = 'all' | ErrorStatus
const filter = ref<Filter>('all')
const search = ref('')
const conceptFilter = ref('all')
const detailId = ref<string | null>(null)
const redoId = ref<string | null>(null)
const redoMsg = ref<string>('')

const tabs: { key: Filter; label: string }[] = [
  { key: 'all', label: '全部' },
  { key: 'pending', label: '待处理' },
  { key: 'reviewing', label: '辅导中' },
  { key: 'resolved', label: '已解决' },
]

const spaceErrors = computed(() =>
  store.ev.errors.filter((e) => e.spaceId === store.activeSpaceId),
)
const errorConcepts = computed(() => [...new Set(spaceErrors.value.map((e) => e.conceptName))])

const list = computed(() =>
  spaceErrors.value.filter(
    (e) =>
      (filter.value === 'all' || e.status === filter.value) &&
      (conceptFilter.value === 'all' || e.conceptName === conceptFilter.value) &&
      (search.value === '' ||
        e.conceptName.includes(search.value) ||
        e.stem.includes(search.value)),
  ),
)

function toggleDetail(id: string) {
  detailId.value = detailId.value === id ? null : id
  redoId.value = null
  redoMsg.value = ''
}
function toggleRedo(id: string) {
  redoId.value = redoId.value === id ? null : id
  redoMsg.value = ''
}

/* 重做：错题状态 → 已解决 + 正证据入账；掌握与否由估计器判断（与错题解耦） */
function redoPass(id: string) {
  const e = store.ev.errors.find((x) => x.id === id)
  if (e) {
    store.ev.resolveError(id)
    store.ev.applyEvidence(e.conceptId, 'review', 'positive', '错题重做', '重做通过')
  }
  redoMsg.value = '这道题已解决，证据已入账。是否真正掌握，由小鹿根据更多证据判断。'
}
function redoFail() {
  redoMsg.value = '没关系，说明还不熟。让小鹿再讲讲，过两天再来重做～'
}
</script>

<template>
  <div class="wrongbook">
    <header class="page-head">
      <h1>我的错题</h1>
      <p class="desc">做错的题会自动收进来，随时查看、复习、重做。</p>
    </header>

    <div class="toolbar">
      <input v-model="search" class="search" placeholder="搜索题目或知识点…" />
      <select v-model="conceptFilter" class="select">
        <option value="all">全部知识点</option>
        <option v-for="c in errorConcepts" :key="c" :value="c">{{ c }}</option>
      </select>
    </div>

    <div class="tabs">
      <button
        v-for="t in tabs"
        :key="t.key"
        class="tab"
        :class="{ on: filter === t.key }"
        @click="filter = t.key"
      >
        {{ t.label }}
      </button>
    </div>

    <div class="list">
      <article v-for="e in list" :key="e.id" class="card">
        <div class="row-top" @click="toggleDetail(e.id)">
          <span class="src">{{ ERROR_SOURCE_LABEL[e.source] }} · {{ e.time }}</span>
          <span class="status" :class="e.status">{{ ERROR_STATUS_CHILD[e.status] }}</span>
        </div>
        <div class="kp">{{ e.conceptName }}</div>
        <div class="stem">{{ e.stem }}</div>
        <div class="row-meta">
          <span class="att">{{ e.attribution }}</span>
          <span class="now-state">错题：{{ ERROR_STATUS_CHILD[e.status] }}</span>
        </div>

        <div class="actions">
          <button class="ghost" @click="toggleDetail(e.id)">
            {{ detailId === e.id ? '收起' : '查看' }}
          </button>
          <button v-if="e.status !== 'resolved'" class="primary" @click="toggleRedo(e.id)">
            {{ redoId === e.id ? '收起' : '现在复习' }}
          </button>
        </div>

        <!-- 详情：错题状态与知识点掌握状态分开 -->
        <div v-if="detailId === e.id" class="detail">
          <div class="sec">原题</div>
          <p class="full">{{ e.stem }}</p>
          <div class="sec">当时为什么错</div>
          <p class="full">{{ e.attribution }}</p>
          <div class="sec">这道题现在</div>
          <p class="full">错题：{{ ERROR_STATUS_CHILD[e.status] }}</p>
          <div class="sec">「{{ e.conceptName }}」这个知识点</div>
          <p class="full">
            <template v-if="childState(store.ev.snapshotOf(e.conceptId)?.status).show">
              {{ childState(store.ev.snapshotOf(e.conceptId)?.status).text }}——一道题会了不等于掌握，小鹿会继续看有没有更多证据。
            </template>
            <template v-else>还没有发现需要处理的问题。</template>
          </p>
          <div class="sec">小鹿的建议</div>
          <p class="full agent">{{ agentLineForWrongbook(e.conceptName, store.ev.snapshotOf(e.conceptId)?.status, e.status === 'resolved') }}</p>
          <button class="ghost" @click="router.push('/student/home'); store.send(`讲讲${e.conceptName}`)">
            让小鹿讲讲 <Icon name="speaker" :size="15" />
          </button>
        </div>

        <!-- 重做 -->
        <div v-if="redoId === e.id" class="redo">
          <div class="sec">重做这道题</div>
          <p class="full">{{ e.stem }}</p>
          <p class="redo-q">现在会做了吗？</p>
          <div class="redo-btns">
            <button class="primary" @click="redoPass(e.id)">会了，我做对了</button>
            <button class="ghost" @click="redoFail">还不会</button>
          </div>
          <p v-if="redoMsg" class="redo-msg">{{ redoMsg }}</p>
        </div>
      </article>

      <div v-if="!list.length" class="empty">
        <Icon name="check" :size="18" /> 这里还没有错题，做错的题会自动收进来
      </div>
    </div>
  </div>
</template>

<style scoped>
.wrongbook {
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
.toolbar {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.search {
  flex: 1;
  min-width: 160px;
  border: 2px solid var(--color-line);
  border-radius: 12px;
  padding: 8px 12px;
  font-family: var(--font-body);
  font-size: 13.5px;
}
.select {
  border: 2px solid var(--color-line);
  border-radius: 12px;
  padding: 8px 10px;
  font-family: var(--font-body);
  font-size: 13px;
  background: #fff;
  color: var(--color-text);
}
.full.agent {
  background: var(--color-warning-soft);
  color: #7c4a03;
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
.list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.card {
  background: var(--color-white);
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-clay);
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.row-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  cursor: pointer;
}
.src {
  font-size: 12px;
  color: var(--color-secondary);
  font-weight: 600;
}
.status {
  font-size: 11px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 999px;
}
.status.pending {
  background: var(--color-warning-soft);
  color: #b45309;
}
.status.reviewing {
  background: var(--color-secondary-soft);
  color: var(--color-primary);
}
.status.resolved {
  background: var(--color-cta-soft);
  color: #15803d;
}
.kp {
  font-family: var(--font-head);
  font-weight: 700;
  font-size: 15px;
}
.stem {
  font-size: 13.5px;
  line-height: 1.6;
  color: #475569;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.row-meta {
  display: flex;
  align-items: center;
  gap: 8px;
}
.att {
  font-size: 12px;
  font-weight: 700;
  color: #b45309;
  background: var(--color-warning-soft);
  padding: 2px 8px;
  border-radius: 999px;
}
.now-state {
  font-size: 12px;
  opacity: 0.75;
}
.actions {
  display: flex;
  gap: 8px;
}
.ghost,
.primary {
  border: 0;
  cursor: pointer;
  font-family: var(--font-body);
  font-weight: 700;
  font-size: 13px;
  padding: 8px 14px;
  border-radius: 12px;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.ghost {
  background: var(--color-primary-soft);
  color: var(--color-primary);
}
.primary {
  background: var(--color-cta);
  color: #fff;
}
.detail,
.redo {
  border-top: 1px dashed var(--color-line);
  padding-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.sec {
  font-size: 12px;
  font-weight: 800;
  color: var(--color-secondary);
}
.full {
  margin: 0;
  font-size: 13.5px;
  line-height: 1.7;
  background: var(--color-primary-soft);
  border-radius: 12px;
  padding: 10px 12px;
}
.redo-q {
  margin: 2px 0 0;
  font-size: 13.5px;
  font-weight: 700;
}
.redo-btns {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.redo-msg {
  margin: 0;
  font-size: 13px;
  font-weight: 700;
  color: #15803d;
  background: var(--color-cta-soft);
  padding: 8px 12px;
  border-radius: 12px;
}
.empty {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13.5px;
  color: var(--color-cta);
  font-weight: 700;
  padding: 16px 4px;
}
</style>
