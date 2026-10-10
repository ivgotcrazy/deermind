import { reactive } from 'vue';
import type { Role, SpaceId } from './data';

export type Intent =
  | 'understand'
  | 'basis'
  | 'verify'
  | 'explain'
  | 'hint'
  | 'challenge'
  | 'delete'
  | 'support'
  | 'prepare';
export interface Context {
  role: Role;
  space: SpaceId;
  page: string;
  label: string;
  question?: number;
  chapter?: string;
  source: string;
  version: number;
  kind: string;
  activity: string;
  hidden: boolean;
  material: number;
}
export interface Action {
  kind: 'verify' | 'teach' | 'delete' | 'challenge' | 'prepare';
  label: string;
  context: Context;
  status: 'pending' | 'done' | 'cancelled';
  help?: 'hint' | 'explain';
}
export interface Exchange {
  id: number;
  request: string;
  response: string;
  context: Context;
  action?: Action;
}
export const conversation = reactive({
  open: false,
  composerRequest: 0,
  focus: null as null | { role: Role; space: SpaceId; question?: number; chapter?: string },
  requested: null as null | { intent: Intent; id: number },
  sessions: {} as Record<string, { draft: string; entries: Exchange[] }>,
});
let sequence = 0;
export const nextId = () => ++sequence;
export function session(role: Role, space: SpaceId) {
  return (conversation.sessions[`${role}:${space}`] ??= { draft: '', entries: [] });
}
export function openConversation(role: Role, space: SpaceId, question?: number, intent?: Intent) {
  conversation.focus = question === undefined ? null : { role, space, question };
  conversation.composerRequest = nextId();
  if (intent) conversation.requested = { intent, id: nextId() };
}
export function clearConversation(role: Role, space: SpaceId) {
  delete conversation.sessions[`${role}:${space}`];
}
export function openChapterConversation(
  role: Role,
  space: SpaceId,
  chapter: string,
  intent?: Intent,
) {
  conversation.focus = { role, space, chapter };
  conversation.composerRequest = nextId();
  if (intent) conversation.requested = { intent, id: nextId() };
}
