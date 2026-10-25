import { reactive, computed, watch, onBeforeUnmount } from 'vue';
import type { ChatMessage, ContentBlock, TeachingMode, LecturePhase } from './types';

export type PageId = 'home' | 'status' | 'textbook' | 'errorbook';
type Command = { requestId: string; kind: string; text?: string; questionId?: string; context?: {page: PageId; label: string} };
type Turn = { id: string; role: 'user' | 'assistant'; displayText?: string; text?: string;
  blocks?: ContentBlock[]; suggestions?: string[]; at: string;
  activity?: {mode: TeachingMode; phase: LecturePhase | null; title: string} };
export interface LiveSession { id: string; revision: number; scope: {space: string}; phase: string;
  turns: Turn[]; pending: {id: string} | null; error: {message: string; retryable: boolean} | null; check: string | null }
export interface ClassroomReport { chapters: string[]; unknown: boolean; confirmedAt: string }
interface Workspace {
  version: 1; creationId: string; sessionId: string; draft: string; answers: Record<string, string>;
  page: PageId; space: string; visible: boolean; collapsed: boolean; operation: Command | null;
  classroom: Record<string, ClassroomReport[]>;
}
const key = 'deermind-next-workspace-v1';
const labels: Record<PageId,string> = {home:'首页',status:'学习情况',textbook:'教材',errorbook:'错题本'};
class ApiError extends Error { constructor(message: string, public status = 0) { super(message); } }
async function api<T>(path: string, value?: unknown): Promise<T> {
  try {
    const response = await fetch(`/api/live/${path}`, {method:value === undefined ? 'GET' : 'POST',
      headers:value === undefined ? {} : {'Content-Type':'application/json'},
      body:value === undefined ? undefined : JSON.stringify(value), signal:AbortSignal.timeout(12000)});
    const data = await response.json();
    if (!response.ok) throw new ApiError(data.error || '请求未完成。', response.status);
    return data;
  } catch (e) { if (e instanceof ApiError) throw e;
    throw new ApiError('连接中断，输入已保留。请恢复连接后再发送。'); }
}

