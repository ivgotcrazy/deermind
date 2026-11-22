/** Domain maintenance writes use the synchronous API and the common receipt reader. */

import { get, post } from '../../../shared/api/http';
import type { components } from '../../../../../contracts/generated/http/schema';
import type { CreateDraft } from './draft';

type Session = Readonly<{
  session_id: string;
  csrf_token: string;
  account: { account_id: string };
}>;

export function listDomains(session: Session, signal: AbortSignal) {
  return get('/api/m1/domains', { session, signal });
}

export async function readDomain(domainId: string, session: Session, signal: AbortSignal) {
  const { object } = await get('/api/m1/domains/{domain_id}/objects/{object_id}', {
    params: { domain_id: domainId, object_id: domainId },
    session,
    signal,
  });
  if ('definition' in object.content) throw new Error('收到无效领域详情。');
  return object as components['schemas']['DomainView'];
}

export function createDomain(draft: CreateDraft, session: Session, signal: AbortSignal) {
  return post(
    '/api/m1/domain-definitions',
    {
      request_id: draft.request_id,
      object_kind: 'domain',
      action: 'create',
      definition: { name: draft.name, coverage: null, description: null },
      change_note: '新建领域',
    },
    { session, signal },
  );
}

export async function readCreateReceipt(draft: CreateDraft, session: Session, signal: AbortSignal) {
  const receipt = await readDefinitionReceipt(draft.request_id, session, signal);
  const result = receipt.result;
  if (receipt.receipt_state === 'completed') {
    if (!result || !('object_ref' in result) || result.object_ref.kind !== 'domain')
      throw new Error('收据缺少新增领域的引用。');
    return { state: 'completed', domainId: result.object_ref.object_id } as const;
  }
  return { state: receipt.receipt_state, message: receipt.error?.message } as const;
}

export function readDefinitionReceipt(requestId: string, session: Session, signal: AbortSignal) {
  return get('/api/m1/requests/receipt', {
    session,
    signal,
    query: {
      action: 'domain.save_definition',
      resource_kind: 'account',
      resource_id: session.account.account_id,
      request_id: requestId,
    },
  });
}

export function listKnowledge(
  domainId: string,
  session: Session,
  signal: AbortSignal,
  name: string,
  cursor?: string,
) {
  return get('/api/m1/domains/{domain_id}/objects', {
    params: { domain_id: domainId },
    query: { name, cursor },
    session,
    signal,
  });
}

export async function readKnowledge(
  domainId: string,
  objectId: string,
  session: Session,
  signal: AbortSignal,
  version?: number,
) {
  const { object } = await get('/api/m1/domains/{domain_id}/objects/{object_id}', {
    params: { domain_id: domainId, object_id: objectId },
    query: { version },
    session,
    signal,
  });
  if (!('definition' in object.content)) throw new Error('收到无效知识成分详情。');
  return object as components['schemas']['KnowledgeView'];
}

export function saveKnowledge(body: KnowledgeRequest, session: Session, signal: AbortSignal) {
  return post('/api/m1/domain-definitions', body, { session, signal });
}

export type KnowledgeRequest =
  | components['schemas']['CreateKnowledgeRequest']
  | components['schemas']['UpdateKnowledgeRequest']
  | components['schemas']['DeleteKnowledgeRequest'];
export type KnowledgeRef = components['schemas']['KnowledgeRef'];
export type KnowledgeContent = components['schemas']['KnowledgeComponent-Input'];
export type KnowledgeRow = components['schemas']['KnowledgeRow'];
export type KnowledgeView = Awaited<ReturnType<typeof readKnowledge>>;
export type DomainView = Awaited<ReturnType<typeof readDomain>>;
export type DomainRow = Awaited<ReturnType<typeof listDomains>>['items'][number];
export type DomainSession = Parameters<typeof listDomains>[0];
