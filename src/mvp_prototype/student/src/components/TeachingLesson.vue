<script setup lang="ts">
import { ref, watch, nextTick, onMounted } from 'vue';
import type { TeachingSession } from '../teaching-session';
import ChatMessage from './ChatMessage.vue';
import ChainDiagram from '../../../shared/ChainDiagram.vue';
const props=defineProps<{session:TeachingSession}>();
const s=props.session.state;
const bottom=ref<HTMLElement|null>(null),zoom=ref(false),tools=ref(false);
async function showCurrent(){await nextTick();const container=bottom.value?.closest('.messages-container');if(container)container.scrollTop=container.scrollHeight;}
onMounted(showCurrent);
watch(()=>[s.messages.length,s.step],showCurrent,{flush:'post'});
function action(id:string){if(id==='practice')props.session.practice();else if(id==='test')props.session.offer();else if(id==='help')props.session.help();else props.session.finish();}
</script>
<template>
  <div class="teaching-lesson">
    <p class="preview-note">教学交互演示 · 预设内容 <button @click="tools=true">演示工具</button></p>
    <template v-for="m in s.messages" :key="m.id">
      <ChatMessage :message="{id:String(m.id),role:m.role,blocks:[{type:'text',text:m.text}],timestamp:0}"/>
      <figure v-if="m.visual==='dots'" class="inline-material"><figcaption>12人平均分成3组，取其中1组</figcaption><div class="dot-groups"><div v-for="g in 3" :key="g" :class="{selected:g===1}"><span v-for="n in 4" :key="n">●</span></div></div><small>框表示分组，每个圆点表示1人。</small></figure>
      <div v-if="m.visual==='contrast'" class="inline-material comparisons"><article><b>A · 以摄影组为整体</b><p>航模人数是摄影组的 3/4。</p></article><article><b>B · 以气象组为整体</b><p>航模人数是气象组的 3/4。</p></article></div>
      <figure v-if="m.visual==='garden'" class="inline-material"><ChainDiagram/><figcaption>5列面积相等；左侧3列是花区，上半部是月季区。</figcaption><button @click="zoom=true">放大图示</button></figure>
    </template>
    <p v-if="s.notice || session.storageError.message" role="status" class="notice">{{s.notice || session.storageError.message}}</p>
    <section v-if="s.step==='offer'" class="inline-material test-offer" aria-label="检测说明">
      <h3>{{s.scenario==='transfer'?'读懂图中的两层关系':'说明新的两层数量关系'}}</h3>
      <p>1题 · 约3分钟。写出结果和理由，提交后统一反馈。可以随时结束；请求讲解会先结束检测。</p>
      <p class="muted">上文和右侧页面仍可查看，这次不会据此认定独立掌握。</p>
      <p v-if="s.preparationError" role="alert">这道题还没准备好，检测尚未开始。可以重试或暂不检测。</p>
      <p v-else-if="s.prepared">题目已准备好。</p>
      <div class="actions"><button v-if="!s.prepared" @click="session.prepare()">{{s.preparationError?'重试准备':'准备题目'}}</button><button v-else class="primary" @click="session.start()">开始检测</button><button @click="session.finish()">暂不检测</button></div>
    </section>
    <div v-else-if="s.step==='testing'" class="actions lesson-actions"><button @click="session.help()">求助并结束检测</button><button v-if="s.scenario==='transfer'" @click="session.unclear()">图示看不清</button><button @click="session.finish()">结束检测</button></div>
    <div v-else-if="session.waiting.value" class="actions lesson-actions"><button @click="action('help')">直接讲解</button><button @click="action('end')">今天先到这里</button></div>
    <div v-else-if="s.step==='choice'" class="actions lesson-actions"><button v-if="!s.attempts.some(a=>a.item==='practice')" @click="action('practice')">试一道练习</button><button v-if="!s.checks" @click="action('test')">用新题检测</button><button @click="action('end')">今天先到这里</button></div>
    <div v-else-if="s.step==='feedback'" class="actions lesson-actions"><button @click="session.help()">讲讲这里</button><button @click="session.finish()">查看本次小结</button></div>
    <section v-if="s.step==='summary'" class="inline-material learning-summary" aria-label="本次学习小结">
      <h3>本次学习小结</h3><p>{{s.attempts.filter(a=>a.purpose==='练习').length}} 次练习回应 · {{s.checks}} 次检测</p>
      <p>{{s.lastResult || '已经练习了当前问题，是否能完成新的完整任务仍需要进一步确认。'}}</p>
      <p>之后可以继续巩固两层关系。今天结束不等于已经长期掌握。</p>
      <details><summary>查看判断依据与学习要求</summary><article v-for="row in session.summary.value" :key="row.name"><b>{{row.name}}</b><p>个人判断：{{row.judgment}}</p><p>学习要求：{{row.target}}</p></article><p class="muted">以上为预写评价示例；只描述本次增加的证据。未检测的方面不清空原有认识。</p></details>
      <details><summary>查看作答与帮助记录</summary><article v-for="(a,i) in s.attempts" :key="i"><b>{{a.purpose}} {{i+1}} · {{a.result}}</b><p>{{a.answer || '未提交'}}</p><p>{{a.help}}</p><small>{{a.basis}}</small></article><p v-if="!s.attempts.length">尚无作答。</p></details>
    </section>
    <div ref="bottom"></div>
    <div v-if="zoom" class="overlay" @click.self="zoom=false"><section role="dialog" aria-modal="true" aria-label="放大图示" class="dialog"><button class="close" @click="zoom=false">关闭图示</button><ChainDiagram/><p>只放大原图，不增加解题提示。</p></section></div>
    <div v-if="tools" class="overlay" @click.self="tools=false"><section role="dialog" aria-modal="true" aria-label="演示工具" class="dialog">
      <header><h3>演示工具</h3><button @click="tools=false">关闭工具</button></header><p>仅供设计走查。填入预设回答后，请在底部提交；这里不替学生选择对错。</p>
      <div class="sample-list"><button v-for="text in session.presets.value" :key="text" @click="s.draft=text;tools=false">{{text}}</button><p v-if="!session.presets.value.length">当前没有需要作答的预设问题。</p></div>
      <button v-if="s.step==='offer'" @click="session.prepare(true);tools=false">模拟题目准备失败</button><button v-if="s.step==='testing'&&s.scenario==='transfer'" @click="session.defective();tools=false">模拟已确认的材料缺陷</button>
      <details><summary>查看教学选择记录</summary><p>采用教学模型固定 v1：Task fraction-chain；方法 S-CHAIN-A／B；单一 Task Claim 的四方面。后台改动不会自动改写本演示。</p><article v-for="(t,i) in s.trace" :key="i"><b>{{t.stage}} · {{t.strategy}}</b><p>{{t.reason}}</p></article><p>题目 {{s.activeTest||'尚未开始检测'}} · {{s.prepared?'检查保存通过（mock）':'尚未准备检测题'}}；不调用 LLM，不写入正式 Belief。</p></details>
      <footer><a href="/student/teaching.html">选择其他情境</a><button @click="session.reset();tools=false">重新开始本情境</button></footer>
    </section></div>
  </div>
