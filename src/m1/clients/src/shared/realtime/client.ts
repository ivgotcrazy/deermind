/** One authenticated socket per tab. A notification invalidates an HTTP view. */

import { ApiError, get } from '../api/http';
import { awaitingReceipt, clearPending, persistPending, restorePending } from './pending';
import type { PendingRequest, RequestState } from './pending';
import { bytes, MESSAGE_BYTES, object, readFrame, SUBPROTOCOL } from './protocol';
import type { Command, Incoming, Outgoing, ReceiptView, Resource, SessionView } from './protocol';

const READY_TIMEOUT = 10_000;
const HEARTBEAT = 30_000;
const LOST_TIMEOUT = 90_000;
const PENDING_REFRESH = 5_000;
const VIEW_REFRESH = 30_000;
const RECONNECT = [1_000, 2_000, 4_000, 8_000, 16_000, 30_000];
const MAX_WATCHES = 4;

export type RealtimeState = 'idle' | 'connecting' | 'ready' | 'reconnecting' | 'unavailable';

export type ReceiptReader = (
  command: Command,
  session: SessionView,
  signal: AbortSignal,
) => Promise<ReceiptView>;

type SyncContext = {
  views: readonly string[];
  signal: AbortSignal;
  current: () => boolean;
  session: SessionView;
};

type Options = {
  readReceipt?: ReceiptReader;
  onSessionInvalid?: () => void;
  onState?: (state: RealtimeState) => void;
  onRequest?: (request: PendingRequest) => void;
  onStorageUnavailable?: () => void;
};

type Watch = {
  id: string;
  views: string[];
  sync: (context: SyncContext) => Promise<void>;
  frame?: string;
  ready: boolean;
  denied: boolean;
};

type Timer = ReturnType<typeof setTimeout>;
type ResourceReads = {
  resource: Resource;
  watch?: Watch;
  timer?: Timer;
  active?: AbortController;
  dirty: boolean;
  failures: number;
};

function key(resource: Resource): string {
  return JSON.stringify([resource.kind, resource.id]);
}

function readReceipt(command: Command, session: SessionView, signal: AbortSignal) {
  if (!command.receipt_action) throw new Error('此动作未登记收据查询入口。');
  return get('/api/m1/requests/receipt', {
    session,
    signal,
    query: {
      action: command.receipt_action,
      resource_kind: command.resource.kind,
      resource_id: command.resource.id,
      request_id: command.request_id,
    },
  });
}

function requestState(receipt: ReceiptView, previous: RequestState): RequestState {
  if (receipt.receipt_state === 'not_found') return previous === 'sending' ? 'unknown' : previous;
  if (receipt.receipt_state === 'rejected') return 'rejected';
  if (receipt.execution_state === 'failed' || receipt.execution_state === 'cancelled')
    return receipt.execution_state;
  if (receipt.execution_ref && receipt.execution_state !== 'completed') return 'accepted';
  return receipt.receipt_state;
}

function invalidIdentity(cause: unknown): boolean {
  return cause instanceof ApiError && (cause.status === 401 || cause.code === 'session_changed');
}

function validReceipt(value: unknown): value is ReceiptView {
  return (
    object(value) &&
    (value.receipt_state === 'not_found' ||
      value.receipt_state === 'accepted' ||
      value.receipt_state === 'completed' ||
      value.receipt_state === 'rejected')
  );
}

export class Realtime {
  private session: SessionView | null = null;
  private lastSessionId?: string;
  private accountId?: string;
  private epoch = 0;
  private socket?: WebSocket;
  private state: RealtimeState = 'idle';
  private reconnects = 0;
  private reconnectExhausted = false;
  private reconnectTimer?: Timer;
  private helloTimer?: Timer;
  private heartbeat?: Timer;
  private sessionCheck?: AbortController;
  private lastHeartbeat = 0;
  private ping?: string;
  private readonly requests = new Map<string, PendingRequest>();
  private readonly commandFrames = new Map<string, string>();
  private readonly resources = new Map<string, ResourceReads>();
  private readonly readReceipt: ReceiptReader;
  private readonly options: Options;

