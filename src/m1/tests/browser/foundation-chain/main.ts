import { get, post } from '../../../clients/src/shared/api/http';
import { Realtime } from '../../../clients/src/shared/realtime/client';
import { object } from '../../../clients/src/shared/realtime/protocol';
import type { SessionView } from '../../../clients/src/shared/realtime/protocol';

const action = 'test.foundation_chain';
const text = '四分之一合成输入';
const form = document.querySelector('form')!;
const socket = document.querySelector('#socket')!;
const watch = document.querySelector('#watch')!;
const failure = document.querySelector('#failure')!;
const cases = new Map(
  Array.from(document.querySelectorAll<HTMLElement>('[data-case]'), (row) => {
    const requestId: string = crypto.randomUUID();
    row.dataset.requestId = requestId;
    return [
      requestId,
      {
        button: row.querySelector('button')!,
        state: row.querySelector('.state')!,
        result: row.querySelector('.result')!,
        resultRead: undefined as AbortController | undefined,
      },
    ];
  }),
);
let session: SessionView | null = null;

const realtime = new Realtime({
  onState: (state) => {
    socket.textContent = state;
    if (state !== 'ready') watch.textContent = 'waiting';
    enableButtons();
  },
  onRequest: ({ command, state, receipt }) => {
    const row = cases.get(command.request_id);
    if (!row) return;
    row.state.textContent = state;
    row.result.textContent = '';
    row.resultRead?.abort();
    const reference: unknown = Array.isArray(receipt?.result_refs) ? receipt.result_refs[0] : null;
    if (state === 'completed' && object(reference) && typeof reference.id === 'string' && session) {
      const read = new AbortController();
      row.resultRead = read;
      void readResult(reference.id, session.session_id, read.signal)
        .then((sha256) => {
          if (!read.signal.aborted) row.result.textContent = sha256;
        })
        .catch(() => {
          if (!read.signal.aborted) failure.textContent = '正式结果读取失败';
        });
    }
    enableButtons();
  },
  onSessionInvalid: () => {
    session = null;
    for (const row of cases.values()) row.resultRead?.abort();
    failure.textContent = '登录状态已变';
  },
});

async function readResult(id: string, sessionId: string, signal: AbortSignal): Promise<string> {
  const response = await fetch(`/api/m1/test/foundation-chain/results/${encodeURIComponent(id)}`, {
    headers: { 'X-Expected-Session': sessionId },
    credentials: 'same-origin',
    cache: 'no-store',
    signal,
  });
  const result: unknown = await response.json();
  if (
    !response.ok ||
    !object(result) ||
    result.execution_id !== id ||
    typeof result.sha256 !== 'string'
  )
    throw new Error('结果与引用不符。');
  return result.sha256;
}

function enableButtons(): void {
  for (const row of cases.values()) {
    row.button.disabled =
      socket.textContent !== 'ready' ||
      watch.textContent !== 'ready' ||
      ['sending', 'unknown', 'accepted'].includes(row.state.textContent ?? '');
  }
}

form.addEventListener('submit', (event) => {
  event.preventDefault();
  const input = new FormData(form);
  form.reset();
  void signIn(String(input.get('login')), String(input.get('password'))).catch(() => {
    failure.textContent = '合成账号登录失败';
  });
});

async function signIn(login: string, password: string): Promise<void> {
  await post('/api/m1/auth/sign-in', { login_identifier: login, password });
  session = await get('/api/m1/auth/session');
  const resource = { kind: 'account', id: session.account.account_id };
  form.hidden = true;
  for (const [requestId, row] of cases.entries()) {
    row.button.onclick = () => {
      realtime.send({
        action,
        receipt_action: action,
        request_id: requestId,
        resource,
        payload: { text },
      });
    };
  }
  realtime.setSession(session);
  realtime.watch(resource, ['foundation_chain'], async ({ current }) => {
    if (!current()) return;
    // Realtime reads the authorized R04 result for unfinished requests after this notification.
    watch.textContent = 'ready';
    enableButtons();
  });
}
