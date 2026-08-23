/* ============================================================
   三端共享 mock 数据（学生端 / 家长端 / 管理员端 共用同一份状态）
   对齐 doc/产品设计.md v0.4.1（证据驱动的学习决策引擎）
   领域模型：Concept（知识点本体）与 MasterySnapshot（掌握快照）分离
   - UNKNOWN ≠ 未掌握：unknown 默认静默，仅由证据触发进入追踪
   - Evidence 区分 polarity（正/负方向）与 informationValue（信息价值）
   算法（估计器公式 / 信息增益 / 阈值校准）见《系统设计.md》
   本文件中的 estimate / confidence / stability 均为【演示值】
   ============================================================ */

export type MasteryState = 'unknown' | 'learning' | 'short' | 'stable'

export const STATE_LABEL: Record<MasteryState, string> = {
  unknown: '未接触',
  learning: '学习中',
  short: '短期掌握',
  stable: '稳定掌握',
}

export const STATE_ORDER: MasteryState[] = ['unknown', 'learning', 'short', 'stable']

export type Polarity = 'positive' | 'negative'

export type EvidenceType =
  | 'quiz'
  | 'practice'
  | 'variant' // 变式（即时迁移）
  | 'migration' // 迁移题（高价值迁移）
  | 'review'
  | 'feynman'
  | 'reading'
  | 'entry'

export const EVIDENCE_TYPE_LABEL: Record<EvidenceType, string> = {
  quiz: '检验',
  practice: '基础练习',
  variant: '变式 · 即时迁移',
  migration: '迁移题 · 高价值',
  review: '间隔复习',
  feynman: 'Teach-back 自述',
  reading: '读题训练',
  entry: '录入 / 观察',
}

/* ---------- Concept：知识点本体（版本无关，去年级化） ---------- */
export interface Concept {
  id: string
  name: string
  domain: string
  important: boolean
  prerequisites: string[]
}

/* ---------- MasterySnapshot：某学生对某知识点的掌握快照 ---------- */
export interface MasterySnapshot {
  conceptId: string
  status: MasteryState
  estimate: number // 演示值：由证据合成（非 state→score）
  confidence: number // 演示值：0-1
  stability: number // 演示值：0-1
  evidenceCount: number
  lastPositiveAt: string
  lastNegativeAt: string
  nextReviewAt: string
}

export interface EvidenceRecord {
  id: string
  time: string // 'HH:MM' / '周一 17:05'
  kpId: string
  kpName: string
  type: EvidenceType
  polarity: Polarity // 正/负方向
  informationValue: number // 演示值：信息价值（与方向分离）
  source: string // 证据来源
  note: string
}

export interface PolicyDecision {
  id: string
  time: string
  kpId: string
  kpName: string
  trigger: string // 触发证据摘要
  action: string // 输出 Action
  reason: string // 决策理由（可解释性）
  fromState: MasteryState
  toState: MasteryState
}

export interface LearningSpace {
  id: string
  name: string
  studentName: string
  textbook: string
  progress: string
  boundKp: number
  trackedKp: number
  status: 'active' | 'archived'
}

export interface StudentAccount {
  id: string
  username: string
  nickname: string
  grade: string
  status: 'active' | 'paused'
  createdAt: string
  spaces: number
}

export interface RuleConfig {
  dailyProactiveActionLimit: number // 每日主动动作上限
  conceptProactiveReminderLimit: number // 单知识点主动提醒上限
  quietHoursStart: string // 静默时段开始
  quietHoursEnd: string // 静默时段结束
  reviewIntervals: number[] // 间隔复习天数
  migrationVariantCount: number // SHORT→STABLE 需通过的高价值迁移题数
  stopAfterStable: boolean // 稳定掌握后是否停止该知识点
}

export interface AttentionState {
  todayProactiveActions: number
  todayReminders: number
  todayFocusMinutes: number
  todayCompleted: boolean // 今日是否已结束（停止语义）
}

export const DEMO_NOTE = '演示数据 · 算法见《系统设计.md》'

