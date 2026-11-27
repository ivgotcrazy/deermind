<script setup lang="ts">
import {
  PanelLeftClose,
  PanelLeftOpen,
  PanelRightClose,
  PanelTopClose,
  PanelTopOpen,
} from '@lucide/vue';
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue';
import type { components } from '../../../../contracts/generated/http/schema';
import { ApiError, get, post } from '../../shared/api/http';
import AdoptedChapter from '../../shared/content/AdoptedChapter.vue';
import BookReader from '../components/BookReader.vue';
import type { Realtime } from '../../shared/realtime/client';
import { Button } from '../components/ui/button';
import ActivityDirectory from '../features/conversation/ActivityDirectory.vue';
import DetectionPlanCard from '../features/conversation/DetectionPlanCard.vue';
import QuestionCard from '../features/conversation/QuestionCard.vue';
import StudyComposer from '../features/conversation/StudyComposer.vue';
import TutorText from '../features/conversation/TutorText.vue';
import {
  activityClock,
  activityDay,
  activityLabels,
} from '../features/conversation/activityLabels';

type Schema = components['schemas'];
const { opened, session, accountId, realtime } = defineProps<{
  opened: Schema['SpaceWorkspace'];
  session: Pick<Schema['SessionView'], 'session_id' | 'csrf_token'>;
  accountId: string;
  realtime: Pick<Realtime, 'watch'>;
  created: boolean;
}>();

// 仅保存界面偏好。空间切换时实例随 space_id 重建。
const key = `deermind:study-layout:${accountId}:${opened.space.space_id}`;
const readerOpen = ref(true);
const chatOpen = ref(true);
const activityOpen = ref(true);
const showDirectoryButton = ref<InstanceType<typeof Button>>();
const hideDirectoryButton = ref<InstanceType<typeof Button>>();
defineExpose({
  readerOpen,
  openReader: () => {
    readerOpen.value = true;
  },
});
const draft = ref('');
const quotedContent = ref<{ title: string; source: Schema['Ref'] }>();
const pending = ref<Schema['LearningInputCommand']>();
const waitingForReceipt = ref(false);
const workNotice = ref('');
type WorkRequest = {
  requestId: string;
  action:
    'interaction.handle_input' | 'interaction.submit_answer' | 'interaction.prepare_detection';
};
const trackedWork = ref<WorkRequest>();
const retryChoice = ref<{ work: WorkRequest; execution: string; requestId: string }>();
const answers = ref<Record<string, string>>({});
const answerRequests = new Map<string, Schema['AnswerCommand']>();
const draftKey = `${key}:draft`;
const pendingKey = `${key}:pending`;
try {
  const saved = localStorage.getItem(key);
  readerOpen.value = saved?.[0] !== '0';
  chatOpen.value = saved?.[1] !== '0';
  activityOpen.value = saved?.[2] !== '0';
  draft.value = sessionStorage.getItem(draftKey) ?? '';
  const savedRequest = sessionStorage.getItem(pendingKey);
  if (savedRequest) pending.value = JSON.parse(savedRequest) as Schema['LearningInputCommand'];
} catch {
  // 浏览器禁用存储时仍可调整本页布局。
}

watch([readerOpen, chatOpen, activityOpen], ([reader, chat, activities]) => {
  try {
    localStorage.setItem(key, `${Number(reader)}${Number(chat)}${Number(activities)}`);
  } catch {
    // 浏览不依赖本地存储。
  }
});

