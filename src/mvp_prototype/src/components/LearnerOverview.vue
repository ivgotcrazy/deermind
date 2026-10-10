<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { current, state } from '../store';
import { spaces } from '../data';
import { chapterViews, type ChapterView } from '../chapterView';
import { conversation, openChapterConversation, type Intent } from '../conversation';
import Icon from './Icon.vue';
import Modal from './Modal.vue';

const props = defineProps<{ role: 'student' | 'parent'; compact?: boolean }>();
const router = useRouter();
const item = computed(current);
const chapters = computed(chapterViews);
const selected = ref('');
const filter = ref<'all' | 'wrong' | 'unclear' | 'empty'>('all');
const detailTab = ref<'summary' | 'records' | 'next'>('summary');
const recordFilter = ref<'all' | 'wrong' | 'unclear'>('all');
const rulesOpen = ref(false);
const sourceIndex = ref<number | null>(null);
const root = ref<HTMLElement>();
const testing = computed(() => props.role === 'student' && item.value.test.stage === 'running');
const totals = computed(() =>
  chapters.value.reduce(
    (sum, c) => ({
      total: sum.total + c.records.length,
      correct: sum.correct + c.correct,
      wrong: sum.wrong + c.wrong,
      unclear: sum.unclear + c.unclear,
      recorded: sum.recorded + Number(c.hasRecord),
      submitted: sum.submitted + c.submitted,
    }),
    { total: 0, correct: 0, wrong: 0, unclear: 0, recorded: 0, submitted: 0 },
  ),
);
const judged = computed(() => totals.value.correct + totals.value.wrong);
const rate = computed(() =>
  judged.value ? Math.round((totals.value.correct / judged.value) * 100) : null,
);
const filters = computed(() => [
  { id: 'all' as const, label: '全部章节', count: chapters.value.length },
  { id: 'wrong' as const, label: '有待回顾', count: chapters.value.filter((c) => c.wrong).length },
  {
    id: 'unclear' as const,
    label: '有待确认',
    count: chapters.value.filter((c) => c.unclear).length,
  },
  {
    id: 'empty' as const,
    label: '暂无记录',
    count: chapters.value.filter((c) => !c.hasRecord).length,
  },
]);
const shown = computed(() =>
  chapters.value.filter(
    (c) =>
      filter.value === 'all' ||
      (filter.value === 'wrong'
        ? c.wrong > 0
        : filter.value === 'unclear'
          ? c.unclear > 0
          : !c.hasRecord),
  ),
);
const canSeeSource = computed(() => props.role === 'parent' || !item.value.hidden);
const source = computed(() =>
  sourceIndex.value === null || !canSeeSource.value
    ? undefined
    : chapters.value.flatMap((c) => c.records).find((r) => r.index === sourceIndex.value),
);
const resultNames = { correct: '答对', wrong: '待回顾', unclear: '待确认' };
function clearFocus() {
  if (
    conversation.focus?.role === props.role &&
    conversation.focus.space === state.space &&
    conversation.focus.chapter === selected.value
  )
    conversation.focus = null;
}
watch(
  () => state.space,
  () => {
    selected.value = '';
    filter.value = 'all';
    sourceIndex.value = null;
    rulesOpen.value = false;
  },
);
onBeforeUnmount(clearFocus);
async function selectChapter(chapter: ChapterView) {
  if (selected.value === chapter.name) {
    clearFocus();
    selected.value = '';
    return;
  }
  selected.value = chapter.name;
  detailTab.value = 'summary';
  recordFilter.value = 'all';
  conversation.focus = { role: props.role, space: state.space, chapter: chapter.name };
  await nextTick();
  root.value
    ?.querySelector(`[data-chapter-index="${chapter.index}"]`)
    ?.scrollIntoView({ block: 'start', behavior: 'smooth' });
}
async function chooseFilter(value: typeof filter.value) {
  clearFocus();
  filter.value = value;
  selected.value = '';
  await nextTick();
  root.value
    ?.querySelector('.chapter-browser')
    ?.scrollIntoView({ block: 'start', behavior: 'smooth' });
}
function discuss(chapter: ChapterView, intent: Intent = 'basis') {
  openChapterConversation(props.role, state.space, chapter.name, intent);
}
function records(chapter: ChapterView) {
  return chapter.records.filter(
    (r) => recordFilter.value === 'all' || r.result === recordFilter.value,
  );
}
function viewRecords(value: typeof recordFilter.value) {
  recordFilter.value = value;
  detailTab.value = 'records';
}
function openQuestion() {
  if (!source.value || props.role !== 'student' || !canSeeSource.value) return;
  item.value.selectedQuestion = source.value.index;
  sourceIndex.value = null;
  void router.push('/student/question');
}
</script>
<template>
  <section ref="root" class="chapter-learning" :class="{ compact }" aria-label="按教材查看学习情况">
    <div v-if="testing" class="card learning-test-notice">
      <Icon name="edit" />
      <h2>先完成这次独立自测</h2>
      <p>结束后再查看章节反馈。已提交的作答和当前草稿会保留。</p>
      <button class="button primary" @click="router.push('/student/test')">继续当前自测</button>
    </div>
    <template v-else>
      <div class="learning-book-heading">
        <div>
          <span v-if="compact" class="eyebrow">{{ spaces[state.space].name }} / 按教材查看</span>
          <h2>{{ compact ? '这本教材，学得怎样' : spaces[state.space].book }}</h2>
        </div>
        <button class="learning-scope" @click="rulesOpen = true">
          <Icon name="info" :size="15" />当前演示资料 · 统计说明
        </button>
      </div>
      <div class="learning-metrics" aria-label="教材统计">
        <button class="learning-metric" @click="chooseFilter('all')">
          <span>有记录的章节</span
          ><strong
            >{{ totals.recorded }}<small>/ {{ chapters.length }} 章</small></strong
          >
          <small>看看记录覆盖了哪里 <Icon name="arrow" :size="13" /></small>
        </button>
        <button class="learning-metric" @click="rulesOpen = true">
          <span>资料答对率</span
          ><strong>{{ rate === null ? '—' : rate }}<small v-if="rate !== null">%</small></strong>
          <small
            >{{ totals.correct }} / {{ judged }} 题已判定答对 <Icon name="info" :size="13"
          /></small>
        </button>
        <button class="learning-metric attention" @click="chooseFilter('wrong')">
          <span>待回顾的题</span><strong>{{ totals.wrong }}<small>题</small></strong>
          <small>定位值得回顾的章节 <Icon name="arrow" :size="13" /></small>
        </button>
        <button class="learning-metric pending" @click="chooseFilter('unclear')">
          <span>待确认的题</span><strong>{{ totals.unclear }}<small>题</small></strong>
          <small>识别待核对，尚未判对错 <Icon name="arrow" :size="13" /></small>
        </button>
      </div>
      <p class="learning-scope-note">
        统计当前资料中的 {{ totals.total }} 道题；原作答的帮助条件未知，答对率不表示整章掌握程度。
      </p>
      <p v-if="totals.submitted" class="learning-pending-note">
        另收到 {{ totals.submitted }} 次检测作答，尚待核验，未计入上述答对率。
      </p>
      <div class="chapter-browser">
        <div class="chapter-list-heading">
          <h3>按章节看</h3>
          <span>按教材顺序 · 点章节展开详情</span>
        </div>
        <div class="chapter-filters" role="group" aria-label="筛选章节">
          <button
            v-for="option in filters"
            :key="option.id"
            :aria-pressed="filter === option.id"
            @click="chooseFilter(option.id)"
          >
            {{ option.label }}<span>{{ option.count }}</span>
          </button>
        </div>
        <div v-if="!shown.length" class="chapter-empty">
          <Icon name="check" :size="26" />
          <h3>{{ filter === 'empty' ? '每章都有一些记录' : '没有符合当前筛选的章节' }}</h3>
          <p>可以查看其他章节；没有待回顾的题，也不直接表示整章已经掌握。</p>
          <button class="text-button" @click="chooseFilter('all')">
            查看全部章节 <Icon name="arrow" :size="14" />
          </button>
        </div>
        <article
          v-for="chapter in shown"
          :key="chapter.name"
          class="learning-chapter"
          :class="{ expanded: selected === chapter.name }"
          :data-chapter-index="chapter.index"
          :data-tone="chapter.tone"
        >
          <button
            class="chapter-summary-button"
            :aria-label="`查看章节：${chapter.name}`"
            :aria-expanded="selected === chapter.name"
            :aria-controls="
              selected === chapter.name ? `chapter-detail-${chapter.index}` : undefined
            "
            @click="selectChapter(chapter)"
          >
            <span class="chapter-number">{{ String(chapter.index + 1).padStart(2, '0') }}</span>
            <span class="chapter-title"
              ><strong>{{ chapter.name }}</strong
              ><small><i class="chapter-status-dot" />{{ chapter.label }}</small></span
            >
            <span class="chapter-rate"
              ><strong>{{ chapter.rate === null ? '—' : `${chapter.rate}%` }}</strong
              ><small>资料答对率</small></span
            >
            <span class="chapter-counts">
              <span class="chapter-distribution" aria-hidden="true"
                ><i
                  v-for="(count, kind) in {
                    correct: chapter.correct,
                    wrong: chapter.wrong,
                    unclear: chapter.unclear,
                  }"
                  :key="kind"
                  :class="kind"
                  :style="{ flexGrow: count }"
              /></span>
              <small
                >答对 {{ chapter.correct }} · 待回顾 {{ chapter.wrong }} · 待确认
                {{ chapter.unclear }}</small
              >
            </span>
            <Icon class="chapter-expand-icon" name="chevron" :size="18" />
          </button>
          <section
            v-if="selected === chapter.name"
            :id="`chapter-detail-${chapter.index}`"
            class="chapter-detail"
            :aria-label="`${chapter.name}详情`"
          >
            <div class="chapter-detail-tabs" role="group" aria-label="章节详情内容">
              <button :aria-pressed="detailTab === 'summary'" @click="detailTab = 'summary'">
                当前情况
              </button>
              <button :aria-pressed="detailTab === 'records'" @click="detailTab = 'records'">
                相关题目 <span>{{ chapter.records.length }}</span>
              </button>
              <button :aria-pressed="detailTab === 'next'" @click="detailTab = 'next'">
                变化与建议
              </button>
            </div>
            <div v-if="detailTab === 'summary'" class="chapter-current">
              <div class="chapter-assessment">
                <span class="eyebrow">DEERMIND · 当前看到的情况</span>
                <h3>{{ chapter.summary }}</h3>
                <p>
                  这些记录能说明当次表现。能否独立解释、换题应用，以及过一段时间是否仍会做，还需要进一步了解。
                </p>
                <button class="text-button" @click="discuss(chapter)">
                  <Icon name="chat" :size="16" />为什么这样判断？
                </button>
              </div>
              <div class="chapter-breakdown" aria-label="本章记录分布">
                <button @click="viewRecords('all')">
                  <span>当前资料</span><b>{{ chapter.records.length }} 题</b
                  ><small>查看题目与原作答 <Icon name="arrow" :size="13" /></small>
                </button>
                <button @click="viewRecords('wrong')">
                  <span>其中待回顾</span><b>{{ chapter.wrong }} 题</b
                  ><small>只看待回顾的题 <Icon name="arrow" :size="13" /></small>
                </button>
                <div>
                  <span>查看过教学帮助</span><b>{{ chapter.helped }} 题</b
                  ><small>不计作帮助后答对</small>
                </div>
                <div>
                  <span>检测作答待核验</span><b>{{ chapter.submitted }} 次</b
                  ><small>未混入资料答对率</small>
                </div>
              </div>
            </div>
            <div v-else-if="detailTab === 'records'" class="chapter-records">
              <div class="chapter-record-filters" role="group" aria-label="筛选相关题目">
                <button :aria-pressed="recordFilter === 'all'" @click="recordFilter = 'all'">
                  全部 {{ chapter.records.length }}
                </button>
                <button :aria-pressed="recordFilter === 'wrong'" @click="recordFilter = 'wrong'">
                  待回顾 {{ chapter.wrong }}
                </button>
                <button
                  :aria-pressed="recordFilter === 'unclear'"
                  @click="recordFilter = 'unclear'"
                >
                  待确认 {{ chapter.unclear }}
                </button>
              </div>
              <p v-if="!canSeeSource" class="chapter-empty-source">
                来源资料已从你的界面删除，原题与原作答不再展示。当前统计与有效判断仍保留。
              </p>
              <template v-else>
                <p v-if="item.hidden" class="note">
                  学生已删除来源资料；这里仅提供本章相关依据的只读查看。
                </p>
                <button
                  v-for="record in records(chapter)"
                  :key="record.index"
                  class="chapter-record"
                  :aria-label="`查看相关题目：${record.question.topic}`"
                  @click="sourceIndex = record.index"
                >
                  <span class="chapter-record-number">{{
                    item.kind === 'single' ? '01' : String(record.index + 1).padStart(2, '0')
                  }}</span>
                  <span
                    ><strong>{{ record.question.prompt }}</strong
                    ><small>{{ item.sourceName }}</small></span
                  >
                  <span class="chapter-result" :class="record.result">{{
                    resultNames[record.result]
                  }}</span
                  ><Icon name="chevron" :size="16" />
                </button>
                <p v-if="!records(chapter).length" class="chapter-empty-source">
                  没有符合当前筛选的题目。
                </p>
              </template>
              <p v-if="chapter.submitted" class="learning-scope-note">
                本章另有 {{ chapter.submitted }} 次检测作答待核验，详情保留在本次检测结果中。
              </p>
            </div>
            <div v-else class="chapter-next">
              <div class="chapter-changes">
                <h3>记录发生了什么变化</h3>
                <p v-if="chapter.corrected">
                  <Icon
                    name="refresh"
                    :size="16"
                  />识别已纠正：相关题目现记为答对。这是记录修正，不表示刚刚学会。
                </p>
                <p v-if="chapter.helped">
                  <Icon name="book" :size="16" />本章
                  {{ chapter.helped }} 道题查看过帮助，尚无帮助后的独立验证结果。
                </p>
                <p v-if="chapter.submitted">
                  <Icon name="edit" :size="16" />收到 {{ chapter.submitted }} 次检测作答，尚待核验。
                </p>
                <p v-if="!chapter.corrected && !chapter.helped && !chapter.submitted">
                  当前只有资料中的当次表现，尚无可确认的学习变化。
                </p>
              </div>
              <div class="chapter-suggestion">
                <span class="eyebrow">可以考虑的下一步</span>
                <h3>
                  {{
                    chapter.unclear
                      ? '先把不清楚的记录核对好'
                      : chapter.wrong
                        ? '从本章的一道错题聊起'
                        : '围绕本章，说说你想了解什么'
                  }}
                </h3>
                <p>
                  {{
                    role === 'parent'
                      ? '可以先听听她具体卡在哪里，在她愿意时提供支持。家长咨询不会直接向孩子派发任务。'
                      : '可以先查看相关题目、讨论判断，或自愿安排一次章节自测。无需为了补满记录反复测试。'
                  }}
                </p>
                <div class="actions">
                  <button
                    class="button secondary"
                    @click="discuss(chapter, role === 'parent' ? 'support' : 'basis')"
                  >
                    {{ role === 'parent' ? '我可以怎样支持' : '聊聊这一章' }}
                  </button>
                  <button
                    v-if="role === 'student'"
                    class="button primary"
                    @click="discuss(chapter, 'verify')"
                  >
                    看看本章自测安排
                  </button>
                </div>
              </div>
            </div>
          </section>
        </article>
      </div>
    </template>
  </section>
  <Modal v-if="rulesOpen" title="这些数字怎么算" @close="rulesOpen = false">
    <dl class="judgment-detail">
      <dt>统计范围</dt>
      <dd>
        当前课程空间、当前演示资料中的题目。每题计一次，不跨课程合并。原型每个空间只有一个资料槽，新上传会替换该槽。
      </dd>
      <dt>资料答对率</dt>
      <dd>
        已确认答对题数 ÷ 已判定题数。待确认的题不进入分母；没有已判定作答时显示“—”，不显示 0%。
      </dd>
      <dt>有记录的章节</dt>
      <dd>存在资料题目、已提交检测作答或教学帮助记录的章节数。有记录不等于整章已了解或已掌握。</dd>
      <dt>帮助与检测作答</dt>
      <dd>
        原资料作答时是否有外部帮助尚不明确。查看过提示或讲解不计作答对；新提交的任意作答尚未核验，不计入正确率。
      </dd>
      <dt>用途</dt>
      <dd>
        这些数字帮助你查看学习记录，不是章节综合分，也不反向改写学习判断。识别纠正会更新统计；从学生界面删除资料不会清除内部有效依据。
      </dd>
    </dl>
  </Modal>
  <Modal v-if="source && !testing" title="本章相关作答" @close="sourceIndex = null">
    <span class="tag">{{ resultNames[source.result] }}</span>
    <p class="chapter-source-prompt">{{ source.question.prompt }}</p>
    <div class="original-work">
      <small
        >识别作答{{
          item.corrected && source.index === 1 && state.space === 'school' ? ' · 已纠正' : ''
        }}</small
      >
      <p>
        {{
          item.corrected && source.index === 1 && state.space === 'school'
            ? '3/4 ÷ 1/2 = 3/2'
            : source.question.work
        }}
      </p>
    </div>
    <p>
      原作答的帮助条件未知。{{
        source.result === 'unclear'
          ? '这段识别尚待核对，暂未用于判断对错。'
          : '本题结果不直接代表整章掌握。'
      }}
    </p>
    <p v-if="item.hidden" class="note">
      学生已删除原资料，家长按相关依据权限只读查看，不能恢复或修改。
    </p>
    <button v-if="role === 'student'" class="button primary" @click="openQuestion">
      打开题目，继续学习
    </button>
    <p v-else class="muted">家长只读；资料录入与更正在学生端完成。</p>
  </Modal>
</template>
