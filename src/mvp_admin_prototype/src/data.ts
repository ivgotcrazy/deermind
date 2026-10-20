import type {
  Trace, Span, MetricCard, TrendPoint, RejectionReason,
  AlertItem, SemanticObject, Student, SpaceOverview, LearningSpace,
  AdminUser, Textbook, Domain, DomainDetail, DomainTask, DomainSolution, DomainKC,
  TaskClaim, LearningTarget, LSInstance, EvaluationDimension,
} from './types';

// ========== Dashboard 数据 ==========
export const metricCards: MetricCard[] = [
  { label: '交互轮次', value: '128', change: '↑12%', trend: 'up', positive: true },
  { label: 'LLM 调用', value: '342', change: '↑8%', trend: 'up', positive: true },
  { label: '平均延迟', value: '2.3s', change: '↓0.2s', trend: 'down', positive: true },
  { label: '验证通过率', value: '87%', change: '↓3%', trend: 'down', positive: false },
  { label: '异常数', value: '5', change: '↑2', trend: 'up', positive: false },
];

export const trendData: TrendPoint[] = [
  { time: '08:00', interactions: 12, validationPass: 92, latencyP95: 2.1 },
  { time: '09:00', interactions: 18, validationPass: 90, latencyP95: 2.3 },
  { time: '10:00', interactions: 25, validationPass: 88, latencyP95: 2.5 },
  { time: '11:00', interactions: 22, validationPass: 85, latencyP95: 2.8 },
  { time: '12:00', interactions: 8, validationPass: 91, latencyP95: 2.0 },
  { time: '13:00', interactions: 15, validationPass: 87, latencyP95: 2.4 },
  { time: '14:00', interactions: 28, validationPass: 84, latencyP95: 3.0 },
];

export const rejectionReasons: RejectionReason[] = [
  { reason: '偷渡教学建议 (AA-A02)', count: 23 },
  { reason: 'KC 引用不存在', count: 12 },
  { reason: '类型不匹配', count: 8 },
  { reason: '置信度低于阈值', count: 5 },
  { reason: '重复 Observation', count: 3 },
];

export const alerts: AlertItem[] = [
  { id: 'A1', severity: 'critical', time: '14:32', title: 'Observation 验证连续失败', description: '学生A 在比例应用章节连续3次验证被拒', traceId: 'a3f8c2d1' },
  { id: 'A2', severity: 'warning', time: '14:15', title: '模型错误率突增', description: 'gpt-4o 最近1小时错误率达12%（基线3%）' },
  { id: 'A3', severity: 'warning', time: '13:58', title: 'Policy 决策超时', description: '1次 Policy 决策超过10秒阈值', traceId: 'b7e4f9a2' },
  { id: 'A4', severity: 'info', time: '13:30', title: '新模型版本部署', description: 'prompt v2.3 已上线，观察验证通过率变化' },
  { id: 'A5', severity: 'info', time: '12:45', title: '学生B 连续学习7天', description: '达到连续学习里程碑' },
];

// ========== Trace 列表数据 ==========
export const traceList: Trace[] = [
  {
    traceId: 'a3f8c2d1',
    studentId: 'S001',
    studentName: '学生A',
    lsId: 'LS-001',
    lsName: '数学·北师大版六下',
    chapter: '比例的应用',
    startTime: '2026-10-18 14:32:15',
    duration: 2568,
    status: 'partial',
    summary: '生成3个Observation，1个被验证拒绝，Policy选择讲解Action，Belief更新2个Claim',
    studentInput: '老师，3/4 + 2/5 等于多少？我不会。',
    systemOutput: '我们来看看这道题。3/4 和 2/5 的分母不同，需要先通分。4和5的最小公倍数是20...',
    modelVersion: 'gpt-4o',
    promptVersion: 'v2.3',
    spans: [],
    semanticEvents: [],
  },
  {
    traceId: 'b7e4f9a2',
    studentId: 'S002',
    studentName: '学生B',
    lsId: 'LS-003',
    lsName: '数学·北师大版六下',
    chapter: '分数运算',
    startTime: '2026-10-18 14:30:02',
    duration: 1820,
    status: 'normal',
    summary: '生成2个Observation，全部通过验证，Policy选择练习Action',
    studentInput: '我想做几道分数减法的练习题',
    systemOutput: '好的，这里有3道分数减法题，先试试第一题：5/6 - 1/3 = ?',
    modelVersion: 'gpt-4o',
    promptVersion: 'v2.3',
    spans: [],
    semanticEvents: [],
  },
  {
    traceId: 'c9d1e5f3',
    studentId: 'S001',
    studentName: '学生A',
    lsId: 'LS-001',
    lsName: '数学·北师大版六下',
    chapter: '比例的应用',
    startTime: '2026-10-18 14:28:40',
    duration: 920,
    status: 'error',
    summary: '生成1个Observation，验证失败（偷渡教学建议），无Action执行',
    studentInput: '为什么比例可以交叉相乘？',
    systemOutput: '（系统未输出，Observation验证失败后进入降级处理）',
    modelVersion: 'gpt-4o',
    promptVersion: 'v2.3',
    spans: [],
    semanticEvents: [],
  },
  {
    traceId: 'd2a6b8c4',
    studentId: 'S003',
    studentName: '学生C',
    lsId: 'LS-004',
    lsName: '数学·人教版六下',
    chapter: '圆柱与圆锥',
    startTime: '2026-10-18 14:25:10',
    duration: 3100,
    status: 'normal',
    summary: '生成4个Observation，全部通过，Policy选择讲解Action，含即时检测',
    studentInput: '圆柱的体积公式是怎么来的？',
    systemOutput: '圆柱体积的推导可以从长方体类比...我们把圆柱底面分成很多扇形...',
    modelVersion: 'gpt-4o',
    promptVersion: 'v2.3',
    spans: [],
    semanticEvents: [],
  },
  {
    traceId: 'e5f7a9d6',
    studentId: 'S002',
    studentName: '学生B',
    lsId: 'LS-003',
    lsName: '数学·北师大版六下',
    chapter: '分数运算',
    startTime: '2026-10-18 14:20:33',
    duration: 1540,
    status: 'normal',
    summary: '生成1个Observation，通过验证，Policy选择答疑Action',
    studentInput: '通分和约分有什么区别？',
    systemOutput: '通分是把几个分数变成同分母，约分是把一个分数化成最简形式...',
    modelVersion: 'gpt-4o',
    promptVersion: 'v2.3',
    spans: [],
    semanticEvents: [],
  },
  {
    traceId: 'f8c3e1a5',
    studentId: 'S001',
    studentName: '学生A',
    lsId: 'LS-001',
    lsName: '数学·北师大版六下',
    chapter: '比例的应用',
    startTime: '2026-10-18 14:15:20',
    duration: 2100,
    status: 'partial',
    summary: '生成2个Observation，1个置信度不足被降级，Policy选择复习Action',
    studentInput: '我昨天学的比例还是不太懂',
    systemOutput: '没关系，我们再来复习一下比例的基本概念...',
    modelVersion: 'gpt-4o',
    promptVersion: 'v2.2',
    spans: [],
    semanticEvents: [],
  },
];

