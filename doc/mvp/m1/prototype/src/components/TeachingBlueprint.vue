<script setup lang="ts">
import { computed } from 'vue';
import type { TeachingBlueprint as BlueprintDefinition } from '../model/teaching-mock';
const props=withDefaults(defineProps<{blueprint:BlueprintDefinition;selectedStage?:string;selectedTransition?:string;activeStage?:string;visited?:string[];tracedEdges?:string[];nodeRouting?:boolean}>(),{visited:()=>[],tracedEdges:()=>[]});
const emit=defineEmits<{stage:[id:string];transition:[id:string]}>();
const height=computed(()=>props.blueprint.stages.length*110+105);
function point(id:string){if(id==='start')return {x:275,y:25,index:-1};if(id==='end')return {x:275,y:height.value-25,index:props.blueprint.stages.length};const index=props.blueprint.stages.findIndex(s=>s.id===id);return {x:275,y:110+index*110,index};}
const edges=computed(()=>{
  let forward=0,backward=0;
  return props.blueprint.transitions.filter(e=>['start','end',...props.blueprint.stages.map(s=>s.id)].includes(e.from)&&['start','end',...props.blueprint.stages.map(s=>s.id)].includes(e.to)).map(e=>{
    const a=point(e.from),b=point(e.to),straight=b.index-a.index===1;
    const ay=a.y+(e.from==='start'?17:30),by=b.y-(e.to==='end'?17:30);
    if(e.from===e.to)return {...e,path:`M 398 ${a.y-14} H 450 V ${a.y+46} H 275 V ${a.y+30}`,lx:450,ly:a.y+22};
    if(straight)return {...e,path:`M 275 ${ay} V ${by}`,lx:275,ly:(ay+by)/2};
    const right=b.index>a.index,lane=right?450+(forward++%3)*82:88-(backward++%2)*48;
    const fromX=e.from==='start'?(right?309:241):(right?398:152),toX=e.to==='end'?(right?309:241):(right?398:152);
    return {...e,path:`M ${fromX} ${a.y} H ${lane} V ${b.y} H ${toX}`,lx:Math.max(49,lane),ly:(a.y+b.y)/2};
  });
});
function stageName(id:string){return id==='start'?'开始':id==='end'?'结束':props.blueprint.stages.find(s=>s.id===id)?.name||'未知节点';}
</script>

