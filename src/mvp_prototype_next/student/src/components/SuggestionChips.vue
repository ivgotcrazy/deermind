<script setup lang="ts">
defineProps<{ suggestions: string[]; disabled?: boolean }>();
const emit = defineEmits<{ select: [text: string] }>();
</script>

<template>
  <div class="suggestion-chips">
    <span class="chips-hint">💡 你可以说：</span>
    <div class="chips-row">
      <button v-for="(s, i) in suggestions" :key="i" class="chip" :disabled="disabled" @click="emit('select', s)">{{ s }}</button>
    </div>
  </div>
</template>

<style scoped>
.suggestion-chips { margin: 8px 0 4px 48px; }
.chips-hint { font-size: 11px; color: #8a99a8; display: block; margin-bottom: 6px; }
.chips-row { display: flex; flex-wrap: wrap; gap: 6px; }
.chip { background: #fff; border: 1px solid #c8d6e0; color: #3a5a6c; padding: 5px 12px; border-radius: 16px; font-size: 12px; cursor: pointer; transition: all 0.15s; font-family: inherit; }
.chip:hover { background: #e8f4ee; border-color: #40916c; color: #1b4332; }
.chip:active { transform: scale(0.97); }
@media (max-width: 700px) {
  .suggestion-chips { margin-left: 42px; }
  .chip { font-size: 11px; padding: 4px 10px; }
}
</style>
