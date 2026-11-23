<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import type { components, operations } from '../../../../../contracts/generated/http/schema';
import { ApiError, get, put } from '../../../shared/api/http';

type Schema = components['schemas'];
type Blueprint = NonNullable<Schema['ConfigView']['definition']['blueprint']>;
type Activity = Blueprint['activity_type'];
type Binding = Schema['LocalBinding'];
type Rule = Schema['BoundRule']['definition'];
type Strategy = Schema['BoundStrategy']['definition'];
type Command = operations['interaction_save_config']['requestBody']['content']['application/json'];
type Change = Command extends infer C
  ? C extends Command
    ? Omit<C, 'request_id' | 'expected_revision'>
    : never
  : never;

const props = defineProps<{ session: Pick<Schema['SessionView'], 'session_id' | 'csrf_token'> }>();
const labels: Record<Activity, string> = {
  explanation: '讲解',
  question_answer: '答疑',
  detection: '检测',
  free_chat: '自由交谈',
};
const stages: Record<Activity, string[]> = {
  explanation: ['确认讲解内容', '讲解与互动', '确认理解'],
  question_answer: ['澄清问题', '回答问题', '确认疑问已解决'],
  detection: ['准备并确认题单', '本轮作答', '结束检测轮'],
  free_chat: ['回应学生', '确认是否进入学习活动'],
};
const path = '/api/m1/interaction/activity-configs/{activity_type}';
const activity = ref<Activity>('explanation');
const view = ref<Schema['ConfigView']>();
const blueprint = ref<Blueprint>();
const binding = ref<Schema['BindingDefinition']>();
const error = ref('');
const status = ref('');
const busy = ref(false);
const node = ref('start');
const rule = ref<Rule>();
const strategy = ref<Strategy>();
const ruleRef = ref<Schema['Ref'] | null>(null);
const strategyRef = ref<Schema['Ref'] | null>(null);
const selected = computed(() =>
  blueprint.value?.nodes.find((entry) => entry.node_id === node.value),
);
const local = computed(
  () =>
    binding.value && (node.value === '' ? binding.value.activity : binding.value.nodes[node.value]),
);

function emptyBinding(): Binding {
  return { rule_ids: [], strategy_ids: [] };
}

function draft(type: Activity): Blueprint {
  const names = ['开始', ...stages[type], '结束'];
  const ids = names.map((_, n) =>
    n === 0 ? 'start' : n === names.length - 1 ? 'end' : `step-${n}`,
  );
  return {
    activity_type: type,
    nodes: names.map((name, n) => ({
      node_id: ids[n]!,
      name,
      purpose: name,
      required_inputs: [],
      execution_guidance: `完成${name}后，按转移条件继续。`,
      outputs: [],
      allowed_actions: n === names.length - 1 ? ['finish'] : ['wait_input'],
      fallback: { action: 'wait_input', explanation: '条件不足时等待学生继续。' },
    })),
    transitions: ids.slice(0, -1).map((source_node_id, n) => ({
      transition_id: `step-to-${n + 1}`,
      source_node_id,
      target_node_id: ids[n + 1]!,
      order: 1,
      when: 'on_input',
      condition_text: '当前节点已完成',
      required_facts: [],
      evidence_required: false,
    })),
  };
}

async function load() {
  const type = activity.value;
  try {
    const current = await get(path, { session: props.session, params: { activity_type: type } });
    if (type !== activity.value) return;
    view.value = current;
    blueprint.value = current.definition.blueprint;
    binding.value = current.definition.binding;
  } catch (caught) {
    if (type !== activity.value) return;
    if (caught instanceof ApiError && caught.status === 404) {
      view.value = undefined;
      blueprint.value = draft(type);
      binding.value = undefined;
      return;
    }
    error.value = (caught as Error).message;
  }
}

watch(
  activity,
  () => {
    view.value = undefined;
    blueprint.value = undefined;
    binding.value = undefined;
    rule.value = undefined;
    strategy.value = undefined;
    node.value = 'start';
    error.value = '';
    status.value = '';
    void load();
  },
  { immediate: true },
);

async function save(change: Change) {
  busy.value = true;
  error.value = '';
  status.value = '';
  try {
    const { result } = await put(
      path,
      {
        ...change,
        request_id: crypto.randomUUID(),
        expected_revision: view.value?.config_ref.revision ?? null,
      },
      { session: props.session, params: { activity_type: activity.value } },
    );
    await load();
    rule.value = undefined;
    strategy.value = undefined;
    status.value = `已保存修订 ${result.config_ref.revision}`;
  } catch (caught) {
    error.value = (caught as Error).message;
  } finally {
    busy.value = false;
  }
}

function selectNode(id: string) {
  node.value = id;
  if (id && binding.value) binding.value.nodes[id] ??= emptyBinding();
}

