<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue';
import { ApiError } from '../../../shared/api/http';
import { readKCPathReceipt, saveKCPath } from './api';
import type {
  ConfirmKCPathRequest,
  DomainSession,
  KnowledgeUse,
  MemberRef,
  TaskDependencies,
} from './api';

const props = defineProps<{
  dependencies: TaskDependencies;
  caption: (reference: MemberRef) => string;
  domainId: string;
  session: DomainSession;
  disabled: boolean;
}>();
const emit = defineEmits<{ changed: [] }>();
const signal = new AbortController();
const task = props.dependencies.task_ref;
const storageKey = `deermind-kc-path:${props.session.account.account_id}:${props.domainId}:${task.object_id}:v${task.version}`;
const form = ref<HTMLDialogElement>();
const use = ref<KnowledgeUse>();
const observed = ref('');
const examples = ref('');
const judgment = ref<'direct' | 'insufficient'>('direct');
const reason = ref('');
const busy = ref(false);
const message = ref('');
const issues = ref<string[]>([]);
const pending = ref<ConfirmKCPathRequest>();
const canRetry = ref(false);
const storageFailed = ref(false);

function matchingPaths(entry: KnowledgeUse) {
  return props.dependencies.kc_test_paths.filter(
    (path) =>
      path.kc_ref.object_id === entry.kc_ref.object_id &&
      path.kc_ref.version === entry.kc_ref.version &&
      path.solution_ref.object_id === entry.method_ref.object_id &&
      path.solution_ref.version === entry.method_ref.version,
  );
}

function open(entry: KnowledgeUse) {
  use.value = entry;
  observed.value = '';
  examples.value = '';
  judgment.value = 'direct';
  reason.value = '';
  message.value = '';
  issues.value = [];
  form.value?.showModal();
}

function remember(value?: ConfirmKCPathRequest) {
  pending.value = value;
  try {
    if (value) sessionStorage.setItem(storageKey, JSON.stringify(value));
    else sessionStorage.removeItem(storageKey);
  } catch {
    storageFailed.value = true;
  }
}

function confirmed() {
  remember();
  form.value?.close();
  message.value = '检验路径已确认。';
  emit('changed');
}

async function recover() {
  const existing = pending.value;
  if (!existing || busy.value) return;
  busy.value = true;
  canRetry.value = false;
  try {
    const receipt = await readKCPathReceipt(
      props.domainId,
      existing.request_id,
      props.session,
      signal.signal,
    );
    if (
      receipt.receipt_state === 'completed' &&
      receipt.result &&
      'confirmation_ref' in receipt.result
    ) {
      confirmed();
    } else if (receipt.receipt_state === 'rejected' && receipt.error) {
      message.value = receipt.error.message;
      issues.value = receipt.error.issues
        .filter((issue) => issue.code !== 'basis')
        .map((issue) => issue.message);
      remember();
      form.value?.close();
    } else if (receipt.receipt_state === 'not_found') {
      canRetry.value = true;
      message.value = '未查到结果，可以用原请求重试。';
    } else {
      message.value = '暂时无法确认保存结果。';
    }
  } catch (error) {
    if (!signal.signal.aborted)
      message.value = error instanceof Error ? error.message : '读取收据失败。';
  } finally {
    busy.value = false;
  }
}

async function submit(body?: ConfirmKCPathRequest) {
  if (busy.value) return;
  if (!body) {
    const entry = use.value;
    const insufficient = examples.value
      .split('\n')
      .map((line) => line.trim())
      .filter(Boolean);
    const why = reason.value.trim();
    if (
      !entry ||
      !observed.value.trim() ||
      !insufficient.length ||
      (judgment.value === 'insufficient' && !why)
    )
      return;
    body = {
      request_id: crypto.randomUUID(),
      kc_ref: entry.kc_ref,
      task_ref: task,
      solution_ref: entry.method_ref,
      observable_behavior: observed.value.trim(),
      insufficient_examples: insufficient,
      not_direct_reason: judgment.value === 'insufficient' ? why : null,
    };
  }
  busy.value = true;
  message.value = '';
  issues.value = [];
  canRetry.value = false;
  remember(body);
  try {
    await saveKCPath(props.domainId, body, props.session, signal.signal);
    confirmed();
  } catch (error) {
    if (error instanceof ApiError && error.status < 500 && error.code !== 'not_ready') {
      remember();
      message.value = error.message;
    } else {
      busy.value = false;
      await recover();
    }
  } finally {
    busy.value = false;
  }
}

