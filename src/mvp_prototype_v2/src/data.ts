import type {
  ChatMessage, LearningState, LearningOverview, TextbookData, WrongQuestion, ErrorCategory
} from './types';

// ========== 学习总览数据 ==========
export const learningOverview: LearningOverview = {
  chapter: '比例的应用',
  targetAssessment: {
    targetName: '比例的应用',
    overallStatus: 'developing',
    claimCount: 4,
    evidence: {
      positive: 12,
      negative: 3,
      pending: 2,
      conflict: false,
    },
    dimensions: [
      { dimension: 'independent', label: '独立完成', status: 'mastered', evidenceCount: 5 },
      { dimension: 'understanding', label: '理解解释', status: 'developing', evidenceCount: 4 },
      { dimension: 'transfer', label: '迁移应用', status: 'insufficient', evidenceCount: 1 },
      { dimension: 'retention', label: '延迟保持', status: 'insufficient', evidenceCount: 0 },
    ],
    lastUpdated: '今天 14:30',
  },
  abilities: [
    { name: '计算能力', score: 82 },
    { name: '应用能力', score: 58 },
    { name: '逻辑推理', score: 70 },
    { name: '审题能力', score: 62 },
    { name: '空间想象', score: 75 },
  ],
  trend: [
    { date: '10-10', mastery: 52 },
    { date: '10-11', mastery: 55 },
    { date: '10-12', mastery: 54 },
    { date: '10-13', mastery: 58 },
    { date: '10-14', mastery: 60 },
    { date: '10-15', mastery: 62 },
    { date: '10-16', mastery: 65 },
  ],
  weakPoints: [
    { name: '比较标准量', mastery: 45, reason: '连续3次在"先涨后降"类题目中出错', suggestion: '建议先复习标准量概念，再做5道专项练习' },
    { name: '连续变化问题', mastery: 50, reason: '多步计算时容易混淆每一步的标准量', suggestion: '建议用分步列式法，每步标注标准量' },
  ],
  rhythm: { weekMinutes: 145, exercisesDone: 28, correctRate: 71, streak: 5 },
  suggestions: [
    { priority: 'high', action: '复习"比较标准量"并完成专项练习', reason: '这是当前最薄弱的知识点，且是后续内容的基础' },
    { priority: 'medium', action: '完成一次分数应用的综合检测', reason: '最近一周掌握度稳步提升，适合做一次综合检验' },
  ],
};

