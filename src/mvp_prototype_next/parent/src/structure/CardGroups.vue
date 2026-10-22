<script setup lang="ts">
defineProps<{total:9|12}>();
</script>
<template>
 <figure class="card-groups" :aria-label="`把 ${total} 张卡片分成 ${total/3} 组，每组 3 张，突出其中 1 组`">
  <figcaption>把 {{ total }} 张看作一整份，每 3 张圈成一组</figcaption>
  <div class="card-group-row" aria-hidden="true"><div v-for="group in total/3" :key="group" class="card-group" :class="{highlight:group===1}"><i v-for="card in 3" :key="card"></i><small>3 张</small></div></div>
  <p>3 张占 {{ total/3 }} 组中的 1 组：<strong>3 / {{ total }} = 1 / {{ total/3 }}</strong></p>
 </figure>
</template>
