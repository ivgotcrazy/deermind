<script setup lang="ts">
import { BookOpen, ChevronDown, PanelRightOpen, UserRound, X } from '@lucide/vue';
import { DialogClose } from 'reka-ui';
import { computed, onUnmounted, ref } from 'vue';
import type { components } from '../../../contracts/generated/http/schema';
import { ApiError, get, post } from '../shared/api/http';
import type { Realtime, RealtimeState } from '../shared/realtime/client';
import { Button } from './components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from './components/ui/dialog';
import LearningWorkspace from './layouts/LearningWorkspace.vue';

type Schema = components['schemas'];
type SpaceRequest = Schema['CreateSpace'] | Schema['EnterSpace'];
const props = defineProps<{
  realtime: Pick<Realtime, 'watch'>;
  session: Pick<Schema['SessionView'], 'session_id' | 'csrf_token'> & {
    account: Pick<Schema['SessionView']['account'], 'account_id' | 'display_name'>;
  };
  signOut: () => Promise<void>;
  signingOut: boolean;
  authError: string;
  realtimeState: RealtimeState;
  storageUnavailable: boolean;
  reconnect: () => void;
}>();
const courses = ref<Schema['CourseOption'][]>();
const spaces = ref<Schema['SpaceRow'][]>([]);
const opened = ref<Schema['SpaceWorkspace']>();
const current = computed(() => opened.value?.space);
const workspace = ref<InstanceType<typeof LearningWorkspace>>();
const pickerOpen = ref(false);
const accountOpen = ref(false);
const created = ref(false);
const pickerLeft = ref(16);
let pickerTrigger: HTMLButtonElement | undefined;
const pending = ref<SpaceRequest>();
const error = ref('');
const loading = ref(false);
const busy = ref(false);
const nextCourse = ref<string>();
const nextSpace = ref<string>();
const requests = new AbortController();
const { signal } = requests;
onUnmounted(() => requests.abort());
const available = computed(() => {
  const openedIds = new Set(spaces.value.map((space) => space.application_ref.id));
  if (current.value) openedIds.add(current.value.application_ref.id);
  return courses.value?.filter((course) => !openedIds.has(course.application_ref.id));
});
const priorSpaces = computed(() =>
  spaces.value.filter((space) => !created.value || space.space_id !== current.value?.space_id),
);
const pickerTitle = computed(() =>
  current.value
    ? `${current.value.textbook_title} · ${current.value.target_title}`
    : '选择学习空间',
);

async function readSpaces(cursor?: string) {
  const result = await get('/api/m1/learning-spaces', {
    session: props.session,
    signal,
    query: { cursor },
  });
  spaces.value = cursor ? [...spaces.value, ...result.items] : result.items;
  nextSpace.value = result.next_cursor ?? undefined;
  return result.recent_space_id;
}

async function readCourses(cursor?: string) {
  const result = await get('/api/m1/course-options', {
    session: props.session,
    query: { cursor },
    signal,
  });
  courses.value = cursor ? [...(courses.value ?? []), ...result.items] : result.items;
  nextCourse.value = result.next_cursor ?? undefined;
}

async function load(page?: 'courses' | 'spaces') {
  loading.value = true;
  try {
    if (page === 'courses') await readCourses(nextCourse.value);
    else if (page === 'spaces') await readSpaces(nextSpace.value);
    else await Promise.all([readSpaces(), readCourses()]);
  } catch (caught) {
    error.value = (caught as Error).message;
  } finally {
    loading.value = false;
  }
}

function showSpace(space: Schema['SpaceWorkspace'] | Schema['SpaceOpenResult']) {
  if (signal.aborted) return;
  created.value = 'created' in space && space.created;
  opened.value = space;
  pickerOpen.value = false;
  const url = new URL(window.location.href);
  url.searchParams.set('space', space.space.space_id);
  window.history.replaceState(window.history.state, '', url);
}