const controller = new AbortController();
let turnCheck: AbortController | undefined;
const unsubscribe = realtime.watch(
  { kind: 'learning_space', id: opened.space.space_id },
  ['conversation', 'activity_tree'],
  async ({ current }) => {
    if (!current() || controller.signal.aborted || saving.value) return;
    await checkTurn();
  },
);
const timer = window.setInterval(() => {
  if (!saving.value && (pending.value || trackedWork.value || active.value?.active_input_id))
    void checkTurn();
}, 2000);
onBeforeUnmount(() => {
  controller.abort();
  turnCheck?.abort();
  unsubscribe();
  window.clearInterval(timer);
});
const active = ref<Schema['CurrentConversation']>();
const activities = ref<Schema['ActivityPage']>();
const branches = ref<Record<string, Schema['ActivityPage']>>({});
const expanded = ref<Record<string, boolean>>({});
const messages = ref<Schema['MessageView'][]>();
const chatContent = ref<HTMLElement>();
const studyInput = ref<InstanceType<typeof StudyComposer>>();
const history = ref<Schema['ActivityView']>();
const loadingHistory = ref(false);
const historyCursor = ref<string>();
const selectedMessage = computed(() => history.value?.first_message_ref);
const displayActivity = computed(
  () => active.value?.current_activity ?? activities.value?.items[0],
);
const pathLabels = computed(
  () => active.value?.path.map((item) => activityLabels[item.type]).join(' / ') || '学习对话',
);
const answerParentId = computed(() =>
  active.value?.current_activity?.type === 'question_answer'
    ? (active.value.current_activity.parent_id ?? undefined)
    : undefined,
);
const completedDisplay = computed(() => {
  const activity = history.value ?? displayActivity.value;
  if (activity?.run_state !== 'completed') return '';
  return `${activityDay(activity.started_at)} ${activityClock.format(new Date(activity.started_at))} · 已完成的${activityLabels[activity.type]}`;
});
const studyTopics = computed(() =>
  opened.study_methods?.length
    ? opened.study_methods
    : (opened.adoption.snapshot.items ?? []).map((item) => item.title),
);
const startPrompt = computed(() =>
  opened.study_methods?.length &&
  opened.adoption.snapshot.items.some((item) => item.method_mode === 'each')
    ? '目标要求分别掌握所选方法。想先学哪一种？'
    : '可以从这里开始，也可以直接提问。',
);
const error = ref('');
const saving = ref(false);
watch(
  saving,
  (writing) => {
    if (writing) turnCheck?.abort();
  },
  { flush: 'sync' },
);
let stopCommand: Schema['StopReply'] | undefined;
let detectionRequest: Schema['PrepareDetectionCommand'] | undefined;
let roundRequest: Schema['OpenDetectionRound'] | undefined;
let navigation = 0;
const options = { params: { scope_id: opened.space.space_id }, session, signal: controller.signal };
const conversation = '/api/m1/learning-spaces/{scope_id}/conversation';
const reports = new Map<string, Schema['PresentationCommand']>();
const reported = new Set<string>();
let presentationObserver: IntersectionObserver | undefined;

// 呈现报告独立发送，刷新或重新连接不阻塞聊天。
function watchPresentations(items: Schema['MessageView'][], surface: 'chat' | 'history') {
  presentationObserver?.disconnect();
  if (!chatOpen.value || !chatContent.value || !('IntersectionObserver' in window)) return;
  const visible = new Map<string, Schema['MessageView']>();
  presentationObserver = new IntersectionObserver(
    (changes, observer) => {
      for (const change of changes) {
        const message = visible.get(change.target.id);
        if (!message || !change.isIntersecting || document.visibilityState !== 'visible') continue;
        observer.unobserve(change.target);
        const key = surface + ':' + message.message_id;
        if (reported.has(key)) continue;
        const resource = { owner: 'interaction', type: 'message', id: message.message_id };
        const report = reports.get(key) ?? {
          presentation_id: crypto.randomUUID(),
          surface,
          resource_ref: resource,
          content_part_refs: message.parts.map((_, index) => ({
            ...resource,
            path: '/parts/' + index,
          })),
          client_reported_at: new Date().toISOString(),
        };
        reports.set(key, report);
        reported.add(key);
        void post('/api/m1/learning-spaces/{scope_id}/presentations', report, options).catch(() => {
          reported.delete(key);
        });
      }
    },
    { root: chatContent.value },
  );
  for (const message of items) {
    if (message.role === 'student' || !message.parts.length) continue;
    const element = document.getElementById('study-message-' + message.message_id);
    if (!element) continue;
    visible.set(element.id, message);
    presentationObserver.observe(element);
  }
}

watch(chatOpen, async (open) => {
  await nextTick();
  if (open && messages.value) {
    watchPresentations(messages.value, selectedMessage.value ? 'history' : 'chat');
  } else {
    presentationObserver?.disconnect();
  }
});
onBeforeUnmount(() => presentationObserver?.disconnect());

watch(
  draft,
  (text) => {
    try {
      if (text) sessionStorage.setItem(draftKey, text);
      else sessionStorage.removeItem(draftKey);
    } catch {
      // 页内仍保留输入。
    }
  },
  { flush: 'sync' },
);

function persistPending(value?: Schema['LearningInputCommand']) {
  pending.value = value;
  try {
    if (value) sessionStorage.setItem(pendingKey, JSON.stringify(value));
    else sessionStorage.removeItem(pendingKey);
  } catch {
    // 无法跨刷新恢复时，仍可在本页补读。
  }
}

function showError(reason: unknown) {
  if (!controller.signal.aborted)
    error.value = reason instanceof Error ? reason.message : '暂时无法读取对话，请重试。';
}

async function readActivities(parent?: string, cursor?: string, signal = controller.signal) {
  const result = await get(conversation, {
    ...options,
    signal,
    query: { view: 'activity_tree', activity_ref: parent, cursor },
  });
  if (signal.aborted) return;
  if (!('items' in result) || 'last_seq' in result) throw new Error('活动目录返回格式不正确。');
  const previous = parent ? branches.value[parent] : activities.value;
  const page =
    cursor && previous
      ? { items: [...previous.items, ...result.items], next_cursor: result.next_cursor }
      : result;
  if (parent) branches.value[parent] = page;
  else activities.value = page;
}

async function more(query: { parent?: string; cursor?: string }) {
  try {
    await readActivities(query.parent, query.cursor);
  } catch (reason) {
    showError(reason);
  }
}

