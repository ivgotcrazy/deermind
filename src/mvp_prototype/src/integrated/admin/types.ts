// ========== Trace & Span ==========
export type SpanType =
  | 'turn.start'
  | 'turn.end'
  | 'observation.generate'
  | 'observation.validate'
  | 'observation.commit'
  | 'policy.evaluate'
  | 'action.execute'
  | 'evidence.interpret'
  | 'belief.infer'
  | 'llm.invoke';

export type SpanStatus = 'success' | 'failed' | 'partial' | 'skipped' | 'running';

export interface ValidationRule {
  ruleId: string;
  ruleName: string;
  passed: boolean;
  detail: string;
}

export interface CandidateAction {
  actionId: string;
  actionType: string;
  label: string;
  score: number;
  selected: boolean;
  reason?: string;
}

export interface SpanDetail {
  // LLM
  model?: string;
  temperature?: number;
  inputTokens?: number;
  outputTokens?: number;
  prompt?: string;
  response?: string;
  // Observation
  candidateId?: string;
  candidateType?: string;
  candidateJson?: string;
  validationRules?: ValidationRule[];
  rejectionReason?: string;
  commitAuthority?: string;
  standing?: string;
  // Policy
  inputObservationRefs?: string[];
  candidateActions?: CandidateAction[];
  selectedAction?: string;
  decisionBasis?: string;
  // Action
  actionType?: string;
  actionPayload?: string;
  actionResult?: string;
  // Evidence
  claimId?: string;
  observationRef?: string;
  evidenceStrength?: string;
  interpretation?: string;
  // Belief
  priorBelief?: number;
  posteriorBelief?: number;
  algorithm?: string;
  evidenceRefs?: string[];
  beliefChange?: number;
}

export interface Span {
  spanId: string;
  parentSpanId?: string;
  type: SpanType;
  label: string;
  startTime: number; // ms offset from trace start
  duration: number; // ms
  status: SpanStatus;
  detail: SpanDetail;
  children?: Span[];
}

export interface SemanticEvent {
  id: string;
  type: 'observation' | 'policy' | 'belief';
  label: string;
  status: 'committed' | 'rejected' | 'updated' | 'selected';
  detail: string;
  spanId: string;
}

export interface Trace {
  traceId: string;
  studentId: string;
  studentName: string;
  lsId: string;
  lsName: string;
  chapter: string;
  startTime: string;
  duration: number;
  status: 'normal' | 'partial' | 'error' | 'idle';
  summary: string;
  studentInput: string;
  systemOutput: string;
  spans: Span[];
  semanticEvents: SemanticEvent[];
  modelVersion: string;
  promptVersion: string;
}

// ========== Dashboard ==========
export interface MetricCard {
  label: string;
  value: string;
  change: string;
  trend: 'up' | 'down' | 'flat';
  positive: boolean;
}

export interface TrendPoint {
  time: string;
  interactions: number;
  validationPass: number;
  latencyP95: number;
}

export interface RejectionReason {
  reason: string;
  count: number;
}

export interface AlertItem {
  id: string;
  severity: 'critical' | 'warning' | 'info';
  time: string;
  title: string;
  description: string;
  traceId?: string;
}

// ========== Semantic Objects ==========
export type ObjectType = 'observation' | 'policy' | 'claim' | 'belief';

export interface SemanticObjectVersion {
  version: number;
  date: string;
  change: string;
  traceId: string;
  content: string;
}

export interface SemanticObject {
  id: string;
  type: ObjectType;
  summary: string;
  subType: string;
  studentName: string;
  status: 'committed' | 'rejected' | 'superseded';
  currentVersion: number;
  createdAt: string;
  versions: SemanticObjectVersion[];
  referencedBy: { type: string; id: string; label: string }[];
}

// ========== Student ==========
export interface StudentEpisode {
  date: string;
  title: string;
  type: string;
  masteryChange: string;
  traceIds: string[];
}

