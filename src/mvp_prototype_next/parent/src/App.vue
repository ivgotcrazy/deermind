<script setup lang="ts">
import { computed } from 'vue';
import { useRoute } from 'vue-router';
import Learner from './structure/Learner.vue';
import { storageWarning, scriptedPreview } from './structure/state';

const route = useRoute();
const area = computed(() => String(route.params.page || ''));
// Preserve the existing review controls, only adapt their destinations.
// This is a link to the retained old preview, not a dependency of the parent app.
const legacyTools = new URL('http://127.0.0.1:5178/phase4.html');
function switchRole(event: Event) {
  const role = (event.target as HTMLSelectElement).value;
  if (['student', 'parent', 'admin'].includes(role)) location.href = `/${role}/`;
}
</script>

<template>
  <div class="wireframe parent">
    <div class="review-strip">
      <span>交互试用 <b>{{ scriptedPreview ? '预写走查 · 合成教学情境' : '章节状态与历史资料为预写参考' }}</b></span>
      <div><a :href="legacyTools.href">旧流程工具</a><label>评审视角 <select value="parent" @change="switchRole" aria-label="评审视角"><option value="student">学生</option><option value="parent">家长</option><option value="admin">管理员</option></select></label></div>
    </div>
    <p v-if="storageWarning" role="alert" class="storage-warning">{{ storageWarning }}</p>
    <Learner :parent="true" :page="area" />
  </div>
</template>
