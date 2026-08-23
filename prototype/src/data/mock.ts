/* ============================================================
   mock 数据：学习空间 / 知识点 / 错题 / 归因对话脚本 / 练习与变式
   对齐 doc/产品设计.md（学习空间、范围护栏、归因、读题训练、变式验收）
   ============================================================ */

export interface Space {
  id: string
  name: string
  type: 'school' | 'tutoring'
  subject: string
  semester: string
  textbooks: { name: string; version: string }[]
  progress: { chapter: string; unit: string; kps: string[] }
  color: string
}

export const spaces: Space[] = [
  {
    id: 's1',
    name: '学校 · 六年级上册数学',
    type: 'school',
    subject: '数学',
    semester: '2026 秋季学期',
    textbooks: [{ name: '人教版 数学 六年级上册', version: '人教版' }],
    progress: {
      chapter: '第一单元 分数乘法',
      unit: '第 2 节 一个数乘分数',
      kps: ['分数乘法', '求一个数的几分之几'],
    },
    color: '#4F46E5',
  },
  {
    id: 's2',
    name: '辅导班 · 学而思思维',
    type: 'tutoring',
    subject: '数学',
    semester: '2026 秋季学期',
    textbooks: [
      { name: '学而思 思维训练 六年级', version: '学而思' },
      { name: '校内同步提升讲义', version: '自定义上传' },
    ],
    progress: {
      chapter: '专题二 分数与百分数',
      unit: '第 1 讲 分数应用进阶',
      kps: ['分数应用题', '单位"1"的确定'],
    },
    color: '#22C55E',
  },
]

export interface Kp {
  id: string
  name: string
  domain: string
  prerequisites: string[]
  source: string
}

export const knowledgePoints: Kp[] = [
  { id: 'kp1', name: '分数乘法', domain: '数与代数', prerequisites: ['分数意义', '整数乘法'], source: '人教版六上 P2-13' },
  { id: 'kp2', name: '求一个数的几分之几', domain: '数与代数', prerequisites: ['分数乘法', '分数意义'], source: '人教版六上 P8-11' },
  { id: 'kp3', name: '分数应用题', domain: '应用', prerequisites: ['求一个数的几分之几'], source: '学而思·分数应用进阶' },
]

export interface ErrorRecord {
  id: string
  imageHint: string
  ocrText: string
  kpId: string
  spaceId: string
  wrongAnswer: string
  source: string
}

/* 示例错题：分数乘法应用题（女儿的真实痛点：应用题/读题失分） */
export const sampleError: ErrorRecord = {
  id: 'e1',
  imageHint: '拍照样例：练习册第 12 页第 3 题',
  ocrText:
    '张叔叔用一根长 5/6 米的彩带做一个中国结，用去了全长的 2/3。用去了多少米？',
  kpId: 'kp2',
  spaceId: 's1',
  wrongAnswer: '5/6 − 2/3 = 1/6（米）',
  source: '人教版 六上 练习三 P13-3',
}

/* 归因对话脚本：决策树（§8.2） */
export interface DialogueStep {
  id: string
  speaker: 'deer' | 'child'
  text: string
  options?: { label: string; next?: string; attribution?: string }[]
}

export const attributionDialogue: DialogueStep[] = [
  {
    id: 'q1',
    speaker: 'deer',
    text: '我们来看看这道题。你先说说，这道题考的是哪个知识点呀？',
    options: [
      { label: '分数加减法', next: 'q1b' },
      { label: '求一个数的几分之几（分数乘法）', next: 'q2' },
      { label: '说不清楚', next: 'q1b' },
    ],
  },
  {
    id: 'q1b',
    speaker: 'deer',
    text: '没关系～这道题其实和"分数乘法"有关。你能把题目里给了哪些条件、要求什么，用自己的话说一遍吗？',
    options: [
      { label: '彩带长 5/6 米，用去了 2/3，问用去多少米', next: 'q3' },
      { label: '漏掉"用去了全长的 2/3"这个条件', next: 'read' },
      { label: '看错数字/单位', next: 'read' },
    ],
  },
  {
    id: 'q2',
    speaker: 'deer',
    text: '很好！那你能把题目里给了哪些条件、要求什么，用自己的话说一遍吗？',
    options: [
      { label: '完整说出：全长 5/6 米，用去 2/3，求用去多少米', next: 'q3' },
      { label: '漏了条件 / 说不清', next: 'read' },
    ],
  },
  {
    id: 'q3',
    speaker: 'deer',
    text: '如果我把数字换成小数，比如 0.8 米用去 2/3，你还知道怎么算吗？',
    options: [
      { label: '会：0.8 × 2/3（求一个数的几分之几用乘法）', next: 'slip' },
      { label: '不太确定', next: 'concept' },
    ],
  },
]

export type Attribution = '审题失误' | '概念不清' | '粗心' | '思路混乱'

export const attributionResult: Record<string, Attribution> = {
  read: '审题失误',
  slip: '粗心',
  concept: '概念不清',
}