  constructor(options: Options = {}) {
    this.options = options;
    this.readReceipt = options.readReceipt ?? readReceipt;
    document.addEventListener('visibilitychange', this.refocus);
    window.addEventListener('focus', this.refocus);
  }

  setSession(session: SessionView | null): void {
    if (
      session?.session_id === this.session?.session_id &&
      session?.account.account_id === this.session?.account.account_id
    ) {
      this.session = session;
      return;
    }
    this.epoch += 1;
    this.session = session;
    this.sessionCheck?.abort();
    this.cancelSocket();
    this.stopReads();
    const accountId = session?.account.account_id;
    if (accountId && this.accountId && this.accountId !== accountId) this.clearPending();
    else this.markUnconfirmed(false);
    if (!session) {
      this.setState('idle');
      return;
    }
    const currentAccount = session.account.account_id;
    if (this.accountId !== currentAccount) {
      this.accountId = currentAccount;
      try {
        for (const request of restorePending(currentAccount)) {
          this.requests.set(request.command.request_id, request);
          this.group(request.command.resource);
        }
      } catch {
        this.options.onStorageUnavailable?.();
      }
    }
    for (const request of this.requests.values()) this.report(request);
    if (session.session_id !== this.lastSessionId) {
      this.lastSessionId = session.session_id;
      this.reconnects = 0;
      this.reconnectExhausted = false;
    }
    if (this.reconnectExhausted) this.deferReconnect();
    else this.open();
  }

  watch(resource: Resource, views: string[], sync: Watch['sync']): () => void {
    if (!this.session) throw new Error('请先登录再订阅资源。');
    if (!views.length) throw new Error('请指定要订阅的视图。');
    const group = this.group(resource);
    if (group.watch) throw new Error('此资源已有订阅。');
    if ([...this.resources.values()].filter((entry) => entry.watch).length >= MAX_WATCHES)
      throw new Error('当前连接的订阅已达上限。');
    const watch: Watch = {
      id: crypto.randomUUID(),
      views: [...new Set(views)],
      sync,
      ready: false,
      denied: false,
    };
    group.watch = watch;
    this.subscribe(group);
    if (this.state === 'unavailable') this.refresh(group);
    return () => {
      if (group.watch !== watch || this.resources.get(key(group.resource)) !== group) return;
      group.watch = undefined;
      group.active?.abort();
      this.sendFrame({ type: 'unwatch', frame_id: crypto.randomUUID(), watch_id: watch.id });
      this.refresh(group);
    };
  }

  send(input: Omit<Command, 'request_id'> & { request_id?: string }): string {
    if (!this.session || this.state !== 'ready') throw new Error('请等待实时连接恢复后再发送。');
    if (!input.receipt_action && !this.options.readReceipt)
      throw new Error('此动作未登记收据查询入口。');
    const command: Command = {
      action: input.action,
      receipt_action: input.receipt_action,
      request_id: input.request_id ?? crypto.randomUUID(),
      resource: { kind: input.resource.kind, id: input.resource.id },
      payload: structuredClone(input.payload),
    };
    if (this.requests.has(command.request_id)) throw new Error('该请求已经登记。');
    this.dispatch(command);
    return command.request_id;
  }

  retry(requestId: string): void {
    if (!this.session || this.state !== 'ready') throw new Error('请等待实时连接恢复后再发送。');
    const request = this.requests.get(requestId);
    if (!request || request.state !== 'unknown') throw new Error('此请求当前不可重试。');
    this.dispatch(request.command);
  }

  reconnect(): void {
    if (!this.session || this.state === 'ready') return;
    this.cancelSocket();
    this.reconnects = 0;
    this.reconnectExhausted = false;
    this.open();
  }

  clearPending(): void {
    this.requests.clear();
    this.commandFrames.clear();
    this.stopReads();
    this.resources.clear();
    try {
      clearPending();
    } catch {
      this.options.onStorageUnavailable?.();
    }
  }

  dispose(): void {
    this.setSession(null);
    document.removeEventListener('visibilitychange', this.refocus);
    window.removeEventListener('focus', this.refocus);
  }