// ========== 完整 Trace 详情（核心演示数据） ==========
export const detailedTrace: Trace = {
  traceId: 'a3f8c2d1',
  studentId: 'S001',
  studentName: '学生A',
  lsId: 'LS-001',
  lsName: '数学·北师大版六下',
  chapter: '比例的应用',
  startTime: '2026-10-18 14:32:15',
  duration: 2568,
  status: 'partial',
  summary: '生成3个Observation，1个被验证拒绝，Policy选择讲解Action，Belief更新2个Claim',
  studentInput: '老师，3/4 + 2/5 等于多少？我不会。',
  systemOutput: '我们来看看这道题。3/4 和 2/5 的分母不同，需要先通分。4和5的最小公倍数是20，所以 3/4 = 15/20，2/5 = 8/20，相加得到 23/20，也就是 1又3/20。',
  modelVersion: 'gpt-4o',
  promptVersion: 'v2.3',
  spans: [
    {
      spanId: 's0',
      type: 'turn.start',
      label: 'Turn Start',
      startTime: 0,
      duration: 12,
      status: 'success',
      detail: {
        actionType: 'input_received',
        actionPayload: '学生输入: "老师，3/4 + 2/5 等于多少？我不会。"',
        actionResult: '解析成功，识别为分数加法问题',
      },
    },
    {
      spanId: 's1',
      type: 'observation.generate',
      label: 'Observation #1 生成',
      startTime: 45,
      duration: 1267,
      status: 'success',
      detail: {
        candidateId: 'OBS-2026-1018-001',
        candidateType: 'ability_observation',
        candidateJson: JSON.stringify({
          type: 'ability_observation',
          kc: 'fraction_addition',
          level: 'struggling',
          confidence: 0.82,
          evidence: ['学生直接表示不会', '涉及异分母分数加法'],
        }, null, 2),
      },
      children: [
        {
          spanId: 's1-1',
          type: 'llm.invoke',
          label: 'LLM: Observation 生成',
          startTime: 50,
          duration: 1200,
          status: 'success',
          detail: {
            model: 'gpt-4o',
            temperature: 0.3,
            inputTokens: 1240,
            outputTokens: 156,
            prompt: `你是一个学习观察系统。根据学生的输入和当前学习状态，生成一个结构化的 Observation。

当前学生：学生A
当前章节：比例的应用
学生历史：分数运算掌握度65%，近期在异分母运算上有困难

学生输入："老师，3/4 + 2/5 等于多少？我不会。"

请输出 JSON 格式的 Observation，包含：type, kc, level, confidence, evidence。
约束：Observation 只描述学生的能力状态，不包含教学建议。`,
            response: `{
  "type": "ability_observation",
  "kc": "fraction_addition",
  "level": "struggling",
  "confidence": 0.82,
  "evidence": ["学生直接表示不会", "涉及异分母分数加法"]
}`,
          },
        },
      ],
    },
    {
      spanId: 's2',
      type: 'observation.validate',
      label: 'Observation #1 验证',
      startTime: 1312,
      duration: 45,
      status: 'success',
      detail: {
        validationRules: [
          { ruleId: 'R01', ruleName: '类型合法', passed: true, detail: 'ability_observation 是有效类型' },
          { ruleId: 'R02', ruleName: 'KC 引用存在', passed: true, detail: 'fraction_addition 在 Learning Space 中存在' },
          { ruleId: 'R03', ruleName: '纯度检查（无教学建议）', passed: true, detail: 'Candidate 中未发现 Policy 域内容' },
          { ruleId: 'R04', ruleName: '置信度阈值', passed: true, detail: '0.82 >= 0.6' },
        ],
      },
    },
    {
      spanId: 's3',
      type: 'observation.commit',
      label: 'Observation #1 Commit',
      startTime: 1357,
      duration: 23,
      status: 'success',
      detail: {
        commitAuthority: 'ObservationCommitAuthority_v1',
        standing: 'Committed',
      },
    },
    {
      spanId: 's4',
      type: 'observation.generate',
      label: 'Observation #2 生成',
      startTime: 1380,
      duration: 890,
      status: 'success',
      detail: {
        candidateId: 'OBS-2026-1018-002',
        candidateType: 'cognitive_observation',
        candidateJson: JSON.stringify({
          type: 'cognitive_observation',
          kc: 'common_denominator',
          level: 'unfamiliar',
          confidence: 0.71,
          evidence: ['题目涉及通分', '学生未表现出通分意识'],
          suggestion: '建议先复习通分概念，再做练习',
        }, null, 2),
      },
      children: [
        {
          spanId: 's4-1',
          type: 'llm.invoke',
          label: 'LLM: Observation 生成',
          startTime: 1385,
          duration: 850,
          status: 'success',
          detail: {
            model: 'gpt-4o',
            temperature: 0.3,
            inputTokens: 1350,
            outputTokens: 142,
            prompt: `你是一个学习观察系统。根据学生的输入和当前学习状态，生成一个结构化的 Observation。

当前学生：学生A
当前章节：比例的应用
已生成 Observation #1: fraction_addition = struggling (confidence 0.82)

学生输入："老师，3/4 + 2/5 等于多少？我不会。"

请输出 JSON 格式的 Observation，包含：type, kc, level, confidence, evidence。
约束：Observation 只描述学生的能力状态，不包含教学建议。`,
            response: `{
  "type": "cognitive_observation",
  "kc": "common_denominator",
  "level": "unfamiliar",
  "confidence": 0.71,
  "evidence": ["题目涉及通分", "学生未表现出通分意识"],
  "suggestion": "建议先复习通分概念，再做练习"
}`,
          },
        },
      ],
    },
    {
      spanId: 's5',
      type: 'observation.validate',
      label: 'Observation #2 验证',
      startTime: 2270,
      duration: 52,
      status: 'failed',
      detail: {
        validationRules: [
          { ruleId: 'R01', ruleName: '类型合法', passed: true, detail: 'cognitive_observation 是有效类型' },
          { ruleId: 'R02', ruleName: 'KC 引用存在', passed: true, detail: 'common_denominator 在 Learning Space 中存在' },
          { ruleId: 'R03', ruleName: '纯度检查（无教学建议）', passed: false, detail: 'Candidate 中包含 "suggestion": "建议先复习通分概念，再做练习"，属于 Policy 域内容' },
          { ruleId: 'R04', ruleName: '置信度阈值', passed: true, detail: '0.71 >= 0.6' },
        ],
        rejectionReason: 'Observation 纯度违规：Candidate 中包含教学建议字段 "suggestion"，属于 Policy 域内容，违反 Observation 纯度约束 (AA-A02)。该字段应被移除，或由 Policy 阶段基于 Observation 自行决策。',
      },
    },
    {
      spanId: 's6',
      type: 'observation.commit',
      label: 'Observation #2 Commit (跳过)',
      startTime: 2322,
      duration: 5,
      status: 'skipped',
      detail: {
        commitAuthority: 'ObservationCommitAuthority_v1',
        standing: 'Skipped (validation failed)',
      },
    },
    {
      spanId: 's7',
      type: 'observation.generate',
      label: 'Observation #3 生成',
      startTime: 2327,
      duration: 0,
      status: 'skipped',
      detail: {
        candidateId: 'N/A',
        candidateType: 'N/A',
        candidateJson: '// 因 #2 验证失败，系统进入降级模式，跳过 #3 生成',
      },
    },
    {
      spanId: 's8',
      type: 'policy.evaluate',
      label: 'Policy 决策',
      startTime: 2330,
      duration: 180,
      status: 'success',
      detail: {
        inputObservationRefs: ['OBS-2026-1018-001'],
        candidateActions: [
          { actionId: 'ACT-001', actionType: 'lecture', label: '讲解：异分母分数加法', score: 0.88, selected: true, reason: '学生明确表示不会，且 Observation 确认 fraction_addition=struggling' },
          { actionId: 'ACT-002', actionType: 'practice', label: '练习题：分数加法', score: 0.45, selected: false, reason: '学生当前处于困难状态，直接练习效果不佳' },
          { actionId: 'ACT-003', actionType: 'review', label: '复习：通分概念', score: 0.62, selected: false, reason: '通分是前置知识，但学生当前需要的是完整解题引导' },
          { actionId: 'ACT-004', actionType: 'qa', label: '答疑：直接回答', score: 0.30, selected: false, reason: '直接给答案不利于学习' },
        ],
        selectedAction: 'ACT-001',
        decisionBasis: '基于已 Commit 的 Observation #1 (fraction_addition=struggling, confidence=0.82)，选择讲解模式。Observation #2 被拒绝，其包含的通分复习建议未被采纳，但 Policy 独立判断将通分纳入讲解内容。',
      },
      children: [
        {
          spanId: 's8-1',
          type: 'llm.invoke',
          label: 'LLM: Policy 评分',
          startTime: 2335,
          duration: 150,
          status: 'success',
          detail: {
            model: 'gpt-4o',
            temperature: 0.1,
            inputTokens: 890,
            outputTokens: 78,
            prompt: `基于以下 Observation，为候选 Action 评分：

已 Commit Observation:
- fraction_addition = struggling (confidence 0.82)

候选 Action:
1. lecture: 讲解异分母分数加法
2. practice: 分数加法练习题
3. review: 复习通分概念
4. qa: 直接回答

请为每个 Action 给出 0-1 的分数和理由。`,
            response: `1. lecture: 0.88 - 学生明确不会，需要完整讲解
2. practice: 0.45 - 困难状态下练习效果差
3. review: 0.62 - 通分是前置但非当前核心
4. qa: 0.30 - 直接给答案不利于学习`,
          },
        },
      ],
    },
    {
      spanId: 's9',
      type: 'action.execute',
      label: 'Action 执行：讲解',
      startTime: 2510,
      duration: 50,
      status: 'success',
      detail: {
        actionType: 'lecture',
        actionPayload: JSON.stringify({
          topic: '异分母分数加法',
          phase: 'concept',
          kcFocus: ['fraction_addition', 'common_denominator'],
        }, null, 2),
        actionResult: '生成讲解内容，包含通分步骤和完整计算过程',
      },
    },
    {
      spanId: 's10',
      type: 'evidence.interpret',
      label: 'Evidence 解释',
      startTime: 2560,
      duration: 8,
      status: 'success',
      detail: {
        claimId: 'CLAIM-fraction-addition',
        observationRef: 'OBS-2026-1018-001',
        evidenceStrength: 'moderate_negative',
        interpretation: '学生直接表示不会异分母分数加法，提供了对"分数加法能力"的负向证据。置信度0.82，属于中等强度证据。',
      },
    },
    {
      spanId: 's11',
      type: 'belief.infer',
      label: 'Belief 更新',
      startTime: 2568,
      duration: 0,
      status: 'success',
      detail: {
        claimId: 'CLAIM-fraction-addition',
        priorBelief: 0.65,
        posteriorBelief: 0.62,
        algorithm: 'Extended BKT (with evidence weighting)',
        evidenceRefs: ['EVID-2026-1018-045'],
        beliefChange: -0.03,
      },
    },
    {
      spanId: 's12',
      type: 'turn.end',
      label: 'Turn End',
      startTime: 2568,
      duration: 0,
      status: 'success',
      detail: {
        actionResult: '完成。输出讲解内容，Belief 更新1个Claim（分数加法 65%→62%）。Observation #2 被拒绝，系统降级处理。',
      },
    },
  ],
  semanticEvents: [
    { id: 'SE1', type: 'observation', label: 'Observation #1: 分数加法困难', status: 'committed', detail: 'fraction_addition = struggling (0.82)', spanId: 's3' },
    { id: 'SE2', type: 'observation', label: 'Observation #2: 通分不熟悉', status: 'rejected', detail: '验证失败：偷渡教学建议 (AA-A02)', spanId: 's5' },
    { id: 'SE3', type: 'policy', label: 'Policy: 选择讲解Action', status: 'selected', detail: 'lecture (score 0.88)，基于Observation #1', spanId: 's8' },
    { id: 'SE4', type: 'belief', label: 'Belief: 分数加法掌握度', status: 'updated', detail: '65% → 62% (↓3%)', spanId: 's11' },
  ],
};

