// 富交互内容块类型
export type ContentBlockType =
  | 'text' | 'formula' | 'bars' | 'question' | 'progress' | 'summary' | 'phase-marker';

export interface TextBlock { type: 'text'; text: string; }
export interface FormulaBlock { type: 'formula'; text: string; }
export interface BarsBlock { type: 'bars'; caption: string; rows: { label: string; value: number }[]; }
export interface QuestionBlock {
  type: 'question'; id: string; mode: 'practice' | 'check';
  prompt: string; state: 'offered' | 'active' | 'answered' | 'helped' | 'skipped'; answer?: string;
}
export interface ProgressBlock { type: 'progress'; label: string; current: number; total: number; }
export interface SummaryBlock { type: 'summary'; title: string; points: string[]; }
export interface PhaseMarkerBlock { type: 'phase-marker'; phase: LecturePhase; label: string; }

export type ContentBlock = TextBlock | FormulaBlock | BarsBlock | QuestionBlock | ProgressBlock | SummaryBlock | PhaseMarkerBlock;

export type TeachingMode = 'lecture' | 'problem' | 'error-check' | 'review' | 'qa' | 'idle';
export type LecturePhase = 'concept' | 'example' | 'practice' | 'summary';
export type MessageRole = 'user' | 'assistant';

export interface ChatMessage {
  id: string; role: MessageRole; blocks: ContentBlock[];
  suggestions?: string[]; timestamp: number; phase?: LecturePhase;
}

export interface LearningState {
  currentChapter: string; chapterTitle: string; masteryPercent: number;
  classroomProgress: string; mode: TeachingMode;
  lecturePhase?: LecturePhase; lectureTopic?: string;
  sessionTitle?: string;
}

// 学习总览数据
export interface AbilityDimension { name: string; score: number; }
export interface MasteryTrendPoint { date: string; mastery: number; }
export interface WeakPoint { name: string; mastery: number; reason: string; suggestion: string; }
export interface LearningRhythm { weekMinutes: number; exercisesDone: number; correctRate: number; streak: number; }
export interface NextSuggestion { priority: 'high' | 'medium'; action: string; reason: string; }

// ===== Evaluation Space v1.4 能力模型类型 =====
// 四维评价维度
export type EvaluationDimension = 'independent' | 'understanding' | 'transfer' | 'retention';

// Claim 评估状态：已达标 / 发展中 / 证据不足 / 证据冲突
export type ClaimStatus = 'mastered' | 'developing' | 'insufficient' | 'conflict';

// 单个维度的评估
export interface DimensionAssessment {
  dimension: EvaluationDimension;
  label: string;
  status: ClaimStatus;
  evidenceCount: number; // 该维度已积累的证据数量
}

// 证据基础摘要
export interface EvidenceSummary {
  positive: number;    // 正向证据数
  negative: number;    // 反向证据数
  pending: number;     // 待取证项数
  conflict?: boolean;  // 是否存在证据冲突
}

// 当前学习目标评估状态（替代单一"综合掌握率"）
export interface TargetAssessment {
  targetName: string;         // 目标名称，如"比例的应用"
  overallStatus: ClaimStatus; // 总体状态
  claimCount: number;         // 涉及的 Task Claim 数量
  evidence: EvidenceSummary;  // 证据基础
  dimensions: DimensionAssessment[]; // 四维概览
  lastUpdated: string;        // 最近更新时间
}

export interface LearningOverview {
  chapter: string;
  targetAssessment: TargetAssessment; // 替代原 mastery 字段
  abilities: AbilityDimension[];
  trend: MasteryTrendPoint[];
  weakPoints: WeakPoint[];
  rhythm: LearningRhythm;
  suggestions: NextSuggestion[];
}

// 教材章节数据
export interface ChapterTopic { name: string; mastery: number; status: string; }
export interface Chapter {
  id: string; name: string; mastery: number; status: string;
  topics: ChapterTopic[]; prerequisites: string[]; description: string;
}
export interface Unit { id: string; name: string; chapters: Chapter[]; }
export interface TextbookData {
  grade: string; subject: string; units: Unit[]; currentChapterId: string;
}

// 错题本数据
export type ErrorType = '概念误解' | '计算错误' | '审题错误' | '方法不会';
export interface WrongQuestion {
  id: number; topic: string; text: string; date: string;
  errorType: ErrorType; retryCount: number; mastered: boolean;
  relatedKnowledge: string[];
}
export interface ErrorCategory { type: ErrorType; count: number; color: string; }