<template><div class="teaching-graph">
  <svg :viewBox="`0 0 720 ${height}`" role="group" aria-label="活动流程图：选择节点或连接查看定义">
    <defs><marker id="teaching-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="context-stroke"/></marker></defs>
    <g v-for="e in edges" :key="e.id" class="graph-edge" :class="{selected:selectedTransition===e.id,traced:tracedEdges.includes(e.id)}" aria-hidden="true" @click="emit('transition',e.id)">
      <path class="edge-hit" :d="e.path"/><path class="edge-line" :d="e.path" marker-end="url(#teaching-arrow)"/>
    </g>
    <g v-for="e in edges" :key="'label-'+e.id" class="graph-edge" :class="{selected:selectedTransition===e.id,traced:tracedEdges.includes(e.id)}" role="button" tabindex="0" :aria-label="`连接：${stageName(e.from)} → ${stageName(e.to)}，${e.label}`" @click="emit('transition',e.id)" @keydown.enter.prevent="emit('transition',e.id)" @keydown.space.prevent="emit('transition',e.id)">
      <rect :x="e.lx-47" :y="e.ly-11" width="94" height="22" rx="4" class="edge-label-bg"/>
      <text :x="e.lx" :y="e.ly+4" text-anchor="middle">{{e.label.length>8?e.label.slice(0,8)+'…':e.label}}</text>
      <title>{{e.condition}}</title>
    </g>
    <g class="terminal" :class="{selectable:nodeRouting,selected:nodeRouting&&selectedStage==='start'}" :role="nodeRouting?'button':undefined" :tabindex="nodeRouting?0:undefined" :aria-label="nodeRouting?'开始节点（预置）':undefined" @click="nodeRouting&&emit('stage','start')" @keydown.enter.prevent="nodeRouting&&emit('stage','start')" @keydown.space.prevent="nodeRouting&&emit('stage','start')"><rect x="241" y="8" width="68" height="34" rx="17"/><text x="275" y="30" text-anchor="middle">开始</text></g>
    <g v-for="(s,i) in blueprint.stages" :key="s.id" class="graph-node" :class="{selected:selectedStage===s.id,active:activeStage===s.id,visited:visited.includes(s.id)}" role="button" tabindex="0" :aria-label="`节点 ${i+1}：${s.name}`" @click="emit('stage',s.id)" @keydown.enter.prevent="emit('stage',s.id)" @keydown.space.prevent="emit('stage',s.id)">
      <rect x="152" :y="80+i*110" width="246" height="60" rx="8"/>
      <text x="170" :y="105+i*110" class="node-number">节点 {{i+1}}<tspan v-if="activeStage===s.id" dx="12">当前节点</tspan></text>
      <text x="170" :y="126+i*110" class="node-name">{{s.name.length>17?s.name.slice(0,17)+'…':s.name}}</text>
      <title>{{s.purpose}}</title>
    </g>
    <g class="terminal" :class="{selectable:nodeRouting,selected:nodeRouting&&selectedStage==='end'}" :role="nodeRouting?'button':undefined" :tabindex="nodeRouting?0:undefined" :aria-label="nodeRouting?'结束节点（预置）':undefined" @click="nodeRouting&&emit('stage','end')" @keydown.enter.prevent="nodeRouting&&emit('stage','end')" @keydown.space.prevent="nodeRouting&&emit('stage','end')"><rect x="241" :y="height-42" width="68" height="34" rx="17"/><text x="275" :y="height-20" text-anchor="middle">结束</text></g>
  </svg>
  <p class="graph-note">{{nodeRouting?'条件转移定义在起点节点内，箭头显示目标。开始和结束为预置节点，不可删除。':'连线表示执行顺序与转移条件；子活动结束后沿返回连接继续。活动实例可暂停、恢复或结束。'}}</p>
</div></template>

<style scoped>
.terminal.selectable{cursor:pointer;outline:none}.terminal.selectable.selected rect,.terminal.selectable:focus rect{stroke:#2d6a4f;stroke-width:2.5}
.teaching-graph{min-width:0;background:#fbfcfb}.teaching-graph svg{display:block;width:100%;min-width:460px}.graph-edge,.graph-node{cursor:pointer;outline:none}.edge-hit{fill:none;stroke:transparent;stroke-width:17}.edge-line{fill:none;stroke:#b3c5ba;stroke-width:1.5;stroke-linejoin:round}.edge-label-bg{fill:#fbfcfb;stroke:transparent}.graph-edge text{fill:#6a8072;font-size:12px}.graph-edge.selected .edge-line,.graph-edge.traced .edge-line,.graph-edge:hover .edge-line,.graph-edge:focus .edge-line{stroke:#2d6a4f;stroke-width:2.5}.graph-edge.selected .edge-label-bg,.graph-edge:focus .edge-label-bg{fill:#e7f2eb;stroke:#75a88b}.graph-edge.selected text,.graph-edge.traced text{fill:#24583f;font-weight:600}.graph-node rect{fill:white;stroke:#d2dfd7;stroke-width:1.5}.graph-node.selected rect,.graph-node:hover rect,.graph-node:focus rect{stroke:#2d6a4f;stroke-width:2}.graph-node.visited rect{fill:#f0f7f3}.graph-node.active rect{fill:#e3f1e9;stroke:#2d6a4f;stroke-width:2.5}.node-number{fill:#6a8172;font-size:11px}.node-name{fill:#254b36;font-size:15px;font-weight:600}.terminal rect{fill:#e9efeb;stroke:#cfdbd3}.terminal text{fill:#526e5e;font-size:12px}.graph-note{font-size:12px;color:#74847b;padding:4px 16px 16px!important;margin:0!important;line-height:1.7}
</style>
