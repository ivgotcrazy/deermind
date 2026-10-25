<script setup lang="ts">
import { scanFixtures } from '../workbench/textbook-import';
defineProps<{fixture:number}>();
</script>
<template><div class="scan-page" role="img" :aria-label="'自编扫描示例：'+scanFixtures[fixture]?.title">
  <div class="scan-heading">数学学习材料 <span>自编示例</span></div>
  <h3>{{scanFixtures[fixture]?.title}}</h3>
  <p v-for="(line,i) in scanFixtures[fixture]?.text.split('\n')" :key="i" :class="{equation:i>1}">{{line}}</p>
  <svg v-if="fixture===1" viewBox="0 0 400 130" aria-label="原长 48 米，增加原长的四分之一"><rect x="20" y="40" width="280" height="35" fill="#d6e0d4" stroke="#5e7861"/><rect x="300" y="40" width="70" height="35" fill="#f3e6bb" stroke="#947f49"/><path d="M90 40v35M160 40v35M230 40v35" stroke="#5e7861"/><text x="110" y="110">原长 48 米</text><text x="300" y="25">增加 1/4</text></svg>
  <svg v-if="fixture===2" viewBox="0 0 400 180" aria-label="三角形底长 12 厘米，对应高 7 厘米"><path d="M60 140L330 140L170 20Z" fill="#e4ebdf" stroke="#5e7861"/><path d="M170 20V140" stroke="#5e7861" stroke-dasharray="5 5"/><path d="M170 126h14v14" fill="none" stroke="#5e7861"/><text x="140" y="165">12 厘米</text><text x="180" y="90">7 厘米</text></svg>
  <p class="scan-footer">{{fixture+6}}</p>
</div></template>
<style scoped>
.scan-page{background:#fffdf6;border:1px solid #e5dfd1;box-shadow:0 3px 10px #22352d0b;min-height:470px;padding:28px 30px;color:#353d34}.scan-heading{font-size:12px;border-bottom:1px solid #d7d6c9;padding-bottom:12px;display:flex;justify-content:space-between}.scan-heading span{color:#8a8c80}.scan-page h3{font-size:20px;margin:28px 0}.scan-page p{line-height:2;font-size:16px;margin:15px 0;overflow-wrap:anywhere}.scan-page .equation{font-family:Georgia,'Times New Roman',serif;text-align:center;font-size:19px}.scan-page svg{width:100%;margin:20px 0}.scan-page .scan-footer{font-size:12px;text-align:center;color:#929282;margin-top:50px}
</style>