/* ---------------- 知识点本体（六年级上 · 人教） ---------------- */
export const seedConcepts: Concept[] = [
  { id: 'kp_frac_mean', name: '分数意义', domain: '数与运算', important: false, prerequisites: [] },
  { id: 'kp_frac_mul_int', name: '分数乘整数', domain: '数与运算', important: true, prerequisites: ['kp_frac_mean'] },
  { id: 'kp_frac_mul', name: '分数乘分数', domain: '数与运算', important: true, prerequisites: ['kp_frac_mul_int'] },
  { id: 'kp_frac_of_num', name: '求一个数的几分之几', domain: '数与运算', important: true, prerequisites: ['kp_frac_mul'] },
  { id: 'kp_simplify', name: '分数乘法·约分与运算律', domain: '数与运算', important: false, prerequisites: ['kp_frac_mul'] },
  { id: 'kp_frac_app', name: '分数乘法应用题', domain: '解决问题', important: true, prerequisites: ['kp_frac_of_num'] },
  { id: 'kp_reciprocal', name: '倒数', domain: '数与运算', important: false, prerequisites: ['kp_frac_mul'] },
]

/* ---------------- 掌握快照（每概念一条） ---------------- */
export const seedSnapshots: MasterySnapshot[] = [
  {
    conceptId: 'kp_frac_mean', status: 'stable', estimate: 96, confidence: 0.93, stability: 0.95,
    evidenceCount: 4, lastPositiveAt: '上周五', lastNegativeAt: '', nextReviewAt: '—',
  },
  {
    conceptId: 'kp_frac_mul_int', status: 'stable', estimate: 92, confidence: 0.9, stability: 0.91,
    evidenceCount: 4, lastPositiveAt: '周一 17:18', lastNegativeAt: '', nextReviewAt: '—',
  },
  {
    conceptId: 'kp_frac_mul', status: 'learning', estimate: 60, confidence: 0.58, stability: 0.4,
    evidenceCount: 2, lastPositiveAt: '今天 17:02', lastNegativeAt: '周二 17:02', nextReviewAt: '明天',
  },
  {
    conceptId: 'kp_frac_of_num', status: 'unknown', estimate: 0, confidence: 0, stability: 0,
    evidenceCount: 0, lastPositiveAt: '', lastNegativeAt: '', nextReviewAt: '—',
  },
  {
    conceptId: 'kp_simplify', status: 'learning', estimate: 48, confidence: 0.5, stability: 0.35,
    evidenceCount: 1, lastPositiveAt: '', lastNegativeAt: '周三 17:20', nextReviewAt: '明天',
  },
  {
    conceptId: 'kp_frac_app', status: 'unknown', estimate: 0, confidence: 0, stability: 0,
    evidenceCount: 0, lastPositiveAt: '', lastNegativeAt: '', nextReviewAt: '—',
  },
  {
    conceptId: 'kp_reciprocal', status: 'unknown', estimate: 0, confidence: 0, stability: 0,
    evidenceCount: 0, lastPositiveAt: '', lastNegativeAt: '', nextReviewAt: '—',
  },
]

