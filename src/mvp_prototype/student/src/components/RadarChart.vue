<script setup lang="ts">
import { computed } from 'vue';
import type { AbilityDimension } from '../types';

const props = defineProps<{
  abilities: AbilityDimension[];
  size?: number;
}>();

const size = computed(() => props.size || 200);
const center = computed(() => size.value / 2);
const radius = computed(() => size.value / 2 - 30);

const points = computed(() => {
  const n = props.abilities.length;
  return props.abilities.map((a, i) => {
    const angle = (Math.PI * 2 * i) / n - Math.PI / 2;
    const r = (a.score / 100) * radius.value;
    return {
      x: center.value + r * Math.cos(angle),
      y: center.value + r * Math.sin(angle),
      labelX: center.value + (radius.value + 18) * Math.cos(angle),
      labelY: center.value + (radius.value + 18) * Math.sin(angle),
      name: a.name,
      score: a.score,
    };
  });
});

const gridLevels = [20, 40, 60, 80, 100];

function gridPolygon(level: number): string {
  const n = props.abilities.length;
  const r = (level / 100) * radius.value;
  return props.abilities.map((_, i) => {
    const angle = (Math.PI * 2 * i) / n - Math.PI / 2;
    return `${center.value + r * Math.cos(angle)},${center.value + r * Math.sin(angle)}`;
  }).join(' ');
}

function axisLine(i: number): string {
  const angle = (Math.PI * 2 * i) / props.abilities.length - Math.PI / 2;
  return `${center.value},${center.value} ${center.value + radius.value * Math.cos(angle)},${center.value + radius.value * Math.sin(angle)}`;
}
</script>

<template>
  <svg :width="size" :height="size" class="radar-chart">
    <!-- 网格 -->
    <polygon v-for="level in gridLevels" :key="level"
      :points="gridPolygon(level)"
      fill="none" stroke="#e1e8ed" stroke-width="1" />
    <!-- 轴线 -->
    <line v-for="(_, i) in abilities" :key="'axis'+i"
      :x1="center" :y1="center"
      :x2="center + radius * Math.cos(Math.PI * 2 * i / abilities.length - Math.PI/2)"
      :y2="center + radius * Math.sin(Math.PI * 2 * i / abilities.length - Math.PI/2)"
      stroke="#e1e8ed" stroke-width="1" />
    <!-- 数据多边形 -->
    <polygon :points="points.map(p => `${p.x},${p.y}`).join(' ')"
      fill="rgba(45,106,79,0.2)" stroke="#2d6a4f" stroke-width="2" />
    <!-- 数据点 -->
    <circle v-for="p in points" :key="'dot'+p.name"
      :cx="p.x" :cy="p.y" r="4" fill="#2d6a4f" />
    <!-- 标签 -->
    <text v-for="p in points" :key="'label'+p.name"
      :x="p.labelX" :y="p.labelY"
      text-anchor="middle" dominant-baseline="middle"
      class="radar-label">
      {{ p.name }} {{ p.score }}
    </text>
  </svg>
</template>

<style scoped>
.radar-chart { display: block; margin: 0 auto; }
.radar-label { font-size: 10px; fill: #5a6b7a; }
</style>