  private open(): void {
    const session = this.session;
    if (!session) return;
    this.setState(this.reconnects ? 'reconnecting' : 'connecting');
    const url = new URL('/ws', window.location.origin);
    url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
    const socket = new WebSocket(url, SUBPROTOCOL);
    this.socket = socket;
    let authenticated = false;
    this.helloTimer = setTimeout(() => socket.close(), READY_TIMEOUT);
    socket.onopen = () => {
      if (socket !== this.socket) return;
      if (socket.protocol !== SUBPROTOCOL) {
        socket.close();
        return;
      }
      this.sendFrame({
        type: 'hello',
        session_id: session.session_id,
        csrf_token: session.csrf_token,
      });
    };
    socket.onmessage = (event: MessageEvent<unknown>) => {
      if (socket !== this.socket) return;
      const frame = readFrame(event.data);
      if (!frame || (frame.type === 'ready') === authenticated) {
        socket.close(4002, 'invalid frame');
        return;
      }
      if (frame.type === 'ready') {
        authenticated = true;
        this.ready();
      } else this.receive(frame);
    };
    socket.onclose = (event) => {
      if (socket !== this.socket) return;
      this.cancelSocket();
      this.markUnconfirmed();
      this.stopReads();
      if (event.code === 4401) this.invalidSession();
      else {
        if (!authenticated) void this.verifySession(session);
        this.deferReconnect();
      }
    };
  }

  private ready(): void {
    clearTimeout(this.helloTimer);
    this.reconnects = 0;
    this.lastHeartbeat = Date.now();
    this.setState('ready');
    for (const group of this.resources.values()) {
      if (group.watch) {
        if (!group.watch.frame) this.subscribe(group);
      } else this.refresh(group);
    }
    this.heartbeat = setInterval(() => {
      if (Date.now() - this.lastHeartbeat >= LOST_TIMEOUT) {
        this.socket?.close();
        return;
      }
      this.ping = crypto.randomUUID();
      this.sendFrame({ type: 'ping', frame_id: this.ping });
    }, HEARTBEAT);
  }

  private cancelSocket(): void {
    clearTimeout(this.reconnectTimer);
    clearTimeout(this.helloTimer);
    clearInterval(this.heartbeat);
    const socket = this.socket;
    this.socket = undefined;
    socket?.close();
  }

  private deferReconnect(): void {
    const delay = RECONNECT[this.reconnects];
    if (delay === undefined) {
      this.reconnectExhausted = true;
      this.setState('unavailable');
      for (const group of this.resources.values()) this.refresh(group);
      return;
    }
    this.reconnects += 1;
    this.setState('reconnecting');
    this.reconnectTimer = setTimeout(
      () => this.open(),
      Math.min(30_000, delay * (0.8 + Math.random() * 0.4)),
    );
  }

  private async verifySession(expected: SessionView): Promise<void> {
    if (this.sessionCheck && !this.sessionCheck.signal.aborted) return;
    const check = new AbortController();
    const generation = this.epoch;
    this.sessionCheck = check;
    try {
      const actual = await get('/api/m1/auth/session', { session: expected, signal: check.signal });
      if (generation !== this.epoch) return;
      if (actual.session_id !== expected.session_id) this.invalidSession();
    } catch (cause) {
      if (generation === this.epoch && invalidIdentity(cause)) this.invalidSession();
    } finally {
      if (this.sessionCheck === check) this.sessionCheck = undefined;
    }
  }

  private invalidSession(): void {
    this.setSession(null);
    this.options.onSessionInvalid?.();
  }

  private setState(state: RealtimeState): void {
    if (this.state === state) return;
    this.state = state;
    this.options.onState?.(state);
  }

  private subscribe(group: ResourceReads): void {
    if (this.state !== 'ready' || !group.watch) return;
    const watch = group.watch;
    group.active?.abort();
    watch.ready = false;
    watch.frame = crypto.randomUUID();
    this.sendFrame({
      type: 'watch',
      frame_id: watch.frame,
      watch_id: watch.id,
      resource: group.resource,
      views: watch.views,
    });
  }