async function initialize() {
  busy.value = true;
  error.value = '';
  try {
    const recent = await readSpaces();
    const selected = new URL(window.location.href).searchParams.get('space');
    if (selected) {
      try {
        showSpace(
          await get('/api/m1/learning-spaces/{space_id}/workspace', {
            session: props.session,
            params: { space_id: selected },
            signal,
          }),
        );
        return;
      } catch (caught) {
        if (!(caught instanceof ApiError) || caught.status !== 404) throw caught;
      }
    }
    if (recent) await enterSpace(recent);
    else await readCourses();
  } catch (caught) {
    error.value = (caught as Error).message;
  } finally {
    busy.value = false;
  }
}

/** Keep the original command until it was acknowledged or explicitly rejected. */
async function send(command: SpaceRequest) {
  pending.value = command;
  busy.value = true;
  error.value = '';
  try {
    const response = await post('/api/m1/learning-spaces/open', command, {
      session: props.session,
      signal,
    });
    pending.value = undefined;
    showSpace(response.result);
  } catch (caught) {
    if (caught instanceof ApiError && caught.status < 500 && caught.status !== 408) {
      pending.value = undefined;
      error.value = caught.message;
      if (caught.code === 'application_changed') await load();
    } else {
      error.value = '暂时无法确认是否已进入空间，请查询本次结果。';
    }
  } finally {
    busy.value = false;
  }
}

async function checkRequest() {
  if (!pending.value) return;
  busy.value = true;
  try {
    const receipt = await get('/api/m1/requests/receipt', {
      session: props.session,
      signal,
      query: {
        action: 'product.open_learning_space',
        resource_kind: 'account',
        resource_id: props.session.account.account_id,
        request_id: pending.value.request_id,
      },
    });
    const result = receipt.result;
    if (receipt.receipt_state === 'completed' && result && 'entry_event_ref' in result) {
      pending.value = undefined;
      error.value = '';
      showSpace(result);
    } else {
      error.value = '尚未查到空间结果，可以用原请求重试。';
    }
  } catch {
    error.value = '查询失败，请稍后再次查询。';
  } finally {
    busy.value = false;
  }
}

function selectCourse(course: Schema['CourseOption']) {
  return send({
    request_id: crypto.randomUUID(),
    action: 'create',
    textbook_id: course.textbook_id,
    target_id: course.target_ref.target_id,
    expected_application_ref: course.application_ref,
  });
}

function enterSpace(id: string) {
  return send({ request_id: crypto.randomUUID(), action: 'enter', space_id: id });
}

function openPicker(event: MouseEvent) {
  if (event.currentTarget instanceof HTMLButtonElement) {
    pickerTrigger = event.currentTarget;
    pickerLeft.value = pickerTrigger.getBoundingClientRect().left;
  }
  pickerOpen.value = true;
  if (!pending.value) void load();
}

function restorePickerFocus(event: Event) {
  event.preventDefault();
  pickerTrigger?.focus();
}

void initialize();
</script>

