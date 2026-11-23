<script setup lang="ts">
import { ref, watch } from 'vue';
import type { components } from '../../../../../contracts/generated/http/schema';
import { ApiError, get, post } from '../../../shared/api/http';
import type { DomainSession } from '../domain/api';

type Schema = components['schemas'];
type Chapter = { id: string; title: string; revision: number };
const props = defineProps<{
  session: DomainSession;
  target: Schema['TargetView'];
  importId: string;
  chapters: Chapter[];
}>();
const selected = ref<string[]>([]);
const check = ref<Schema['CourseCheckResult']>();
const error = ref('');
const status = ref('');
const busy = ref(false);
const activities = ['explanation', 'question_answer', 'detection', 'free_chat'] as const;
const labels = {
  reading: '阅读',
  explanation: '讲解',
  qa: '答疑',
  practice_feedback: '练习反馈',
  detection: '检测',
  evaluation: '评价',
};
const states = { ready: '就绪', limited: '受限', blocked: '阻止应用' };
watch(
  () => props.target.target_ref,
  () => {
    selected.value = Array.from(new Set(props.target.items.flatMap((item) => item.chapter_refs)));
    check.value = undefined;
    status.value = '';
    error.value = '';
  },
  { immediate: true },
);
watch(selected, () => {
  check.value = undefined;
});

async function inspect() {
  busy.value = true;
  error.value = '';
  status.value = '';
  check.value = undefined;
  try {
    const session = props.session;
    const target = props.target;
    const chosen = props.chapters.filter((chapter) => selected.value.includes(chapter.id));
    const [head, configs, chapters] = await Promise.all([
      get('/api/m1/course-applications/current', {
        session,
        query: { textbook_id: target.textbook_id, target_id: target.target_ref.target_id },
      }),
      Promise.all(
        activities.map(async (activity_type) => {
          try {
            const view = await get('/api/m1/interaction/activity-configs/{activity_type}', {
              session,
              params: { activity_type },
            });
            return view.config_ref;
          } catch (caught) {
            if (caught instanceof ApiError && caught.status === 404) return undefined;
            throw caught;
          }
        }),
      ),
      Promise.all(
        chosen.map(async (chapter) => {
          const content = await get('/api/m1/material-imports/{import_id}/contents', {
            session,
            params: { import_id: props.importId },
            query: { chapter_id: chapter.id },
          });
          return {
            chapter_id: chapter.id,
            revision: chapter.revision,
            content_refs: content.items.flatMap((item) =>
              item.validity === 'current' &&
              typeof item.candidate_id === 'string' &&
              typeof item.candidate_revision === 'number'
                ? [
                    {
                      owner: 'product',
                      type: 'material_candidate',
                      id: item.candidate_id,
                      revision: item.candidate_revision,
                    },
                  ]
                : [],
            ),
          };
        }),
      ),
    ]);
    check.value = (
      await post(
        '/api/m1/course-applications/checks',
        {
          request_id: crypto.randomUUID(),
          textbook_id: target.textbook_id,
          target_ref: target.target_ref,
          expected_application_ref: head.application_ref,
          chapters,
          activity_config_refs: configs.filter(
            (config): config is Schema['Ref'] => config !== undefined,
          ),
        },
        { session },
      )
    ).result;
  } catch (caught) {
    error.value = (caught as Error).message;
  } finally {
    busy.value = false;
  }
}

async function apply() {
  if (!check.value?.can_apply) return;
  busy.value = true;
  error.value = '';
  try {
    const { result } = await post(
      '/api/m1/course-applications/confirmations',
      {
        request_id: crypto.randomUUID(),
        check_ref: check.value.check_ref,
        expected_application_ref: check.value.base_application_ref,
      },
      { session: props.session },
    );
    status.value = result.changed
      ? `课程已应用，更新 ${result.affected_spaces.length} 个空间。`
      : '已经是当前应用。';
    check.value = undefined;
  } catch (caught) {
    error.value = (caught as Error).message;
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <section aria-label="课程应用">
    <h3>课程应用</h3>
    <fieldset :disabled="busy">
      <legend>本次选用章节</legend>
      <label v-for="chapter in chapters" :key="chapter.id">
        <input v-model="selected" type="checkbox" :value="chapter.id" /> {{ chapter.title }}
      </label>
    </fieldset>
    <button type="button" :disabled="busy || !selected.length" @click="inspect">检查课程</button>
    <p v-if="error" role="alert">{{ error }}</p>
    <p v-if="status" role="status">{{ status }}</p>
    <template v-if="check">
      <table>
        <thead>
          <tr>
            <th>适用内容</th>
            <th>用途</th>
            <th>准备情况</th>
            <th>依据与缺项</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(item, index) in check.readiness" :key="index">
            <td>
              {{
                chapters.find((chapter) => chapter.id === item.subject_ref.id)?.title ??
                target.title
              }}
            </td>
            <td>{{ labels[item.purpose] }}</td>
            <td>{{ states[item.status] }}</td>
            <td>{{ item.reasons.map((issue) => issue.message).join(' ') || '已核对' }}</td>
          </tr>
        </tbody>
      </table>
      <button type="button" :disabled="busy || !check.can_apply" @click="apply">确认应用</button>
    </template>
  </section>
</template>