  private receive(frame: Exclude<Incoming, { type: 'ready' }>): void {
    switch (frame.type) {
      case 'ping':
        this.lastHeartbeat = Date.now();
        this.sendFrame({ type: 'pong', frame_id: frame.frame_id });
        break;
      case 'pong':
        if (frame.frame_id === this.ping) this.lastHeartbeat = Date.now();
        break;
      case 'resync_required':
        for (const group of this.resources.values()) {
          if (group.watch && (!frame.watch_id || frame.watch_id === group.watch.id))
            this.subscribe(group);
        }
        break;
      case 'watch_ready':
      case 'changed': {
        const group = this.resources.get(key(frame.resource));
        const watch = group?.watch;
        if (!group || !watch || watch.id !== frame.watch_id) break;
        if (frame.type === 'watch_ready') {
          if (watch.frame !== frame.frame_id) break;
          if (!watch.views.every((view) => frame.views.includes(view))) break;
          watch.ready = true;
          watch.denied = false;
        } else if (!watch.ready || !frame.views.some((view) => watch.views.includes(view))) break;
        this.refresh(group);
        break;
      }
      case 'receipt':
        this.receiveCommand(frame);
        break;
      case 'error':
        if (frame.request_id) this.receiveCommand(frame);
        else if (frame.frame_id) {
          for (const group of this.resources.values()) {
            if (group.watch?.frame !== frame.frame_id) continue;
            group.watch.denied = true;
            this.refresh(group);
            break;
          }
        }
        break;
    }
  }

  private receiveCommand(frame: Extract<Incoming, { type: 'receipt' | 'error' }>): void {
    if (!frame.request_id || !frame.frame_id) return;
    if (this.commandFrames.get(frame.request_id) !== frame.frame_id) return;
    const request = this.requests.get(frame.request_id);
    if (!request) return;
    this.commandFrames.delete(frame.request_id);
    if (frame.type === 'receipt') {
      const receipt: ReceiptView = {
        receipt_state: frame.state,
        receipt_ref: frame.owner_receipt_ref,
        execution_ref: frame.execution_ref,
        result_refs: frame.result_refs,
      };
      // Even a completed acknowledgement still needs its authoritative HTTP result.
      this.save({ command: request.command, state: 'accepted', receipt });
    } else {
      this.save({
        command: request.command,
        state: frame.acceptance === 'unknown' ? 'unknown' : 'rejected',
        error: new Error(frame.error.message),
      });
    }
    this.refresh(this.group(request.command.resource));
  }

  private sendFrame(frame: Outgoing): boolean {
    const socket = this.socket;
    if (socket?.readyState !== WebSocket.OPEN) return false;
    const encoded = JSON.stringify(frame);
    const size = bytes(encoded);
    if (size > MESSAGE_BYTES) throw new Error('消息超过 64 KiB。请缩小内容后再发送。');
    if (socket.bufferedAmount + size > MESSAGE_BYTES) {
      socket.close();
      return false;
    }
    socket.send(encoded);
    return true;
  }

  private dispatch(command: Command): void {
    const frameId = crypto.randomUUID();
    const frame = {
      type: 'command',
      frame_id: frameId,
      action: command.action,
      request_id: command.request_id,
      resource: command.resource,
      payload: command.payload,
    } as const;
    const projected = JSON.stringify({ ...frame, frame_id: command.request_id });
    if (bytes(projected) > MESSAGE_BYTES) throw new Error('消息超过 64 KiB。请缩小内容后再发送。');
    if (!this.sendFrame(frame)) throw new Error('连接中断。请恢复连接后再发送。');
    this.commandFrames.set(command.request_id, frameId);
    this.save({ command, state: 'sending' });
    const group = this.group(command.resource);
    this.schedule(group, group.dirty ? 0 : PENDING_REFRESH);
  }

  private save(request: PendingRequest, report = true): void {
    if (awaitingReceipt(request.state)) this.requests.set(request.command.request_id, request);
    else this.requests.delete(request.command.request_id);
    if (report) this.report(request);
    if (!this.accountId) return;
    try {
      persistPending(this.accountId, this.requests.values());
    } catch {
      this.options.onStorageUnavailable?.();
    }
  }

