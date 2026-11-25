import type { components } from '../../../../../contracts/generated/http/schema';
import { get, post, putFile } from '../../../shared/api/http';
import type { DomainSession } from '../domain/api';

type Schemas = components['schemas'];
export type MaterialDetail = Schemas['MaterialView'];
export type TextbookRow = Schemas['TextbookRow'];
export type MaterialFile = Schemas['MaterialFile'];
export type SourceView = Schemas['MaterialSourceView'];
type NewMaterial = Schemas['NewMaterial'];
type AppendMaterial = Schemas['AppendMaterial'];
type DomainRef = Schemas['RegisterMaterialFile']['domain_ref'];

export type ReceiveCommand =
  | { kind: 'domain'; scope: string; body: NewMaterial }
  | { kind: 'material_import'; scope: string; body: AppendMaterial };

export const listTextbooks = (
  session: DomainSession,
  query: { name: string; domain_id?: string; cursor?: string },
  signal: AbortSignal,
) => get('/api/m1/textbooks', { session, query, signal });

export const detail = (session: DomainSession, id: string, cursor?: string) =>
  get('/api/m1/textbooks/{textbook_id}', {
    session,
    params: { textbook_id: id },
    query: { cursor },
  });

export async function upload(
  session: DomainSession,
  file: File,
  domain: DomainRef,
  order: number,
  importId?: string,
): Promise<MaterialFile> {
  if (file.type !== 'application/pdf' && file.type !== 'image/png' && file.type !== 'image/jpeg') {
    throw new Error('请选择 PDF、PNG 或 JPEG 文件。');
  }
  const data = {
    request_id: crypto.randomUUID(),
    purpose: 'material_source',
    original_name: file.name,
    declared_media_type: file.type,
    declared_byte_size: file.size,
    domain_ref: domain,
    import_id: importId,
  } satisfies Schemas['RegisterMaterialFile'];
  const registered = await post('/api/m1/file-uploads', data, { session });
  const params = { upload_id: registered.upload_id };
  let receipt = registered.receipt;
  if (!receipt) {
    try {
      receipt = (
        await putFile('/api/m1/file-uploads/{upload_id}/content', file, { session, params })
      ).receipt;
    } catch (error) {
      const status = await get('/api/m1/file-uploads/{upload_id}', { session, params });
      if (!status.receipt) throw error;
      receipt = status.receipt;
    }
  }
  if (!receipt) throw new Error('服务器未确认原件可用。');
  return { receipt, original_name: file.name, order };
}

export function receive(session: DomainSession, command: ReceiveCommand) {
  if (command.kind === 'domain') return post('/api/m1/material-imports', command.body, { session });
  return post('/api/m1/material-imports/{import_id}/files', command.body, {
    session,
    params: { import_id: command.scope },
  });
}

export async function readReceipt(session: DomainSession, command: ReceiveCommand) {
  const result = await get('/api/m1/requests/receipt', {
    session,
    query: {
      action: 'product.receive_material',
      resource_kind: command.kind,
      resource_id: command.scope,
      request_id: command.body.request_id,
    },
  });
  return {
    state: result.receipt_state,
    result: result.result && 'textbook_id' in result.result ? result.result : null,
    error: result.error?.message,
  };
}

export async function download(session: DomainSession, source: SourceView) {
  const query = new URLSearchParams({
    view: 'source',
    storage_ref: source.receipt.storage_ref,
    owner_ref: JSON.stringify(source.source_ref),
  });
  const result = await fetch(`/api/m1/resource-files?${query}`, {
    headers: { 'X-Expected-Session': session.session_id },
    credentials: 'same-origin',
    cache: 'no-store',
  });
  if (!result.ok) throw new Error('无法读取该原件，请核对当前登录和原件状态。');
  const url = URL.createObjectURL(await result.blob());
  const link = document.createElement('a');
  link.href = url;
  link.download = source.original_name;
  link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 10_000);
}
