<script setup lang="ts">
import type { TeachingRule, TeachingStrategy } from '../model/teaching-mock';
defineProps<{title:string;rules?:TeachingRule[];strategies?:TeachingStrategy[];readonly?:boolean}>();
defineEmits<{rule:[id:string];strategy:[id:string]}>();
</script>
<template>
  <section class="teaching-references" :aria-label="title"><h4>{{title}}</h4>
    <template v-if="rules"><details v-for="r in rules" :key="r.id"><summary>{{r.name}} <span v-if="!r.enabled" class="badge amber">已停用 · 不生效</span></summary><p>适用：{{r.when}}</p><p>{{r.requirement}}</p><button v-if="!readonly" class="text-link" @click="$emit('rule',r.id)">查看来源定义 →</button></details><p v-if="!rules.length" class="muted">未配置。</p></template>
    <template v-if="strategies"><div v-for="s in strategies" :key="s.id" class="strategy-ref"><span v-if="readonly">{{s.name}}</span><button v-else class="text-link" @click="$emit('strategy',s.id)">{{s.name}} →</button> <span v-if="!s.enabled" class="badge amber">已停用 · 不推荐</span><small>{{s.when}}</small></div><p v-if="!strategies.length" class="muted">未配置。仍可使用其他符合规则的教法。</p></template>
  </section>
</template>
<style scoped>
.teaching-references{margin:18px 0}.teaching-references h4{font-size:14px;margin:0 0 10px}.teaching-references details{padding:9px 0;border-bottom:1px solid #e4ebe6;font-size:13px;line-height:1.7}.teaching-references summary{cursor:pointer;color:#365b44}.teaching-references p{margin:8px 0}.strategy-ref{margin:12px 0;font-size:13px}.strategy-ref small{display:block;color:#718175;margin-top:5px;line-height:1.6}
</style>
