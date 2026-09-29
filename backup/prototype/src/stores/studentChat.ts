import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { useEvidenceStore } from '@/stores/evidence'

export type CardKind =
  | 'task'
  | 'explain'
  | 'quiz'
  | 'review'
  | 'variant' // 变式 · 即时迁移
  | 'migration' // 迁移题 · 高价值
  | 'mastery-short'
  | 'mastery-stable'
  | 'stop'
  | 'suggest'
  | 'good'

export interface ChatMsg {
  id: number
  role: 'user' | 'bot'
  ts: number // 时间戳（按自然日分组的依据）
  text?: string
  card?: CardKind
  kpName?: string
  kpId?: string
}

let seq = 100
const nextId = () => ++seq

/* 意图路由 mock：关键词 → 技能（轻技能对话内卡片 / 重流程建议跳页）
   对齐 PRD v0.4.1：Chat = Control Plane（对话引导）、结构化 UI = Execution Plane */
function route(text: string): { card?: CardKind; reply?: string; kpName?: string; nav?: string } {
  if (/考|检验|测一测|试试/.test(text)) return { card: 'quiz', reply: '好呀！先考考你几道题～' }
  if (/复习|回顾|再练练/.test(text)) return { card: 'review', reply: '来，做一道间隔复习题（第 1 天）～' }
  if (/迁移/.test(text)) return { card: 'migration', reply: '好，做一道高价值迁移题，验证一下稳定性～' }
  if (/变式/.test(text)) return { card: 'variant', reply: '好，做一道变式题（即时迁移）～' }
  if (/讲|不懂|不会概念|讲讲/.test(text)) return { card: 'explain', reply: '好，我们一起看看分数乘分数～' }
  if (/教小鹿|讲给小鹿|费曼|我来讲|教教我/.test(text))
    return { reply: '好呀！把「分数乘分数」讲给小鹿听听，你能讲清楚就是真掌握～', nav: '/student/teachback' }
  if (/应用题|读不懂|读题/.test(text)) return { reply: '应用题读不懂的话，我们专门练一下读题三步法～', nav: '/student/reading' }
  if (/今天|任务|学什么|安排/.test(text)) return { card: 'task', reply: '这是今天的安排（最省时方案）：' }
  if (/会了|懂了|会做|明白/.test(text)) return { card: 'good', reply: '太棒了！这个知识点你已经会了，不用再花时间啦～' }
  if (/这道题|这题|不会做|帮我解/.test(text)) return { card: 'suggest', reply: '把这道题拍给小鹿看看吧，我们一步步来～', nav: '/student/photo' }
  return { card: 'suggest', reply: '这个有意思！不过我们先看看今天的数学吧～要复习、做迁移题，还是讲给小鹿听？' }
}

