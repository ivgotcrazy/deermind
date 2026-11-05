<script setup lang="ts">
import type { ParsedElement } from '../model/material-flow';
import ReviewBlockView from './ReviewBlockView.vue';
defineProps<{element:ParsedElement}>();
</script>
<template><section class="parsed-element-view"><h4>{{element.title}}</h4><ReviewBlockView v-for="block in element.blocks" :key="block.id" :block="block"/><p v-if="element.pending" class="callout amber">{{element.pending}}</p></section></template>
<style scoped>h4{font-size:14px;margin:10px 0}.parsed-element-view{min-width:0}</style>