export interface StudentBelief {
  claim: string;
  current: number;
  previous: number;
  change: number;
}

export interface StudentWeakKC {
  kcId: string;
  kcName: string;
  mastery: number;
  evidenceCount: number;
}

export interface StudentActionDist {
  type: string;
  count: number;
}

export interface StudentLS {
  id: string;
  name: string;
  subject: string;
  textbook: string;
  grade: string;
  status: 'active' | 'paused' | 'archived';
  totalInteractions: number;
  avgMastery: number;
  errorRate: number;
  lastActive: string;
  beliefs: StudentBelief[];
  weakKCs: StudentWeakKC[];
  actionDistribution: StudentActionDist[];
  episodes: StudentEpisode[];
  masteryTrend: { date: string; value: number }[];
}

export interface Student {
  id: string;
  name: string;
  grade: string;
  learningSpaces: StudentLS[];
  totalInteractions: number;
  avgMastery: number;
  streak: number;
  errorRate: number;
  avgSessionDuration: string;
  lastActive: string;
}

export type PageType = 'actual' | 'maintenance' | 'review' | 'content' | 'account' | 'dashboard' | 'trace-list' | 'trace-detail' | 'objects' | 'object-detail' | 'students' | 'student-detail' | 'users' | 'domain' | 'evaluation' | 'textbooks' | 'targets' | 'learning-spaces' | 'config';

// ========== Space Observability ==========
export type SpaceId = 'domain' | 'learning' | 'evaluation' | 'interaction' | 'reasoning' | 'evolution';

export interface SpaceMetric {
  label: string;
  value: string;
  sub?: string;
  trend?: 'up' | 'down' | 'flat';
}

export interface SpaceDistribution {
  label: string;
  count: number;
  color: string;
}

export interface SpaceObjectItem {
  id: string;
  name: string;
  type: string;
  status: string;
  metrics: { label: string; value: string }[];
  updatedAt: string;
  lsId?: string; // 归属的 Learning Space，全局对象无此字段
}

export interface LearningSpace {
  id: string;
  studentName: string;
  subject: string;
  textbook: string;
  grade: string;
  status: 'active' | 'paused' | 'archived';
  totalInteractions: number;
  avgMastery: number;
  lastActive: string;
}

export interface SpaceOverview {
  spaceId: SpaceId;
  spaceName: string;
  description: string;
  isGlobal: boolean; // true=Domain/Evolution，无 LS 维度
  metrics: SpaceMetric[];
  distributions: { title: string; items: SpaceDistribution[] }[];
  objectTypes: { id: string; label: string; count: number }[];
  objects: Record<string, SpaceObjectItem[]>;
}

// ========== User Management ==========
export type UserRole = 'student' | 'teacher' | 'admin';

export interface AdminUser {
  id: string;
  name: string;
  role: UserRole;
  email: string;
  status: 'active' | 'inactive' | 'pending';
  createdAt: string;
  lastActive: string;
  // student specific
  grade?: string;
  textbook?: string;
  totalInteractions?: number;
  avgMastery?: number;
  // teacher specific
  classes?: string[];
  studentCount?: number;
}

// ========== Resource Management (Textbook) ==========
export interface TextbookChapter {
  id: string;
  name: string;
  kcRefs: string[];
  mastery?: number;
}

export interface TextbookUnit {
  id: string;
  name: string;
  chapters: TextbookChapter[];
}

export interface Textbook {
  id: string;
  name: string;
  domain: string;
  subject: string;
  grade: string;
  version: string;
  publisher: string;
  status: 'active' | 'draft' | 'archived';
  totalChapters: number;
  mappedKcCount: number;
  unmappedChapters: number;
  units: TextbookUnit[];
  importedAt: string;
}

export interface Domain {
  id: string;
  name: string;
  subject: string;
  kcCount: number;
  textbookCount: number;
  studentCount: number;
  status: 'active' | 'draft';
}