// ========== 教材目录数据 ==========
export const textbookData: TextbookData = {
  grade: '六年级下册',
  subject: '数学',
  currentChapterId: 'c4-3',
  units: [
    {
      id: 'unit1', name: '第一单元 负数',
      chapters: [
        { id: 'c1-1', name: '负数的认识', mastery: 92, status: '已学完', description: '理解负数的意义，会用负数表示日常生活中的量',
          topics: [{ name: '负数的意义', mastery: 95, status: '已掌握' }, { name: '正负数的大小比较', mastery: 90, status: '已掌握' }],
          prerequisites: [] },
        { id: 'c1-2', name: '负数的应用', mastery: 88, status: '已学完', description: '能在具体情境中应用负数解决问题',
          topics: [{ name: '温度中的负数', mastery: 90, status: '已掌握' }, { name: '收支中的负数', mastery: 85, status: '已掌握' }],
          prerequisites: ['c1-1'] },
      ],
    },
    {
      id: 'unit2', name: '第二单元 百分数（二）',
      chapters: [
        { id: 'c2-1', name: '折扣', mastery: 85, status: '已学完', description: '理解折扣的含义，能解决折扣相关的实际问题',
          topics: [{ name: '折扣的意义', mastery: 88, status: '已掌握' }, { name: '折扣计算', mastery: 82, status: '已掌握' }],
          prerequisites: [] },
        { id: 'c2-2', name: '成数', mastery: 80, status: '已学完', description: '理解成数的含义，能进行成数与百分数的转换',
          topics: [{ name: '成数的意义', mastery: 82, status: '已掌握' }, { name: '成数应用', mastery: 78, status: '基本掌握' }],
          prerequisites: ['c2-1'] },
        { id: 'c2-3', name: '税率', mastery: 78, status: '已学完', description: '了解税收的意义，会计算应纳税额',
          topics: [{ name: '税率的意义', mastery: 80, status: '已掌握' }, { name: '税额计算', mastery: 75, status: '基本掌握' }],
          prerequisites: ['c2-1'] },
        { id: 'c2-4', name: '利率', mastery: 75, status: '已学完', description: '了解储蓄的意义，会计算利息',
          topics: [{ name: '利率的意义', mastery: 78, status: '基本掌握' }, { name: '利息计算', mastery: 72, status: '基本掌握' }],
          prerequisites: ['c2-3'] },
      ],
    },
    {
      id: 'unit3', name: '第三单元 圆柱与圆锥',
      chapters: [
        { id: 'c3-1', name: '圆柱的认识', mastery: 82, status: '已学完', description: '认识圆柱的特征，了解圆柱各部分名称',
          topics: [{ name: '圆柱的特征', mastery: 85, status: '已掌握' }, { name: '圆柱的展开图', mastery: 80, status: '已掌握' }],
          prerequisites: [] },
        { id: 'c3-2', name: '圆柱的表面积', mastery: 78, status: '已学完', description: '理解圆柱表面积的含义，掌握计算方法',
          topics: [{ name: '侧面积计算', mastery: 80, status: '已掌握' }, { name: '表面积计算', mastery: 75, status: '基本掌握' }],
          prerequisites: ['c3-1'] },
        { id: 'c3-3', name: '圆柱的体积', mastery: 72, status: '已学完', description: '掌握圆柱体积公式，能解决实际问题',
          topics: [{ name: '体积公式推导', mastery: 75, status: '基本掌握' }, { name: '体积计算', mastery: 70, status: '基本掌握' }],
          prerequisites: ['c3-2'] },
        { id: 'c3-4', name: '圆锥的认识', mastery: 68, status: '已学完', description: '认识圆锥的特征，了解圆锥与圆柱的关系',
          topics: [{ name: '圆锥的特征', mastery: 70, status: '基本掌握' }, { name: '圆锥与圆柱的关系', mastery: 65, status: '待加强' }],
          prerequisites: ['c3-1'] },
        { id: 'c3-5', name: '圆锥的体积', mastery: 65, status: '已学完', description: '掌握圆锥体积公式，能解决实际问题',
          topics: [{ name: '体积公式', mastery: 68, status: '基本掌握' }, { name: '体积应用', mastery: 62, status: '待加强' }],
          prerequisites: ['c3-3', 'c3-4'] },
      ],
    },
    {
      id: 'unit4', name: '第四单元 比例',
      chapters: [
        { id: 'c4-1', name: '比例的意义和基本性质', mastery: 70, status: '已学完', description: '理解比例的意义，掌握比例的基本性质',
          topics: [{ name: '比例的意义', mastery: 72, status: '基本掌握' }, { name: '比例的基本性质', mastery: 68, status: '基本掌握' }],
          prerequisites: [] },
        { id: 'c4-2', name: '正比例和反比例', mastery: 68, status: '已学完', description: '理解正反比例的意义，能正确判断',
          topics: [{ name: '正比例的意义', mastery: 70, status: '基本掌握' }, { name: '反比例的意义', mastery: 65, status: '待加强' }],
          prerequisites: ['c4-1'] },
        { id: 'c4-3', name: '比例的应用', mastery: 65, status: '学习中', description: '能运用比例知识解决实际问题（当前章节）',
          topics: [{ name: '比较标准量', mastery: 45, status: '需加强' }, { name: '连续变化问题', mastery: 50, status: '需加强' }, { name: '倒推法', mastery: 60, status: '待确认' }],
          prerequisites: ['c4-2'] },
        { id: 'c4-4', name: '比例尺', mastery: 62, status: '已学完', description: '理解比例尺的意义，能进行相关计算',
          topics: [{ name: '比例尺的意义', mastery: 65, status: '基本掌握' }, { name: '比例尺应用', mastery: 60, status: '待加强' }],
          prerequisites: ['c4-1'] },
      ],
    },
    {
      id: 'unit5', name: '第五单元 数学广角',
      chapters: [
        { id: 'c5-1', name: '鸽巢问题', mastery: 55, status: '已学完', description: '了解鸽巢原理，能解决简单的鸽巢问题',
          topics: [{ name: '鸽巢原理', mastery: 58, status: '待加强' }, { name: '鸽巢问题应用', mastery: 52, status: '待加强' }],
          prerequisites: [] },
      ],
    },
    {
      id: 'unit6', name: '第六单元 整理和复习',
      chapters: [
        { id: 'c6-1', name: '数与代数', mastery: 0, status: '未开始', description: '系统复习小学阶段的数与代数知识',
          topics: [], prerequisites: [] },
        { id: 'c6-2', name: '图形与几何', mastery: 0, status: '未开始', description: '系统复习图形与几何知识',
          topics: [], prerequisites: [] },
        { id: 'c6-3', name: '统计与概率', mastery: 0, status: '未开始', description: '系统复习统计与概率知识',
          topics: [], prerequisites: [] },
      ],
    },
  ],
};