/* ---------------- 证据账本（本周已发生的过往事件） ---------------- */
export const seedEvidence: EvidenceRecord[] = [
  {
    id: 'e-101', time: '周一 17:05', kpId: 'kp_frac_mul_int', kpName: '分数乘整数',
    type: 'practice', polarity: 'positive', informationValue: 0.4,
    source: '人教六上 P2 例题后练习', note: '3/4 × 8 等 3 道全对',
  },
  {
    id: 'e-102', time: '周一 17:12', kpId: 'kp_frac_mul_int', kpName: '分数乘整数',
    type: 'variant', polarity: 'positive', informationValue: 0.7,
    source: '变式题 · 即时迁移', note: '换个情境仍会做，思路一句话正确',
  },
  {
    id: 'e-103', time: '周一 17:15', kpId: 'kp_frac_mul_int', kpName: '分数乘整数',
    type: 'review', polarity: 'positive', informationValue: 0.55,
    source: '间隔复习 · 第 1 天', note: '复习通过，进入第 3 天间隔',
  },
  {
    id: 'e-104', time: '周一 17:18', kpId: 'kp_frac_mul_int', kpName: '分数乘整数',
    type: 'migration', polarity: 'positive', informationValue: 0.85,
    source: '迁移题 · 高价值（应用题）', note: '跨题型仍正确',
  },
  {
    id: 'e-201', time: '周二 17:02', kpId: 'kp_frac_mul', kpName: '分数乘分数',
    type: 'quiz', polarity: 'negative', informationValue: 0.5,
    source: '课后检验 2/5 × 5/6', note: '归因：粗心（最后一步约分错）',
  },
  {
    id: 'e-202', time: '今天 17:02', kpId: 'kp_frac_mul', kpName: '分数乘分数',
    type: 'practice', polarity: 'positive', informationValue: 0.4,
    source: '讲解后基础练习 3 道', note: '归因后重新练习，全对',
  },
  {
    id: 'e-301', time: '周三 17:20', kpId: 'kp_simplify', kpName: '分数乘法·约分与运算律',
    type: 'quiz', polarity: 'negative', informationValue: 0.5,
    source: '课堂小测', note: '归因：概念不清（运算律混淆）',
  },
]

/* ---------------- 决策记录（政策引擎，本周） ---------------- */
export const seedDecisions: PolicyDecision[] = [
  {
    id: 'd-101', time: '周一 17:18', kpId: 'kp_frac_mul_int', kpName: '分数乘整数',
    trigger: '基础练习全对 + 变式(即时迁移)通过 + 复习通过 + 迁移题通过',
    action: '判定稳定掌握 → 停止该知识点主动练习',
    reason: '多条独立证据一致通过，含高价值迁移证据，估计器达到 STABLE 阈值（演示 0.8）。',
    fromState: 'short', toState: 'stable',
  },
  {
    id: 'd-201', time: '今天 17:05', kpId: 'kp_frac_mul', kpName: '分数乘分数',
    trigger: '归因(粗心) + 讲解后基础练习全对',
    action: '状态保持【学习中】→ 安排变式验收',
    reason: '单次全对不直接切换状态；待变式（即时迁移）证据后再判定。',
    fromState: 'learning', toState: 'learning',
  },
]

/* ---------------- 学习空间 / 学生账号 ---------------- */
export const seedSpaces: LearningSpace[] = [
  {
    id: 'sp_school', name: '学校 · 六年级上册数学', studentName: '小鹿同学',
    textbook: '人教版 六上（1-4 单元）', progress: '第一单元 分数乘法 · 第 2 节',
    boundKp: 7, trackedKp: 4, status: 'active',
  },
  {
    id: 'sp_tutor', name: '辅导班 · 思维拓展', studentName: '小鹿同学',
    textbook: '自编专题（分数与比）', progress: '专题 2 · 分数应用',
    boundKp: 5, trackedKp: 2, status: 'active',
  },
]

export const seedStudents: StudentAccount[] = [
  {
    id: 's_1', username: 'xiaolu_0608', nickname: '小鹿同学', grade: '六年级',
    status: 'active', createdAt: '2026-08-01', spaces: 2,
  },
]

/* ---------------- 规则配置（Attention Budget MVP 默认值 §8.3） ---------------- */
export const seedRules: RuleConfig = {
  dailyProactiveActionLimit: 3,
  conceptProactiveReminderLimit: 1,
  quietHoursStart: '21:00',
  quietHoursEnd: '07:00',
  reviewIntervals: [1, 3, 7],
  migrationVariantCount: 1,
  stopAfterStable: true,
}

export const seedAttention: AttentionState = {
  todayProactiveActions: 1,
  todayReminders: 0,
  todayFocusMinutes: 20,
  todayCompleted: false,
}

/* ---------------- 教材大纲（学习空间 ↔ 章/节/知识点，Curriculum 层） ---------------- */
export interface TextbookSection {
  id: string
  title: string
  conceptIds: string[]
}
export interface TextbookUnit {
  id: string
  title: string
  sections: TextbookSection[]
}
export interface Textbook {
  spaceId: string
  name: string
  grade: string
  units: TextbookUnit[]
}

