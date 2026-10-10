<script setup lang="ts">
import { computed, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { navs, spaces, type Role, type SpaceId } from './data';
import { state, ui, reset, notify, allowed } from './store';
import Icon from './components/Icon.vue';
import Modal from './components/Modal.vue';
import IntentPanel from './components/IntentPanel.vue';
const route = useRoute();
const router = useRouter();
const role = computed(() => (route.path.split('/')[1] || 'student') as Role);
const page = computed(() => String(route.params.page || 'home'));
const labels = { student: '学生平板端', parent: '家长手机端', admin: '管理工作台' };
const timeOpen = ref(false);
const minutes = ref(0);
const active = (key: string) =>
  page.value === key ||
  (role.value === 'student' &&
    ((key === 'materials' && ['upload', 'exam', 'question'].includes(page.value)) ||
      (key === 'book' && page.value === 'lesson') ||
      (key === 'learning' && ['test', 'results'].includes(page.value))));
function switchRole(next: Role) {
  void router.push(`/${next}/${navs[next][0]!.key}`);
}
function switchSpace(e: Event) {
  state.space = (e.target as HTMLSelectElement).value as SpaceId;
  void router.push(`/${role.value}/${navs[role.value][0]!.key}`);
}
function addTime() {
  if (!Number.isFinite(minutes.value) || minutes.value < 0 || minutes.value > 180) {
    notify('请填写 0–180 分钟的本次用时');
    return;
  }
  state.extraMinutes += minutes.value;
  state.timeUnknown = false;
  minutes.value = 0;
  timeOpen.value = false;
  notify('已补记未被自动记录的时间。');
}
</script>
<template>
  <div class="prototype-bar">
    <span
      ><span class="prototype-dot" />交互原型 · 第 5 轮
      <span class="demo-descriptor">· 示例数据，无真实账号与模型调用</span></span
    >
    <div class="role-switch" aria-label="原型角色切换">
      <button
        v-for="(_, key) in labels"
        :key="key"
        :class="{ selected: role === key }"
        @click="switchRole(key)"
      >
        {{ labels[key] }}
      </button>
    </div>
    <button class="review-toggle" @click="ui.reviewOpen = !ui.reviewOpen">
      <Icon name="settings" :size="15" />走查工具
    </button>
  </div>
  <div v-if="ui.reviewOpen" class="review-tools">
    <label
      >演示状态
      <select v-model="state.scenario">
        <option value="normal">正常处理</option>
        <option value="partial">局部识别不清</option>
        <option value="offline">模拟断网</option>
        <option value="failure">模拟处理失败</option>
      </select></label
    ><button @click="reset()">重置全部演示</button
    ><button
      @click="
        reset(true);
        router.push('/student/home');
      "
    >
      首次使用场景</button
    ><button
      @click="
        state.timeUnknown = true;
        notify('已设为存在离页学习待补记');
      "
    >
      离页学习场景</button
    ><span>任意输入不作真实识别或语义判断。家长时间筛选、学生会话删除仍待讨论。</span>
  </div>
  <div v-if="ui.storageWarning" class="banner warning">
    浏览器存储不可用，当前演示可继续，刷新后可能无法保留。
  </div>
  <div class="app-shell" :class="[role, { 'with-review': ui.reviewOpen }]">
    <header class="app-header">
      <a class="brand" :href="`#/${role}/${navs[role][0]!.key}`"
        ><span class="brand-symbol"
          ><svg viewBox="0 0 40 40" aria-hidden="true">
            <path
              d="M12 16 7 6m5 10-7-2m23 2 5-10m-5 10 7-2M12 16c-3 14 1 19 8 19s11-5 8-19c-4-4-12-4-16 0Z"
            />
            <path d="M16 24h.1M24 24h.1m-7 5 3 2 3-2" /></svg></span
        ><span
          >DeerMind<small>{{
            role === 'admin' ? '内容与学习支持' : '让理解，慢慢生长'
          }}</small></span
        ></a
      >
      <div class="header-right">
        <label class="space-picker"
          ><Icon name="book" :size="17" /><select
            :value="state.space"
            aria-label="当前课程空间"
            @change="switchSpace"
          >
            <option v-for="(space, id) in spaces" :value="id" :key="id">{{ space.name }}</option>
          </select></label
        ><button v-if="role === 'student'" class="time-chip" @click="timeOpen = true">
          <Icon name="clock" :size="16" />{{ state.autoMinutes + state.extraMinutes }} / 30
          分钟<span v-if="state.timeUnknown"> · 待补记</span></button
        ><span class="avatar">{{ role === 'admin' ? '管' : role === 'parent' ? '家' : '禾' }}</span>
      </div>
    </header>
    <aside v-if="role !== 'parent'" class="sidebar">
      <span class="nav-caption">{{
        role === 'admin' ? 'WORKSPACE / 管理' : 'LEARNING / 学习'
      }}</span>
      <nav>
        <RouterLink
          v-for="item in navs[role]"
          :key="item.key"
          :to="`/${role}/${item.key}`"
          :class="{ active: active(item.key) }"
          ><Icon :name="item.icon" /><span>{{ item.label }}</span
          ><span v-if="active(item.key)" class="nav-active-dot"
        /></RouterLink>
      </nav>
      <div class="sidebar-footer">
        <Icon name="leaf" :size="26" />
        <p>
          {{ role === 'admin' ? '有依据地维护，每一步可追溯。' : '不急着答对，先把问题想明白。' }}
        </p>
        <span>{{ role === 'admin' ? '单人管理 · 独立身份' : '自己的节奏，也很好。' }}</span>
      </div>
    </aside>
    <main class="main-content" :class="{ 'phone-content': role === 'parent' }">
      <div
        v-if="role === 'student' && state.autoMinutes + state.extraMinutes >= 30"
        class="banner warning"
      >
        今天已记录
        {{ state.autoMinutes + state.extraMinutes }}
        分钟。先保存进度，明天再继续吧。不会锁屏，实际超时仍如实记录。
      </div>
      <div v-if="state.scenario === 'offline'" class="banner warning">
        <Icon name="info" />当前为断网演示：输入保留，新的提交和帮助等待连接恢复。
      </div>
      <section v-if="role === 'student' && !allowed()" class="onboarding card">
        <span class="eyebrow">初次见面</span>
        <h1>你好，一起把问题讲明白。</h1>
        <p>
          你可以拍下题目、写下思路，也可以直接问我。讲解可能有错，你可以随时提出问题，不想继续时也可以结束。
        </p>
        <div class="note">
          提交后的题目、作答和发出的录音会保留，用于帮助学习。关联家长可以查看相关依据；从你的界面删除资料后，内部记录仍保留。
        </div>
        <p>
          {{
            state.familyConsent
              ? '家长已完成数据使用说明确认。'
              : '请家长先在家长 App 的账号页面完成说明确认。'
          }}
        </p>
        <button
          class="button primary"
          :disabled="!state.familyConsent"
          @click="
            state.childConsent = true;
            notify('已记录愿意使用，进入学习首页');
          "
        >
          我了解了，愿意开始
        </button>
      </section>
      <RouterView v-else />
    </main>
    <nav class="bottom-nav" v-if="role !== 'admin'">
      <RouterLink
        v-for="item in navs[role]"
        :key="item.key"
        :to="`/${role}/${item.key}`"
        :class="{ active: active(item.key) }"
        ><Icon :name="item.icon" /><span>{{ item.label }}</span></RouterLink
      >
    </nav>
  </div>
  <IntentPanel v-if="!(role === 'student' && page === 'lesson')" />
  <div v-if="ui.toast" class="toast" role="status">
    <Icon name="info" :size="18" />{{ ui.toast }}
  </div>
  <Modal v-if="timeOpen" title="今天的学习时间" @close="timeOpen = false"
    ><p>
      自动记录 <strong>{{ state.autoMinutes }} 分钟</strong>，已补记
      <strong>{{ state.extraMinutes }} 分钟</strong>。这里是演示计时，不采集真实使用时长。
    </p>
    <p>
      刚才离开 App 后，还在纸上做 DeerMind 的题吗？只补记尚未计入的时间，休息和后台独自处理不计算。
    </p>
    <label class="field"
      >补记分钟数<input v-model.number="minutes" type="number" min="0" max="180"
    /></label>
    <div class="actions">
      <button
        class="button secondary"
        @click="
          state.timeUnknown = false;
          timeOpen = false;
        "
      >
        没有继续学习</button
      ><button class="button primary" @click="addTime">确认补记</button>
    </div></Modal
  >
</template>