// ========== 语义对象数据 ==========
export const semanticObjects: SemanticObject[] = [
  {
    id: 'OBS-2026-1018-001',
    type: 'observation',
    summary: '分数加法困难',
    subType: 'ability_observation',
    studentName: '学生A',
    status: 'committed',
    currentVersion: 3,
    createdAt: '2026-10-15',
    versions: [
      { version: 3, date: '2026-10-18', change: '重新生成，置信度0.65→0.82，增加evidence', traceId: 'a3f8c2d1', content: '{"type":"ability_observation","kc":"fraction_addition","level":"struggling","confidence":0.82}' },
      { version: 2, date: '2026-10-16', change: '验证拒绝（偷渡建议），未Commit', traceId: '8c2d4e5f', content: '{"type":"ability_observation","kc":"fraction_addition","level":"struggling","confidence":0.65,"suggestion":"多做练习"}' },
      { version: 1, date: '2026-10-15', change: '初始生成', traceId: '5b1e7a9c', content: '{"type":"ability_observation","kc":"fraction_addition","level":"struggling","confidence":0.60}' },
    ],
    referencedBy: [
      { type: 'policy', id: 'POL-2026-1018-089', label: '选择讲解Action' },
      { type: 'evidence', id: 'EVID-2026-1018-045', label: '支持Claim分数加法' },
    ],
  },
  {
    id: 'OBS-2026-1018-002',
    type: 'observation',
    summary: '通分概念不熟悉',
    subType: 'cognitive_observation',
    studentName: '学生A',
    status: 'rejected',
    currentVersion: 2,
    createdAt: '2026-10-17',
    versions: [
      { version: 2, date: '2026-10-18', change: '验证拒绝（偷渡教学建议）', traceId: 'a3f8c2d1', content: '{"type":"cognitive_observation","kc":"common_denominator","level":"unfamiliar","confidence":0.71,"suggestion":"建议复习通分"}' },
      { version: 1, date: '2026-10-17', change: '初始生成，通过验证', traceId: '3d6f9a1b', content: '{"type":"cognitive_observation","kc":"common_denominator","level":"unfamiliar","confidence":0.68}' },
    ],
    referencedBy: [],
  },
  {
    id: 'POL-2026-1018-089',
    type: 'policy',
    summary: '选择讲解：异分母分数加法',
    subType: 'lecture_decision',
    studentName: '学生A',
    status: 'committed',
    currentVersion: 1,
    createdAt: '2026-10-18',
    versions: [
      { version: 1, date: '2026-10-18', change: '初始决策', traceId: 'a3f8c2d1', content: '{"selected_action":"lecture","score":0.88,"basis":"fraction_addition=struggling"}' },
    ],
    referencedBy: [
      { type: 'action', id: 'ACT-2026-1018-001', label: '讲解执行' },
    ],
  },
  {
    id: 'CLAIM-fraction-addition',
    type: 'claim',
    summary: '能力主张：分数加法',
    subType: 'ability_claim',
    studentName: '学生A',
    status: 'committed',
    currentVersion: 5,
    createdAt: '2026-10-10',
    versions: [
      { version: 5, date: '2026-10-18', change: 'Belief更新 65%→62%', traceId: 'a3f8c2d1', content: '{"claim":"fraction_addition","belief":0.62}' },
      { version: 4, date: '2026-10-17', change: 'Belief更新 60%→65%', traceId: '7e2a4c6d', content: '{"claim":"fraction_addition","belief":0.65}' },
      { version: 3, date: '2026-10-16', change: 'Belief更新 55%→60%', traceId: '9b5d1f3e', content: '{"claim":"fraction_addition","belief":0.60}' },
    ],
    referencedBy: [
      { type: 'evidence', id: 'EVID-2026-1018-045', label: '负向证据' },
      { type: 'belief', id: 'BELIEF-001', label: '当前Belief' },
    ],
  },
  {
    id: 'OBS-2026-1018-003',
    type: 'observation',
    summary: '比例应用题理解不足',
    subType: 'ability_observation',
    studentName: '学生B',
    status: 'committed',
    currentVersion: 1,
    createdAt: '2026-10-18',
    versions: [
      { version: 1, date: '2026-10-18', change: '初始生成', traceId: 'b7e4f9a2', content: '{"type":"ability_observation","kc":"ratio_word_problem","level":"developing","confidence":0.74}' },
    ],
    referencedBy: [
      { type: 'policy', id: 'POL-2026-1018-090', label: '选择练习Action' },
    ],
  },
];

