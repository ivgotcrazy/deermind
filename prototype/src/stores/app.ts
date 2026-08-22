import { defineStore } from 'pinia'
import { ref } from 'vue'
import { spaces } from '@/data/mock'

export type Mode = 'child' | 'parent'

export const useAppStore = defineStore('app', () => {
  const mode = ref<Mode>('child')
  const activeSpaceId = ref(spaces[0].id)
  const prdNote = ref(false)

  // J3 闭环流程状态
  const attribution = ref('')
  const readingStep = ref(0)
  const practiceDone = ref(false)
  const practiceScore = ref(0)
  const variantPassed = ref(false)
  const masteredNow = ref<string[]>([])
  const todayTaskDone = ref(false)

  function setMode(m: Mode) {
    mode.value = m
  }

  function resetFlow() {
    attribution.value = ''
    readingStep.value = 0
    practiceDone.value = false
    practiceScore.value = 0
    variantPassed.value = false
    masteredNow.value = []
    todayTaskDone.value = false
  }

  function resetAll() {
    resetFlow()
    mode.value = 'child'
    prdNote.value = false
  }

  return {
    mode,
    activeSpaceId,
    prdNote,
    attribution,
    readingStep,
    practiceDone,
    practiceScore,
    variantPassed,
    masteredNow,
    todayTaskDone,
    setMode,
    resetFlow,
    resetAll,
  }
})
