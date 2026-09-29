/* ============================================================
   学生端语义层（Student Experience Semantics）
   把领域模型（Evidence / Mastery / Policy / 错题）翻译成孩子能懂的"产品语义"。
   学生端页面一律从本层取文案，不直接展示系统术语（UNKNOWN / Evidence / 迁移 / 稳定掌握…）。
   - UNKNOWN 对学生不可见：show=false（或弱化为"暂时不用管"）
   - 状态：LEARNING→正在学 / SHORT→刚刚会了 / STABLE→已经会了
   - 错题状态：pending→待处理 / reviewing→辅导中 / resolved→已解决
   - 按自然日分组由时间戳（occurredAt / ts）完成，而非 UI 文本判断
   ============================================================ */
import type { ErrorStatus, MasteryState } from '@/data/sharedMock'

export interface ChildState {
  text: string
  show: boolean // UNKNOWN 学生端不展示
}

export function childState(s: MasteryState | undefined): ChildState {
  switch (s) {
    case 'learning':
      return { text: '正在学', show: true }
    case 'short':
      return { text: '刚刚会了', show: true }
    case 'stable':
      return { text: '已经会了', show: true }
    default:
      return { text: '暂时不用管', show: false }
  }
}

export const ERROR_STATUS_CHILD: Record<ErrorStatus, string> = {
  pending: '待处理',
  reviewing: '辅导中',
  resolved: '已解决',
}

export function transitionChild(
  from: MasteryState | undefined,
  to: MasteryState | undefined,
): string {
  const f = childState(from)
  return `${f.show ? f.text : '—'} → ${childState(to).text}`
}

/* ---------------- 小鹿跨页面 Agent 文案（儿童语建议） ---------------- */
export function agentLineForConcept(name: string, s: MasteryState | undefined): string {
  switch (s) {
    case 'stable':
      return `「${name}」已经会了，暂时不用管它。`
    case 'short':
      return `「${name}」刚刚会了，还缺一次延迟的检验，过几天小鹿会提醒你复习一下。`
    case 'learning':
      return `「${name}」正在学，小鹿在收集证据；还差一次变式（或迁移）通过就能更确定。`
    default:
      return `「${name}」还没有发现需要处理的问题，先放着就好。`
  }
}

export function agentLineForWrongbook(
  kpName: string,
  kpState: MasteryState | undefined,
  resolved: boolean,
): string {
  if (resolved)
    return `这道题已经解决，证据已入账。保持住就好，小鹿会继续留意「${kpName}」。`
  if (kpState === 'short')
    return `这道题关联的「${kpName}」刚刚会了，还缺一次延迟迁移的证据，值得复习一次。`
  if (kpState === 'learning')
    return `这道题关联的「${kpName}」正在学，小鹿建议讲一讲、再做一道变式。`
  return `这道题关联的「${kpName}」还没有发现需要处理的问题，先放着。`
}

/* ---------------- 按自然日分组（领域层，基于时间戳） ---------------- */
export interface DayGroup<T> {
  key: string // 'YYYY-MM-DD'
  label: string // '今天' | '昨天' | '8月23日'
  items: T[]
}

export function dayKey(isoOrTs: string | number): string {
  const d = typeof isoOrTs === 'number' ? new Date(isoOrTs) : new Date(isoOrTs)
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

export function dayLabel(key: string): string {
  const today = dayKey(new Date().toISOString())
  const yesterday = dayKey(Date.now() - 86400000)
  if (key === today) return '今天'
  if (key === yesterday) return '昨天'
  const [, m, d] = key.split('-')
  return `${Number(m)}月${Number(d)}日`
}

export function groupByDay<T>(items: T[], pickKey: (item: T) => string): DayGroup<T>[] {
  const map = new Map<string, T[]>()
  for (const it of items) {
    const k = pickKey(it)
    if (!map.has(k)) map.set(k, [])
    map.get(k)!.push(it)
  }
  const keys = [...map.keys()].sort().reverse()
  return keys.map((k) => ({ key: k, label: dayLabel(k), items: map.get(k)! }))
}