/* 读题训练三步（§5.5 / §8.6） */
export interface ReadingStep {
  id: string
  title: string
  prompt: string
  hint: string
  confirmText: string
}

export const readingSteps: ReadingStep[] = [
  {
    id: 'r1',
    title: '① 圈关键信息',
    prompt: '先别急着算，我们把题目里的关键信息找出来：哪些是已知条件？哪个是要求的问题？',
    hint: '关键条件：全长 5/6 米；用去了全长的 2/3；问题：用去了多少米？',
    confirmText: '我圈出来了',
  },
  {
    id: 'r2',
    title: '② 复述题意',
    prompt: '用自己的话说一遍：这道题让我求什么？给了哪些条件？',
    hint: '"一根 5/6 米长的彩带，用去了 2/3，求用去的长度。"',
    confirmText: '我说完了',
  },
  {
    id: 'r3',
    title: '③ 数量关系',
    prompt: '条件和问题之间是什么关系？能写成一个算式吗？（提示：求一个数的几分之几 → 用乘法）',
    hint: '用去的长度 = 全长 × 用去的比例，即 5/6 × 2/3',
    confirmText: '明白了，我重做',
  },
]

/* 讲解内容（§5.3：绑定教材 + 多角度 + TTS） */
export const explainContent = {
  title: '求一个数的几分之几',
  source: '人教版六上 P8-11',
  body: '"求一个数的几分之几"就是求这个数乘上几分之几，用乘法。\n\n比如"5/6 米用去了 2/3"，就是把 5/6 米平均分成 3 份，取其中 2 份。\n\n我们换个角度想：把彩带画成一条线段，全长 5/6 米看作 1 份，用去 2/3 就是取这样的 2 份——也就是全长 × 2/3。',
  secondAngle:
    '再换个讲法：你想买一瓶 12 元的饮料，只带了 2/3 的钱，那你有 12 × 2/3 = 8 元。道理一样——"的几分之几"就是"乘几分之几"。',
  ttsAvailable: true,
}

/* 基础练习（预置题库，§5.4） */
export interface Question {
  id: string
  text: string
  answer: string
  distractors: string[]
}

export const practiceQuestions: Question[] = [
  {
    id: 'p1',
    text: '一块布长 3/4 米，用去了 1/3。用去了多少米？',
    answer: '3/4 × 1/3 = 1/4（米）',
    distractors: ['3/4 − 1/3 = 5/12', '3/4 ÷ 1/3 = 9/4'],
  },
  {
    id: 'p2',
    text: '一本书有 40 页，小明看了全书的 3/5。看了多少页？',
    answer: '40 × 3/5 = 24（页）',
    distractors: ['40 − 3/5 = 39 又 2/5', '40 ÷ 3/5 = 66 又 2/3'],
  },
  {
    id: 'p3',
    text: '果园有 60 棵苹果树，梨树的棵数是苹果树的 5/6。梨树有多少棵？',
    answer: '60 × 5/6 = 50（棵）',
    distractors: ['60 − 5/6 = 59 又 1/6', '60 ÷ 5/6 = 72'],
  },
]

/* 变式验收（三不变一变，§5.4 / §8.4） */
export const variantQuestion: Question = {
  id: 'v1',
  text: '王阿姨有 4/5 千克面粉，做馒头用了其中的 3/4。做馒头用了多少千克面粉？（情境、数字、表述都变了，但考的还是同一个知识点哦）',
  answer: '4/5 × 3/4 = 3/5（千克）',
  distractors: ['4/5 − 3/4 = 1/20', '4/5 ÷ 3/4 = 16/15'],
}

/* 掌握度画像（mock） */
export const masteryPillars = [
  { kp: '分数乘法', state: 'mastered' },
  { kp: '求一个数的几分之几', state: 'inprogress' },
  { kp: '分数应用题', state: 'focus' },
]

/* 日报/周报 mock */
export const dailyReport = {
  date: '8月23日',
  items: [
    { label: '学习时长', value: '22 分钟' },
    { label: '完成知识点', value: '1 个' },
    { label: '错题闭环', value: '1 道' },
  ],
  alert: '「求一个数的几分之几」已连续 2 天出现读题失分，小鹿已加练读题训练。',
}

export const weeklyReport = {
  week: '本周（8/17 - 8/23）',
  masteredRate: 68,
  rateTrend: '+6%',
  weakness: [
    { kp: '求一个数的几分之几', count: 4, type: '审题失误' },
    { kp: '分数乘法计算', count: 2, type: '粗心' },
  ],
  suggestion: '下周重点：应用题读题训练 + 分数乘法变式巩固；建议每天 15-30 分钟，优先完成 2 个读题练习。',
}

/* ==================== Phase B：摸底 / 复习 / 错题详情 / 录入 / 记忆 / 设置 ==================== */

/* 摸底（J2 冷启动）：3 道摸底题 */
export interface QuizQuestion {
  id: string
  text: string
  options: string[]
  answer: string
  kp: string
}

