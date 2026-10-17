<script setup lang="ts">
import { computed, ref } from 'vue';
import { checkInputs, openInputCheck, closeInputCheck, confirmInputCheck, type InputCheck } from '../checkInputState';
const props=defineProps<{context:string;draft:string}>();
const emit=defineEmits<{apply:[text:string,entry:InputCheck]}>();
const panel=computed(()=>checkInputs.panels[props.context]);const notice=ref('');
function apply(){const entry=confirmInputCheck(props.context);if(entry){emit('apply',entry.corrected,entry);notice.value='核对已保存，仍是当前题的未提交草稿；没有提供解题提示，也没有结束检测。';}}
</script>
<template><section class="f-check-input">
 <button v-if="!panel?.open" @click="openInputCheck(context,draft);notice=''">核对输入，不要解题提示</button>
 <div v-else class="f-card"><h3>只核对刚才录入的内容</h3><p class="f-muted">当前为文本核对走查，未运行识别。下面保留打开核对时的草稿；你确认的是原意是否记录准确，不是答案是否正确。</p><details><summary>查看核对前的输入</summary><p>{{ panel.original||'原草稿为空' }}</p></details>
  <label class="f-field">核对后的作答文字<textarea v-model="panel.corrected" aria-label="核对后的作答文字" @input="panel.confirmed=false"/></label>
  <label class="f-field">哪里录入不符？<textarea v-model="panel.reason" aria-label="检测输入核对说明" placeholder="例如：我写的是 7，录入时变成了 1。" @input="panel.confirmed=false"/></label>
  <label class="f-check-line"><input type="checkbox" v-model="panel.confirmed"/> 我只是在核对输入是否符合原意，没有请求解题提示</label>
  <div class="f-actions"><button class="f-secondary" :disabled="!panel.confirmed||!panel.corrected.trim()||!panel.reason.trim()" @click="apply">保留核对，返回作答</button><button @click="closeInputCheck(context)">取消核对，保留原草稿</button></div><p class="f-muted">修改说明会保留。原型不判断更改是否仅属识别核对，也不因此认证作答独立性；需要讲解时使用本题的求助入口。</p>
 </div><p v-if="notice&&!panel?.open" role="status" class="f-notice">{{ notice }}</p>
</section></template>
