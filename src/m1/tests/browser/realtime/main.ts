import { get, post } from '../../../clients/src/shared/api/http';
import { Realtime } from '../../../clients/src/shared/realtime/client';

const form = document.querySelector('form')!;
const confirm = document.querySelector<HTMLButtonElement>('#confirm')!;
const view = document.querySelector('#view')!;
const socket = document.querySelector('#socket')!;
const request = document.querySelector('#request')!;
const failure = document.querySelector('#failure')!;

const realtime = new Realtime({
  readReceipt: (command, session, signal) =>
    get('/api/m1/requests/receipt', {
      session,
      signal,
      query: {
        action: 'product.record_usage_confirmation',
        resource_kind: command.resource.kind,
        resource_id: command.resource.id,
        request_id: command.request_id,
      },
    }),
  onState: (state) => {
    socket.textContent = state;
  },
  onRequest: (result) => {
    request.textContent = result.state;
  },
  onSessionInvalid: () => {
    failure.textContent = '登录状态已变';
  },
});

form.addEventListener('submit', (event) => {
  event.preventDefault();
  const input = new FormData(form);
  void signIn(String(input.get('login')), String(input.get('password'))).catch((error: Error) => {
    failure.textContent = error.message;
  });
});

async function signIn(login: string, password: string): Promise<void> {
  await post('/api/m1/auth/sign-in', { login_identifier: login, password });
  const session = await get('/api/m1/auth/session');
  const resource = { kind: 'account', id: session.account.account_id };
  form.hidden = true;
  realtime.setSession(session);
  realtime.watch(resource, ['usage'], async ({ session: currentSession, signal, current }) => {
    const usage = await get('/api/m1/usage-conditions', { session: currentSession, signal });
    if (!current()) return;
    view.textContent = usage.allowed ? '已通过' : '待确认';
    if (!usage.can_confirm || usage.allowed) return;
    confirm.disabled = false;
    confirm.onclick = () => {
      confirm.disabled = true;
      realtime.send({
        action: 'test.confirm',
        resource,
        payload: {
          expected_revision: usage.revision,
          confirmation: {
            student_id: usage.student_id,
            kind: 'student_assent',
            decision: 'accepted',
            notice_ref: usage.notice_ref,
            source_ref: usage.source_ref,
          },
        },
      });
    };
  });
}