// ========== Domain Space Management ==========
export interface DomainKC {
  id: string;
  name: string;
  description: string;
  prerequisites: string[]; // 前置 KC id
  relatedKCs: string[];
  taskCount: number;
  status: 'active' | 'draft';
}

export interface DomainTask {
  id: string;
  name: string;
  description: string;
  taskType: 'problem-solving' | 'explanation' | 'modeling' | 'proof';
  kcRefs: string[];
  solutionRefs: string[];
  parameterRange: string;
  context: string;
  representation: string;
  exclusionScope: string;
  status: 'active' | 'draft';
  createdAt: string;
}

export interface DomainSolution {
  id: string;
  name: string;
  description: string;
  method: string;
  applicableConditions: string;
  subtaskDependencies: string[];
  taskRefs: string[];
  status: 'active' | 'draft';
}

export interface DomainDetail extends Domain {
  description: string;
  gradeRange: string;
  kcs: DomainKC[];
  tasks: DomainTask[];
  solutions: DomainSolution[];
}

// ========== Evaluation Space Management ==========
export type EvaluationDimension = 'independent' | 'understanding' | 'transfer' | 'retention';

export interface ClaimDimensionConfig {
  dimension: EvaluationDimension;
  label: string;
  enabled: boolean;
  criteria: string; // 评价细则
  evidenceRequirement: string; // 证据要求
}

export interface EvidenceRule {
  id: string;
  dimension: EvaluationDimension;
  observationType: string;
  polarity: 'positive' | 'negative' | 'non-informative';
  condition: string;
  description: string;
}

export interface TaskClaim {
  id: string;
  name: string;
  description: string;
  domainId: string;
  domainName: string;
  taskId: string; // 一对一映射
  taskName: string;
  taskScope: string;
  responsibility: string;
  methodRequirement: string;
  conditions: string;
  supportBoundary: string;
  qualityRequirement: string;
  dimensions: ClaimDimensionConfig[];
  evidenceRules: EvidenceRule[];
  status: 'active' | 'draft' | 'archived';
  version: number;
  updatedAt: string;
}

// ========== Learning Target Management ==========
export interface TargetTaskSelection {
  taskId: string;
  taskName: string;
  chapterRef: string; // 所属章节
  selected: boolean;
}

export interface TargetClaimConfig {
  claimId: string;
  claimName: string;
  taskId: string;
  dimensions: { dimension: EvaluationDimension; label: string; enabled: boolean }[];
  trimReason?: string;
}

export interface LearningTarget {
  id: string;
  name: string;
  description: string;
  textbookId: string;
  textbookName: string;
  domainId: string;
  domainName: string;
  status: 'draft' | 'published' | 'archived';
  version: number;
  taskCount: number; // 遴选的 Task 数
  claimCount: number; // 激活的 Claim 数
  chapterCoverage: number; // 覆盖章节数
  selectedTasks: TargetTaskSelection[];
  claimConfigs: TargetClaimConfig[];
  createdAt: string;
  publishedAt?: string;
}

// ========== Learning Space Instance Management ==========
export interface ActivatedDomainSubset {
  taskCount: number;
  solutionCount: number;
  kcCount: number;
  tasks: { id: string; name: string; chapter: string }[];
}

export interface ActivatedEvaluationSubset {
  claimCount: number;
  dimensionCount: number;
  claims: { id: string; name: string; dimensions: string[] }[];
}

export interface LSInstance {
  id: string;
  name: string;
  studentId: string;
  studentName: string;
  grade: string;
  textbookId: string;
  textbookName: string;
  targetId: string;
  targetName: string;
  domainId: string;
  domainName: string;
  status: 'active' | 'paused' | 'archived';
  totalInteractions: number;
  totalEvidence: number;
  claimStatusDist: { status: string; count: number }[];
  activatedDomain: ActivatedDomainSubset;
  activatedEvaluation: ActivatedEvaluationSubset;
  createdAt: string;
  lastActive: string;
}
