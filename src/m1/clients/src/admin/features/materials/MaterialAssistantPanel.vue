<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import type { components } from '../../../../../contracts/generated/http/schema';
import { ApiError, get, post, postAccepted } from '../../../shared/api/http';
import ChapterReview from './ChapterReview.vue';
import type { ChapterOption, ReviewItem } from './ChapterReview.vue';
import type { DomainSession } from '../domain/api';
import type { MaterialDetail } from './api';
import MaterialIntakePanel from './MaterialIntakePanel.vue';

type Schema = components['schemas'];
const { material, session } = defineProps<{ material: MaterialDetail; session: DomainSession }>();
const lifecycle = new AbortController();
const history = ref<Schema['MaterialMessageView'][]>([]);
const conversation = ref<HTMLOListElement>();
const draft = ref('');
const file = ref('');
const first = ref(1);
const last = ref(1);
const busy = ref(false);
const notice = ref('');
const error = ref('');
const pending = ref<Schema['MaterialMessageInput']>();
const proposed = ref<ReviewItem[]>([]);
const chapters = ref<ChapterOption[]>([]);
const adoptedChapters = ref<ChapterOption[]>([]);
const previousItems = ref<ReviewItem[]>();
type Focus = { candidate_id: string; body: { title: string } };
const focus = ref<Focus>();
const part = ref('');
const composer = ref<HTMLTextAreaElement>();
const tab = ref<'review' | 'adopted'>('review');
const concerns = ref<string[]>([]);
let lastSeenBatch = '';
const retirements = ref<string[]>([]);
const candidateBatch = ref<Schema['PreviousMaterialBatch']>();
const reference = ref<Schema['PreviousMaterialBatch']>();
const decisionRevision = ref<number>();
const decisionState = ref('');
const completeCandidate = ref(false);
const deciding = ref(false);
const completedRevision = ref(material.content_revision);
const adopted = ref<ReviewItem[]>([]);
const pendingDecision = ref<Schema['DecideMaterialBatch']>();
const params = { import_id: material.textbook.import_id };
let scheduled: ReturnType<typeof setTimeout> | undefined;
const opts = { session, signal: lifecycle.signal };
const draftKey = `material-draft:${session.session_id}:${params.import_id}`;
const requestKey = `${draftKey}:request`;

function saveValue(key: string, value: string) {
  try {
    if (value) sessionStorage.setItem(key, value);
    else sessionStorage.removeItem(key);
  } catch {
    // 浏览器禁用存储时仍保留当前页面的草稿及请求。
  }
}

watch(draft, (value) => saveValue(draftKey, value));
watch([reference, focus, part], () =>
  saveValue(
    `${draftKey}:quote`,
    reference.value
      ? JSON.stringify({ reference: reference.value, focus: focus.value, part: part.value })
      : '',
  ),
);
watch(pending, (command) => saveValue(requestKey, command ? JSON.stringify(command) : ''));

function showError(cause: unknown) {
  if (!lifecycle.signal.aborted)
    error.value = cause instanceof Error ? cause.message : '无法读取教材助手。';
}

async function update() {
  let page = await get('/api/m1/material-imports/{import_id}/messages', { ...opts, params });
  const messages = [...page.items];
  while (page.next_cursor) {
    page = await get('/api/m1/material-imports/{import_id}/messages', {
      ...opts,
      params,
      query: { after_seq: page.last_seq, upper_seq: page.upper_seq },
    });
    messages.push(...page.items);
  }
  const list = conversation.value;
  const follow = !list || list.scrollHeight - list.scrollTop - list.clientHeight < 32;
  const newMessage = messages.at(-1)?.message_id !== history.value.at(-1)?.message_id;
  history.value = messages;
  if (follow && newMessage) {
    await nextTick();
    if (conversation.value) conversation.value.scrollTop = conversation.value.scrollHeight;
  }
  busy.value = Boolean(page.active_request_ref);
  const command = pending.value;
  if (command) {
    const receipt = await get('/api/m1/requests/receipt', {
      ...opts,
      query: {
        action: 'product.converse_material_assistant',
        resource_kind: 'material_import',
        resource_id: params.import_id,
        request_id: command.request_id,
      },
    });
    if (receipt.receipt_state === 'accepted' && draft.value.trim() === command.message) {
      draft.value = '';
    }
    if (
      receipt.receipt_state === 'completed' &&
      receipt.result &&
      'candidate_batch_refs' in receipt.result
    ) {
      const candidate = receipt.result.candidate_batch_refs[0];
      if (candidate) await read(candidate.id);
      notice.value = {
        needs_input: '等待补充材料。',
        failed: '本轮解析失败，可重新发送。',
        cancelled: '本轮已停止。',
        completed: '本轮处理已结束。',
      }[receipt.result.outcome];
      if (draft.value.trim() === command.message) draft.value = '';
      pending.value = undefined;
    }
  }
  const latest = messages
    .flatMap((m) => m.explicit_refs.filter((r) => r.type === 'candidate_batch'))
    .at(-1);
  if (latest && latest.id !== lastSeenBatch) {
    if (candidateBatch.value?.batch_id !== latest.id) await read(latest.id);
    if (decisionState.value === 'adopted') tab.value = 'adopted';
    lastSeenBatch = latest.id;
  }
  if ((busy.value || pending.value) && !lifecycle.signal.aborted) schedule();
}

