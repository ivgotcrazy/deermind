<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useStudentChat } from '@/stores/studentChat'
import DeerAvatar from '@/components/DeerAvatar.vue'
import Icon from '@/components/Icon.vue'
import ChatMessage from '@/components/student/ChatMessage.vue'

const store = useStudentChat()
const router = useRouter()

const hasAction = computed(
  () => store.plan.review.length + store.plan.migration.length + store.plan.consolidate.length > 0,
)

function startAction(kind: 'review' | 'migration' | 'variant') {
  store.quick(kind)
}

const draft = ref('')
const voice = ref(false)
const listRef = ref<HTMLElement>()

function scrollBottom() {
  nextTick(() => {
    if (listRef.value) listRef.value.scrollTop = listRef.value.scrollHeight
  })
}
watch(() => store.messages.length, scrollBottom)
watch(() => store.typing, scrollBottom)

onMounted(() => {
  if (!store.loggedIn) {
    router.replace('/student/login')
    return
  }
  scrollBottom()
})

function send() {
  const nav = store.send(draft.value)
  draft.value = ''
  if (nav) router.push(nav)
}

function onQuick(kind: 'review') {
  store.quick(kind)
}
</script>

<template>
  <div class="today">
    <!-- 今日安排卡（从共享掌握度派生；UNKNOWN 不进卡） -->
    <section class="plan-card">
      <div class="plan-title">
        <span class="pt-left"><Icon name="calendar" :size="16" /> 今日安排（最省时方案）</span>
        <span class="summary" :class="{ done: store.todaySummary.done }">{{ store.todaySummary.text }}</span>
      </div>
      <div class="plan-prog">{{ store.activeSpace?.progress ?? '' }}</div>
      <div class="plan-body">
        <div v-if="hasAction" class="nba-label"><span class="nba-dot"></span> 现在最值得做</div>
        <template v-if="store.plan.review.length">
          <div class="plan-row action" @click="startAction('review')">
            <span class="tag tag-review">待复习</span>
            <span class="kp">{{ store.plan.review[0].kp }}</span>
            <span class="note">{{ store.plan.review[0].day }}</span>
            <Icon name="play" :size="14" class="go" />
          </div>
        </template>
        <template v-if="store.plan.migration.length">
          <div class="plan-row action" @click="startAction('migration')">
            <span class="tag tag-migration">待迁移</span>
            <span class="kp">{{ store.plan.migration[0].kp }}</span>
            <span class="note">迁移题 · 验证稳定性</span>
            <Icon name="play" :size="14" class="go" />
          </div>
        </template>
        <template v-if="store.plan.consolidate.length">
          <div class="plan-row action" @click="startAction('variant')">
            <span class="tag tag-learn">继续巩固</span>
            <span class="kp">{{ store.plan.consolidate[0].kp }}</span>
            <span class="note">{{ store.plan.consolidate[0].note }}</span>
            <Icon name="play" :size="14" class="go" />
          </div>
        </template>
        <template v-if="store.plan.mastered.length">
          <div class="plan-row done">
            <span class="tag tag-mastered">已掌握</span>
            <span class="kp">{{ store.plan.mastered.slice(0, 2).join('、') }}</span>
            <span class="note">今天不用学</span>
          </div>
        </template>
        <div v-if="store.todaySummary.done" class="plan-empty">
          <Icon name="check" :size="16" /> 今天没有需要你继续处理的数学问题，可以去玩啦
        </div>
      </div>
    </section>

    <!-- 大对话区 -->
    <main ref="listRef" class="chat">
      <ChatMessage v-for="m in store.messages" :key="m.id" :msg="m" />
      <div v-if="store.typing" class="typing">
        <DeerAvatar :size="26" class="typing-avatar" />
        <span class="typing-text">小鹿正在想</span>
        <span class="dots"><i></i><i></i><i></i></span>
      </div>
    </main>

    <!-- 输入区 -->
    <footer class="input">
      <div class="quick">
        <button class="q" @click="router.push('/student/photo')"><Icon name="camera" :size="16" /> 拍题</button>
        <button class="q" @click="onQuick('review')"><Icon name="refresh" :size="16" /> 复习</button>
      </div>
      <div class="bar">
        <button class="mic" :class="{ on: voice }" title="说给小鹿听" @click="voice = !voice">
          <Icon :name="voice ? 'volumeOff' : 'speaker'" :size="20" />
        </button>
        <input v-model="draft" class="text" placeholder="说给小鹿听，或直接拍照…" @keyup.enter="send" />
        <button class="send" :disabled="!draft.trim()" @click="send">
          <Icon name="play" :size="18" />
        </button>
      </div>
      <div v-if="voice" class="voice-tip">请说话…（原型演示：模拟语音输入）</div>
    </footer>
  </div>