// ========== 学生数据 ==========
export const students: Student[] = [
  {
    id: 'S001', name: '学生A', grade: '六年级',
    totalInteractions: 179, avgMastery: 66, streak: 12, errorRate: 7, avgSessionDuration: '12.5min', lastActive: '10-18 14:35',
    learningSpaces: [
      {
        id: 'LS-001', name: '数学·北师大版六下', subject: '数学', textbook: '北师大版', grade: '六年级下册', status: 'active',
        totalInteractions: 156, avgMastery: 68, errorRate: 8, lastActive: '10-18 14:35',
        beliefs: [
          { claim: '分数运算', current: 68, previous: 55, change: 13 },
          { claim: '比例应用', current: 52, previous: 40, change: 12 },
          { claim: '方程基础', current: 78, previous: 75, change: 3 },
        ],
        weakKCs: [
          { kcId: 'KC-004', kcName: '比例应用题', mastery: 48, evidenceCount: 8 },
          { kcId: 'KC-003', kcName: '比例的基本性质', mastery: 55, evidenceCount: 6 },
          { kcId: 'KC-024', kcName: '利率', mastery: 48, evidenceCount: 3 },
        ],
        actionDistribution: [
          { type: '讲解', count: 52 }, { type: '练习', count: 48 }, { type: '答疑', count: 38 }, { type: '复习', count: 18 },
        ],
        episodes: [
          { date: '10-18', title: '讲解比例的应用', type: 'lecture', masteryChange: '62→65', traceIds: ['a3f8c2d1', 'c9d1e5f3'] },
          { date: '10-18', title: '练习：分数加法', type: 'practice', masteryChange: '60→62', traceIds: ['f8c3e1a5'] },
          { date: '10-17', title: '复习分数运算', type: 'review', masteryChange: '58→60', traceIds: ['d2a6b8c4'] },
          { date: '10-16', title: '讲解通分', type: 'lecture', masteryChange: '55→58', traceIds: ['e5f7a9d6'] },
        ],
        masteryTrend: [
          { date: '10-12', value: 55 }, { date: '10-13', value: 57 }, { date: '10-14', value: 58 },
          { date: '10-15', value: 60 }, { date: '10-16', value: 62 }, { date: '10-17', value: 65 }, { date: '10-18', value: 68 },
        ],
      },
      {
        id: 'LS-002', name: '数学·人教版六下', subject: '数学', textbook: '人教版', grade: '六年级下册', status: 'paused',
        totalInteractions: 23, avgMastery: 55, errorRate: 4, lastActive: '10-10 09:20',
        beliefs: [
          { claim: '分数运算', current: 58, previous: 52, change: 6 },
          { claim: '几何图形', current: 52, previous: 48, change: 4 },
        ],
        weakKCs: [
          { kcId: 'KC-031', kcName: '圆柱的表面积', mastery: 45, evidenceCount: 3 },
        ],
        actionDistribution: [
          { type: '讲解', count: 10 }, { type: '练习', count: 8 }, { type: '答疑', count: 5 },
        ],
        episodes: [
          { date: '10-10', title: '讲解负数', type: 'lecture', masteryChange: '50→55', traceIds: [] },
        ],
        masteryTrend: [
          { date: '10-08', value: 50 }, { date: '10-09', value: 52 }, { date: '10-10', value: 55 },
        ],
      },
    ],
  },
  {
    id: 'S002', name: '学生B', grade: '六年级',
    totalInteractions: 89, avgMastery: 72, streak: 7, errorRate: 3, avgSessionDuration: '15.2min', lastActive: '10-18 14:30',
    learningSpaces: [
      {
        id: 'LS-003', name: '数学·北师大版六下', subject: '数学', textbook: '北师大版', grade: '六年级下册', status: 'active',
        totalInteractions: 89, avgMastery: 72, errorRate: 3, lastActive: '10-18 14:30',
        beliefs: [
          { claim: '分数运算', current: 75, previous: 70, change: 5 },
          { claim: '比例应用', current: 68, previous: 65, change: 3 },
        ],
        weakKCs: [
          { kcId: 'KC-035', kcName: '圆锥的体积', mastery: 55, evidenceCount: 4 },
          { kcId: 'KC-043', kcName: '反比例', mastery: 58, evidenceCount: 3 },
        ],
        actionDistribution: [
          { type: '讲解', count: 28 }, { type: '练习', count: 35 }, { type: '答疑', count: 18 }, { type: '复习', count: 8 },
        ],
        episodes: [
          { date: '10-18', title: '练习：分数运算', type: 'practice', masteryChange: '70→72', traceIds: ['b7e4f9a2'] },
          { date: '10-17', title: '答疑：通分与约分', type: 'qa', masteryChange: '68→70', traceIds: ['e5f7a9d6'] },
        ],
        masteryTrend: [
          { date: '10-12', value: 65 }, { date: '10-13', value: 66 }, { date: '10-14', value: 67 },
          { date: '10-15', value: 68 }, { date: '10-16', value: 69 }, { date: '10-17', value: 70 }, { date: '10-18', value: 72 },
        ],
      },
    ],
  },
  {
    id: 'S003', name: '学生C', grade: '六年级',
    totalInteractions: 45, avgMastery: 61, streak: 3, errorRate: 5, avgSessionDuration: '18.0min', lastActive: '10-18 14:25',
    learningSpaces: [
      {
        id: 'LS-004', name: '数学·人教版六下', subject: '数学', textbook: '人教版', grade: '六年级下册', status: 'active',
        totalInteractions: 45, avgMastery: 61, errorRate: 5, lastActive: '10-18 14:25',
        beliefs: [
          { claim: '几何图形', current: 61, previous: 55, change: 6 },
        ],
        weakKCs: [
          { kcId: 'KC-031', kcName: '圆柱的表面积', mastery: 52, evidenceCount: 5 },
          { kcId: 'KC-035', kcName: '圆锥的体积', mastery: 45, evidenceCount: 2 },
        ],
        actionDistribution: [
          { type: '讲解', count: 18 }, { type: '练习', count: 15 }, { type: '答疑', count: 8 }, { type: '复习', count: 4 },
        ],
        episodes: [
          { date: '10-18', title: '讲解圆柱体积', type: 'lecture', masteryChange: '58→61', traceIds: ['d2a6b8c4'] },
        ],
        masteryTrend: [
          { date: '10-14', value: 55 }, { date: '10-15', value: 56 }, { date: '10-16', value: 57 },
          { date: '10-17', value: 58 }, { date: '10-18', value: 61 },
        ],
      },
    ],
  },
  {
    id: 'S004', name: '学生D', grade: '六年级',
    totalInteractions: 67, avgMastery: 58, streak: 5, errorRate: 12, avgSessionDuration: '9.8min', lastActive: '10-17 16:00',
    learningSpaces: [
      {
        id: 'LS-005', name: '数学·北师大版六下', subject: '数学', textbook: '北师大版', grade: '六年级下册', status: 'active',
        totalInteractions: 67, avgMastery: 58, errorRate: 12, lastActive: '10-17 16:00',
        beliefs: [
          { claim: '分数运算', current: 55, previous: 50, change: 5 },
          { claim: '比例应用', current: 48, previous: 42, change: 6 },
          { claim: '几何图形', current: 62, previous: 58, change: 4 },
        ],
        weakKCs: [
          { kcId: 'KC-004', kcName: '比例应用题', mastery: 42, evidenceCount: 6 },
          { kcId: 'KC-001', kcName: '异分母分数加法', mastery: 48, evidenceCount: 5 },
        ],
        actionDistribution: [
          { type: '讲解', count: 25 }, { type: '练习', count: 20 }, { type: '答疑', count: 15 }, { type: '复习', count: 7 },
        ],
        episodes: [
          { date: '10-17', title: '讲解比例应用', type: 'lecture', masteryChange: '45→48', traceIds: [] },
        ],
        masteryTrend: [
          { date: '10-13', value: 52 }, { date: '10-14', value: 53 }, { date: '10-15', value: 55 },
          { date: '10-16', value: 56 }, { date: '10-17', value: 58 },
        ],
      },
    ],
  },
  {
    id: 'S005', name: '学生E', grade: '五年级',
    totalInteractions: 34, avgMastery: 75, streak: 10, errorRate: 2, avgSessionDuration: '20.5min', lastActive: '10-18 11:20',
    learningSpaces: [
      {
        id: 'LS-006', name: '数学·北师大版五下', subject: '数学', textbook: '北师大版', grade: '五年级下册', status: 'active',
        totalInteractions: 34, avgMastery: 75, errorRate: 2, lastActive: '10-18 11:20',
        beliefs: [
          { claim: '分数基础', current: 78, previous: 72, change: 6 },
          { claim: '因数倍数', current: 72, previous: 68, change: 4 },
        ],
        weakKCs: [],
        actionDistribution: [
          { type: '讲解', count: 12 }, { type: '练习', count: 14 }, { type: '答疑', count: 8 },
        ],
        episodes: [
          { date: '10-18', title: '练习：分数乘法', type: 'practice', masteryChange: '73→75', traceIds: [] },
        ],
        masteryTrend: [
          { date: '10-12', value: 68 }, { date: '10-14', value: 70 }, { date: '10-16', value: 72 }, { date: '10-18', value: 75 },
        ],
      },
    ],
  },
  {
    id: 'S006', name: '学生F', grade: '六年级',
    totalInteractions: 8, avgMastery: 45, streak: 1, errorRate: 25, avgSessionDuration: '5.2min', lastActive: '10-12 09:15',
    learningSpaces: [
      {
        id: 'LS-007', name: '数学·北师大版六下', subject: '数学', textbook: '北师大版', grade: '六年级下册', status: 'active',
        totalInteractions: 8, avgMastery: 45, errorRate: 25, lastActive: '10-12 09:15',
        beliefs: [
          { claim: '分数运算', current: 42, previous: 40, change: 2 },
        ],
        weakKCs: [
          { kcId: 'KC-001', kcName: '异分母分数加法', mastery: 35, evidenceCount: 2 },
          { kcId: 'KC-002', kcName: '通分与最小公倍数', mastery: 38, evidenceCount: 2 },
        ],
        actionDistribution: [
          { type: '讲解', count: 4 }, { type: '练习', count: 2 }, { type: '答疑', count: 2 },
        ],
        episodes: [
          { date: '10-12', title: '尝试分数加法练习', type: 'practice', masteryChange: '40→42', traceIds: [] },
        ],
        masteryTrend: [
          { date: '10-10', value: 40 }, { date: '10-12', value: 45 },
        ],
      },
    ],
  },
];

