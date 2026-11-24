<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, watch } from 'vue';
import type { components } from '../../../../contracts/generated/http/schema';
import { ApiError, get, post } from '../../shared/api/http';
import AdoptedChapter from '../../shared/content/AdoptedChapter.vue';
import type { Realtime } from '../../shared/realtime/client';
import ActivityDirectory from '../features/conversation/ActivityDirectory.vue';
import DetectionPlanCard from '../features/conversation/DetectionPlanCard.vue';
import QuestionCard from '../features/conversation/QuestionCard.vue';
import { activityLabels } from '../features/conversation/activityLabels';

type Schema = components['schemas'];
const { opened, session, accountId, realtime } = defineProps<{
  opened: Schema['SpaceWorkspace'];
  session: Pick<Schema['SessionView'], 'session_id' | 'csrf_token'>;
  accountId: string;
  realtime: Pick<Realtime, 'watch'>;
}>();

// 仅保存界面偏好。空间切换时实例随 space_id 重建。
const key = `deermind:study-layout:${accountId}:${opened.space.space_id}`;
const readerOpen = ref(true);
const chatOpen = ref(true);
const activityOpen = ref(true);
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
  unsubscribe();
  window.clearInterval(timer);
});
const active = ref<Schema['CurrentConversation']>();
const activities = ref<Schema['ActivityPage']>();
const branches = ref<Record<string, Schema['ActivityPage']>>({});
const expanded = ref<Record<string, boolean>>({});
const messages = ref<Schema['MessageView'][]>();
const chatContent = ref<HTMLElement>();
const selectedMessage = ref<string>();
const error = ref('');
const saving = ref(false);
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

