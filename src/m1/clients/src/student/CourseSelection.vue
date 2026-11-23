<script setup lang="ts">
import { ref } from 'vue';
import type { components } from '../../../contracts/generated/http/schema';
import { get, post } from '../shared/api/http';
import type { Realtime } from '../shared/realtime/client';
import LearningWorkspace from './layouts/LearningWorkspace.vue';

type Schema = components['schemas'];
const props = defineProps<{
  realtime: Pick<Realtime, 'watch'>;
  session: Pick<Schema['SessionView'], 'session_id' | 'csrf_token'> & {
    account: Pick<Schema['SessionView']['account'], 'account_id'>;
  };
}>();
const courses = ref<Schema['CourseOption'][]>();
const spaces = ref<Schema['SpaceRow'][]>([]);
const opened = ref<Schema['SpaceWorkspace']>();
const error = ref('');
const busy = ref(false);
const next = ref<string>();

async function load(cursor?: string) {
  error.value = '';
  try {
    const session = props.session;
    const [options, existing] = await Promise.all([
      get('/api/m1/course-options', { session, query: { cursor } }),
      get('/api/m1/learning-spaces', { session }),
    ]);
    courses.value = cursor ? [...(courses.value ?? []), ...options.items] : options.items;
    next.value = options.next_cursor ?? undefined;
    spaces.value = existing.items;
  } catch (caught) {
    error.value = (caught as Error).message;
  }
}
function reflectSpace(space?: string) {
  const url = new URL(window.location.href);
  if (space) url.searchParams.set('space', space);
  else url.searchParams.delete('space');
  window.history.replaceState(window.history.state, '', url);
}

async function restoreWorkspace(space: string) {
  busy.value = true;
  try {
    opened.value = await get('/api/m1/learning-spaces/{space_id}/workspace', {
      session: props.session,
      params: { space_id: space },
    });
  } catch {
    reflectSpace();
    await load();
  } finally {
    busy.value = false;
  }
}

const savedSpace = new URL(window.location.href).searchParams.get('space');
if (savedSpace) void restoreWorkspace(savedSpace);
else void load();

async function open(command: Schema['CreateSpace'] | Schema['EnterSpace']) {
  busy.value = true;
  error.value = '';
  try {
    opened.value = (
      await post('/api/m1/learning-spaces/open', command, { session: props.session })
    ).result;
    reflectSpace(opened.value.space.space_id);
  } catch (caught) {
    error.value = (caught as Error).message;
  } finally {
    busy.value = false;
  }
}

function selectCourse(course: Schema['CourseOption']) {
  return open({
    request_id: crypto.randomUUID(),
    action: 'create',
    textbook_id: course.textbook_id,
    target_id: course.target_ref.target_id,
    expected_application_ref: course.application_ref,
  });
}

function enterSpace(space: Schema['SpaceRow']) {
  return open({ request_id: crypto.randomUUID(), action: 'enter', space_id: space.space_id });
}
</script>

<template>
  <section aria-label="学生学习空间">
    <p v-if="error" role="alert">{{ error }}</p>
    <template v-if="!opened">
      <h2>选择教材和目标</h2>
      <p v-if="courses && !courses.length">还没有可以选用的组合。</p>
      <ul v-if="courses?.length">
        <li v-for="course in courses" :key="course.application_ref.id">
          <button type="button" :disabled="busy" @click="selectCourse(course)">
            {{ course.textbook_title }} · {{ course.target_title }}
          </button>
        </li>
      </ul>
      <button v-if="next" type="button" :disabled="busy" @click="load(next)">更多组合</button>
      <template v-if="spaces.length">
        <h2>我的学习空间</h2>
        <ul>
          <li v-for="space in spaces" :key="space.space_id">
            <button type="button" :disabled="busy" @click="enterSpace(space)">
              {{ space.textbook_title }} · {{ space.target_title }}
            </button>
          </li>
        </ul>
      </template>
    </template>
    <template v-else>
      <button
        type="button"
        @click="
          opened = undefined;
          reflectSpace();
          load();
        "
      >
        返回课程列表
      </button>
      <LearningWorkspace
        :key="opened.space.space_id"
        :session="session"
        :account-id="session.account.account_id"
        :realtime="realtime"
        :opened="opened"
      />
    </template>
  </section>
</template>
