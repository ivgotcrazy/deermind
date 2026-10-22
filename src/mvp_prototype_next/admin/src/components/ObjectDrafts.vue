<script setup lang="ts">
import { computed } from 'vue';
import { state } from '../workbench/store';
import { kinds, type Kind } from '../workbench/model';
import { editDraft } from '../workbench/ui';
const props=defineProps<{kind?:Kind;domain?:string;parent?:string}>();
const rows=computed(()=>state.drafts.filter(d=>(!props.kind||d.object.kind===props.kind)&&(!props.domain||d.object.domainId===props.domain)&&(!props.parent||d.object.relations.some(r=>r.ref.split('@')[0]===props.parent))));
</script>
<template><details v-if="rows.length" class="panel"><summary>未保存到目录的草稿（{{rows.length}}）</summary><div v-for="d in rows" :key="d.id" class="list-row"><button class="text-link" @click="editDraft(d.id)">{{d.object.name||'未命名'+kinds[d.object.kind]}}</button><span class="muted">{{d.sourceIssueId?'原有草稿，未自动生效':'本地草稿'}}</span></div></details></template>
