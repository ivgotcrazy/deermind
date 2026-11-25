<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { ApiError, get, post } from '../../../shared/api/http';
import type { components, operations } from '../../../../../contracts/generated/http/schema';
import { listDomains, listMembers, readMember } from '../domain/api';
import type { DomainRow, DomainSession, SolutionRef, TaskRef } from '../domain/api';

type Schema = components['schemas'];
const { session } = defineProps<{ session: DomainSession }>();
const scope = new AbortController();
const standards: Schema['AspectDefinition'][] = [
  { code: 'independent', label: '独立完成', description: '是否在无本题帮助下完成。' },
  { code: 'understanding', label: '理解与解释', description: '能否说明方法成立的原理。' },
  { code: 'transfer', label: '迁移', description: '能否在变化情境下采用同一方法。' },
  { code: 'retention', label: '保持', description: '能否在规定间隔后再次完成。' },
];
const domains = ref<DomainRow[]>([]);
const domain = ref('');
const tasks = ref<{ ref: TaskRef; name: string }[]>([]);
const rows = ref<Schema['ClaimRow'][] | null>(null);
const selected = ref<Schema['ClaimView'] | null>(null);
const head = ref(0);
const revision = ref(1);
const names = ref<Record<string, string>>({});
const methodIndex = ref(0);
const criterion = ref<Schema['CriterionDraft']>(emptyCriterion());
const associated = ref<string[]>([]);
const aspectCode = ref('independent');
const ruleBasis = ref('');
const requirements = ref('');
const conditions = ref('{"type":"object","properties":{}}');
const defaults = ref('{}');
const title = ref('');
const description = ref('');
const taskId = ref('');
const error = ref('');
const status = ref('');
const busy = ref(false);
const dialog = ref<HTMLDialogElement>();
const basics = ref<HTMLDialogElement>();
const aspectChoices = ref<Schema['AspectDefinition'][]>([]);
const selectedAspects = ref<string[]>([]);
const changeReason = ref('');
const newAspect = ref<Schema['AspectDefinition']>({ code: '', label: '', description: '' });
const editable = computed(() => selected.value?.claim_ref.revision === head.value);
const method = computed(() => selected.value?.definition.methods[methodIndex.value]);
let lastCommand: { payload: string; request: string } | undefined;
let detailRead = 0;

function emptyCriterion(): Schema['CriterionDraft'] {
  return {
    title: '',
    required_inputs: [],
    judgement_basis: '',
    pass_description: '',
    fail_description: '',
    unknown_description: '',
  };
}

function report(cause: unknown) {
  if (!scope.signal.aborted)
    error.value =
      cause instanceof ApiError || cause instanceof Error
        ? cause.message
        : '操作暂时失败，请稍后再试。';
}

async function loadDomain() {
  const id = domain.value;
  detailRead++;
  rows.value = null;
  selected.value = null;
  tasks.value = [];
  taskId.value = '';
  title.value = '';
  description.value = '';
  if (!id) return;
  try {
    const [listed, members] = await Promise.all([
      get('/api/m1/evaluation/claims', { session, signal: scope.signal, query: { domain_id: id } }),
      listMembers(id, 'task', session, scope.signal, '', undefined, 100),
    ]);
    if (domain.value !== id) return;
    rows.value = listed.items;
    tasks.value = members.items.flatMap((item) =>
      item.object_ref.kind === 'task' ? [{ ref: item.object_ref, name: item.name }] : [],
    );
  } catch (cause) {
    report(cause);
  }
}

