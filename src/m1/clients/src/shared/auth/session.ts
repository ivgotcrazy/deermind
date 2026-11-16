/** 只在内存保存身份；Cookie由服务端维护，旧身份响应不得恢复页面。 */
import { onBeforeUnmount, onMounted, readonly, ref } from 'vue';
import type { components } from '../../../../contracts/generated/http/schema';

type Session = components['schemas']['SessionView'];
type Phase = 'checking' | 'anonymous' | 'authenticated' | 'unavailable';

async function failure(response: Response): Promise<string> {
  const body: unknown = await response.json().catch(() => null);
  const message = body && typeof body === 'object' && 'error' in body ? body.error : null;
  if (
    message &&
    typeof message === 'object' &&
    'message' in message &&
    typeof message.message === 'string'
  ) {
    return message.message;
  }
  return '请求未完成，请稍后重试。';
}

export function useSession() {
  const session = ref<Session | null>(null);
  const phase = ref<Phase>('checking');
  const busy = ref(false);
  const error = ref('');
  let epoch = 0;
  let read: AbortController | undefined;
  let channel: BroadcastChannel | undefined;
  let expiry: ReturnType<typeof setTimeout> | undefined;
  let disposed = false;

  function clear() {
    epoch += 1;
    read?.abort();
    clearTimeout(expiry);
    session.value = null;
    phase.value = 'checking';
  }

  async function refresh(preserveError = false) {
    if (disposed) return;
    clear();
    if (!preserveError) error.value = '';
    const current = epoch;
    read = new AbortController();
    try {
      const response = await fetch('/api/m1/auth/session', {
        credentials: 'same-origin',
        cache: 'no-store',
        signal: read.signal,
      });
      const value: Session | null = response.ok ? await response.json() : null;
      const message = !response.ok && response.status !== 401 ? await failure(response) : '';
      if (disposed || current !== epoch) return;
      if (response.status === 401) {
        phase.value = 'anonymous';
      } else if (value) {
        session.value = value;
        phase.value = 'authenticated';
        // 计时器只触发重新读取，是否过期最终以服务端为准。
        expiry = setTimeout(
          () => void refresh(),
          Math.max(1000, Date.parse(value.expires_at) - Date.now()),
        );
      } else {
        phase.value = 'unavailable';
        error.value = message;
      }
    } catch {
      if (disposed || current !== epoch) return;
      phase.value = 'unavailable';
      error.value = '暂时无法确认登录状态，请检查连接后重试。';
    }
  }

  function announce(state: 'changing' | 'changed') {
    if (channel) channel.postMessage(state);
    else {
      try {
        localStorage.setItem(
          'deermind-auth-change',
          JSON.stringify({ state, nonce: crypto.randomUUID() }),
        );
      } catch {
        // 浏览器禁止本地存储时，其他标签页在返回前台时重新核验身份。
      }
    }
  }

  async function mutate(path: 'sign-in' | 'sign-out', payload: object) {
    if (busy.value) return;
    const previous = session.value;
    busy.value = true;
    error.value = '';
    const execute = async () => {
      clear();
      announce('changing');
      try {
        const headers: Record<string, string> = { 'Content-Type': 'application/json' };
        if (path === 'sign-out' && previous) {
          headers['X-Expected-Session'] = previous.session_id;
          headers['X-CSRF-Token'] = previous.csrf_token;
        }
        const response = await fetch(`/api/m1/auth/${path}`, {
          method: 'POST',
          credentials: 'same-origin',
          headers,
          body: JSON.stringify(payload),
        });
        if (!response.ok) error.value = await failure(response);
      } catch {
        // 写请求不自动重发；重新读取服务端，处理“已保存但响应丢失”。
        error.value = '连接中断；页面将以服务端返回的登录状态为准。';
      } finally {
        announce('changed');
        await refresh(true);
      }
    };
    try {
      if (navigator.locks) await navigator.locks.request('deermind-auth', execute);
      else await execute();
    } finally {
      busy.value = false;
    }
  }

  function changed(state: unknown) {
    if (state === 'changing') clear();
    if (state === 'changed') void refresh();
  }
  function storage(event: StorageEvent) {
    if (event.key !== 'deermind-auth-change' || !event.newValue) return;
    try {
      const value: unknown = JSON.parse(event.newValue);
      if (value && typeof value === 'object' && 'state' in value) changed(value.state);
    } catch {
      /* 非本应用格式不触发身份修改。 */
    }
  }
  function visible() {
    if (!document.hidden && !busy.value) void refresh();
  }

  onMounted(() => {
    if (typeof BroadcastChannel !== 'undefined') {
      channel = new BroadcastChannel('deermind-auth');
      channel.onmessage = (event: MessageEvent<unknown>) => changed(event.data);
    } else window.addEventListener('storage', storage);
    document.addEventListener('visibilitychange', visible);
    window.addEventListener('focus', visible);
    void refresh();
  });
  onBeforeUnmount(() => {
    disposed = true;
    clear();
    channel?.close();
    window.removeEventListener('storage', storage);
    window.removeEventListener('focus', visible);
    document.removeEventListener('visibilitychange', visible);
  });

  return {
    session: readonly(session),
    phase: readonly(phase),
    busy: readonly(busy),
    error: readonly(error),
    refresh,
    signIn: (login: string, password: string) =>
      mutate('sign-in', { login_identifier: login, password }),
    signOut: () => mutate('sign-out', {}),
  };
}