async function toggle(id: string) {
  expanded.value[id] = !expanded.value[id];
  if (expanded.value[id] && !branches.value[id]) await more({ parent: id });
}

async function readMessages(
  after?: number,
  viewed?: Schema['ActivityView'],
  cursor?: string,
  signal = controller.signal,
) {
  const request = ++navigation;
  const anchor = viewed?.first_message_ref;
  const result = await get(conversation, {
    ...options,
    signal,
    query: {
      view: 'messages',
      after_seq: after,
      anchor_message_id: anchor,
      activity_ref: viewed?.activity_ref.activity_id,
      cursor,
    },
  });
  if (signal.aborted) return;
  if (!('last_seq' in result)) throw new Error('聊天记录返回格式不正确。');
  if (request !== navigation) return;
  messages.value = cursor ? [...(messages.value ?? []), ...result.items] : result.items;
  loadingHistory.value = false;
  historyCursor.value = viewed ? (result.next_cursor ?? undefined) : undefined;
  if (viewed) chatOpen.value = true;
  await nextTick();
  if (signal.aborted || request !== navigation) return;
  if (chatContent.value && !cursor) {
    chatContent.value.scrollTop = viewed ? 0 : chatContent.value.scrollHeight;
  }
  watchPresentations(messages.value, viewed ? 'history' : 'chat');
}

async function locate(activity: Schema['ActivityView']) {
  if (
    activity.activity_ref.activity_id === active.value?.current_activity?.activity_ref.activity_id
  ) {
    await returnToCurrent();
    return;
  }
  const previous = history.value;
  history.value = activity;
  loadingHistory.value = true;
  try {
    await readMessages(undefined, activity);
  } catch (reason) {
    if (history.value === activity) {
      history.value = previous;
      loadingHistory.value = false;
      showError(reason);
    }
  }
}

async function readHistoryPage() {
  if (!history.value || !historyCursor.value) return;
  try {
    await readMessages(undefined, history.value, historyCursor.value);
  } catch (reason) {
    showError(reason);
  }
}

function readLatest(signal = controller.signal) {
  return readMessages(
    Math.max(0, (active.value?.latest_message_seq ?? 0) - 50),
    undefined,
    undefined,
    signal,
  );
}

async function returnToCurrent() {
  const previous = history.value;
  history.value = undefined;
  chatOpen.value = true;
  try {
    await readLatest();
  } catch (reason) {
    history.value = previous;
    showError(reason);
  }
}

async function refresh() {
  error.value = '';
  try {
    await readCurrent();
    await Promise.all([readActivities(), history.value ? Promise.resolve() : readLatest()]);
  } catch (reason) {
    showError(reason);
  }
}

async function readCurrent(signal = controller.signal) {
  const result = await get(conversation, { ...options, signal, query: { view: 'current' } });
  if (signal.aborted) return;
  if (!('current' in result)) throw new Error('当前活动返回格式不正确。');
  const previous = active.value?.current_activity?.activity_ref.activity_id;
  active.value = result.current;
  if (previous !== result.current.current_activity?.activity_ref.activity_id) {
    const ancestors = result.current.path.slice(0, -1);
    for (const item of ancestors) expanded.value[item.activity_ref.activity_id] = true;
    await Promise.all(
      ancestors.map((item) => readActivities(item.activity_ref.activity_id, undefined, signal)),
    );
  }
}

function confirmAccepted(sent: Schema['LearningInputCommand']) {
  waitingForReceipt.value = false;
  if (draft.value === sent.input.text) draft.value = '';
  if (quotedContent.value?.source.id === sent.input.explicit_refs[0]?.id)
    quotedContent.value = undefined;
}

async function readWork(work: WorkRequest, signal: AbortSignal) {
  return get('/api/m1/requests/receipt', {
    session,
    signal,
    query: {
      action: work.action,
      resource_kind: 'learning_space',
      resource_id: opened.space.space_id,
      request_id: work.requestId,
    },
  });
}

function offerRetry(work: WorkRequest, execution: string | null | undefined) {
  if (!execution) return;
  retryChoice.value = { work, execution, requestId: crypto.randomUUID() };
  workNotice.value =
    work.action === 'interaction.submit_answer' ? '作答已保存，反馈未完成。' : '这次处理未完成。';
}

async function retryLast() {
  const choice = retryChoice.value;
  if (!choice || saving.value || active.value?.active_input_id) return;
  saving.value = true;
  try {
    await post(
      '/api/m1/learning-spaces/{scope_id}/input-retries',
      {
        request_id: choice.requestId,
        execution_ref: choice.execution,
      },
      options,
    );
    trackedWork.value = choice.work;
    retryChoice.value = undefined;
    workNotice.value = '正在重试原请求。';
    await refresh();
  } catch (reason) {
    showError(reason);
  } finally {
    saving.value = false;
  }
}