</template>

<style scoped>
.today {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--color-background);
  max-width: 760px;
  margin: 0 auto;
  width: 100%;
}
.plan-card {
  margin: 10px 16px 8px;
  background: var(--color-white);
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-clay);
  padding: 12px 14px;
}
.plan-title {
  font-family: var(--font-head);
  font-weight: 700;
  font-size: 14px;
  color: var(--color-text);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  flex-wrap: wrap;
}
.pt-left {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.summary {
  font-size: 12px;
  font-weight: 700;
  color: var(--color-primary);
  background: var(--color-primary-soft);
  padding: 3px 10px;
  border-radius: 999px;
  white-space: nowrap;
}
.summary.done {
  color: #15803d;
  background: var(--color-cta-soft);
}
.plan-prog {
  font-size: 12px;
  opacity: 0.7;
  margin: 4px 0 8px;
}
.plan-body {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.nba-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 800;
  color: var(--color-primary);
  margin-top: 2px;
}
.nba-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-primary);
  animation: pulse 1.6s infinite;
}
@keyframes pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.35;
  }
}
.plan-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13.5px;
  padding: 8px 10px;
  border-radius: 12px;
  background: var(--color-primary-soft);
}
.plan-row.action {
  background: linear-gradient(135deg, var(--color-primary-soft), #e0e7ff);
  border: 2px solid rgba(79, 70, 229, 0.25);
  cursor: pointer;
  transition: transform var(--ease-soft), box-shadow var(--ease-soft);
}
.plan-row.action:active {
  transform: scale(0.98);
}
.plan-row.action .go {
  color: var(--color-primary);
}
.plan-row.done {
  background: var(--color-cta-soft);
  opacity: 0.72;
}
.tag {
  font-size: 11px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 999px;
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
.kp {
  font-weight: 700;
}
.note {
  margin-left: auto;
  font-size: 12px;
  opacity: 0.7;
}
.plan-empty {
  font-size: 14px;
  font-weight: 700;
  color: var(--color-cta);
  padding: 4px 0;
  display: flex;
  align-items: center;
  gap: 6px;
}
.chat {
  flex: 1;
  overflow-y: auto;
  padding: 8px 16px 12px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.typing {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: var(--color-white);
  border-radius: 18px;
  width: fit-content;
  box-shadow: var(--shadow-clay);
}
.typing-avatar {
  animation: think-bounce 1s infinite;
}
@keyframes think-bounce {
  0%,
  100% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(-3px);
  }
}
.typing-text {
  font-size: 12.5px;
  font-weight: 700;
  color: var(--color-secondary);
}
.dots {
  display: inline-flex;
  gap: 4px;
}
.dots i {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--color-secondary);
  animation: blink 1.2s infinite;
}
.dots i:nth-child(2) {
  animation-delay: 0.2s;
}
.dots i:nth-child(3) {
  animation-delay: 0.4s;
}
@keyframes blink {
  0%,
  80%,
  100% {
    opacity: 0.3;
  }
  40% {
    opacity: 1;
  }
}
.input {
  padding: 8px 16px 14px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  border-top: 1px solid var(--color-line);
  background: rgba(255, 255, 255, 0.6);
}
.quick {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.q {
  border: 0;
  cursor: pointer;
  font-family: var(--font-body);
  font-size: 13px;
  font-weight: 700;
  padding: 7px 14px;
  border-radius: 999px;
  background: var(--color-primary-soft);
  color: var(--color-primary);
  display: inline-flex;
  align-items: center;
  gap: 5px;
}
.bar {
  display: flex;
  gap: 8px;
  align-items: center;
}
.mic,
.send {
  border: 0;
  width: 44px;
  height: 44px;
  border-radius: 50%;
  cursor: pointer;
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.mic {
  background: var(--color-primary-soft);
  color: var(--color-primary);
}
.mic.on {
  background: var(--color-danger-soft);
  color: var(--color-danger);
}
.send {
  background: var(--color-cta);
  color: #fff;
}
.send:disabled {
  opacity: 0.5;
  cursor: default;
}
.text {
  flex: 1;
  border: 2px solid var(--color-line);
  border-radius: 999px;
  padding: 10px 16px;
  font-family: var(--font-body);
  font-size: 14.5px;
  min-width: 0;
}
.voice-tip {
  font-size: 12.5px;
  color: var(--color-primary);
  background: var(--color-primary-soft);
  border-radius: 12px;
  padding: 8px 12px;
}
</style>