export function useLiveWorkspace() {
  const defaults: Workspace = {version:1,creationId:crypto.randomUUID(),sessionId:'',draft:'',answers:{},
    page:'home',space:'math-6b',visible:false,collapsed:false,operation:null,classroom:{}};
  let saved: Partial<Workspace> = {};
  try { const value = JSON.parse(localStorage.getItem(key) || 'null');
    if (value?.version === 1) saved = value;
  } catch { /* Keep the corrupt source untouched until an actual workspace change is saved. */ }
  const workspace = reactive<Workspace>({...defaults,...saved});
  if (!Object.prototype.hasOwnProperty.call(labels, workspace.page)) workspace.page = 'home';
  const view = reactive({ session:null as LiveSession | null, loading:false, sending:false, error:'', connectionError:'', storageError:'' });
  function persist() {
    try { localStorage.setItem(key, JSON.stringify(workspace)); view.storageError = ''; return true; }
    catch { view.storageError = '浏览器无法保存草稿，请先保留输入并检查存储空间。'; return false; }
  }
  watch(workspace, persist, {deep:true,flush:'sync'});
  const busy = computed(() => view.loading || view.sending || !!view.session?.pending);
  const messages = computed<ChatMessage[]>(() => (view.session?.turns || []).map(t => ({id:t.id,role:t.role,
    timestamp:Date.parse(t.at),blocks:t.role === 'assistant' ? t.blocks || [] : [{type:'text',text:t.displayText || t.text || ''}],
    suggestions:t.suggestions,phase:t.activity?.phase || undefined})));
  const activity = computed(() => [...(view.session?.turns || [])].reverse().find(t => t.activity)?.activity);
  function adopt(session: LiveSession) {
    if (session.scope.space !== 'math-6b') throw new ApiError('对话课程不匹配，原记录已保留。',409);
    if (workspace.sessionId && session.id !== workspace.sessionId) return;
    if (view.session && session.id === view.session.id && session.revision < view.session.revision) return;
    workspace.sessionId = session.id; view.session = session;
  }
  let creating: Promise<void> | null = null;
  async function ensureSession() {
    if (view.session) return;
    if (!creating) creating = (async () => {
      view.loading = true;
      try { adopt(workspace.sessionId ? await api<LiveSession>(`sessions/${workspace.sessionId}`)
        : await api<LiveSession>('sessions',{space:'math-6b',creationId:workspace.creationId})); }
      finally { view.loading = false; creating = null; }
    })();
    return creating;
  }
  function acknowledge(command: Command) {
    if (command.kind === 'message' && workspace.draft.trim() === command.text?.trim()) workspace.draft = '';
    if (command.kind === 'answer' && command.questionId && workspace.answers[command.questionId]?.trim() === command.text?.trim()) delete workspace.answers[command.questionId];
    if (workspace.operation?.requestId === command.requestId) workspace.operation = null;
  }
  async function dispatch(command: Command): Promise<boolean> {
    workspace.operation = command;
    if (!persist()) return false;
    try {
      await ensureSession();
      if (view.session?.phase === 'ended' && !['end','resume'].includes(command.kind)) {
        adopt(await api<LiveSession>(`sessions/${workspace.sessionId}/commands`,
          {requestId:`${command.requestId}-resume`,kind:'resume'}));
      }
      const session = await api<LiveSession>(`sessions/${workspace.sessionId}/commands`,command);
      adopt(session); acknowledge(command); view.error = ''; return true;
    } catch (e) {
      view.error = (e as Error).message;
      // Keep the exact command ID for uncertain outcomes. Replaying it cannot create a second turn.
      if (e instanceof ApiError && e.status >= 400 && e.status < 500) workspace.operation = null;
      return false;
    }
  }
  async function command(kind: string, text?: string, questionId?: string): Promise<boolean> {
    if (workspace.space !== 'math-6b' || view.sending || (view.session?.pending && !['cancel','end'].includes(kind))) return false;
    view.sending = true;
    try {
      if (workspace.operation) {
        const unresolved = workspace.operation;
        if (!await dispatch(unresolved)) return false;
        if (unresolved.kind === kind && unresolved.text === text && unresolved.questionId === questionId) return true;
        if (view.session?.pending && !['cancel','end'].includes(kind)) return false;
      }
      const next: Command = {requestId:crypto.randomUUID(),kind,...(text !== undefined ? {text}:{}),
        ...(questionId ? {questionId}:{}),context:{page:workspace.page,label:labels[workspace.page]}};
      // Persist the request before session creation, including shortcut/button requests.
      return await dispatch(next);
    } catch (e) { view.error = (e as Error).message; return false; }
    finally { view.sending = false; }
  }
  async function refresh() {
    if (!workspace.sessionId || view.loading || view.sending) return;
    try { adopt(await api<LiveSession>(`sessions/${workspace.sessionId}`)); view.connectionError = ''; }
    catch (e) { view.connectionError = (e as Error).message; }
  }
  async function retry() {
    if (workspace.space !== 'math-6b' || view.sending || view.loading) return;
    if (workspace.operation) {
      // An uncertain HTTP result must replay its original ID before considering another model call.
      view.sending = true;
      try { await dispatch(workspace.operation); } finally { view.sending = false; }
      return;
    }
    await refresh();
    if (!view.connectionError && !view.session?.pending && view.session?.error?.retryable) await command('retry');
  }
  let timer: ReturnType<typeof setTimeout> | undefined;
  let disposed = false;
  async function poll() {
    await refresh();
    if (!disposed) timer = setTimeout(poll, view.session?.pending ? 650 : 4000);
  }
  async function restore() {
    if (workspace.operation) {
      view.sending = true;
      try { await dispatch(workspace.operation); } finally { view.sending = false; }
    }
    if (!disposed) void poll();
  }
  void restore();
  onBeforeUnmount(() => { disposed = true; clearTimeout(timer); });
  return {workspace,view,busy,messages,activity,command,refresh,retry};
}
export type LiveWorkspace = ReturnType<typeof useLiveWorkspace>;
