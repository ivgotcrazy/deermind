import { get, postAccepted } from '../../../shared/api/http';
import type { BookSession, BookTypes } from '../../../shared/book/editions';

export async function generateBookDraft(
  options: { session: BookSession; signal: AbortSignal },
  importId: string,
  job: BookTypes['EditionJob'],
  message: string,
) {
  const request = crypto.randomUUID();
  const work = await postAccepted(
    '/api/m1/material-imports/{import_id}/messages',
    { request_id: request, message, edition_job: job },
    { ...options, params: { import_id: importId } },
  );
  for (;;) {
    options.signal.throwIfAborted();
    const result = await get('/api/m1/requests/receipt', {
      ...options,
      query: {
        request_id: request,
        action: 'product.converse_material_assistant',
        resource_kind: 'material_import',
        resource_id: importId,
      },
    });
    if (
      result.business_state === 'failed' ||
      result.receipt_state === 'rejected' ||
      result.business_state === 'needs_input'
    )
      throw Error(result.error?.message ?? '生成未完成，请核对原件或任务后重试。');
    if (result.receipt_state === 'completed') return work.request_ref;
    await new Promise((resolve) => setTimeout(resolve, 2000));
  }
}
