<script setup lang="ts">
import { ref, computed } from 'vue';
import { canAccess, recordAccess, act, mode } from '../workbench/store';
const props=defineProps<{subject:string}>();const purpose=ref('');const allowed=computed(()=>canAccess(props.subject,mode.value));
</script>
<template><slot v-if="allowed"/><section v-else class="panel access-gate"><h3>记录本次查看用途</h3><p>查看对象：{{subject}}。只查与当前抽查或维护事项有关的个人记录。</p><label>用途<textarea v-model="purpose" placeholder="例如：核对本次求助后的评价是否使用了实际帮助记录"/></label><button class="btn primary" @click="act(()=>recordAccess(subject,purpose,mode))">记录用途并查看</button><p class="muted">此处为本地原型的访问记录，不代表已实现正式身份认证和服务端授权。</p></section></template>