// ========== 错题本数据 ==========
export const wrongQuestions: WrongQuestion[] = [
  { id: 1, topic: '比较标准量', text: '甲比乙多 1/3，乙比甲少几分之几？', date: '10-15',
    errorType: '概念误解', retryCount: 2, mastered: false, relatedKnowledge: ['比较标准量', '分数的意义'] },
  { id: 2, topic: '连续变化问题', text: '原价 100 元，先涨 1/10 再降 1/10，现价多少？', date: '10-16',
    errorType: '概念误解', retryCount: 1, mastered: false, relatedKnowledge: ['比较标准量', '连续变化问题'] },
  { id: 3, topic: '分数乘法', text: '一根绳子长 12 米，先用去 1/3，再用去剩下的 1/4，还剩多少米？', date: '10-14',
    errorType: '计算错误', retryCount: 3, mastered: true, relatedKnowledge: ['分数乘法', '连续变化问题'] },
  { id: 4, topic: '比例的应用', text: '在比例尺 1:5000000 的地图上，量得 A、B 两地距离 4cm，实际距离是多少？', date: '10-13',
    errorType: '审题错误', retryCount: 1, mastered: true, relatedKnowledge: ['比例尺', '比例的应用'] },
  { id: 5, topic: '圆锥体积', text: '一个圆锥底面半径 3cm，高 5cm，体积是多少？', date: '10-12',
    errorType: '方法不会', retryCount: 2, mastered: false, relatedKnowledge: ['圆锥的体积', '圆柱的体积'] },
  { id: 6, topic: '比较标准量', text: '某厂去年产量 2000 吨，今年比去年增产 1/5，今年产量多少？', date: '10-16',
    errorType: '计算错误', retryCount: 0, mastered: false, relatedKnowledge: ['比较标准量', '分数乘法'] },
];

export const errorCategories: ErrorCategory[] = [
  { type: '概念误解', count: 2, color: '#d4726a' },
  { type: '计算错误', count: 2, color: '#e0a458' },
  { type: '审题错误', count: 1, color: '#6a9ed4' },
  { type: '方法不会', count: 1, color: '#8a7ad4' },
];

// ========== 欢迎消息 ==========
export const welcomeMessage: ChatMessage = {
  id: 'welcome', role: 'assistant', timestamp: 0,
  blocks: [
    { type: 'text', text: '你好！我是 DeerMind，你的数学学习伙伴。' },
    { type: 'text', text: '你们学校现在学到**比例的应用**了。根据你最近的练习，这个知识点你掌握了大约 65%，在"比较标准量"这个地方还有点模糊。' },
    { type: 'text', text: '你今天想做什么？直接说就行。' },
  ],
  suggestions: ['今天学的没听懂，再讲一遍', '有一道题不会做', '测一下我掌握得怎么样', '我想复习上一章'],
};

