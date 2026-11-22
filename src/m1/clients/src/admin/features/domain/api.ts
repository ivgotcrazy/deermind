/** Domain maintenance writes use the synchronous API and the common receipt reader. */

import { get, post } from '../../../shared/api/http';
import type { CreateDraft } from './draft';

type Session = Readonly<{
  session_id: string;
  csrf_token: string;
  account: { account_id: string };
}>;

export function listDomains(session: Session, signal: AbortSignal) {
  return get('/api/m1/domains', { session, signal });
}

export function readDomain(domainId: string, session: Session, signal: AbortSignal) {
  return get('/api/m1/domains/{domain_id}/objects/{object_id}', {
    params: { domain_id: domainId, object_id: domainId },
    session,
    signal,
  });
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
  const receipt = await get('/api/m1/requests/receipt', {
    session,
    signal,
    query: {
      action: 'domain.save_definition',
      resource_kind: 'account',
      resource_id: session.account.account_id,
      request_id: draft.request_id,
    },
  });
  const result = receipt.result;
  if (receipt.receipt_state === 'completed') {
    if (!result || !('object_ref' in result)) throw new Error('收据缺少新增领域的引用。');
    return { state: 'completed', domainId: result.object_ref.object_id } as const;
  }
  return { state: receipt.receipt_state, message: receipt.error?.message } as const;
}

export type DomainRow = Awaited<ReturnType<typeof listDomains>>['items'][number];
export type DomainView = Awaited<ReturnType<typeof readDomain>>['object'];
export type DomainSession = Parameters<typeof listDomains>[0];
