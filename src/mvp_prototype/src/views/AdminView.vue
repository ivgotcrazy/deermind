<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { spaces } from '../data';
import { state, current, notify, audit, correctIssue, importExam } from '../store';
import Icon from '../components/Icon.vue';
import Modal from '../components/Modal.vue';
const route = useRoute();
const router = useRouter();
const page = computed(() => String(route.params.page || 'dashboard'));
const item = computed(current);
const space = computed(() => spaces[state.space]);
const modal = ref('');
const checked = ref(false);
const chapterName = ref<string>(space.value.chapter);
const proposal = computed({
  get: () =>
    item.value.proposal ||
    (state.space === 'school'
      ? '补充已知部分求整体的适用任务条件与解法边界。'
      : '补充整除与余数的适用任务条件与解法边界。'),
  set: (value) => {
    item.value.proposal = value;
  },
});
watch(
  () => state.space,
  () => {
    modal.value = '';
    checked.value = false;
  },
);
const deliveryStatus = {
  none: '尚无候选',
  received: '已接收，待检查',
  checked: '检查完成，待批准',
  approved: '已批准，待交付',
  active: '已限定启用',
  rejected: '检查未通过',
};
const modelStatus = {
  current: '当前版本',
  candidate: '候选待检查',
  validated: '检查完成，待审核',
  approved: '已批准，待提交启用',
  active: '新版本已启用',
  conflict: '基础版本冲突',
};
const contentStatus = { draft: '待识别核对', review: '候选待审核', open: '已按范围开放' };
function go(next: string) {
  void router.push(`/admin/${next}`);
}
function modelAction() {
  const m = item.value.model;
  if (m === 'current' || m === 'active') {
    item.value.model = 'candidate';
  } else if (m === 'candidate') {
    item.value.model = 'validated';
  } else if (m === 'validated') {
    modal.value = 'publish';
    checked.value = false;
  } else if (m === 'approved') {
    item.value.model = 'active';
    item.value.modelVersion++;
    audit(`${state.space}：owner 提交并启用模型 v${item.value.modelVersion}，历史影响待检查`);
    notify('示例版本已启用；尚不表示后续使用已经改善。');
  }
}
function bookAction() {
  if (item.value.book === 'draft') {
    item.value.book = 'review';
    notify('示例内容识别完成，等待人工核对。');
  } else if (item.value.book === 'review') {
    modal.value = 'book-publish';
    checked.value = false;
  }
}
function unlink() {
  state.linked = !state.linked;
  audit(`管理员：${state.linked ? '人工核实后建立' : '解除'}示例亲子关联，保留学习档案`);
  modal.value = '';
  notify(state.linked ? '关联已建立' : '关联已解除，家长后续访问将被阻止');
}
const pageTitles: Record<string, string> = {
  dashboard: '让内容与判断都有来处',
  content: '教材与内容',
  domain: '模型与教材映射',
  issues: '反馈与质量复核',
  tasks: '失败任务',
  accounts: '账号与亲子关联',
  config: '模型服务配置',
  usage: '用量与费用',
};
const configLabels: Record<string, string> = {
  saved: '已保存',
  checked: '检查完成，待启用',
  active: '已模拟启用',
  failed: '检查失败',
};
</script>
<template>
  <div class="page-heading">
    <div>
      <span class="eyebrow">{{ space.name }} / 独立管理身份</span>
      <h1>{{ pageTitles[page] || '管理工作台' }}</h1>
      <p>按具体事项查看、核对和维护。当前操作均为本地演示。</p>
    </div>
    <span class="tag neutral">单人管理 · 操作分别留痕</span>
  </div>
  <template v-if="page === 'dashboard'"
    ><div class="metrics">
      <button class="card metric" @click="go('content')">
        <span>内容准备</span><strong>{{ item.book === 'open' ? '已开放' : '待核对' }}</strong
        ><small>示例章节 · 按功能开放 <Icon name="arrow" :size="15" /></small></button
      ><button class="card metric" @click="go('issues')">
        <span>质量事项</span
        ><strong
          >{{ item.issue === 'open' || item.issue === 'reviewing' ? '1' : '0'
          }}<em> 待处理</em></strong
        ><small>只读取事项所需材料 <Icon name="arrow" :size="15" /></small></button
      ><button class="card metric" @click="go('domain')">
        <span>领域模型</span><strong>v{{ item.modelVersion }}<em> 当前</em></strong
        ><small>{{ modelStatus[item.model] }} <Icon name="arrow" :size="15" /></small>
      </button>
    </div>
    <div class="two-columns admin-columns">
      <section class="card">
        <div class="section-title">
          <h2>准备好一个可用章节</h2>
          <button class="text-button" @click="go('content')">进入内容管理 →</button>
        </div>
        <ol class="workflow-list">
          <li>
            <span>01</span>
            <div>
              <h3>导入与核对来源</h3>
              <p>保留页码、题目、解法出处及未决材料。</p>
            </div>
          </li>
          <li>
            <span>02</span>
            <div>
              <h3>确认领域关系</h3>
              <p>检查 Task / Solution / KC 及对应教材映射。</p>
            </div>
          </li>
          <li>
            <span>03</span>
            <div>
              <h3>限定开放与后续检查</h3>
              <p>审核、提交、生效分别记录，发布不代表效果已证实。</p>
            </div>
          </li>
        </ol>
      </section>
      <section class="card quiet">
        <span class="eyebrow">近期操作</span>
        <div v-if="!state.audit.length" class="empty small-empty">
          <Icon name="nodes" :size="30" />
          <p>完成一次操作后，这里会留下记录。</p>
        </div>
        <ol v-else class="audit-list">
          <li v-for="(event, i) in state.audit.slice(0, 7)" :key="i">{{ event }}</li>
        </ol>
        <p class="muted">本地演示记录用于走查，不构成真实审计证据。</p>
      </section>
    </div></template
  >
  <template v-else-if="page === 'content'"
    ><section class="card">
      <div class="section-title">
        <div>
          <h2>{{ space.book }}</h2>
          <p class="muted">原型示例内容，实际教材尚待提供。</p>
        </div>
        <button class="button primary" @click="modal = 'import-book'">导入教材</button>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>章节</th>
              <th>内容状态</th>
              <th>解法来源</th>
              <th>开放范围</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="chapter in space.chapters" :key="chapter">
              <td>
                <strong>{{ chapter }}</strong
                ><small>来源页、原图与识别内容分别保留</small>
              </td>
              <td>
                <span class="tag" :class="item.book === 'open' ? '' : 'amber'">{{
                  contentStatus[item.book]
                }}</span>
              </td>
              <td>系统候选 · 示例校验</td>
              <td>
                {{ item.book === 'open' ? '浏览、讲解及适用当题反馈' : '待核对，不用于正式判断' }}
              </td>
              <td>
                <button
                  class="text-button"
                  @click="
                    chapterName = chapter;
                    modal = 'chapter';
                  "
                >
                  查看 / 核对
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="note">未确认的 KC 关系不随整章批准生效。内容核对与正式模型批准分别完成。</div>
      <div class="actions">
        <button v-if="item.book !== 'open'" class="button primary" @click="bookAction">
          {{ item.book === 'draft' ? '模拟识别并生成候选' : '审核开放范围' }}</button
        ><button class="button secondary" @click="go('domain')">查看领域映射</button>
      </div>
    </section></template
  >
  <template v-else-if="page === 'domain'"
    ><section class="card">
      <div class="section-title">
        <div>
          <span class="eyebrow">{{ space.chapter }}</span>
          <h2>从教材内容到学习要求</h2>
        </div>
        <span class="tag" :class="item.model === 'conflict' ? 'amber' : ''"
          >{{ modelStatus[item.model] }} · v{{ item.modelVersion }}</span
        >
      </div>
      <div class="model-map">
        <div>
          <small>教材内容</small><strong>{{ space.chapter }}</strong
          ><span>章节与示例题</span>
        </div>
        <Icon name="arrow" />
        <div>
          <small>Task Family</small
          ><strong>{{ state.space === 'school' ? '已知部分求整体' : '整除与余数判断' }}</strong
          ><span>任务条件、责任与成功标准</span>
        </div>
        <Icon name="arrow" />
        <div>
          <small>Solution / KC</small
          ><strong>{{
            state.space === 'school' ? '单位份数 / 整体与部分' : '枚举 / 余数范围'
          }}</strong
          ><span>适用解法与知识关系</span>
        </div>
      </div>
      <div class="two-columns">
        <div class="note">
          <h3>已经具备的依据</h3>
          <p>示例原题、可复核计算、当前任务范围及一条适用解法。只是原型内容，不是正式领域包。</p>
        </div>
        <div class="note warm">
          <h3>仍需检查</h3>
          <p>
            变式是否检验相同责任、替代解法的适用边界，以及与 KC 的关系。入库不代表模型已经完善。
          </p>
        </div>
      </div>
      <div class="divider" />
      <label class="field"
        >候选变化说明<textarea
          v-model="proposal"
          :disabled="item.model === 'approved' || item.model === 'active'"
          @input="item.model === 'validated' && (item.model = 'candidate')"
        />
      </label>
      <p class="muted">修改已检查候选后，需要重新检查；批准绑定准确候选与范围。</p>
      <div class="actions">
        <button class="button primary" :disabled="item.model === 'conflict'" @click="modelAction">
          {{
            {
              current: '发起基础领域维护',
              candidate: '查看示例检查结果',
              validated: '审核候选',
              approved: '提交并启用此版本',
              active: '继续提出新候选',
              conflict: '基础冲突，暂不能启用',
            }[item.model]
          }}</button
        ><button
          v-if="['candidate', 'validated', 'approved'].includes(item.model)"
          class="button secondary"
          @click="
            item.model = 'conflict';
            notify('已模拟基础版本冲突，禁止沿用原检查与授权');
          "
        >
          演示基础冲突</button
        ><button
          v-if="item.model === 'conflict'"
          class="button secondary"
          @click="item.model = 'candidate'"
        >
          重取基础，重新检查</button
        ><button class="text-button" @click="modal = 'other-models'">其他语义模型交付</button>
      </div>
      <div v-if="item.model === 'active'" class="banner spaced">
        新版本已在本空间启用，尚无后续效果证据。旧判断的影响检查与必要修复仍是独立工作。
      </div>
    </section></template
  >
  <template v-else-if="page === 'issues'"
    ><section v-if="item.issue === 'none'" class="card empty">
      <Icon name="chat" :size="40" />
      <h2>当前没有待复核事项</h2>
      <p>在学生端从题目提出识别问题，或在家长端提报已删资料问题，再回到这里走查。</p>
      <button class="button secondary" @click="router.push('/student/materials')">
        切换学生端走查
      </button>
    </section>
    <section v-else class="card">
      <div class="section-title">
        <div>
          <span class="eyebrow">事项 DEMO-ISSUE-01 · {{ space.name }}</span>
          <h2>第 2 题的数字识别需要复核</h2>
        </div>
        <span class="tag" :class="item.issue === 'fixed' ? '' : 'amber'">{{
          item.issue === 'fixed' ? '已修复' : item.issue === 'reviewing' ? '复核中' : '已提交'
        }}</span>
      </div>
      <p>本事项仅取得对应题目、原件局部、识别结果及受影响反馈，不开放其他学习资料或私人咨询。</p>
      <div class="compare-box">
        <div><small>原识别记录</small><strong>3/8</strong><span>识别 v1 · 保留历史</span></div>
        <Icon name="arrow" />
        <div>
          <small>合成原件中的数字</small><strong class="handwritten">3/2</strong
          ><span>原件局部 · 复核依据</span>
        </div>
      </div>
      <div class="note">
        示例原件能够确认识别错误。本次只修正记录并处理依赖，不直接填入掌握结论，不需要修改正式模型。
      </div>
      <p v-if="item.hidden" class="banner warning">
        学生端已删除这份资料。后台修复不能恢复学生条目。
      </p>
      <div class="actions">
        <button
          v-if="item.issue === 'open'"
          class="button secondary"
          @click="
            item.issue = 'reviewing';
            audit('管理员开始事项复核');
          "
        >
          记录开始复核</button
        ><button class="button primary" :disabled="item.issue === 'fixed'" @click="correctIssue">
          {{ item.issue === 'fixed' ? '已完成示例修复' : '确认依据并执行示例修复' }}</button
        ><button
          class="button secondary"
          v-if="item.issue !== 'fixed'"
          @click="notify('保持未决，不改写当前事实或能力判断。')"
        >
          材料不足，保留未决
        </button>
      </div>
      <div v-if="item.issue === 'fixed'" class="banner spaced">
        记录已更正，相关当题反馈已更新，学生和当前关联家长可收到必要告知；不重放旧教学。
      </div>
    </section></template
  >
  <template v-else-if="page === 'tasks'"
    ><section class="card">
      <div class="section-title">
        <h2>示例试卷处理任务</h2>
        <span class="tag" :class="item.failure ? 'amber' : ''">{{
          item.failure ? '处理失败' : item.processing ? '处理中' : '当前无失败'
        }}</span>
      </div>
      <p>接收、处理、提交和展示分别核对；重试关联原任务，不制造新的作答或教学。</p>
      <ol class="steps">
        <li>原材料是否已接收：{{ item.imported ? '是' : '否' }}</li>
        <li>
          处理是否完成：{{
            item.failure ? '失败，待恢复' : item.processing ? '处理中' : '本场景无未完成步骤'
          }}
        </li>
        <li>学生端是否删除：{{ item.hidden ? '是，重试不得恢复展示' : '否' }}</li>
      </ol>
      <button
        class="button primary"
        :disabled="!item.failure || state.scenario === 'failure' || state.scenario === 'offline'"
        @click="
          item.failure = false;
          audit('管理员核对原任务后重试未完成步骤；保留删除状态');
          notify('原任务恢复，未重复导入或恢复已删条目');
        "
      >
        重试原任务未完成步骤
      </button>
      <p class="muted">使用走查工具模拟处理失败，上传示例后可查看；恢复正常状态再重试。</p>
    </section></template
  >
  <template v-else-if="page === 'accounts'"
    ><section class="card">
      <div class="section-title">
        <h2>稳定档案与独立账号</h2>
        <button
          class="button secondary"
          @click="
            modal = 'create-account';
            checked = false;
          "
        >
          核实并开户
        </button>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>身份</th>
              <th>账号与档案</th>
              <th>当前范围</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>学习者 · 小禾</td>
              <td>student.demo / DEMO-L01</td>
              <td>自己的两个独立课程空间</td>
              <td>
                <button
                  class="text-button"
                  @click="
                    modal = 'recover';
                    checked = false;
                  "
                >
                  核实后重置凭据
                </button>
              </td>
            </tr>
            <tr>
              <td>家长</td>
              <td>parent.demo</td>
              <td>{{ state.linked ? '关联小禾，相关依据只读' : '关系已解除，无孩子访问权' }}</td>
              <td>
                <button
                  class="text-button"
                  @click="
                    modal = 'relation';
                    checked = false;
                  "
                >
                  {{ state.linked ? '解除关联' : '核实后建立关联' }}
                </button>
              </td>
            </tr>
            <tr>
              <td>管理员</td>
              <td>admin.demo</td>
              <td>独立管理身份，按事项访问</td>
              <td>独立恢复机制由工程实现</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="note">
        换设备、恢复密码或增减关联均保留同一学习档案；家长账号不因此获得管理员权限。
      </div>
    </section></template
  >
  <template v-else-if="page === 'config'"
    ><section class="card narrow-card">
      <span class="tag neutral">演示配置 · 不发送网络请求</span>
      <h2>模型用途与连接</h2>
      <label class="field"
        >服务名称<input
          value="示例推理服务"
          placeholder="服务名称"
          @input="state.config = 'saved'" /></label
      ><label class="field"
        >接口地址<input
          value="https://example.invalid/v1"
          type="url"
          @input="state.config = 'saved'" /></label
      ><label class="field"
        >模型标识<input value="demo-model" @input="state.config = 'saved'"
      /></label>
      <div class="note">
        原型不收集 API
        Key。正式系统需区分保存配置、连通检查、协议能力、语义质量和限定启用；实际数据目的地仍受首次授权范围约束。
      </div>
      <div class="actions">
        <button
          class="button secondary"
          @click="
            state.config = 'saved';
            notify('配置已模拟保存，尚未证明可用');
          "
        >
          保存演示配置</button
        ><button
          class="button primary"
          @click="
            state.config = state.scenario === 'failure' ? 'failed' : 'checked';
            notify(
              state.config === 'failed'
                ? '模拟连接失败，当前配置未启用'
                : '合成检查已模拟完成，尚未启用',
            );
          "
        >
          模拟连接与合同检查</button
        ><button
          class="button secondary"
          :disabled="state.config !== 'checked'"
          @click="
            state.config = 'active';
            audit('示例配置限定启用，不发送真实资料');
            notify('仅演示启用状态，不进行真实调用');
          "
        >
          限定启用
        </button>
      </div>
      <p>
        当前状态：<strong>{{ configLabels[state.config] }}</strong>
      </p>
    </section></template
  >
  <template v-else-if="page === 'usage'"
    ><div class="metrics">
      <div class="card metric">
        <span>真实模型调用</span><strong>0</strong><small>原型不连接模型</small>
      </div>
      <div class="card metric">
        <span>模型费用</span><strong>未产生</strong><small>不虚构运行测量结果</small>
      </div>
      <div class="card metric">
        <span>记录的演示操作</span><strong>{{ state.audit.length }}</strong
        ><small>不等于学习证据数量</small>
      </div>
    </div>
    <section class="card spaced">
      <h2>后续正式运行的查看方式</h2>
      <p>
        按用途区分学习支持、教材准备、检查与维护；保留失败和重试成本，已知、估算与未知费用分别表达。
      </p>
      <ol class="audit-list">
        <li v-for="(event, i) in state.audit" :key="i">{{ event }}</li>
      </ol>
    </section></template
  >
  <Modal
    v-if="modal === 'publish' || modal === 'book-publish'"
    :title="modal === 'publish' ? '审核领域候选' : '审核章节开放范围'"
    @close="modal = ''"
    ><span class="tag">{{ space.name }} · 限定当前空间</span>
    <p>
      {{
        modal === 'publish'
          ? proposal
          : '示例章节的来源与适用解法已供核对。仅开放具备依据的浏览、讲解和当题反馈，不自动批准未决 KC 关系。'
      }}
    </p>
    <div class="note">
      检查材料：示例正例、适用边界及拒绝路径。实际内容和评测资产尚待教材补齐，原型不能证明候选语义正确。
    </div>
    <label class="checkbox-line"
      ><input v-model="checked" type="checkbox" />已查看本次差异、范围、检查结果与未决</label
    ><button
      class="button primary full-width"
      :disabled="!checked"
      @click="
        modal === 'publish'
          ? ((item.model = 'approved'), audit('管理员批准准确示例候选，等待 owner 提交'))
          : ((item.book = 'open'), audit('管理员审核示例章节，模拟提交与限定开放'));
        modal = '';
        notify('审核结果已记录');
      "
    >
      {{ modal === 'publish' ? '批准此候选，进入待提交' : '批准并模拟限定开放' }}
    </button></Modal
  >
  <Modal v-if="modal === 'chapter'" title="核对章节内容与用途" @close="modal = ''"
    ><h3>{{ chapterName }}</h3>
    <div class="compare-box">
      <div>
        <small>示例来源</small><strong>教材第 1–2 页</strong><span>原页、结构和题目对应</span>
      </div>
      <div>
        <small>示例模型</small><strong>Task → Solution → KC</strong
        ><span>未确认关系继续保留未决</span>
      </div>
    </div>
    <p>原型不包含真实教材扫描件；正式核对需要对照实际来源，不能只看系统生成的说明。</p>
    <button
      class="button secondary"
      @click="
        modal = '';
        go('domain');
      "
    >
      查看双向映射
    </button></Modal
  >
  <Modal v-if="modal === 'import-book'" title="导入教材 · 示例流程" @close="modal = ''"
    ><label class="field">教材名称<input :value="space.book" /></label
    ><label class="field"
      >PDF 或成组图片<input type="file" accept="image/*,application/pdf" multiple
    /></label>
    <p class="note">
      原型不读取或上传内容。继续将创建本空间的模拟待核对章节，无答案也可以进入准备流程。
    </p>
    <button
      class="button primary"
      @click="
        item.book = 'draft';
        modal = '';
        audit('建立示例教材导入任务，尚未发布');
      "
    >
      创建示例导入任务
    </button></Modal
  >
  <Modal
    v-if="['relation', 'recover', 'create-account'].includes(modal)"
    :title="
      modal === 'relation' ? '确认关联变更' : modal === 'recover' ? '核实后重置凭据' : '核实并开户'
    "
    @close="modal = ''"
    ><p>
      {{
        modal === 'relation' && state.linked
          ? '解除示例家长与小禾的关联后，家长后续不能读取相应资料。学习档案和历史继续保留。'
          : '由管理员在系统外核实本人及必要关系，后台记录核实结果，不上传证件或新增第二人审批。'
      }}
    </p>
    <label class="checkbox-line"
      ><input v-model="checked" type="checkbox" />已核对对象、操作范围和人工核实记录（演示）</label
    ><button
      class="button primary full-width"
      :disabled="!checked"
      @click="
        modal === 'relation'
          ? unlink()
          : (audit(
              modal === 'recover'
                ? '管理员核实后模拟重置凭据，档案保持'
                : '示例账号已存在，继续原档案，不重复开户',
            ),
            notify('演示操作已记录，原档案保留'),
            (modal = ''))
      "
    >
      确认并记录
    </button></Modal
  >
  <Modal v-if="modal === 'other-models'" title="其他语义模型的受控交付" @close="modal = ''"
    ><p>评价、交互及推理规则提供查看、追溯与受控版本交付，不提供通用在线编辑。</p>
    <span class="tag">{{ deliveryStatus[item.delivery] }}</span>
    <div class="note">
      <h3>示例评价规则包 · EV-DEMO-02</h3>
      <p>
        来源：人工准备的合成版本；差异：明确“看过讲解”不能直接支持“独立掌握”；限定范围：当前课程的示例规则。
      </p>
      <p>
        检查依据：独立完成、获得讲解、条件缺失三个固定示例；这里只演示交付步骤，不执行语义评测，不修改正式
        Belief。
      </p>
    </div>
    <div class="actions">
      <button
        v-if="item.delivery === 'none' || item.delivery === 'rejected'"
        class="button primary"
        @click="
          item.delivery = 'received';
          audit('接收示例规则包，尚未启用');
        "
      >
        接收示例交付包</button
      ><template v-if="item.delivery === 'received'"
        ><button
          class="button primary"
          @click="
            item.delivery = 'checked';
            audit('查看固定示例检查结果');
          "
        >
          查看合成检查结果</button
        ><button class="button secondary" @click="item.delivery = 'rejected'">
          模拟检查未通过
        </button></template
      ><button
        v-if="item.delivery === 'checked'"
        class="button primary"
        @click="
          item.delivery = 'approved';
          audit('管理员批准准确规则包及范围');
        "
      >
        批准此版本及范围</button
      ><button
        v-if="item.delivery === 'approved'"
        class="button primary"
        @click="
          item.delivery = 'active';
          audit('owner 模拟交付并限定启用规则包');
        "
      >
        交付并限定启用
      </button>
    </div>
    <p v-if="item.delivery === 'active'">
      新规则版本已模拟启用；运行后检查、撤回和真实合同验证需在工程阶段完成，不自动改写历史结果。
    </p></Modal
  >
</template>
