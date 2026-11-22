import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import { build } from 'vite';

const entry = fileURLToPath(new URL('../../src/shared/realtime/client.ts', import.meta.url));
const bundle = await build({
  configFile: false,
  logLevel: 'silent',
  build: { write: false, lib: { entry, formats: ['es'] }, minify: false },
});
const { code } = bundle[0].output[0];
const { Realtime } = await import(
  'data:text/javascript;base64,' + Buffer.from(code).toString('base64')
);

// Use a deterministic clock to exercise the 61-second retry sequence without sleeping.

let timestamp = 0;
let nextTimer = 1;
const timers = new Map();
Date.now = () => timestamp;
Math.random = () => 0.5;
function queue(run, delay, repeat = 0) {
  const id = nextTimer++;
  timers.set(id, { run, time: timestamp + Number(delay), repeat });
  return id;
}
globalThis.clearTimeout = globalThis.clearInterval = (id) => timers.delete(id);
globalThis.setTimeout = queue;
globalThis.setInterval = (run, delay) => queue(run, delay, delay);
const flush = async () => {
  for (let i = 0; i < 12; i++) await Promise.resolve();
};
async function tick(delta = 0) {
  await flush();
  const until = timestamp + delta;
  while (true) {
    const available = [...timers]
      .filter(([, timer]) => timer.time <= until)
      .sort((a, b) => a[1].time - b[1].time);
    if (!available.length) break;
    const [id, timer] = available[0];
    timestamp = timer.time;
    if (timer.repeat) timer.time += timer.repeat;
    else timers.delete(id);
    timer.run();
    await flush();
  }
  timestamp = until;
  await flush();
}
globalThis.window = Object.assign(new EventTarget(), {
  location: { origin: 'http://localhost:7899' },
});
globalThis.document = Object.assign(new EventTarget(), { hidden: false });
const storage = new Map();
globalThis.sessionStorage = {
  getItem: (k) => storage.get(k),
  setItem: (k, v) => storage.set(k, v),
  removeItem: (k) => storage.delete(k),
};
globalThis.fetch = async (_, opts) =>
  Response.json({ session_id: opts.headers['X-Expected-Session'] });