async function checkTurn() {
  if (saving.value || turnCheck || controller.signal.aborted) return;
  const check = new AbortController();
  turnCheck = check;
  const { signal } = check;
  try {
    const sent = pending.value;
    if (sent) {
      const work: WorkRequest = { requestId: sent.request_id, action: 'interaction.handle_input' };
      const receipt = await readWork(work, signal);
      if (signal.aborted) return;
      if (receipt.receipt_state === 'not_found') {
        waitingForReceipt.value = true;
      } else {
        confirmAccepted(sent);
        if (receipt.receipt_state === 'completed') {
          persistPending();
          workNotice.value = receipt.business_state === 'cancelled' ? '已停止本次回复。' : '';
          if (receipt.business_state === 'failed') offerRetry(work, receipt.execution_ref);
        }
      }
    }
    const tracked = trackedWork.value;
    if (tracked) {
      const receipt = await readWork(tracked, signal);
      if (signal.aborted) return;
      if (receipt.receipt_state === 'completed') {
        trackedWork.value = undefined;
        workNotice.value = '';
        if (receipt.business_state === 'failed') offerRetry(tracked, receipt.execution_ref);
      }
    }
    const previous = active.value;
    await readCurrent(signal);
    if (signal.aborted) return;
    if (
      previous?.active_input_id &&
      !active.value?.active_input_id &&
      workNotice.value === '作答已保存，正在核对这道题。'
    ) {
      workNotice.value = '作答已保存。';
    }
    if (
      previous?.current_activity?.activity_ref.activity_id !==
      active.value?.current_activity?.activity_ref.activity_id
    ) {
      const parents = new Set(
        [...(previous?.path ?? []), ...(active.value?.path ?? [])]
          .map((item) => item.activity_ref.activity_id)
          .filter((id) => expanded.value[id]),
      );
      await Promise.all([
        readActivities(undefined, undefined, signal),
        ...[...parents].map((id) => readActivities(id, undefined, signal)),
      ]);
    }
    if (
      !signal.aborted &&
      !history.value &&
      (messages.value?.at(-1)?.message_seq ?? -1) < (active.value?.latest_message_seq ?? 0)
    ) {
      await readLatest(signal);
    }
  } catch {
    // 查询失败时不推断已受理、失败或完成，下一次继续补查。
  } finally {
    turnCheck = undefined;
  }
}

async function send() {
  if (saving.value || active.value?.active_input_id) return;
  const original = pending.value;
  if (!original && !draft.value.trim()) return;
  const sent = original ?? {
    request_id: crypto.randomUUID(),
    input: {
      text: draft.value,
      attachment_refs: [],
      explicit_refs: quotedContent.value ? [quotedContent.value.source] : [],
    },
  };
  persistPending(sent);
  retryChoice.value = undefined;
  error.value = '';
  workNotice.value = '';
  saving.value = true;
  try {
    await post('/api/m1/learning-spaces/{scope_id}/inputs', sent, options);
    confirmAccepted(sent);
    history.value = undefined;
    await refresh();
  } catch (reason) {
    if (reason instanceof ApiError && reason.status < 500 && reason.status !== 408) {
      persistPending();
      waitingForReceipt.value = false;
      showError(reason);
    } else {
      waitingForReceipt.value = true;
    }
  } finally {
    saving.value = false;
  }
  if (pending.value) void checkTurn();
}

async function answer(part: Schema['QuestionPart']) {
  const identity = part.task_use_ref.id;
  const activity = active.value?.current_activity;
  const wording = answers.value[identity]?.trim();
  if (!activity || !wording || saving.value || active.value?.active_input_id) return;
  const round = part.purpose === 'detection' ? active.value?.current_round : null;
  if (
    part.purpose === 'detection' &&
    (!round || round.state !== 'open' || round.task_use_ref.id !== identity)
  )
    return;
  const command = answerRequests.get(identity) ?? {
    request_id: crypto.randomUUID(),
    submission_id: crypto.randomUUID(),
    task_use_ref: part.task_use_ref,
    activity_ref: activity.activity_ref,
    round_ref: round?.round_ref ?? null,
    expected_round_revision: round?.round_ref.revision ?? null,
    answer: { text: wording },
  };
  answerRequests.set(identity, command);
  error.value = '';
  saving.value = true;
  try {
    await post('/api/m1/learning-spaces/{scope_id}/answers', command, options);
    trackedWork.value = { requestId: command.request_id, action: 'interaction.submit_answer' };
    retryChoice.value = undefined;
    answerRequests.delete(identity);
    if (answers.value[identity]?.trim() === command.answer.text) answers.value[identity] = '';
    history.value = undefined;
    workNotice.value = '作答已保存，正在核对这道题。';
    await refresh();
  } catch (reason) {
    if (reason instanceof ApiError && reason.status < 500 && reason.status !== 408) {
      answerRequests.delete(identity);
    }
    showError(reason);
  } finally {
    saving.value = false;
  }
}