// ========== 完整讲解演示 ==========
export const fullLectureFlow: ChatMessage[] = [
  { id: 'l1', role: 'assistant', timestamp: 1, phase: 'concept',
    blocks: [
      { type: 'phase-marker', phase: 'concept', label: '第 1 步：理解概念 — 比较标准量' },
      { type: 'text', text: '今天我们系统讲一下**比较标准量**——这是分数应用中最容易出错的概念。' },
      { type: 'text', text: '甲有 12 张卡片，乙有 9 张。问"甲比乙多几分之几"，应该除以谁？' },
      { type: 'bars', caption: '甲和乙的卡片数量', rows: [{ label: '甲', value: 12 }, { label: '乙', value: 9 }] },
    ],
    suggestions: ['除以 9（乙的数量）', '除以 12（甲的数量）', '我不确定，讲讲为什么'] },
  { id: 'l2', role: 'user', timestamp: 2, blocks: [{ type: 'text', text: '除以 9，因为是和乙比。' }] },
  { id: 'l3', role: 'assistant', timestamp: 3, phase: 'concept',
    blocks: [
      { type: 'text', text: '完全正确！**和谁比，谁就是标准量，就除以谁。**' },
      { type: 'formula', text: '甲比乙多 = (12-9) ÷ 9 = 1/3\n乙比甲少 = (12-9) ÷ 12 = 1/4' },
      { type: 'text', text: '同样差 3 张，但标准量不同，结果就不同。这是考试高频丢分点。' },
    ],
    suggestions: ['我懂了，继续讲例题', '再举个生活中的例子', '那百分数也是一样吗？'] },
  { id: 'l4', role: 'assistant', timestamp: 4, phase: 'example',
    blocks: [
      { type: 'phase-marker', phase: 'example', label: '第 2 步：例题演示 — 先涨后降' },
      { type: 'text', text: '**一件衣服原价 200 元，先涨价 1/10，再降价 1/10，现价多少？**' },
      { type: 'text', text: '很多人以为"先涨后降回到原价"，这是错的——因为两次的标准量不一样。' },
      { type: 'formula', text: '涨价后：200 × (1+1/10) = 220 元（标准量：200）\n降价后：220 × (1-1/10) = 198 元（标准量：220）' },
      { type: 'text', text: '最终 198 元，比原价少 2 元。关键：每一步的标准量都在变化。' },
    ],
    suggestions: ['出练习题我做做', '再讲一道更难的', '这个和折扣有关系吗？'] },
  { id: 'l5', role: 'assistant', timestamp: 5, phase: 'practice',
    blocks: [
      { type: 'phase-marker', phase: 'practice', label: '第 3 步：随堂练习' },
      { type: 'text', text: '来自己做一道。做错了正好知道哪里没掌握。' },
      { type: 'question', id: 'p1', mode: 'practice', prompt: '小明有 20 颗糖，给了小红 1/5，又给了小刚剩下的 1/4，还剩多少颗？', state: 'offered' },
    ],
    suggestions: ['给我一点提示', '这道题我不会，求助'] },
  { id: 'l6', role: 'user', timestamp: 6, blocks: [{ type: 'text', text: '20×4/5=16，16×3/4=12 颗。' }] },
  { id: 'l7', role: 'assistant', timestamp: 7, phase: 'practice',
    blocks: [
      { type: 'text', text: '**完全正确！** 你每一步都重新计算了标准量，思路很清晰。' },
      { type: 'formula', text: '给小红后：20 × (1-1/5) = 16 颗\n给小刚后：16 × (1-1/4) = 12 颗' },
    ],
    suggestions: ['再来一道', '做个总结吧', '出道难点的'] },
  { id: 'l8', role: 'assistant', timestamp: 8, phase: 'summary',
    blocks: [
      { type: 'phase-marker', phase: 'summary', label: '第 4 步：总结回顾' },
      { type: 'summary', title: '比较标准量 · 要点总结', points: [
        '核心原则：和谁比，谁就是标准量，就除以谁',
        '连续变化：每一步的标准量都可能变化，必须逐步计算',
        '常见陷阱："先涨 1/10 再降 1/10"不等于回到原价',
        '解题步骤：① 确定每步标准量 ② 计算变化后量 ③ 用新量作下一步标准量',
      ]},
    ],
    suggestions: ['好的，谢谢老师', '我想再练几道', '测一下我掌握得怎么样'] },
];

// ========== 答疑演示 ==========
export const fullQAFlow: ChatMessage[] = [
  { id: 'q1', role: 'user', timestamp: 1, blocks: [{ type: 'text', text: '老师，3/4 + 2/5 等于多少？我不会。' }] },
  { id: 'q2', role: 'assistant', timestamp: 2, blocks: [
    { type: 'text', text: '好的，一步步来。异分母分数相加，第一步要做什么？' },
  ], suggestions: ['通分', '直接分子加分子', '我不知道'] },
  { id: 'q3', role: 'user', timestamp: 3, blocks: [{ type: 'text', text: '通分，找最小公倍数。' }] },
  { id: 'q4', role: 'assistant', timestamp: 4, blocks: [
    { type: 'text', text: '对！4 和 5 互质，最小公倍数就是 4×5=20。' },
    { type: 'formula', text: '3/4 = 15/20\n2/5 = 8/20\n15/20 + 8/20 = 23/20 = 1又3/20' },
    { type: 'text', text: '你是通分找不准，还是计算容易错？' },
  ], suggestions: ['通分有时候找不准', '计算容易错', '我懂了，谢谢'] },
];