export const seedTextbooks: Textbook[] = [
  {
    spaceId: 'sp_school',
    name: '人教版 六年级上册',
    grade: '六年级',
    units: [
      {
        id: 'u1',
        title: '第 1 单元 分数乘法',
        sections: [
          { id: 'u1s1', title: '1.1 分数乘整数', conceptIds: ['kp_frac_mul_int'] },
          { id: 'u1s2', title: '1.2 分数乘分数', conceptIds: ['kp_frac_mul'] },
          { id: 'u1s3', title: '1.3 约分与运算律', conceptIds: ['kp_simplify'] },
          { id: 'u1s4', title: '1.4 求一个数的几分之几', conceptIds: ['kp_frac_of_num'] },
          { id: 'u1s5', title: '1.5 分数乘法应用题', conceptIds: ['kp_frac_app'] },
          { id: 'u1s6', title: '1.6 倒数', conceptIds: ['kp_reciprocal'] },
        ],
      },
      { id: 'u2', title: '第 2 单元 位置与方向', sections: [] },
      { id: 'u3', title: '第 3 单元 分数除法', sections: [] },
    ],
  },
  {
    spaceId: 'sp_tutor',
    name: '辅导班 · 思维拓展',
    grade: '六年级',
    units: [
      {
        id: 't1',
        title: '专题 1 分数初步',
        sections: [
          { id: 't1s1', title: '1.1 分数意义', conceptIds: ['kp_frac_mean'] },
          { id: 't1s2', title: '1.2 分数乘除', conceptIds: ['kp_frac_mul_int', 'kp_frac_mul'] },
        ],
      },
      {
        id: 't2',
        title: '专题 2 分数应用',
        sections: [
          { id: 't2s1', title: '2.1 实际问题', conceptIds: ['kp_frac_of_num', 'kp_frac_app'] },
        ],
      },
      { id: 't3', title: '专题 3 比与比例', sections: [] },
    ],
  },
]

/* ---------------- 错题集（错题 = 证据原始对象，关联知识点 = 决策抽象对象） ---------------- */
export type ErrorSource = 'photo' | 'quiz' | 'practice' | 'variant' | 'migration' | 'review' | 'reading'

export const ERROR_SOURCE_LABEL: Record<ErrorSource, string> = {
  photo: '拍照上传',
  quiz: '检验',
  practice: '基础练习',
  variant: '变式',
  migration: '迁移题',
  review: '间隔复习',
  reading: '读题训练',
}

export type ErrorStatus = 'pending' | 'reviewing' | 'mastered'

export interface ErrorRecord {
  id: string
  time: string
  spaceId: string
  conceptId: string
  conceptName: string
  source: ErrorSource
  stem: string
  attribution: string
  status: ErrorStatus
  lastTriedAt?: string
}

export const seedErrors: ErrorRecord[] = [
  {
    id: 'err-1', time: '8月23日', spaceId: 'sp_school',
    conceptId: 'kp_frac_mul', conceptName: '分数乘分数',
    source: 'photo',
    stem: '张叔叔用一根长 5/6 米的彩带做中国结，用去了全长的 2/3。用去了多少米？',
    attribution: '审题失误', status: 'pending',
  },
  {
    id: 'err-2', time: '8月20日', spaceId: 'sp_school',
    conceptId: 'kp_frac_mean', conceptName: '分数意义',
    source: 'photo',
    stem: '判断：分数的分子可以大于分母吗？',
    attribution: '概念不清', status: 'mastered', lastTriedAt: '8月21日',
  },
  {
    id: 'err-3', time: '8月23日', spaceId: 'sp_school',
    conceptId: 'kp_simplify', conceptName: '分数乘法·约分与运算律',
    source: 'quiz',
    stem: '课堂小测：运用乘法分配律简便计算分数乘法',
    attribution: '概念不清', status: 'pending',
  },
]
