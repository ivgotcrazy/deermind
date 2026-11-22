/** Pending writes survive a tab reload under the same account. */

const STORAGE_KEY = 'deermind-domain-create-pending-v1';

export type CreateDraft = Readonly<{
  request_id: string;
  name: string;
}>;

export function readCreateDraft(accountId: string): CreateDraft | null {
  const raw = sessionStorage.getItem(STORAGE_KEY);
  if (!raw) return null;
  const value: unknown = JSON.parse(raw);
  if (
    value &&
    typeof value === 'object' &&
    'accountId' in value &&
    value.accountId === accountId &&
    'request_id' in value &&
    typeof value.request_id === 'string' &&
    'name' in value &&
    typeof value.name === 'string'
  ) {
    return { request_id: value.request_id, name: value.name };
  }
  clearCreateDraft();
  return null;
}

export function saveCreateDraft(accountId: string, draft: CreateDraft): void {
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify({ accountId, ...draft }));
}

export function clearCreateDraft(): void {
  try {
    sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    // A tab with storage disabled keeps its current draft in memory only.
  }
}
