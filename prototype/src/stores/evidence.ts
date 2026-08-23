/* ============================================================
   三端共享 Pinia store：证据账本 + 掌握度估计器(演示) + 政策引擎
   学生端 / 家长端 / 管理员端 共用同一份 mock 状态 → 联动演示
   - Concept 与 MasterySnapshot 分离
   - estimate/confidence/stability 由证据序列合成（非 state→score）
   - Evidence 区分 polarity（正负方向）与 informationValue（信息价值）
   算法（估计器公式 / 更新函数 / 信息增益 / 阈值校准）
   见《系统设计.md》——本文件仅做【演示规则】
   ============================================================ */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import {
  type AttentionState,
  type Concept,
  type ErrorRecord,
  type ErrorSource,
  type EvidenceRecord,
  type EvidenceType,
  type LearningSpace,
  type MasterySnapshot,
  type MasteryState,
  type Polarity,
  type PolicyDecision,
  type RuleConfig,
  type StudentAccount,
  type Textbook,
  seedAttention,
  seedConcepts,
  seedDecisions,
  seedErrors,
  seedEvidence,
  seedRules,
  seedSnapshots,
  seedSpaces,
  seedStudents,
  seedTextbooks,
  STATE_LABEL,
} from '@/data/sharedMock'

/* 演示信息价值（与正负方向分离）：
   高价值失败（延迟/迁移）比普通成功信息量更大（PRD §6.3） */
function infoValue(type: EvidenceType, polarity: Polarity): number {
  if (polarity === 'negative') {
    switch (type) {
      case 'migration':
        return 0.9
      case 'review':
        return 0.75
      case 'variant':
        return 0.7
      case 'quiz':
        return 0.5
      case 'practice':
        return 0.5
      default:
        return 0.4
    }
  }
  switch (type) {
    case 'migration':
      return 0.85
    case 'variant':
      return 0.7
    case 'feynman':
      return 0.6
    case 'review':
      return 0.55
    case 'quiz':
      return 0.5
    case 'practice':
      return 0.4
    case 'reading':
      return 0.4
    default:
      return 0.3
  }
}

/* 演示状态机：单条证据 → 状态迁移判定（产品规则见 PRD，公式见系统设计） */
function estimateStatus(
  status: MasteryState,
  type: EvidenceType,
  polarity: Polarity,
): MasteryState | null {
  if (polarity === 'negative') {
    // 单次错误不直接降级（§5.4）；仅高价值反证回退一档（演示）
    if (type === 'migration' || type === 'review') {
      if (status === 'stable') return 'short'
      if (status === 'short') return 'learning'
    }
    return null
  }
  switch (type) {
    case 'variant': // 变式（即时迁移）→ SHORT 的触发证据
      if (status === 'unknown') return 'learning'
      if (status === 'learning') return 'short'
      return null
    case 'migration': // 迁移题（高价值）→ STABLE 的关键证据
      if (status === 'unknown') return 'learning'
      if (status === 'learning') return 'short'
      if (status === 'short') return 'stable'
      return null
    case 'feynman':
      return null // Teach-back 为支持性证据，不单独切态（§14）
    case 'review':
      return null
    case 'quiz':
    case 'practice':
      if (status === 'unknown') return 'learning'
      return null
    default:
      return null
  }
}

/* 演示：由证据序列推导 estimate/confidence/stability（非 state→score） */
function computeEstimate(
  evs: EvidenceRecord[],
): { estimate: number; confidence: number; stability: number } {
  let score = 45
  const total = evs.length
  let pos = 0
  let neg = 0
  let decay = 1
  for (const e of evs) {
    score += (e.polarity === 'positive' ? 1 : -1) * e.informationValue * 30 * decay
    if (e.polarity === 'positive') pos++
    else neg++
    decay *= 0.92 // 时间衰减（演示）
  }
  score = Math.max(0, Math.min(100, Math.round(score)))
  const confidence = Math.max(0.3, Math.min(0.95, 0.3 + total * 0.08 + (score / 100) * 0.2))
  const stability = Math.max(
    0,
    (score / 100) * (0.5 + 0.5 * Math.min(1, pos / 4)) - neg * 0.02,
  )
  return {
    estimate: score,
    confidence: Number(confidence.toFixed(2)),
    stability: Number(Math.min(1, stability).toFixed(2)),
  }
}

function label(s: MasteryState): string {
  return STATE_LABEL[s]
}