export const mogiQuestions: QuizQuestion[] = [
  {
    id: 'm1',
    text: '5 × 2/3 等于多少？',
    options: ['10/3', '10/15', '7/3', '5 又 2/3'],
    answer: '10/3',
    kp: '分数乘法',
  },
  {
    id: 'm2',
    text: '一根绳子长 3/4 米，用去了 1/2，用去了多少米？',
    options: ['3/8 米', '1/4 米', '3/2 米', '1/8 米'],
    answer: '3/8 米',
    kp: '求一个数的几分之几',
  },
  {
    id: 'm3',
    text: '果园有 60 棵苹果树，梨树是苹果树的 2/5，梨树有多少棵？',
    options: ['24 棵', '12 棵', '150 棵', '58 棵'],
    answer: '24 棵',
    kp: '分数应用题',
  },
]

/* 间隔复习（J4）任务与题目 */
export interface ReviewTask {
  id: string
  kp: string
  day: number
  due: string
  state: '待复习' | '已完成'
}

export const reviewTasks: ReviewTask[] = [
  { id: 'r1', kp: '求一个数的几分之几', day: 1, due: '今天', state: '待复习' },
  { id: 'r2', kp: '分数乘法', day: 3, due: '今天', state: '待复习' },
  { id: 'r3', kp: '分数应用题', day: 7, due: '3 天后', state: '待复习' },
]

export const reviewQuestions: QuizQuestion[] = [
  {
    id: 'rv1',
    text: '一本书有 45 页，小红看了全书的 2/3，看了多少页？（复习：求一个数的几分之几）',
    options: ['30 页', '15 页', '22 页', '35 页'],
    answer: '30 页',
    kp: '求一个数的几分之几',
  },
  {
    id: 'rv2',
    text: '5/6 × 2/3 计算结果是？（复习：分数乘法）',
    options: ['5/9', '10/18', '7/9', '15/12'],
    answer: '5/9',
    kp: '分数乘法',
  },
]

/* 错题详情列表（家长高参与） */
export interface ErrorDetail {
  id: string
  kp: string
  attribution: string
  time: string
  text: string
  status: '短期掌握' | '攻克中' | '需关注'
  timeline: string[]
}

export const errorList: ErrorDetail[] = [
  {
    id: 'e1',
    kp: '求一个数的几分之几',
    attribution: '审题失误',
    time: '8月23日 17:02',
    text: '张叔叔用一根长 5/6 米的彩带做一个中国结，用去了全长的 2/3。用去了多少米？',
    status: '短期掌握',
    timeline: ['收录', '归因（审题失误）', '读题训练', '讲解', '练习全对', '变式通过'],
  },
  {
    id: 'e2',
    kp: '分数乘法计算',
    attribution: '粗心',
    time: '8月22日 16:48',
    text: '计算：3/7 × 14 = ?（把 3/7 × 14 算成 14/21）',
    status: '攻克中',
    timeline: ['收录', '归因（粗心）', '检查习惯训练', '变式通过'],
  },
  {
    id: 'e3',
    kp: '分数应用题',
    attribution: '概念不清',
    time: '8月21日 17:10',
    text: '单位"1"的确定：把 20 吨看作单位"1"，求它的 3/5 是多少。',
    status: '需关注',
    timeline: ['收录', '归因（概念不清）', '讲解中'],
  },
]

/* 家长录入（J6） */
export const parentNotes = {
  teacher: '老师说女儿分数应用题常漏条件，建议加强读题训练。',
  observation: '她口算不错，但一遇到长题干的大题就容易慌。',
  materials: ['校内同步提升讲义.pdf', '学而思 分数应用进阶.pdf'],
}

/* 记忆列表（§8.8） */
export interface MemoryItem {
  id: string
  type: '事实' | '偏好' | '状态'
  content: string
  source: string
  time: string
  confidence: number
}

export const memoryItems: MemoryItem[] = [
  { id: 'mem1', type: '事实', content: '「求一个数的几分之几」于 8/23 达到短期掌握', source: '会话#123', time: '8月23日', confidence: 0.95 },
  { id: 'mem2', type: '偏好', content: '更喜欢图形/线段讲解，文字长段落容易走神', source: '会话#98', time: '8月22日', confidence: 0.8 },
  { id: 'mem3', type: '状态', content: '对应用题（长题干）有畏难情绪，需要先鼓励再引导', source: '会话#110', time: '8月22日', confidence: 0.85 },
  { id: 'mem4', type: '事实', content: '分数乘法计算错误多为粗心（倒数抄错/约分遗漏）', source: '会话#87', time: '8月20日', confidence: 0.9 },
]

/* 家长设置（J7） */
export const parentSettings = {
  tierOptions: [
    { id: 'low', label: '低参与（默认）', desc: '只看每周周报' },
    { id: 'mid', label: '中参与', desc: '加看每日日报 + 异常告警' },
    { id: 'high', label: '高参与', desc: '错题详情 + 家长录入' },
  ],
  dailyLimit: 30,
  lockEnabled: false,
}
