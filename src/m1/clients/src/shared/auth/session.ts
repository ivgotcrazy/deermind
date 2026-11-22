/** 只在内存保存身份；Cookie由服务端维护，旧身份响应不得恢复页面。 */
import { onBeforeUnmount, onMounted, readonly, ref } from 'vue';
import { ApiError, get, post } from '../api/http';
import type { components } from '../../../../contracts/generated/http/schema';

type Session = components['schemas']['SessionView'];
type Phase = 'checking' | 'anonymous' | 'authenticated' | 'unavailable';

type AuthChange = 'changing' | 'signing-out' | 'changed';

export function useSession(onSignOut?: () => void) {
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
      const value = await get('/api/m1/auth/session', { signal: read.signal });
      if (disposed || current !== epoch) return;
      session.value = value;
      phase.value = 'authenticated';
      // 计时器只触发重新读取，是否过期最终以服务端为准。
      expiry = setTimeout(
        () => void refresh(),
        Math.max(1000, Date.parse(value.expires_at) - Date.now()),
      );
    } catch (cause) {
      if (disposed || current !== epoch) return;
      phase.value = cause instanceof ApiError && cause.status === 401 ? 'anonymous' : 'unavailable';
      if (phase.value !== 'anonymous')
        error.value = cause instanceof Error ? cause.message : '暂时无法确认登录状态。';
    }
  }

  function announce(state: AuthChange) {
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

  async function mutate(
    path: 'sign-in' | 'sign-out',
    payload?: components['schemas']['SignInRequest'],
  ) {
    if (busy.value) return;
    const previous = session.value;
    busy.value = true;
    error.value = '';
    const execute = async () => {
      clear();
      if (path === 'sign-out') onSignOut?.();
      announce(path === 'sign-out' ? 'signing-out' : 'changing');
      try {
        if (path === 'sign-in' && payload) await post('/api/m1/auth/sign-in', payload);
        else await post('/api/m1/auth/sign-out', undefined, { session: previous ?? undefined });
      } catch (cause) {
        // 登录不使用业务收据；不重发凭据，重新读取当前会话。
        error.value =
          cause instanceof ApiError
            ? cause.message
            : '连接中断；页面将以服务端返回的登录状态为准。';
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
    if (state === 'changing' || state === 'signing-out') clear();
    if (state === 'signing-out') onSignOut?.();
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
    signOut: () => mutate('sign-out'),
  };
}