function typeLabel(t: EvidenceType): string {
  return (
    {
      quiz: '检验',
      practice: '基础练习',
      variant: '变式',
      migration: '迁移题',
      review: '间隔复习',
      feynman: 'Teach-back',
      reading: '读题训练',
      entry: '录入',
    } as Record<EvidenceType, string>
  )[t]
}

function demoReason(
  from: MasteryState,
  to: MasteryState,
  type: EvidenceType,
  kpName: string,
): string {
  if (from === to) {
    return `证据入账，状态保持【${label(from)}】；未达下一档阈值（演示），继续收集证据。`
  }
  switch (to) {
    case 'learning':
      return `首次有效证据（${kpName}），从【${label(from)}】进入【学习中】；UNKNOWN≠未掌握，静默推进。`
    case 'short':
      return `${type === 'migration' ? '迁移题（高价值）通过' : '变式（即时迁移）通过'}，证据充分 → 判定【短期掌握】；安排间隔复习 + 一道迁移题验证稳定性。`
    case 'stable':
      return `高价值迁移题通过，估计器达到 STABLE 阈值（演示 0.8）→ 判定【稳定掌握】；执行停止策略：不再花时间主动练习。`
    default:
      return '证据入账。'
  }
}

function demoAction(to: MasteryState): string {
  switch (to) {
    case 'learning':
      return '安排讲解 + 基础练习'
    case 'short':
      return '安排间隔复习(1/3/7天) + 高价值迁移题'
    case 'stable':
      return '停止该知识点主动练习（减负）'
    default:
      return '保持观察'
  }
}

let seq = 1000
const nextId = (p: string) => `${p}-${++seq}`

