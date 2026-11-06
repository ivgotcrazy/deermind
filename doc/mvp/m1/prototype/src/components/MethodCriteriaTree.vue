<script setup lang="ts">
import { domainData } from '../model/domain';
import { executionCriteria, methodName, type MethodNode } from '../model/evaluation';
defineProps<{node:MethodNode}>();
function sourceUrl(claimId:string,methodId:string){
  return '#/evaluation?'+new URLSearchParams({id:claimId,method:methodId});
}
</script>

<template>
  <article class="child-source">
    <strong>{{node.step?.title}} · {{node.method?.name||node.methodId||'子方法待选'}}</strong>
    <div class="muted">{{domainData.tasks.find(t=>t.id===node.taskId)?.name||'子任务待选'}}</div>
    <p v-if="node.method?.conditions" class="muted">适用条件 · {{node.method.conditions}}</p>
    <p v-if="node.entryConditions.length">进入条件 · {{node.entryConditions.join(' / ')}}</p>
    <p v-if="node.step?.inputs||node.step?.output" class="muted">输入 · {{node.step?.inputs||'待补充'}}　返回 · {{node.step?.output||'待补充'}}</p>
    <template v-if="node.owner">
      <a :href="sourceUrl(node.owner.id,node.methodId)">{{node.owner.name}} · v{{node.owner.version}} ↗</a>
      <ul v-if="executionCriteria(node.owner,node.methodId).length" class="child-checks">
        <li v-for="c in executionCriteria(node.owner,node.methodId)" :key="c.id"><strong>{{c.name}}</strong><small>{{c.met}}</small></li>
      </ul>
      <p v-else class="muted">本层执行判据待关联。</p>
    </template>
    <div v-if="node.issue" class="callout amber">{{node.issue}}
      <a v-for="c in node.sources" :key="c.id" :href="sourceUrl(c.id,node.methodId)">{{c.name}} ↗ </a>
      <a v-if="!node.sources.length&&node.taskId&&node.method" :href="'#/evaluation?task='+node.taskId+'&domain='+node.method.domainId">查看子任务 Claim →</a>
    </div>
    <details v-if="node.children.length"><summary>{{methodName(node.methodId)}} 的子方法（{{node.children.length}}）</summary>
      <MethodCriteriaTree v-for="(child,index) in node.children" :key="index" :node="child"/>
    </details>
  </article>
</template>
<style scoped>
.child-source{border-left:3px solid #bfd5c8;padding:10px 18px;margin:10px 0;background:#f8faf9}.child-checks{padding-left:18px}.child-checks small{display:block;color:#687b70}.child-source p{margin:6px 0}.child-source summary{cursor:pointer}
</style>