function schedule() {
  clearTimeout(scheduled);
  scheduled = setTimeout(() => {
    void update().catch((cause: unknown) => {
      showError(cause);
      if ((busy.value || pending.value) && !lifecycle.signal.aborted) schedule();
    });
  }, 1800);
}

async function read(batch: string) {
  const snapshot = await get('/api/m1/material-imports/{import_id}/candidate-batches/{batch_id}', {
    ...opts,
    params: { ...params, batch_id: batch },
  });
  const diff = snapshot.batch.diff_summary as {
    chapters: { chapter_id: string; name: string }[];
    previous_batch?: { batch_id: string };
  };
  previousItems.value = diff.previous_batch
    ? ((
        await get('/api/m1/material-imports/{import_id}/candidate-batches/{batch_id}', {
          ...opts,
          params: { ...params, batch_id: diff.previous_batch.batch_id },
        })
      ).items as unknown as ReviewItem[])
    : undefined;
  proposed.value = snapshot.items as unknown as ReviewItem[];
  chapters.value = diff.chapters.map((c) => ({ id: c.chapter_id, title: c.name }));
  tab.value = 'review';
  const changes = snapshot.batch.write_set;
  retirements.value = Array.isArray(changes)
    ? changes.flatMap((change) =>
        change &&
        typeof change === 'object' &&
        'action' in change &&
        change.action === 'retire' &&
        'title' in change &&
        typeof change.title === 'string'
          ? [change.title]
          : [],
      )
    : [];
  decisionState.value = String(snapshot.batch.decision_state);
  decisionRevision.value =
    typeof snapshot.batch.decision_revision === 'number'
      ? snapshot.batch.decision_revision
      : undefined;
  const coverage = snapshot.batch.coverage;
  const checks = coverage as {
    issues?: string[];
    questions?: string[];
    pages?: { status: string; reason: string }[];
  };
  concerns.value = [
    ...(checks.issues ?? []),
    ...(checks.questions ?? []),
    ...(checks.pages ?? []).filter((p) => p.status === 'unreadable').map((p) => p.reason),
  ];
  completeCandidate.value =
    !!coverage &&
    typeof coverage === 'object' &&
    'complete' in coverage &&
    coverage.complete === true;
  if (typeof snapshot.batch.batch_revision === 'number') {
    candidateBatch.value = { batch_id: batch, batch_revision: snapshot.batch.batch_revision };
  }
}

async function readAdopted() {
  const snapshot = await get('/api/m1/material-imports/{import_id}/contents', {
    ...opts,
    params,
    query: { catalog_only: true },
  });
  adoptedChapters.value = (
    snapshot.chapters as unknown as { chapter_id: string; title: string }[]
  ).map((c) => ({ id: c.chapter_id, title: c.title }));
  completedRevision.value = snapshot.content_revision;
  await loadChapter(adoptedChapter.value || adoptedChapters.value[0]?.id || '');
}

const adoptedChapter = ref('');
let chapterRequest = 0;
async function loadChapter(id: string) {
  const ticket = ++chapterRequest;
  adoptedChapter.value = id;
  adopted.value = [];
  if (!id) return;
  const result = await get('/api/m1/material-imports/{import_id}/contents', {
    ...opts,
    params,
    query: { chapter_id: id },
  });
  if (ticket === chapterRequest) adopted.value = result.items as unknown as ReviewItem[];
}