function nowTime(): string {
  const d = new Date()
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

function freshSnapshot(c: Concept): MasterySnapshot {
  return {
    conceptId: c.id,
    status: 'unknown',
    estimate: 0,
    confidence: 0,
    stability: 0,
    evidenceCount: 0,
    lastPositiveAt: '',
    lastNegativeAt: '',
    nextReviewAt: '—',
  }
}

export const useEvidenceStore = defineStore('evidence', () => {
  const concepts = ref<Concept[]>(JSON.parse(JSON.stringify(seedConcepts)) as Concept[])
  const snapshots = ref<Record<string, MasterySnapshot>>(
    JSON.parse(
      JSON.stringify(Object.fromEntries(seedSnapshots.map((s) => [s.conceptId, s]))),
    ) as Record<string, MasterySnapshot>,
  )
  const evidence = ref<EvidenceRecord[]>(JSON.parse(JSON.stringify(seedEvidence)) as EvidenceRecord[])
  const errors = ref<ErrorRecord[]>(JSON.parse(JSON.stringify(seedErrors)) as ErrorRecord[])
  const decisions = ref<PolicyDecision[]>(JSON.parse(JSON.stringify(seedDecisions)) as PolicyDecision[])
  const spaces = ref<LearningSpace[]>(JSON.parse(JSON.stringify(seedSpaces)) as LearningSpace[])
  const students = ref<StudentAccount[]>(JSON.parse(JSON.stringify(seedStudents)) as StudentAccount[])
  const rules = ref<RuleConfig>(JSON.parse(JSON.stringify(seedRules)) as RuleConfig)
  const attention = ref<AttentionState>(JSON.parse(JSON.stringify(seedAttention)) as AttentionState)
  const textbooks = seedTextbooks as Textbook[] // 静态内容，非状态

  function findConcept(id: string): Concept | undefined {
    return concepts.value.find((c) => c.id === id)
  }
  function snapshotOf(id: string): MasterySnapshot | undefined {
    return snapshots.value[id]
  }
  function evidencesOf(id: string): EvidenceRecord[] {
    return evidence.value.filter((e) => e.kpId === id)
  }
  /* UNKNOWN 进入追踪的判定：有证据（错题/求助/检验失败/前置薄弱等触发过） */
  function isTracked(id: string): boolean {
    return evidencesOf(id).length > 0
  }

  /* 错题集：错题 = 证据原始对象，关联知识点 = 决策抽象对象 */
  function addError(input: {
    spaceId?: string
    conceptId: string
    conceptName: string
    source: ErrorSource
    stem: string
    attribution?: string
  }) {
    errors.value.push({
      id: nextId('err'),
      time: nowTime(),
      spaceId: input.spaceId ?? spaces.value[0]?.id ?? '',
      conceptId: input.conceptId,
      conceptName: input.conceptName,
      source: input.source,
      stem: input.stem,
      attribution: input.attribution ?? '待归因',
      status: 'pending',
      lastTriedAt: nowTime(),
    })
  }

  function resolveError(id: string) {
    const e = errors.value.find((x) => x.id === id)
    if (e) e.status = 'mastered'
  }

  function textbookOf(spaceId: string): Textbook | undefined {
    return textbooks.find((t) => t.spaceId === spaceId)
  }

  /* 核心：写入证据 → 证据合成估计 → 状态判定 → 必要时生成决策 */
  function applyEvidence(
    kpId: string,
    type: EvidenceType,
    polarity: Polarity,
    source: string,
    note: string,
  ): MasteryState | null {
    const concept = findConcept(kpId)
    if (!concept) return null

    const iv = infoValue(type, polarity)
    evidence.value.push({
      id: nextId('e'),
      time: nowTime(),
      kpId,
      kpName: concept.name,
      type,
      polarity,
      informationValue: iv,
      source,
      note,
    })

    let sn = snapshotOf(kpId)
    if (!sn) {
      sn = freshSnapshot(concept)
      snapshots.value[kpId] = sn
    }

    const evs = evidencesOf(kpId)
    const { estimate, confidence, stability } = computeEstimate(evs)
    const from = sn.status
    const to = estimateStatus(from, type, polarity) ?? from

    sn.evidenceCount = evs.length
    if (polarity === 'positive') sn.lastPositiveAt = nowTime()
    else sn.lastNegativeAt = nowTime()
    sn.estimate = estimate
    sn.confidence = confidence
    sn.stability = stability
    sn.nextReviewAt = to === 'stable' ? '—' : to === 'short' ? '明天' : '后天'

    const trigger = `${typeLabel(type)}${polarity === 'positive' ? '通过' : '未通过'} · ${source}`
    // 负证据自动收入错题集（拍照/做题失败），错题=证据原始对象
    if (polarity === 'negative' && type !== 'feynman' && type !== 'entry') {
      addError({
        conceptId: kpId,
        conceptName: concept.name,
        source: type as ErrorSource,
        stem: `${concept.name} · ${typeLabel(type)}题`,
        attribution: note.includes('归因') ? note : '待归因',
      })
    }
    if (to !== from) {
      sn.status = to
      decisions.value.push({
        id: nextId('d'),
        time: nowTime(),
        kpId,
        kpName: concept.name,
        trigger,
        action: demoAction(to),
        reason: demoReason(from, to, type, concept.name),
        fromState: from,
        toState: to,
      })
    } else {
      decisions.value.push({
        id: nextId('d'),
        time: nowTime(),
        kpId,
        kpName: concept.name,
        trigger,
        action: '证据入账，状态不变',
        reason: demoReason(from, from, type, concept.name),
        fromState: from,
        toState: from,
      })
    }
    return to
  }

  /* Attention Budget 消耗 */
  function spendProactiveAction() {
    attention.value.todayProactiveActions++
  }
  function spendReminder() {
    attention.value.todayReminders++
  }
  function addFocusMinutes(m: number) {
    attention.value.todayFocusMinutes += m
  }
  function markTodayDone() {
    attention.value.todayCompleted = true
  }

  function resetAll() {
    concepts.value = JSON.parse(JSON.stringify(seedConcepts)) as Concept[]
    snapshots.value = JSON.parse(
      JSON.stringify(Object.fromEntries(seedSnapshots.map((s) => [s.conceptId, s]))),
    ) as Record<string, MasterySnapshot>
    evidence.value = JSON.parse(JSON.stringify(seedEvidence)) as EvidenceRecord[]
    errors.value = JSON.parse(JSON.stringify(seedErrors)) as ErrorRecord[]
    decisions.value = JSON.parse(JSON.stringify(seedDecisions)) as PolicyDecision[]
    spaces.value = JSON.parse(JSON.stringify(seedSpaces)) as LearningSpace[]
    students.value = JSON.parse(JSON.stringify(seedStudents)) as StudentAccount[]
    rules.value = JSON.parse(JSON.stringify(seedRules)) as RuleConfig
    attention.value = JSON.parse(JSON.stringify(seedAttention)) as AttentionState
  }

  return {
    concepts,
    snapshots,
    evidence,
    errors,
    decisions,
    spaces,
    students,
    rules,
    attention,
    textbooks,
    findConcept,
    snapshotOf,
    evidencesOf,
    isTracked,
    addError,
    resolveError,
    textbookOf,
    applyEvidence,
    spendProactiveAction,
    spendReminder,
    addFocusMinutes,
    markTodayDone,
    resetAll,
  }
})
