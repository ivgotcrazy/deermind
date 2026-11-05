<script setup lang="ts">
import { computed } from 'vue';
import { parseFormula, blockIssues, type Expression, type ReviewBlock } from '../model/review-content';
const props=defineProps<{block:ReviewBlock}>();
const esc=(s:unknown)=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]!));
function math(e:Expression):string{
  if(e.op==='number'||e.op==='variable')return `<${e.op==='number'?'mn':'mi'}>${esc(e.value)}</${e.op==='number'?'mn':'mi'}>`;
  const args=e.args!.map(math);if(e.op==='fraction')return `<mfrac>${args[0]}${args[1]}</mfrac>`;
  if(e.op==='group')return `<mrow><mo>(</mo>${args[0]}<mo>)</mo></mrow>`;
  return `<mrow>${args[0]}<mo>${({multiply:'×',divide:'÷',add:'+',subtract:'−',equal:'='} as Record<string,string>)[e.op]}</mo>${args[1]}</mrow>`;
}
const formulas=computed(()=>props.block.lines.map(line=>{try{return `<math xmlns="http://www.w3.org/1998/Math/MathML">${line.trim().startsWith('=')?'<mo>=</mo>':''}${math(parseFormula(line))}</math>`;}catch{return null;}}));
const chartOk=computed(()=>!blockIssues({...props.block,gap:''}).length);
const c=computed(()=>props.block.chart),x=(i:number)=>65+(i+.5)*470/c.value.categories.length;
const y=(v:number)=>210-v/c.value.axis.max*170;
const ticks=computed(()=>chartOk.value?Array.from({length:Math.floor(c.value.axis.max/c.value.axis.step)+1},(_,i)=>i*c.value.axis.step):[]);
const pie=computed(()=>{let angle=-Math.PI/2;return c.value.series[0]?.values.map((v,i)=>{const next=angle+v/100*2*Math.PI,mid=(angle+next)/2;const slice={path:`M160 145 L${160+90*Math.cos(angle)} ${145+90*Math.sin(angle)} A90 90 0 ${v>50?1:0} 1 ${160+90*Math.cos(next)} ${145+90*Math.sin(next)} Z`,x:160+113*Math.cos(mid),y:145+113*Math.sin(mid),value:v,color:c.value.colors[i%c.value.colors.length]||'#4f81bd'};angle=next;return slice;})||[];});
const points=(count:number,x:number)=>Array.from({length:count},(_,i)=>{const a=-Math.PI/2+2*Math.PI*i/count;return `${x+32*Math.cos(a)},${48+32*Math.sin(a)}`;}).join(' ');
</script>
<template><div class="review-block-view">
  <p v-if="block.type==='text'" class="text-content">{{block.text}}</p>
  <template v-else-if="block.type==='formula'"><div v-for="(line,i) in block.lines" :key="i" class="math-line"><span v-if="formulas[i]" v-html="formulas[i]"/><code v-else class="invalid-formula">{{line}}（待修正格式）</code></div><small v-if="block.unit">单位：{{block.unit}}</small></template>
  <template v-else-if="block.type==='table'"><small v-if="block.unit">单位：{{block.unit}}</small><div class="table-scroll"><table class="data-table"><thead><tr><th v-for="(h,i) in block.headers" :key="i">{{h}}</th></tr></thead><tbody><tr v-for="(r,i) in block.rows" :key="i"><td v-for="(v,j) in r" :key="j">{{v||'待填写'}}</td></tr></tbody></table></div></template>
  <template v-else-if="block.type==='chart'"><h4>{{c.title||'未命名统计图'}}</h4><p v-if="!chartOk" class="muted">图表数据或坐标尚不完整，补齐后预览；原值保留。</p>
    <svg v-else-if="c.chartType==='pie'" viewBox="0 0 590 290" role="img" :aria-label="c.title"><g v-for="(s,i) in pie" :key="i"><circle v-if="s.value===100" cx="160" cy="145" r="90" :fill="s.color"/><path v-else :d="s.path" :fill="s.color" stroke="white"/><text :x="s.x" :y="s.y" text-anchor="middle">{{s.value}}%</text><rect x="315" :y="55+i*42" width="12" height="12" :fill="s.color"/><text x="336" :y="67+i*42">{{c.categories[i]}}</text></g></svg>
    <svg v-else viewBox="0 0 590 300" role="img" :aria-label="c.title"><text x="8" y="20">{{c.unit}}</text><g v-for="v in ticks" :key="v"><line x1="65" :y1="y(v)" x2="540" :y2="y(v)" stroke="#dce7e0"/><text x="54" :y="y(v)+4" text-anchor="end">{{v}}</text></g><text v-for="(label,i) in c.categories" :key="i" :x="x(i)" y="235" text-anchor="middle">{{label}}</text><g v-for="(s,j) in c.series" :key="j"><polyline v-if="c.chartType==='line'" :points="s.values.map((v,i)=>x(i)+','+y(v)).join(' ')" fill="none" :stroke="s.color" stroke-width="2"/><g v-for="(v,i) in s.values" :key="i"><rect v-if="c.chartType==='bar'" :x="x(i)+(j-(c.series.length-1)/2)*28-11" :y="y(v)" width="22" :height="210-y(v)" :fill="s.color"/><circle v-else :cx="x(i)" :cy="y(v)" r="3" :fill="s.color"/><text :x="x(i)+(c.chartType==='bar'?(j-(c.series.length-1)/2)*28:0)" :y="y(v)+(c.chartType==='line'&&j?17:-7)" text-anchor="middle">{{v.toFixed(c.precision)}}</text></g><rect :x="75+j*220" y="268" width="12" height="12" :fill="s.color"/><text :x="94+j*220" y="280">{{s.name}}</text></g></svg>
  </template>
  <template v-else-if="block.type==='shapes'"><svg :viewBox="`0 0 ${block.shapes.length*100} 105`" role="img" aria-label="题目给出的图形序列"><g v-for="(s,i) in block.shapes" :key="i" stroke="#1883ad" stroke-width="2" fill="none"><circle v-if="s.shape==='circle'" :cx="50+i*100" cy="48" r="32"/><ellipse v-else-if="s.shape==='ellipse'" :cx="50+i*100" cy="48" rx="37" ry="25"/><rect v-else-if="s.shape==='square'" :x="18+i*100" y="16" width="64" height="64"/><polygon v-else :points="points(({triangle:3,pentagon:5,hexagon:6} as Record<string,number>)[s.shape]||3,50+i*100)"/><circle v-if="s.dot==='center_like'" :cx="50+i*100" cy="48" r="2.5" fill="#c62a7c" stroke="none"/></g></svg><p class="muted">示意尺寸与点的视觉位置不是额外给定的数学条件。</p></template>
  <p v-else class="callout amber">{{block.text||'原件中的内容尚未结构化，请补齐后再确认。'}}</p>
  <p v-if="block.gap" class="gap">待补：{{block.gap}}</p>
</div></template>
<style scoped>.text-content{white-space:pre-wrap;margin:8px 0}.math-line{font-size:20px;margin:12px 0;overflow:auto}svg{display:block;width:100%;max-height:380px}svg text{font-size:13px;fill:#2c3e50}h4{font-size:13px}.invalid-formula,.gap{color:#a1542b;white-space:pre-wrap}.gap{font-size:12px}.table-scroll{overflow:auto}small{color:#75847b}</style>
