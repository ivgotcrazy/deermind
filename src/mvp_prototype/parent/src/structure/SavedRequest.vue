<script setup lang="ts">
import { computed } from 'vue';
import { state } from './state';
const props=defineProps<{scope:string;available:boolean}>();
defineEmits<{materials:[]}>();
const lastRequest=computed(()=>state.messages[props.scope]?.at(-1));
</script>
<template>
   <section v-if="lastRequest" class="home-request" aria-label="刚刚提出的问题">
    <div class="section-title"><h2>你刚刚提出的问题</h2><span class="tag">已保存 · 尚未处理</span></div>
    <p v-if="lastRequest.text" class="request-text">{{ lastRequest.text }}</p><img v-if="lastRequest.attachment" :src="lastRequest.attachment.data" :alt="lastRequest.attachment.name" class="request-image"/>
    <p class="muted small">此处输入目前只在本地保存，尚未识别图片或理解请求。选择已开放章节后，可进入真实对话。</p><button v-if="available" @click="$emit('materials')">从教材选择讲解内容</button>
   </section>


</template>