async function prepareDetection() {
  if (saving.value || active.value?.active_input_id) return;
  detectionRequest ??= { request_id: crypto.randomUUID() };
  saving.value = true;
  error.value = '';
  try {
    await post('/api/m1/learning-spaces/{scope_id}/detection-plans', detectionRequest, options);
    trackedWork.value = {
      requestId: detectionRequest.request_id,
      action: 'interaction.prepare_detection',
    };
    retryChoice.value = undefined;
    detectionRequest = undefined;
    history.value = undefined;
    await refresh();
  } catch (reason) {
    if (reason instanceof ApiError && reason.status < 500 && reason.status !== 408) {
      detectionRequest = undefined;
    }
    showError(reason);
  } finally {
    saving.value = false;
  }
}

async function openRound(
  action: 'start_detection' | 'continue_detection',
  plan: Schema['DetectionPlanRef'],
) {
  const activity = active.value?.current_activity;
  if (!activity || saving.value || active.value?.active_input_id) return;
  saving.value = true;
  error.value = '';
  if (
    roundRequest?.action !== action ||
    roundRequest?.plan_ref.plan_id !== plan.plan_id ||
    roundRequest?.plan_ref.revision !== plan.revision ||
    roundRequest?.activity_ref.revision !== activity.activity_ref.revision
  ) {
    roundRequest = {
      request_id: crypto.randomUUID(),
      action,
      plan_ref: plan,
      activity_ref: activity.activity_ref,
      expected_activity_revision: activity.activity_ref.revision,
    };
  }
  try {
    const changed = await post(
      '/api/m1/learning-spaces/{scope_id}/activity-actions',
      roundRequest,
      options,
    );
    roundRequest = undefined;
    active.value = changed.result.current;
    history.value = undefined;
    await refresh();
  } catch (reason) {
    if (reason instanceof ApiError && reason.status < 500 && reason.status !== 408) {
      roundRequest = undefined;
    }
    showError(reason);
  } finally {
    saving.value = false;
  }
}

async function stop() {
  const target = active.value?.active_input_id;
  if (!target || saving.value) return;
  if (stopCommand?.target_input_id !== target) {
    stopCommand = {
      request_id: crypto.randomUUID(),
      action: 'stop_reply',
      target_input_id: target,
    };
  }
  error.value = '';
  saving.value = true;
  try {
    const reply = await post(
      '/api/m1/learning-spaces/{scope_id}/activity-actions',
      stopCommand,
      options,
    );
    active.value = reply.result.current;
    workNotice.value = reply.result.outcome === 'stopped' ? '已停止本次回复。' : '本次回复已结束。';
    stopCommand = undefined;
    if (!history.value) await readLatest();
  } catch (reason) {
    showError(reason);
  } finally {
    saving.value = false;
  }
  if (pending.value) void checkTurn();
}

async function control(action: Schema['ControlAction'], activity: Schema['ActivityView']) {
  if (saving.value) return;
  error.value = '';
  saving.value = true;
  try {
    const result = await post(
      '/api/m1/learning-spaces/{scope_id}/activity-actions',
      {
        request_id: crypto.randomUUID(),
        activity_ref: activity.activity_ref,
        expected_activity_revision: activity.activity_ref.revision,
        action,
      },
      options,
    );
    active.value = result.result.current;
    branches.value = {};
    expanded.value = {};
    await refresh();
  } catch (reason) {
    showError(reason);
  } finally {
    saving.value = false;
  }
}

function controlCurrent(action: Schema['ControlAction']) {
  const item = active.value?.current_activity;
  if (item) void control(action, item);
}

function startTopic(title: string) {
  if (draft.value.trim()) {
    studyInput.value?.focus();
    return;
  }
  draft.value = `请讲解「${title}」。`;
  chatOpen.value = true;
  studyInput.value?.focus();
}

async function setDirectoryOpen(open: boolean) {
  activityOpen.value = open;
  await nextTick();
  const button = open ? hideDirectoryButton.value : showDirectoryButton.value;
  (button?.$el as HTMLElement | undefined)?.focus({ preventScroll: true });
}

void refresh();
</script>