<template>
  <section class="student-shell" aria-label="学生学习空间">
    <header class="space-header">
      <span class="wordmark">DeerMind</span>
      <Button
        class="space-trigger"
        type="button"
        variant="outline"
        size="sm"
        :data-current="!!current"
        aria-label="切换学习空间"
        aria-haspopup="dialog"
        :aria-expanded="pickerOpen"
        :title="pickerTitle"
        :disabled="busy && !current"
        @click="openPicker"
      >
        <BookOpen class="space-icon" aria-hidden="true" />
        <span class="space-name">{{ current?.target_title ?? '选择学习空间' }}</span>
        <span v-if="current" class="version">v{{ current.application_version }}</span>
        <ChevronDown aria-hidden="true" />
      </Button>
      <div class="account-actions">
        <Button
          v-if="workspace?.readerOpen === false"
          class="header-icon"
          type="button"
          variant="outline"
          size="icon-sm"
          aria-label="展开教材"
          title="展开教材"
          aria-controls="study-reader-content"
          aria-expanded="false"
          @click="workspace.openReader()"
        >
          <PanelRightOpen aria-hidden="true" />
        </Button>
        <div
          class="account"
          @focusout="
            (event) => {
              if (!(event.currentTarget as HTMLElement).contains(event.relatedTarget as Node))
                accountOpen = false;
            }
          "
          @keydown.esc="accountOpen = false"
        >
          <Button
            type="button"
            variant="outline"
            size="sm"
            class="account-trigger"
            aria-label="学生账号与退出登录"
            :title="session.account.display_name"
            :aria-expanded="accountOpen"
            @click="accountOpen = !accountOpen"
          >
            <UserRound aria-hidden="true" />
            <span class="account-name">{{ session.account.display_name }}</span>
            <ChevronDown class="account-chevron" aria-hidden="true" />
          </Button>
          <div v-if="accountOpen" class="account-menu">
            <Button variant="outline" size="sm" :disabled="signingOut" @click="signOut"
              >退出登录</Button
            >
          </div>
        </div>
      </div>
    </header>

    <div
      v-if="
        authError ||
        storageUnavailable ||
        realtimeState === 'reconnecting' ||
        realtimeState === 'unavailable'
      "
      class="connection"
    >
      <p v-if="authError" role="alert">{{ authError }}</p>
      <p v-if="storageUnavailable" role="status">待核对的消息暂存在本页，刷新后可能丢失。</p>
      <p v-if="realtimeState === 'reconnecting'" role="status">实时连接中断，正在重连…</p>
      <p v-else-if="realtimeState === 'unavailable'" role="status">
        实时连接暂不可用。 <Button variant="outline" size="sm" @click="reconnect">重新连接</Button>
      </p>
    </div>

    <div v-if="!current" class="first-entry">
      <h1>选择教材和目标</h1>
      <p v-if="busy || loading" role="status">正在打开学习空间…</p>
      <p v-if="error" role="alert">{{ error }}</p>
      <div v-if="pending" class="recovery">
        <Button variant="outline" :disabled="busy" @click="checkRequest">查询本次结果</Button>
        <Button :disabled="busy" @click="send(pending)">用原请求重试</Button>
      </div>
      <p v-if="!busy && courses?.length === 0 && !spaces.length">还没有可选用的课程。</p>
      <ul v-if="!busy && !pending" class="options">
        <li v-for="course in available" :key="course.application_ref.id">
          <Button variant="outline" @click="selectCourse(course)">
            {{ course.textbook_title }} · {{ course.target_title }} · 课程 v{{
              course.application_version
            }}
          </Button>
        </li>
      </ul>
    </div>
    <LearningWorkspace
      v-if="opened"
      :key="opened.space.space_id"
      ref="workspace"
      :session="session"
      :account-id="session.account.account_id"
      :realtime="realtime"
      :opened="opened"
      :created="created"
    />

    <Dialog v-model:open="pickerOpen">
      <DialogContent
        class="space-picker"
        :style="{ '--picker-left': pickerLeft + 'px' }"
        overlay-class="space-picker-overlay"
        :show-close-button="false"
        @close-auto-focus="restorePickerFocus"
      >
        <DialogHeader class="picker-header">
          <DialogTitle>切换学习空间</DialogTitle>
          <DialogDescription class="sr-only"
            >每个空间保留选用时的课程和目标版本。</DialogDescription
          >
          <DialogClose as-child>
            <Button type="button" variant="outline" size="icon-sm" aria-label="关闭" title="关闭">
              <X aria-hidden="true" />
            </Button>
          </DialogClose>
        </DialogHeader>
        <p v-if="loading || busy" role="status">
          {{ loading ? '正在读取课程…' : '正在打开空间…' }}
        </p>
        <p v-if="error" role="alert">{{ error }}</p>
        <div v-if="pending" class="recovery">
          <Button variant="outline" :disabled="busy" @click="checkRequest">查询本次结果</Button>
          <Button :disabled="busy" @click="send(pending)">用原请求重试</Button>
        </div>
        <section v-if="priorSpaces.length" class="space-group" aria-label="我的学习空间">
          <h3>我的学习空间</h3>
          <ul class="options">
            <li
              v-for="space in priorSpaces"
              :key="space.space_id"
              class="choice"
              :aria-current="space.space_id === current?.space_id ? 'true' : undefined"
            >
              <div>
                <strong>{{ space.target_title }}</strong>
                <small>课程 v{{ space.application_version }} · {{ space.textbook_title }}</small>
              </div>
              <Button
                v-if="space.space_id !== current?.space_id"
                size="sm"
                variant="outline"
                :disabled="busy || !!pending"
                :aria-label="`进入空间 ${space.target_title} 课程 v${space.application_version}`"
                @click="enterSpace(space.space_id)"
              >
                进入空间
              </Button>
              <DialogClose v-else as-child>
                <Button size="sm" variant="outline">继续学习</Button>
              </DialogClose>
            </li>
          </ul>
          <Button v-if="nextSpace" variant="ghost" :disabled="loading" @click="load('spaces')">
            更多空间
          </Button>
        </section>
        <section v-if="created && current" class="space-group" aria-label="当前学习空间">
          <h3>当前学习空间</h3>
          <div class="choice" aria-current="true">
            <div>
              <strong>{{ current.target_title }}</strong>
              <small>课程 v{{ current.application_version }} · {{ current.textbook_title }}</small>
            </div>
            <DialogClose as-child><Button size="sm">继续学习</Button></DialogClose>
          </div>
        </section>
        <section
          v-if="available?.length || nextCourse || (!loading && !spaces.length && !current)"
          class="space-group"
          aria-label="可选的新课程版本"
        >
          <h3>可选的新课程版本</h3>
          <p v-if="!available?.length && !nextCourse">当前没有其他可选用的课程版本。</p>
          <ul class="options">
            <li v-for="course in available" :key="course.application_ref.id" class="choice">
              <div>
                <strong>{{ course.target_title }}</strong>
                <small>课程 v{{ course.application_version }} · {{ course.textbook_title }}</small>
              </div>
              <Button
                size="sm"
                :disabled="busy || !!pending"
                :aria-label="`创建空间 ${course.target_title} 课程 v${course.application_version}`"
                @click="selectCourse(course)"
              >
                创建空间
              </Button>
            </li>
          </ul>
          <Button v-if="nextCourse" variant="ghost" :disabled="loading" @click="load('courses')">
            更多课程
          </Button>
        </section>
      </DialogContent>
    </Dialog>
  </section>
