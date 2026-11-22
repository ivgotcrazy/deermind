/** Shared WebSocket envelope, with runtime checks at the browser receive boundary. */

import type { components } from '../../../../contracts/generated/http/schema';
import type { DeepReadonly } from 'vue';

export const SUBPROTOCOL = 'deermind.v1';
export const MESSAGE_BYTES = 64 * 1024;

export type SessionView = DeepReadonly<components['schemas']['SessionView']>;
export type Resource = { kind: string; id: string };

type JsonValue = null | boolean | number | string | JsonValue[] | { [key: string]: JsonValue };

export type Command = {
  action: string;
  receipt_action?: string;
  request_id: string;
  resource: Resource;
  payload: Record<string, JsonValue>;
};

export type ReceiptView = Pick<
  components['schemas']['ReceiptView_ConfirmationResult_'],
  'receipt_state' | 'business_state' | 'execution_ref' | 'execution_state'
> & { [key: string]: unknown };

export type Outgoing =
  | { type: 'hello'; session_id: string; csrf_token: string }
  | { type: 'ping' | 'pong'; frame_id: string }
  | { type: 'watch'; frame_id: string; watch_id: string; resource: Resource; views: string[] }
  | { type: 'unwatch'; frame_id: string; watch_id: string }
  | ({ type: 'command'; frame_id: string } & Omit<Command, 'receipt_action'>);

export type Incoming =
  | { type: 'ready'; connection_id: string; server_time: string }
  | { type: 'ping' | 'pong'; frame_id: string }
  | { type: 'watch_ready'; frame_id: string; watch_id: string; resource: Resource; views: string[] }
  | { type: 'unwatch_ready'; frame_id: string; watch_id: string }
  | {
      type: 'changed';
      watch_id: string;
      resource: Resource;
      views: string[];
      request_id: string | null;
    }
  | { type: 'resync_required'; watch_id: string | null; reason: string }
  | {
      type: 'receipt';
      frame_id: string;
      request_id: string;
      state: 'accepted' | 'completed';
      owner_receipt_ref: string;
      execution_ref: string | null;
      result_refs: unknown[];
    }
  | {
      type: 'error';
      frame_id: string | null;
      request_id: string | null;
      error: { code: string; message: string; issues: unknown[]; retryable: boolean };
      acceptance: 'not_accepted' | 'unknown';
    };

export function object(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === 'object' && !Array.isArray(value);
}

export function isResource(value: unknown): value is Resource {
  return object(value) && typeof value.kind === 'string' && typeof value.id === 'string';
}

function nullableId(value: unknown): value is string | null {
  return value === null || typeof value === 'string';
}

function names(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((part) => typeof part === 'string');
}

function isIncoming(value: unknown): value is Incoming {
  if (!object(value)) return false;
  switch (value.type) {
    case 'ready':
      return typeof value.connection_id === 'string' && typeof value.server_time === 'string';
    case 'ping':
    case 'pong':
      return typeof value.frame_id === 'string';
    case 'watch_ready':
      return (
        typeof value.frame_id === 'string' &&
        typeof value.watch_id === 'string' &&
        isResource(value.resource) &&
        names(value.views)
      );
    case 'unwatch_ready':
      return typeof value.frame_id === 'string' && typeof value.watch_id === 'string';
    case 'changed':
      return (
        typeof value.watch_id === 'string' &&
        isResource(value.resource) &&
        names(value.views) &&
        nullableId(value.request_id)
      );
    case 'resync_required':
      return nullableId(value.watch_id) && typeof value.reason === 'string';
    case 'receipt':
      return (
        typeof value.frame_id === 'string' &&
        typeof value.request_id === 'string' &&
        (value.state === 'accepted' || value.state === 'completed') &&
        typeof value.owner_receipt_ref === 'string' &&
        nullableId(value.execution_ref) &&
        Array.isArray(value.result_refs)
      );
    case 'error':
      return (
        nullableId(value.frame_id) &&
        nullableId(value.request_id) &&
        object(value.error) &&
        typeof value.error.code === 'string' &&
        typeof value.error.message === 'string' &&
        Array.isArray(value.error.issues) &&
        typeof value.error.retryable === 'boolean' &&
        (value.acceptance === 'not_accepted' || value.acceptance === 'unknown')
      );
    default:
      return false;
  }
}

export function readFrame(data: unknown): Incoming | undefined {
  if (typeof data !== 'string' || bytes(data) > MESSAGE_BYTES) return;
  try {
    const value: unknown = JSON.parse(data);
    return isIncoming(value) ? value : undefined;
  } catch {
    return;
  }
}

export function bytes(value: string): number {
  return new TextEncoder().encode(value).length;
}
