import { computed, ref, watch, onUnmounted, type Ref } from 'vue';
import { state, type Session } from '../../structure/state';
import { liveRequest, LiveRequestError, type LiveSession, type LiveCommand } from '../../structure/live';

// Protocol adapter only: no routes, screen components or teaching decisions from the old UI.
export function useConversation(session: Ref<Session | undefined>) {
  const data = ref<LiveSession>(), error = ref(''), sending = ref(false), uncertain = ref<LiveCommand>();
  const ready = ref(false);
  let generation = 0, timer: ReturnType<typeof setTimeout> | undefined;
  const busy = computed(() => sending.value || !!data.value?.pending);
  const checking = computed(() => data.value?.phase === 'check');
  const key = computed(() => session.value ? `real:${session.value.id}` : '');
  const draft = computed({ get: () => state.drafts[key.value] || '', set: (v: string) => { if (key.value) state.drafts[key.value] = v; } });
  const answer = (id: string) => state.drafts[`${key.value}:${id}`] || '';
  const setAnswer = (id: string, text: string) => { state.drafts[`${key.value}:${id}`] = text; };
  function accept(value: LiveSession, target: Session, epoch: number) {
    if (epoch !== generation || target.id !== session.value?.id) return;
    if (data.value && Date.parse(value.updatedAt) < Date.parse(data.value.updatedAt)) return;
    data.value = value; ready.value = true;
    target.status = value.phase === 'ended' ? 'ended' : value.phase === 'check' ? 'check' : 'learning';
    target.realTurns = value.turns.length; target.updatedAt = Date.parse(value.updatedAt);
    target.endedReason = value.phase === 'ended' ? '真实对话已暂停' : '';
  }
  async function refresh() {
    clearTimeout(timer);
    const target = session.value, epoch = generation;
    if (!target) return;
    try { accept(await liveRequest<LiveSession>(`sessions/${target.id}`), target, epoch); }
    catch (e) { if (epoch === generation) error.value = (e as Error).message; }
    finally { if (epoch === generation) timer = setTimeout(refresh, data.value?.pending ? 800 : 4000); }
  }
  async function perform(command: LiveCommand) {
    const target = session.value, epoch = generation;
    if (!target || sending.value) return;
    const requestKey = `real-request:${target.id}`;
    state.drafts[requestKey] = JSON.stringify(command);
    uncertain.value = command; sending.value = true; error.value = '';
    try {
      const value = await liveRequest<LiveSession>(`sessions/${target.id}/commands`, command);
      delete state.drafts[requestKey];
      if (['message', 'help', 'answer'].includes(command.kind) && state.drafts[`real:${target.id}`]?.trim() === command.text?.trim()) state.drafts[`real:${target.id}`] = '';
      if (epoch === generation) { uncertain.value = undefined; accept(value, target, epoch); }
    } catch (e) {
      if (epoch !== generation) return;
      if (e instanceof LiveRequestError && e.status < 500) { delete state.drafts[requestKey]; uncertain.value = undefined; }
      error.value = (e as Error).message;
    } finally { if (epoch === generation) sending.value = false; }
  }
  async function act(kind: string, text?: string, questionId?: string, context?: LiveCommand['context']) {
    if (!ready.value || sending.value || uncertain.value || (busy.value && kind !== 'cancel')) return;
    await perform({ requestId: crypto.randomUUID(), kind, ...(text ? { text } : {}), ...(questionId ? { questionId } : {}), ...(context ? { context } : {}) });
  }
  watch(() => session.value?.id, async () => {
    generation++; const epoch = generation; clearTimeout(timer);
    data.value = undefined; error.value = ''; sending.value = false; ready.value = false; uncertain.value = undefined;
    const saved = session.value && state.drafts[`real-request:${session.value.id}`];
    try { if (saved) uncertain.value = JSON.parse(saved); } catch { error.value = '上次请求记录无法读取，草稿仍保留。'; }
    await refresh();
    // Same persisted request ID makes refresh/re-entry safe after an interrupted handoff.
    if (epoch === generation && ready.value && uncertain.value) await perform(uncertain.value);
  }, { immediate: true });
  onUnmounted(() => { generation++; clearTimeout(timer); });
  return { data, ready, error, busy, sending, uncertain, checking, draft, answer, setAnswer, act, perform, refresh };
}