async function readActivities(parent?: string, cursor?: string) {
  const result = await get(conversation, {
    ...options,
    query: { view: 'activity_tree', activity_ref: parent, cursor },
  });
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

async function readMessages(after?: number, anchor?: string) {
  const request = ++navigation;
  const result = await get(conversation, {
    ...options,
    query: { view: 'messages', after_seq: after, anchor_message_id: anchor },
  });
  if (!('last_seq' in result)) throw new Error('聊天记录返回格式不正确。');
  if (request !== navigation) return;
  messages.value = result.items;
  selectedMessage.value = anchor;
  if (anchor) {
    chatOpen.value = true;
    await nextTick();
    document.getElementById('study-message-' + anchor)?.scrollIntoView({ block: 'nearest' });
  } else {
    await nextTick();
    if (chatContent.value) chatContent.value.scrollTop = chatContent.value.scrollHeight;
  }
  watchPresentations(result.items, anchor ? 'history' : 'chat');
}

async function locate(activity: Schema['ActivityView']) {
  try {
    await readMessages(undefined, activity.first_message_ref);
  } catch (reason) {
    showError(reason);
  }
}

async function refresh() {
  error.value = '';
  try {
    await readCurrent();
    await Promise.all([
      readActivities(),
      readMessages(Math.max(0, (active.value?.latest_message_seq ?? 0) - 50)),
    ]);
  } catch (reason) {
    showError(reason);
  }
}

async function readCurrent() {
  const result = await get(conversation, { ...options, query: { view: 'current' } });
  if (!('current' in result)) throw new Error('当前活动返回格式不正确。');
  active.value = result.current;
}

function confirmAccepted(sent: Schema['LearningInputCommand']) {
  waitingForReceipt.value = false;
  if (draft.value === sent.input.text) draft.value = '';
  if (quotedContent.value?.source.id === sent.input.explicit_refs[0]?.id)
    quotedContent.value = undefined;
}

async function readWork(work: WorkRequest) {
  return get('/api/m1/requests/receipt', {
    session,
    signal: controller.signal,
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
  if (saving.value || controller.signal.aborted) return;
  saving.value = true;
  try {
    const sent = pending.value;
    if (sent) {
      const work: WorkRequest = { requestId: sent.request_id, action: 'interaction.handle_input' };
      const receipt = await readWork(work);
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
      const receipt = await readWork(tracked);
      if (receipt.receipt_state === 'completed') {
        trackedWork.value = undefined;
        workNotice.value = '';
        if (receipt.business_state === 'failed') offerRetry(tracked, receipt.execution_ref);
      }
    }
    const previous = active.value;
    await readCurrent();
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
      await Promise.all([readActivities(), ...[...parents].map((id) => readActivities(id))]);
    }
    if (
      !selectedMessage.value &&
      previous?.latest_message_seq !== active.value?.latest_message_seq
    ) {
      await readMessages(Math.max(0, (active.value?.latest_message_seq ?? 0) - 50));
    }
  } catch {
    // 查询失败时不推断已受理、失败或完成，下一次继续补查。
  } finally {
    saving.value = false;
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
    selectedMessage.value = undefined;
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
    selectedMessage.value = undefined;
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
    selectedMessage.value = undefined;
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
    selectedMessage.value = undefined;
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
    if (!selectedMessage.value)
      await readMessages(Math.max(0, reply.result.current.latest_message_seq - 50));
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

void refresh();
</script>

<template>
  <section class="workspace" aria-label="学习工作区">
    <h2>{{ opened.space.textbook_title }} · {{ opened.space.target_title }}</h2>
    <p v-if="error" role="alert">
      {{ error }} <button type="button" @click="refresh()">重试读取</button>
    </p>
    <div class="panes" :class="{ paired: readerOpen, 'has-directory': activityOpen }">
      <aside class="pane" aria-label="活动目录">
        <header class="pane-header">
          <h3>活动</h3>
          <button type="button" :aria-expanded="activityOpen" @click="activityOpen = !activityOpen">
            {{ activityOpen ? '收起目录' : '展开目录' }}
          </button>
        </header>
        <div v-show="activityOpen" class="directory">
          <ActivityDirectory
            v-if="activities?.items.length"
            :page="activities"
            :expanded="expanded"
            :branches="branches"
            :can-resume="!saving && !active?.current_activity && !active?.active_input_id"
            @locate="locate"
            @toggle="toggle"
            @more="more"
            @resume="control('resume', $event)"
          />
          <p v-else-if="activities">暂无活动。</p>
          <button
            v-if="activities?.next_cursor"
            type="button"
            @click="more({ cursor: activities.next_cursor })"
          >
            更多活动
          </button>
        </div>
      </aside>
      <section class="pane" aria-label="学习对话">
        <header class="pane-header">
          <h3>学习对话</h3>
          <button
            type="button"
            aria-controls="study-chat-content"
            :aria-expanded="chatOpen"
            @click="chatOpen = !chatOpen"
          >
            {{ chatOpen ? '收起聊天' : '展开聊天' }}
          </button>
        </header>
        <div v-if="active?.path.length" class="activity-path">
          <div v-for="item in active.path" :key="item.activity_ref.activity_id" class="path-item">
            <span>{{ activityLabels[item.type] }}</span>
            <strong>{{ item.name }}</strong>
          </div>
          <button
            v-if="active.allowed_actions.includes('pause')"
            type="button"
            :disabled="saving"
            @click="controlCurrent('pause')"
          >
            暂停活动
          </button>
          <button
            v-if="active.allowed_actions.includes('finish')"
            type="button"
            :disabled="saving"
            @click="controlCurrent('finish')"
          >
            结束活动
          </button>
        </div>
        <div v-show="chatOpen" id="study-chat-content" ref="chatContent" class="chat-content">
          <p v-if="messages && !messages.length">暂无聊天记录。</p>
          <article
            v-for="message in messages"
            :id="'study-message-' + message.message_id"
            :key="message.message_id"
            :class="{ selected: selectedMessage === message.message_id }"
          >
            <small v-if="message.role !== 'system'">
              {{ message.role === 'student' ? '我' : 'DeerMind' }}
            </small>
            <template v-for="part in message.parts" :key="part.part_id">
              <QuestionCard
                v-if="part.type === 'question'"
                v-model:answer="answers[part.task_use_ref.id]"
                :question="part"
                :can-answer="
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
              <p v-else>{{ part.text }}</p>
            </template>
          </article>
        </div>
        <form class="composer" @submit.prevent="send()">
          <button
            v-if="active?.current_round?.can_continue"
            type="button"
            :disabled="saving || !!active.active_input_id"
            @click="openRound('continue_detection', active.current_round.plan_ref)"
          >
            继续下一题
          </button>
          <button
            v-if="active?.current_activity?.type !== 'detection'"
            type="button"
            :disabled="saving || !!active?.active_input_id"
            @click="prepareDetection()"
          >
            准备检测
          </button>
          <label for="study-input">输入消息</label>
          <p v-if="quotedContent">
            引用 {{ quotedContent.title }}
            <button type="button" @click="quotedContent = undefined">移除引用</button>
          </p>
          <textarea id="study-input" v-model="draft" rows="2" />
          <p v-if="workNotice" role="status">{{ workNotice }}</p>
          <button v-if="retryChoice" type="button" :disabled="saving" @click="retryLast()">
            重试原请求
          </button>
          <p v-if="active?.active_input_id" role="status">正在处理上一条消息。</p>
          <p v-else-if="waitingForReceipt" role="status">正在核对是否已受理，草稿已保留。</p>
          <div class="composer-actions">
            <button v-if="active?.active_input_id" type="button" :disabled="saving" @click="stop()">
              停止本次回复
            </button>
            <button
              v-else
              type="submit"
              :disabled="saving || (!waitingForReceipt && (!!pending || !draft.trim()))"
            >
              {{ waitingForReceipt ? '重试发送' : '发送' }}
            </button>
          </div>
        </form>
      </section>
      <section class="pane" aria-label="教材">
        <header class="pane-header">
          <h3>教材</h3>
          <button
            type="button"
            aria-controls="study-reader-content"
            :aria-expanded="readerOpen"
            @click="readerOpen = !readerOpen"
          >
            {{ readerOpen ? '收起教材' : '展开教材' }}
          </button>
        </header>
        <div v-show="readerOpen" id="study-reader-content" class="reader-content">
          <AdoptedChapter
            :session="session"
            :space="opened.space.space_id"
            :chapters="opened.adoption.snapshot.chapters"
            allow-reference
            @reference="
              quotedContent = $event;
              chatOpen = true;
            "
          />
        </div>
      </section>
    </div>
  </section>
</template>

<style scoped>
.workspace h2 {
  margin: 1.25rem 0;
  font-size: clamp(1.15rem, 2vw, 1.6rem);
  line-height: 1.4;
}
.panes {
  display: grid;
  gap: 0.75rem;
}
.pane {
  min-width: 0;
  align-self: start;
  border: 1px solid var(--color-line);
  border-radius: 0.5rem;
  background: #fcfdfb;
}
.pane-header {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  padding: 0.625rem 0.875rem;
}
.pane-header h3 {
  margin: 0;
  font-size: 1rem;
}
.pane-header button,
.composer-actions button {
  border: 1px solid var(--color-line);
  border-radius: 0.35rem;
  background: white;
  color: var(--color-accent);
  font: inherit;
  padding: 0.25rem 0.625rem;
  cursor: pointer;
}
.chat-content,
.reader-content,
.composer,
.directory,
.activity-path {
  padding: 0.875rem;
  border-top: 1px solid var(--color-line);
}
.path-item {
  display: inline-flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  align-items: center;
}
.path-item + .path-item {
  border-inline-start: 1px solid var(--color-line);
  padding-inline-start: 0.375rem;
}
.chat-content {
  min-height: 10rem;
  max-height: 60vh;
  overflow: auto;
  color: var(--color-muted);
}
.chat-content p {
  margin: 0;
}
.chat-content article {
  padding: 0.5rem;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.chat-content .selected {
  border-left: 2px solid var(--color-accent);
  background: #eef4ee;
}
.activity-path {
  display: flex;
  gap: 0.375rem;
  flex-wrap: wrap;
  font-size: 0.875rem;
}
.reader-content {
  max-height: 70vh;
  overflow: auto;
}
.composer {
  display: grid;
  gap: 0.375rem;
}
.composer-actions {
  display: flex;
  justify-content: flex-end;
}
.composer-actions button:disabled {
  opacity: 0.5;
  cursor: default;
}
.composer textarea {
  width: 100%;
  resize: vertical;
  border: 1px solid var(--color-line);
  border-radius: 0.35rem;
  padding: 0.5rem;
  font: inherit;
  color: inherit;
}
.workspace :focus-visible {
  outline: 2px solid var(--color-accent);
  outline-offset: 2px;
}
@media (min-width: 56rem) {
  .paired {
    grid-template-columns: minmax(0, 5fr) minmax(0, 6fr);
  }
  .pane:first-child {
    grid-column: 1 / -1;
  }
}
@media (min-width: 70rem) {
  .has-directory {
    grid-template-columns: minmax(11rem, 2fr) minmax(0, 5fr);
  }
  .paired.has-directory {
    grid-template-columns: minmax(11rem, 2fr) minmax(0, 5fr) minmax(0, 6fr);
  }
  .has-directory .pane:first-child {
    grid-column: auto;
  }
}
</style>