</template>

<style scoped>
.student-shell {
  display: flex;
  flex-direction: column;
  height: 100dvh;
  min-height: 27rem;
}
.space-header,
.account-actions,
.recovery,
.choice,
.picker-header {
  display: flex;
  align-items: center;
}
.picker-header :deep(h2) {
  margin: 0;
  font: var(--study-font-title);
}
.space-header {
  box-sizing: border-box;
  flex: 0 0 var(--study-nav-height);
  min-width: 0;
  gap: 1rem;
  padding-inline: 1.25rem;
  border-bottom: 1px solid var(--border);
  background: var(--study-nav-surface);
}
.wordmark {
  flex: none;
  padding-inline-end: 1rem;
  border-inline-end: 1px solid var(--border);
  font: 750 1.125rem/1.15 var(--study-font-family);
  letter-spacing: -0.025em;
}
.space-trigger {
  flex: 0 1 auto;
  justify-content: flex-start;
  min-width: 0;
  max-width: min(26rem, 54vw);
  gap: 0.5rem;
  border-radius: 0.5rem;
  box-shadow: none;
}
.space-trigger[data-current='true'] {
  border-color: color-mix(in srgb, var(--study-nav-selected) 72%, var(--study-nav-ink));
  background: var(--study-nav-selected);
}
.space-trigger[data-current='true']:hover {
  background: color-mix(in srgb, var(--study-nav-selected) 90%, var(--study-nav-ink));
}
.space-name {
  min-width: 0;
  overflow: hidden;
  font-weight: 600;
  text-overflow: ellipsis;
}
.version {
  flex: none;
  padding-inline-start: 0.375rem;
  border-inline-start: 1px solid color-mix(in srgb, currentColor 23%, transparent);
  font: 600 0.6875rem/1.2 var(--study-font-family);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
.account-actions {
  flex: none;
  gap: 0.4375rem;
  margin-inline-start: auto;
}
.account {
  position: relative;
}
.account-trigger,
.header-icon {
  gap: 0.375rem;
  border-radius: 0.5rem;
  box-shadow: none;
}
.account-name {
  max-width: 12rem;
  overflow: hidden;
  text-overflow: ellipsis;
}
.account-menu {
  position: absolute;
  z-index: 2;
  inset: calc(100% + 6px) 0 auto auto;
  padding: 0.375rem;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--background);
}
.first-entry {
  margin: clamp(1rem, 6vw, 5rem) auto;
  padding-inline: 1rem;
}
.first-entry h1 {
  font: var(--study-font-title);
}
.connection {
  padding-inline: 1.75rem;
  background: var(--muted);
}
.connection p,
.space-picker p {
  margin-block: 0.375rem;
}
:global([data-slot='dialog-overlay'].space-picker-overlay) {
  top: var(--study-nav-height);
  background: rgb(58 44 28 / 16%);
}
:global([data-slot='dialog-content'].space-picker) {
  top: calc(var(--study-nav-height) + 6px);
  left: clamp(16px, var(--picker-left), calc(100vw - 488px));
  width: min(472px, calc(100vw - 32px));
  max-width: none;
  max-height: calc(100dvh - var(--study-nav-height) - 22px);
  translate: none;
  gap: 1rem;
  overflow-y: auto;
  padding: 1.25rem;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: none;
}
.picker-header {
  flex-direction: row;
  justify-content: space-between;
  gap: 1rem;
  text-align: start;
}
.choice > button {
  flex: none;
}
.space-group + .space-group {
  padding-top: 1rem;
  border-top: 1px solid var(--border);
}
.space-group h3 {
  margin: 0 0 0.875rem;
  color: var(--muted-foreground);
  font: var(--study-font-meta);
  font-weight: 600;
}
.options {
  display: grid;
  gap: 0.5rem;
  margin: 0;
  padding: 0;
  list-style: none;
}
.choice {
  justify-content: space-between;
  gap: 0.75rem;
  min-height: 70px;
  padding: 0.625rem 0.75rem;
  border-radius: var(--radius);
}
.choice > div {
  min-width: 0;
  overflow-wrap: anywhere;
}
.choice[aria-current='true'] {
  background: var(--study-nav-selected);
}
.choice small {
  display: block;
  margin-top: 0.25rem;
  color: var(--muted-foreground);
  font: var(--study-font-meta);
}
.choice strong {
  font-weight: 600;
}
.recovery {
  gap: 0.75rem;
}
[role='alert'] {
  color: #943f31;
}
@media (max-width: 41rem) {
  .space-header {
    gap: 0.5rem;
    padding-inline: 0.75rem;
  }
  .wordmark {
    padding-inline-end: 0.5rem;
    font-size: 1rem;
  }
  .space-trigger,
  .account-trigger,
  .header-icon {
    height: 2.25rem;
  }
  .space-trigger {
    max-width: none;
    gap: 0.375rem;
    padding-inline: 0.5rem;
  }
  .account-trigger,
  .header-icon {
    width: 2.25rem;
    padding: 0;
  }
  .space-trigger .space-icon,
  .account-trigger .account-name,
  .account-trigger .account-chevron {
    display: none;
  }
}
</style>
