import { reactive, ref, watch } from 'vue';
import { emptyTextbook, mockId, recordBookChange, type MockTextbook } from './textbook';
import { prepareRealBook, realBookPages } from './material-fixture';
import { prepareIntegration, seedIntegration, type Integration } from './material-integration';
import type { ReviewState } from './review-content';
import type { MaterialFlow } from './material-flow';

export interface ImportFile { id: string; name: string; kind: string; size: number }
export interface ImportDraft {
  id: string; book: MockTextbook; files: ImportFile[]; sample: boolean;
  state: 'upload' | 'processing' | 'paused' | 'failed' | 'review';
  progress: number; failNext: boolean; error: string;
  workspace?:'semantic'|'source'|'fusion'|'application';
  integration?:Integration;
  demo?:'empty'|'partial'|'full';
  reviewExamples?:boolean; contentReview?:ReviewState;
  flow?:MaterialFlow;
}
export const storageKey = 'deermind-m1-import-v1';
export const storageError = ref('');
let saved: ImportDraft[] = [];
let readable = true;
try {
  const parsed = JSON.parse(localStorage.getItem(storageKey) || '[]');
  if (!Array.isArray(parsed) || parsed.some(d => !d.id || !d.book?.units || !Array.isArray(d.files))) throw Error();
  saved = parsed;
} catch {
  readable = false;
  storageError.value = '本地M1草稿无法读取，未覆盖原记录。请先保留浏览器数据并检查。';
}
for (const draft of saved) if (draft.state === 'processing') draft.state = 'paused';
export const imports = reactive(saved);
watch(imports, value => {
  if (!readable) return;
  try { localStorage.setItem(storageKey, JSON.stringify(value)); storageError.value = ''; }
  catch { storageError.value = '浏览器保存失败，本次修改尚未保存。请勿关闭页面。'; }
}, { deep: true });

export function newImport() {
  const draft: ImportDraft = { id: mockId('IMPORT'), book: emptyTextbook(), files: [], sample: false, state: 'upload', progress: 0, failNext: false, error: '' };
  imports.unshift(draft);
  return draft.id;
}
export function loadSample(draft: ImportDraft) {
  draft.files = realBookPages.map(page => ({ id: 'BNU-PAGE-' + page, name: '北师大六上-书页' + page + '.png', kind: '扫描图片', size: 0 }));
  draft.sample = true;
  draft.error = '';
  Object.assign(draft.book, {
    name: '北师大版数学六年级上册 · 书页走查', publisher: '北京师范大学出版社',
    edition: '用户提供的电子教材；版权页待补', grade: '六年级上册', subject: '数学',
    sourceNote: '真实书页49—50、91—93，电子页序52—53、94—96。识别结果为固定mock，不代表整册已准备。',
  });
}
export function finishRecognition(draft: ImportDraft) {
  const book = draft.book;
  if(draft.reviewExamples){book.sources=draft.files.map(({id,name,kind})=>({id,name,kind}));draft.state='review';draft.progress=100;draft.workspace='semantic';recordBookChange(book,'载入四例核对候选（mock），尚未核对');return;}
  prepareRealBook(book);
  book.sources = draft.files.map(({ id, name, kind }) => ({ id, name, kind }));
  const supplied = new Set(draft.files.map(f => f.id));
  for (const chapter of book.units.flatMap(u => u.chapters)) {
    const missing = chapter.locations.filter(l => !supplied.has(l.fileId)).map(l => l.printedPage);
    chapter.locations = chapter.locations.filter(l => supplied.has(l.fileId));
    chapter.items = (chapter.items || []).map(i => ({ ...i, blocks: i.blocks.filter(b => supplied.has('BNU-PAGE-' + b.page)) })).filter(i => i.blocks.length);
    if (missing.length && chapter.items[0]) chapter.items[0].issue = [chapter.items[0].issue, '原件缺页：本课还需要第 ' + missing.join('、') + ' 页，请补齐后核对。'].filter(Boolean).join(' ');
    chapter.content = chapter.items.map(i => i.title).join('\n');
  }
  book.units = book.units.map(u => ({ ...u, chapters: u.chapters.filter(c => c.items?.length) })).filter(u => u.chapters.length);
  const blocks = book.units.flatMap(u => u.chapters).flatMap(c => c.items || []).flatMap(i => i.blocks);
  const available = new Set(blocks.map(b => b.id));
  for (const block of blocks) if (block.references.some(id => !available.has(id))) {
    block.issue = [block.issue, '缺少关联的来源内容，请补齐原页后核对。'].filter(Boolean).join(' ');
    block.resolved = false;
  }
  recordBookChange(book, '生成整理候选（mock），等待对照原页核对');
  draft.state = 'review';
  draft.progress = 100;
  draft.integration=prepareIntegration(book);
  if(draft.demo&&draft.demo!=='empty')seedIntegration(book,draft.integration,draft.demo);
}
export function deleteImport(id: string) {
  const index = imports.findIndex(d => d.id === id);
  if (index < 0 || imports[index].integration?.applications.length || Object.keys(imports[index].flow?.links||{}).length) return;
  sessionStorage.removeItem('deermind-m1-material-selection-' + imports[index].book.id);
  imports.splice(index, 1);
}
