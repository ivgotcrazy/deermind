import { reactive, watch } from 'vue';
import { questions, fixturePlan, type SpaceId } from './data';
import { conversation } from './conversation';
import { resetLessons } from './lessons';

const KEY = 'deermind-mvp-ux-v1';
export type Scenario = 'normal' | 'partial' | 'offline' | 'failure';
export interface SpaceState {
  materialRevision: number;
  activityRevision: number;
  imported: boolean;
  kind: 'exam' | 'single';
  hidden: boolean;
  processing: boolean;
  failure: boolean;
  unclear: boolean;
  corrected: boolean;
  sourceName: string;
  selectedQuestion: number;
  helps: string[];
  draft: string;
  strokes: string[];
  practice: Record<string, { draft: string; strokes: string[] }>;
  proposal: string;
  delivery: 'none' | 'received' | 'checked' | 'approved' | 'active' | 'rejected';
  issue: 'none' | 'open' | 'reviewing' | 'fixed';
  notice: boolean;
  chats: { question: string; answer: string }[];
  test: {
    stage: 'plan' | 'running' | 'result';
    index: number;
    count: number;
    questionIndexes: number[];
    answers: string[];
    draft: string;
    reason: string;
    chapters: string[];
  };
  book: 'draft' | 'review' | 'open';
  model: 'current' | 'candidate' | 'validated' | 'approved' | 'active' | 'conflict';
  modelVersion: number;
}
function newSpace(): SpaceState {
  return {
    materialRevision: 0,
    activityRevision: 0,
    imported: true,
    kind: 'exam',
    hidden: false,
    processing: false,
    failure: false,
    unclear: false,
    corrected: false,
    practice: {},
    proposal: '',
    delivery: 'none',
    sourceName: '单元练习 · 示例试卷',
    selectedQuestion: 2,
    helps: [],
    draft: '',
    strokes: [],
    issue: 'none',
    notice: false,
    chats: [],
    test: {
      stage: 'plan',
      index: 0,
      count: 3,
      questionIndexes: [0, 1, 2],
      answers: [],
      draft: '',
      reason: '',
      chapters: [],
    },
    book: 'open',
    model: 'current',
    modelVersion: 1,
  };
}
function initial() {
  return {
    space: 'school' as SpaceId,
    scenario: 'normal' as Scenario,
    familyConsent: true,
    childConsent: true,
    linked: true,
    autoMinutes: 12,
    extraMinutes: 0,
    timeUnknown: false,
    config: 'saved',
    audit: [] as string[],
    spaces: {
      school: newSpace(),
      extension: { ...newSpace(), imported: false, book: 'draft' as const },
    },
  };
}
function read() {
  try {
    const raw = localStorage.getItem(KEY);
    if (raw) {
      const value = JSON.parse(raw);
      if (value.version === 2 && value.data?.spaces?.school && value.data?.spaces?.extension) {
        const data = value.data as ReturnType<typeof initial>;
        for (const item of Object.values(data.spaces)) {
          item.materialRevision ??= 0;
          item.activityRevision ??= 0;
          if (item.processing) {
            item.processing = false;
            item.failure = true;
          }
        }
        return data;
      }
    }
  } catch {
    /* An unavailable local store leaves the demo usable in memory. */
  }
  return initial();
}
export const state = reactive(read());
export const ui = reactive({ toast: '', reviewOpen: false, storageWarning: false });
watch(
  state,
  () => {
    try {
      localStorage.setItem(KEY, JSON.stringify({ version: 2, data: state }));
    } catch {
      ui.storageWarning = true;
    }
  },
  { deep: true },
);
let toastTimer: ReturnType<typeof setTimeout>;
export function notify(message: string) {
  ui.toast = message;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    ui.toast = '';
  }, 4200);
}
export function audit(message: string) {
  state.audit.unshift(`${new Date().toLocaleTimeString('zh-CN', { hour12: false })} · ${message}`);
}
export function current() {
  return state.spaces[state.space];
}
export function allowed() {
  return state.familyConsent && state.childConsent;
}
let generation = 0;
export function reset(onboarding = false) {
  generation++;
  resetLessons();
  conversation.open = false;
  conversation.focus = null;
  conversation.requested = null;
  conversation.sessions = {};
  Object.assign(state, initial());
  if (onboarding) {
    state.familyConsent = false;
    state.childConsent = false;
    state.spaces.school.imported = false;
  }
  notify(onboarding ? '已切换到首次使用场景' : '演示数据已重置');
}
export async function importExam(name = '单元练习 · 示例试卷', kind: 'exam' | 'single' = 'exam') {
  if (!allowed()) {
    notify('请先完成家长确认和孩子的首次参与确认');
    return false;
  }
  const space = state.space;
  const item = state.spaces[space];
  const token = generation;
  if (item.processing) return true;
  if (state.scenario === 'offline') {
    item.draft = name;
    notify('尚未发送，材料名称已保留。联网后可继续原提交。');
    return false;
  }
  item.processing = true;
  item.materialRevision++;
  item.imported = true;
  item.kind = kind;
  item.hidden = false;
  item.failure = false;
  item.sourceName = name;
  item.corrected = false;
  item.selectedQuestion = 2;
  item.helps = [];
  item.draft = '';
  item.strokes = [];
  item.practice = {};
  item.unclear = state.scenario === 'partial' && kind === 'exam';
  item.issue = 'none';
  item.notice = false;
  audit(`${space}：接收示例试卷，开始模拟处理`);
  await new Promise((resolve) => setTimeout(resolve, 850));
  if (token !== generation) return false;
  item.processing = false;
  item.failure = state.scenario === 'failure';
  audit(`${space}：${item.failure ? '处理失败，保留原任务' : '示例分析完成，确认错题自动归集'}`);
  return true;
}
export function showHelp(kind: 'hint' | 'explain', standalone = false) {
  const item = current();
  if (!allowed() || (!standalone && item.hidden)) {
    notify('当前无法打开这份学习材料');
    return false;
  }
  if (state.scenario === 'offline') {
    notify('连接已断开，未展示新的帮助。恢复连接后可重试。');
    return false;
  }
  const key = `${questions[state.space][item.selectedQuestion]!.id}:${kind}`;
  if (!item.helps.includes(key)) item.helps.push(key);
  audit(`${state.space}：实际呈现示例${kind === 'hint' ? '提示' : '讲解'}；不生成掌握结论`);
  return true;
}
export async function retryExam() {
  const item = current();
  const token = generation;
  if (!item.failure || item.processing) return;
  if (state.scenario === 'offline') {
    notify('连接尚未恢复，原任务和输入继续保留。');
    return;
  }
  item.processing = true;
  await new Promise((resolve) => setTimeout(resolve, 850));
  if (token !== generation) return;
  item.processing = false;
  item.failure = state.scenario === 'failure';
  audit(`${state.space}：重试原任务，保留原对象、资料类型及删除状态`);
}
export function deleteExam() {
  const item = current();
  item.hidden = true;
  audit(
    `${state.space}：学生端删除${item.kind === 'exam' ? '整卷及关联错题' : '独立题'}，原作答同步隐藏`,
  );
  notify('资料已从你的界面移除，不能恢复。');
}
export function reportIssue() {
  const item = current();
  if (state.space !== 'school' || item.kind !== 'exam') {
    notify('本轮纠错走查使用校内示例试卷第 2 题，请切换对应场景。');
    return;
  }
  if (item.issue === 'none') {
    item.issue = 'open';
    audit(`${state.space}：提交识别复核事项，尚未确认错误`);
  }
  notify('已提交复核，可继续其他学习。');
}
export function correctIssue() {
  const item = current();
  item.issue = 'fixed';
  item.corrected = true;
  item.unclear = false;
  item.notice = true;
  audit(`${state.space}：依据示例原件更正第 2 题识别；保留原记录，通知受影响用户`);
  notify('识别已更正，相关结果已更新；已删资料仍保持隐藏。');
}
export function questionStatus(index: number) {
  const item = current();
  if (index === 1 && item.unclear) return 'unclear';
  if (index === 1 && item.corrected) return 'correct';
  return questions[state.space][index]!.status;
}
export function startTest(chapters: string[]) {
  if (!allowed()) {
    notify('请先完成首次使用确认');
    return false;
  }
  if (!chapters.length) {
    notify('请从教材中选择检测范围');
    return false;
  }
  if (current().book !== 'open') {
    notify('当前示例章节尚未开放，请先在管理端完成核对。');
    return false;
  }
  if (state.scenario === 'offline') {
    notify('题单尚未确认，联网后继续');
    return false;
  }
  const item = current();
  const questionIndexes = fixturePlan(state.space, chapters);
  if (!questionIndexes.length) return false;
  item.activityRevision++;
  item.test = {
    stage: 'running',
    index: 0,
    count: questionIndexes.length,
    questionIndexes,
    answers: [],
    draft: '',
    reason: '',
    chapters,
  };
  return true;
}
export function submitTest() {
  const test = current().test;
  if (test.stage !== 'running' || !test.draft.trim()) {
    notify('请先写下作答，或选择结束本次检测');
    return;
  }
  if (state.scenario === 'offline') {
    notify('尚未收到提交，当前输入已保留。');
    return;
  }
  test.answers.push(test.draft);
  test.draft = '';
  test.index++;
  if (test.index >= test.count) {
    test.stage = 'result';
    test.reason = '已完成题单';
  } else notify('已收到作答，检测结束后统一反馈。');
}
export function endTest(reason: string) {
  const test = current().test;
  test.stage = 'result';
  test.reason = reason;
  audit(`${state.space}：${reason}，未做题保留为未检测`);
}
