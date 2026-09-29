<script setup lang="ts">
import { STATE_LABEL } from '@/data/sharedMock'
import type { MasteryState } from '@/data/sharedMock'

defineProps<{ state: MasteryState }>()
</script>

<template>
  <span class="sb" :class="state">{{ STATE_LABEL[state] }}</span>
</template>

<style scoped>
.sb {
  font-size: 12px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 999px;
  white-space: nowrap;
}
.sb.stable {
  background: #dcfce7;
  color: #15803d;
}
.sb.short {
  background: #ecfdf5;
  color: #059669;
}
.sb.learning {
  background: #fef3c7;
  color: #b45309;
}
.sb.unknown {
  background: #f1f5f9;
  color: #64748b;
}
</style>
