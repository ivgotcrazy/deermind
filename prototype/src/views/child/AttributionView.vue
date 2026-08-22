<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAppStore } from '@/stores/app'
import { attributionDialogue, attributionResult, sampleError, type Attribution } from '@/data/mock'
import DeerAvatar from '@/components/DeerAvatar.vue'
import Icon from '@/components/Icon.vue'

const store = useAppStore()
const router = useRouter()

interface Msg {
  speaker: 'deer' | 'child'
  text: string
}

const messages = ref<Msg[]>([])
const current = ref(attributionDialogue[0])
const result = ref<Attribution | ''>('')
const done = ref(false)

const stepsMap = Object.fromEntries(attributionDialogue.map((s) => [s.id, s]))

const terminalText: Record<string, string> = {
  read: '明白了，是读题时漏掉了关键条件。我们来做一组读题训练吧！',
  slip: '其实你会算，是最后一步算错了，属于"粗心"。我们直接做一道变式确认一下！',
  concept: '这个知识点我们还没完全掌握，小鹿给你讲一讲，好不好？',
}

onMounted(() => {
  if (store.attribution) {
    // 若已有归因结果（如跳转回来），直接展示结果页
    result.value = store.attribution as Attribution
    done.value = true
    return
  }
  messages.value.push({ speaker: 'deer', text: '我们来看看这道题：' + sampleError.ocrText })
  setTimeout(() => messages.value.push({ speaker: 'deer', text: current.value.text }), 400)
})

function choose(opt: { label: string; next?: string; attribution?: string }) {
  if (done.value) return
  messages.value.push({ speaker: 'child', text: opt.label })
  const next = opt.next
  if (next && stepsMap[next]) {
    current.value = stepsMap[next]
    setTimeout(() => messages.value.push({ speaker: 'deer', text: current.value.text }), 500)
  } else if (next) {
    done.value = true
    result.value = attributionResult[next]
    store.attribution = attributionResult[next]
    setTimeout(() => messages.value.push({ speaker: 'deer', text: terminalText[next] }), 500)
  }
}

function goNext() {
  if (result.value === '审题失误') router.push('/child/reading')
  else if (result.value === '概念不清') router.push('/child/explain')
  else if (result.value === '粗心') router.push('/child/variant')
}
</script>

<template>
  <div class="attribution">
    <h2 class="title">小鹿帮你分析错因</h2>

    <div class="chat" ref="chatRef">
      <div v-for="(m, i) in messages" :key="i" class="msg" :class="m.speaker">
        <DeerAvatar v-if="m.speaker === 'deer'" :size="40" />
        <div class="bubble" :class="m.speaker">{{ m.text }}</div>
      </div>
    </div>

    <!-- 选项 -->
    <div v-if="!done" class="options">
      <button
        v-for="opt in current.options"
        :key="opt.label"
        class="opt"
        @click="choose(opt)"
      >
        {{ opt.label }}
      </button>
    </div>

    <!-- 归因结果 -->
    <section v-if="done" class="card result">
      <div class="result-head">
        <Icon name="sparkles" :size="22" />
        <span>归因结果</span>
      </div>
      <div class="tag" :class="result === '审题失误' ? 'pill-focus' : result === '概念不清' ? 'pill-inprogress' : 'pill-mastered'">
        {{ result }}
      </div>
      <p class="why" v-if="result === '审题失误'">你在复述题意时漏掉了"用去了全长的 2/3"这个关键条件——这道题不是不会算，是读题时漏了信息。</p>
      <p class="why" v-else-if="result === '概念不清'">"求一个数的几分之几"这个知识点还需要巩固。</p>
      <p class="why" v-else>概念和方法都对，最后一步算错了，属于粗心。</p>
      <button class="btn btn-primary btn-block" @click="goNext">
        {{
          result === '审题失误'
            ? '开始读题训练 →'
            : result === '概念不清'
            ? '小鹿给你讲解 →'
            : '做变式确认 →'
        }}
      </button>
    </section>
  </div>
</template>

<style scoped>
.attribution {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.title {
  margin: 0;
  font-family: var(--font-head);
  font-size: 20px;
}
.chat {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 200px;
}
.msg {
  display: flex;
  align-items: flex-start;
  gap: 8px;
}
.msg.child {
  flex-direction: row-reverse;
}
.bubble {
  max-width: 76%;
  padding: 12px 14px;
  border-radius: 16px;
  font-size: 15px;
  line-height: 1.6;
  box-shadow: var(--shadow-md);
}
.bubble.deer {
  background: #fff;
  border-top-left-radius: 4px;
}
.bubble.child {
  background: var(--color-primary);
  color: #fff;
  border-top-right-radius: 4px;
}
.options {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.opt {
  text-align: left;
  padding: 14px;
  border: 2px solid var(--color-line);
  border-radius: 14px;
  background: #fff;
  font-size: 14px;
  transition: all var(--ease-soft);
}
.opt:active {
  border-color: var(--color-primary);
  background: var(--color-primary-soft);
  transform: scale(0.99);
}
.result {
  border-top: 4px solid var(--color-primary);
}
.result-head {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 700;
  margin-bottom: 10px;
  color: var(--color-primary);
}
.tag {
  display: inline-block;
  font-size: 14px;
  font-weight: 700;
  padding: 5px 14px;
  border-radius: 999px;
  margin-bottom: 10px;
}
.why {
  margin: 0 0 14px;
  font-size: 14px;
  line-height: 1.6;
}
</style>