async function openClaim(row: Schema['ClaimRow'], version = row.claim_ref.revision) {
  const read = ++detailRead;
  const currentMethod = method.value?.method_ref;
  const sameClaim = selected.value?.claim_ref.claim_id === row.claim_ref.claim_id;
  error.value = '';
  try {
    const { claim } = await get('/api/m1/evaluation/claims/{claim_id}', {
      session,
      signal: scope.signal,
      params: { claim_id: row.claim_ref.claim_id },
      query: { revision: version },
    });
    if (read !== detailRead || claim.definition.domain_id !== domain.value) return;
    head.value = row.claim_ref.revision;
    selected.value = claim;
    revision.value = version;
    title.value = claim.definition.title;
    description.value = claim.definition.description;
    methodIndex.value =
      sameClaim && currentMethod
        ? Math.max(
            0,
            claim.definition.methods.findIndex(
              (item) => methodKey(item.method_ref) === methodKey(currentMethod),
            ),
          )
        : 0;
    if (!claim.definition.aspects.some((aspect) => aspect.code === aspectCode.value)) {
      aspectCode.value = claim.definition.aspects[0]?.code ?? '';
    }
    criterion.value = emptyCriterion();
    await Promise.all(
      claim.definition.methods.map(async ({ method_ref: ref }) => {
        const key = methodKey(ref);
        if (names.value[key]) return;
        try {
          const item = await readMember(
            claim.definition.domain_id,
            ref.object_id,
            'solution',
            session,
            scope.signal,
            ref.version,
          );
          names.value[key] = item.content.name;
        } catch {
          names.value[key] = ref.object_id;
        }
      }),
    );
  } catch (cause) {
    if (read === detailRead) report(cause);
  }
}

function methodKey(ref: SolutionRef) {
  return `${ref.object_id}@${ref.version}`;
}

watch(method, (value) => {
  associated.value = value?.criterion_ids.slice() ?? [];
});
watch(
  [method, aspectCode],
  ([value, code]) => {
    const rule = value?.aspect_rules.find((item) => item.aspect_code === code);
    ruleBasis.value = rule?.judgement_basis ?? '';
    requirements.value = rule?.evidence_requirements.join('\n') ?? '';
    conditions.value = JSON.stringify(
      rule?.condition_schema ?? { type: 'object', properties: {} },
      null,
      2,
    );
    defaults.value = JSON.stringify(rule?.default_values ?? {}, null, 2);
  },
  { immediate: true },
);

onMounted(async () => {
  try {
    domains.value = (await listDomains(session, scope.signal)).items;
    domain.value = domains.value[0]?.object_ref.object_id ?? '';
    await loadDomain();
  } catch (cause) {
    report(cause);
  }
});
onBeforeUnmount(() => scope.abort());

type Command = operations['evaluation_save_claim']['requestBody']['content']['application/json'];
type Changes = Pick<Schema['SaveClaim'], 'title' | 'description' | 'aspects'>;
function base() {
  const claim = selected.value;
  if (!claim) throw new Error('请先选择 Claim。');
  return {
    domain_id: claim.definition.domain_id,
    task_ref: claim.definition.task_ref,
    claim_id: claim.claim_ref.claim_id,
    expected_revision: claim.claim_ref.revision,
  };
}

async function submit(command: Command) {
  if (busy.value) return;
  error.value = '';
  status.value = '';
  busy.value = true;
  const payload = JSON.stringify(command);
  if (lastCommand?.payload !== payload) lastCommand = { payload, request: crypto.randomUUID() };
  try {
    const { result } = await post(
      '/api/m1/evaluation/claim-commands',
      { ...command, request_id: lastCommand.request },
      { session, signal: scope.signal },
    );
    const target = domain.value;
    rows.value = (
      await get('/api/m1/evaluation/claims', {
        session,
        signal: scope.signal,
        query: { domain_id: target },
      })
    ).items;
    const row = rows.value.find((item) => item.claim_ref.claim_id === result.claim_ref.claim_id);
    if (row) await openClaim(row);
    lastCommand = undefined;
    dialog.value?.close();
    basics.value?.close();
    status.value = result.changed
      ? `已保存第 ${result.claim_ref.revision} 版。`
      : '内容一致，沿用当前版本。';
  } catch (cause) {
    report(cause);
  } finally {
    busy.value = false;
  }
}

function create() {
  const task = tasks.value.find((entry) => entry.ref.object_id === taskId.value);
  if (!task) return;
  void submit({
    request_id: '',
    action: 'create_claim',
    domain_id: domain.value,
    task_ref: task.ref,
    title: title.value,
    description: description.value,
    aspects: standards,
  });
}

function editBasic() {
  const definition = selected.value?.definition;
  if (!definition) return;
  title.value = definition.title;
  description.value = definition.description;
  const choices = new Map(standards.map((aspect) => [aspect.code, aspect]));
  for (const aspect of definition.aspects) choices.set(aspect.code, aspect);
  aspectChoices.value = [...choices.values()];
  selectedAspects.value = definition.aspects.map((aspect) => aspect.code);
  changeReason.value = '';
  newAspect.value = { code: '', label: '', description: '' };
  error.value = '';
  basics.value?.showModal();
}

