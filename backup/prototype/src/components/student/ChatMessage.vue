<script setup lang="ts">
import { ref } from 'vue'
import { useStudentChat, type ChatMsg } from '@/stores/studentChat'
import { explainContent, quizQuestions, reviewQuestions, variantQuestion, migrationQuestion } from '@/data/studentMock'
import DeerAvatar from '@/components/DeerAvatar.vue'
import Icon from '@/components/Icon.vue'

defineProps<{ msg: ChatMsg }>()
const store = useStudentChat()

/* ---------- 讲解卡 ---------- */
const angle = ref(0)
const tts = ref(false)

/* ---------- 检验卡（全对 → 证据入账 + 变式引导，单次全对不直接掌握） ---------- */
const quizSel = ref<(number | null)[]>(quizQuestions.map(() => null))
const quizChecked = ref(false)
const quizPass = ref(false)
function checkQuiz() {
  if (quizChecked.value) return
  quizChecked.value = true
  quizPass.value = quizQuestions.every((q, i) => q.answer === quizSel.value[i])
  store.onQuizDone(quizPass.value)
}

/* ---------- 间隔复习卡（延迟复习，SHORT 保持） ---------- */
const reviewSel = ref<(number | null)[]>(reviewQuestions.map(() => null))
const reviewChecked = ref(false)
const reviewPass = ref(false)
function checkReview() {
  if (reviewChecked.value) return
  reviewChecked.value = true
  reviewPass.value = reviewQuestions.every((q, i) => q.answer === reviewSel.value[i])
  store.onReviewDone(reviewPass.value)
}

/* ---------- 变式卡（即时迁移 LEARNING→SHORT） ---------- */
const variantSel = ref<number | null>(null)
const variantIdea = ref('')
const variantChecked = ref(false)
const variantPass = ref(false)
function submitVariant() {
  if (variantChecked.value) return
  variantChecked.value = true
  variantPass.value = variantSel.value === variantQuestion.answer && variantIdea.value.trim().length > 0
  store.onVariantDone(variantPass.value)
}

/* ---------- 迁移题卡（高价值迁移 SHORT→STABLE） ---------- */
const migrSel = ref<number | null>(null)
const migrIdea = ref('')
const migrChecked = ref(false)
const migrPass = ref(false)
function submitMigration() {
  if (migrChecked.value) return
  migrChecked.value = true
  migrPass.value = migrSel.value === migrationQuestion.answer && migrIdea.value.trim().length > 0
  store.onMigrationDone(migrPass.value)
}
</script>