// ========== Learning Space 列表 ==========
export const learningSpaces: LearningSpace[] = [
  { id: 'LS-001', studentName: '学生A', subject: '数学', textbook: '北师大版', grade: '六年级下册', status: 'active', totalInteractions: 156, avgMastery: 68, lastActive: '10-18 14:35' },
  { id: 'LS-002', studentName: '学生A', subject: '数学', textbook: '人教版', grade: '六年级下册', status: 'paused', totalInteractions: 23, avgMastery: 55, lastActive: '10-10 09:20' },
  { id: 'LS-003', studentName: '学生B', subject: '数学', textbook: '北师大版', grade: '六年级下册', status: 'active', totalInteractions: 89, avgMastery: 72, lastActive: '10-18 14:30' },
  { id: 'LS-004', studentName: '学生C', subject: '数学', textbook: '人教版', grade: '六年级下册', status: 'active', totalInteractions: 45, avgMastery: 61, lastActive: '10-18 14:25' },
  { id: 'LS-005', studentName: '学生D', subject: '数学', textbook: '北师大版', grade: '六年级下册', status: 'active', totalInteractions: 67, avgMastery: 58, lastActive: '10-17 16:00' },
];

// ========== Space 观测数据 ==========
export const spaceOverviews: SpaceOverview[] = [
  {
    spaceId: 'domain',
    spaceName: 'Domain Space',
    description: '领域知识体系：知识组件、解法、题目的建模与维护',
    isGlobal: true,
    metrics: [
      { label: 'KC 总数', value: '142', sub: '覆盖6个单元' },
      { label: '平均掌握度', value: '64%', sub: '↑3% 本周', trend: 'up' },
      { label: '题目总数', value: '856', sub: '正确率 71%' },
      { label: '关联教材', value: '3本', sub: '2个版本' },
    ],
    distributions: [
      {
        title: 'KC 掌握度分布',
        items: [
          { label: '未掌握 (<40%)', count: 28, color: '#b85c3c' },
          { label: '发展中 (40-60%)', count: 52, color: '#c9942a' },
          { label: '掌握 (60-80%)', count: 45, color: '#52b788' },
          { label: '熟练 (>80%)', count: 17, color: '#2d6a4f' },
        ],
      },
      {
        title: '题目难度分布',
        items: [
          { label: '基础', count: 312, color: '#52b788' },
          { label: '中等', count: 385, color: '#c9942a' },
          { label: '提高', count: 159, color: '#b85c3c' },
        ],
      },
    ],
    objectTypes: [
      { id: 'kc', label: 'KC 知识组件', count: 142 },
      { id: 'solution', label: 'Solution 解法', count: 89 },
      { id: 'problem', label: 'Problem 题目', count: 856 },
    ],
    objects: {
      kc: [
        { id: 'KC-001', name: '异分母分数加法', type: 'procedure', status: 'active', metrics: [{ label: '掌握度', value: '62%' }, { label: '覆盖学生', value: '8/12' }, { label: '前置依赖', value: '2个' }], updatedAt: '10-18' },
        { id: 'KC-002', name: '通分与最小公倍数', type: 'concept', status: 'active', metrics: [{ label: '掌握度', value: '58%' }, { label: '覆盖学生', value: '10/12' }, { label: '前置依赖', value: '1个' }], updatedAt: '10-18' },
        { id: 'KC-003', name: '比例的基本性质', type: 'concept', status: 'active', metrics: [{ label: '掌握度', value: '55%' }, { label: '覆盖学生', value: '6/12' }, { label: '前置依赖', value: '3个' }], updatedAt: '10-17' },
        { id: 'KC-004', name: '比例应用题', type: 'procedure', status: 'active', metrics: [{ label: '掌握度', value: '48%' }, { label: '覆盖学生', value: '5/12' }, { label: '前置依赖', value: '2个' }], updatedAt: '10-17' },
        { id: 'KC-005', name: '圆柱体积公式', type: 'concept', status: 'active', metrics: [{ label: '掌握度', value: '71%' }, { label: '覆盖学生', value: '4/12' }, { label: '前置依赖', value: '2个' }], updatedAt: '10-16' },
        { id: 'KC-006', name: '方程的解', type: 'procedure', status: 'draft', metrics: [{ label: '掌握度', value: '—' }, { label: '覆盖学生', value: '0/12' }, { label: '前置依赖', value: '待完善' }], updatedAt: '10-10' },
      ],
      solution: [
        { id: 'SOL-001', name: '通分法解异分母加法', type: 'standard', status: 'active', metrics: [{ label: '使用次数', value: '34' }, { label: '成功率', value: '82%' }, { label: '关联KC', value: '2个' }], updatedAt: '10-18' },
        { id: 'SOL-002', name: '交叉相乘法解比例', type: 'standard', status: 'active', metrics: [{ label: '使用次数', value: '21' }, { label: '成功率', value: '67%' }, { label: '关联KC', value: '1个' }], updatedAt: '10-17' },
        { id: 'SOL-003', name: '设未知数法解应用题', type: 'advanced', status: 'active', metrics: [{ label: '使用次数', value: '12' }, { label: '成功率', value: '58%' }, { label: '关联KC', value: '3个' }], updatedAt: '10-16' },
      ],
      problem: [
        { id: 'P-1001', name: '3/4 + 2/5 = ?', type: 'basic', status: 'active', metrics: [{ label: '正确率', value: '76%' }, { label: '作答次数', value: '45' }, { label: '平均用时', value: '2.1min' }], updatedAt: '10-18' },
        { id: 'P-1002', name: '甲乙比例应用题', type: 'word', status: 'active', metrics: [{ label: '正确率', value: '52%' }, { label: '作答次数', value: '38' }, { label: '平均用时', value: '4.5min' }], updatedAt: '10-18' },
        { id: 'P-1003', name: '圆柱体积计算', type: 'basic', status: 'active', metrics: [{ label: '正确率', value: '81%' }, { label: '作答次数', value: '22' }, { label: '平均用时', value: '1.8min' }], updatedAt: '10-17' },
      ],
    },
  },
  {
    spaceId: 'learning',
    spaceName: 'Learning Space',
    description: '学生学习空间：能力主张、信念状态与学习轨迹（学生维度）',
    isGlobal: false,
    metrics: [
      { label: '活跃学生', value: '12', sub: '本周 +2' },
      { label: 'Claim 总数', value: '38', sub: '覆盖6个单元' },
      { label: '平均 Belief', value: '64%', sub: '↑3% 本周', trend: 'up' },
      { label: 'Belief 更新', value: '156次', sub: '本周' },
    ],
    distributions: [
      {
        title: '学生掌握度分布',
        items: [
          { label: '需加强 (<50%)', count: 3, color: '#b85c3c' },
          { label: '发展中 (50-70%)', count: 6, color: '#c9942a' },
          { label: '良好 (70-85%)', count: 2, color: '#52b788' },
          { label: '优秀 (>85%)', count: 1, color: '#2d6a4f' },
        ],
      },
      {
        title: 'Claim 证据充分度',
        items: [
          { label: '充分 (>10条)', count: 18, color: '#2d6a4f' },
          { label: '一般 (5-10条)', count: 14, color: '#c9942a' },
          { label: '不足 (<5条)', count: 6, color: '#b85c3c' },
        ],
      },
    ],
    objectTypes: [
      { id: 'claim', label: 'Claim 能力主张', count: 38 },
      { id: 'belief', label: 'Belief 信念状态', count: 456 },
      { id: 'trajectory', label: '学习轨迹', count: 12 },
    ],
    objects: {
      claim: [
        { id: 'CLAIM-001', name: '分数加法能力', type: 'ability', status: 'active', metrics: [{ label: '平均Belief', value: '64%' }, { label: '关联LS', value: '5个' }, { label: 'Evidence数', value: '156' }], updatedAt: '10-18', lsId: 'LS-001' },
        { id: 'CLAIM-002', name: '比例应用能力', type: 'ability', status: 'active', metrics: [{ label: '平均Belief', value: '51%' }, { label: '关联LS', value: '3个' }, { label: 'Evidence数', value: '89' }], updatedAt: '10-18', lsId: 'LS-001' },
        { id: 'CLAIM-003', name: '几何空间能力', type: 'ability', status: 'active', metrics: [{ label: '平均Belief', value: '68%' }, { label: '关联LS', value: '2个' }, { label: 'Evidence数', value: '34' }], updatedAt: '10-17', lsId: 'LS-003' },
      ],
      belief: [
        { id: 'BEL-001', name: '学生A · 分数加法', type: 'belief', status: 'active', metrics: [{ label: '当前值', value: '62%' }, { label: '先验', value: '65%' }, { label: 'Evidence', value: '12条' }], updatedAt: '10-18', lsId: 'LS-001' },
        { id: 'BEL-002', name: '学生A · 比例应用', type: 'belief', status: 'active', metrics: [{ label: '当前值', value: '52%' }, { label: '先验', value: '48%' }, { label: 'Evidence', value: '8条' }], updatedAt: '10-18', lsId: 'LS-001' },
        { id: 'BEL-003', name: '学生B · 分数运算', type: 'belief', status: 'active', metrics: [{ label: '当前值', value: '75%' }, { label: '先验', value: '70%' }, { label: 'Evidence', value: '15条' }], updatedAt: '10-18', lsId: 'LS-003' },
        { id: 'BEL-004', name: '学生C · 几何图形', type: 'belief', status: 'active', metrics: [{ label: '当前值', value: '58%' }, { label: '先验', value: '55%' }, { label: 'Evidence', value: '6条' }], updatedAt: '10-18', lsId: 'LS-004' },
      ],
      trajectory: [
        { id: 'TRAJ-001', name: '学生A · 学习轨迹', type: 'trajectory', status: 'active', metrics: [{ label: '总交互', value: '156' }, { label: '连续天数', value: '12' }, { label: '掌握度变化', value: '+13%' }], updatedAt: '10-18', lsId: 'LS-001' },
        { id: 'TRAJ-002', name: '学生B · 学习轨迹', type: 'trajectory', status: 'active', metrics: [{ label: '总交互', value: '89' }, { label: '连续天数', value: '7' }, { label: '掌握度变化', value: '+8%' }], updatedAt: '10-18', lsId: 'LS-003' },
        { id: 'TRAJ-003', name: '学生C · 学习轨迹', type: 'trajectory', status: 'active', metrics: [{ label: '总交互', value: '45' }, { label: '连续天数', value: '5' }, { label: '掌握度变化', value: '+5%' }], updatedAt: '10-18', lsId: 'LS-004' },
      ],
    },
  },
  {
    spaceId: 'evaluation',
    spaceName: 'Evaluation Space',
    description: '证据解释、信念推断与学习效果评估',
    isGlobal: false,
    metrics: [
      { label: 'Evidence 总数', value: '342', sub: '本周 +89' },
      { label: '解释一致率', value: '83%', sub: '人工抽检', trend: 'up' },
      { label: 'Belief 更新', value: '156次', sub: '本周' },
      { label: '平均收敛轮数', value: '3.2', sub: '到稳定Belief' },
    ],
    distributions: [
      {
        title: 'Evidence 类型分布',
        items: [
          { label: '正面证据', count: 198, color: '#2d8a5e' },
          { label: '负面证据', count: 112, color: '#b85c3c' },
          { label: '中性证据', count: 32, color: '#8a99a8' },
        ],
      },
      {
        title: '证据强度分布',
        items: [
          { label: '强', count: 87, color: '#2d6a4f' },
          { label: '中', count: 178, color: '#52b788' },
          { label: '弱', count: 77, color: '#a8d5ba' },
        ],
      },
    ],
    objectTypes: [
      { id: 'evidence', label: 'Evidence 证据', count: 342 },
      { id: 'interpreter', label: 'Interpreter 解释器', count: 4 },
      { id: 'inferencer', label: 'Inferencer 推断器', count: 2 },
    ],
    objects: {
      evidence: [
        { id: 'EVID-045', name: '学生A不会异分母加法', type: 'negative', status: 'committed', metrics: [{ label: '强度', value: '中' }, { label: '关联Claim', value: '分数加法' }, { label: '来源', value: 'Obs#001' }], updatedAt: '10-18', lsId: 'LS-001' },
        { id: 'EVID-044', name: '学生A正确完成通分题', type: 'positive', status: 'committed', metrics: [{ label: '强度', value: '强' }, { label: '关联Claim', value: '通分概念' }, { label: '来源', value: 'Action练习' }], updatedAt: '10-18', lsId: 'LS-001' },
        { id: 'EVID-043', name: '学生B比例题正确率70%', type: 'positive', status: 'committed', metrics: [{ label: '强度', value: '中' }, { label: '关联Claim', value: '比例应用' }, { label: '来源', value: '测验结果' }], updatedAt: '10-17', lsId: 'LS-003' },
        { id: 'EVID-042', name: '学生C圆柱体积公式混淆', type: 'negative', status: 'committed', metrics: [{ label: '强度', value: '弱' }, { label: '关联Claim', value: '几何空间' }, { label: '来源', value: 'Obs#003' }], updatedAt: '10-17', lsId: 'LS-004' },
      ],
      interpreter: [
        { id: 'INTERP-01', name: '练习结果解释器', type: 'rule-based', status: 'active', metrics: [{ label: '解释次数', value: '128' }, { label: '一致率', value: '88%' }, { label: '平均延迟', value: '45ms' }], updatedAt: '10-18' },
        { id: 'INTERP-02', name: 'Observation解释器', type: 'llm-based', status: 'active', metrics: [{ label: '解释次数', value: '214' }, { label: '一致率', value: '79%' }, { label: '平均延迟', value: '1.2s' }], updatedAt: '10-18' },
      ],
      inferencer: [
        { id: 'INFER-01', name: 'Extended BKT', type: 'algorithm', status: 'active', metrics: [{ label: '更新次数', value: '156' }, { label: '收敛率', value: '87%' }, { label: '平均轮数', value: '3.2' }], updatedAt: '10-18' },
        { id: 'INFER-02', name: 'Simple Bayesian', type: 'algorithm', status: 'experimental', metrics: [{ label: '更新次数', value: '0' }, { label: '收敛率', value: '—' }, { label: '平均轮数', value: '—' }], updatedAt: '10-10' },
      ],
    },
  },
  {
    spaceId: 'interaction',
    spaceName: 'Interaction Space',
    description: '观察生成、策略决策与教学动作执行',
    isGlobal: false,
    metrics: [
      { label: 'Observation 生成', value: '284', sub: '通过率 87%' },
      { label: 'Policy 决策', value: '128', sub: '4类Action' },
      { label: 'Action 执行', value: '128', sub: '成功率 96%' },
      { label: '平均决策延迟', value: '1.8s', sub: '↓0.3s', trend: 'down' },
    ],
    distributions: [
      {
        title: 'Observation 拒绝原因',
        items: [
          { label: '偷渡教学建议', count: 23, color: '#b85c3c' },
          { label: 'KC引用不存在', count: 12, color: '#c9942a' },
          { label: '类型不匹配', count: 8, color: '#4a6fa5' },
          { label: '置信度不足', count: 5, color: '#8a99a8' },
        ],
      },
      {
        title: 'Action 类型分布',
        items: [
          { label: '讲解', count: 52, color: '#2d6a4f' },
          { label: '练习', count: 38, color: '#52b788' },
          { label: '答疑', count: 28, color: '#4a6fa5' },
          { label: '总结', count: 10, color: '#c9942a' },
        ],
      },
    ],
    objectTypes: [
      { id: 'observation', label: 'Observation 观察', count: 284 },
      { id: 'policy', label: 'Policy 决策', count: 128 },
      { id: 'action', label: 'Action 动作', count: 128 },
    ],
    objects: {
      observation: [
        { id: 'OBS-001', name: '分数加法困难', type: 'ability', status: 'committed', metrics: [{ label: '置信度', value: '0.82' }, { label: '验证', value: '通过' }, { label: '版本', value: 'v3' }], updatedAt: '10-18', lsId: 'LS-001' },
        { id: 'OBS-002', name: '通分不熟悉', type: 'cognitive', status: 'rejected', metrics: [{ label: '置信度', value: '0.71' }, { label: '验证', value: '拒绝(AA-A02)' }, { label: '版本', value: 'v2' }], updatedAt: '10-18', lsId: 'LS-001' },
        { id: 'OBS-003', name: '比例题理解不足', type: 'ability', status: 'committed', metrics: [{ label: '置信度', value: '0.74' }, { label: '验证', value: '通过' }, { label: '版本', value: 'v1' }], updatedAt: '10-18', lsId: 'LS-003' },
        { id: 'OBS-004', name: '几何公式记忆模糊', type: 'memory', status: 'committed', metrics: [{ label: '置信度', value: '0.68' }, { label: '验证', value: '通过' }, { label: '版本', value: 'v1' }], updatedAt: '10-17', lsId: 'LS-004' },
      ],
      policy: [
        { id: 'POL-089', name: '选择讲解Action', type: 'lecture', status: 'executed', metrics: [{ label: '候选数', value: '4' }, { label: '选择分', value: '0.88' }, { label: '延迟', value: '180ms' }], updatedAt: '10-18', lsId: 'LS-001' },
        { id: 'POL-090', name: '选择练习Action', type: 'practice', status: 'executed', metrics: [{ label: '候选数', value: '3' }, { label: '选择分', value: '0.76' }, { label: '延迟', value: '150ms' }], updatedAt: '10-18', lsId: 'LS-001' },
        { id: 'POL-091', name: '选择答疑Action', type: 'qa', status: 'executed', metrics: [{ label: '候选数', value: '2' }, { label: '选择分', value: '0.82' }, { label: '延迟', value: '120ms' }], updatedAt: '10-18', lsId: 'LS-003' },
      ],
      action: [
        { id: 'ACT-001', name: '讲解异分母加法', type: 'lecture', status: 'completed', metrics: [{ label: '学生反馈', value: '理解' }, { label: '时长', value: '4.2min' }, { label: '含检测', value: '是' }], updatedAt: '10-18', lsId: 'LS-001' },
        { id: 'ACT-002', name: '分数加法练习', type: 'practice', status: 'completed', metrics: [{ label: '正确率', value: '3/5' }, { label: '时长', value: '6.1min' }, { label: '含检测', value: '否' }], updatedAt: '10-18', lsId: 'LS-001' },
        { id: 'ACT-003', name: '比例题答疑', type: 'qa', status: 'completed', metrics: [{ label: '学生反馈', value: '基本理解' }, { label: '时长', value: '3.5min' }, { label: '含检测', value: '是' }], updatedAt: '10-18', lsId: 'LS-003' },
      ],
    },
  },
  {
    spaceId: 'reasoning',
    spaceName: 'AI Reasoning Runtime',
    description: 'Candidate生成、Validation验证与Commit审批的运行时',
    isGlobal: false,
    metrics: [
      { label: 'Candidate 生成', value: '312', sub: '5种类型' },
      { label: 'Validation 通过', value: '87%', sub: '4条规则' },
      { label: 'Commit 率', value: '82%', sub: '含降级' },
      { label: 'LLM 调用', value: '456次', sub: '平均1.2s' },
    ],
    distributions: [
      {
        title: 'Candidate 类型分布',
        items: [
          { label: 'Observation', count: 186, color: '#2d6a4f' },
          { label: 'Policy', count: 78, color: '#4a6fa5' },
          { label: 'Evidence', count: 34, color: '#c9942a' },
          { label: 'Belief', count: 14, color: '#8a99a8' },
        ],
      },
      {
        title: 'Validation 规则命中率',
        items: [
          { label: 'R01 类型合法', count: 310, color: '#2d8a5e' },
          { label: 'R02 KC引用', count: 298, color: '#52b788' },
          { label: 'R03 纯度检查', count: 271, color: '#c9942a' },
          { label: 'R04 置信度', count: 305, color: '#4a6fa5' },
        ],
      },
    ],
    objectTypes: [
      { id: 'candidate', label: 'Candidate 候选', count: 312 },
      { id: 'validation', label: 'Validation 验证', count: 312 },
      { id: 'commit', label: 'Commit 审批', count: 256 },
    ],
    objects: {
      candidate: [
        { id: 'CAND-001', name: 'Observation: 分数加法困难', type: 'observation', status: 'committed', metrics: [{ label: '生成耗时', value: '1.2s' }, { label: 'Token', value: '1240/156' }, { label: '模型', value: 'gpt-4o' }], updatedAt: '10-18', lsId: 'LS-001' },
        { id: 'CAND-002', name: 'Observation: 通分不熟悉', type: 'observation', status: 'rejected', metrics: [{ label: '生成耗时', value: '0.85s' }, { label: 'Token', value: '1350/142' }, { label: '模型', value: 'gpt-4o' }], updatedAt: '10-18', lsId: 'LS-001' },
        { id: 'CAND-003', name: 'Policy: 选择讲解', type: 'policy', status: 'committed', metrics: [{ label: '生成耗时', value: '0.15s' }, { label: 'Token', value: '890/78' }, { label: '模型', value: 'gpt-4o' }], updatedAt: '10-18', lsId: 'LS-001' },
        { id: 'CAND-004', name: 'Observation: 比例题理解不足', type: 'observation', status: 'committed', metrics: [{ label: '生成耗时', value: '1.1s' }, { label: 'Token', value: '1100/130' }, { label: '模型', value: 'gpt-4o' }], updatedAt: '10-18', lsId: 'LS-003' },
      ],
      validation: [
        { id: 'VAL-001', name: 'CAND-001 验证', type: 'observation', status: 'passed', metrics: [{ label: '规则数', value: '4/4通过' }, { label: '耗时', value: '45ms' }, { label: '拒绝原因', value: '—' }], updatedAt: '10-18', lsId: 'LS-001' },
        { id: 'VAL-002', name: 'CAND-002 验证', type: 'observation', status: 'failed', metrics: [{ label: '规则数', value: '3/4通过' }, { label: '耗时', value: '52ms' }, { label: '拒绝原因', value: 'R03纯度' }], updatedAt: '10-18', lsId: 'LS-001' },
        { id: 'VAL-003', name: 'CAND-004 验证', type: 'observation', status: 'passed', metrics: [{ label: '规则数', value: '4/4通过' }, { label: '耗时', value: '41ms' }, { label: '拒绝原因', value: '—' }], updatedAt: '10-18', lsId: 'LS-003' },
      ],
      commit: [
        { id: 'COMMIT-001', name: 'CAND-001 Commit', type: 'observation', status: 'approved', metrics: [{ label: 'Authority', value: 'v1' }, { label: 'Standing', value: 'Committed' }, { label: '耗时', value: '23ms' }], updatedAt: '10-18', lsId: 'LS-001' },
        { id: 'COMMIT-002', name: 'CAND-002 Commit', type: 'observation', status: 'skipped', metrics: [{ label: 'Authority', value: 'v1' }, { label: 'Standing', value: 'Skipped' }, { label: '原因', value: '验证失败' }], updatedAt: '10-18', lsId: 'LS-001' },
        { id: 'COMMIT-003', name: 'CAND-004 Commit', type: 'observation', status: 'approved', metrics: [{ label: 'Authority', value: 'v1' }, { label: 'Standing', value: 'Committed' }, { label: '耗时', value: '19ms' }], updatedAt: '10-18', lsId: 'LS-003' },
      ],
    },
  },
  {
    spaceId: 'evolution',
    spaceName: 'Evolution Space',
    description: '系统自学习、新模式发现与演化审批（MVP后启用）',
    isGlobal: true,
    metrics: [
      { label: '演化候选', value: '0', sub: 'MVP未启用' },
      { label: '已审批', value: '0', sub: '—' },
      { label: '效果验证', value: '—', sub: '待启用' },
      { label: '自动扩展KC', value: '0', sub: '待启用' },
    ],
    distributions: [
      {
        title: '演化状态',
        items: [
          { label: '未启用', count: 1, color: '#8a99a8' },
        ],
      },
      {
        title: '规划中的演化类型',
        items: [
          { label: '新KC发现', count: 3, color: '#4a6fa5' },
          { label: 'Policy优化', count: 2, color: '#2d6a4f' },
          { label: 'Solution扩展', count: 1, color: '#c9942a' },
        ],
      },
    ],
    objectTypes: [
      { id: 'evo-candidate', label: '演化候选', count: 0 },
      { id: 'evo-review', label: '审批记录', count: 0 },
    ],
    objects: {
      'evo-candidate': [],
      'evo-review': [],
    },
  },
];