<template>
  <section class="workspace" aria-label="学习工作区">
    <p v-if="error" class="workspace-error" role="alert">
      {{ error }} <Button variant="outline" size="sm" @click="refresh()">重试读取</Button>
    </p>
    <div
      class="panes"
      :class="{ 'has-reader': readerOpen, 'has-directory': activityOpen, 'chat-folded': !chatOpen }"
    >
      <aside
        v-show="activityOpen"
        id="study-directory"
        class="pane activity-pane"
        aria-label="活动目录"
      >
        <header class="pane-header">
          <h2>活动历史</h2>
          <Button
            ref="hideDirectoryButton"
            class="pane-icon"
            type="button"
            variant="ghost"
            size="icon-sm"
            aria-label="收起目录"
            title="收起目录"
            aria-expanded="true"
            aria-controls="study-directory"
            @click="setDirectoryOpen(false)"
          >
            <PanelLeftClose aria-hidden="true" />
          </Button>
        </header>
        <div class="directory">
          <ActivityDirectory
            v-if="activities?.items.length"
            :page="activities"
            :expanded="expanded"
            :branches="branches"
            :can-resume="!saving && !active?.current_activity && !active?.active_input_id"
            :current-id="active?.current_activity?.activity_ref.activity_id"
            :history-id="history?.activity_ref.activity_id"
            :answer-parent-id="answerParentId"
            group-by-day
            @locate="locate"
            @toggle="toggle"
            @more="more"
            @resume="control('resume', $event)"
          />
          <p v-else-if="activities" class="muted">开始学习后，活动会按时间出现在这里。</p>
          <Button
            v-if="activities?.next_cursor"
            type="button"
            variant="ghost"
            size="sm"
            @click="more({ cursor: activities.next_cursor })"
          >
            更多活动
          </Button>
        </div>
      </aside>

      <section class="pane dialogue-pane" aria-label="学习对话">
        <header class="dialogue-header">
          <div class="dialogue-column heading-row">
            <div class="dialogue-title">
              <Button
                v-if="!activityOpen"
                ref="showDirectoryButton"
                class="pane-icon"
                type="button"
                variant="ghost"
                size="icon-sm"
                aria-label="展开目录"
                title="展开目录"
                aria-expanded="false"
                aria-controls="study-directory"
                @click="setDirectoryOpen(true)"
              >
                <PanelLeftOpen aria-hidden="true" />
              </Button>
              <div>
                <p class="activity-path">{{ pathLabels }}</p>
                <h1>{{ displayActivity?.name ?? '开始学习' }}</h1>
              </div>
            </div>
            <div class="dialogue-actions">
              <Button
                v-if="active?.allowed_actions.includes('pause')"
                type="button"
                variant="outline"
                size="sm"
                :disabled="saving"
                @click="controlCurrent('pause')"
              >
                暂停活动
              </Button>
              <Button
                v-if="active?.allowed_actions.includes('finish')"
                type="button"
                variant="outline"
                size="sm"
                :disabled="saving"
                @click="controlCurrent('finish')"
              >
                结束活动
              </Button>
              <Button
                v-if="active && active.current_activity?.type !== 'detection'"
                type="button"
                variant="outline"
                size="sm"
                :disabled="saving || !!active.active_input_id"
                @click="prepareDetection()"
              >
                准备检测
              </Button>
              <Button
                class="pane-icon"
                type="button"
                variant="ghost"
                size="icon-sm"
                aria-controls="study-chat-content"
                :aria-label="chatOpen ? '收起聊天' : '展开聊天'"
                :title="chatOpen ? '收起聊天' : '展开聊天'"
                :aria-expanded="chatOpen"
                @click="chatOpen = !chatOpen"
              >
                <PanelTopClose v-if="chatOpen" />
                <PanelTopOpen v-else />
              </Button>
            </div>
          </div>
        </header>
        <div v-show="chatOpen" id="study-chat-content" ref="chatContent" class="chat-content">
          <div class="dialogue-column message-list">
            <div v-if="history" class="history-notice">
              <span>正在回看 · {{ history.name }}</span>
              <Button type="button" variant="outline" size="sm" @click="returnToCurrent()"
                >回到当前</Button
              >
            </div>
            <p v-if="completedDisplay" class="past-state">{{ completedDisplay }}</p>
            <p v-if="history && loadingHistory" role="status">正在读取活动消息…</p>
            <div v-if="messages && !messages.length && !history" class="new-space">
              <h2 v-if="created">这是你在课程 v{{ opened.space.application_version }} 的新空间</h2>
              <p class="muted">{{ created ? startPrompt : '暂无聊天记录。' }}</p>
              <Button
                v-for="title in created ? studyTopics : []"
                :key="title"
                class="start-topic"
                type="button"
                variant="secondary"
                @click="startTopic(title)"
              >
                {{ title }}
              </Button>
            </div>
            <article
              v-for="message in messages"
              v-show="!history || !loadingHistory"
              :id="'study-message-' + message.message_id"
              :key="message.message_id"
              :class="[message.role, { selected: selectedMessage === message.message_id }]"
            >
              <small
                v-if="message.role === 'assistant'"
                class="speaker"
                :class="{ 'sr-only': completedDisplay }"
                >DeerMind</small
              >
              <template v-for="part in message.parts" :key="part.part_id">
                <QuestionCard
                  v-if="part.type === 'question'"
                  v-model:answer="answers[part.task_use_ref.id]"
                  :question="part"
                  :can-answer="
                    !history &&
                    (part.purpose === 'practice' ||
                      (part.purpose === 'detection' &&
                        active?.current_round?.state === 'open' &&
                        active.current_round.task_use_ref.id === part.task_use_ref.id)) &&
                    message.activity_ref?.activity_id ===
                      active?.current_activity?.activity_ref.activity_id
                  "
                  :busy="saving || !!active?.active_input_id"
                  @submit="answer(part)"
                />
                <DetectionPlanCard
                  v-else-if="part.type === 'detection_plan'"
                  :plan="part"
                  :can-start="
                    !history &&
                    !active?.current_round &&
                    message.activity_ref?.activity_id ===
                      active?.current_activity?.activity_ref.activity_id
                  "
                  :busy="saving || !!active?.active_input_id"
                  @start="
                    openRound('start_detection', {
                      plan_id: part.plan_ref.id,
                      revision: part.plan_ref.revision ?? 1,
                    })
                  "
                />
                <TutorText
                  v-else-if="part.type === 'text' && message.role === 'assistant'"
                  :text="part.text"
                />
                <p v-else>{{ part.text }}</p>
              </template>
            </article>
            <Button
              v-if="historyCursor && !loadingHistory"
              type="button"
              variant="ghost"
              size="sm"
              @click="readHistoryPage()"
              >更多活动消息</Button
            >
          </div>
        </div>

        <div class="composer-dock">
          <StudyComposer
            ref="studyInput"
            v-model="draft"
            class="dialogue-column"
            :citation="quotedContent?.title"
            :action="active?.active_input_id ? 'stop' : waitingForReceipt ? 'resend' : 'send'"
            :disabled="saving || (!active?.active_input_id && !waitingForReceipt && !!pending)"
            @send="send()"
            @stop="stop()"
            @remove-citation="quotedContent = undefined"
          >
            <div
              v-if="
                workNotice ||
                retryChoice ||
                waitingForReceipt ||
                active?.current_round?.can_continue
              "
              class="composer-status"
            >
              <p v-if="workNotice" role="status">{{ workNotice }}</p>
              <p v-if="waitingForReceipt && !active?.active_input_id" role="status">
                正在核对是否已受理，草稿已保留。
              </p>
              <Button
                v-if="retryChoice"
                type="button"
                variant="outline"
                size="sm"
                :disabled="saving"
                @click="retryLast()"
                >重试原请求</Button
              >
              <Button
                v-if="active?.current_round?.can_continue"
                type="button"
                variant="outline"
                size="sm"
                :disabled="saving || !!active.active_input_id"
                @click="openRound('continue_detection', active.current_round.plan_ref)"
                >继续下一题</Button
              >
            </div>
          </StudyComposer>
        </div>
      </section>

      <section v-show="readerOpen" class="pane reader-pane" aria-label="教材">
        <header class="pane-header">
          <h2>教材</h2>
          <Button
            class="pane-icon"
            type="button"
            variant="ghost"
            size="icon-sm"
            aria-label="收起教材"
            title="收起教材"
            aria-controls="study-reader-content"
            :aria-expanded="readerOpen"
            @click="readerOpen = false"
          >
            <PanelRightClose aria-hidden="true" />
          </Button>
        </header>
        <div id="study-reader-content" class="reader-content">
          <BookReader
            :session="session"
            :space="opened.space.space_id"
            @reference="
              quotedContent = $event;
              chatOpen = true;
            "
          >
            <AdoptedChapter
              :session="session"
              :space="opened.space.space_id"
              :chapters="opened.adoption.snapshot.chapters"
              :reading="{ title: opened.space.textbook_title, selectionKey: key + ':chapter' }"
              allow-reference
              @reference="
                quotedContent = $event;
                chatOpen = true;
              "
          /></BookReader>
        </div>
      </section>
    </div>
  </section>