async function decide(decision: 'adopt' | 'decline') {
  if (!candidateBatch.value || !decisionRevision.value || deciding.value) return;
  const batch = candidateBatch.value;
  deciding.value = true;
  error.value = '';
  const command =
    pendingDecision.value?.decision === decision &&
    pendingDecision.value.batch_ref.batch_id === batch.batch_id
      ? pendingDecision.value
      : {
          request_id: crypto.randomUUID(),
          batch_ref: batch,
          decision,
          expected_revision: decisionRevision.value,
        };
  pendingDecision.value = command;
  try {
    try {
      await post(
        '/api/m1/material-imports/{import_id}/candidate-batches/{batch_id}/decision',
        command,
        {
          ...opts,
          params: { ...params, batch_id: batch.batch_id },
        },
      );
    } catch (cause) {
      const saved = await get('/api/m1/requests/receipt', {
        ...opts,
        query: {
          action: 'product.decide_material_candidate',
          resource_kind: 'material_import',
          resource_id: params.import_id,
          request_id: command.request_id,
        },
      });
      if (saved.receipt_state !== 'completed') throw cause;
    }
    pendingDecision.value = undefined;
    notice.value = decision === 'adopt' ? '已采用。' : '已记录不采用。';
    await Promise.all([read(batch.batch_id), readAdopted()]);
    if (decision === 'adopt') tab.value = 'adopted';
  } catch (cause) {
    if (cause instanceof ApiError && cause.status < 500) pendingDecision.value = undefined;
    showError(cause);
  } finally {
    deciding.value = false;
  }
}

async function correct(item: ReviewItem, block: string) {
  reference.value = { batch_id: item.batch_id, batch_revision: 1 };
  focus.value = { candidate_id: item.candidate_id, body: { title: item.body.title } };
  part.value = block;
  file.value = '';
  await nextTick();
  composer.value?.focus();
}
function clearReference() {
  reference.value = undefined;
  focus.value = undefined;
  part.value = '';
}

async function send(whole = false) {
  if (busy.value) return;
  const value = whole
    ? '请解析整本教材。'
    : (part.value ? `只核对图表 ${part.value}。` : '') + draft.value.trim();
  if (!value) return;
  error.value = '';
  notice.value = '正在处理。';
  busy.value = true;
  const command = pending.value ?? {
    request_id: crypto.randomUUID(),
    message: value,
    previous_batch_ref: whole ? null : (reference.value ?? null),
    focus_candidate: whole ? null : focus.value?.candidate_id,
    selection:
      !whole && file.value
        ? {
            import_id: params.import_id,
            scope: 'batch' as const,
            basis_revision: completedRevision.value,
            source_refs: [
              { source_id: file.value, first_page: first.value, last_page: last.value },
            ],
          }
        : null,
  };
  pending.value = command;
  try {
    await postAccepted('/api/m1/material-imports/{import_id}/messages', command, {
      ...opts,
      params,
    });
    if (!whole) draft.value = '';
    clearReference();
    await update();
  } catch (cause) {
    if (cause instanceof ApiError && cause.status < 500) pending.value = undefined;
    busy.value = false;
    notice.value = '';
    showError(cause);
    schedule();
  }
}

onMounted(() => {
  try {
    draft.value = sessionStorage.getItem(draftKey) ?? '';
    const quote = sessionStorage.getItem(`${draftKey}:quote`);
    if (quote) {
      const saved = JSON.parse(quote) as {
        reference: Schema['PreviousMaterialBatch'];
        focus?: Focus;
        part: string;
      };
      reference.value = saved.reference;
      focus.value = saved.focus;
      part.value = saved.part;
    }
    const stored = sessionStorage.getItem(requestKey);
    if (stored) pending.value = JSON.parse(stored) as Schema['MaterialMessageInput'];
  } catch {
    saveValue(requestKey, '');
  }
  void update().catch(showError);
  void readAdopted().catch(showError);
});
onBeforeUnmount(() => {
  clearTimeout(scheduled);
  lifecycle.abort();
});
</script>

