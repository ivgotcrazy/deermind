<script setup lang="ts">
import { computed, ref, watch, nextTick, onBeforeUnmount } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { questions, spaces, statusText, fixturePlan } from '../data';
import {
  state,
  current,
  notify,
  importExam,
  retryExam,
  showHelp,
  deleteExam,
  reportIssue,
  questionStatus,
  startTest,
  submitTest,
  endTest,
  audit,
} from '../store';
import Icon from '../components/Icon.vue';
import Modal from '../components/Modal.vue';
import WritingPad from '../components/WritingPad.vue';
import LearnerOverview from '../components/LearnerOverview.vue';
import LessonWorkspace from '../components/LessonWorkspace.vue';
import { lessons, lessonState } from '../lessons';
import { openConversation } from '../conversation';
const route = useRoute();
const router = useRouter();
const page = computed(() => String(route.params.page || 'home'));
const isTest = computed(() => route.query.from === 'test');
const space = computed(() => spaces[state.space]);
const item = computed(current);
const list = computed(() => questions[state.space]);
const question = computed(() => list.value[item.value.selectedQuestion]!);
const visible = computed(
  () => item.value.imported && !item.value.hidden && !item.value.processing && !item.value.failure,
);
const work = computed(
  () => (item.value.practice[question.value.id] ??= { draft: '', strokes: [] }),
);
const planned = computed(() => fixturePlan(state.space, chosen.value));
const materialQuestions = computed(() =>
  item.value.kind === 'single' ? [list.value[2]!] : list.value,
);
const wrongs = computed(() =>
  materialQuestions.value.filter((q) => questionStatus(list.value.indexOf(q)) === 'wrong'),
);
const knowledgeChapter = ref<string>(space.value.chapter);
const savedLessons = computed(() => state.space === 'school' ? lessons.filter((l) => lessonState.records.school[l.id]) : []);
const knowledgeText: Record<string, string> = {
  百分数的应用:
    '百分数表示一个量是另一个量的百分之几。处理应用题时，先找出被看作 100% 的整体，再确定已知的是整体还是其中一部分。',
  分数除法:
    '3/4 除以 1/2，可以理解为 3/4 里面有几个 1/2。把它们都画成四等份，比较 3 份与 2 份：前者是后者的 1.5 倍。除法表达的是两个数量的这种关系。',
  整除与余数:
    '一个整数除以另一个非零整数，恰好除尽时余数是 0。除不尽时，余数必须小于除数，否则还能继续分出一份。',
  数的规律:
    '遇到周期重复的问题，可以分别记录每次发生的时刻，再找共同出现的位置。用具体例子检查规律，避免只凭一次看起来相同就下结论。',
};
function openKnowledge(chapter: string = space.value.chapter) {
  if (item.value.test.stage === 'running') {
    notify('本次自测尚未结束。请回到自测继续，或结束检测后求讲解。');
    go('test');
    return;
  }
  const lesson = lessons.find((l) => l.chapter === chapter);
  if (state.space === 'school' && lesson) {
    void router.push({ path: '/student/lesson', query: { lesson: lesson.id } });
    return;
  }
  knowledgeChapter.value = chapter;
  modal.value = 'knowledge';
}
const tab = ref('all');
const help = ref<'none' | 'hint' | 'explain'>('none');
const modal = ref('');
const chosen = ref<string[]>([]);
const uploadedName = ref('');
const voice = ref('');
const voiceState = ref('idle');
const uploadKind = ref<'exam' | 'single'>('exam');
const testQuestion = computed(
  () => list.value[item.value.test.questionIndexes[item.value.test.index] ?? 0]!,
);
const filtered = computed(() =>
  tab.value === 'wrong'
    ? materialQuestions.value.filter((q) => questionStatus(list.value.indexOf(q)) === 'wrong')
    : materialQuestions.value,
);
watch(
  () => [state.space, page.value, item.value.selectedQuestion],
  () => {
    help.value = 'none';
    voiceState.value = 'idle';
    stopAudio();
  },
);
watch(
  () => state.space,
  () => {
    chosen.value = [];
    modal.value = '';
    uploadedName.value = '';
    voice.value = '';
  },
);
function go(name: string) {
  void router.push(`/student/${name}`);
}
function openQuestion(index: number) {
  item.value.selectedQuestion = index;
  go('question');
}
function requestHelp(kind: 'hint' | 'explain') {
  if (showHelp(kind, isTest.value)) help.value = kind;
}
async function upload() {
  const promise = importExam(
    uploadedName.value
      ? `${uploadedName.value}（固定示例演示）`
      : uploadKind.value === 'single'
        ? '独立上传题 · 示例'
        : undefined,
    uploadKind.value,
  );
  if (state.scenario !== 'offline') go('exam');
  await promise;
}
function pickFile(e: Event) {
  const files = (e.target as HTMLInputElement).files;
  if (files?.length)
    uploadedName.value = Array.from(files)
      .map((f) => f.name)
      .join('、');
}
function plan(mode = 'chapter') {
  item.value.test.stage = 'plan';
  chosen.value = mode === 'chapter' ? [] : [space.value.chapter];
  go('test');
}
async function helpDuringTest() {
  endTest('中途请求讲解');
  item.value.selectedQuestion = item.value.test.questionIndexes[item.value.test.index] ?? 0;
  modal.value = '';
  await router.push({ path: '/student/question', query: { from: 'test' } });
  await nextTick();
  requestHelp('explain');
}
function play() {
  if (!('speechSynthesis' in window)) {
    notify('当前浏览器不支持播放，可以阅读文字讲解');
    return;
  }
  const speech = new SpeechSynthesisUtterance(
    help.value === 'hint' ? question.value.hint : question.value.explanation.join('。'),
  );
  speech.lang = 'zh-CN';
  window.speechSynthesis.cancel();
  window.speechSynthesis.speak(speech);
  audit('浏览器演示播放已请求，不代表孩子听懂');
}
function stopAudio() {
  window.speechSynthesis?.cancel();
}
onBeforeUnmount(stopAudio);
function submitPractice() {
  if (!work.value.draft.trim() && !work.value.strokes.length) {
    notify('请先写下你的思路');
    return;
  }
  if (state.scenario === 'offline') {
    notify('尚未收到提交，输入已保留');
    return;
  }
  notify('作答已保存为演示输入；原型不判定任意输入的对错。');
  audit(`${state.space}：保存练习演示输入，不写掌握结论`);
}
</script>
<template>
  <template v-if="page === 'home'">
    <div class="page-heading">
      <div>
        <span class="eyebrow">{{ space.subtitle }}</span>
        <h1>今天，想弄懂什么？</h1>
        <p>从一个问题开始，按自己的节奏学。</p>
      </div>
      <span class="date-pill"><Icon name="leaf" :size="16" />每一步理解，都算数</span>
    </div>
    <section class="intent-entry">
      <div>
        <span class="eyebrow">随时说出你的想法</span>
        <h2>有哪里不明白，或想试试自己？</h2>
        <p>围绕眼前的题，也围绕我们对学习情况的理解。</p>
      </div>
      <button class="intent-entry-button" @click="openConversation('student', state.space)">
        <Icon name="chat" /><span
          >直接和 DeerMind 说说<small>文字表达 · 情景示例 · 保留当前上下文</small></span
        ><Icon name="arrow" />
      </button>
      <div class="entry-shortcuts">
        <button class="text-button" @click="go('upload')">
          <Icon name="camera" :size="17" />拍题 / 上传资料</button
        ><button class="text-button" @click="go('book')">章节讲解</button
        ><button class="text-button" @click="plan()">从教材选择自测</button>
      </div>
    </section>
    <section v-if="savedLessons.length" class="lesson-resume card" aria-label="保留的章节讲解">
      <strong>上次的讲解，还在这里</strong>
      <button v-for="l in savedLessons" :key="l.id" class="text-button" @click="openKnowledge(l.chapter)">
        {{ lessonState.records.school[l.id]?.ended ? '回看' : '继续' }}{{ l.chapter }}
        <Icon name="arrow" :size="15" />
      </button>
    </section>
    <LearnerOverview role="student" compact />
    <div class="section-title">
      <h2>接着上次的思路</h2>
      <button class="text-button" @click="go('materials')">
        我的资料 <Icon name="arrow" :size="16" />
      </button>
    </div>
    <section class="resume-strip card">
      <Icon name="folder" />
      <div>
        <strong>{{ visible ? '回到当前资料，接着讨论' : '添加一份资料，从实际问题开始' }}</strong>
        <p>学习判断会随着有效的新表现更新，不需要为了补满状态而反复测验。</p>
      </div>
      <button class="button secondary" @click="visible ? openQuestion(2) : go('upload')">
        {{ visible ? '继续查看题目' : '添加学习资料' }}
      </button>
    </section>
    <section v-if="item.notice" class="banner">
      <Icon name="bell" />
      <div>
        <strong>一条作答记录已更正</strong>
        <p>
          分数除法题的识别结果已更新，相关判断一并复核。{{
            item.hidden ? '已删除的原资料不会重新显示。' : '可以回到试卷查看具体变化。'
          }}
        </p>
      </div>
      <button v-if="!item.hidden" class="text-button" @click="go('exam')">查看</button>
    </section>
  </template>
  <LessonWorkspace v-else-if="page === 'lesson'" />
  <template v-else-if="page === 'upload'">
    <button class="back-link" @click="go('home')">← 返回学习首页</button>
    <div class="page-heading">
      <div>
        <span class="eyebrow">保留你的思考</span>
        <h1>把题目带过来</h1>
        <p>整份试卷可以一次提交，清晰的部分会先处理。</p>
      </div>
    </div>
    <div class="two-columns">
      <section class="card">
        <div class="tabs">
          <button :class="{ active: uploadKind === 'exam' }" @click="uploadKind = 'exam'">
            整份试卷</button
          ><button :class="{ active: uploadKind === 'single' }" @click="uploadKind = 'single'">
            独立错题
          </button>
        </div>
        <div class="upload-zone">
          <span class="upload-icon"><Icon name="upload" :size="32" /></span>
          <h3>照片、图片或 PDF</h3>
          <p>包含题目、图示和你写下的过程</p>
          <label class="button secondary file-button"
            >选择文件<input
              type="file"
              accept="image/*,application/pdf"
              multiple
              @change="pickFile"
          /></label>
          <p v-if="uploadedName" class="file-name">{{ uploadedName }}</p>
        </div>
        <div class="note">
          原型仅读取文件名，不上传或识别内容。以下使用固定示例题演示；每个空间只有一个演示资料槽，新导入会替换该槽的样例。
        </div>
        <button class="button primary full-width" @click="upload">
          {{
            uploadedName
              ? '用示例结果演示处理'
              : uploadKind === 'exam'
                ? '使用示例试卷继续'
                : '使用独立题示例继续'
          }}<Icon name="arrow" :size="17" />
        </button>
      </section>
      <section class="card quiet">
        <span class="eyebrow">本次资料</span>
        <h3>{{ space.name }} · 单元练习</h3>
        <ol class="steps">
          <li>保留原题和原作答</li>
          <li>不清楚的地方，局部确认</li>
          <li>确认答错的题，自动进入错题本</li>
          <li>你可以随时选择讲解或复测</li>
        </ol>
        <p class="muted">上传后可以离开页面，回来查看原任务。课程空间之间的材料不会混用。</p>
      </section>
    </div>
  </template>
  <template v-else-if="page === 'materials' || page === 'exam'">
    <div class="page-heading">
      <div>
        <span class="eyebrow">{{ space.name }} / 我的资料</span>
        <h1>{{ page === 'exam' ? '看见每一步的思路' : '留下题目，找回思路' }}</h1>
        <p>原来的作答与后来的理解，分别保留。</p>
      </div>
      <button class="button primary" @click="go('upload')">
        <Icon name="plus" :size="17" />添加资料
      </button>
    </div>
    <div v-if="!item.imported || item.hidden" class="card empty">
      <Icon name="folder" :size="40" />
      <h2>{{ item.hidden ? '这份资料已从你的界面移除' : '这里还没有学习资料' }}</h2>
      <p>
        {{
          item.hidden
            ? '相关错题和原作答也已隐藏，不能恢复。可以添加其他资料继续学习。'
            : '上传一道错题或一份试卷，开始整理自己的思路。'
        }}
      </p>
      <button class="button secondary" @click="go('upload')">添加资料</button>
    </div>
    <section v-else-if="item.processing" class="card empty">
      <span class="spinner" />
      <h2>正在整理题目与作答</h2>
      <p>原任务已接收，可以先离开，稍后回来查看。</p>
      <button class="button secondary" @click="go('home')">先回首页</button>
    </section>
    <section v-else-if="item.failure" class="card empty">
      <Icon name="info" :size="36" />
      <h2>这次处理没有完成</h2>
      <p>已保留原任务和资料，无需重新拍照。可在走查工具恢复正常状态后重试。</p>
      <button class="button primary" @click="retryExam">重试原任务</button>
    </section>
    <template v-else
      ><section class="exam-summary card">
        <div class="document-cover">
          <Icon name="book" :size="32" /><span>{{
            item.kind === 'single' ? '独立题' : '单元练习'
          }}</span>
        </div>
        <div>
          <span class="eyebrow">{{ item.sourceName }}</span>
          <h2>{{ space.chapter }} · 练习回顾</h2>
          <p>
            {{ materialQuestions.length }} 道示例题 · {{ wrongs.length }} 道确认错题{{
              item.unclear ? ' · 1 道待确认' : ''
            }}
          </p>
          <span class="muted">这是当次作答反馈，不代表整章掌握情况。</span>
        </div>
        <button
          class="icon-button delete-material"
          :aria-label="item.kind === 'exam' ? '删除整份试卷' : '删除独立题'"
          @click="modal = 'delete'"
        >
          <Icon name="trash" />
        </button>
      </section>
      <div v-if="item.corrected" class="banner">
        第 2 题识别已更正：原识别为 3/8，示例原件为 3/2。原作答与更正记录分别保留。
      </div>
      <div class="tabs">
        <button :class="{ active: tab === 'all' }" @click="tab = 'all'">
          全部题目 <span>{{ materialQuestions.length }}</span></button
        ><button :class="{ active: tab === 'wrong' }" @click="tab = 'wrong'">
          确认错题 <span>{{ wrongs.length }}</span>
        </button>
      </div>
      <div class="question-list">
        <button
          v-for="q in filtered"
          :key="q.id"
          class="question-row card"
          @click="openQuestion(list.indexOf(q))"
        >
          <span class="question-number">{{ String(list.indexOf(q) + 1).padStart(2, '0') }}</span>
          <div>
            <span class="tag" :class="questionStatus(list.indexOf(q))">{{
              statusText[questionStatus(list.indexOf(q))]
            }}</span>
            <h3>{{ q.prompt }}</h3>
            <p>{{ q.topic }} · 来源：单元练习</p>
          </div>
          <Icon name="chevron" />
        </button>
      </div>
      <p class="muted footnote">
        确认错题已自动归集。试卷和错题入口对应同一次作答，不重复累计表现。
      </p></template
    >
  </template>
  <template v-else-if="page === 'question'">
    <button class="back-link" @click="go(isTest ? 'results' : 'exam')">
      {{ isTest ? '← 返回本次检测结果' : '← 返回资料回顾' }}
    </button>
    <section v-if="!visible && !isTest" class="card empty">
      <h2>当前材料不可查看</h2>
      <p>资料可能已删除、尚未处理完成或处理失败。</p>
      <button class="button secondary" @click="go('materials')">返回我的资料</button>
    </section>
    <template v-else
      ><div class="page-heading compact">
        <div>
          <span class="eyebrow">{{ space.name }} / {{ question.topic }}</span>
          <h1>先把问题看清楚</h1>
        </div>
        <span v-if="!isTest" class="tag" :class="questionStatus(item.selectedQuestion)">{{
          statusText[questionStatus(item.selectedQuestion)]
        }}</span
        ><span v-else class="tag neutral">检测已结束 · 教学帮助</span>
      </div>
      <div class="question-workspace">
        <section class="card problem-card">
          <div class="section-title">
            <h2>题目 {{ item.selectedQuestion + 1 }}</h2>
            <span class="muted">示例原题</span>
          </div>
          <p class="problem-text">{{ question.prompt }}</p>
          <div v-if="question.id === 'S-Q3'" class="math-diagram">
            <span>原价 · 100%</span>
            <div class="percent-bar"><i>现价 160 元 · 80%</i><b>20%</b></div>
            <small>先找出哪个量是整体</small>
          </div>
          <div class="original-work">
            <span class="eyebrow">当时的作答</span>
            <p>
              {{
                isTest
                  ? item.test.answers[item.test.index] || item.test.draft || '尚未提交作答'
                  : item.corrected && item.selectedQuestion === 1
                    ? '3/4 ÷ 1/2 = 3/2'
                    : question.work
              }}
            </p>
            <small>{{
              item.corrected && item.selectedQuestion === 1
                ? '依据原件更正了识别，原识别记录保留。'
                : '保留原来的思路，后续练习不会覆盖它。'
            }}</small>
          </div>
          <button
            v-if="!isTest && state.space === 'school' && item.kind === 'exam'"
            class="text-button"
            @click="modal = 'correction'"
          >
            识别或判断有问题？
          </button>
          <div class="divider" />
          <label class="field"
            >写下现在的思路<textarea
              v-model="work.draft"
              placeholder="可以先写已知条件，或者说说卡在哪里……"
            /></label
          ><WritingPad v-model="work.strokes" />
          <div class="actions">
            <button
              class="button secondary"
              @click="
                voiceState = 'preview';
                voice = '我想知道，为什么这里要用除法？';
              "
            >
              <Icon name="mic" :size="17" />语音输入演示</button
            ><button class="button secondary" @click="submitPractice">保存练习作答</button>
          </div>
          <div v-if="voiceState === 'preview'" class="note">
            <label class="field">转写预览（模拟录音）<textarea v-model="voice" /></label>
            <div class="actions">
              <button
                class="text-button"
                @click="
                  voiceState = 'idle';
                  voice = '';
                "
              >
                取消</button
              ><button
                class="button small primary"
                @click="
                  work.draft = voice;
                  voiceState = 'idle';
                  notify('已放入输入区；点击求助才展示示例回复');
                "
              >
                发送到输入区
              </button>
            </div>
          </div>
        </section>
        <section class="card explanation-card">
          <div class="section-title">
            <h2><Icon name="leaf" />一起想一想</h2>
            <span class="tag neutral">由你选择帮助</span>
          </div>
          <div v-if="help === 'none'" class="help-intro">
            <span class="help-symbol">?</span>
            <h3>这次需要怎样的帮助？</h3>
            <p>可以从一点提示开始，也可以直接看分步骤的讲解。</p>
            <div class="actions">
              <button class="button secondary" @click="requestHelp('hint')">只给提示</button
              ><button class="button primary" @click="requestHelp('explain')">讲讲这道题</button>
            </div>
          </div>
          <template v-else
            ><span class="eyebrow">{{ help === 'hint' ? '先想这一点' : '从数量关系开始' }}</span>
            <p v-if="help === 'hint'" class="hint-text">{{ question.hint }}</p>
            <ol v-else class="explanation-steps">
              <li v-for="(step, i) in question.explanation" :key="i">
                <span>{{ i + 1 }}</span>
                <p>{{ step }}</p>
              </li>
            </ol>
            <div class="actions">
              <button class="text-button" @click="play"><Icon name="play" :size="16" />播放</button
              ><button class="text-button" @click="stopAudio">停止播放</button
              ><button v-if="help === 'hint'" class="text-button" @click="requestHelp('explain')">
                看完整讲解
              </button>
            </div>
            <div class="note green">
              已经看过{{
                help === 'hint' ? '提示' : '讲解'
              }}。这说明获得了帮助，还需要自己的后续表现才能了解掌握情况。
            </div>
            <button class="button secondary full-width" @click="plan('retest')">
              我想检查一下理解</button
            ><button class="text-button full-width" @click="go('home')">
              今天先到这里
            </button></template
          >
        </section>
      </div></template
    >
  </template>
  <template v-else-if="page === 'book'">
    <div class="page-heading">
      <div>
        <span class="eyebrow">{{ space.name }} / 教材</span>
        <h1>从教材里，找到入口</h1>
        <p>课程内尚未学到的内容，也可以主动了解。</p>
      </div>
    </div>
    <section class="book-banner card">
      <div class="book-cover">
        <Icon name="book" :size="45" /><strong>数学</strong><small>示例教材</small>
      </div>
      <div>
        <span class="eyebrow">{{ space.subtitle }}</span>
        <h2>{{ space.book }}</h2>
        <p>目录与内容为原型样例，等待实际教材替换。</p>
        <span class="tag" :class="item.book === 'open' ? '' : 'amber'">{{
          item.book === 'open' ? '示例章节已开放' : '内容准备中'
        }}</span>
      </div>
    </section>
    <div class="question-list">
      <section class="card chapter-row" v-for="(chapter, i) in space.chapters" :key="chapter">
        <span class="question-number">0{{ i + 1 }}</span>
        <div>
          <h3>{{ chapter }}</h3>
          <p>
            {{
              item.book === 'open'
                ? '可浏览 · 可讲解 · 检测依据按题检查'
                : '等待管理员核对来源与适用功能'
            }}
          </p>
        </div>
        <button
          class="button secondary"
          :disabled="item.book !== 'open'"
          @click="openKnowledge(chapter)"
        >
          {{ lessonState.records[state.space][lessons.find((l) => l.chapter === chapter)?.id || '']?.ended ? '回看讲解' : lessonState.records[state.space][lessons.find((l) => l.chapter === chapter)?.id || ''] ? '继续讲解' : '打开章节' }}
        </button>
      </section>
    </div>
  </template>
  <template v-else-if="page === 'learning'">
    <div class="page-heading learning-page-heading">
      <div>
        <h1>学习情况</h1>
      </div>
      <button class="button primary" @click="plan()">从教材选择自测</button>
    </div>
    <LearnerOverview role="student" />
    <div v-if="item.test.stage === 'result'" class="card spaced">
      <h3>上一次检测</h3>
      <p>
        {{ item.test.reason }} · 已提交 {{ item.test.answers.length }} / {{ item.test.count }} 题
      </p>
      <button class="text-button" @click="go('results')">查看部分或完整结果</button>
    </div>
  </template>
  <template v-else-if="page === 'test' || page === 'results'">
    <template v-if="item.test.stage === 'plan'"
      ><div class="page-heading">
        <div>
          <span class="eyebrow">主动自测</span>
          <h1>这次，想检查哪一部分？</h1>
          <p>从当前教材选范围，先看安排，再决定开始。</p>
        </div>
      </div>
      <div class="two-columns">
        <section class="card">
          <h2>{{ space.book }}</h2>
          <label class="chapter-select" v-for="chapter in space.chapters" :key="chapter"
            ><input v-model="chosen" type="checkbox" :value="chapter" /><Icon name="book" /><span>{{
              chapter
            }}</span></label
          >
          <p class="muted">这里的题单为场景样例，真实选题计算留给工程实现。</p>
        </section>
        <section class="card quiet">
          <span class="eyebrow">本次安排</span>
          <h2>{{ chosen.length ? chosen.join('、') : '先选择一个范围' }}</h2>
          <p v-if="chosen.length">
            示例题单 {{ planned.length }} 题 · 参考用时 {{ planned.length * 3 }} 分钟
          </p>
          <p>检查所选任务的独立作答与关键理由。未覆盖的内容会单独说明，不承诺测完等于整章掌握。</p>
          <div class="note">
            提交后先不显示答案。中途求提示或讲解，会结束本次检测再转入教学，未做题记为未检测。
          </div>
          <button
            class="button primary full-width"
            :disabled="!chosen.length"
            @click="startTest(chosen)"
          >
            开始本次自测
          </button>
        </section>
      </div></template
    >
    <template v-else-if="item.test.stage === 'running'"
      ><div class="page-heading">
        <div>
          <span class="eyebrow">独立自测 · {{ item.test.chapters.join('、') }}</span>
          <h1>第 {{ item.test.index + 1 }} 题 / 共 {{ item.test.count }} 题</h1>
          <p>按自己的思路写，全部结束后再看反馈。</p>
        </div>
        <button class="text-button" @click="modal = 'end-test'">结束本次检测</button>
      </div>
      <section class="card test-card">
        <div class="progress-track">
          <i :style="{ width: `${(item.test.answers.length / item.test.count) * 100}%` }" />
        </div>
        <p class="problem-text">{{ testQuestion.prompt }}</p>
        <label class="field"
          >我的作答<textarea v-model="item.test.draft" placeholder="写下答案与必要的思路……" />
        </label>
        <p class="muted" v-if="item.test.answers.length">
          前 {{ item.test.answers.length }} 题已收到，尚未展示对错。
        </p>
        <div class="actions">
          <button class="button secondary" @click="modal = 'test-help'">结束检测并求讲解</button
          ><button class="button primary" @click="submitTest">
            {{ item.test.index + 1 === item.test.count ? '提交并结束' : '提交，进入下一题'
            }}<Icon name="arrow" :size="16" />
          </button>
        </div></section
    ></template>
    <template v-else
      ><div class="page-heading">
        <div>
          <span class="eyebrow">本次检测结果</span>
          <h1>把已经完成的部分留下来</h1>
          <p>{{ item.test.reason }}，未做的部分仍是未检测。</p>
        </div>
      </div>
      <section class="card">
        <div class="result-stats">
          <div>
            <strong>{{ item.test.answers.length }}</strong
            ><span>已提交</span>
          </div>
          <div>
            <strong>{{ item.test.count - item.test.answers.length }}</strong
            ><span>未检测</span>
          </div>
          <div><strong>待核验</strong><span>任意输入不作真实判题</span></div>
        </div>
        <div class="note">
          原型保留你输入的作答并演示结果结构，不根据这些输入生成真实正确率或掌握判断。
        </div>
        <div v-for="(answer, i) in item.test.answers" :key="i" class="result-answer">
          <strong>第 {{ i + 1 }} 题</strong>
          <p>{{ answer }}</p>
          <span class="tag neutral">已记录 · 待核验</span>
        </div>
        <div v-if="item.test.draft" class="note">未提交草稿：{{ item.test.draft }}</div>
        <div class="actions">
          <button class="button primary" @click="go('learning')">回到学习情况</button
          ><button class="button secondary" @click="plan()">另开一次检测</button>
        </div>
      </section></template
    >
  </template>
  <template v-else-if="page === 'settings'"
    ><div class="page-heading">
      <div>
        <span class="eyebrow">账号与设置</span>
        <h1>我的学习空间</h1>
      </div>
    </div>
    <section class="card">
      <div class="profile-line">
        <span class="avatar large">禾</span>
        <div>
          <h2>小禾（示例学习者）</h2>
          <p>稳定学习档案 DEMO-L01</p>
        </div>
      </div>
      <div class="setting-row">
        <div>
          <strong>当前关联的家长</strong>
          <p>
            {{
              state.linked
                ? '示例家长 · 可以查看相关学习依据，不能从家长端改动你的资料'
                : '当前没有有效关联的家长'
            }}
          </p>
        </div>
      </div>
      <div class="setting-row">
        <div>
          <strong>资料保留与删除</strong>
          <p>界面删除后不能恢复，内部记录仍按确认范围保留和使用；关联家长仍可查看相关依据。</p>
        </div>
      </div>
      <div class="setting-row">
        <div>
          <strong>忘记密码或关联有误</strong>
          <p>联系管理员，核实后恢复原账号，不新建学习历史。</p>
        </div>
      </div>
      <p class="muted">当前为原型身份，未连接真实账号系统。</p>
    </section></template
  >
  <template v-else
    ><section class="card empty">
      <h2>从学习首页继续</h2>
      <button class="button primary" @click="go('home')">学习首页</button>
    </section></template
  >
  <Modal
    v-if="modal === 'delete'"
    :title="item.kind === 'exam' ? '删除整份试卷？' : '删除这道独立题？'"
    @close="modal = ''"
    ><p>
      将从你的界面移除“{{ item.sourceName }}”，包括关联错题和原作答，不能恢复。{{
        item.kind === 'exam' ? '首版不单独删除卷内某一道题。' : '独立上传题可以单独删除。'
      }}
    </p>
    <p class="note">内部学习记录仍保留并用于获准分析，关联家长仍可在相关依据中查看。</p>
    <div class="actions">
      <button class="button secondary" @click="modal = ''">保留资料</button
      ><button
        class="button danger"
        @click="
          deleteExam();
          modal = '';
          go('materials');
        "
      >
        {{ item.kind === 'exam' ? '确认删除整卷' : '确认删除独立题' }}
      </button>
    </div></Modal
  >
  <Modal v-if="modal === 'correction'" title="核对原件与识别" @close="modal = ''"
    ><p>演示问题：第 2 题的原件写的是 3/2，系统识别成了 3/8。其他输入不会在原型中自动判断对错。</p>
    <div class="compare-box">
      <div><small>原识别</small><strong>3/8</strong></div>
      <Icon name="arrow" />
      <div><small>示例原件</small><strong>3/2</strong></div>
    </div>
    <label class="field">问题说明<textarea placeholder="说明哪个位置需要复核（演示输入）" /></label>
    <div class="actions">
      <button class="button secondary" @click="modal = ''">取消</button
      ><button
        class="button primary"
        @click="
          reportIssue();
          modal = '';
        "
      >
        提交复核
      </button>
    </div>
    <p class="muted">提交是问题线索，不直接改写掌握判断。可在管理员端继续处理此事项。</p></Modal
  >
  <Modal
    v-if="modal === 'test-help' || modal === 'end-test'"
    :title="modal === 'test-help' ? '结束检测，转入讲解？' : '结束本次检测？'"
    @close="modal = ''"
    ><p>
      已提交的 {{ item.test.answers.length }} 道题和当前草稿会保留，剩余题目记为未检测。{{
        modal === 'test-help'
          ? '之后可以另开一次检测，实际获得的帮助仍会保留。'
          : '没有完成不代表不会。'
      }}
    </p>
    <div class="actions">
      <button class="button secondary" @click="modal = ''">继续独立作答</button
      ><button
        class="button primary"
        @click="modal === 'test-help' ? helpDuringTest() : (endTest('主动结束'), (modal = ''))"
      >
        {{ modal === 'test-help' ? '结束并讲解' : '确认结束' }}
      </button>
    </div></Modal
  >
  <Modal v-if="modal === 'knowledge'" title="想了解哪个知识点？" @close="modal = ''"
    ><p>原型先提供当前课程的固定知识讲解样例，不解析任意问题。</p>
    <section class="note">
      <h3>{{ knowledgeChapter }}</h3>
      <p>{{ knowledgeText[knowledgeChapter] }}</p>
    </section>
    <p>讲解之后，你可以选择继续追问、找一道例题，或先结束，不需要先做测试。</p>
    <button class="button primary" @click="modal = ''">先理解到这里</button></Modal
  >
</template>
