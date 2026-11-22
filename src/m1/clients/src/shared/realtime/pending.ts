/** Unconfirmed submissions belong to one account in one browser tab. */

import { isResource, object } from './protocol';
import type { Command, ReceiptView } from './protocol';

export type RequestState =
  'sending' | 'unknown' | 'accepted' | 'completed' | 'rejected' | 'failed' | 'cancelled';

export type PendingRequest = {
  command: Command;
  state: RequestState;
  receipt?: ReceiptView;
  error?: Error;
  checkError?: string;
};

const STORAGE_KEY = 'deermind-realtime-pending-v1';

export function awaitingReceipt(state: RequestState): boolean {
  return state === 'sending' || state === 'unknown' || state === 'accepted';
}

function command(value: unknown): value is Command {
  return (
    object(value) &&
    typeof value.action === 'string' &&
    (value.receipt_action === undefined || typeof value.receipt_action === 'string') &&
    typeof value.request_id === 'string' &&
    isResource(value.resource) &&
    object(value.payload)
  );
}

export function restorePending(accountId: string): PendingRequest[] {
  const raw = sessionStorage.getItem(STORAGE_KEY);
  if (!raw) return [];
  const value: unknown = JSON.parse(raw);
  if (!object(value) || value.accountId !== accountId || !Array.isArray(value.requests)) {
    clearPending();
    return [];
  }
  const requests: PendingRequest[] = [];
  for (const item of value.requests as unknown[]) {
    if (!object(item) || !command(item.command)) continue;
    if (item.state !== 'accepted' && item.state !== 'unknown') continue;
    requests.push({ command: item.command, state: item.state });
  }
  return requests;
}

export function persistPending(accountId: string, requests: Iterable<PendingRequest>): void {
  const entries = [...requests].filter((entry) => awaitingReceipt(entry.state));
  if (!entries.length) {
    clearPending();
    return;
  }
  sessionStorage.setItem(
    STORAGE_KEY,
    JSON.stringify({
      accountId,
      requests: entries.map(({ command, state }) => ({
        command,
        state: state === 'accepted' ? 'accepted' : 'unknown',
      })),
    }),
  );
}

export function clearPending(): void {
  sessionStorage.removeItem(STORAGE_KEY);
}