function addAspect() {
  const { code, label, description } = newAspect.value;
  if (
    !/^[a-z][a-z0-9_]{0,63}$/.test(code) ||
    !label.trim() ||
    !description.trim() ||
    aspectChoices.value.some((aspect) => aspect.code === code)
  ) {
    error.value = '请填写唯一的英文代码、名称和说明。';
    return;
  }
  aspectChoices.value.push({ code, label, description });
  selectedAspects.value.push(code);
  newAspect.value = { code: '', label: '', description: '' };
  error.value = '';
}

function saveBasic() {
  const claim = selected.value;
  if (!claim) return;
  const previous = claim.definition.aspects.map((aspect) => aspect.code);
  const changed =
    previous.length !== selectedAspects.value.length ||
    previous.some((code) => !selectedAspects.value.includes(code));
  if (!selectedAspects.value.length || (changed && !changeReason.value.trim())) {
    error.value = '请保留至少一个评价方面，并说明调整理由。';
    return;
  }
  const aspects = changed
    ? aspectChoices.value
        .filter(({ code }) => selectedAspects.value.includes(code))
        .map((aspect) => ({ ...aspect, change_reason: changeReason.value.trim() }))
    : claim.definition.aspects;
  const value: Changes = {
    title: title.value,
    description: description.value,
    aspects,
  };
  void submit({ ...base(), ...value, request_id: '', action: 'save_claim' });
}

function editCriterion(item?: Schema['ExecutionCriterion']) {
  criterion.value = item ? { ...item } : emptyCriterion();
  dialog.value?.showModal();
}

function saveCriterion() {
  void submit({ ...base(), request_id: '', action: 'save_criterion', criterion: criterion.value });
}

function removeCriterion(id: string) {
  void submit({ ...base(), request_id: '', action: 'remove_criterion', criterion_id: id });
}

function saveMethod() {
  if (method.value)
    void submit({
      ...base(),
      request_id: '',
      action: 'set_method_criteria',
      method_ref: method.value.method_ref,
      criterion_ids: associated.value,
    });
}

function saveRule() {
  if (!method.value) return;
  try {
    void submit({
      ...base(),
      request_id: '',
      action: 'save_aspect_rule',
      method_ref: method.value.method_ref,
      rule: {
        aspect_code: aspectCode.value,
        judgement_basis: ruleBasis.value,
        evidence_requirements: requirements.value
          .split('\n')
          .map((value) => value.trim())
          .filter(Boolean),
        condition_schema: JSON.parse(conditions.value),
        default_values: JSON.parse(defaults.value),
      },
    });
  } catch {
    error.value = '条件和默认值需要用 JSON 对象填写。';
  }
}
</script>