onMounted(() => {
  try {
    const stored = sessionStorage.getItem(storageKey);
    if (stored) {
      pending.value = JSON.parse(stored) as ConfirmKCPathRequest;
      void recover();
    }
  } catch {
    storageFailed.value = true;
  }
});
onBeforeUnmount(() => signal.abort());
</script>

<template>
  <section v-if="dependencies.kc_sources.length" class="paths" aria-label="知识成分及检验路径">
    <h5>知识成分及来源方法</h5>
    <p v-if="message && !form?.open" role="status">{{ message }}</p>
    <ul v-if="issues.length && !form?.open" aria-label="检验依据不足">
      <li v-for="(issue, index) in issues" :key="index">{{ issue }}</li>
    </ul>
    <button v-if="pending" type="button" :disabled="busy || disabled" @click="form?.showModal()">
      核对保存结果
    </button>
    <ul class="groups">
      <li v-for="group in dependencies.kc_sources" :key="group.kc_id">
        <ul>
          <li v-for="entry in group.uses" :key="entry.method_ref.object_id" class="item">
            <span>{{ caption(entry.kc_ref) }}（{{ caption(entry.method_ref) }}）</span>
            <template v-for="path in matchingPaths(entry)" :key="path.confirmation_ref.id">
              <details>
                <summary>查看已确认的检验依据</summary>
                <dl>
                  <dt>应观察到的表现</dt>
                  <dd>{{ path.observable_behavior }}</dd>
                  <dt>不足示例</dt>
                  <dd>
                    <ul>
                      <li v-for="example in path.insufficient_examples" :key="example">
                        {{ example }}
                      </li>
                    </ul>
                  </dd>
                  <dt>依据编号</dt>
                  <dd>{{ path.basis_ref.id }}</dd>
                  <dt>确认人和时间</dt>
                  <dd>
                    {{ path.confirmed_by.id }} ·
                    {{ new Date(path.confirmed_at).toLocaleString('zh-CN') }}
                  </dd>
                </dl>
              </details>
            </template>
            <template v-if="!matchingPaths(entry).length">
              <small>仅引用，待确认</small>
              <button type="button" :disabled="busy || disabled || !!pending" @click="open(entry)">
                核对检验路径
              </button>
            </template>
          </li>
        </ul>
      </li>
    </ul>

    <dialog ref="form" aria-labelledby="kc-path-title" @cancel.prevent="!busy && form?.close()">
      <form @submit.prevent="submit()">
        <h3 id="kc-path-title">{{ pending ? '核对保存结果' : '核对直接检验路径' }}</h3>
        <template v-if="!pending">
          <p v-if="use">{{ caption(use.kc_ref) }}（{{ caption(use.method_ref) }}）</p>
          <label>应观察到的表现<textarea v-model="observed" required rows="3" /></label>
          <label>不足示例（每行一条）<textarea v-model="examples" required rows="2" /></label>
          <label>
            核对结论
            <select v-model="judgment">
              <option value="direct">能直接检验</option>
              <option value="insufficient">检验依据不足</option>
            </select>
          </label>
          <label v-if="judgment === 'insufficient'"
            >不足原因<textarea v-model="reason" required rows="2" />
          </label>
        </template>
        <p v-if="message" role="alert">{{ message }}</p>
        <p v-if="storageFailed && pending">浏览器无法暂存请求，请在刷新前核对。</p>
        <div class="actions">
          <button type="button" :disabled="busy" @click="form?.close()">
            {{ pending ? '关闭' : '取消' }}
          </button>
          <button v-if="!pending" type="submit" class="primary" :disabled="busy">
            {{ judgment === 'direct' ? '保存确认' : '记录不足' }}
          </button>
          <template v-else>
            <button type="button" :disabled="busy" @click="recover">查询保存结果</button>
            <button v-if="canRetry" type="button" :disabled="busy" @click="submit(pending)">
              用原请求重试
            </button>
          </template>
        </div>
      </form>
    </dialog>
  </section>
</template>

<style scoped>
.paths,
.item,
form,
label {
  display: grid;
  gap: 0.45rem;
}
h5,
p,
dl,
dd,
ul {
  margin: 0;
}
.groups,
.groups > li > ul {
  list-style: none;
  padding: 0;
}
.item {
  margin-block: 0.55rem;
}
.item button {
  justify-self: start;
}
.item details {
  padding-inline-start: 0.5rem;
}
dt {
  font-weight: 600;
  margin-top: 0.35rem;
}
summary {
  cursor: pointer;
  color: var(--el-color-primary);
}
small {
  color: var(--el-text-color-secondary);
}
.actions {
  display: flex;
  gap: 0.55rem;
  justify-content: flex-end;
}
</style>