<template>
  <section class="material-assistant editor-panel" aria-label="教材助手">
    <div class="assistant-chat">
      <h3>教材助手</h3>
      <ol v-if="history.length" ref="conversation">
        <li
          v-for="entry in history"
          :key="entry.message_id"
          :class="{ outgoing: entry.role === 'user' }"
        >
          <b>{{ entry.role === 'user' ? '你' : '教材助手' }}</b>
          <p v-for="messagePart in entry.body" :key="messagePart.part_id">{{ messagePart.text }}</p>
          <button
            v-for="item in entry.explicit_refs.filter((ref) => ref.type === 'candidate_batch')"
            :key="item.id"
            type="button"
            @click="read(item.id).catch(showError)"
          >
            核对候选
          </button>
        </li>
      </ol>
      <form class="assistant-compose" @submit.prevent="send()">
        <div v-if="reference">
          引用 · {{ focus?.body.title ?? '这批候选' }} {{ part }}
          <button type="button" @click="clearReference()">移除引用</button>
        </div>
        <label>
          引用原件
          <select v-model="file" :disabled="!!focus">
            <option value="">选择要核对的文件</option>
            <option
              v-for="source in material.sources"
              :key="source.source_ref.id"
              :value="source.source_ref.id"
            >
              {{ source.original_name }}
            </option>
          </select>
        </label>
        <div v-if="file">
          <label>开始页 <input v-model.number="first" type="number" min="1" required /></label>
          <label>结束页 <input v-model.number="last" type="number" :min="first" required /></label>
        </div>
        <label
          >给教材助手发消息 <textarea ref="composer" v-model="draft" maxlength="4096" rows="3" />
        </label>
        <div>
          <button type="submit" :disabled="busy || !draft.trim()">发送</button>
          <button type="button" :disabled="busy" @click="send(true)">解析整本</button>
        </div>
      </form>
      <p v-if="notice" role="status">{{ notice }}</p>
      <p v-else-if="busy" role="status">正在处理上一条消息。</p>
      <p v-if="error" role="alert">{{ error }}</p>
    </div>
    <div class="chapter-work">
      <nav class="editor-tabs" aria-label="章节核对">
        <button type="button" :aria-pressed="tab === 'review'" @click="tab = 'review'">
          核对候选
        </button>
        <button type="button" :aria-pressed="tab === 'adopted'" @click="tab = 'adopted'">
          教材已采用
        </button>
      </nav>
      <section v-if="tab === 'review' && candidateBatch" aria-label="待核对候选">
        <h3>
          {{
            decisionState === 'adopted'
              ? '本批已采用'
              : decisionState === 'declined'
                ? '本批未采用'
                : decisionState === 'superseded'
                  ? '本批已被替代'
                  : '待核对候选'
          }}
        </h3>
        <ul v-if="concerns.length">
          <li v-for="(c, i) in concerns" :key="i">{{ c }}</li>
        </ul>
        <button
          v-if="['pending', 'adopted'].includes(decisionState)"
          type="button"
          :disabled="busy"
          @click="
            clearReference();
            reference = candidateBatch;
            composer?.focus();
          "
        >
          引用这批候选继续修正
        </button>
        <ChapterReview
          :items="proposed"
          :chapters="chapters"
          :previous="previousItems"
          :material="material"
          :session="session"
          :can-correct="!busy && ['pending', 'adopted'].includes(decisionState)"
          @correct="correct"
        />
        <ul v-if="retirements.length">
          <li v-for="title in retirements" :key="title">拟从教材解析结果撤下：{{ title }}</li>
        </ul>
        <div v-if="decisionState === 'pending'" class="editor-footer">
          <button
            type="button"
            class="primary"
            :disabled="deciding || !completeCandidate"
            @click="decide('adopt')"
          >
            采用
          </button>
          <button type="button" :disabled="deciding" @click="decide('decline')">不采用</button>
        </div>
      </section>
      <p v-else-if="tab === 'review'">解析完成后，在这里按章节核对候选。</p>
      <section v-if="tab === 'adopted'" aria-label="已采用内容">
        <h3>教材已采用</h3>
        <ChapterReview
          :items="adopted"
          :chapters="adoptedChapters"
          :material="material"
          :session="session"
          :can-correct="!busy"
          @chapter="
            (id) => {
              if (id !== adoptedChapter) loadChapter(id).catch(showError);
            }
          "
          @correct="correct"
        />
        <h4 v-if="adopted.length">领域入库</h4>
        <MaterialIntakePanel
          v-if="adopted.length"
          :items="adopted"
          :import-id="params.import_id"
          :domain-id="material.textbook.domain_id"
          :session="session"
          @changed="loadChapter(adoptedChapter).catch(showError)"
        />
      </section>
    </div>
  </section>
</template>

<style scoped>
.material-assistant {
  display: grid;
  grid-template-columns: minmax(255px, 0.8fr) minmax(0, 1.6fr);
  gap: 24px;
  align-items: start;
}
.chapter-work {
  min-width: 0;
  border-left: 1px solid var(--el-border-color-light);
  padding-left: 20px;
}
@media (max-width: 900px) {
  .material-assistant {
    grid-template-columns: 1fr;
  }
  .chapter-work {
    border: 0;
    padding: 0;
  }
}

.assistant-chat > ol {
  display: grid;
  gap: 10px;
  max-height: 24rem;
  overflow: auto;
  list-style: none;
  padding: 12px;
  background: var(--el-fill-color-light);
  border-radius: 4px;
}
.assistant-chat li {
  background: white;
  border: 1px solid var(--el-border-color);
  padding: 12px 16px;
  border-radius: 4px;
  width: fit-content;
  max-width: 90%;
  overflow-wrap: anywhere;
}
.material-assistant .outgoing {
  justify-self: end;
  background: var(--admin-selected);
}
.assistant-chat li p {
  white-space: pre-wrap;
  margin: 4px 0;
}
.assistant-compose {
  display: grid;
  gap: 12px;
  margin-top: 12px;
}
.assistant-compose > div {
  display: flex;
  align-items: end;
  gap: 8px;
  flex-wrap: wrap;
}
.assistant-compose textarea {
  width: 100%;
}
</style>
