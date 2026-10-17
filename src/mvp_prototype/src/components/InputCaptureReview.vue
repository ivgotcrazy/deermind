<script setup lang="ts">
import { computed } from 'vue';
import { capture as d, captureWarning, clearCapture, selectCapture, loadCapture, previewCapture, captureSnapshot, originalPages, voiceOriginal, type Capture, type Point } from '../captureState';
const emit=defineEmits<{use:[capture:Capture]}>();
const labels={images:'同题两张图片',pdf:'同题 PDF 两页',ink:'手写草稿',voice:'语音提问'};
const canUse=computed(()=>d.stage==='preview'&&d.prompt.trim()&&d.checked&&(d.kind!=='ink'||d.strokes.length>0)&&(d.kind==='voice'||d.kind==='ink'||d.sameQuestion));
let pointer:number|null=null;
function point(e:PointerEvent):Point{const b=(e.currentTarget as SVGSVGElement).getBoundingClientRect();return [Math.max(0,Math.min(600,(e.clientX-b.left)*600/b.width)),Math.max(0,Math.min(200,(e.clientY-b.top)*200/b.height))];}
function begin(e:PointerEvent){if(pointer!==null)return;pointer=e.pointerId;(e.currentTarget as SVGSVGElement).setPointerCapture(pointer);d.strokes.push([point(e)]);}
function move(e:PointerEvent){if(pointer===e.pointerId)d.strokes.at(-1)?.push(point(e));}
function stop(e:PointerEvent){if(pointer===e.pointerId)pointer=null;}
function use(){if(!canUse.value)return;emit('use',captureSnapshot());clearCapture();}
</script>
<template>
<details class="f-capture-panel"><summary>图片、PDF、手写与语音输入</summary>
  <p class="f-muted">合成输入走查。图片、PDF 和语音使用明确选择的示例；手写板保存实际笔迹。未接入识别、麦克风或音频播放，请勿录入真实资料。</p>
  <div class="f-actions"><button v-for="(label,kind) in labels" :key="kind" :aria-pressed="d.kind===kind" @click="selectCapture(kind)">{{ label }}</button></div>
  <template v-if="d.kind==='ink'">
    <p>在下面写下思路；书写中不会分析。可用笔或鼠标，实机防误触和书写性能留待 Android 验证。</p>
    <svg class="f-ink" viewBox="0 0 600 200" aria-label="手写草稿板" @pointerdown.prevent="begin" @pointermove.prevent="move" @pointerup="stop" @pointercancel="stop" @lostpointercapture="pointer=null"><path v-for="(stroke,i) in d.strokes" :key="i" :d="stroke.map((p,j)=>`${j?'L':'M'} ${p[0]} ${p[1]}`).join(' ')" fill="none" stroke="#285a48" stroke-width="3" stroke-linecap="round"/></svg>
    <div class="f-actions"><button @click="d.strokes.pop()" :disabled="!d.strokes.length">撤销最后一笔</button><button :disabled="!d.strokes.length" @click="d.stage='preview';d.prompt='';d.answer='';d.checked=false">保留笔迹，补充题意</button></div>
  </template>
  <button v-else-if="d.stage==='empty'" class="f-secondary f-spaced" @click="loadCapture">{{ d.kind==='voice'?'开始录音演示（不启用麦克风）':'载入两页合成材料' }}</button>
  <div v-if="d.stage==='recording'" class="f-notice"><p>录音流程演示中，没有实际收音。停止后才预览转写，不会产生作答或教学回复。</p><button @click="previewCapture">结束并预览转写示例</button><button @click="clearCapture">取消本次录音演示</button></div>
  <div v-if="(d.kind==='images'||d.kind==='pdf')&&d.stage!=='empty'" class="f-source-review"><figure v-for="(text,i) in originalPages" :key="i" class="f-source-page"><figcaption>{{ d.kind==='pdf'?'PDF 页':'图片' }} {{ i+1 }} · 自编原材料</figcaption><svg v-if="i===0" viewBox="0 0 280 130" role="img" aria-label="底6厘米、对应高4厘米的三角形示意"><polygon points="30,100 240,100 100,20" fill="#dce8da" stroke="#285a48"/><path d="M100 20V100" stroke="#285a48" stroke-dasharray="4"/><text x="125" y="123">底 6 厘米</text><text x="105" y="60">高 4 厘米</text></svg><p>{{ text }}</p></figure></div>
  <button v-if="d.stage==='source'" @click="previewCapture">查看预写识别结果</button>
  <section v-if="d.stage==='preview'" class="f-card">
    <h3>{{ d.kind==='ink'?'补充题意，保持原笔迹':d.kind==='voice'?'先听清你要问什么':'核对题面中的局部疑点' }}</h3>
    <p v-if="d.kind==='voice'">合成原话：{{ voiceOriginal }}。原转写：{{ d.transcript }}。此处不播放声音。</p><p v-else-if="d.kind!=='ink'">预写识别把高“4”写成“1”。对照原页核对这处即可；原作答是否正确尚未判断。</p><p v-else>未运行手写识别。请用文字补充题意；笔迹会与这次提交一起保留。</p>
    <label class="f-field">{{ d.kind==='voice'?'准备发送的文字':'确认后的题意' }}<textarea v-model="d.prompt" aria-label="确认后的输入" @input="d.checked=false"/></label>
    <label v-if="d.kind!=='voice'" class="f-field">原作答内容<textarea v-model="d.answer" aria-label="核对原作答" @input="d.checked=false"/></label>
    <label v-if="d.kind==='images'||d.kind==='pdf'" class="f-check-line"><input type="checkbox" v-model="d.sameQuestion"/> 这两页属于同一道题</label>
    <label class="f-check-line"><input type="checkbox" v-model="d.checked"/> 我已核对准备发送的内容</label>
    <div class="f-actions"><button class="f-secondary" :disabled="!canUse" @click="use">用于这次求助，暂不发送</button><button @click="selectCapture(d.kind)">{{ d.kind==='voice'?'取消并重新录音演示':'取消本次输入' }}</button></div><p class="f-muted">核对输入不等于提供解题帮助，也不形成新的正确或错误表现。回到求助区后仍由你点击提交。</p>
  </section><p v-if="captureWarning.text" role="status">{{ captureWarning.text }}</p>
</details>
</template>