function addNode() {
  const data = blueprint.value;
  if (!data) return;
  const start = data.nodes.find((item) => item.node_id === 'start');
  if (!start) return;
  const id = `node-${crypto.randomUUID()}`;
  data.nodes.splice(data.nodes.length - 1, 0, {
    ...start,
    required_inputs: [],
    outputs: [],
    allowed_actions: ['wait_input'],
    fallback: { ...start.fallback },

    node_id: id,
    name: '新节点',
  });
  selectNode(id);
}

function addTransition() {
  const data = blueprint.value;
  if (!data || !node.value || node.value === 'end') return;
  const order =
    Math.max(
      0,
      ...data.transitions
        .filter((item) => item.source_node_id === node.value)
        .map((item) => item.order),
    ) + 1;
  data.transitions.push({
    transition_id: `edge-${crypto.randomUUID()}`,
    source_node_id: node.value,
    target_node_id: 'end',
    order,
    when: 'on_input',
    required_facts: [],
    evidence_required: false,
  });
}

function editRule(entry?: Schema['BoundRule']) {
  ruleRef.value = entry?.ref ?? null;
  rule.value = entry
    ? { ...entry.definition }
    : {
        activity_type: activity.value,
        name: '',
        applies_when: '活动中',
        requirement: '',
        basis: '活动配置',
        limitations: [],
        enabled: true,
      };
}

function editStrategy(entry?: Schema['BoundStrategy']) {
  strategyRef.value = entry?.ref ?? null;
  strategy.value = entry
    ? { ...entry.definition }
    : {
        activity_type: activity.value,
        name: '',
        purpose: '',
        applicability: '',
        materials: [],
        approach: '',
        adaptation: '按学生回应调整',
        finish_conditions: '达到本节点目的',
        enabled: true,
      };
}

const triggers = {
  on_enter: '进入节点',
  on_input: '收到输入',
  after_reply: '回复后',
  on_child_return: '子活动返回',
  on_result: '结果可用',
  on_control: '收到操作',
} as const;
const actions = {
  reply: '回复',
  clarify: '澄清',
  wait_input: '等待输入',
  start_child: '开始子活动',
  prepare_detection: '准备检测',
  start_detection: '开始检测',
  continue_detection: '继续检测',
  record_answer: '记录作答',
  return_parent: '返回上层',
  pause: '暂停',
  finish: '结束',
  switch: '切换',
} as const;
</script>

