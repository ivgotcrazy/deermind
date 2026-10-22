import { reactive, watch } from 'vue';
import { state, orderedSessions } from '../../structure/state';
import { statusCatalog } from '../../structure/statusCatalog';

export type PageId = 'home' | 'status' | 'textbook' | 'errorbook';
export const navigation: { id: PageId; label: string; icon: string }[] = [
  { id: 'home', label: '首页', icon: '🏠' }, { id: 'status', label: '学习情况', icon: '📊' },
  { id: 'textbook', label: '教材', icon: '📖' }, { id: 'errorbook', label: '错题本', icon: '📝' },
];
export const canonicalPage = (page: string): PageId =>
  ({ materials: 'textbook', chapter: 'textbook', records: 'errorbook', record: 'errorbook' }[page] as PageId)
  || (navigation.some(n => n.id === page) ? page as PageId : 'home');
export const sessionsForSpace = (space: string) => orderedSessions(state.sessions.filter(s => s.learner === 'S0001' && s.space === space));
export const catalogForSpace = (space: string) => space === 'school' ? statusCatalog(state.home.catalogScale) : [];
export const inputScope = (space: string) => `integrated:student:S0001:${space}`;
export function readView<T extends object>(key: string, defaults: T): T {
  try { return { ...defaults, ...JSON.parse(state.drafts[`v2:${key}`] || '{}') }; } catch { return { ...defaults }; }
}
export function useView<T extends object>(key: string, defaults: T) {
  const value = reactive(readView(key, defaults));
  watch(value, () => { state.drafts[`v2:${key}`] = JSON.stringify(value); }, { deep: true });
  return value;
}
export function rememberContext(id: string, page: PageId) { state.drafts[`v2:context:${id}`] = JSON.stringify({ page }); }
export function contextPage(id: string): PageId { return canonicalPage(readView(`context:${id}`, { page: 'home' }).page); }
export function viewContext(page: PageId) {
  // Navigation context only. Sample assessments and teaching history never enter the model.
  return { page, label: navigation.find(n => n.id === page)!.label };
}
