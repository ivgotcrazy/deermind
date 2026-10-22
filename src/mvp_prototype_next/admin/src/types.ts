// Shared rendering contracts retained from the V2 trace components.
export type SpanType = 'turn.start' | 'turn.end' | 'observation.generate' | 'observation.validate' | 'observation.commit' | 'policy.evaluate' | 'action.execute' | 'evidence.interpret' | 'belief.infer' | 'target.assess' | 'llm.invoke';
export type SpanStatus = 'success' | 'failed' | 'partial' | 'skipped' | 'running';
export interface Span { spanId:string; parentSpanId?:string; type:SpanType; label:string; startTime:number; duration:number; status:SpanStatus; detail:Record<string,unknown>; children?:Span[] }
export interface SemanticEvent { id:string; type:'observation'|'policy'|'action'|'evidence'|'belief'|'assessment'; label:string; status:'committed'|'rejected'|'updated'|'selected'; detail:string; spanId:string }