// ========== 用户管理数据 ==========

export const adminUsers: AdminUser[] = [
  { id: 'U001', name: '学生A', role: 'student', email: 'student_a@school.edu', status: 'active', createdAt: '2026-09-01', lastActive: '10-18 14:35', grade: '六年级', textbook: '北师大版六下数学', totalInteractions: 156, avgMastery: 68 },
  { id: 'U002', name: '学生B', role: 'student', email: 'student_b@school.edu', status: 'active', createdAt: '2026-09-05', lastActive: '10-18 14:30', grade: '六年级', textbook: '北师大版六下数学', totalInteractions: 89, avgMastery: 72 },
  { id: 'U003', name: '学生C', role: 'student', email: 'student_c@school.edu', status: 'active', createdAt: '2026-09-10', lastActive: '10-18 14:25', grade: '六年级', textbook: '人教版六下数学', totalInteractions: 45, avgMastery: 61 },
  { id: 'U004', name: '学生D', role: 'student', email: 'student_d@school.edu', status: 'inactive', createdAt: '2026-09-12', lastActive: '10-10 09:20', grade: '六年级', textbook: '北师大版六下数学', totalInteractions: 12, avgMastery: 55 },
  { id: 'U005', name: '学生E', role: 'student', email: 'student_e@school.edu', status: 'pending', createdAt: '2026-10-15', lastActive: '—', grade: '六年级', textbook: '—', totalInteractions: 0, avgMastery: 0 },
  { id: 'T001', name: '王老师', role: 'teacher', email: 'wang@school.edu', status: 'active', createdAt: '2026-08-20', lastActive: '10-18 10:00', classes: ['六年级1班', '六年级2班'], studentCount: 45 },
  { id: 'T002', name: '李老师', role: 'teacher', email: 'li@school.edu', status: 'active', createdAt: '2026-08-25', lastActive: '10-17 16:30', classes: ['六年级3班'], studentCount: 22 },
  { id: 'A001', name: '系统管理员', role: 'admin', email: 'admin@deermind.ai', status: 'active', createdAt: '2026-08-01', lastActive: '10-18 14:00' },
];

