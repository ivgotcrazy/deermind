<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { spaces, questions } from '../data';
import { state, current, notify, reportIssue, audit } from '../store';
import Icon from '../components/Icon.vue';
import Modal from '../components/Modal.vue';
import LearnerOverview from '../components/LearnerOverview.vue';
import { clearConversation } from '../conversation';
const route = useRoute();
const router = useRouter();
const page = computed(() => String(route.params.page || 'overview'));
const item = computed(current);
const space = computed(() => spaces[state.space]);
const modal = ref('');
const message = ref('');
const canRead = computed(() => state.linked && state.familyConsent && state.childConsent);
const checkbox = ref(false);
const evidenceIndex = computed(() =>
  item.value.kind === 'single' ? 2 : item.value.corrected || item.value.hidden ? 1 : 0,
);
watch(
  () => state.space,
  () => {
    modal.value = '';
    message.value = '';
    checkbox.value = false;
  },
);
function consult(question?: string) {
  if (!canRead.value) return;
  const text = question || message.value.trim();
  if (!text) return;
  if (state.scenario === 'offline') {
    notify('尚未发送，问题仍保留在输入区。');
    return;
  }
  const answer = question
    ? item.value.imported
      ? `本空间的示例依据只支持当次作答表现。${item.value.corrected ? '第 2 题识别已经纠正，不再以原误识别说明困难。' : '当前需要区分作答错误、识别问题与依据不足。'}可以请她在愿意时解释关键理由，或自愿做一次适用的检查；不强制布置任务。`
      : '当前课程尚无学生作答记录，暂不能据此判断困难。没有记录不等于孩子不会。'
    : '已收到这段演示咨询。原型不理解任意输入，也不据此判断孩子的能力。正式产品中，线下表现转述只用于有条件的咨询建议，不更新正式掌握证据。';
  item.value.chats.push({ question: text, answer });
  message.value = '';
  void router.push('/parent/consult');
}
function consent() {
  if (!checkbox.value || !state.linked) return;
  state.familyConsent = true;
  audit('示例家长：确认首次数据说明 v0.1；孩子参与意愿另行确认');
  notify('家长确认已记录。请切换学生端，由孩子确认愿意使用。');
}
</script>
<template>
  <template v-if="page !== 'settings' && !canRead"
    ><section class="card empty">
      <Icon name="user" :size="36" />
      <h2>{{ !state.linked ? '当前没有可查看的孩子' : '首次使用确认尚未完成' }}</h2>
      <p>
        {{
          !state.linked
            ? '请联系管理员核对亲子关联。原登录状态不会继续开放已解除关系的资料。'
            : '先完成家长的数据说明确认，再由孩子确认愿意使用。'
        }}
      </p>
      <button class="button primary" @click="router.push('/parent/settings')">
        查看账号与关联
      </button>
    </section></template
  >
  <template v-else-if="page === 'overview'">
    <div class="parent-heading">
      <span class="eyebrow">{{ space.name }} / 学习概况</span>
      <h1>看看她的学习情况</h1>
      <div class="child-line">
        <span class="avatar">禾</span>
        <div>
          <strong>小禾 · 示例学习者</strong><small>{{ space.name }} · 当前有效判断</small>
        </div>
      </div>
    </div>
    <p class="learning-scope-note parent-learning-time">
      今天已记录 {{ state.autoMinutes + state.extraMinutes }} 分钟 / 全部课程共 30 分钟
    </p>
    <LearnerOverview role="parent" />
    <button v-if="item.imported" class="button secondary full-width" @click="modal = 'evidence'">
      查看相关依据<Icon name="arrow" :size="16" />
    </button>
    <section v-if="item.notice" class="notice-card">
      <Icon name="bell" />
      <div>
        <strong>一条学习记录已经更正</strong>
        <p>识别结果和相关反馈有变化。</p>
        <button class="text-button" @click="router.push('/parent/notices')">了解变化</button>
      </div>
    </section>
    <button class="button secondary full-width" @click="consult('为什么说还需要了解她的理解？')">
      <Icon name="chat" :size="18" />问问这些判断的依据
    </button>
  </template>
  <template v-else-if="page === 'consult'"
    ><div class="page-heading">
      <div>
        <span class="eyebrow">{{ space.name }} / 家长咨询</span>
        <h1>一起理解她的学习</h1>
        <p>你的咨询只对自己可见。</p>
      </div>
    </div>
    <div class="note">可以询问原因和支持方式；这里不修改孩子的资料，不向她派发任务。</div>
    <div v-if="!item.chats.length" class="card empty">
      <Icon name="chat" :size="35" />
      <h3>从一个具体问题开始</h3>
      <button class="suggestion" @click="consult('这条判断有哪些依据？')">
        这条判断有哪些依据？</button
      ><button class="suggestion" @click="consult('我可以怎样帮助她？')">我可以怎样帮助她？</button>
    </div>
    <div class="conversation" v-else>
      <template v-for="(entry, i) in item.chats" :key="i"
        ><div class="bubble user-bubble">{{ entry.question }}</div>
        <div class="bubble assistant-bubble">
          <span class="bubble-author"><Icon name="leaf" :size="15" />DeerMind · 演示回复</span
          >{{ entry.answer }}
        </div></template
      ><button class="text-button danger-text" @click="modal = 'delete-chat'">删除整段会话</button>
    </div>
    <form class="consult-input card" @submit.prevent="consult()">
      <label class="sr-only" for="parent-message">咨询问题</label
      ><textarea
        id="parent-message"
        v-model="message"
        placeholder="想了解什么？写下你的问题……"
      /><button class="button primary" :disabled="!message.trim()" type="submit">
        发送<Icon name="arrow" :size="17" />
      </button>
    </form>
    <p class="muted footnote">
      任意文字只演示提交与保留，不调用模型。线下转述不成为孩子的正式能力证据。
    </p></template
  >
  <template v-else-if="page === 'notices'"
    ><div class="page-heading">
      <div>
        <span class="eyebrow">更正与处理</span>
        <h1>把变化说明白</h1>
      </div>
    </div>
    <section v-if="item.notice" class="card">
      <span class="tag">已更正</span>
      <h2>第 2 题的识别结果已更新</h2>
      <p>此前把作答中的 3/2 识别成了 3/8。已依据示例原件更正识别和相应当题反馈。</p>
      <p>这次更正不直接证明整章已经掌握，也不会重放旧讲解。</p>
      <button class="text-button" @click="modal = 'evidence'">查看相关依据</button>
    </section>
    <section v-else class="card empty">
      <Icon name="bell" :size="36" />
      <h3>目前没有实质更正通知</h3>
      <p>影响已展示结果的更正，会在这里说明。</p>
    </section>
    <section v-if="item.issue !== 'none'" class="card spaced">
      <h3>识别复核事项</h3>
      <span class="tag" :class="item.issue === 'fixed' ? '' : 'amber'">{{
        item.issue === 'fixed' ? '已修复' : item.issue === 'reviewing' ? '复核中' : '已提交，待复核'
      }}</span>
      <p>事项与原咨询分别保存；删除自己的咨询不撤销此事项。</p>
    </section></template
  >
  <template v-else-if="page === 'settings'"
    ><div class="page-heading">
      <div>
        <span class="eyebrow">家长账号</span>
        <h1>账号与关联</h1>
      </div>
    </div>
    <section class="card">
      <div class="profile-line">
        <span class="avatar large">家</span>
        <div>
          <h2>示例家长</h2>
          <p>家长身份 · 管理后台另行登录</p>
        </div>
      </div>
      <div class="setting-row">
        <div>
          <strong>当前关联</strong>
          <p>
            {{
              state.linked
                ? '小禾（DEMO-L01） · 相关学习依据只读'
                : '暂无有效关联，请联系管理员核实'
            }}
          </p>
        </div>
      </div>
      <div class="setting-row">
        <div>
          <strong>首次数据说明</strong>
          <p>
            照片、手写、发出的录音和学习记录用于学习支持；按课程空间隔离。家长查看相关依据，管理员按具体事项维护。
          </p>
          <p>
            内部资料随档案保留；学生界面删除不意味着物理销毁。家长私人咨询不向孩子或其他家长开放。
          </p>
        </div>
      </div>
      <div class="note">
        本原型仅保存本浏览器的合成演示状态，不连接外部模型服务。正式使用前必须列明实际服务、数据类别和用途，重新取得对应确认；此处点击不替代真实授权。
      </div>
      <span v-if="state.familyConsent" class="tag">演示说明 v0.1 已确认</span
      ><template v-else
        ><label class="checkbox-line"
          ><input v-model="checkbox" type="checkbox" />我已了解上述演示数据说明</label
        ><button
          class="button primary full-width"
          :disabled="!checkbox || !state.linked"
          @click="consent"
        >
          确认首次说明
        </button></template
      >
      <p class="muted">凭据找回及关联调整由管理员系统外核实后办理，继续原档案。</p>
    </section></template
  >
  <Modal v-if="modal === 'evidence' && canRead" title="相关学习依据 · 只读" @close="modal = ''"
    ><span class="eyebrow">{{ space.name }} / 单元练习</span>
    <p>{{ questions[state.space][evidenceIndex]!.prompt }}</p>
    <div class="original-work">
      <small>原作答与帮助条件</small>
      <p>
        {{
          item.corrected
            ? '3/4 ÷ 1/2 = 3/2（已更正识别）'
            : questions[state.space][evidenceIndex]!.work
        }}
      </p>
      <span>对应当次表现，不表示所有同类题均已掌握。</span>
    </div>
    <p v-if="item.hidden" class="note">
      这份资料已从学生界面删除。你仍可按相关依据权限查看，但不能恢复或修改。
    </p>
    <template v-if="item.hidden && state.space === 'school' && item.kind === 'exam'"
      ><button
        class="button secondary"
        :disabled="item.issue !== 'none'"
        @click="
          reportIssue();
          modal = '';
        "
      >
        提报已删资料的识别问题
      </button></template
    >
    <p v-else class="muted">普通资料的录入和更正在学生端完成；家长端只读。</p></Modal
  >
  <Modal v-if="modal === 'delete-chat'" title="删除整段咨询？" @close="modal = ''"
    ><p>
      本会话的全部提问与回复将从你的界面移除，不能恢复。孩子的资料及已提交的独立后台事项不受影响。
    </p>
    <div class="actions">
      <button class="button secondary" @click="modal = ''">保留会话</button
      ><button
        class="button danger"
        @click="
          clearConversation('parent', state.space);
          item.chats = [];
          audit('家长删除整段示例咨询；独立事项保留');
          modal = '';
          notify('整段咨询已移除');
        "
      >
        确认删除会话
      </button>
    </div></Modal
  >
</template>
