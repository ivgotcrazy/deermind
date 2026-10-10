<script setup lang="ts">
import { computed, nextTick, onUnmounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { spaces, questions, navs, fixturePlan, type Role } from '../data';
import {
  state,
  current,
  allowed,
  notify,
  showHelp,
  startTest,
  endTest,
  deleteExam,
  reportIssue,
  audit,
} from '../store';
import { learnerViews } from '../learnerView';
import { chapterViews, chapterExplanation } from '../chapterView';
import {
  conversation,
  session,
  nextId,
  type Context,
  type Intent,
  type Exchange,
  type Action,
} from '../conversation';
import Icon from './Icon.vue';
import IntentReply from './IntentReply.vue';
const route = useRoute();
const router = useRouter();
const role = computed(() => (route.path.split('/')[1] || 'student') as Role);
const page = computed(() => String(route.params.page || 'home'));
const item = computed(current);
const readable = computed(
  () => role.value === 'admin' || (allowed() && (role.value !== 'parent' || state.linked)),
);
const chat = computed(() => session(role.value, state.space));
const visibleEntries = computed(() =>
  chat.value.entries.filter(
    (entry) =>
      !(
        role.value === 'student' &&
        item.value.hidden &&
        !entry.context.hidden &&
        entry.context.material === item.value.materialRevision &&
        entry.action?.kind !== 'delete'
      ),
  ),
);
const scroller = ref<HTMLElement>();
const composer = ref<HTMLTextAreaElement>();
const dock = ref<HTMLElement>();
const examplesOpen = ref(false);
const activeId = ref<number | null>(null);
const receipt = ref('');
const activeEntry = computed(() =>
  visibleEntries.value.find((entry) => entry.id === activeId.value),
);
const dockObserver = new ResizeObserver(([entry]) => {
  document.documentElement.style.setProperty(
    '--intent-dock-height',
    `${entry!.target.getBoundingClientRect().height}px`,
  );
});
watch(
  dock,
  (element) => {
    dockObserver.disconnect();
    document.documentElement.style.setProperty('--intent-dock-height', '0px');
    if (element) dockObserver.observe(element);
  },
  { flush: 'post' },
);
onUnmounted(() => {
  dockObserver.disconnect();
  document.documentElement.style.removeProperty('--intent-dock-height');
});
watch(chat, () => {
  activeId.value = null;
  receipt.value = '';
  examplesOpen.value = false;
});
watch(
  () => conversation.composerRequest,
  async () => {
    await nextTick();
    composer.value?.focus({ preventScroll: true });
  },
);
const context = computed<Context>(() => {
  const focus = conversation.focus;
  const focused =
    focus?.role === role.value && focus.space === state.space ? focus.question : undefined;
  const chapter =
    focus?.role === role.value && focus.space === state.space ? focus.chapter : undefined;
  const index =
    focused ??
    (role.value === 'student' && page.value === 'question'
      ? item.value.selectedQuestion
      : role.value === 'student' && page.value === 'test' && item.value.test.stage === 'running'
        ? item.value.test.questionIndexes[item.value.test.index]
        : undefined);
  const label =
    chapter ??
    (index !== undefined
      ? learnerViews()[index]!.title
      : navs[role.value].find((n) => n.key === page.value)?.label ||
        (
          { exam: '试卷回顾', test: '当前检测', results: '检测结果', upload: '上传资料' } as Record<
            string,
            string
          >
        )[page.value] ||
        '当前页面');
  return {
    role: role.value,
    space: state.space,
    page: page.value,
    label,
    question: index,
    chapter,
    source: `${item.value.materialRevision}:${item.value.sourceName}:${item.value.hidden}`,
    version: item.value.modelVersion,
    kind: item.value.kind,
    activity: `${item.value.activityRevision}:${item.value.test.stage}:${item.value.test.index}`,
    hidden: item.value.hidden,
    material: item.value.materialRevision,
  };
});
const contextKey = (c: Context) =>
  JSON.stringify([c.role, c.space, c.question, c.chapter, c.source, c.version, c.kind, c.activity]);
const choices = computed<{ id: Intent; label: string }[]>(() => {
  if (role.value === 'admin')
    return [
      { id: 'understand', label: '这个页面可以帮我做什么？' },
      { id: 'prepare', label: '整理本章的模型维护候选' },
    ];
  if (role.value === 'parent')
    return [
      { id: 'basis', label: '为什么这样判断？' },
      { id: 'support', label: '我可以怎样支持她？' },
    ];
  if (page.value === 'question' || (page.value === 'test' && item.value.test.stage === 'running'))
    return [
      { id: 'explain', label: '讲讲当前这道题' },
      { id: 'hint', label: '只给我一点提示' },
      { id: 'basis', label: '这次表现说明了什么？' },
      { id: 'challenge', label: '我觉得这里识别错了' },
    ];
  return [
    { id: 'understand', label: '我现在学得怎样？' },
    { id: 'basis', label: '为什么这样判断？' },
    { id: 'verify', label: '我想验证一下理解' },
    ...(item.value.imported && !item.value.hidden
      ? [{ id: 'delete' as Intent, label: '删除当前这份资料' }]
      : []),
  ];
});
const labels: Record<Intent, string> = {
  understand: '我现在学得怎样？',
  basis: '为什么这样判断？',
  verify: '我想验证一下理解',
  explain: '讲讲当前这道题',
  hint: '只给我一点提示',
  challenge: '我觉得这里识别错了',
  delete: '删除当前这份资料',
  support: '我可以怎样支持她？',
  prepare: '整理本章的模型维护候选',
};
watch(
  () => [role.value, state.space, route.path],
  () => {
    conversation.focus = null;
  },
);
watch(
  () => readable.value,
  (value) => {
    if (!value) conversation.open = false;
  },
);
watch(
  () => conversation.requested?.id,
  () => {
    const request = conversation.requested;
    if (request) {
      conversation.requested = null;
      run(request.intent);
    }
  },
);
watch(
  () => [chat.value.entries.length, conversation.open],
  async () => {
    await nextTick();
    scroller.value?.scrollTo({ top: scroller.value.scrollHeight, behavior: 'smooth' });
  },
);
function add(request: string, response: string, action?: Action) {
  const id = nextId();
  chat.value.entries.push({
    id,
    request,
    response,
    context: { ...context.value },
    action,
  });
  activeId.value = id;
  receipt.value = '';
  if (role.value === 'parent') item.value.chats.push({ question: request, answer: response });
}
function action(kind: Action['kind'], label: string): Action {
  return { kind, label, context: { ...context.value }, status: 'pending' };
}
function run(intent: Intent) {
  examplesOpen.value = false;
  if (!readable.value) return;
  if (state.scenario === 'offline') {
    notify('连接未恢复，尚未展示新的回复或执行操作。输入继续保留。');
    return;
  }
  const c = context.value;
  const view = c.question === undefined ? undefined : learnerViews()[c.question];
  const chapter = chapterViews().find((v) => v.name === c.chapter);
  if (
    role.value === 'student' &&
    item.value.test.stage === 'running' &&
    (intent === 'understand' || intent === 'basis')
  ) {
    add(
      labels[intent],
      '当前仍在独立检测中，先不展开可能影响作答的判断或相关反馈。结束后可以继续了解依据；如果现在需要提示或讲解，可以明确提出并结束本次检测。',
    );
    return;
  }
  if (intent === 'understand' || intent === 'basis') {
    const answer =
      role.value === 'admin'
        ? `当前在“${c.label}”。可以围绕本章准备维护候选；检查、批准与正式启用仍分别完成。`
        : chapter
          ? chapterExplanation(chapter)
          : view
            ? `${view.assessment}\n\n依据：${view.basis}\n条件：${view.conditions}\n还缺什么：${view.missing}\n变化：${view.change}`
            : `${spaces[state.space].name}的当前概况：\n${chapterViews()
                .map((v) => `${v.name}：${v.summary}`)
                .join(
                  '\n',
                )}\n\n这些是当次表现与认识边界，不是整章掌握结论。可以点一项判断，继续讨论它的依据。`;
    add(role.value === 'admin' ? '这个页面可以帮我做什么？' : labels[intent], answer);
    return;
  }
  if (intent === 'support') {
    add(
      labels[intent],
      '可以先听她解释具体卡点；她愿意时，再在学生端请求讲解或验证。当前判断不足的地方，不必全部立即补测。家长咨询不会直接改变掌握判断，也不会向孩子派发任务。',
    );
    return;
  }
  if (intent === 'verify') {
    if (role.value !== 'student') return;
    if (item.value.test.stage === 'running') {
      add(labels[intent], '当前还有一次未结束的检测。请先继续或结束它，再决定是否另开。');
      return;
    }
    if (!view && !chapter) {
      add(labels[intent], '先在学习情况中选择一个章节，或从教材选择章节范围，再准备检测。');
      return;
    }
    const chapterName = chapter?.name ?? view!.chapter;
    const plan = fixturePlan(state.space, [chapterName]);
    add(
      labels[intent],
      `围绕“${chapter?.name ?? view!.title}”，准备查看${chapterName}的示例表现。\n本轮固定题单 ${plan.length} 题，参考 ${plan.length * 3} 分钟；其中包含可能看过的原题，后续解释仍需考虑接触与帮助。\n这是原型题单，不承诺充分覆盖或测完即掌握。你可以开始，也可以暂时不做。`,
      action('verify', '按此安排开始'),
    );
    return;
  }
  if (intent === 'explain' || intent === 'hint') {
    if (role.value !== 'student' || c.question === undefined) {
      add(labels[intent], '先打开或明确选择要讨论的题目。');
      return;
    }
    if (item.value.test.stage === 'running') {
      const a = action('teach', intent === 'hint' ? '结束检测，只看提示' : '结束检测，转入讲解');
      a.help = intent === 'hint' ? 'hint' : 'explain';
      add(
        labels[intent],
        `这会结束当前独立检测。已提交 ${item.value.test.answers.length} 题及当前草稿会保留，其余记为未检测。确认前不展示提示或答案。`,
        a,
      );
      return;
    }
    const standalone = route.query.from === 'test';
    if (
      (!item.value.imported || item.value.processing || item.value.failure || item.value.hidden) &&
      !standalone
    ) {
      add(labels[intent], '当前原资料不可查看，不能通过对话恢复已删除或未处理完成的原件。');
      return;
    }
    item.value.selectedQuestion = c.question;
    if (!showHelp(intent === 'hint' ? 'hint' : 'explain', standalone)) return;
    add(
      labels[intent],
      intent === 'hint'
        ? questions[state.space][c.question]!.hint
        : questions[state.space][c.question]!.explanation.join('\n\n'),
    );
    return;
  }
  if (intent === 'challenge') {
    if (role.value !== 'student') return;
    if (
      state.space !== 'school' ||
      c.question !== 1 ||
      item.value.kind !== 'exam' ||
      item.value.hidden ||
      !item.value.imported
    ) {
      add(
        labels[intent],
        '本轮复核情景为校内示例整卷第 2 题。当前请求没有提交为该题的事项，也没有更改学习判断。',
      );
      return;
    }
    add(
      labels[intent],
      '将针对当前第 2 题提交识别复核，保留原件和原识别。提报不直接证明系统错了，也不直接更改掌握判断。',
      action('challenge', '提交这道题的复核'),
    );
    return;
  }
  if (intent === 'delete') {
    if (role.value !== 'student' || !item.value.imported || item.value.hidden) return;
    add(
      labels[intent],
      `确认对象：${item.value.sourceName}。\n将从学生界面移除${item.value.kind === 'exam' ? '整卷及关联错题、原作答' : '这道独立上传题及原作答'}，不可恢复。内部获准记录仍保留；家长相关依据权限不变。`,
      action('delete', '确认删除这份资料'),
    );
    return;
  }
  if (intent === 'prepare') {
    if (role.value !== 'admin') return;
    if (!['current', 'active'].includes(item.value.model)) {
      add(labels[intent], '当前已有维护候选。请在模型与映射页继续检查，不覆盖尚未结束的候选。');
      return;
    }
    add(
      labels[intent],
      `对象：${spaces[state.space].name} / ${spaces[state.space].chapter}。将建立本章的固定示例维护候选，供查看差异、检查和审核；不会自动批准或发布。`,
      action('prepare', '建立并查看候选'),
    );
  }
}
function stale(entry: Exchange) {
  return (
    !!entry.action &&
    (contextKey(entry.action.context) !== contextKey(context.value) ||
      !readable.value ||
      (entry.action.kind === 'prepare' && !['current', 'active'].includes(item.value.model)))
  );
}
async function execute(entry: Exchange) {
  const a = entry.action;
  if (!a || a.status !== 'pending' || stale(entry) || state.scenario === 'offline') return;
  const index = a.context.question;
  if (a.kind === 'verify') {
    const chapterName =
      a.context.chapter ?? (index === undefined ? undefined : learnerViews()[index]!.chapter);
    if (
      !chapterName ||
      !spaces[state.space].chapters.includes(chapterName) ||
      !startTest([chapterName])
    )
      return;
    a.status = 'done';
    entry.response += '\n\n已开始本次检测，作答在当前工作区完成。';
    conversation.open = false;
    await router.push('/student/test');
  } else if (a.kind === 'teach') {
    if (index === undefined) return;
    endTest('中途请求讲解');
    item.value.selectedQuestion = index;
    const hint = a.help === 'hint';
    if (!showHelp(hint ? 'hint' : 'explain', true)) return;
    a.status = 'done';
    entry.response +=
      '\n\n检测已结束。以下是本次实际展示的帮助：\n' +
      (hint
        ? questions[state.space][index]!.hint
        : questions[state.space][index]!.explanation.join('\n\n'));
    await router.push({ path: '/student/question', query: { from: 'test' } });
  } else if (a.kind === 'delete') {
    deleteExam();
    a.status = 'done';
    entry.response = '已移除指定资料。原确认中的对象不会通过再次点击重复删除。';
    await router.push('/student/materials');
  } else if (a.kind === 'challenge') {
    reportIssue();
    a.status = 'done';
    entry.response += '\n\n复核事项已提交，尚未确认识别错误。';
  } else if (a.kind === 'prepare') {
    if (!['current', 'active'].includes(item.value.model)) return;
    item.value.proposal = `核对${spaces[state.space].chapter}的任务条件、适用解法及教材映射（固定候选样例）。`;
    item.value.model = 'candidate';
    audit('从对话建立本章示例维护候选，未批准或发布');
    a.status = 'done';
    entry.response += '\n\n候选已建立，可以继续查看与检查。';
    await router.push('/admin/domain');
  }
}
function sendFree() {
  if (!chat.value.draft.trim() || !readable.value) return;
  if (state.scenario === 'offline') {
    notify('尚未发送，输入保留。');
    return;
  }
  add(
    chat.value.draft.trim(),
    '这段表达已保留在本轮演示对话中。本轮未连接语义模型，尚未理解或执行这个请求；可选择情景示例走查完整交互。',
  );
  chat.value.draft = '';
  activeId.value = null;
  examplesOpen.value = false;
  receipt.value = '已记录 · 原型未连接模型，尚未理解或执行。';
  composer.value?.focus({ preventScroll: true });
}
function close() {
  conversation.open = false;
  activeId.value = null;
  composer.value?.focus({ preventScroll: true });
}
function toggleHistory() {
  conversation.open = !conversation.open;
  activeId.value = null;
  receipt.value = '';
  examplesOpen.value = false;
}
function keydown(event: KeyboardEvent) {
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing && event.keyCode !== 229) {
    event.preventDefault();
    sendFree();
  }
}
function cancel(entry: Exchange) {
  if (entry.action?.status === 'pending') entry.action.status = 'cancelled';
}
</script>
<template>
  <section
    v-if="readable"
    ref="dock"
    class="intent-dock"
    :class="[role, { 'history-open': conversation.open }]"
    aria-label="DeerMind 输入区"
  >
    <aside
      v-if="conversation.open"
      id="intent-history"
      class="intent-panel"
      aria-label="DeerMind 对话历史"
      @keydown.esc="close"
    >
      <header class="intent-heading">
        <span class="intent-avatar"><Icon name="chat" /></span>
        <div>
          <strong>对话历史</strong><small>{{ spaces[state.space].name }} · 仅当前角色</small>
        </div>
        <button class="icon-button" aria-label="收起对话历史" @click="close">×</button>
      </header>
      <div ref="scroller" class="intent-messages">
        <div v-if="!visibleEntries.length" class="intent-welcome">
          <h2>从眼前的问题聊起。</h2>
          <p>直接在下方输入。已发送的内容会保留在这里，随时可以收起。</p>
        </div>
        <p v-if="visibleEntries.length !== chat.entries.length" class="note">
          与已删除原资料有关的旧对话内容已同步隐藏。
        </p>
        <article v-for="entry in visibleEntries" :key="entry.id" class="intent-exchange">
          <div class="intent-user">{{ entry.request }}</div>
          <small class="message-context">围绕：{{ entry.context.label }}</small>
          <IntentReply
            :entry="entry"
            :stale="stale(entry)"
            :offline="state.scenario === 'offline'"
            @execute="execute"
            @cancel="cancel"
          />
        </article>
      </div>
    </aside>
    <section
      v-else-if="activeEntry"
      class="intent-current"
      aria-label="DeerMind 当前回复"
      aria-live="polite"
    >
      <header>
        <Icon name="leaf" :size="17" />
        <strong>{{
          activeEntry.action?.status === 'pending' ? '请确认下一步' : 'DeerMind'
        }}</strong>
        <small>{{ activeEntry.context.label }}</small>
        <button class="icon-button" aria-label="收起当前回复" @click="activeId = null">×</button>
      </header>
      <div class="intent-current-body">
        <IntentReply
          :entry="activeEntry"
          :stale="stale(activeEntry)"
          :offline="state.scenario === 'offline'"
          @execute="execute"
          @cancel="cancel"
        />
      </div>
    </section>
    <div v-if="examplesOpen" id="intent-examples" class="intent-suggestions">
      <span>固定情景示例 · 预写回复与操作，非模型理解</span>
      <button v-for="choice in choices" :key="choice.id" @click="run(choice.id)">
        {{ choice.label }}<Icon name="arrow" :size="13" />
      </button>
    </div>
    <form class="intent-composer" @submit.prevent="sendFree">
      <div class="conversation-context">
        <Icon name="leaf" :size="15" />
        <strong>DeerMind</strong>
        <span :title="`${spaces[state.space].name} · ${context.label}`"
          >{{ spaces[state.space].name }} · {{ context.label }}</span
        >
        <small>{{ { student: '学生', parent: '家长', admin: '管理' }[role] }}</small>
      </div>
      <label class="sr-only" for="intent-input">对 DeerMind 说</label>
      <textarea
        ref="composer"
        id="intent-input"
        v-model="chat.draft"
        rows="2"
        placeholder="说说你的问题，或想做的事…"
        @keydown="keydown"
      />
      <p v-if="receipt" class="intent-receipt" role="status">{{ receipt }}</p>
      <div class="composer-toolbar">
        <button
          type="button"
          class="composer-tool"
          :aria-expanded="conversation.open"
          :aria-label="conversation.open ? '隐藏对话历史' : '展开对话历史'"
          :aria-controls="conversation.open ? 'intent-history' : undefined"
          @click="toggleHistory"
        >
          <Icon name="clock" :size="16" /><span>对话历史</span>
          <small v-if="visibleEntries.length">{{ visibleEntries.length }}</small>
        </button>
        <button
          type="button"
          class="composer-tool"
          :aria-expanded="examplesOpen"
          :aria-controls="examplesOpen ? 'intent-examples' : undefined"
          @click="examplesOpen = !examplesOpen"
        >
          <Icon name="plus" :size="16" /><span>情景示例</span>
        </button>
        <span class="composer-key-hint">Enter 发送 · Shift + Enter 换行</span>
        <button
          class="round-button"
          :disabled="!chat.draft.trim()"
          aria-label="发送对话"
          type="submit"
        >
          <Icon name="arrow" :size="18" />
        </button>
      </div>
    </form>
  </section>
</template>