// ========== 领域与教材数据 ==========
export const domains: Domain[] = [
  { id: 'DOM-001', name: '数学', subject: '数学', kcCount: 142, textbookCount: 3, studentCount: 12, status: 'active' },
  { id: 'DOM-002', name: '语文', subject: '语文', kcCount: 0, textbookCount: 0, studentCount: 0, status: 'draft' },
  { id: 'DOM-003', name: '英语', subject: '英语', kcCount: 0, textbookCount: 0, studentCount: 0, status: 'draft' },
];

export const textbooks: Textbook[] = [
  {
    id: 'TB-001',
    name: '北师大版六年级数学下册',
    domain: '数学',
    subject: '数学',
    grade: '六年级下册',
    version: '北师大版',
    publisher: '北京师范大学出版社',
    status: 'active',
    totalChapters: 18,
    mappedKcCount: 142,
    unmappedChapters: 0,
    importedAt: '2026-09-01',
    units: [
      { id: 'U1', name: '第一单元 负数', chapters: [
        { id: 'C1-1', name: '负数的认识', kcRefs: ['KC-010', 'KC-011'], mastery: 72 },
        { id: 'C1-2', name: '负数的大小比较', kcRefs: ['KC-012'], mastery: 68 },
      ]},
      { id: 'U2', name: '第二单元 百分数（二）', chapters: [
        { id: 'C2-1', name: '折扣', kcRefs: ['KC-020', 'KC-021'], mastery: 65 },
        { id: 'C2-2', name: '成数', kcRefs: ['KC-022'], mastery: 58 },
        { id: 'C2-3', name: '税率', kcRefs: ['KC-023'], mastery: 52 },
        { id: 'C2-4', name: '利率', kcRefs: ['KC-024'], mastery: 48 },
      ]},
      { id: 'U3', name: '第三单元 圆柱与圆锥', chapters: [
        { id: 'C3-1', name: '圆柱的认识', kcRefs: ['KC-030'], mastery: 75 },
        { id: 'C3-2', name: '圆柱的表面积', kcRefs: ['KC-031', 'KC-032'], mastery: 62 },
        { id: 'C3-3', name: '圆柱的体积', kcRefs: ['KC-005', 'KC-033'], mastery: 71 },
        { id: 'C3-4', name: '圆锥的认识', kcRefs: ['KC-034'], mastery: 68 },
        { id: 'C3-5', name: '圆锥的体积', kcRefs: ['KC-035'], mastery: 55 },
      ]},
      { id: 'U4', name: '第四单元 比例', chapters: [
        { id: 'C4-1', name: '比例的意义', kcRefs: ['KC-003'], mastery: 58 },
        { id: 'C4-2', name: '比例的基本性质', kcRefs: ['KC-003', 'KC-040'], mastery: 55 },
        { id: 'C4-3', name: '解比例', kcRefs: ['KC-041'], mastery: 50 },
        { id: 'C4-4', name: '正比例', kcRefs: ['KC-042'], mastery: 48 },
        { id: 'C4-5', name: '反比例', kcRefs: ['KC-043'], mastery: 45 },
        { id: 'C4-6', name: '比例的应用', kcRefs: ['KC-004', 'KC-044'], mastery: 48 },
      ]},
      { id: 'U5', name: '第五单元 数学广角', chapters: [
        { id: 'C5-1', name: '鸽巢问题', kcRefs: ['KC-050'], mastery: 60 },
      ]},
      { id: 'U6', name: '第六单元 整理和复习', chapters: [
        { id: 'C6-1', name: '数与代数', kcRefs: ['KC-001', 'KC-002', 'KC-003'], mastery: 64 },
        { id: 'C6-2', name: '图形与几何', kcRefs: ['KC-005', 'KC-030'], mastery: 68 },
      ]},
    ],
  },
  {
    id: 'TB-002',
    name: '人教版六年级数学下册',
    domain: '数学',
    subject: '数学',
    grade: '六年级下册',
    version: '人教版',
    publisher: '人民教育出版社',
    status: 'active',
    totalChapters: 16,
    mappedKcCount: 128,
    unmappedChapters: 2,
    importedAt: '2026-09-15',
    units: [
      { id: 'U1', name: '第一单元 负数', chapters: [
        { id: 'C1-1', name: '负数的认识', kcRefs: ['KC-010'], mastery: 70 },
      ]},
      { id: 'U2', name: '第二单元 百分数（二）', chapters: [
        { id: 'C2-1', name: '折扣与成数', kcRefs: ['KC-020', 'KC-022'], mastery: 60 },
      ]},
    ],
  },
  {
    id: 'TB-003',
    name: '苏教版六年级数学下册',
    domain: '数学',
    subject: '数学',
    grade: '六年级下册',
    version: '苏教版',
    publisher: '江苏教育出版社',
    status: 'draft',
    totalChapters: 15,
    mappedKcCount: 0,
    unmappedChapters: 15,
    importedAt: '2026-10-10',
    units: [],
  },
];