</template>

<style scoped>
.workspace {
  display: flex;
  flex: 1 1 auto;
  flex-direction: column;
  min-height: 0;
  padding: 20px 18px 24px;
}
.workspace-error {
  margin: 0 0 0.5rem;
  color: #943f31;
}
.panes {
  --directory: 250px;
  --reader: 364px;
  display: grid;
  flex: 1 1 auto;
  grid-template-columns: minmax(0, 1fr);
  gap: 16px;
  min-height: 0;
}
.panes.has-directory {
  grid-template-columns: var(--directory) minmax(0, 1fr);
}
.panes.has-reader {
  grid-template-columns: minmax(0, 1fr) var(--reader);
  column-gap: 18px;
}
.panes.has-directory.has-reader {
  grid-template-columns: var(--directory) minmax(0, 1fr) var(--reader);
}
.pane {
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  border: 1px solid var(--border);
  border-radius: 12px;
  background: var(--background);
}
.pane-header {
  display: flex;
  flex: 0 0 57px;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  padding: 0 16px;
  border-bottom: 1px solid var(--border);
}
.pane-header h2 {
  margin: 0;
  font: var(--study-font-section);
}
.pane-icon {
  color: var(--muted-foreground);
}
.dialogue-header {
  flex: 0 0 auto;
  min-height: 92px;
  padding: 15px 22px 16px;
  border-bottom: 1px solid var(--border);
}
.dialogue-column {
  width: min(100%, 706px);
  margin-inline: auto;
}
.heading-row,
.dialogue-actions {
  display: flex;
  justify-content: space-between;
  gap: 0.375rem;
}
.dialogue-title {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  min-width: 0;
}
.dialogue-actions {
  flex-wrap: wrap;
  align-content: flex-start;
  justify-content: flex-end;
}
.activity-path {
  margin: 0 0 0.25rem;
  color: var(--primary);
  font: var(--study-font-meta);
  font-weight: 600;
}
.dialogue-header h1 {
  margin: 0;
  font: var(--study-font-title);
  overflow-wrap: anywhere;
}
.directory,
.reader-content,
.chat-content {
  flex: 1 1 auto;
  min-height: 0;
  overflow: auto;
  overscroll-behavior: contain;
}
.directory {
  padding: 15px 11px;
}
.directory > p {
  margin: 0.25rem 0.375rem;
  font: var(--study-font-ui);
}
.reader-content {
  padding: 19px 17px 23px;
}
.chat-content {
  padding: 24px 21px 26px;
}
.chat-content:has(.history-notice) {
  padding-top: 16px;
}
.message-list {
  display: grid;
  align-content: start;
  gap: 1.375rem;
}
.message-list article {
  display: grid;
  gap: 0.5rem;
  min-width: 0;
  font: var(--study-font-body);
  overflow-wrap: anywhere;
}
.message-list article > p {
  margin: 0;
  white-space: pre-wrap;
}
.message-list .student {
  justify-self: end;
  width: fit-content;
  max-width: min(100%, 28rem);
  padding: 0.625rem 0.875rem;
  border-radius: 10px;
  background: var(--accent);
}
.speaker {
  color: var(--primary);
  font: var(--study-font-meta);
  font-weight: 600;
}
.message-list .system,
.past-state {
  color: var(--muted-foreground);
  font: var(--study-font-meta);
}
.message-list .selected {
  scroll-margin-top: 0.5rem;
}
.history-notice {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.5rem 0.75rem;
  border-radius: 0.5rem;
  background: var(--accent);
  color: var(--primary);
  font: var(--study-font-ui);
  font-weight: 600;
}
.history-notice :deep(button) {
  flex: none;
}
.new-space {
  padding-top: 0.5rem;
}
.new-space h2 {
  margin-top: 0;
  font: var(--study-font-section);
}
.new-space p {
  margin-bottom: 1.875rem;
}
.new-space .start-topic {
  display: flex;
  justify-content: flex-start;
  width: 100%;
  height: auto;
  min-height: 64px;
  margin-top: 1rem;
  padding: 0.875rem 1rem;
  border: 1px solid var(--border);
  background: var(--muted);
  color: var(--foreground);
  font: var(--study-font-ui);
  font-weight: 600;
  text-align: start;
  white-space: normal;
}
.muted {
  color: var(--muted-foreground);
}
.composer-dock {
  flex: none;
  padding: 0.625rem 21px 1rem;
}
.chat-folded .dialogue-pane {
  justify-content: space-between;
}
.composer-status {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.375rem 0.75rem;
  margin-bottom: 0.5rem;
  color: var(--muted-foreground);
  font: var(--study-font-ui);
}
.composer-status p {
  margin: 0;
}
.workspace :focus-visible:not(textarea) {
  outline: 2px solid var(--ring);
  outline-offset: 1px;
}
@media (max-width: 76rem) {
  .panes {
    --directory: 210px;
    --reader: 300px;
  }
}
@media (max-width: 60rem) {
  .workspace {
    padding: 0.75rem;
  }
  .panes {
    gap: 0.625rem;
  }
  .panes.has-reader {
    grid-template-columns: minmax(0, 1fr);
    grid-template-rows: minmax(13rem, 2fr) minmax(9rem, 1fr);
  }
  .panes.has-directory.has-reader {
    grid-template-columns: var(--directory) minmax(0, 1fr);
  }
  .has-directory.has-reader .activity-pane {
    grid-row: span 2;
  }
  .has-directory.has-reader .reader-pane {
    grid-column: 2;
  }
}
@media (max-width: 41rem) {
  .panes,
  .panes.has-directory,
  .panes.has-reader,
  .panes.has-directory.has-reader {
    grid-template-columns: minmax(0, 1fr);
  }
  .panes.has-directory {
    grid-template-rows: auto minmax(0, 1fr);
  }
  .panes.has-reader {
    grid-template-rows: minmax(11rem, 2fr) minmax(7rem, 1fr);
  }
  .panes.has-directory.has-reader {
    grid-template-rows: auto minmax(11rem, 2fr) minmax(7rem, 1fr);
  }
  .has-directory.has-reader .activity-pane {
    grid-row: auto;
  }
  .has-directory.has-reader .reader-pane {
    grid-column: auto;
  }
  .activity-pane .pane-header {
    flex-basis: 40px;
  }
  .directory {
    max-height: 8rem;
  }
  .dialogue-header,
  .chat-content,
  .composer-dock {
    padding-inline: 0.75rem;
  }
  .dialogue-header {
    min-height: 64px;
  }
  .heading-row {
    flex-wrap: wrap;
  }
}
</style>