<template>
  <section aria-label="交互活动">
    <h2>交互活动</h2>
    <nav aria-label="活动类型">
      <button
        v-for="(label, type) in labels"
        :key="type"
        type="button"
        :disabled="busy"
        :aria-pressed="activity === type"
        @click="activity = type"
      >
        {{ label }}
      </button>
    </nav>
    <p v-if="error" role="alert">{{ error }}</p>
    <p v-if="status" role="status">{{ status }}</p>
    <template v-if="blueprint">
      <p v-if="!view">首次保存蓝图时会建立空规则与策略绑定。</p>
      <ul v-else-if="view.gaps.length" aria-label="配置缺项">
        <li v-for="gap in view.gaps" :key="gap.path">{{ gap.message }}</li>
      </ul>
      <section aria-label="活动蓝图">
        <h3>活动蓝图</h3>
        <div class="flow">
          <div v-for="entry in blueprint.nodes" :key="entry.node_id" class="flow-node">
            <button
              type="button"
              :aria-pressed="node === entry.node_id"
              @click="selectNode(entry.node_id)"
            >
              {{ entry.name }}
            </button>
            <span
              v-for="edge in blueprint.transitions.filter(
                (item) => item.source_node_id === entry.node_id,
              )"
              :key="edge.transition_id"
              >→
              {{
                blueprint.nodes.find((target) => target.node_id === edge.target_node_id)?.name
              }}</span
            >
          </div>
        </div>
        <form
          @submit.prevent="
            save({
              config_kind: 'blueprint',
              config_ref: view?.definition.blueprint_ref ?? null,
              definition: blueprint!,
            })
          "
        >
          <fieldset :disabled="busy">
            <div v-if="selected" class="fields">
              <label>节点名称 <input v-model="selected.name" required /></label>
              <label>目的 <input v-model="selected.purpose" required /></label>
              <label>执行说明 <textarea v-model="selected.execution_guidance" required /></label>
              <label
                >无法继续时 <textarea v-model="selected.fallback.explanation" required />
              </label>
              <label
                >允许动作
                <select v-model="selected.allowed_actions" multiple>
                  <option v-for="(label, action) in actions" :key="action" :value="action">
                    {{ label }}
                  </option>
                </select></label
              >
              <button
                v-if="node !== 'start' && node !== 'end'"
                type="button"
                @click="
                  blueprint.nodes = blueprint.nodes.filter((item) => item.node_id !== node);
                  blueprint.transitions = blueprint.transitions.filter(
                    (item) => item.source_node_id !== node && item.target_node_id !== node,
                  );
                  selectNode('start');
                "
              >
                删除节点
              </button>
            </div>
            <div
              v-for="edge in blueprint.transitions.filter((item) => item.source_node_id === node)"
              :key="edge.transition_id"
              class="fields"
            >
              <label
                >转移时机
                <select v-model="edge.when">
                  <option v-for="(label, when) in triggers" :key="when" :value="when">
                    {{ label }}
                  </option>
                </select></label
              >
              <label>转移条件 <input v-model="edge.condition_text" /></label>
              <label
                >下一节点
                <select v-model="edge.target_node_id">
                  <option
                    v-for="target in blueprint.nodes.filter((item) => item.node_id !== 'start')"
                    :key="target.node_id"
                    :value="target.node_id"
                  >
                    {{ target.name }}
                  </option>
                </select></label
              >
              <button
                type="button"
                @click="
                  blueprint.transitions = blueprint.transitions.filter((item) => item !== edge)
                "
              >
                移除此转移
              </button>
            </div>
            <div class="actions">
              <button type="button" @click="addNode">添加节点</button>
              <button v-if="node && node !== 'end'" type="button" @click="addTransition">
                添加转移
              </button>
              <button type="submit">保存蓝图</button>
            </div>
          </fieldset>
        </form>
      </section>
      <template v-if="view && binding">
        <section>
          <h3>规则与推荐策略</h3>
          <div class="actions">
            <button type="button" :disabled="busy" @click="editRule()">新建规则</button>
            <button type="button" :disabled="busy" @click="editStrategy()">新建策略</button>
          </div>
          <div class="fields">
            <button
              v-for="entry in view.definition.rules"
              :key="entry.ref.id"
              type="button"
              @click="editRule(entry)"
            >
              {{ entry.definition.name }}
            </button>
            <button
              v-for="entry in view.definition.strategies"
              :key="entry.ref.id"
              type="button"
              @click="editStrategy(entry)"
            >
              {{ entry.definition.name }}
            </button>
          </div>
          <form
            v-if="rule"
            class="fields"
            @submit.prevent="save({ config_kind: 'rule', config_ref: ruleRef, definition: rule! })"
          >
            <label>规则名称 <input v-model="rule.name" required /></label>
            <label>生效条件 <input v-model="rule.applies_when" required /></label>
            <label>规则内容 <textarea v-model="rule.requirement" required /></label>
            <label><input v-model="rule.enabled" type="checkbox" /> 启用规则</label>
            <button type="submit" :disabled="busy">保存规则</button>
          </form>
          <form
            v-if="strategy"
            class="fields"
            @submit.prevent="
              save({ config_kind: 'strategy', config_ref: strategyRef, definition: strategy! })
            "
          >
            <label>策略名称 <input v-model="strategy.name" required /></label>
            <label>教学目的 <input v-model="strategy.purpose" required /></label>
            <label>适用情况 <input v-model="strategy.applicability" required /></label>
            <label>建议做法 <textarea v-model="strategy.approach" required /></label>
            <label><input v-model="strategy.enabled" type="checkbox" /> 启用推荐策略</label>
            <button type="submit" :disabled="busy">保存策略</button>
          </form>
          <form
            @submit.prevent="
              save({
                config_kind: 'binding',
                config_ref: view.definition.binding_ref,
                definition: binding,
              })
            "
          >
            <fieldset :disabled="busy">
              <legend>规则与策略的作用范围</legend>
              <label
                >配置位置
                <select
                  :value="node"
                  @change="selectNode(($event.target as HTMLSelectElement).value)"
                >
                  <option value="">活动级</option>
                  <option
                    v-for="entry in blueprint.nodes"
                    :key="entry.node_id"
                    :value="entry.node_id"
                  >
                    {{ entry.name }}
                  </option>
                </select></label
              >
              <div v-if="local" class="fields">
                <label v-for="entry in view.definition.rules" :key="entry.ref.id">
                  <input v-model="local.rule_ids" type="checkbox" :value="entry.ref.id" />
                  {{ entry.definition.name }}
                </label>
                <label v-for="entry in view.definition.strategies" :key="entry.ref.id">
                  <input v-model="local.strategy_ids" type="checkbox" :value="entry.ref.id" />
                  {{ entry.definition.name }}（推荐）
                </label>
              </div>
              <button type="submit">保存作用范围</button>
            </fieldset>
          </form>
        </section>
      </template>
    </template>
  </section>
</template>

<style scoped>
.flow,
.actions,
.fields {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  align-items: center;
}
.flow {
  margin-block: 0.75rem;
}
.flow-node {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}
.fields {
  margin-block: 0.75rem;
}
.fields label {
  display: grid;
  gap: 0.25rem;
}
</style>
