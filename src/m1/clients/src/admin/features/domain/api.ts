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
  if (object.object_ref.kind !== 'domain') throw new Error('收到无效领域详情。');
  return object as components['schemas']['DomainView'];
}

function definitionText(text?: string): components['schemas']['RichContent-Input'] | null {
  if (!text) return null;
  return {
    role: 'definition',
    schema_version: '1',
    data_tables: [],
    source_refs: [],
    blocks: text
      .split('\n')
      .filter((line) => line.trim())
      .map((line, i) => ({
        block_id: `p-${i + 1}`,
        type: 'paragraph',
        payload: { spans: [{ type: 'text', text: line }] },
        provenance: { transformation: 'generated', source_refs: [], note: '' },
      })),
  };
}

export function createDomain(draft: CreateDraft, session: Session, signal: AbortSignal) {
  return post(
    '/api/m1/domain-definitions',
    {
      request_id: draft.request_id,
      object_kind: 'domain',
      action: 'create',
      definition: {
        name: draft.name,
        coverage: definitionText(draft.coverage),
        description: definitionText(draft.description),
      },
      change_note: '新建领域',
    },
    { session, signal },
  );
}

export async function readCreateReceipt(draft: CreateDraft, session: Session, signal: AbortSignal) {
  const receipt = await readDefinitionReceipt(draft.request_id, session, signal);
  const result = receipt.result;
  if (receipt.receipt_state === 'completed') {
    if (!result || !('content_ref' in result) || result.object_ref.kind !== 'domain')
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

export function listMembers(
  domainId: string,
  kind: MemberKind,
  session: Session,
  signal: AbortSignal,
  name: string,
  cursor?: string,
  limit?: number,
) {
  return get('/api/m1/domains/{domain_id}/objects', {
    params: { domain_id: domainId },
    query: { kinds: [kind], name, cursor, limit },
    session,
    signal,
  });
}

export async function readMember(
  domainId: string,
  objectId: string,
  kind: MemberKind,
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
  if (object.object_ref.kind !== kind) throw new Error('收到无效领域对象详情。');
  return object as MemberView;
}

export function saveMember(body: MemberRequest, session: Session, signal: AbortSignal) {
  return post('/api/m1/domain-definitions', body, { session, signal });
}

export function readDependencies(
  domainId: string,
  task: TaskRef,
  session: Session,
  signal: AbortSignal,
  solutionId: string,
) {
  return get('/api/m1/domains/{domain_id}/dependencies', {
    params: { domain_id: domainId },
    query: {
      task_id: task.object_id,
      version: task.version,
      solution_ids: solutionId ? [solutionId] : undefined,
    },
    session,
    signal,
  });
}

export function saveKCPath(
  domainId: string,
  body: ConfirmKCPathRequest,
  session: Session,
  signal: AbortSignal,
) {
  return post('/api/m1/domains/{domain_id}/kc-test-paths', body, {
    params: { domain_id: domainId },
    session,
    signal,
  });
}

export function readKCPathReceipt(
  domainId: string,
  requestId: string,
  session: Session,
  signal: AbortSignal,
) {
  return get('/api/m1/requests/receipt', {
    query: {
      action: 'domain.confirm_kc_path',
      resource_kind: 'domain',
      resource_id: domainId,
      request_id: requestId,
    },
    session,
    signal,
  });
}

export type MemberRequest =
  | components['schemas']['CreateKnowledgeRequest']
  | components['schemas']['UpdateKnowledgeRequest']
  | components['schemas']['DeleteKnowledgeRequest']
  | components['schemas']['CreateTaskRequest']
  | components['schemas']['UpdateTaskRequest']
  | components['schemas']['DeleteTaskRequest']
  | components['schemas']['CreateSolutionRequest']
  | components['schemas']['UpdateSolutionRequest']
  | components['schemas']['DeleteSolutionRequest'];
export type MemberRef = components['schemas']['MemberRef'];
export type MemberKind = MemberRef['kind'];
export type MemberRow = components['schemas']['MemberRow'];
export type MemberView =
  | components['schemas']['KnowledgeView']
  | components['schemas']['TaskView']
  | components['schemas']['SolutionView'];
export type TaskRef = components['schemas']['TaskRef'];
export type SolutionRef = components['schemas']['SolutionRef'];
export type KnowledgeRef = components['schemas']['KnowledgeRef'];
export type Prerequisite = components['schemas']['Prerequisite'];
export type TaskDependencies = components['schemas']['TaskDependencies'];
export type ConfirmKCPathRequest = components['schemas']['ConfirmKCPathRequest'];
export type KnowledgeUse = components['schemas']['KnowledgeUse'];
export type DomainView = Awaited<ReturnType<typeof readDomain>>;
export type DomainRow = Awaited<ReturnType<typeof listDomains>>['items'][number];
export type DomainSession = Parameters<typeof listDomains>[0];