<template>
  <section class="admin-editor claim-workspace" aria-label="评估管理">
    <h1 class="admin-page-title">评估管理</h1>
    <div class="admin-list-toolbar">
      <label for="claim-domain">领域</label>
      <select id="claim-domain" v-model="domain" :disabled="busy" @change="loadDomain">
        <option value="">请选择领域</option>
        <option
          v-for="item in domains"
          :key="item.object_ref.object_id"
          :value="item.object_ref.object_id"
        >
          {{ item.name }}
        </option>
      </select>
    </div>
    <p v-if="error" role="alert">{{ error }}</p>
    <p v-if="status" role="status">{{ status }}</p>
    <div v-if="rows" class="claim-layout">
      <aside class="editor-panel" aria-label="Claim 列表">
        <h3>Claim 列表</h3>
        <button
          type="button"
          :disabled="busy"
          @click="
            selected = null;
            title = '';
            description = '';
            error = '';
          "
        >
          新建 Claim
        </button>
        <ul v-if="rows.length">
          <li v-for="item in rows" :key="item.claim_ref.claim_id">
            <button
              type="button"
              :aria-pressed="selected?.claim_ref.claim_id === item.claim_ref.claim_id"
              :disabled="busy"
              @click="openClaim(item)"
            >
              {{ item.title }} · v{{ item.claim_ref.revision }}
            </button>
          </li>
        </ul>
        <p v-else>这个领域还没有 Claim。</p>
      </aside>
      <form v-if="!selected" class="claim-fields editor-panel" @submit.prevent="create">
        <h2>新建 Claim</h2>
        <label
          >任务
          <select v-model="taskId" required>
            <option value="">选择任务</option>
            <option v-for="item in tasks" :key="item.ref.object_id" :value="item.ref.object_id">
              {{ item.name }} · v{{ item.ref.version }}
            </option>
          </select></label
        >
        <label>名称 <input v-model="title" required maxlength="160" /></label>
        <label>说明 <textarea v-model="description" required maxlength="4096" /></label>
        <button type="submit" :disabled="busy || !tasks.length">创建 Claim</button>
      </form>
      <div v-else class="claim-fields editor-panel">
        <header class="editor-row claim-heading">
          <h2>{{ selected.definition.title }}</h2>
          <label
            >修订版本
            <select
              v-model="revision"
              :disabled="busy"
              @change="
                openClaim(
                  rows.find((row) => row.claim_ref.claim_id === selected?.claim_ref.claim_id)!,
                  revision,
                )
              "
            >
              <option v-for="value in head" :key="value" :value="value">v{{ value }}</option>
            </select></label
          >
        </header>
        <button v-if="editable" type="button" :disabled="busy" @click="editBasic">
          编辑 Claim 基本信息
        </button>
        <p v-else>正在查看历史版本。</p>
        <details v-if="selected.gaps.length">
          <summary>待补齐 {{ selected.gaps.length }} 项</summary>
          <ul>
            <li v-for="gap in selected.gaps" :key="gap.path">{{ gap.message }}</li>
          </ul>
        </details>
        <section aria-label="判据库" class="claim-section">
          <header class="editor-row">
            <h3>执行判据库</h3>
            <button v-if="editable" type="button" :disabled="busy" @click="editCriterion()">
              添加判据
            </button>
          </header>
          <ul v-if="selected.definition.criteria.length" class="criteria-list">
            <li v-for="item in selected.definition.criteria" :key="item.criterion_id">
              <div class="criterion-content">
                <strong>{{ item.title }}</strong
                ><small>{{ item.judgement_basis }}</small>
              </div>
              <div v-if="editable" class="actions">
                <button type="button" :disabled="busy" @click="editCriterion(item)">编辑</button>
                <button
                  type="button"
                  :disabled="
                    busy ||
                    selected.definition.methods.some((entry) =>
                      entry.criterion_ids.includes(item.criterion_id),
                    )
                  "
                  @click="removeCriterion(item.criterion_id)"
                >
                  移除
                </button>
              </div>
            </li>
          </ul>
          <p v-else>先添加判据，再为方法选择判据。</p>
        </section>
        <section v-if="method" aria-label="方法与评价" class="claim-section">
          <h3>任务方法</h3>
          <nav aria-label="任务方法" class="editor-tabs">
            <button
              v-for="(entry, index) in selected.definition.methods"
              :key="methodKey(entry.method_ref)"
              type="button"
              :aria-pressed="index === methodIndex"
              @click="methodIndex = index"
            >
              {{ names[methodKey(entry.method_ref)] ?? `方法 ${index + 1}` }}
            </button>
          </nav>
          <form class="claim-fields" @submit.prevent="saveMethod">
            <h4>方法执行判据</h4>
            <label v-for="item in selected.definition.criteria" :key="item.criterion_id">
              <input
                v-model="associated"
                type="checkbox"
                :value="item.criterion_id"
                :disabled="!editable"
              />
              {{ item.title }}
            </label>
            <button v-if="editable" type="submit" :disabled="busy">保存方法判据</button>
          </form>
          <form class="claim-fields" @submit.prevent="saveRule">
            <h4>评价方面规则</h4>
            <label
              >评价方面
              <select v-model="aspectCode">
                <option
                  v-for="aspect in selected.definition.aspects"
                  :key="aspect.code"
                  :value="aspect.code"
                >
                  {{ aspect.label }}
                </option>
              </select></label
            >
            <label>判断依据 <textarea v-model="ruleBasis" required :readonly="!editable" /></label>
            <label
              >证据要求（每行一项） <textarea v-model="requirements" :readonly="!editable" />
            </label>
            <details>
              <summary>适用条件</summary>
              <label>条件结构 <textarea v-model="conditions" :readonly="!editable" /></label>
              <label>默认值 <textarea v-model="defaults" :readonly="!editable" /></label>
            </details>
            <button v-if="editable" type="submit" :disabled="busy">保存方面规则</button>
          </form>
        </section>
      </div>
    </div>
    <dialog ref="basics" aria-labelledby="claim-basics-title">
      <form class="claim-fields" @submit.prevent="saveBasic">
        <h2 id="claim-basics-title">编辑 Claim 基本信息</h2>
        <label>名称 <input v-model="title" required maxlength="160" /></label>
        <label>说明 <textarea v-model="description" required maxlength="4096" /></label>
        <fieldset class="claim-fields">
          <legend>评价方面</legend>
          <label v-for="aspect in aspectChoices" :key="aspect.code">
            <input v-model="selectedAspects" type="checkbox" :value="aspect.code" />
            {{ aspect.label }}
          </label>
        </fieldset>
        <details>
          <summary>新增评价方面</summary>
          <div class="claim-fields">
            <label>英文代码 <input v-model="newAspect.code" maxlength="64" /></label>
            <label>方面名称 <input v-model="newAspect.label" maxlength="160" /></label>
            <label>方面说明 <textarea v-model="newAspect.description" maxlength="4096" /></label>
            <button type="button" @click="addAspect">添加</button>
          </div>
        </details>
        <label>调整理由 <textarea v-model="changeReason" maxlength="4096" /></label>
        <p v-if="error" role="alert">{{ error }}</p>
        <div class="actions">
          <button type="button" :disabled="busy" @click="basics?.close()">取消</button>
          <button type="submit" :disabled="busy">保存基本信息</button>
        </div>
      </form>
    </dialog>
    <dialog ref="dialog" aria-labelledby="criterion-title">
      <form class="claim-fields" @submit.prevent="saveCriterion">
        <h2 id="criterion-title">{{ criterion.criterion_id ? '编辑判据' : '添加判据' }}</h2>
        <label>名称 <input v-model="criterion.title" required maxlength="160" /></label>
        <label
          >所需材料（每行一项）
          <textarea
            :value="criterion.required_inputs.join('\n')"
            @change="
              criterion.required_inputs = ($event.target as HTMLTextAreaElement).value
                .split('\n')
                .map((value) => value.trim())
                .filter(Boolean)
            "
          />
        </label>
        <label>判断依据 <textarea v-model="criterion.judgement_basis" required /></label>
        <label>符合时 <textarea v-model="criterion.pass_description" required /></label>
        <label>不符合时 <textarea v-model="criterion.fail_description" required /></label>
        <label>证据不足时 <textarea v-model="criterion.unknown_description" required /></label>
        <p v-if="error" role="alert">{{ error }}</p>
        <div class="actions">
          <button type="button" :disabled="busy" @click="dialog?.close()">取消</button>
          <button type="submit" :disabled="busy">保存判据</button>
        </div>
      </form>
    </dialog>
  </section>
