export type LiveBlock = { type: 'text' | 'formula'; text: string } | { type: 'bars'; caption: string; rows: {label:string;value:number}[] } | { type: 'question'; id: string; mode: 'practice'|'check'; prompt: string; state: 'offered'|'active'|'answered'|'helped'|'skipped'; answer?: string };
export type LiveTurn = { id: string; role: 'user'|'assistant'; text?: string; displayText?: string; action?: string; blocks?: LiveBlock[]; suggestions?: string[]; at: string; metrics?: {ms:number;calls:{usage?:{total_tokens:number}}[]} };
export type LiveSession = { id:string;model:string;chapter:string;phase:'learning'|'check'|'ended';check:string|null;turns:LiveTurn[];pending:{id:string;startedAt:string}|null;error:{message:string;retryable:boolean}|null;updatedAt:string };
export type LiveCommand = { requestId:string; kind:string; text?:string;questionId?:string };
export class LiveRequestError extends Error {constructor(message:string,public status:number){super(message);}}
export async function liveRequest<T>(path:string, body?:unknown):Promise<T> {
  const controller = new AbortController(), timer = setTimeout(()=>controller.abort(), 15000);
  try {
    const response = await fetch(`/api/live/${path}`, { method:body?'POST':'GET', headers:body?{'Content-Type':'application/json','X-DeerMind-Live':'1'}:undefined, body:body?JSON.stringify(body):undefined, signal:controller.signal });
    const value = await response.json();
    if (!response.ok) throw new LiveRequestError(value.error || '本地服务返回异常。',response.status);
    return value;
  } catch(e) { if(e instanceof Error&&e.name!=='AbortError'&&!(e instanceof TypeError)) throw e; throw Error('无法连接本地服务。输入已保留，请检查启动脚本后重试。'); }
  finally { clearTimeout(timer); }
}