<template>
  <!-- 用户气泡 -->
  <div v-if="msg.role === 'user'" class="row user">
    <div class="bubble user">{{ msg.text }}</div>
  </div>

  <!-- 小鹿文字 / 卡片 -->
  <div v-else class="row bot">
    <div class="avatar"><DeerAvatar :size="30" /></div>
    <div class="col">
      <div v-if="msg.text" class="bubble bot">{{ msg.text }}</div>

      <!-- 今日任务卡（从共享掌握度状态派生，四态联动；UNKNOWN 不进卡） -->
      <div v-if="msg.card === 'task'" class="card">
        <div class="card-title"><Icon name="calendar" :size="16" /> 今日安排（最省时方案）</div>
        <template v-if="store.plan.review.length">
          <div class="task-item">
            <span class="tag tag-review">待复习</span>
            <span class="task-kp">{{ store.plan.review[0].kp }}</span>
            <span class="task-note">{{ store.plan.review[0].day }}</span>
          </div>
        </template>
        <template v-if="store.plan.migration.length">
          <div class="task-item">
            <span class="tag tag-migration">待迁移</span>
            <span class="task-kp">{{ store.plan.migration[0].kp }}</span>
            <span class="task-note">迁移题 · 验证稳定性</span>
          </div>
        </template>
        <template v-if="store.plan.consolidate.length">
          <div class="task-item">
            <span class="tag tag-learn">继续巩固</span>
            <span class="task-kp">{{ store.plan.consolidate[0].kp }}</span>
            <span class="task-note">{{ store.plan.consolidate[0].note }}</span>
          </div>
        </template>
        <template v-if="store.plan.mastered.length">
          <div class="task-item mastered">
            <span class="tag tag-mastered">已掌握</span>
            <span class="task-kp">{{ store.plan.mastered.slice(0, 2).join('、') }}</span>
            <span class="task-note">今天不用学</span>
          </div>
        </template>
        <div v-if="store.todaySummary.done" class="task-empty">
          今天没有需要你继续处理的数学问题，可以去玩啦
        </div>
      </div>

      <!-- 讲解卡（讲知识点） -->
      <div v-if="msg.card === 'explain'" class="card">
        <div class="card-title">{{ msg.kpName }} <span class="src">来源 · {{ explainContent.source }}</span></div>
        <div class="tabs">
          <button
            v-for="(a, i) in explainContent.angles"
            :key="i"
            class="tab"
            :class="{ on: angle === i }"
            @click="angle = i"
          >
            {{ a.title }}
          </button>
        </div>
        <p class="explain-text">{{ explainContent.angles[angle].text }}</p>
        <div class="card-actions">
          <button class="ghost" :class="{ playing: tts }" @click="tts = !tts">
            <Icon :name="tts ? 'volumeOff' : 'speaker'" :size="16" />
            {{ tts ? '朗读中…' : '朗读' }}
          </button>
          <button class="ghost" @click="store.quick('quiz')">考考我</button>
        </div>
      </div>

      <!-- 检验卡（对话内答题） -->
      <div v-if="msg.card === 'quiz'" class="card">
        <div class="card-title">检验 · {{ explainContent.kp }}</div>
        <div v-for="(q, i) in quizQuestions" :key="i" class="quiz-item">
          <div class="quiz-q">{{ i + 1 }}. {{ q.q }}</div>
          <div class="quiz-opts">
            <button
              v-for="(o, j) in q.options"
              :key="j"
              class="opt"
              :class="{
                sel: quizSel[i] === j,
                right: quizChecked && q.answer === j,
                wrong: quizChecked && quizSel[i] === j && q.answer !== j,
              }"
              :disabled="quizChecked"
              @click="quizSel[i] = j"
            >
              {{ o }}
            </button>
          </div>
        </div>
        <div class="card-actions">
          <button class="primary" :disabled="quizChecked || quizSel.some((s) => s === null)" @click="checkQuiz">
            提交
          </button>
        </div>
        <div v-if="quizChecked && quizPass" class="result pass">全对！证据已入账 ✓（再做一道变式验证稳定性）</div>
        <div v-if="quizChecked && !quizPass" class="result fail">有两道要再巩固，我们再讲讲？</div>
      </div>

      <!-- 复习卡（间隔复习） -->
      <div v-if="msg.card === 'review'" class="card">
        <div class="card-title">间隔复习 · 第 1 天</div>
        <div v-for="(q, i) in reviewQuestions" :key="i" class="quiz-item">
          <div class="quiz-q">{{ q.q }}</div>
          <div class="quiz-opts">
            <button
              v-for="(o, j) in q.options"
              :key="j"
              class="opt"
              :class="{
                sel: reviewSel[i] === j,
                right: reviewChecked && q.answer === j,
                wrong: reviewChecked && reviewSel[i] === j && q.answer !== j,
              }"
              :disabled="reviewChecked"
              @click="reviewSel[i] = j"
            >
              {{ o }}
            </button>
          </div>
        </div>
        <div class="card-actions">
          <button class="primary" :disabled="reviewChecked || reviewSel.some((s) => s === null)" @click="checkReview">
            提交
          </button>
        </div>
        <div v-if="reviewChecked && reviewPass" class="result pass">复习通过！距离稳定掌握又近一步 ✓</div>
        <div v-if="reviewChecked && !reviewPass" class="result fail">没答对没关系，我们回看讲解～</div>
      </div>

      <!-- 变式卡（即时迁移 LEARNING→SHORT，§12） -->
      <div v-if="msg.card === 'variant'" class="card">
        <div class="card-title">变式 · 即时迁移 <span class="src">{{ msg.kpName }}</span></div>
        <p class="quiz-q">{{ variantQuestion.q }}</p>
        <div class="quiz-opts">
          <button
            v-for="(o, j) in variantQuestion.options"
            :key="j"
            class="opt"
            :class="{
              sel: variantSel === j,
              right: variantChecked && variantQuestion.answer === j,
              wrong: variantChecked && variantSel === j && variantQuestion.answer !== j,
            }"
            :disabled="variantChecked"
            @click="variantSel = j"
          >
            {{ o }}
          </button>
        </div>
        <p class="att-q">用一句话说说你的思路：</p>
        <textarea v-model="variantIdea" rows="2" placeholder="120 × 1/4，先约分再算…"></textarea>
        <div class="card-actions">
          <button
            class="primary"
            :disabled="variantChecked || variantSel === null || !variantIdea.trim()"
            @click="submitVariant"
          >
            提交
          </button>
        </div>
        <div v-if="variantChecked && variantPass" class="result pass">变式通过 → 证据入账 ✓</div>
        <div v-if="variantChecked && !variantPass" class="result fail">没答对，先回看讲解巩固一下～</div>
      </div>

      <!-- 迁移题卡（高价值迁移 SHORT→STABLE，§12） -->
      <div v-if="msg.card === 'migration'" class="card">
        <div class="card-title">迁移题 · 高价值迁移 <span class="src">{{ msg.kpName }}</span></div>
        <p class="quiz-q">{{ migrationQuestion.q }}</p>
        <div class="quiz-opts">
          <button
            v-for="(o, j) in migrationQuestion.options"
            :key="j"
            class="opt"
            :class="{
              sel: migrSel === j,
              right: migrChecked && migrationQuestion.answer === j,
              wrong: migrChecked && migrSel === j && migrationQuestion.answer !== j,
            }"
            :disabled="migrChecked"
            @click="migrSel = j"
          >
            {{ o }}
          </button>
        </div>
        <p class="att-q">用一句话说说你的思路：</p>
        <textarea v-model="migrIdea" rows="2" placeholder="4/5 × 3/4，先约分再算…"></textarea>
        <div class="card-actions">
          <button
            class="primary"
            :disabled="migrChecked || migrSel === null || !migrIdea.trim()"
            @click="submitMigration"
          >
            提交
          </button>
        </div>
        <div v-if="migrChecked && migrPass" class="result pass">迁移通过 → 稳定性验证 ✓</div>
        <div v-if="migrChecked && !migrPass" class="result fail">没答对，先回看讲解巩固一下～</div>
      </div>

      <!-- 短期掌握卡（减负） -->
      <div v-if="msg.card === 'mastery-short'" class="card mastery">
        <div class="card-title">「{{ msg.kpName }}」已短期掌握</div>
        <div class="mastery-body">今天先不用再花时间练啦，把时间留给你自己。接下来按遗忘曲线安排复习，再做一道迁移题验证稳定性～</div>
      </div>

      <!-- 稳定掌握卡 -->
      <div v-if="msg.card === 'mastery-stable'" class="card mastery stable">
        <div class="card-title">「{{ msg.kpName }}」稳定掌握</div>
        <div class="mastery-body">掌握的证据已经足够，这个知识点不用再花时间练了～</div>
      </div>

      <!-- 停止卡（减负 · 停止语义 §20.9） -->
      <div v-if="msg.card === 'stop'" class="card stop">
        <div class="card-title">今天的数学搞定啦</div>
        <div class="mastery-body">今天没有需要你继续处理的数学问题，可以去玩啦～</div>
      </div>

      <!-- 建议卡（重流程引导 / 聊天边界拉回） -->
      <div v-if="msg.card === 'suggest'" class="card suggest">
        <div class="card-title">小鹿建议</div>
        <div class="card-actions">
          <button v-if="msg.kpName === undefined" class="ghost" @click="store.quick('quiz')">先做两道题</button>
          <button class="ghost" @click="store.quick('task')">看今日安排</button>
        </div>
      </div>

      <!-- 鼓励卡（掌握确认） -->
      <div v-if="msg.card === 'good'" class="card good">
        <div class="card-title">太棒了！</div>
        <div class="mastery-body">今天到这里就很棒啦，剩下的时间好好玩～</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.row {
  display: flex;
  gap: 8px;
  align-items: flex-start;
}
.row.bot {
  animation: msg-in 0.3s ease-out;
}
@keyframes msg-in {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
.row.user {
  justify-content: flex-end;
}
.avatar {
  flex: 0 0 auto;
  margin-top: 2px;
}
.col {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-width: 86%;
}
.bubble {
  padding: 10px 14px;
  border-radius: 18px;
  font-size: 15px;
  line-height: 1.6;
}
.bubble.bot {
  background: var(--color-white);
  box-shadow: var(--shadow-clay);
}
.bubble.user {
  background: var(--color-primary);
  color: #fff;
  box-shadow: var(--shadow-clay);
}
.card {
  background: var(--color-white);
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-clay);
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-width: 300px;
  max-width: 100%;
}
.card-title {
  font-family: var(--font-head);
  font-weight: 700;
  font-size: 15px;
  color: var(--color-text);
  display: flex;
  align-items: baseline;
  gap: 8px;
  flex-wrap: wrap;
}
.src {
  font-size: 12px;
  font-weight: 400;
  color: var(--color-secondary);
}
.task-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 12px;
  background: var(--color-primary-soft);
}
.task-item.mastered {
  background: var(--color-cta-soft);
}
.tag {
  font-size: 11px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 999px;
  flex: 0 0 auto;
}
.tag-review {
  background: var(--color-warning-soft);
  color: var(--color-warning);
}
.tag-learn {
  background: var(--color-secondary-soft);
  color: var(--color-primary);
}
.tag-mastered {
  background: var(--color-cta-soft);
  color: var(--color-cta);
}
.tag-migration {
  background: var(--color-secondary-soft);
  color: var(--color-primary);
}
.task-kp {
  font-weight: 700;
  font-size: 14px;
}
.task-note {
  margin-left: auto;
  font-size: 12px;
  opacity: 0.7;
}
.tabs {
  display: flex;
  gap: 8px;
}
.tab {
  font-size: 13px;
  padding: 6px 12px;
  border-radius: 999px;
  border: 0;
  background: var(--color-primary-soft);
  color: var(--color-primary);
  cursor: pointer;
  font-weight: 700;
}
.tab.on {
  background: var(--color-primary);
  color: #fff;
}
.explain-text {
  font-size: 14.5px;
  line-height: 1.75;
  margin: 0;
  color: var(--color-text);
}
.card-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.primary,
.ghost {
  border: 0;
  cursor: pointer;
  font-family: var(--font-body);
  font-weight: 700;
  padding: 8px 14px;
  border-radius: 14px;
  font-size: 13.5px;
  display: inline-flex;
  align-items: center;
  gap: 5px;
}
.primary {
  background: var(--color-cta);
  color: #fff;
  box-shadow: var(--shadow-clay-press);
}
.primary:disabled {
  opacity: 0.5;
  cursor: default;
}
.ghost {
  background: var(--color-primary-soft);
  color: var(--color-primary);
}
.ghost.playing {
  background: var(--color-cta-soft);
  color: var(--color-cta);
}
.quiz-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.quiz-q {
  font-size: 14.5px;
  font-weight: 700;
}
.quiz-opts {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.opt {
  border: 0;
  cursor: pointer;
  font-family: var(--font-body);
  font-size: 13.5px;
  padding: 8px 14px;
  border-radius: 12px;
  background: var(--color-primary-soft);
  color: var(--color-text);
  font-weight: 600;
}
.opt.sel {
  background: var(--color-primary);
  color: #fff;
}
.opt.right {
  background: var(--color-cta);
  color: #fff;
}
.opt.wrong {
  background: var(--color-danger);
  color: #fff;
}
.opt:disabled {
  cursor: default;
}
.result {
  font-size: 13.5px;
  font-weight: 700;
  padding: 8px 12px;
  border-radius: 12px;
}
.result.pass {
  background: var(--color-cta-soft);
  color: #15803d;
}
.result.fail {
  background: var(--color-danger-soft);
  color: #b91c1c;
}
.att-q {
  font-size: 13.5px;
  font-weight: 700;
  margin: 2px 0 0;
}
.task-empty {
  font-size: 14px;
  font-weight: 700;
  color: var(--color-cta);
  padding: 6px 0;
}
.mastery.stable {
  border-top: 4px solid var(--color-cta);
}
.stop {
  border-top: 4px solid var(--color-primary);
}
.feynman-guide {
  font-size: 14px;
  line-height: 1.6;
}
textarea {
  width: 100%;
  margin-top: 6px;
  border: 2px solid var(--color-line);
  border-radius: 12px;
  padding: 8px 10px;
  font-family: var(--font-body);
  font-size: 14px;
  resize: vertical;
}
.checklist {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.check {
  text-align: left;
  border: 0;
  cursor: pointer;
  font-family: var(--font-body);
  font-size: 13.5px;
  padding: 8px 10px;
  border-radius: 12px;
  background: var(--color-primary-soft);
  color: var(--color-text);
}
.check.on {
  background: var(--color-cta-soft);
  color: #15803d;
  font-weight: 700;
}
.card.mastery {
  border: 3px solid var(--color-cta);
  background: linear-gradient(135deg, #f0fdf4, #ffffff);
}
.mastery-body {
  font-size: 14px;
  line-height: 1.6;
}
.card.suggest,
.card.good {
  background: var(--color-secondary-soft);
}
</style>
