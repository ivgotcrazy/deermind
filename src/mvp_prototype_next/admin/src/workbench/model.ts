export type Space = 'Domain' | 'Evaluation' | 'Interaction' | 'Learning' | 'Evolution';
export type Kind = 'task' | 'solution' | 'kc' | 'claim' | 'evidence-rule' | 'inference-rule' | 'material' | 'chapter' | 'mapping' | 'target' | 'observation' | 'policy' | 'action' | 'evidence' | 'belief' | 'assessment';
export interface Relation { label: string; ref: string }
export interface Aspect { key: string; label: string; criterion: string; evidence: string; applicable: boolean; reason?: string }
export interface AspectState { key: string; judgment: string; uncertainty: string; evidence: string[]; note: string }
export interface ModelObject {
  id: string; version: number; kind: Kind; space: Space; model: string; name: string;
  summary: string; status: 'published' | 'draft' | 'recorded'; source: string;
  fields: Record<string, string>; relations: Relation[]; aspects?: Aspect[]; states?: AspectState[];
  requiredAspects?: string[]; referenceVersions?: Record<string,number>; domainId?: string; at: string;
}
export interface Domain { id: string; name: string; scope: string; description: string; createdAt: string; version?: number; history?: {name:string;scope:string;description:string;version:number;at:string}[] }
export interface Adoption { at: string; issueId: string; before: Record<string, number>; after: Record<string, number>; reason: string }
export interface LearningContext { id: string; name: string; studentId: string; studentName: string; chapters: string[]; material: string; target: string; adopted: Record<string, number>; history: Adoption[] }
export interface Fact { id: string; at: string; actor: string; text: string; kind: string; object?: string }
export interface Activity { id: string; name: string; ls: string; at: string; facts: Fact[]; objects: string[]; versions: Record<string, number>; note: string }
export interface Check { name: string; passed: boolean; detail: string }
export interface CheckRun { at: string; signature: string; checks: Check[]; cases: { id: string; before: string; after: string; note: string; verdict?: 'pass' | 'fail'; review?: string }[] }
export interface Impact { space: string; status: 'pending' | 'failed' | 'done' | 'unresolved'; detail: string }
export interface Issue {
  id: string; title: string; origin: string; purpose: string; finding: string; conclusion: string;
  verdict: 'open' | 'confirmed' | 'reasonable' | 'insufficient'; candidate?: ModelObject;
  baseVersion?: number; proposedNew?: boolean; delivery?: boolean; sampleCases: string[]; check?: CheckRun;
  approval?: { at: string; reason: string; signature: string }; published?: string;
  impacts: Impact[]; log: { at: string; text: string }[]; dataMode: 'demo' | 'real';
}
export interface Preparation { chapter: string; reviewed: boolean; note: string; at?: string }
export interface ObjectDraft { id:string; object:ModelObject; baseVersion:number; sourceIssueId?:string; at:string }
export interface Change { ref:string; beforeVersion:number; at:string; note:string }
export interface Annotation { id:string; subject:string; text:string; at:string; mode:'demo'|'real' }
export interface AdminState {
  schema: 3; revision: number; domains: Domain[]; objects: ModelObject[]; spaces: LearningContext[]; activities: Activity[];
  drafts:ObjectDraft[]; changes:Change[]; annotations:Annotation[];
  issues: Issue[]; preparations: Preparation[]; invalidated: Record<string,string>; access: { at: string; ref: string; purpose: string; mode: string }[];
}
export const kinds: Record<Kind, string> = {task:'任务模板',solution:'方法模板',kc:'知识成分',claim:'Task Claim','evidence-rule':'证据解释规则','inference-rule':'推断规则',material:'教材',chapter:'章节',mapping:'教材映射',target:'学习目标',observation:'Observation',policy:'决策',action:'实际行动',evidence:'Evidence',belief:'Task Belief',assessment:'目标评价'};
export const aspectNames: Record<string,string> = {independent:'独立完成',understanding:'理解与解释',transfer:'迁移',retention:'延迟保持'};
export const objectKey = (o: Pick<ModelObject,'id'|'version'>) => `${o.id}@${o.version}`;
export const editableKinds: Kind[] = ['task','solution','kc','mapping','target','material','chapter'];
export const personalKinds: Kind[] = ['observation','policy','action','evidence','belief','assessment'];