// ========== Mock 回复生成 ==========
export function generateMockReply(input: string, state: LearningState, messages: ChatMessage[]): {
  reply: ChatMessage; stateUpdate?: Partial<LearningState>;
} {
  const lower = input.toLowerCase();
  const lastMsg = messages[messages.length - 1];

  if (lastMsg?.blocks.some(b => b.type === 'question' && (b as any).state === 'offered')) {
    return { reply: {
      id: 'r' + Date.now(), role: 'assistant', timestamp: Date.now(), phase: state.lecturePhase,
      blocks: [
        { type: 'text', text: `我看看你的答案："${input}"` },
        { type: 'text', text: '思路是对的！你准确处理了标准量的变化。这道题的关键就是每一步都要重新确定标准量。' },
      ],
      suggestions: ['再来一道', '做个总结', '我想提问'],
    }};
  }

  if (lower.includes('讲') || lower.includes('不懂') || lower.includes('没听懂')) {
    return {
      reply: { id: 'r' + Date.now(), role: 'assistant', timestamp: Date.now(), phase: 'concept',
        blocks: [
          { type: 'phase-marker', phase: 'concept', label: '第 1 步：理解概念' },
          { type: 'text', text: `好的，我们来系统讲一下。从最基础的概念开始。` },
          { type: 'text', text: '先确认一下：你是概念不清楚，还是做题不会用？' },
        ],
        suggestions: ['概念不太清楚', '做题不会用', '都有点问题'] },
      stateUpdate: { mode: 'lecture', lecturePhase: 'concept', lectureTopic: '比例的应用' },
    };
  }
  if (lower.includes('题') || lower.includes('不会')) {
    return {
      reply: { id: 'r' + Date.now(), role: 'assistant', timestamp: Date.now(),
        blocks: [
          { type: 'text', text: '好的，把题目发给我。如果做了一部分，也把思路告诉我。' },
        ],
        suggestions: ['（模拟）输入一道题', '我先说说思路'] },
      stateUpdate: { mode: 'qa' },
    };
  }
  if (lower.includes('测') || lower.includes('掌握') || lower.includes('评估')) {
    return {
      reply: { id: 'r' + Date.now(), role: 'assistant', timestamp: Date.now(),
        blocks: [
          { type: 'text', text: '好的，我们做个小检测，3 道题。需要帮助可以说"求助"，但那样不算独立完成。准备好了吗？' },
        ],
        suggestions: ['准备好了，开始', '先出 1 道试试', '我想先复习'] },
      stateUpdate: { mode: 'idle' },
    };
  }
  return {
    reply: { id: 'r' + Date.now(), role: 'assistant', timestamp: Date.now(), phase: state.lecturePhase,
      blocks: [
        { type: 'text', text: `收到："${input}"。你是希望我系统讲解，还是针对具体问题解答？` },
      ],
      suggestions: ['系统讲解', '针对具体问题', '我先想想'] },
  };
}

export function getContextActions(mode: string, phase?: string): string[] {
  if (mode === 'lecture') {
    switch (phase) {
      case 'concept': return ['继续讲例题', '我有问题', '这个我懂了'];
      case 'example': return ['出练习题', '再讲一道', '我有问题'];
      case 'practice': return ['对答案', '需要提示', '求助'];
      case 'summary': return ['再来几道', '测一下', '结束讲解'];
      default: return ['继续讲解', '出道题', '结束讲解'];
    }
  }
  if (mode === 'problem') return ['再讲一遍', '出类似题', '我懂了'];
  if (mode === 'error-check') return ['重做此题', '出迁移题', '查看解析'];
  if (mode === 'review') return ['继续复习', '做个检测', '结束复习'];
  if (mode === 'qa') return ['我懂了', '再问一个', '给我出道题'];
  return ['再讲一遍', '出道题', '测一下掌握'];
}
