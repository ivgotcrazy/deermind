import { defineStore } from 'pinia'
import { ref } from 'vue'

export type Mode = 'child' | 'parent' | 'admin'

export const useAppStore = defineStore('app', () => {
  const mode = ref<Mode>('child')
  const prdNote = ref(false)

  function setMode(m: Mode) {
    mode.value = m
  }

  function resetAll() {
    mode.value = 'child'
    prdNote.value = false
  }

  return {
    mode,
    prdNote,
    setMode,
    resetAll,
  }
})