</template>
<style scoped>
.preview-note{font-size:12px;color:#75857c;display:flex;justify-content:space-between;align-items:center;margin:0 0 20px}.preview-note button{border:0;background:none;padding:4px}.inline-material{margin:0 0 24px 48px;background:#fff;border:1px solid #dce5df;border-radius:12px;padding:18px;font-size:14px;line-height:1.8}.inline-material h3{margin:0 0 10px;font-size:16px}.muted,small{font-size:12px;color:#75857c}button{border:1px solid #d5dfd8;border-radius:7px;background:white;color:#2d6a4f;padding:8px 12px;cursor:pointer;font:inherit;font-size:13px}.primary{background:#2d6a4f;color:white}.actions{display:flex;flex-wrap:wrap;gap:8px}.lesson-actions{margin:0 0 20px 48px}.dot-groups{display:flex;gap:12px;margin:18px 0}.dot-groups>div{display:grid;grid-template-columns:repeat(2,1fr);gap:8px;padding:12px;border:1px solid #c8d6cf;border-radius:8px;color:#718b7c}.dot-groups .selected{background:#d7efdf;border:2px solid #40916c;color:#1b6344}.comparisons{display:grid;grid-template-columns:1fr 1fr;gap:16px}.comparisons article+article{border-left:1px solid #dce5df;padding-left:16px}.notice{padding:12px;background:#fff7e9;line-height:1.7;font-size:13px}.learning-summary details{border-top:1px solid #e4ece6;padding-top:12px;margin-top:12px}summary{cursor:pointer;color:#2d6a4f}.learning-summary article,.dialog article{border-top:1px solid #edf1ee;margin-top:12px;padding-top:12px}.overlay{position:fixed;inset:0;z-index:1000;background:#172e2655;display:flex;align-items:center;justify-content:center;padding:24px}.dialog{background:#fff;border-radius:12px;padding:24px;width:640px;max-width:90vw;max-height:85vh;overflow:auto;font-size:14px;line-height:1.8}.dialog header,.dialog footer{display:flex;justify-content:space-between;gap:16px;align-items:center}.dialog footer{margin-top:20px}.sample-list{display:grid;gap:10px;margin:18px 0}.sample-list button{text-align:left}.close{float:right}.dialog a{color:#2d6a4f}@media(max-width:900px){.inline-material,.lesson-actions{margin-left:0}.comparisons{grid-template-columns:1fr}.comparisons article+article{border-left:0;border-top:1px solid #dce5df;padding:12px 0 0}}
</style>