export const useStudentChat = defineStore('studentChat', () => {
  const ev = useEvidenceStore()
  const loggedIn = ref(false)
  const username = ref('')
  const messages = ref<ChatMsg[]>([])
  const typing = ref(false)
  /* 当前学习空间（可切换：学校 / 辅导班等） */
  const activeSpaceId = ref('sp_school')
  const activeSpace = computed(
    () => ev.spaces.find((s) => s.id === activeSpaceId.value) ?? ev.spaces[0],
  )
  function switchSpace(id: string) {
    if (ev.spaces.some((s) => s.id === id)) activeSpaceId.value = id
  }
  /* 更新当前学习进度（课程位置，非掌握度） */
  function setSpaceProgress(spaceId: string, label: string) {
    const sp = ev.spaces.find((s) => s.id === spaceId)
    if (sp) sp.progress = label
  }

  /* 当前学习知识点（默认演示：分数乘分数） */
  const activeKpId = ref('kp_frac_mul')
  const activeKpName = computed(() => ev.findConcept(activeKpId.value)?.name ?? '分数乘分数')

  /* 今日任务卡：只展示"真正值得做的动作 / 必要复习 / 已无高价值任务的结束提示"
     UNKNOWN 不进今日卡（红线二）；learning 仅在有证据（追踪）时作为"继续巩固"出现 */
  const plan = computed(() => {
    const tracked = ev.concepts.filter((c) => ev.isTracked(c.id))
    const shortKps = tracked.filter((c) => ev.snapshotOf(c.id)?.status === 'short')
    const learningKps = tracked.filter((c) => ev.snapshotOf(c.id)?.status === 'learning')
    const stableKps = ev.concepts.filter((c) => ev.snapshotOf(c.id)?.status === 'stable')
    return {
      review: shortKps.map((c) => ({ kp: c.name, day: '间隔复习 · 第 1 天' })),
      migration: shortKps.map((c) => ({ kp: c.name })),
      consolidate: learningKps.map((c) => ({ kp: c.name, note: '变式/迁移验证稳定性' })),
      mastered: stableKps.map((c) => c.name),
    }
  })

  /* 今日摘要：替代 streak（减负，不展示留存/打卡激励） */
  const todaySummary = computed(() => {
    const p = plan.value
    const tasks = p.review.length + p.migration.length + p.consolidate.length
    if (tasks === 0) return { text: '今天没有需要你继续处理的数学问题', done: true }
    return { text: `今天还需处理 ${tasks} 件事 · 约 ${tasks * 8} 分钟`, done: false }
  })

  function login(u: string) {
    loggedIn.value = true
    username.value = u || 'xiaolu_0608'
    // 今日安排是结构化决策对象（页面卡片），不重复推入对话
    messages.value = [
      { id: nextId(), role: 'bot', ts: Date.now(), text: `嗨，我是小鹿！今天想先复习「${activeKpName.value}」，还是做一道变式验证一下？` },
    ]
  }

  function logout() {
    loggedIn.value = false
    username.value = ''
    messages.value = []
  }

  function pushBot(m: Omit<ChatMsg, 'id' | 'role' | 'ts'>) {
    typing.value = true
    setTimeout(() => {
      messages.value.push({ id: nextId(), role: 'bot', ts: Date.now(), ...m })
      typing.value = false
    }, 450)
  }

  function send(text: string) {
    const t = text.trim()
    if (!t) return
    messages.value.push({ id: nextId(), role: 'user', ts: Date.now(), text: t })
    const r = route(t)
    if (r.reply) pushBot({ text: r.reply })
    if (r.card) pushBot({ card: r.card, kpName: r.kpName ?? activeKpName.value, kpId: activeKpId.value })
    return r.nav
  }

  /* 快捷技能按钮 */
  function quick(kind: 'quiz' | 'review' | 'variant' | 'migration' | 'task') {
    if (kind === 'quiz') pushBot({ card: 'quiz', text: '来，考考你～' })
    if (kind === 'review') pushBot({ card: 'review', text: '做一道间隔复习题（第 1 天）吧～' })
    if (kind === 'variant') pushBot({ card: 'variant', text: '做一道变式题（即时迁移）吧～' })
    if (kind === 'migration') pushBot({ card: 'migration', text: '做一道高价值迁移题，验证稳定性～' })
    if (kind === 'task') pushBot({ card: 'task' })
  }

  /* ---- 四态流转（演示估计器见 stores/evidence.ts，算法见系统设计） ---- */

  function onQuizDone(pass: boolean) {
    if (!pass) {
      pushBot({ text: '有两道要再巩固，我们再讲讲？' })
      return
    }
    const st = ev.applyEvidence(activeKpId.value, 'quiz', 'positive', '对话内检验', '客观题全对')
    if (st === 'learning') {
      pushBot({ text: '全对！不过先别急——单次全对不直接判定掌握。再做一道变式（即时迁移）验证一下？' })
      pushBot({ card: 'variant', kpName: activeKpName.value, kpId: activeKpId.value })
    } else {
      pushBot({ text: '全对，证据已入账～' })
    }
  }

  function onReviewDone(pass: boolean) {
    if (!pass) {
      pushBot({ text: '没答对没关系，我们回看讲解，明天再复习一次～' })
      return
    }
    ev.applyEvidence(activeKpId.value, 'review', 'positive', '间隔复习 · 第 1 天', '复习通过')
    pushBot({ text: '复习通过！距离稳定掌握又近一步，再做一道迁移题确认稳定性吧～' })
    pushBot({ card: 'migration', kpName: activeKpName.value, kpId: activeKpId.value })
  }

  function onVariantDone(pass: boolean) {
    if (!pass) {
      pushBot({ text: '变式没通过没关系，说明还不够稳，我们回看讲解巩固一下～' })
      return
    }
    const before = ev.snapshotOf(activeKpId.value)?.status
    const st = ev.applyEvidence(activeKpId.value, 'variant', 'positive', '变式 · 即时迁移', '做对 + 思路正确')
    if (before === 'short' && st === 'short') {
      pushBot({ text: '变式通过，短期掌握进一步确认！再做一道迁移题（换题型），就能稳定掌握啦～' })
      pushBot({ card: 'migration', kpName: activeKpName.value, kpId: activeKpId.value })
    } else if (st === 'short') {
      pushBot({ card: 'mastery-short', kpName: activeKpName.value })
      pushBot({ text: '变式通过 → 已短期掌握。再做一道迁移题（换题型），就能稳定掌握啦～' })
      pushBot({ card: 'migration', kpName: activeKpName.value, kpId: activeKpId.value })
    } else if (st === 'learning') {
      pushBot({ text: '变式通过，证据已入账～ 继续巩固' })
      pushBot({ card: 'variant', kpName: activeKpName.value, kpId: activeKpId.value })
    } else {
      pushBot({ text: '变式通过，证据已入账～' })
    }
  }

  function onMigrationDone(pass: boolean) {
    if (!pass) {
      pushBot({ text: '迁移没通过没关系，说明还不够稳，我们回看讲解巩固一下～' })
      return
    }
    const st = ev.applyEvidence(activeKpId.value, 'migration', 'positive', '迁移题 · 高价值迁移', '做对 + 思路正确')
    if (st === 'stable') {
      pushBot({ card: 'mastery-stable', kpName: activeKpName.value })
      pushBot({ card: 'stop' })
      ev.markTodayDone()
    } else if (st === 'short') {
      pushBot({ card: 'mastery-short', kpName: activeKpName.value })
      pushBot({ text: '再做一道迁移题，就能稳定掌握啦～' })
      pushBot({ card: 'migration', kpName: activeKpName.value, kpId: activeKpId.value })
    } else {
      pushBot({ text: '迁移题通过，证据已入账～' })
    }
  }

  /* P-C4 错题闭环完成：讲解后练习全对 + 变式（即时迁移）通过 → 短期已会 */
  function onExplainComplete() {
    ev.applyEvidence(activeKpId.value, 'practice', 'positive', '讲解后基础练习 3 道', '全对')
    const st = ev.applyEvidence(activeKpId.value, 'variant', 'positive', '变式 · 即时迁移', '做对 + 思路一句话正确')
    if (st === 'short') {
      pushBot({ card: 'mastery-short', kpName: activeKpName.value })
      pushBot({ text: '今天先不用再花时间练啦。再做一道迁移题验证稳定性，就可以收工去玩～' })
      pushBot({ card: 'migration', kpName: activeKpName.value, kpId: activeKpId.value })
    } else {
      pushBot({ text: `「${activeKpName.value}」的错题闭环完成，证据已入账～` })
    }
  }

  /* P-C7 Teach-back 完成：支持性证据，不单独切态（§14） */
  function onTeachBackDone() {
    ev.applyEvidence(activeKpId.value, 'feynman', 'positive', 'Teach-back 结构化自述', '要点核对全过')
    const st = ev.snapshotOf(activeKpId.value)?.status
    if (st === 'short') {
      pushBot({ text: '讲得很清楚！Teach-back 已作为重要证据入账。再做一道迁移题验证稳定性，就可以收工～' })
      pushBot({ card: 'migration', kpName: activeKpName.value, kpId: activeKpId.value })
    } else if (st === 'learning') {
      pushBot({ text: '讲给小鹿听很棒！要点全说到位，证据已入账。再做一道变式验证一下～' })
      pushBot({ card: 'variant', kpName: activeKpName.value, kpId: activeKpId.value })
    } else {
      pushBot({ text: '讲给小鹿听很棒！证据已入账～' })
    }
  }

  function onReadingDone() {
    pushBot({ text: '读题三步你掌握得很棒！以后再遇到应用题，先圈信息、复述、找关系～' })
  }

  function resetChat() {
    messages.value = []
  }

  return {
    ev,
    loggedIn,
    username,
    messages,
    typing,
    activeSpaceId,
    activeSpace,
    switchSpace,
    setSpaceProgress,
    activeKpId,
    activeKpName,
    plan,
    todaySummary,
    login,
    logout,
    send,
    quick,
    onQuizDone,
    onReviewDone,
    onVariantDone,
    onMigrationDone,
    onExplainComplete,
    onTeachBackDone,
    onReadingDone,
    resetChat,
  }
})