const sockets = [];
globalThis.WebSocket = class {
  static OPEN = 1;
  protocol = 'deermind.v1';
  readyState = 0;
  bufferedAmount = 0;
  frames = [];
  constructor(url, protocol) {
    assert.equal(url.href, 'ws://localhost:7899/ws');
    assert.equal(protocol, this.protocol);
    sockets.push(this);
  }
  send(value) {
    this.frames.push(JSON.parse(value));
  }
  close() {
    this.readyState = 3;
  }
  fail() {
    this.close();
    this.onclose({ code: 1006 });
  }
  receive(frame) {
    this.onmessage({ data: JSON.stringify(frame) });
  }
  login(id) {
    this.readyState = 1;
    this.onopen();
    assert.deepEqual(this.frames[0], { type: 'hello', session_id: id, csrf_token: 'csrf-' + id });
    this.receive({ type: 'ready', connection_id: id, server_time: '2026-11-22T10:00:00Z' });
  }
  ack(resource) {
    const { frame_id, watch_id, views } = this.frames.find(
      (x) => x.type === 'watch' && x.resource.id === resource.id,
    );
    this.receive({ type: 'watch_ready', frame_id, watch_id, resource, views });
  }
};
const session = (sessionId, accountId) => ({
  session_id: sessionId,
  account: { account_id: accountId },
  csrf_token: 'csrf-' + sessionId,
});
const a = { kind: 'learning_space', id: 'a' };
const b = { kind: 'learning_space', id: 'b' };
const accountA = session('login-a', 'alice');
const accountB = session('login-b', 'bob');
const accountB2 = session('login-b2', 'bob');
const events = [];
const states = [];
const client = new Realtime({
  onState: (state) => states.push(state),
  onRequest: (request) => events.push(request),
  readReceipt: async (cmd, liveSession) => {
    assert.equal(cmd.request_id, 'req-b');
    assert.equal(liveSession.session_id, 'login-b2');
    return { receipt_state: receipt };
  },
});
client.setSession(accountA);
const begin = [];
const rendered = [];
client.watch(a, ['conversation'], async (ctx) => {
  begin.push(ctx);
  await new Promise((resolve) => {
    ctx.release = resolve;
  });
  if (ctx.current()) rendered.push(ctx.session.account.account_id);
});
const first = sockets[0];
first.login('login-a');
first.ack(a);
await tick();
assert.equal(begin.length, 1);
const watch = first.frames.find((x) => x.type === 'watch');
for (let count = 0; count < 3; count++) {
  first.receive({
    type: 'changed',
    watch_id: watch.watch_id,
    resource: a,
    views: ['conversation'],
    request_id: null,
  });
}
await tick();
assert.equal(begin.length, 1, 'notifications wait for the current HTTP read');
begin[0].release();
await tick();
assert.equal(begin.length, 2, 'three hints collapse into one follow-up');
client.setSession(accountB);
assert.equal(begin[1].signal.aborted, true);
begin[1].release();
await tick();
assert.deepEqual(rendered, ['alice'], 'old account response is discarded');
let authorized = 0;
let denied = 0;
client.watch(a, ['conversation'], async () => {
  authorized++;
});
client.watch(b, ['activity_tree'], async () => {
  denied++;
});
const second = sockets[1];
second.login('login-b');
second.ack(a);
const rejected = second.frames.find((x) => x.type === 'watch' && x.resource.id === b.id);
second.receive({
  type: 'error',
  frame_id: rejected.frame_id,
  request_id: null,
  error: { code: 'not_found', message: 'No access', issues: [], retryable: false },
  acceptance: 'not_accepted',
});
await tick();
assert.equal(authorized, 1);
assert.equal(denied, 0);
second.fail();
for (const gap of [1000, 2000, 4000, 8000, 16000, 30000]) {
  await tick(gap);
  sockets.at(-1).fail();
}
await tick();
assert.deepEqual(states.slice(-2), ['reconnecting', 'unavailable']);
assert.equal(sockets.length, 8, 'six automatic retries then stop');
assert.equal(authorized, 2, 'HTTP fallback refreshes allowed views');
assert.equal(denied, 0, 'HTTP fallback never polls a denied watch');
await tick(30000);
assert.equal(authorized, 3);
assert.equal(denied, 0);
client.setSession(null);
client.setSession(accountB);
await tick();
assert.equal(sockets.length, 8, 'same-session revalidation preserves the retry limit');
assert.equal(authorized, 4);
client.reconnect();
const third = sockets.at(-1);
assert.equal(sockets.length, 9);
third.login('login-b');
third.ack(a);
await tick();
const payload = { body: { text: '请给一点提示' } };
client.send({ action: 'learning.input', resource: a, payload, request_id: 'req-b' });
payload.body.text = 'local edit';
const original = third.frames.find((x) => x.type === 'command');
assert.equal(original.payload.body.text, '请给一点提示');
assert.equal(events.at(-1).state, 'sending');
assert.ok(![...storage.values()][0].includes('csrf'));
third.fail();
assert.equal(events.at(-1).state, 'unknown');
let receipt = 'not_found';
client.setSession(accountB2);
const fourth = sockets.at(-1);
fourth.login('login-b2');
fourth.ack(a);
await tick();
assert.ok(!fourth.frames.some((x) => x.type === 'command'), 'reconnect does not replay writes');
assert.equal(events.at(-1).state, 'unknown');
client.retry('req-b');
const retried = fourth.frames.find((x) => x.type === 'command');
assert.notEqual(retried.frame_id, original.frame_id);
assert.deepEqual({ ...retried, frame_id: original.frame_id }, original);
receipt = 'completed';
await tick(5000);
assert.equal(events.at(-1).state, 'completed');
assert.equal(storage.size, 0);
client.dispose();
