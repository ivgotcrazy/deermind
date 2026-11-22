<script setup lang="ts">
import { computed, useId } from 'vue';
import type { Diagram } from './types';

const { diagram } = defineProps<{ diagram: Diagram }>();

const descriptionId = useId();
const shapeLabels = {
  circle: '圆',
  ellipse: '椭圆',
  triangle: '三角形',
  square: '正方形',
  pentagon: '五边形',
  hexagon: '六边形',
  point: '点',
};
const basisLabels = {
  source_text: '原文',
  source_mark: '原图标记',
  visual_observation: '原图所见',
};
const objects = computed(
  () => new Map(diagram.objects.map((object) => [object.object_id, object])),
);
const boxes = computed(() =>
  diagram.layout.boxes.flatMap((layout) => {
    const object = objects.value.get(layout.object_ref);
    if (!object) return [];
    const [x, y, width, height] = layout.box;
    if (x === undefined || y === undefined || width === undefined || height === undefined)
      return [];
    return [{ ...object, x, y, width, height, cx: x + width / 2, cy: y + height / 2 }];
  }),
);
const points = computed(() =>
  diagram.layout.points.flatMap((layout) => {
    const object = objects.value.get(layout.object_ref);
    if (!object) return [];
    const [x, y] = layout.position;
    if (x === undefined || y === undefined) return [];
    return [{ ...object, x, y }];
  }),
);

// 多边形布局只提供轮廓，不产生边长和角度的数学条件。
const outlines = {
  triangle: [
    [0.42, 0],
    [1, 1],
    [0, 1],
  ],
  pentagon: [
    [0.42, 0],
    [1, 0.36],
    [0.83, 1],
    [0.17, 0.98],
    [0, 0.42],
  ],
  hexagon: [
    [0.26, 0],
    [0.74, 0.05],
    [1, 0.45],
    [0.79, 1],
    [0.18, 0.95],
    [0, 0.49],
  ],
};

function polygonPoints(box: (typeof boxes.value)[number]) {
  if (box.shape !== 'triangle' && box.shape !== 'pentagon' && box.shape !== 'hexagon') return '';
  return outlines[box.shape]
    .map(([x = 0, y = 0]) => `${box.x + box.width * x},${box.y + box.height * y}`)
    .join(' ');
}

function label(id: string) {
  const object = objects.value.get(id);
  return object && (object.label || shapeLabels[object.shape]);
}

const relationDescriptions = computed(() =>
  diagram.relations
    .map(
      ({ subject, object, basis }) =>
        `${label(subject)}在${label(object)}内（${basisLabels[basis]}）`,
    )
    .join('。'),
);
</script>

<template>
  <figure data-diagram>
    <figcaption>{{ diagram.caption }}</figcaption>
    <svg
      :viewBox="diagram.layout.view_box.join(' ')"
      role="img"
      :aria-label="diagram.caption"
      :aria-describedby="relationDescriptions ? descriptionId : undefined"
    >
      <title>{{ diagram.caption }}</title>
      <desc v-if="relationDescriptions" :id="descriptionId">{{ relationDescriptions }}</desc>
      <g v-for="box in boxes" :key="box.object_id">
        <circle
          v-if="box.shape === 'circle'"
          data-shape="circle"
          :cx="box.cx"
          :cy="box.cy"
          :r="box.width / 2"
        />
        <ellipse
          v-else-if="box.shape === 'ellipse'"
          data-shape="ellipse"
          :cx="box.cx"
          :cy="box.cy"
          :rx="box.width / 2"
          :ry="box.height / 2"
        />
        <rect
          v-else-if="box.shape === 'square'"
          data-shape="square"
          :x="box.x"
          :y="box.y"
          :width="box.width"
          :height="box.height"
        />
        <polygon v-else :data-shape="box.shape" :points="polygonPoints(box)" />
        <text v-if="box.label" :x="box.cx" :y="box.y + box.height + 17" text-anchor="middle">
          {{ box.label }}
        </text>
      </g>
      <g v-for="point in points" :key="point.object_id">
        <circle data-shape="point" data-mark :cx="point.x" :cy="point.y" r="2.8" />
        <text v-if="point.label" :x="point.x + 7" :y="point.y + 4">{{ point.label }}</text>
      </g>
    </svg>
  </figure>
</template>

<style scoped>
figure {
  margin: 0;
}

figcaption {
  margin-bottom: 0.375rem;
  font-weight: 600;
}

svg {
  display: block;
  width: 100%;
  background: #f6f8f5;
}

[data-shape] {
  fill: none;
  stroke: var(--color-accent);
  stroke-width: 2px;
}

[data-mark] {
  fill: #a44b38;
  stroke: none;
}

text {
  fill: currentColor;
  font-size: 14px;
}
</style>
