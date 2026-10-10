import { reactive, watch } from 'vue';
import type { SpaceId } from './data';

export interface LessonStep {
  title: string;
  text: string;
  formula: string;
  takeaway: string;
  question: string;
  answer: string;
  illustration?: boolean;
}
export interface Lesson {
  id: string;
  chapter: string;
  purpose: string;
  steps: LessonStep[];
}
export const lessons: Lesson[] = [
  {
    id: 'fractions', chapter: '分数除法', purpose: '先理解除法在问什么，再看看为什么可以乘倒数。',
    steps: [
      { title: '分数除法，在问什么？', text: '3/4 除以 1/2，可以理解为：3/4 里面有几个 1/2？先把同样大小的一整个都分成四份，再比较。', formula: '3/4 ÷ 1/2 = 3/4 ÷ 2/4', illustration: true,
        takeaway: '要比较的是：3 个四分之一，是 2 个四分之一的多少倍。', question: '为什么要把它们都分成四份？', answer: '这样每一小份一样大，都是整个的 1/4。3/4 有 3 小份，1/2 有 2 小份，就能直接比较 3 与 2。这里没有改变原来的大小，只是换了一种表示。' },
      { title: '为什么商是一个半？', text: '3 个四分之一里，先拿出 2 个四分之一，正好是一份 1/2。还剩下 1 个四分之一，是这一份 1/2 的一半。', formula: '3 ÷ 2 = 1.5 = 3/2',
        takeaway: '3/4 中有一个半的 1/2。商告诉我们有多少个这样的“一份”。', question: '为什么剩下的不是再加 1/4？', answer: '剩下的量确实是 1/4，但我们在数“几个 1/2”。这 1/4 相当于半个 1/2，所以在“个数”上加的是 1/2，结果是一个半。' },
      { title: '乘倒数，怎样得到同一个结果？', text: '把两个数量同时放大 2 倍，它们的倍数关系不变。1/2 变成 1，3/4 变成 3/2。现在的问题是：3/2 里面有几个 1？', formula: '(3/4 × 2) ÷ (1/2 × 2) = 3/2 ÷ 1',
        takeaway: '对非零除数，乘它的倒数会把除数变成 1；被除数同时乘同一个数，商保持不变。', question: '为什么同时乘一个数，商不变？', answer: '这里同时放大的，是要分的总量和每份的大小。两者都放大 2 倍，需要的份数不会改变。比如 6 里面有 3 个 2，12 里面也有 3 个 4。' },
    ],
  },
  {
    id: 'percent', chapter: '百分数的应用', purpose: '找到被看作 100% 的整体，分清已知部分和整体。',
    steps: [
      { title: '先找到完整的一份', text: '一件上衣打八折，意思是现价占原价的 80%。在这句话里，被看作 100% 的整体是原价。', formula: '现价 = 原价 × 80%',
        takeaway: '同一个数是部分还是整体，要看题目在比较哪两个量。', question: '为什么原价才是 100%？', answer: '“八折”描述的是现在的价格相对于原来的价格。比较的基准是原价，所以把原价看作完整的 100%。' },
      { title: '已知 80%，怎样找到整体？', text: '如果打折后是 160 元，160 元对应原价的 80%。先算出 1% 对应多少钱，再求 100%。', formula: '160 ÷ 80 × 100 = 200（元）',
        takeaway: '也可以列成 160 ÷ 80% = 200。这里是在用已知部分求整体。', question: '为什么不能直接用 160 乘 80%？', answer: '160 已经是打折后的部分。再乘 80% 会求出“现价的 80%”，而问题要的是原价。已知原价求现价，才用原价乘 80%。' },
      { title: '把结果放回原题检查', text: '用求出的原价重新打八折。如果得到题目给出的现价，数量关系就对应上了。', formula: '200 × 80% = 160（元）',
        takeaway: '先认清整体，再确定乘还是除；最后把结果代回去检查。', question: '换成别的折扣也能这样想吗？', answer: '可以。先把折扣写成现价占原价的比例，再判断题目给了部分还是整体。例如七五折对应 75%，已知现价求原价时，用现价除以 75%。' },
    ],
  },
];
export interface LessonExchange { step: number; question: string; answer: string; fixture: boolean }
export interface LessonProgress {
  index: number;
  revealed: number;
  ended: boolean;
  drafts: Record<string, string>;
  exchanges: LessonExchange[];
  updated: number;
}
const KEY = 'deermind-lesson-ux-v1';
type Records = Record<SpaceId, Record<string, LessonProgress>>;
const empty = (): Records => ({ school: {}, extension: {} });
function read(): Records {
  try {
    const value = JSON.parse(localStorage.getItem(KEY) || 'null');
    if (!value?.school || !value?.extension) return empty();
    for (const byId of Object.values(value) as Record<string, LessonProgress>[]) {
      for (const [id, p] of Object.entries(byId)) {
        const count = lessons.find((l) => l.id === id)?.steps.length || 0;
        const oldDraft = (p as LessonProgress & { draft?: string }).draft;
        p.drafts ??= typeof oldDraft === 'string' ? { [p.index]: oldDraft } : {};
        if (!Number.isInteger(p.index) || !Number.isInteger(p.revealed) || p.index < 0 || p.index > p.revealed || p.revealed >= count || typeof p.ended !== 'boolean' || !Array.isArray(p.exchanges) || !p.drafts || Object.values(p.drafts).some((v) => typeof v !== 'string')) return empty();
      }
    }
    return value;
  } catch { return empty(); }
}
export const lessonState = reactive({ records: read(), storageWarning: false });
watch(() => lessonState.records, (records) => {
  try { localStorage.setItem(KEY, JSON.stringify(records)); }
  catch { lessonState.storageWarning = true; }
}, { deep: true, flush: 'sync' });
export function lessonProgress(space: SpaceId, id: string) {
  if (!lessonState.records[space][id]) lessonState.records[space][id] = { index: 0, revealed: 0, ended: false, drafts: {}, exchanges: [], updated: Date.now() };
  return lessonState.records[space][id]!;
}
export function resetLessons() { lessonState.records = empty(); }