  private report(request: PendingRequest): void {
    this.options.onRequest?.(structuredClone(request));
  }

  private markUnconfirmed(report = true): void {
    this.commandFrames.clear();
    for (const request of this.requests.values()) {
      if (request.state === 'sending') this.save({ ...request, state: 'unknown' }, report);
    }
  }

  private group(resource: Resource): ResourceReads {
    const id = key(resource);
    let group = this.resources.get(id);
    if (!group) {
      group = { resource: { ...resource }, dirty: false, failures: 0 };
      this.resources.set(id, group);
    }
    return group;
  }

  private pendingFor(group: ResourceReads): PendingRequest[] {
    const id = key(group.resource);
    return [...this.requests.values()].filter((request) => key(request.command.resource) === id);
  }

  private refresh(group: ResourceReads): void {
    group.dirty = true;
    this.schedule(group, 0);
  }

  private schedule(group: ResourceReads, delay: number): void {
    if (group.active || !this.session || document.hidden) return;
    clearTimeout(group.timer);
    if (!this.canReadView(group.watch) && !this.pendingFor(group).length) {
      if (!group.watch) this.resources.delete(key(group.resource));
      return;
    }
    if (this.state !== 'ready' && this.state !== 'unavailable') return;
    if (this.state === 'ready' && group.watch && !group.watch.ready && !group.watch.denied) return;
    group.timer = setTimeout(() => void this.sync(group), delay);
  }

  private canReadView(watch?: Watch): watch is Watch {
    return !!watch && (watch.ready || (this.state === 'unavailable' && !watch.denied));
  }

  private async sync(group: ResourceReads): Promise<void> {
    const session = this.session;
    if (!session || document.hidden || group.active) return;
    const generation = this.epoch;
    const active = new AbortController();
    group.active = active;
    group.dirty = false;
    const watch = group.watch;
    const current = () =>
      generation === this.epoch &&
      !active.signal.aborted &&
      this.resources.get(key(group.resource)) === group;
    let failed = false;
    try {
      if (this.canReadView(watch)) {
        try {
          await watch.sync({ views: watch.views, signal: active.signal, current, session });
        } catch (cause) {
          if (current() && invalidIdentity(cause)) this.invalidSession();
          failed = true;
        }
      }
      for (const request of this.pendingFor(group)) {
        if (!current()) break;
        const id = request.command.request_id;
        try {
          const receipt = await this.readReceipt(request.command, session, active.signal);
          if (!validReceipt(receipt)) throw new Error('服务返回的收据格式不正确。');
          if (current() && this.requests.get(id) === request) {
            const state = requestState(receipt, request.state);
            const saved = receipt.receipt_state === 'not_found' ? request.receipt : receipt;
            this.save({ command: request.command, state, receipt: saved });
          }
        } catch (cause) {
          if (!current()) break;
          if (invalidIdentity(cause)) this.invalidSession();
          else if (this.requests.get(id) === request) {
            this.save({ ...request, checkError: '暂时无法核对原请求，请稍候。' });
            failed = true;
          }
        }
      }
    } finally {
      group.active = undefined;
      if (this.resources.get(key(group.resource)) === group) {
        group.failures = failed ? group.failures + 1 : 0;
        const interval = this.pendingFor(group).length ? PENDING_REFRESH : VIEW_REFRESH;
        this.schedule(
          group,
          group.dirty && !failed ? 0 : Math.min(VIEW_REFRESH, interval * 2 ** group.failures),
        );
      }
    }
  }

  private stopReads(): void {
    for (const group of this.resources.values()) {
      clearTimeout(group.timer);
      group.active?.abort();
      if (group.watch) {
        group.watch.ready = false;
        group.watch.frame = undefined;
      }
    }
  }

  private refocus = (): void => {
    if (!this.session) return;
    for (const group of this.resources.values()) {
      if (document.hidden) clearTimeout(group.timer);
      else this.refresh(group);
    }
  };
}
