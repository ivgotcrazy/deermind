<script setup lang="ts">
import { computed } from 'vue';
import type { MasteryTrendPoint } from '../types';

const props = defineProps<{
  data: MasteryTrendPoint[];
  width?: number;
  height?: number;
}>();

const W = computed(() => props.width || 300);
const H = computed(() => props.height || 120);
const pad = { top: 15, right: 15, bottom: 25, left: 30 };
const innerW = computed(() => W.value - pad.left - pad.right);
const innerH = computed(() => H.value - pad.top - pad.bottom);

const points = computed(() => {
  const n = props.data.length;
  return props.data.map((d, i) => ({
    x: pad.left + (i / (n - 1)) * innerW.value,
    y: pad.top + (1 - d.mastery / 100) * innerH.value,
    date: d.date,
    mastery: d.mastery,
  }));
});

const linePath = computed(() => points.value.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x},${p.y}`).join(' '));
const areaPath = computed(() => {
  const first = points.value[0];
  const last = points.value[points.value.length - 1];
  return `${linePath.value} L${last.x},${pad.top + innerH.value} L${first.x},${pad.top + innerH.value} Z`;
});

const yTicks = [0, 25, 50, 75, 100];
</script>

<template>
  <svg :width="W" :height="H" class="trend-chart">
    <!-- Y轴刻度 -->
    <text v-for="t in yTicks" :key="t"
      :x="pad.left - 5" :y="pad.top + (1 - t/100) * innerH + 3"
      text-anchor="end" class="tick-label">{{ t }}</text>
    <line v-for="t in yTicks" :key="'line'+t"
      :x1="pad.left" :y1="pad.top + (1 - t/100) * innerH"
      :x2="pad.left + innerW" :y2="pad.top + (1 - t/100) * innerH"
      stroke="#f0f4f7" stroke-width="1" />
    <!-- 面积 -->
    <path :d="areaPath" fill="url(#trendGradient)" />
    <defs>
      <linearGradient id="trendGradient" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#2d6a4f" stop-opacity="0.3" />
        <stop offset="100%" stop-color="#2d6a4f" stop-opacity="0.02" />
      </linearGradient>
    </defs>
    <!-- 折线 -->
    <path :d="linePath" fill="none" stroke="#2d6a4f" stroke-width="2" stroke-linejoin="round" />
    <!-- 数据点 -->
    <circle v-for="p in points" :key="p.date"
      :cx="p.x" :cy="p.y" r="3.5" fill="#fff" stroke="#2d6a4f" stroke-width="2" />
    <!-- X轴标签 -->
    <text v-for="p in points" :key="'x'+p.date"
      :x="p.x" :y="H - 6" text-anchor="middle" class="tick-label">{{ p.date }}</text>
  </svg>
</template>

<style scoped>
.trend-chart { display: block; width: 100%; }
.tick-label { font-size: 9px; fill: #8a99a8; }
</style>
