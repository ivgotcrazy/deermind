<script setup lang="ts">
import { methodName, type Claim, type Requirement } from '../model/evaluation';
defineProps<{claim?:Claim;requirement:Requirement}>();
</script>
<template>
  <div v-if="requirement.standards.length" class="method-standards">
    <p v-if="requirement.methodMode==='all'"><strong>各方法分别达标</strong> · 每种方法单独满足所列标准，题量和证据按方法核对。</p>
    <p v-else><strong>{{requirement.methods.length===1?'指定方法达标':'任选一种方法达标'}}</strong> · {{requirement.methods.map(methodName).join('、')}}</p>
    <table class="data-table">
      <thead><tr><th v-if="requirement.methodMode==='all'">方法</th><th>评价方面</th><th>达标标准</th></tr></thead>
      <tbody v-for="key in (requirement.methodMode==='all'?requirement.methods:['any'])" :key="key">
        <tr v-for="(s,i) in requirement.standards" :key="s.aspectId">
          <td v-if="requirement.methodMode==='all'&&i===0" :rowspan="requirement.standards.length">{{methodName(key)}}</td>
          <td>{{claim?.aspects.find(a=>a.id===s.aspectId)?.name||'方面已不存在'}}</td><td>{{s.text||'待填写'}}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
<style scoped>
.method-standards{margin-top:18px}.method-standards td{vertical-align:top;white-space:pre-wrap}.method-standards th:nth-last-child(2){min-width:100px}.method-standards td[rowspan]{width:18%}
</style>
