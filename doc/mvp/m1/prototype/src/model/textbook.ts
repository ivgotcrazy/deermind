import type { MaterialItem } from './material-content';

export interface SourceLocation {
  id: string; fileId: string; filePage: number; printedPage: string;
  label: string; text: string; image?: string;
}
export interface MaterialChapter {
  id: string; name: string; content: string; locations: SourceLocation[];
  checked: boolean; reviewNote: string; items?: MaterialItem[];
}
export interface MockTextbook {
  id: string; name: string; publisher: string; edition: string; grade: string;
  subject: string; domainId: string; sourceNote: string;
  sources: { id: string; name: string; kind: string }[];
  units: { id: string; name: string; chapters: MaterialChapter[] }[];
  revision: number; history: { at: string; change: string }[];
}
export const mockId = (prefix: string) => prefix + '-' + crypto.randomUUID().slice(0, 8).toUpperCase();
export const emptyChapter = (): MaterialChapter => ({
  id: mockId('CHAPTER'), name: '', content: '', locations: [], checked: false, reviewNote: '',
});
export const emptyTextbook = (): MockTextbook => ({
  id: mockId('BOOK'), name: '', publisher: '', edition: '', grade: '', subject: '',
  domainId: '', sourceNote: '', sources: [], units: [], revision: 1, history: [],
});
export function recordBookChange(book: MockTextbook, change: string) {
  book.revision++;
  book.history.unshift({ at: new Date().toLocaleString('sv-SE', { hour12: false }), change });
}