</template>

<style scoped>
.claim-layout {
  display: grid;
  grid-template-columns: minmax(180px, 24%) minmax(0, 1fr);
  align-items: start;
  gap: 16px;
}
.claim-layout aside ul {
  padding: 0;
  margin: 12px 0 0;
  list-style: none;
  max-height: 55vh;
  overflow: auto;
}
.claim-layout aside li + li {
  border-top: 1px solid var(--el-border-color-light);
}
.claim-layout aside li button {
  width: 100%;
  text-align: start;
}
.claim-fields {
  display: grid;
  gap: 12px;
  align-content: start;
}
.claim-fields > button {
  justify-self: start;
}
.claim-section {
  border-top: 1px solid var(--el-border-color);
  padding-top: 16px;
}
.claim-section form {
  padding: 16px 0;
}
.claim-heading {
  align-items: end;
  flex-wrap: wrap;
}
.claim-heading label {
  min-width: 7rem;
}
.criteria-list {
  margin: 12px 0 0;
  padding: 0;
  border-top: 1px solid var(--el-border-color-light);
  list-style: none;
}
.criteria-list li {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 8px 16px;
  padding: 12px 0;
  border-bottom: 1px solid var(--el-border-color-light);
}
.criterion-content {
  display: grid;
  flex: 1 1 15rem;
  gap: 4px;
  min-width: 0;
  overflow-wrap: anywhere;
}
.actions {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}
.claim-section small {
  overflow-wrap: anywhere;
}
@media (max-width: 840px) {
  .claim-layout {
    grid-template-columns: 1fr;
  }
}
</style>
